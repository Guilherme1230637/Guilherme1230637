import pytest

from awaken.engine import config, cultivation

BRONZE, SILVER, HEAVENLY_FATE, SUPREME = 1, 2, 6, 13


def test_rank_table_is_ordered_every_15_levels():
    levels = [r.min_level for r in config.CULTIVATION_RANKS[1:]]
    assert levels == list(range(10, 191, 15))
    assert [r.name for r in config.CULTIVATION_RANKS][-1] == "Supreme"


def test_breakthrough_pays_gold_and_gives_bonus_points():
    result = cultivation.breakthrough(rank_index=0, level=10, gold=800)
    assert result == cultivation.BreakthroughResult(rank_index=BRONZE, gold=300, bonus_points=5)


def test_breakthrough_requires_level():
    with pytest.raises(cultivation.BreakthroughError, match="level 10"):
        cultivation.breakthrough(0, level=9, gold=10_000)


def test_breakthrough_requires_gold():
    with pytest.raises(cultivation.BreakthroughError, match="500 Gold"):
        cultivation.breakthrough(0, level=10, gold=499)


def test_breakthrough_locked_in_penalty_zone():
    with pytest.raises(cultivation.BreakthroughError, match="Penalty Zone"):
        cultivation.breakthrough(0, level=10, gold=500, in_penalty_zone=True)


def test_breakthrough_never_skips_ranks():
    # nível 40 dava para Gold, mas a partir de Unranked só se sobe para Bronze
    assert cultivation.breakthrough(0, level=40, gold=50_000).rank_index == BRONZE


def test_no_breakthrough_after_supreme():
    assert cultivation.next_rank(SUPREME) is None
    with pytest.raises(cultivation.BreakthroughError, match="highest"):
        cultivation.breakthrough(SUPREME, level=999, gold=10**9)


def test_unranked_has_no_subdivision():
    assert cultivation.subdivision(0, level=5, xp_into_level=0) is None
    assert cultivation.rank_label(0, 5, 0) == "Unranked"


@pytest.mark.parametrize(
    "level, star",
    [(10, 1), (14, 1), (15, 2), (17, 2), (18, 3), (20, 3), (21, 4), (22, 4), (23, 5), (24, 5)],
)
def test_bronze_stars_match_spec_example(level, star):
    assert cultivation.subdivision(BRONZE, level, 0) == star


@pytest.mark.parametrize("level, stage", [(85, 1), (86, 1), (87, 2), (92, 5), (99, 10)])
def test_heavenly_fate_stages_match_spec_example(level, stage):
    assert cultivation.subdivision(HEAVENLY_FATE, level, 0) == stage


def test_subdivision_caps_when_next_rank_not_paid():
    # nível 30 já passou o Silver (25), mas continua Bronze → fica em ★5, nunca ★6
    assert cultivation.subdivision(BRONZE, level=30, xp_into_level=0) == 5


def test_supreme_uses_a_15_level_span():
    assert cultivation.subdivision(SUPREME, 190, 0) == 1
    assert cultivation.subdivision(SUPREME, 204, 0) == 10
    assert cultivation.subdivision(SUPREME, 400, 0) == 10


def test_labels():
    assert cultivation.rank_label(SILVER, 25, 0) == "★1 Silver"
    assert cultivation.rank_label(HEAVENLY_FATE, 99, 0) == "Heavenly Fate · Stage 10"
