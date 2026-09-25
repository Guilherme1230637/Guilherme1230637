"""Períodos de tempo: dia, semana (segunda a domingo) e mês (secções 2.2 e 8)."""

import calendar
from datetime import date, timedelta

from .habits import Periodicity


def period_start(day: date, periodicity: Periodicity) -> date:
    """Primeiro dia do período que contém `day`. Serve de chave para os registos."""
    if periodicity == Periodicity.DAILY:
        return day
    if periodicity == Periodicity.WEEKLY:
        return day - timedelta(days=day.weekday())  # weekday(): segunda = 0
    return day.replace(day=1)


def period_end(day: date, periodicity: Periodicity) -> date:
    """Último dia do período que contém `day`."""
    if periodicity == Periodicity.DAILY:
        return day
    if periodicity == Periodicity.WEEKLY:
        return period_start(day, periodicity) + timedelta(days=6)
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def closes_on(day: date, periodicity: Periodicity) -> bool:
    """True se o período termina neste dia (é avaliado no fecho deste dia)."""
    return period_end(day, periodicity) == day


def days_of_period(day: date, periodicity: Periodicity) -> list[date]:
    start, end = period_start(day, periodicity), period_end(day, periodicity)
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]
