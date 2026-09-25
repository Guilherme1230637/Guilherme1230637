"""Lembretes de horário (secção 10).

Função pura: dado o intervalo de tempo desde a última verificação, diz que hábitos devem ser lembrados.
Um lembrete dispara uma vez por dia, à hora marcada, e só se o hábito ainda não estiver cumprido.
"""

from datetime import datetime
from typing import Callable

from ..engine.habits import Habit


def due_reminders(habits: list[Habit], last_check: datetime, now: datetime,
                  ratio_of: Callable[[int], float]) -> list[Habit]:
    """Hábitos cujo lembrete de hoje calhou em ]last_check, now] e que ainda não estão a 100 %."""
    due = []
    for habit in habits:
        if habit.archived or habit.reminder is None:
            continue
        moment = datetime.combine(now.date(), habit.reminder)
        if last_check < moment <= now and ratio_of(habit.id) < 1:
            due.append(habit)
    return due
