"""Hábitos: percentagem de cumprimento, recompensas e penalizações (secções 2.1–2.6 e 3.3)."""

import math
from dataclasses import dataclass, field
from enum import Enum

from . import config


class HabitType(Enum):
    CHECK = "check"          # Sim/Não
    QUANTITY = "quantity"    # ex.: 2 L de água
    COUNTER = "counter"      # ex.: 3× alongamentos
    TIMER = "timer"          # ex.: 60 min de estudo
    LIMIT = "limit"          # negativo: ex.: máx. 60 min de redes sociais


class Periodicity(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


WEIGHT_TOLERANCE = 1e-6


def validate_weights(weights: dict[str, float]) -> None:
    """Os pesos têm de usar atributos válidos, ser positivos e somar 100 % (1.0)."""
    if not weights:
        raise ValueError("A habit needs at least one attribute.")
    unknown = set(weights) - set(config.ATTRIBUTES)
    if unknown:
        raise ValueError(f"Unknown attributes: {sorted(unknown)}")
    if any(w <= 0 for w in weights.values()):
        raise ValueError("Attribute weights must be positive.")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=WEIGHT_TOLERANCE):
        raise ValueError("Attribute weights must add up to 100%.")


@dataclass
class Habit:
    name: str
    habit_type: HabitType
    rank: str
    attribute_weights: dict[str, float]
    target: float = 1.0                    # alvo (litros, vezes, minutos) ou limite, nos LIMIT
    periodicity: Periodicity = Periodicity.DAILY
    streak_threshold: float = 1.0          # % mínima para o dia contar para a streak
    streak: int = 0
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.rank not in config.HABIT_RANKS:
            raise ValueError(f"Unknown habit rank: {self.rank}")
        if not 0 < self.streak_threshold <= 1:
            raise ValueError("Streak threshold must be in ]0, 1].")
        if self.habit_type == HabitType.LIMIT:
            if self.target < 0:
                raise ValueError("A limit cannot be negative.")
        elif self.target <= 0:
            raise ValueError("Target must be positive.")
        validate_weights(self.attribute_weights)


def completion_ratio(habit: Habit, value: float) -> float:
    """Percentagem de cumprimento r ∈ [0, 1] para o valor registado."""
    if value < 0:
        raise ValueError("Value cannot be negative.")
    if habit.habit_type == HabitType.CHECK:
        return 1.0 if value >= 1 else 0.0
    if habit.habit_type == HabitType.LIMIT:
        limit = habit.target
        if value <= limit:
            return 1.0
        if limit == 0:            # caso especial: limite 0 → qualquer valor é falha total
            return 0.0
        return max(0.0, 1 - (value - limit) / limit)
    # QUANTITY, COUNTER, TIMER: proporcional ao alvo, sem passar de 100 %
    return min(value / habit.target, 1.0)


def xp_multiplier(streak_days: int, skills_bonus: float, rank_bonus: float, xp_scroll: bool = False) -> float:
    """(1 + bónus de streak + bónus de Skills + bónus de ranking) × pergaminho de XP."""
    streak = min(streak_days * config.STREAK_BONUS_PER_DAY, config.STREAK_BONUS_MAX)
    skills = min(skills_bonus, config.SKILLS_BONUS_MAX)
    multiplier = 1 + streak + skills + rank_bonus
    return multiplier * (config.XP_SCROLL_MULTIPLIER if xp_scroll else 1)


@dataclass(frozen=True)
class Reward:
    xp: int
    gold: int
    attributes: dict[str, float]


def reward_for_progress(habit: Habit, old_ratio: float, new_ratio: float, multiplier: float) -> Reward:
    """Recompensa por passar de old_ratio para new_ratio (pode ser negativa, se o registo for corrigido para baixo).

    Calcula round(total(new)) − round(total(old)) em vez de arredondar cada incremento. Assim, 3 incrementos
    de 1/3 dão exatamente o mesmo que um único registo a 100 % (sem acumular erros de arredondamento).
    """
    values = config.HABIT_RANKS[habit.rank]
    xp = round(values.xp * new_ratio * multiplier) - round(values.xp * old_ratio * multiplier)
    gold = round(values.gold * new_ratio) - round(values.gold * old_ratio)  # o Gold não leva bónus
    delta = new_ratio - old_ratio
    attributes = {attr: values.stat_points * weight * delta for attr, weight in habit.attribute_weights.items()}
    return Reward(xp, gold, attributes)


def hp_penalty(habit: Habit, final_ratio: float) -> int:
    """HP perdido no fecho do período: proporcional ao que faltou cumprir."""
    return round(config.HABIT_RANKS[habit.rank].hp_penalty * (1 - final_ratio))


def counts_for_streak(habit: Habit, ratio: float) -> bool:
    return ratio >= habit.streak_threshold - WEIGHT_TOLERANCE


def next_streak(habit: Habit, final_ratio: float, shield: bool = False) -> tuple[int, bool]:
    """Streak depois de fechar o período. Devolve (nova streak, se o Streak Shield foi gasto)."""
    if counts_for_streak(habit, final_ratio):
        return habit.streak + 1, False
    if shield and habit.streak > 0:
        return habit.streak, True
    return 0, False
