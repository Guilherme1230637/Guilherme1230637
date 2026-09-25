import pytest

from awaken.engine import leveling


@pytest.mark.parametrize(
    "level, expected",
    [(1, 102), (5, 122), (10, 163), (25, 350), (40, 606), (55, 916), (70, 1271), (85, 1667), (100, 2100)],
)
def test_xp_curve_matches_spec_table(level, expected):
    assert leveling.xp_to_next_level(level) == expected


def test_xp_curve_rejects_level_zero():
    with pytest.raises(ValueError):
        leveling.xp_to_next_level(0)


def test_total_xp_is_sum_of_previous_levels():
    assert leveling.total_xp_to_reach(1) == 0
    assert leveling.total_xp_to_reach(2) == 102
    assert leveling.total_xp_to_reach(4) == 102 + leveling.xp_to_next_level(2) + leveling.xp_to_next_level(3)


def test_total_xp_handles_very_high_levels():
    # a versão recursiva rebentava o limite de recursão aqui
    assert leveling.total_xp_to_reach(3000) > 0


def test_add_xp_without_level_up():
    p = leveling.add_xp(1, 0, 50)
    assert (p.level, p.xp_into_level, p.levels_gained, p.free_points_gained) == (1, 50, 0, 0)


def test_add_xp_exact_level_up():
    p = leveling.add_xp(1, 0, 102)
    assert (p.level, p.xp_into_level, p.free_points_gained) == (2, 0, 3)


def test_add_xp_multiple_level_ups_keeps_remainder():
    amount = leveling.xp_to_next_level(1) + leveling.xp_to_next_level(2) + 7
    p = leveling.add_xp(1, 0, amount)
    assert (p.level, p.xp_into_level, p.levels_gained, p.free_points_gained) == (3, 7, 2, 6)


def test_add_xp_rejects_negative():
    with pytest.raises(ValueError):
        leveling.add_xp(1, 0, -5)


def test_remove_xp_never_goes_below_zero():
    assert leveling.remove_xp(30, 10) == 20
    assert leveling.remove_xp(30, 100) == 0


@pytest.mark.parametrize(
    "level, rank",
    [(1, "E"), (9, "E"), (10, "D"), (19, "D"), (20, "C"), (35, "B"), (50, "A"), (69, "A"), (70, "S"),
     (100, "National Level"), (250, "National Level")],
)
def test_hunter_rank_boundaries(level, rank):
    assert leveling.hunter_rank(level) == rank
