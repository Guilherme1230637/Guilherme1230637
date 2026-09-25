"""Gera capturas de ecrã de todas as páginas com um jogo de demonstração (para docs e apresentação).

Uso:  python tools/capturas.py [pasta_de_saida]
Em Linux sem ecrã: QT_QPA_PLATFORM=offscreen python tools/capturas.py
"""

import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from awaken.engine import items  # noqa: E402
from awaken.engine.habits import Habit, HabitType, Periodicity  # noqa: E402
from awaken.services.game_service import GameService  # noqa: E402
from awaken.ui.habit_dialog import HabitDialog  # noqa: E402
from awaken.services import security  # noqa: E402
from awaken.ui.main_window import AwakeningDialog, MainWindow, PinDialog  # noqa: E402
from awaken.ui.theme import STYLESHEET  # noqa: E402
from awaken.ui.widgets import SystemPopup  # noqa: E402

START = date(2026, 9, 7)   # segunda-feira
DAYS = 24


class DemoClock:
    def __init__(self):
        self.day = START

    def today(self):
        return self.day


def _blocked(s: GameService) -> bool:
    from awaken.engine import cultivation
    p = s.state.player
    return cultivation.breakthrough_blocker(p.rank_index, p.level, p.gold, p.in_penalty_zone) is not None


def demo_service(path: Path) -> GameService:
    clock = DemoClock()
    s = GameService.open(path, clock=clock, rng=random.Random(42))
    s.new_game("Guilherme")
    ids = {
        "study": s.add_habit(Habit("Study Japanese", HabitType.TIMER, "C", {"INT": 0.5, "CHA": 0.3, "TEN": 0.2},
                                   target=60, unit="min", tags=["language"])),
        "water": s.add_habit(Habit("Drink water", HabitType.QUANTITY, "E", {"VIT": 1.0}, target=2, unit="L",
                                   streak_threshold=0.8)),
        "pushups": s.add_habit(Habit("100 push-ups", HabitType.COUNTER, "B", {"STR": 0.6, "END": 0.3, "VIT": 0.1},
                                     target=4, unit="sets")),
        "bed": s.add_habit(Habit("Make the bed", HabitType.CHECK, "E", {"TEN": 1.0})),
        "social": s.add_habit(Habit("Social media", HabitType.LIMIT, "B", {"TEN": 0.7, "PER": 0.3},
                                    target=60, unit="min")),
        "gym": s.add_habit(Habit("Gym", HabitType.COUNTER, "A", {"STR": 0.6, "END": 0.3, "VIT": 0.1},
                                 target=3, unit="sessions", periodicity=Periodicity.WEEKLY)),
        "book": s.add_habit(Habit("Finish a book", HabitType.CHECK, "S", {"WIS": 0.6, "INT": 0.4},
                                  periodicity=Periodicity.MONTHLY)),
    }
    rng = random.Random(7)
    for i in range(DAYS):
        clock.day = START + timedelta(days=i)
        s.tick()
        if s.state.penalty_quest:          # um jogador real cumpre a Penalty Quest no dia seguinte
            s.complete_penalty_quest()
        while s.state.player.rank_index < 2 and not _blocked(s):
            s.breakthrough()
        good = rng.random() < 0.8
        s.record(ids["study"], rng.choice([60, 60, 45, 30]) if good else 20)
        s.record(ids["water"], rng.choice([2, 2, 1.75, 1.5]))
        s.record(ids["pushups"], 4 if good else 2)
        s.record(ids["bed"], 1 if rng.random() < 0.9 else 0)
        s.record(ids["social"], rng.choice([30, 45, 60, 90]))
        if clock.day.weekday() in (0, 2, 4):
            s.record(ids["gym"], s.value(ids["gym"]) + 1)
    clock.day = START + timedelta(days=DAYS)
    s.tick()
    # "hoje": algum progresso para os cartões mostrarem estados diferentes
    s.record(ids["study"], 35)
    s.record(ids["water"], 1.25)
    s.record(ids["pushups"], 4)
    s.record(ids["bed"], 1)
    s.record(ids["social"], 20)
    s.state.inventory[items.Item.XP_SCROLL] = 1
    s.state.player.free_points = 3
    return s


def settle(app: QApplication) -> None:
    """O Qt reorganiza os layouts em várias passagens do ciclo de eventos: esperar antes de capturar."""
    for _ in range(5):
        app.processEvents()


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyleSheet(STYLESHEET)
    service = demo_service(Path(tempfile.mkdtemp()) / "demo.db")

    window = MainWindow(service)
    window.resize(1280, 820)
    window.show()
    for i, (name, _) in enumerate(MainWindow.PAGES):
        window.sidebar.setCurrentRow(i)
        settle(app)
        window.grab().save(str(out / f"{i + 1:02d}_{name.lower()}.png"))
        print("saved", name)

    extras = {
        "popup_level_up": SystemPopup("LEVEL UP!", "Level 11 → 12. +3 free points.", "level_up"),
        "popup_penalty": SystemPopup("[PENALTY ZONE]", "Your HP reached 0. Breakthroughs are locked until you "
                                     "clear the Penalty Quest.", "penalty"),
        "dialog_new_quest": HabitDialog(),
        "dialog_awakening": AwakeningDialog(service),
        "dialog_pin": PinDialog(security.PinGate(security.hash_pin("1234"))),
    }
    for name, widget in extras.items():
        widget.show()
        settle(app)
        widget.grab().save(str(out / f"{name}.png"))
        print("saved", name)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/screenshots"))
