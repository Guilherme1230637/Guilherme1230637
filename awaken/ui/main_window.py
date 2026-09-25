"""Janela principal: barra lateral + páginas, popups [SYSTEM] e verificação periódica da meia-noite."""

from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..services.game_service import GameService, Notification
from ..services.security import PinGate
from . import theme
from .home import HomePage
from .icon import make_icon
from .pages import (
    AchievementsPage,
    CalendarPage,
    InventoryPage,
    RankingPage,
    ReportPage,
    SettingsPage,
    SkillsPage,
)
from .widgets import Panel, SystemPopup

TICK_MS = 60_000       # de minuto a minuto: se o dia mudou, fecha o dia anterior
REMINDER_MS = 30_000   # de 30 em 30 segundos: há lembretes para mostrar?


class MainWindow(QMainWindow):
    PAGES = (
        ("Status", HomePage), ("Skills", SkillsPage), ("Inventory", InventoryPage),
        ("Ranking", RankingPage), ("Calendar", CalendarPage), ("Report", ReportPage),
        ("Achievements", AchievementsPage), ("Settings", SettingsPage),
    )

    def __init__(self, service: GameService):
        super().__init__()
        self.service = service
        self.setWindowTitle("Awaken System")
        self.resize(1180, 760)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(170)
        self.stack = QStackedWidget()
        self.pages = []
        for name, cls in self.PAGES:
            self.sidebar.addItem(name)
            page = cls(service, self.changed)
            self.pages.append(page)
            self.stack.addWidget(page)
        self.sidebar.currentRowChanged.connect(self._show)

        central = QWidget()
        central.setObjectName("Page")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.changed(self.service.tick()))
        self.timer.start(TICK_MS)
        self.sidebar.setCurrentRow(0)
        self.setWindowIcon(make_icon())
        self._setup_tray()

    # ---------- bandeja do sistema e lembretes ----------
    def _setup_tray(self) -> None:
        self.tray = None
        self.last_reminder_check = datetime.now()
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip("Awaken System")
        menu = QMenu()
        menu.addAction("Open", self.bring_to_front)
        menu.addAction("Quit", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: reason == QSystemTrayIcon.Trigger and self.bring_to_front())
        self.tray.show()
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(REMINDER_MS)

    def check_reminders(self) -> None:
        now = datetime.now()
        due = self.service.due_reminders(self.last_reminder_check, now)
        self.last_reminder_check = now
        if self.tray and due:
            names = ", ".join(h.name for h in due)
            self.tray.showMessage("[SYSTEM] Quest reminder", f"{names} — waiting for you, Player.",
                                  QSystemTrayIcon.Information, 10_000)

    def bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.changed()

    def quit(self) -> None:
        self._quitting = True
        QApplication.quit()

    def closeEvent(self, event) -> None:
        """Fechar a janela esconde-a junto ao relógio (os lembretes continuam), se essa opção estiver ligada."""
        if self.tray and self.service.minimize_to_tray and not getattr(self, "_quitting", False):
            event.ignore()
            self.hide()
            if not getattr(self, "_told_about_tray", False):
                self.tray.showMessage("Awaken System", "Still running next to the clock. Right-click → Quit to exit.")
                self._told_about_tray = True
            return
        event.accept()
        QApplication.quit()

    def _show(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.pages[index].refresh()

    def changed(self, notifications: list[Notification] | None = None) -> None:
        """Chamado depois de qualquer ação: atualiza o ecrã visível e mostra as notificações."""
        self.stack.currentWidget().refresh()
        self.show_notifications(notifications or [])

    def show_notifications(self, notifications: list[Notification]) -> None:
        for n in notifications:
            SystemPopup(n.title, n.message, n.kind.value, self).exec()
        if notifications:
            self.stack.currentWidget().refresh()


class AwakeningDialog(QDialog):
    """Primeiro arranque: '[SYSTEM] You have acquired the qualifications to be a Player.'"""

    def __init__(self, service: GameService):
        super().__init__()
        self.service = service
        self.setWindowTitle("Awaken System")
        panel = Panel("System")
        heading = QLabel("You have acquired the qualifications\nto be a Player.")
        heading.setStyleSheet(f"color: {theme.GLOW}; font-size: 20px; font-weight: bold;")
        question = QLabel("Will you accept?  Enter your name, Player:")
        question.setObjectName("Dim")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Your name")
        self.error = QLabel()
        self.error.setStyleSheet(f"color: {theme.DANGER};")
        accept = QPushButton("Accept")
        accept.setObjectName("Primary")
        accept.clicked.connect(self._accept)
        self.name.returnPressed.connect(self._accept)
        for w in (heading, question, self.name, self.error, accept):
            panel.body.addWidget(w)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.addWidget(panel)
        self.setMinimumWidth(480)
        self.notifications: list[Notification] = []

    def _accept(self) -> None:
        try:
            self.notifications = self.service.new_game(self.name.text())
        except ValueError as e:
            self.error.setText(str(e))
            return
        self.accept()


class PinDialog(QDialog):
    """Pedido de PIN ao abrir a app (5 erros → 30 s de espera)."""

    def __init__(self, gate: PinGate):
        super().__init__()
        self.gate = gate
        self.setWindowTitle("Awaken System")
        panel = Panel("Locked")
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setMaxLength(6)
        self.pin.setPlaceholderText("PIN")
        self.pin.returnPressed.connect(self._try)
        self.message = QLabel()
        self.message.setStyleSheet(f"color: {theme.DANGER};")
        unlock = QPushButton("Unlock")
        unlock.setObjectName("Primary")
        unlock.clicked.connect(self._try)
        for w in (QLabel("Enter your PIN, Player."), self.pin, self.message, unlock):
            panel.body.addWidget(w)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.addWidget(panel)
        self.setMinimumWidth(360)
        self.countdown = QTimer(self)
        self.countdown.timeout.connect(self._update_lock)

    def _try(self) -> None:
        if self.gate.try_pin(self.pin.text()):
            self.accept()
            return
        self.pin.clear()
        self.message.setText("Wrong PIN.")
        self._update_lock()

    def _update_lock(self) -> None:
        locked = self.gate.seconds_locked()
        self.pin.setEnabled(not locked)
        if locked:
            self.message.setText(f"Too many attempts. Try again in {locked} s.")
            self.countdown.start(1000)
        else:
            self.countdown.stop()
