from datetime import date, timedelta

import pytest

from awaken.engine.habits import Habit, HabitType
from awaken.services.game_service import GameService, Kind

MONDAY = date(2026, 9, 28)


class FakeClock:
    def __init__(self, day):
        self.day = day

    def today(self):
        return self.day


def service(tmp_path, clock):
    return GameService.open(tmp_path / "awaken.db", clock=clock)


def test_new_game_is_saved_and_reloaded(tmp_path):
    clock = FakeClock(MONDAY)
    s = service(tmp_path, clock)
    assert not s.has_game()
    notes = s.new_game("  Jin ")
    assert "qualifications" in notes[0].message
    hid = s.add_habit(Habit("Read", HabitType.CHECK, "C", {"WIS": 1.0}))
    s.record(hid, 1)

    again = service(tmp_path, clock)
    assert again.has_game()
    again.load()
    assert again.state == s.state


def test_empty_name_rejected(tmp_path):
    with pytest.raises(ValueError):
        service(tmp_path, FakeClock(MONDAY)).new_game("   ")


def test_level_up_notification(tmp_path):
    s = service(tmp_path, FakeClock(MONDAY))
    s.new_game("Jin")
    hid = s.add_habit(Habit("Boss", HabitType.CHECK, "S", {"STR": 1.0}))
    notes = s.record(hid, 1)          # 120 XP > 102 → Level Up
    assert notes[0].kind == Kind.LEVEL_UP and "1 → 2" in notes[0].message


def test_reopening_after_days_away_processes_them(tmp_path):
    clock = FakeClock(MONDAY)
    s = service(tmp_path, clock)
    s.new_game("Jin")
    s.add_habit(Habit("Run", HabitType.CHECK, "C", {"AGI": 1.0}))

    clock.day = MONDAY + timedelta(days=3)          # 3 dias sem abrir a app
    again = service(tmp_path, clock)
    notes = again.load()
    assert again.state.player.hp == 100 - 3 * 12
    assert any(n.kind == Kind.WARNING and "-36 HP" in n.message for n in notes)
    assert again.tick() == []                       # nada novo até mudar o dia


def test_weekly_report_is_stored(tmp_path):
    clock = FakeClock(MONDAY)
    s = service(tmp_path, clock)
    s.new_game("Jin")
    hid = s.add_habit(Habit("Read", HabitType.CHECK, "C", {"WIS": 1.0}))
    for i in range(7):
        clock.day = MONDAY + timedelta(days=i)
        s.tick()
        s.record(hid, 1)
    clock.day = MONDAY + timedelta(days=7)
    notes = s.tick()
    assert any(n.kind == Kind.REPORT for n in notes)
    report = service(tmp_path, clock).last_weekly_report()
    assert report.week_start == MONDAY and report.completion_by_habit == {"Read": 1.0}


def test_breakthrough_notification(tmp_path):
    s = service(tmp_path, FakeClock(MONDAY))
    s.new_game("Jin")
    s.state.player.level, s.state.player.gold = 10, 600
    notes = s.breakthrough()
    assert notes[0].kind == Kind.BREAKTHROUGH and "Bronze" in notes[0].message
