import pytest

from awaken.engine import config, leveling
from awaken.engine.cultivation import BreakthroughError
from awaken.engine.habits import Reward
from awaken.engine.player import Player


def test_new_player_matches_spec():
    p = Player("Jin")
    assert (p.level, p.hp, p.max_hp, p.gold, p.rank.name, p.hunter_rank) == (1, 100, 100, 0, "Unranked", "E")
    assert set(p.attributes.values()) == {10.0} and len(p.attributes) == 9


def test_reward_levels_up_and_grants_free_points():
    p = Player("Jin")
    xp = leveling.xp_to_next_level(1) + leveling.xp_to_next_level(2)  # 102 + 106
    gained = p.apply_reward(Reward(xp=xp, gold=40, attributes={"INT": 0.5}))
    assert (gained, p.level, p.free_points, p.gold) == (2, 3, 6, 40)
    assert p.attributes["INT"] == 10.5


def test_negative_correction_never_drops_below_start_values():
    p = Player("Jin", xp_into_level=10, gold=5)
    p.apply_reward(Reward(xp=-50, gold=-50, attributes={"INT": -3}))
    assert (p.xp_into_level, p.gold, p.attributes["INT"]) == (0, 0, 10.0)


def test_vitality_raises_max_hp():
    p = Player("Jin", free_points=4)
    p.spend_free_point("VIT", 4)
    assert (p.max_hp, p.hp) == (120, 120)


def test_cannot_spend_more_points_than_available():
    with pytest.raises(ValueError):
        Player("Jin", free_points=1).spend_free_point("STR", 2)


def test_penalty_zone_entry_and_exit():
    p = Player("Jin", level=10, xp_into_level=100, gold=1000, hp=10)
    assert p.take_damage(15) is True
    assert p.in_penalty_zone and p.hp == 0
    assert p.xp_into_level == 100 - round(163 * config.PENALTY_XP_LOSS)  # perde 10 % do XP do nível 10
    assert p.level == 10  # nunca desce de nível
    assert p.gold == 800  # perde 20 %

    with pytest.raises(BreakthroughError, match="Penalty Zone"):
        p.breakthrough()

    p.complete_penalty_quest()
    assert not p.in_penalty_zone and p.hp == 50


def test_heal_is_capped_and_blocked_in_penalty_zone():
    p = Player("Jin", hp=90)
    p.heal(30)
    assert p.hp == 100
    p.take_damage(100)
    p.heal(30)
    assert p.hp == 0


def test_breakthrough_through_player():
    p = Player("Jin", level=10, gold=600)
    assert p.breakthrough().name == "Bronze"
    assert (p.gold, p.free_points, p.rank_label) == (100, 5, "★1 Bronze")
