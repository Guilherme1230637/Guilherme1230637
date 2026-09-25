"""Ponto de entrada da app:  python -m awaken"""

import sys

from PySide6.QtWidgets import QApplication

from .persistence.paths import default_db_path
from .services.game_service import GameService
from .ui.icon import make_icon
from .ui.main_window import AwakeningDialog, MainWindow, PinDialog
from .ui.theme import STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Awaken System")
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(make_icon())
    app.setQuitOnLastWindowClosed(False)    # a app pode continuar junto ao relógio (lembretes)
    service = GameService.open(default_db_path())

    if service.has_pin and not PinDialog(service.pin_gate()).exec():
        return 0

    if service.has_game():
        notifications = service.load()          # fecha os dias que passaram com a app fechada
    else:
        awakening = AwakeningDialog(service)
        if not awakening.exec():
            return 0
        notifications = awakening.notifications

    window = MainWindow(service)
    window.show()
    window.show_notifications(notifications)
    return app.exec()
