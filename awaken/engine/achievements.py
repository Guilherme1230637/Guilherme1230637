"""Achievements e Títulos (secções 3.8 e 6.3)."""

from dataclasses import dataclass, field
from typing import Callable

LANGUAGE_TAG = "language"


@dataclass
class Stats:
    """Contadores históricos usados por Skills, Achievements e relatórios."""
    total_completions: int = 0
    completions_by_habit: dict[int, int] = field(default_factory=dict)
    completions_by_attribute: dict[str, int] = field(default_factory=dict)
    minutes_by_tag: dict[str, float] = field(default_factory=dict)
    perfect_day_streak: int = 0
    best_perfect_day_streak: int = 0
    best_habit_streak: int = 0
    penalty_entries: int = 0
    penalty_exits: int = 0


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    condition: Callable[["AchievementContext"], bool]
    title: str | None = None   # alguns achievements desbloqueiam um Título


@dataclass(frozen=True)
class AchievementContext:
    stats: Stats
    level: int
    rank_index: int
    skill_count: int


ACHIEVEMENTS = (
    Achievement("first_step", "First Step", "Complete your first quest.",
                lambda c: c.stats.total_completions >= 1),
    Achievement("week_warrior", "Week Warrior", "7 perfect days in a row.",
                lambda c: c.stats.best_perfect_day_streak >= 7),
    Achievement("month_of_discipline", "Month of Discipline", "30 perfect days in a row.",
                lambda c: c.stats.best_perfect_day_streak >= 30, title="The Disciplined"),
    Achievement("level_10", "Level 10", "Reach level 10.", lambda c: c.level >= 10),
    Achievement("level_40", "Level 40", "Reach level 40.", lambda c: c.level >= 40),
    Achievement("level_100", "Level 100", "Reach level 100.", lambda c: c.level >= 100, title="Centurion"),
    Achievement("first_breakthrough", "Breakthrough", "Reach Bronze rank.", lambda c: c.rank_index >= 1),
    Achievement("survivor", "Survivor", "Escape the Penalty Zone.",
                lambda c: c.stats.penalty_exits >= 1, title="The One Who Overcame Adversity"),
    Achievement("unbreakable", "Unbreakable", "Reach a 66-day streak on any quest.",
                lambda c: c.stats.best_habit_streak >= 66, title="Unbreakable"),
    Achievement("polyglot", "Polyglot", "100 hours of language practice.",
                lambda c: c.stats.minutes_by_tag.get(LANGUAGE_TAG, 0) >= 100 * 60, title="Polyglot"),
    Achievement("skill_collector", "Skill Collector", "Own 10 skills.", lambda c: c.skill_count >= 10),
)


def newly_unlocked(context: AchievementContext, unlocked: set[str]) -> list[Achievement]:
    return [a for a in ACHIEVEMENTS if a.id not in unlocked and a.condition(context)]
