import random
import sqlite3
from datetime import date, timedelta

import pytest

from awaken.engine import items
from awaken.engine.habits import Habit, HabitType, Periodicity
from awaken.engine.player import Player
from awaken.engine.state import GameState
from awaken.persistence import repository, schema

MONDAY = date(2026, 9, 28)


class AlwaysLoot(random.Random):
    def random(self):
        return 0.0


def rich_state() -> GameState:
    """Um jogo com um pouco de tudo: hábitos de vários tipos, dias fechados, Skills, loot, pausa, penalty."""
    s = GameState(player=Player("Jin", hp=40, gold=900), created_on=MONDAY)
    study = s.add_habit(Habit("Study Japanese", HabitType.TIMER, "C", {"INT": 0.6, "WIS": 0.3, "TEN": 0.1},
                              target=60, tags=["language"], streak_threshold=0.8), MONDAY)
    water = s.add_habit(Habit("Water", HabitType.QUANTITY, "E", {"VIT": 1.0}, target=2.0, unit="L"), MONDAY)
    s.add_habit(Habit("Social media", HabitType.LIMIT, "B", {"TEN": 0.7, "PER": 0.3}, target=0), MONDAY)
    s.add_habit(Habit("Gym", HabitType.COUNTER, "A", {"STR": 0.6, "END": 0.4}, target=3,
                      periodicity=Periodicity.WEEKLY), MONDAY)
    rng = AlwaysLoot(7)
    for i in range(9):
        day = MONDAY + timedelta(days=i)
        s.record(study, day, 60)
        s.record(water, day, 1.5)
        s.close_day(day, rng)
    s.player.hp = 20                               # pouco HP antes de...
    s.catch_up(MONDAY + timedelta(days=11), rng)   # ...2 dias sem registos → entra na Penalty Zone
    s.pause(MONDAY + timedelta(days=20), MONDAY + timedelta(days=22))
    s.inventory[items.Item.XP_SCROLL] = 2
    s.player.free_points = 4
    return s


def roundtrip(state: GameState) -> GameState:
    conn = repository.connect(":memory:")
    repository.save(conn, state)
    return repository.load(conn)


def test_full_roundtrip_preserves_everything():
    original = rich_state()
    assert original.skills and original.player.in_penalty_zone and original.penalty_quest  # o cenário é rico
    loaded = roundtrip(original)
    assert loaded == original


def test_roundtrip_of_a_brand_new_game():
    s = GameState(player=Player("Jin"), created_on=MONDAY)
    assert roundtrip(s) == s


def test_loaded_game_keeps_playing_identically():
    a = rich_state()
    b = roundtrip(a)
    day = a.last_closed_day + timedelta(days=1)
    for s in (a, b):
        s.record(1, day, 45)
        s.close_day(day, random.Random(3))
    assert a == b


def test_saving_twice_replaces_instead_of_duplicating():
    conn = repository.connect(":memory:")
    s = rich_state()
    repository.save(conn, s)
    repository.save(conn, s)
    assert conn.execute("SELECT COUNT(*) FROM habits").fetchone()[0] == 4
    assert repository.load(conn) == s


def test_failed_save_leaves_previous_save_intact():
    conn = repository.connect(":memory:")
    good = rich_state()
    repository.save(conn, good)
    broken = rich_state()
    broken.inventory[items.Item.HP_POTION] = -1          # viola CHECK (quantity >= 0)
    with pytest.raises(sqlite3.IntegrityError):
        repository.save(conn, broken)
    assert repository.load(conn) == good                  # a transação foi revertida por inteiro


def test_foreign_keys_are_enforced():
    conn = repository.connect(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("INSERT INTO logs VALUES (999, '2026-01-01', 1, 0, 0, 0, 0, NULL)")


def test_empty_database():
    conn = repository.connect(":memory:")
    assert not repository.has_game(conn)
    with pytest.raises(LookupError):
        repository.load(conn)


def test_schema_version_and_idempotent_migration(tmp_path):
    path = tmp_path / "awaken.db"
    conn = repository.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == schema.LATEST_VERSION
    repository.save(conn, rich_state())
    conn.close()
    conn = repository.connect(path)            # voltar a abrir não reaplica migrações nem perde dados
    assert repository.load(conn) == rich_state()


def test_refuses_database_from_newer_app(tmp_path):
    path = tmp_path / "future.db"
    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {schema.LATEST_VERSION + 1}")
    raw.close()
    with pytest.raises(RuntimeError, match="newer"):
        repository.connect(path)


def test_settings():
    conn = repository.connect(":memory:")
    assert repository.get_setting(conn, "pin_hash") is None
    repository.set_setting(conn, "pin_hash", "abc")
    repository.set_setting(conn, "pin_hash", "def")
    assert repository.get_setting(conn, "pin_hash") == "def"


def test_default_path_uses_appdata_on_windows(monkeypatch, tmp_path):
    from awaken.persistence import paths
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.default_db_path() == tmp_path / "AwakenSystem" / "awaken.db"
    assert (tmp_path / "AwakenSystem").is_dir()


def test_migration_from_v1_keeps_existing_habits(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(schema.MIGRATIONS[0] + "PRAGMA user_version = 1;")   # base de dados da versão 1
    raw.execute("INSERT INTO habits VALUES (1, 'Read', 'check', 'C', 1.0, 'daily', 1.0, 4, '2026-09-28')")
    raw.execute("INSERT INTO habit_weights VALUES (1, 'WIS', 1.0)")
    raw.commit()
    raw.close()

    conn = repository.connect(path)                         # aplica as migrações v2 e v3
    assert conn.execute("PRAGMA user_version").fetchone()[0] == schema.LATEST_VERSION
    streak, archived = conn.execute("SELECT streak, archived FROM habits WHERE id = 1").fetchone()
    assert (streak, archived) == (4, 0)                      # dados antigos intactos, coluna nova com default


def test_archived_flag_roundtrip():
    s = rich_state()
    s.archive_habit(2)
    assert roundtrip(s).habits[2].archived
