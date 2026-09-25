import random
from datetime import date, timedelta

import pytest

from awaken.engine import config, items, penalty, periods
from awaken.engine.habits import Habit, HabitType, Periodicity
from awaken.engine.player import Player
from awaken.engine.skills import Skill, TableSkillNamer, SkillTrigger, TriggerKind
from awaken.engine.state import GameState

MONDAY = date(2026, 9, 28)  # uma segunda-feira


class NoLoot(random.Random):
    """Nunca há drop (random() = 0.999…), para testes que não querem loot."""
    def random(self):
        return 0.999999


class AlwaysLoot(random.Random):
    """Há sempre drop e sai sempre o primeiro item da tabela (HP Potion)."""
    def random(self):
        return 0.0


def new_state(**player_kw) -> GameState:
    return GameState(player=Player("Jin", **player_kw), created_on=MONDAY)


def add(state, habit_type=HabitType.CHECK, target=1.0, rank="C", periodicity=Periodicity.DAILY,
        weights=None, **kw) -> int:
    habit = Habit("Quest", habit_type, rank, weights or {"STR": 1.0}, target=target,
                  periodicity=periodicity, **kw)
    return state.add_habit(habit, MONDAY)


# ---------------- períodos ----------------
def test_periods():
    wed = MONDAY + timedelta(days=2)
    assert periods.period_start(wed, Periodicity.WEEKLY) == MONDAY
    assert periods.period_end(wed, Periodicity.WEEKLY) == MONDAY + timedelta(days=6)
    assert periods.period_end(date(2028, 2, 10), Periodicity.MONTHLY) == date(2028, 2, 29)  # ano bissexto
    assert periods.closes_on(date(2026, 9, 30), Periodicity.MONTHLY)
    assert not periods.closes_on(wed, Periodicity.WEEKLY)


# ---------------- registo ----------------
def test_record_gives_reward_and_corrections_are_exact():
    s = new_state()
    h = add(s, HabitType.QUANTITY, target=2)
    r1 = s.record(h, MONDAY, 1.0)
    r2 = s.record(h, MONDAY, 2.0)
    assert r1.reward.xp + r2.reward.xp == 35          # rank C, streak 0
    s.record(h, MONDAY, 0.0)
    assert s.player.xp_into_level == 0 and s.player.gold == 0


def test_record_on_closed_period_is_rejected():
    s = new_state()
    h = add(s)
    s.close_day(MONDAY, NoLoot())
    with pytest.raises(ValueError, match="closed"):
        s.record(h, MONDAY, 1)


def test_first_quest_unlocks_first_step():
    s = new_state()
    h = add(s)
    s.record(h, MONDAY, 1)
    report = s.close_day(MONDAY, NoLoot())
    assert "first_step" in {a.id for a in report.achievements}


def test_xp_scroll_doubles_the_next_three_quests():
    s = new_state()
    s.inventory[items.Item.XP_SCROLL] = 1
    s.use_item(items.Item.XP_SCROLL, NoLoot())
    ids = [add(s) for _ in range(4)]
    xps = [s.record(i, MONDAY, 1).reward.xp for i in ids]
    assert xps == [70, 70, 70, 35]


# ---------------- hábitos negativos ----------------
def test_limit_habit_rewarded_only_on_close():
    s = new_state()
    h = add(s, HabitType.LIMIT, target=60)
    assert s.record(h, MONDAY, 30).reward.xp == 0
    s.close_day(MONDAY, NoLoot())
    assert s.player.xp_into_level == 35 and s.player.hp == 100


def test_limit_habit_exceeded_costs_hp():
    s = new_state()
    h = add(s, HabitType.LIMIT, target=60)
    s.record(h, MONDAY, 90)                       # r = 0.5
    report = s.close_day(MONDAY, NoLoot())
    assert report.hp_lost == round(12 * 0.5)


# ---------------- fecho do dia e catch-up ----------------
def test_days_must_be_closed_in_order():
    s = new_state()
    with pytest.raises(ValueError, match="order"):
        s.close_day(MONDAY + timedelta(days=1), NoLoot())


def test_catch_up_processes_every_missed_day():
    s = new_state()
    add(s, rank="C")                               # falhar custa 12 HP por dia
    reports = s.catch_up(MONDAY + timedelta(days=3), NoLoot())
    assert [r.day for r in reports] == [MONDAY + timedelta(days=i) for i in range(3)]
    assert s.player.hp == 100 - 3 * 12             # dia a 0 % → regenera 15 × 0 = 0
    assert s.catch_up(MONDAY + timedelta(days=3), NoLoot()) == []   # nada mais por fechar


def test_perfect_day_heals_and_counts():
    s = new_state(hp=50)
    h = add(s)
    s.record(h, MONDAY, 1)
    report = s.close_day(MONDAY, NoLoot())
    assert report.healed == config.HP_REGEN_PER_DAY + config.PERFECT_DAY_HP_BONUS   # 15 + 5
    assert s.stats.perfect_day_streak == 1


def test_regen_is_proportional_to_daily_completion():
    s = new_state(hp=50)
    a, b = add(s, rank="E"), add(s, HabitType.QUANTITY, target=2, rank="E")
    s.record(a, MONDAY, 1)
    s.record(b, MONDAY, 1)                          # 50 %  → média (100 % + 50 %) / 2 = 75 %
    report = s.close_day(MONDAY, NoLoot())
    assert report.hp_lost == round(5 * 0.5)        # dano primeiro...
    assert report.healed == round(15 * 0.75)       # ...depois regenera 11
    assert s.stats.perfect_day_streak == 0


def test_no_regen_in_penalty_zone_or_paused_days():
    s = new_state(hp=5)
    add(s)                                          # falhar custa 12 → entra na Penalty Zone
    report = s.close_day(MONDAY, NoLoot())
    assert report.entered_penalty_zone and report.healed == 0
    s2 = new_state(hp=50)
    add(s2)
    s2.pause(MONDAY, MONDAY)
    assert s2.close_day(MONDAY, NoLoot()).healed == 0


def test_full_regen_without_daily_habits():
    s = new_state(hp=50)
    add(s, periodicity=Periodicity.WEEKLY)
    assert s.close_day(MONDAY, NoLoot()).healed == config.HP_REGEN_PER_DAY


# ---------------- Penalty Zone ----------------
def test_penalty_zone_cycle():
    s = new_state(hp=10, gold=1000)
    add(s, rank="C")
    report = s.close_day(MONDAY, NoLoot())
    assert report.entered_penalty_zone and s.player.in_penalty_zone
    assert s.penalty_quest.due == MONDAY + timedelta(days=1)

    failed = s.close_day(MONDAY + timedelta(days=1), NoLoot())      # não cumpriu no prazo
    assert failed.penalty_quest_failed
    assert s.penalty_quest.due == MONDAY + timedelta(days=2)

    unlocked = s.complete_penalty_quest()
    assert not s.player.in_penalty_zone and s.penalty_quest is None
    assert "The One Who Overcame Adversity" in s.unlocked_titles
    assert "survivor" in {a.id for a in unlocked}


def test_penalty_rank_is_ceiling_of_average():
    assert penalty.penalty_rank([]) == "E"
    assert penalty.penalty_rank(["E", "C"]) == "D"    # média 1,0 → D
    assert penalty.penalty_rank(["E", "D"]) == "D"    # média 0,5 → arredonda para cima
    assert penalty.penalty_rank(["S", "S"]) == "S"


# ---------------- pausa ----------------
def test_paused_day_costs_nothing():
    s = new_state()
    add(s)
    s.pause(MONDAY, MONDAY)
    report = s.close_day(MONDAY, NoLoot())
    assert report.paused and report.hp_lost == 0 and report.ratios == {}


def test_pause_scales_weekly_target():
    s = new_state()
    h = add(s, HabitType.COUNTER, target=7, periodicity=Periodicity.WEEKLY)
    s.pause(MONDAY, MONDAY + timedelta(days=1))    # 2 dias em pausa → alvo 7 × 5/7 = 5
    s.record(h, MONDAY + timedelta(days=3), 5)
    reports = s.catch_up(MONDAY + timedelta(days=7), NoLoot())
    assert reports[-1].ratios[h] == 1.0


def test_cannot_pause_closed_days():
    s = new_state()
    s.close_day(MONDAY, NoLoot())
    with pytest.raises(ValueError):
        s.pause(MONDAY, MONDAY)


def test_habit_created_mid_week_has_proportional_target():
    s = new_state()
    thursday = MONDAY + timedelta(days=3)
    habit = Habit("Gym", HabitType.COUNTER, "C", {"STR": 1.0}, target=7, periodicity=Periodicity.WEEKLY)
    h = s.add_habit(habit, thursday)               # só 4 dias ativos → alvo 4
    s.record(h, thursday, 4)
    reports = s.catch_up(MONDAY + timedelta(days=7), NoLoot())
    assert reports[-1].ratios[h] == 1.0


# ---------------- streaks, loot e itens ----------------
def test_streak_shield_is_used_automatically():
    s = new_state()
    h = add(s)
    s.habits[h].streak = 5
    s.inventory[items.Item.STREAK_SHIELD] = 1
    report = s.close_day(MONDAY, NoLoot())
    assert report.shields_used == [h] and s.habits[h].streak == 5
    assert s.inventory[items.Item.STREAK_SHIELD] == 0


def test_completed_quest_can_drop_loot():
    s = new_state()
    h = add(s)
    s.record(h, MONDAY, 1)
    report = s.close_day(MONDAY, AlwaysLoot())
    assert report.loot == [items.Item.HP_POTION]
    assert s.inventory[items.Item.HP_POTION] == 1


def test_items():
    s = new_state(hp=50)
    s.inventory = {items.Item.HP_POTION: 1, items.Item.GOLD_POUCH: 1, items.Item.STREAK_SHIELD: 1}
    s.use_item(items.Item.HP_POTION, NoLoot())
    assert s.player.hp == 80
    s.use_item(items.Item.GOLD_POUCH, random.Random(1))
    assert 50 <= s.player.gold <= 200
    with pytest.raises(ValueError, match="automatically"):
        s.use_item(items.Item.STREAK_SHIELD, NoLoot())
    with pytest.raises(ValueError, match="no HP Potion"):
        s.use_item(items.Item.HP_POTION, NoLoot())


# ---------------- Skills ----------------
def test_skill_unlocks_after_ten_completions_and_boosts_xp():
    s = new_state()
    h = add(s, weights={"INT": 1.0})
    day = MONDAY
    for _ in range(10):
        s.record(h, day, 1)
        report = s.close_day(day, NoLoot())
        day += timedelta(days=1)
    assert [sk.trigger_id for sk in report.new_skills] == [f"habit:{h}:10"]
    # a streak de 7 dias já tinha gerado outra Skill ao dia 7
    assert sorted(sk.trigger_id for sk in s.skills) == [f"habit:{h}:10", f"streak:{h}:7"]
    assert all(sk.linked_habit_id == h and sk.name for sk in s.skills)
    # streak 10 (+10 %) + 2 Skills Lv1 (+2 % cada) → 35 × 1,14 = 39,9 → 40
    assert s.record(h, day, 1).reward.xp == 40


def test_skill_proficiency_levels():
    sk = Skill("Iron Body", "", "x", 1, None)
    assert sk.gain_proficiency(9.5) == 0
    assert sk.gain_proficiency(0.5) == 1 and sk.level == 2      # 10 para o Lv2
    assert sk.gain_proficiency(20) == 1 and sk.level == 3       # 20 para o Lv3
    assert sk.gain_proficiency(10_000) == 7 and sk.level == 10  # teto Lv10
    assert sk.gain_proficiency(50) == 0


def test_table_namer_never_repeats_names():
    namer = TableSkillNamer(random.Random(0))
    trigger = SkillTrigger(TriggerKind.ATTRIBUTE, "STR", 25, "STR")
    taken: set[str] = set()
    for _ in range(20):                               # 16 combinações → depois vêm os "II"
        name, _ = namer.name(trigger, taken)
        assert name not in taken
        taken.add(name)
    assert any(n.endswith(" II") for n in taken)


# ---------------- relatório semanal ----------------
def test_weekly_report_on_sunday():
    s = new_state()
    good = s.add_habit(Habit("Read", HabitType.CHECK, "C", {"WIS": 1.0}), MONDAY)
    bad = s.add_habit(Habit("Run", HabitType.CHECK, "C", {"AGI": 1.0}), MONDAY)
    for i in range(7):
        day = MONDAY + timedelta(days=i)
        s.record(good, day, 1)
        report = s.close_day(day, NoLoot())
    weekly = report.weekly_report
    assert weekly and weekly.week_start == MONDAY
    assert weekly.completion_by_habit == {"Read": 1.0, "Run": 0.0}
    assert (weekly.best_habit, weekly.worst_habit) == ("Read", "Run")
    assert weekly.hp_lost == 7 * 12 and weekly.xp_earned > 0
    assert s.week.xp_earned == 0                       # nova semana começa do zero


# ---------------- edição e arquivo ----------------
def test_update_habit_validates_before_changing():
    s = new_state()
    h = add(s)
    s.update_habit(h, name="Push-ups", rank="B")
    assert (s.habits[h].name, s.habits[h].rank) == ("Push-ups", "B")
    with pytest.raises(ValueError):
        s.update_habit(h, attribute_weights={"STR": 0.5})   # não soma 100 %
    assert s.habits[h].attribute_weights == {"STR": 1.0}    # o original ficou intacto
    with pytest.raises(ValueError):
        s.update_habit(h, streak=99)


def test_archived_habit_is_ignored_but_history_kept():
    s = new_state()
    h = add(s)
    s.record(h, MONDAY, 1)
    s.archive_habit(h)
    report = s.close_day(MONDAY, NoLoot())
    assert report.ratios == {} and report.hp_lost == 0
    assert s.value_of(h, MONDAY) == 1
    assert s.active_habits() == []
    with pytest.raises(ValueError, match="archived"):
        s.record(h, MONDAY + timedelta(days=1), 1)


def test_weight_templates_are_valid():
    from awaken.engine.habits import validate_weights
    from awaken.engine.templates import WEIGHT_TEMPLATES
    for weights in WEIGHT_TEMPLATES.values():
        validate_weights(weights)
