"""GameState: junta a personagem, os hábitos e o histórico, e aplica as regras no tempo.

Duas operações principais:
- `record`   — o jogador regista progresso num hábito (recompensa imediata).
- `close_day` — fecha um dia que já passou: penalizações, streaks, loot, Skills, Achievements, relatório semanal.
`catch_up` fecha, pela ordem, todos os dias que ficaram por fechar enquanto a app esteve fechada (secção 8).
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import achievements as ach
from . import config, items, penalty, periods
from .habits import (
    Habit,
    HabitType,
    Periodicity,
    Reward,
    attribute_gains,
    closing_ratio,
    completion_ratio,
    counts_for_streak,
    hp_penalty,
    next_streak,
    period_totals,
    xp_multiplier,
)
from .player import Player
from .report import WeekAccumulator, WeeklyReport, build_weekly_report
from .skills import Skill, SkillNamer, TableSkillNamer, create_skill, pending_triggers, skills_bonus_for


@dataclass
class LogEntry:
    """Registo de um hábito num período (dia, semana ou mês)."""
    value: float = 0.0
    xp_awarded: int = 0          # guardado para que correções posteriores sejam exatas
    gold_awarded: int = 0
    ratio_rewarded: float = 0.0  # % já convertida em atributos
    boosted: bool = False        # XP Scroll aplicado a este período
    final_ratio: float | None = None  # preenchido no fecho (é o que o calendário mostra)


@dataclass(frozen=True)
class RecordResult:
    ratio: float
    reward: Reward
    levels_gained: int
    achievements: list[ach.Achievement]


@dataclass
class DayReport:
    day: date
    paused: bool
    ratios: dict[int, float] = field(default_factory=dict)
    hp_lost: int = 0
    healed: int = 0
    entered_penalty_zone: bool = False
    new_penalty_quest: penalty.PenaltyQuest | None = None
    penalty_quest_failed: bool = False
    streaks_broken: list[int] = field(default_factory=list)
    shields_used: list[int] = field(default_factory=list)
    loot: list[items.Item] = field(default_factory=list)
    new_skills: list[Skill] = field(default_factory=list)
    skill_level_ups: list[tuple[str, int]] = field(default_factory=list)
    achievements: list[ach.Achievement] = field(default_factory=list)
    weekly_report: WeeklyReport | None = None


@dataclass
class GameState:
    player: Player
    created_on: date
    habits: dict[int, Habit] = field(default_factory=dict)
    logs: dict[tuple[int, date], LogEntry] = field(default_factory=dict)
    skills: list[Skill] = field(default_factory=list)
    awarded_triggers: set[str] = field(default_factory=set)
    inventory: dict[items.Item, int] = field(default_factory=dict)
    xp_scroll_charges: int = 0
    stats: ach.Stats = field(default_factory=ach.Stats)
    unlocked_achievements: set[str] = field(default_factory=set)
    unlocked_titles: list[str] = field(default_factory=list)
    active_title: str | None = None
    penalty_quest: penalty.PenaltyQuest | None = None
    paused_days: set[date] = field(default_factory=set)
    last_closed_day: date | None = None
    week: WeekAccumulator | None = None
    next_habit_id: int = 1

    def __post_init__(self):
        if self.last_closed_day is None:
            self.last_closed_day = self.created_on - timedelta(days=1)
        if self.week is None:
            self.week = WeekAccumulator(start_level=self.player.level)

    # ================= hábitos =================
    def add_habit(self, habit: Habit, today: date) -> int:
        habit.id = self.next_habit_id
        habit.created_on = habit.created_on or today
        self.habits[habit.id] = habit
        self.next_habit_id += 1
        return habit.id

    def active_habits(self) -> list[Habit]:
        return [h for h in self.habits.values() if not h.archived]

    def update_habit(self, habit_id: int, **changes) -> None:
        """Edita um hábito. A validação do Habit volta a correr (ex.: pesos a somar 100 %)."""
        habit = self.habits[habit_id]
        forbidden = {"id", "created_on", "streak", "archived"} & changes.keys()
        if forbidden:
            raise ValueError(f"Cannot change {sorted(forbidden)} directly.")
        candidate = Habit(**{**habit.__dict__, **changes})   # valida antes de alterar o original
        habit.__dict__.update(candidate.__dict__)

    def archive_habit(self, habit_id: int) -> None:
        self.habits[habit_id].archived = True

    def _log_key(self, habit: Habit, day: date) -> tuple[int, date]:
        return habit.id, periods.period_start(day, habit.periodicity)

    def value_of(self, habit_id: int, day: date) -> float:
        entry = self.logs.get(self._log_key(self.habits[habit_id], day))
        return entry.value if entry else 0.0

    def ratio_of(self, habit_id: int, day: date) -> float:
        """% de cumprimento para o calendário: a final se o período já fechou, senão a atual."""
        habit = self.habits[habit_id]
        entry = self.logs.get(self._log_key(habit, day))
        if entry and entry.final_ratio is not None:
            return entry.final_ratio
        return completion_ratio(habit, entry.value if entry else 0.0)

    def _multiplier(self, habit: Habit, boosted: bool) -> float:
        skills = skills_bonus_for(self.skills, habit.id, habit.dominant_attribute)
        return xp_multiplier(habit.streak, skills, self.player.rank.xp_bonus, boosted)

    def _settle(self, habit: Habit, entry: LogEntry, ratio: float) -> tuple[Reward, int]:
        """Acerta as recompensas do período para a % atual, descontando o que já foi atribuído."""
        xp_total, gold_total = period_totals(habit, ratio, self._multiplier(habit, entry.boosted))
        reward = Reward(xp_total - entry.xp_awarded, gold_total - entry.gold_awarded,
                        attribute_gains(habit, ratio - entry.ratio_rewarded))
        entry.xp_awarded, entry.gold_awarded, entry.ratio_rewarded = xp_total, gold_total, ratio
        levels = self.player.apply_reward(reward)
        self.week.xp_earned += reward.xp
        self.week.gold_earned += reward.gold
        return reward, levels

    def record(self, habit_id: int, day: date, value: float) -> RecordResult:
        """Regista o valor total do período (não um incremento) e atribui a diferença de recompensa."""
        habit = self.habits[habit_id]
        if habit.archived:
            raise ValueError("This quest is archived.")
        if periods.period_end(day, habit.periodicity) <= self.last_closed_day:
            raise ValueError("This period is already closed.")
        entry = self.logs.setdefault(self._log_key(habit, day), LogEntry())
        entry.value = value
        ratio = completion_ratio(habit, value)
        if habit.rewarded_on_close:
            return RecordResult(ratio, Reward(0, 0, {}), 0, [])
        if ratio > 0 and not entry.boosted and entry.xp_awarded == 0 and self.xp_scroll_charges > 0:
            self.xp_scroll_charges -= 1
            entry.boosted = True
        reward, levels = self._settle(habit, entry, ratio)
        return RecordResult(ratio, reward, levels, self._check_achievements())

    # ================= fecho do dia =================
    def close_day(self, day: date, rng: random.Random, namer: SkillNamer | None = None) -> DayReport:
        if day != self.last_closed_day + timedelta(days=1):
            raise ValueError("Days must be closed in order, one at a time.")
        namer = namer or TableSkillNamer(rng)
        report = DayReport(day=day, paused=day in self.paused_days)
        damage = 0
        daily_ratios: list[float] = []

        for habit in self.active_habits():
            if not periods.closes_on(day, habit.periodicity):
                continue
            period_days = periods.days_of_period(day, habit.periodicity)
            active = [d for d in period_days
                      if d not in self.paused_days and (habit.created_on is None or d >= habit.created_on)]
            if not active:
                continue  # período todo em pausa (ou antes do hábito existir): não conta
            entry = self.logs.setdefault(self._log_key(habit, day), LogEntry())
            ratio = closing_ratio(habit, entry.value, len(active) / len(period_days))
            entry.final_ratio = ratio
            report.ratios[habit.id] = ratio
            self.week.ratios.setdefault(habit.id, []).append(ratio)
            if habit.periodicity == Periodicity.DAILY:
                daily_ratios.append(ratio)

            if habit.rewarded_on_close:
                self._settle(habit, entry, ratio)
            damage += hp_penalty(habit, ratio)
            self._close_streak(habit, ratio, report)
            if counts_for_streak(habit, ratio):
                self._count_completion(habit, rng, report)
            if ratio > 0:
                self._train_skills(habit, ratio, report)
            if habit.habit_type == HabitType.TIMER:
                for tag in habit.tags:
                    self.stats.minutes_by_tag[tag] = self.stats.minutes_by_tag.get(tag, 0) + entry.value

        self._close_penalty(day, damage, rng, report)   # primeiro o dano (pode levar à Penalty Zone)...
        self._close_regen(report, daily_ratios)          # ...depois a regeneração (não cura na Penalty Zone)
        self._unlock_skills(namer, report)
        report.achievements = self._check_achievements()
        self.last_closed_day = day
        if day.weekday() == 6:  # domingo: fecha a semana
            report.weekly_report = self._close_week(day)
        return report

    def catch_up(self, today: date, rng: random.Random, namer: SkillNamer | None = None) -> list[DayReport]:
        """Fecha, pela ordem, todos os dias completos que ficaram por fechar (até ontem)."""
        reports = []
        while self.last_closed_day < today - timedelta(days=1):
            reports.append(self.close_day(self.last_closed_day + timedelta(days=1), rng, namer))
        return reports

    def _close_streak(self, habit: Habit, ratio: float, report: DayReport) -> None:
        has_shield = self.inventory.get(items.Item.STREAK_SHIELD, 0) > 0
        new_streak, shield_used = next_streak(habit, ratio, has_shield)
        if shield_used:
            self.inventory[items.Item.STREAK_SHIELD] -= 1
            report.shields_used.append(habit.id)
        elif new_streak == 0 and habit.streak > 0:
            report.streaks_broken.append(habit.id)
        habit.streak = new_streak
        self.stats.best_habit_streak = max(self.stats.best_habit_streak, new_streak)

    def _count_completion(self, habit: Habit, rng: random.Random, report: DayReport) -> None:
        self.stats.total_completions += 1
        by_habit, by_attr = self.stats.completions_by_habit, self.stats.completions_by_attribute
        by_habit[habit.id] = by_habit.get(habit.id, 0) + 1
        by_attr[habit.dominant_attribute] = by_attr.get(habit.dominant_attribute, 0) + 1
        loot = items.roll_loot(habit.rank, rng)
        if loot:
            self.inventory[loot] = self.inventory.get(loot, 0) + 1
            report.loot.append(loot)
            self.week.loot.append(loot)

    def _train_skills(self, habit: Habit, ratio: float, report: DayReport) -> None:
        for skill in self.skills:
            if skill.applies_to(habit.id, habit.dominant_attribute):
                gained = skill.gain_proficiency(ratio)
                if gained:
                    report.skill_level_ups.append((skill.name, skill.level))
                    self.week.skill_level_ups += gained

    def _close_regen(self, report: DayReport, daily_ratios: list[float]) -> None:
        """Regeneração diária proporcional ao cumprimento (secção 3.5).

        HP = 15 × % média dos hábitos diários (+5 num dia perfeito). Sem hábitos diários, regenera os 15 completos
        (não havia nada diário para falhar). Dias em pausa não regeneram nem contam para os dias perfeitos.
        """
        if report.paused:
            return
        perfect = bool(daily_ratios) and all(r >= 1 for r in daily_ratios)
        average = sum(daily_ratios) / len(daily_ratios) if daily_ratios else 1.0
        amount = round(config.HP_REGEN_PER_DAY * average) + (config.PERFECT_DAY_HP_BONUS if perfect else 0)
        before = self.player.hp
        self.player.heal(amount)
        report.healed = self.player.hp - before
        if not daily_ratios:
            return
        if perfect:
            self.stats.perfect_day_streak += 1
            self.stats.best_perfect_day_streak = max(self.stats.best_perfect_day_streak,
                                                     self.stats.perfect_day_streak)
        else:
            self.stats.perfect_day_streak = 0

    def _close_penalty(self, day: date, damage: int, rng: random.Random, report: DayReport) -> None:
        ranks = [h.rank for h in self.active_habits()]
        tomorrow = day + timedelta(days=1)
        if self.penalty_quest and self.penalty_quest.due <= day:   # não foi cumprida a tempo
            self.penalty_quest = penalty.generate(ranks, tomorrow, rng)
            report.penalty_quest_failed = True
            report.new_penalty_quest = self.penalty_quest
        before = self.player.hp
        if self.player.take_damage(damage):
            report.entered_penalty_zone = True
            self.stats.penalty_entries += 1
            self.week.penalty_entries += 1
            self.penalty_quest = penalty.generate(ranks, tomorrow, rng)
            report.new_penalty_quest = self.penalty_quest
        report.hp_lost = before - self.player.hp
        self.week.hp_lost += report.hp_lost

    def _unlock_skills(self, namer: SkillNamer, report: DayReport) -> None:
        info = {h.id: (h.name, h.dominant_attribute) for h in self.habits.values()}
        streaks = {h.id: h.streak for h in self.habits.values()}
        triggers = pending_triggers(self.stats.completions_by_habit, self.stats.completions_by_attribute,
                                    streaks, info, self.awarded_triggers)
        for trigger in triggers:
            skill = create_skill(trigger, namer, {s.name for s in self.skills})
            self.skills.append(skill)
            self.awarded_triggers.add(trigger.trigger_id)
            report.new_skills.append(skill)
            self.week.new_skills.append(skill.name)

    def _close_week(self, sunday: date) -> WeeklyReport:
        report = build_weekly_report(
            week_start=sunday - timedelta(days=6),
            acc=self.week,
            current_level=self.player.level,
            habit_names={h.id: h.name for h in self.habits.values()},
            streaks={h.id: h.streak for h in self.habits.values()},
        )
        self.week = WeekAccumulator(start_level=self.player.level)
        return report

    # ================= ações do jogador =================
    def _check_achievements(self) -> list[ach.Achievement]:
        context = ach.AchievementContext(self.stats, self.player.level, self.player.rank_index, len(self.skills))
        new = ach.newly_unlocked(context, self.unlocked_achievements)
        for a in new:
            self.unlocked_achievements.add(a.id)
            if a.title:
                self.unlocked_titles.append(a.title)
        return new

    def complete_penalty_quest(self) -> list[ach.Achievement]:
        if self.penalty_quest is None:
            raise ValueError("There is no Penalty Quest to complete.")
        self.player.complete_penalty_quest()
        self.penalty_quest = None
        self.stats.penalty_exits += 1
        return self._check_achievements()

    def breakthrough(self) -> list[ach.Achievement]:
        self.player.breakthrough()
        return self._check_achievements()

    def use_item(self, item: items.Item, rng: random.Random) -> str:
        if self.inventory.get(item, 0) <= 0:
            raise ValueError(f"You have no {item.value}.")
        if item == items.Item.STREAK_SHIELD:
            raise ValueError("Streak Shields are used automatically when a streak would break.")
        if item == items.Item.HP_POTION:
            if self.player.in_penalty_zone:
                raise ValueError("Potions have no effect in the Penalty Zone. Complete the Penalty Quest.")
            self.player.heal(items.HP_POTION_HEAL)
            message = f"+{items.HP_POTION_HEAL} HP"
        elif item == items.Item.XP_SCROLL:
            self.xp_scroll_charges += items.XP_SCROLL_CHARGES
            message = f"XP ×2 on your next {items.XP_SCROLL_CHARGES} quests"
        else:
            amount = items.gold_pouch_amount(rng)
            self.player.gold += amount
            self.week.gold_earned += amount
            message = f"+{amount} Gold"
        self.inventory[item] -= 1
        return message

    def set_title(self, title: str | None) -> None:
        if title is not None and title not in self.unlocked_titles:
            raise ValueError("Title not unlocked.")
        self.active_title = title

    def pause(self, start: date, end: date) -> None:
        """Modo Pausa (férias, doença): os dias em pausa não contam."""
        if start <= self.last_closed_day:
            raise ValueError("Cannot pause days that are already closed.")
        if end < start:
            raise ValueError("End must be on or after start.")
        self.paused_days.update(start + timedelta(days=i) for i in range((end - start).days + 1))
