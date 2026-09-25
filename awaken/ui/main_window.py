"""Janela principal: barra lateral + páginas, popups [SYSTEM] e verificação periódica da meia-noite."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..services.game_service import GameService, Notification
from . import theme
from .home import HomePage
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

TICK_MS = 60_000   # de minuto a minuto: se o dia mudou, fecha o dia anterior


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
