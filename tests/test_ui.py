"""Testes da interface (sem ecrã: plataforma 'offscreen')."""

import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from awaken.engine.habits import Habit, HabitType  # noqa: E402
from awaken.services.game_service import GameService  # noqa: E402
from awaken.ui import widgets  # noqa: E402
from awaken.ui.habit_dialog import HabitDialog  # noqa: E402
from awaken.ui.home import QuestCard  # noqa: E402
from awaken.ui.main_window import MainWindow  # noqa: E402
from awaken.ui.theme import STYLESHEET  # noqa: E402


class FixedClock:
    def today(self):
        return date(2026, 9, 28)


@pytest.fixture(scope="module")
def app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


@pytest.fixture
def service(tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(widgets.SystemPopup, "exec", lambda self: shown.append(self) or 1)  # popups não bloqueiam
    s = GameService.open(tmp_path / "ui.db", clock=FixedClock())
    s.new_game("Jin")
    s.popups = shown
    return s


def test_every_page_renders(app, service):
    service.add_habit(Habit("Read", HabitType.CHECK, "C", {"WIS": 1.0}))
    window = MainWindow(service)
    for row in range(window.sidebar.count()):
        window.sidebar.setCurrentRow(row)
        app.processEvents()
        assert window.stack.currentIndex() == row


def test_completing_a_quest_from_its_card(app, service):
    hid = service.add_habit(Habit("Boss", HabitType.CHECK, "S", {"STR": 1.0}))
    window = MainWindow(service)
    card = window.pages[0].board.findChildren(QuestCard)[0]
    card.check.click()                                       # "Complete"
    assert service.value(hid) == 1
    assert service.state.player.level == 2                  # 120 XP → Level Up
    assert any(p.windowTitle() == "System" for p in service.popups)


def test_counter_card_buttons(app, service):
    hid = service.add_habit(Habit("Stretch", HabitType.COUNTER, "E", {"AGI": 1.0}, target=3))
    window = MainWindow(service)
    card = window.pages[0].board.findChildren(QuestCard)[0]
    plus = [b for b in card.findChildren(QtWidgets.QPushButton) if b.text() == "+1"][0]
    plus.click()
    assert service.value(hid) == 1


def test_habit_dialog_builds_valid_habit(app):
    dialog = HabitDialog()
    dialog.name.setText("Study")
    dialog.type.setCurrentIndex(dialog.type.findData(HabitType.TIMER))
    dialog.target.setValue(60)
    dialog.template.setCurrentIndex(dialog.template.findData("Study"))   # INT 60 / WIS 30 / TEN 10
    habit = dialog.build_habit()
    assert (habit.target, habit.unit) == (60, "min")
    assert habit.attribute_weights == {"INT": 0.6, "WIS": 0.3, "TEN": 0.1}


def test_habit_dialog_rejects_bad_weights(app):
    dialog = HabitDialog()
    dialog.name.setText("Study")
    dialog.weights["INT"].setValue(50)
    dialog._accept()
    assert "100%" in dialog.error.text() and dialog.result() == 0


def test_spending_free_points_from_status(app, service):
    service.state.player.free_points = 1
    window = MainWindow(service)
    window.pages[0].status.attr_buttons["VIT"].click()
    assert service.state.player.attributes["VIT"] == 11 and service.state.player.free_points == 0
