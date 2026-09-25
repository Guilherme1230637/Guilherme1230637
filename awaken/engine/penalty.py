"""Penalty Quest (secção 4): tarefa obrigatória gerada ao entrar na Penalty Zone."""

import math
import random
from dataclasses import dataclass
from datetime import date

RANK_ORDER = ("E", "D", "C", "B", "A", "S")

PENALTY_TASKS = {
    "E": ("Do 20 push-ups", "Walk 2 km", "Read 10 pages"),
    "D": ("Do 50 push-ups", "Run 2 km", "Study for 30 minutes"),
    "C": ("Do 100 push-ups", "Run 5 km", "Study for 60 minutes"),
    "B": ("Do 150 push-ups and 100 squats", "Run 8 km", "Study for 90 minutes"),
    "A": ("Do 100 push-ups, 100 sit-ups and 100 squats", "Run 10 km", "Study for 2 hours"),
    "S": ("Do 100 push-ups, 100 sit-ups, 100 squats and run 10 km", "Study for 3 hours without your phone"),
}


@dataclass
class PenaltyQuest:
    task: str
    rank: str
    due: date          # tem de ser cumprida até ao fim deste dia (24 h)


def penalty_rank(habit_ranks: list[str]) -> str:
    """Rank igual ou superior ao rank médio dos hábitos (média arredondada para cima)."""
    if not habit_ranks:
        return "E"
    average = sum(RANK_ORDER.index(r) for r in habit_ranks) / len(habit_ranks)
    return RANK_ORDER[math.ceil(average)]


def generate(habit_ranks: list[str], due: date, rng: random.Random) -> PenaltyQuest:
    rank = penalty_rank(habit_ranks)
    return PenaltyQuest(rng.choice(PENALTY_TASKS[rank]), rank, due)
