"""Ranking de cultivação: breakthroughs, estrelas e estágios (secção 3.7)."""

from dataclasses import dataclass

from . import config
from .leveling import total_xp_to_reach

RANKS = config.CULTIVATION_RANKS


class BreakthroughError(Exception):
    """Tentativa de breakthrough sem cumprir os requisitos."""


@dataclass(frozen=True)
class BreakthroughResult:
    rank_index: int
    gold: int
    bonus_points: int


def next_rank(rank_index: int) -> config.CultivationRank | None:
    """Ranking seguinte, ou None se já estás no último (Supreme)."""
    return RANKS[rank_index + 1] if rank_index + 1 < len(RANKS) else None


def breakthrough_blocker(rank_index: int, level: int, gold: int, in_penalty_zone: bool) -> str | None:
    """Motivo pelo qual o breakthrough não é possível, ou None se é possível."""
    target = next_rank(rank_index)
    if target is None:
        return "Already at the highest rank."
    if in_penalty_zone:
        return "Breakthroughs are locked while in the Penalty Zone."
    if level < target.min_level:
        return f"Requires level {target.min_level}."
    if gold < target.gold_cost:
        return f"Requires {target.gold_cost} Gold."
    return None


def breakthrough(rank_index: int, level: int, gold: int, in_penalty_zone: bool = False) -> BreakthroughResult:
    """Sobe UM ranking (nunca salta) e paga o Gold."""
    blocker = breakthrough_blocker(rank_index, level, gold, in_penalty_zone)
    if blocker:
        raise BreakthroughError(blocker)
    target = RANKS[rank_index + 1]
    return BreakthroughResult(rank_index + 1, gold - target.gold_cost, target.bonus_points)


def _rank_end_level(rank_index: int) -> int:
    """Nível onde acaba o caminho do ranking: o do ranking seguinte, ou +15 no último."""
    following = next_rank(rank_index)
    return following.min_level if following else RANKS[rank_index].min_level + config.RANK_LEVEL_SPAN


def subdivision(rank_index: int, level: int, xp_into_level: int) -> int | None:
    """Estrela (1–5) ou estágio (1–10) atual: fração do caminho em XP até ao próximo ranking.

    progresso  = (XP total atual − XP total no início do ranking) / (XP total no fim − XP total no início)
    subdivisão = min(floor(progresso × N) + 1, N)
    """
    rank = RANKS[rank_index]
    if rank.divisions == 0:
        return None
    start = total_xp_to_reach(rank.min_level)
    end = total_xp_to_reach(_rank_end_level(rank_index))
    progress = (total_xp_to_reach(level) + xp_into_level - start) / (end - start)
    progress = max(progress, 0.0)
    return min(int(progress * rank.divisions) + 1, rank.divisions)


def rank_label(rank_index: int, level: int, xp_into_level: int) -> str:
    """Texto para a UI, ex.: '★3 Silver' ou 'Heavenly Fate · Stage 4'."""
    rank = RANKS[rank_index]
    division = subdivision(rank_index, level, xp_into_level)
    if division is None:
        return rank.name
    if rank.divisions == config.STARS:
        return f"★{division} {rank.name}"
    return f"{rank.name} · Stage {division}"
