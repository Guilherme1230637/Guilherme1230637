"""Camada de serviço: o único ponto de contacto entre a interface e o jogo.

A UI pede ações ("regista 1,5 L de água"); o serviço aplica as regras do motor, grava na base de dados e
devolve Notificações para a UI mostrar. Assim a UI só trata do aspeto visual, e tudo o resto é testável sem janelas.
"""

import json
import random
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from ..engine import items
from ..engine.achievements import Achievement
from ..engine.habits import Habit
from ..engine.player import Player
from ..engine.report import WeeklyReport
from ..engine.skills import SkillNamer, TableSkillNamer
from ..engine.state import DayReport, GameState
from ..persistence import repository

LAST_REPORT_KEY = "last_weekly_report"


class Clock(Protocol):
    def today(self) -> date: ...


class SystemClock:
    def today(self) -> date:
        return date.today()


class Kind(Enum):
    LEVEL_UP = "level_up"
    SKILL = "skill"
    LOOT = "loot"
    ACHIEVEMENT = "achievement"
    PENALTY = "penalty"
    BREAKTHROUGH = "breakthrough"
    REPORT = "report"
    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True)
class Notification:
    kind: Kind
    title: str
    message: str


class GameService:
    def __init__(self, conn: sqlite3.Connection, clock: Clock | None = None, rng: random.Random | None = None,
                 namer_factory: Callable[[random.Random], SkillNamer] | None = None):
        self.conn = conn
        self.clock = clock or SystemClock()
        self.rng = rng or random.Random()
        self.namer_factory = namer_factory or TableSkillNamer
        self.state: GameState | None = None

    @classmethod
    def open(cls, path: str | Path, **kwargs) -> "GameService":
        return cls(repository.connect(path), **kwargs)

    # ---------------- ciclo de vida ----------------
    @property
    def today(self) -> date:
        return self.clock.today()

    def has_game(self) -> bool:
        return repository.has_game(self.conn)

    def new_game(self, name: str) -> list[Notification]:
        name = name.strip()
        if not name:
            raise ValueError("Please enter a name.")
        self.state = GameState(player=Player(name), created_on=self.today)
        self._save()
        return [Notification(Kind.INFO, "[SYSTEM]", f"You have acquired the qualifications to be a Player, {name}.")]

    def load(self) -> list[Notification]:
        """Carrega o jogo e fecha os dias que passaram enquanto a app esteve fechada."""
        self.state = repository.load(self.conn)
        return self.tick()

    def tick(self) -> list[Notification]:
        """Chamado ao abrir e periodicamente (ex.: a cada minuto): trata a passagem da meia-noite."""
        reports = self.state.catch_up(self.today, self.rng, self.namer_factory(self.rng))
        if not reports:
            return []
        self._save()
        for r in reports:
            if r.weekly_report:
                repository.set_setting(self.conn, LAST_REPORT_KEY, _report_to_json(r.weekly_report))
        return _summarize(reports, self.state)

    def _save(self) -> None:
        repository.save(self.conn, self.state)

    # ---------------- hábitos ----------------
    def add_habit(self, habit: Habit) -> int:
        habit_id = self.state.add_habit(habit, self.today)
        self._save()
        return habit_id

    def update_habit(self, habit_id: int, **changes) -> None:
        self.state.update_habit(habit_id, **changes)
        self._save()

    def archive_habit(self, habit_id: int) -> None:
        self.state.archive_habit(habit_id)
        self._save()

    def value(self, habit_id: int) -> float:
        return self.state.value_of(habit_id, self.today)

    def ratio(self, habit_id: int) -> float:
        return self.state.ratio_of(habit_id, self.today)

    def record(self, habit_id: int, value: float) -> list[Notification]:
        before_level = self.state.player.level
        result = self.state.record(habit_id, self.today, value)
        self._save()
        notes = []
        if result.levels_gained:
            notes.append(Notification(Kind.LEVEL_UP, "LEVEL UP!",
                                      f"Level {before_level} → {self.state.player.level}. "
                                      f"+{3 * result.levels_gained} free points."))
        notes += [_achievement_note(a) for a in result.achievements]
        return notes

    # ---------------- personagem ----------------
    def spend_free_point(self, attribute: str) -> None:
        self.state.player.spend_free_point(attribute)
        self._save()

    def breakthrough(self) -> list[Notification]:
        unlocked = self.state.breakthrough()
        self._save()
        rank = self.state.player.rank
        return [Notification(Kind.BREAKTHROUGH, "BREAKTHROUGH!",
                             f"You have reached {rank.name} Rank. +{rank.bonus_points} free points, "
                             f"+{rank.xp_bonus:.0%} XP on all quests.")] + [_achievement_note(a) for a in unlocked]

    def use_item(self, item: items.Item) -> list[Notification]:
        message = self.state.use_item(item, self.rng)
        self._save()
        return [Notification(Kind.LOOT, item.value, message)]

    def complete_penalty_quest(self) -> list[Notification]:
        unlocked = self.state.complete_penalty_quest()
        self._save()
        return [Notification(Kind.INFO, "[SYSTEM]", "Penalty Quest cleared. You have left the Penalty Zone.")] + \
               [_achievement_note(a) for a in unlocked]

    def set_title(self, title: str | None) -> None:
        self.state.set_title(title)
        self._save()

    def pause(self, start: date, end: date) -> None:
        self.state.pause(start, end)
        self._save()

    def last_weekly_report(self) -> WeeklyReport | None:
        raw = repository.get_setting(self.conn, LAST_REPORT_KEY)
        return _report_from_json(raw) if raw else None


# ---------------- notificações do fecho do dia ----------------
def _achievement_note(a: Achievement) -> Notification:
    extra = f' Title unlocked: "{a.title}".' if a.title else ""
    return Notification(Kind.ACHIEVEMENT, f"Achievement: {a.name}", a.description + extra)


def _summarize(reports: list[DayReport], state: GameState) -> list[Notification]:
    """Junta os relatórios de vários dias num número pequeno de notificações (o catch-up pode fechar muitos dias)."""
    names = {h.id: h.name for h in state.habits.values()}
    notes: list[Notification] = []
    hp_lost = sum(r.hp_lost for r in reports)
    days = len(reports)
    header = "Yesterday" if days == 1 else f"The last {days} days"
    if hp_lost:
        notes.append(Notification(Kind.WARNING, "[SYSTEM] Unfinished quests", f"{header}: -{hp_lost} HP."))
    broken = [names[h] for r in reports for h in r.streaks_broken]
    if broken:
        notes.append(Notification(Kind.WARNING, "Streak lost", ", ".join(sorted(set(broken)))))
    shielded = [names[h] for r in reports for h in r.shields_used]
    if shielded:
        notes.append(Notification(Kind.LOOT, "Streak Shield used", ", ".join(shielded)))
    loot = Counter(i.value for r in reports for i in r.loot)
    if loot:
        notes.append(Notification(Kind.LOOT, "Loot acquired", ", ".join(f"{n}× {i}" for i, n in loot.items())))
    for r in reports:
        if r.entered_penalty_zone:
            notes.append(Notification(Kind.PENALTY, "[PENALTY ZONE]",
                                      "Your HP reached 0. Breakthroughs are locked until you clear the Penalty Quest."))
        if r.penalty_quest_failed:
            notes.append(Notification(Kind.PENALTY, "[PENALTY] Quest failed", "A new Penalty Quest was issued."))
        if r.new_penalty_quest:
            q = r.new_penalty_quest
            notes.append(Notification(Kind.PENALTY, f"Penalty Quest (Rank {q.rank})",
                                      f"{q.task} — before the end of {q.due:%d/%m}."))
        notes += [Notification(Kind.SKILL, f"New Skill: {s.name}", s.description) for s in r.new_skills]
        notes += [Notification(Kind.SKILL, "Skill Level Up", f"{name} → Lv.{lv}") for name, lv in r.skill_level_ups]
        notes += [_achievement_note(a) for a in r.achievements]
        if r.weekly_report:
            notes.append(Notification(Kind.REPORT, "[SYSTEM] Weekly Report",
                                      f"Your report for the week of {r.weekly_report.week_start:%d/%m} is ready."))
    return notes


def _report_to_json(report: WeeklyReport) -> str:
    data = asdict(report)
    data["week_start"] = report.week_start.isoformat()
    return json.dumps(data)


def _report_from_json(raw: str) -> WeeklyReport:
    data = json.loads(raw)
    data["week_start"] = date.fromisoformat(data["week_start"])
    return WeeklyReport(**data)
