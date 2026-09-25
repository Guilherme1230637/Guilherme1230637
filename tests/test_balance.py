"""Testes de equilíbrio: protegem os objetivos de design contra alterações acidentais aos números."""

import importlib.util
from pathlib import Path

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
