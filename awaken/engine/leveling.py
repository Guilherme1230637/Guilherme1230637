"""Níveis, XP e Hunter Rank (secções 3.4 e 3.6)."""

from dataclasses import dataclass
from functools import lru_cache

from . import config


def xp_to_next_level(level: int) -> int:
    """XP necessário para passar do nível `level` para `level + 1`."""
    if level < 1:
        raise ValueError("level must be >= 1")
    return round(config.XP_CURVE_BASE + config.XP_CURVE_COEF * level ** config.XP_CURVE_EXP)


@lru_cache(maxsize=None)
def total_xp_to_reach(level: int) -> int:
    """XP acumulado desde o nível 1 até ao início de `level` (soma de todos os níveis anteriores)."""
    return sum(xp_to_next_level(n) for n in range(1, level))


@dataclass(frozen=True)
class LevelProgress:
    level: int
    xp_into_level: int      # XP já feito dentro do nível atual
    levels_gained: int
    free_points_gained: int


def add_xp(level: int, xp_into_level: int, amount: int) -> LevelProgress:
    """Soma XP e processa todos os Level Ups que isso provocar (pode ser mais do que um)."""
    if amount < 0:
        raise ValueError("use remove_xp for negative amounts")
    xp = xp_into_level + amount
    gained = 0
    while xp >= xp_to_next_level(level):
        xp -= xp_to_next_level(level)
        level += 1
        gained += 1
    return LevelProgress(level, xp, gained, gained * config.FREE_POINTS_PER_LEVEL)


def remove_xp(xp_into_level: int, amount: int) -> int:
    """Retira XP dentro do nível atual. Nunca desce de nível (fica, no mínimo, a 0)."""
    return max(0, xp_into_level - amount)


def hunter_rank(level: int) -> str:
    """Hunter Rank (E → National Level) correspondente ao nível."""
    rank = config.HUNTER_RANKS[0][1]
    for min_level, name in config.HUNTER_RANKS:
        if level >= min_level:
            rank = name
    return rank
