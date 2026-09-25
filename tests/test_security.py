import pytest

from awaken.services import security


def test_hash_never_contains_the_pin_and_is_salted():
    a, b = security.hash_pin("123456"), security.hash_pin("123456")
    assert "123456" not in a
    assert a != b                                   # salts diferentes → hashes diferentes
    assert a.startswith("pbkdf2_sha256$200000$")


def test_verify():
    stored = security.hash_pin("2468")
    assert security.verify_pin("2468", stored)
    assert not security.verify_pin("2469", stored)
    assert not security.verify_pin("2468", "garbage")


def test_known_vector_is_stable():
    # mesmo salt e iterações → mesmo resultado (o formato guardado é reprodutível)
    salt = bytes(16)
    assert security.hash_pin("1234", salt, 1000) == security.hash_pin("1234", salt, 1000)


@pytest.mark.parametrize("pin", ["123", "1234567", "12a4", "", "    "])
def test_invalid_pins(pin):
    with pytest.raises(ValueError):
        security.hash_pin(pin)


def test_lockout_after_five_failures():
    now = [1000.0]
    gate = security.PinGate(security.hash_pin("1111"), clock=lambda: now[0])
    for _ in range(5):
        assert not gate.try_pin("0000")
    assert gate.seconds_locked() == 30
    assert not gate.try_pin("1111")                 # nem o PIN certo entra durante o bloqueio
    now[0] += 30
    assert gate.try_pin("1111")
