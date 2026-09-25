import pytest

from awaken.engine.habits import (
    Habit,
    HabitType,
    completion_ratio,
    hp_penalty,
    next_streak,
    reward_for_progress,
    validate_weights,
    xp_multiplier,
)

STUDY_WEIGHTS = {"INT": 0.6, "WIS": 0.3, "TEN": 0.1}


def make(habit_type, target=1.0, rank="C", weights=None, **kw):
    return Habit("test", habit_type, rank, weights or {"STR": 1.0}, target=target, **kw)


# ---------- validação ----------
def test_weights_must_sum_to_100_percent():
    validate_weights(STUDY_WEIGHTS)
    with pytest.raises(ValueError, match="100%"):
        validate_weights({"INT": 0.6, "WIS": 0.3})


@pytest.mark.parametrize("weights", [{}, {"LUCK": 1.0}, {"INT": 1.2, "WIS": -0.2}])
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        validate_weights(weights)


def test_habit_rejects_unknown_rank_and_bad_target():
    with pytest.raises(ValueError):
        make(HabitType.QUANTITY, rank="Z")
    with pytest.raises(ValueError):
        make(HabitType.QUANTITY, target=0)
    make(HabitType.LIMIT, target=0)  # limite 0 é válido ("Não fumar")


# ---------- percentagem de cumprimento ----------
def test_check():
    h = make(HabitType.CHECK)
    assert completion_ratio(h, 0) == 0 and completion_ratio(h, 1) == 1


def test_quantity_is_proportional_and_capped():
    water = make(HabitType.QUANTITY, target=2.0)
    assert completion_ratio(water, 1.5) == 0.75
    assert completion_ratio(water, 3.0) == 1.0


def test_counter_and_timer():
    assert completion_ratio(make(HabitType.COUNTER, target=3), 2) == pytest.approx(2 / 3)
    assert completion_ratio(make(HabitType.TIMER, target=60), 45) == 0.75


def test_limit_spec_example():
    social = make(HabitType.LIMIT, target=60)
    assert completion_ratio(social, 40) == 1.0
    assert completion_ratio(social, 90) == 0.5   # excesso 30 → 1 − 30/60
    assert completion_ratio(social, 200) == 0.0  # nunca negativo


def test_limit_zero_special_case():
    smoking = make(HabitType.LIMIT, target=0)
    assert completion_ratio(smoking, 0) == 1.0
    assert completion_ratio(smoking, 1) == 0.0   # sem divisão por zero


def test_negative_value_rejected():
    with pytest.raises(ValueError):
        completion_ratio(make(HabitType.QUANTITY, target=2), -1)


# ---------- multiplicador ----------
def test_xp_multiplier_caps():
    assert xp_multiplier(0, 0, 0) == 1
    assert xp_multiplier(10, 0, 0) == pytest.approx(1.10)
    assert xp_multiplier(100, 0.9, 0) == pytest.approx(1 + 0.30 + 0.50)  # tetos de streak e Skills
    assert xp_multiplier(0, 0, 0.06, xp_scroll=True) == pytest.approx(2.12)


# ---------- recompensas ----------
def test_study_example_from_spec():
    study = make(HabitType.TIMER, target=60, rank="C", weights=STUDY_WEIGHTS)
    r = reward_for_progress(study, 0, 1, multiplier=1)
    assert (r.xp, r.gold) == (35, 18)
    assert r.attributes == pytest.approx({"INT": 0.36, "WIS": 0.18, "TEN": 0.06})


def test_partial_completion_gives_partial_reward():
    water = make(HabitType.QUANTITY, target=2, rank="C")
    assert reward_for_progress(water, 0, 0.75, 1).xp == round(35 * 0.75)


def test_incremental_rewards_add_up_exactly():
    stretch = make(HabitType.COUNTER, target=3, rank="C")
    ratios = [0, 1 / 3, 2 / 3, 1]
    steps = [reward_for_progress(stretch, a, b, 1.37) for a, b in zip(ratios, ratios[1:])]
    single = reward_for_progress(stretch, 0, 1, 1.37)
    assert sum(s.xp for s in steps) == single.xp
    assert sum(s.gold for s in steps) == single.gold


def test_correcting_downwards_gives_negative_reward():
    water = make(HabitType.QUANTITY, target=2, rank="C")
    r = reward_for_progress(water, 1.0, 0.5, 1)
    assert r.xp < 0 and r.gold < 0


def test_gold_ignores_multiplier():
    h = make(HabitType.CHECK, rank="S")
    assert reward_for_progress(h, 0, 1, 2.5).gold == 60


# ---------- penalização e streak ----------
def test_hp_penalty_is_proportional_to_missing_part():
    h = make(HabitType.QUANTITY, target=2, rank="C")  # penalização base 12
    assert hp_penalty(h, 1.0) == 0
    assert hp_penalty(h, 0.75) == 3
    assert hp_penalty(h, 0.0) == 12


def test_streak_uses_each_habits_own_threshold():
    water = make(HabitType.QUANTITY, target=2, streak_threshold=0.8, streak=4)
    assert next_streak(water, 0.8) == (5, False)
    assert next_streak(water, 0.79) == (0, False)


def test_streak_shield_protects_one_miss():
    h = make(HabitType.CHECK, streak=10)
    assert next_streak(h, 0, shield=True) == (10, True)
    assert next_streak(make(HabitType.CHECK, streak=0), 0, shield=True) == (0, False)  # não gasta à toa
