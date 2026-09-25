"""Testes de equilíbrio: protegem os objetivos de design contra alterações acidentais aos números."""

import importlib.util
import random
from datetime import date, timedelta
from pathlib import Path

from awaken.engine.habits import Habit, HabitType
from awaken.engine.player import Player
from awaken.engine.state import GameState

_path = Path(__file__).resolve().parent.parent / "tools" / "simular_progressao.py"
_spec = importlib.util.spec_from_file_location("simulador", _path)
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)


def _run(profile: str) -> dict:
    p = sim.PERFIS[profile]
    return sim.simular(p["xp_base"], p["r"])


def _run_level_only(profile: str) -> dict:
    original = sim.MARCOS
    sim.MARCOS = [(name, level, 0) for name, level, _ in original]
    try:
        return _run(profile)
    finally:
        sim.MARCOS = original


def test_regular_player_reaches_gold_rank_in_one_and_a_half_to_two_months():
    assert 45 <= _run("Regular")["Gold"] <= 60


def test_gold_never_delays_regular_or_hardcore_players():
    for profile in ("Regular", "Hardcore"):
        assert _run(profile) == _run_level_only(profile)


def test_gold_delays_casual_players_but_not_for_long():
    with_gold, level_only = _run("Casual"), _run_level_only("Casual")
    delays = [with_gold[k] - level_only[k] for k in level_only if k in with_gold]
    assert max(delays) > 0      # o Gold mede a consistência: quem cumpre pouco espera
    assert max(delays) <= 60    # mas nunca bloqueia durante meses a fio


# ---------------- HP e Penalty Zone (motor real, um ano) ----------------


def penalty_entries_per_year(average_completion: float, seed: int) -> int:
    """6 hábitos diários (E, E, D, C, C, B). Cada dia, cada hábito é cumprido a 100 % com probabilidade q,
    senão fica numa % aleatória — com média `average_completion`. A Penalty Quest é cumprida no dia seguinte."""
    rng = random.Random(seed)
    q = 2 * average_completion - 1
    start = date(2026, 1, 5)
    s = GameState(player=Player("Sim"), created_on=start)
    ids = [s.add_habit(Habit(f"H{i}", HabitType.QUANTITY, r, {"STR": 1.0}, target=1), start)
           for i, r in enumerate("EEDCCB")]
    for i in range(365):
        day = start + timedelta(days=i)
        if s.penalty_quest:
            s.complete_penalty_quest()
        for h in ids:
            s.record(h, day, 1.0 if rng.random() < q else rng.random())
        s.close_day(day, rng)
    return s.stats.penalty_entries


def _average(completion: float) -> float:
    return sum(penalty_entries_per_year(completion, seed) for seed in range(5)) / 5


def test_regular_player_rarely_enters_penalty_zone():
    assert _average(0.80) <= 6          # no máximo ~uma vez a cada 2 meses


def test_hardcore_player_never_enters_penalty_zone():
    assert _average(0.95) == 0


def test_casual_player_is_punished_more_than_regular():
    assert _average(0.65) > 3 * max(_average(0.80), 1)
