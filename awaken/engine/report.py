"""Weekly Report [SYSTEM] (secção 7)."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .items import Item


@dataclass
class WeekAccumulator:
    """Vai somando o que acontece durante a semana; fecha ao domingo."""
    start_level: int
    xp_earned: int = 0
    gold_earned: int = 0
    hp_lost: int = 0
    penalty_entries: int = 0
    ratios: dict[int, list[float]] = field(default_factory=dict)   # id do hábito → % de cada período fechado
    new_skills: list[str] = field(default_factory=list)
    skill_level_ups: int = 0
    loot: list[Item] = field(default_factory=list)


@dataclass(frozen=True)
class WeeklyReport:
    week_start: date
    xp_earned: int
    gold_earned: int
    levels_gained: int
    completion_by_habit: dict[str, float]    # nome → média da % de cumprimento
    overall_completion: float
    best_habit: str | None
    worst_habit: str | None
    streaks: dict[str, int]
    new_skills: list[str]
    skill_level_ups: int
    hp_lost: int
    penalty_entries: int
    loot: dict[str, int]


def build_weekly_report(week_start: date, acc: WeekAccumulator, current_level: int,
                        habit_names: dict[int, str], streaks: dict[int, int]) -> WeeklyReport:
    completion = {habit_names[h]: sum(r) / len(r) for h, r in acc.ratios.items() if r and h in habit_names}
    all_ratios = [r for rs in acc.ratios.values() for r in rs]
    ranked = sorted(completion, key=completion.get)
    return WeeklyReport(
        week_start=week_start,
        xp_earned=acc.xp_earned,
        gold_earned=acc.gold_earned,
        levels_gained=current_level - acc.start_level,
        completion_by_habit=completion,
        overall_completion=sum(all_ratios) / len(all_ratios) if all_ratios else 0.0,
        best_habit=ranked[-1] if ranked else None,
        worst_habit=ranked[0] if ranked else None,
        streaks={habit_names[h]: s for h, s in streaks.items() if h in habit_names},
        new_skills=list(acc.new_skills),
        skill_level_ups=acc.skill_level_ups,
        hp_lost=acc.hp_lost,
        penalty_entries=acc.penalty_entries,
        loot={item.value: n for item, n in Counter(acc.loot).items()},
    )
