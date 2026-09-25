"""Ecrã principal: Status Window (esquerda) + Quests Daily/Weekly/Monthly (direita)."""

import time
from datetime import datetime, timedelta
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..engine import config, leveling
from ..engine.habits import Habit, HabitType, Periodicity
from ..services.game_service import GameService, Notification
from . import theme
from .habit_dialog import HabitDialog
from .widgets import Bar, Panel, rank_badge

Notify = Callable[[list[Notification]], None]

ATTRIBUTE_NAMES = {
    "STR": "Strength", "AGI": "Agility", "VIT": "Vitality", "END": "Endurance", "INT": "Intelligence",
    "PER": "Perception", "CHA": "Charisma", "WIS": "Wisdom", "TEN": "Tenacity",
}


def fmt(value: float) -> str:
    return f"{value:g}"


# ============================ Status Window ============================
class StatusWindow(Panel):
    def __init__(self, service: GameService, on_change: Callable[[], None]):
        super().__init__("Status")
        self.service, self.on_change = service, on_change
        self.setFixedWidth(360)

        self.name = QLabel()
        self.name.setObjectName("Big")
        self.name.setAlignment(Qt.AlignCenter)
        self.title = QLabel()
        self.title.setObjectName("Dim")
        self.title.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.name)
        self.body.addWidget(self.title)

        grid = QGridLayout()
        self.level = QLabel()
        self.level.setStyleSheet(f"font-size: 34px; font-weight: bold; color: {theme.GLOW};")
        self.level.setAlignment(Qt.AlignCenter)
        self.hunter = QLabel()
        self.cultivation = QLabel()
        for w in (self.hunter, self.cultivation):
            w.setAlignment(Qt.AlignCenter)
        level_caption = QLabel("LEVEL")
        level_caption.setObjectName("Dim")
        level_caption.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.level, 0, 0)
        grid.addWidget(level_caption, 1, 0)
        grid.addWidget(self.cultivation, 0, 1)
        grid.addWidget(self.hunter, 1, 1)
        self.body.addLayout(grid)

        self.hp = Bar(theme.HP, 18)
        self.xp = Bar(theme.XP, 18)
        for caption, bar in (("HP", self.hp), ("XP", self.xp)):
            row = QHBoxLayout()
            label = QLabel(caption)
            label.setFixedWidth(26)
            label.setStyleSheet("font-weight: bold;")
            row.addWidget(label)
            row.addWidget(bar)
            self.body.addLayout(row)

        self.gold = QLabel()
        self.gold.setObjectName("Gold")
        self.body.addWidget(self.gold)

        self.penalty = QLabel()
        self.penalty.setWordWrap(True)
        self.penalty.setStyleSheet(f"color: {theme.DANGER}; border: 1px solid {theme.DANGER}; padding: 8px;")
        self.penalty_button = QPushButton("Penalty Quest completed")
        self.penalty_button.setObjectName("Danger")
        self.penalty_button.clicked.connect(self._clear_penalty)
        self.body.addWidget(self.penalty)
        self.body.addWidget(self.penalty_button)

        self.points = QLabel()
        self.points.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.points)
        self.attr_grid = QGridLayout()
        self.attr_grid.setHorizontalSpacing(6)
        self.attr_values: dict[str, QLabel] = {}
        self.attr_buttons: dict[str, QPushButton] = {}
        for i, attr in enumerate(config.ATTRIBUTES):
            name = QLabel(attr)
            name.setToolTip(ATTRIBUTE_NAMES[attr])
            name.setStyleSheet(f"color: {theme.TEXT_DIM}; font-weight: bold;")
            value = QLabel()
            value.setStyleSheet("font-size: 16px; font-weight: bold;")
            value.setMinimumWidth(30)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            plus = QPushButton("+")
            plus.setObjectName("Small")
            plus.clicked.connect(lambda _=False, a=attr: self._spend(a))
            row, col = divmod(i, 3)
            cell = QHBoxLayout()
            cell.addWidget(name)
            cell.addWidget(value)
            cell.addWidget(plus)
            cell.addStretch()
            self.attr_grid.addLayout(cell, row, col)
            self.attr_values[attr], self.attr_buttons[attr] = value, plus
        self.body.addLayout(self.attr_grid)
        self.body.addStretch()

    def refresh(self) -> None:
        state = self.service.state
        p = state.player
        self.name.setText(p.name)
        self.title.setText(f"“{state.active_title}”" if state.active_title else "No title")
        self.level.setText(str(p.level))
        color = theme.CULTIVATION_COLORS[p.rank.name]
        self.cultivation.setText(p.rank_label)
        self.cultivation.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        self.hunter.setText(f"Hunter Rank: {p.hunter_rank}")
        self.hp.set_value(p.hp, p.max_hp)
        need = leveling.xp_to_next_level(p.level)
        self.xp.set_value(p.xp_into_level, need)
        self.gold.setText(f"◆ {p.gold:,} Gold")
        in_zone = p.in_penalty_zone
        self.penalty.setVisible(in_zone)
        self.penalty_button.setVisible(in_zone and state.penalty_quest is not None)
        if in_zone and state.penalty_quest:
            q = state.penalty_quest
            self.penalty.setText(f"⚠ PENALTY ZONE\n{q.task} (Rank {q.rank}) — until {q.due:%d/%m}")
        self.points.setText(f"Free points: {p.free_points}" if p.free_points else "")
        for attr in config.ATTRIBUTES:
            self.attr_values[attr].setText(str(int(p.attributes[attr])))
            self.attr_buttons[attr].setVisible(p.free_points > 0)

    def _spend(self, attr: str) -> None:
        self.service.spend_free_point(attr)
        self.on_change()

    def _clear_penalty(self) -> None:
        answer = QMessageBox.question(self, "Penalty Quest", "Did you really complete the Penalty Quest?")
        if answer == QMessageBox.Yes:
            self.on_change(self.service.complete_penalty_quest())


# ============================ Quest card ============================
class QuestCard(Panel):
    def __init__(self, habit: Habit, service: GameService, timers: dict[int, float], on_change):
        super().__init__()
        self.habit, self.service, self.timers, self.on_change = habit, service, timers, on_change
        self.setGraphicsEffect(None)   # sem brilho nos cartões (evita "ruído" visual)

        top = QHBoxLayout()
        top.addWidget(rank_badge(habit.rank))
        texts = QVBoxLayout()
        title = QLabel(habit.name)
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("Dim")
        texts.addWidget(title)
        texts.addWidget(self.subtitle)
        top.addLayout(texts, 1)
        self.controls = QHBoxLayout()
        top.addLayout(self.controls)
        menu_button = QPushButton("⋯")
        menu_button.setObjectName("Small")
        menu_button.clicked.connect(self._menu)
        top.addWidget(menu_button)
        self.body.addLayout(top)
        self.bar = Bar(theme.XP, 10)
        self.body.addWidget(self.bar)
        self._build_controls()
        self.refresh()

    # ---------- controlos específicos de cada tipo ----------
    def _build_controls(self) -> None:
        t = self.habit.habit_type
        if t == HabitType.CHECK:
            self.check = QPushButton()
            self.check.clicked.connect(lambda: self._set(0 if self._value() >= 1 else 1))
            self.controls.addWidget(self.check)
        elif t == HabitType.COUNTER:
            minus, plus = QPushButton("−"), QPushButton("+1")
            minus.setObjectName("Small")
            minus.clicked.connect(lambda: self._set(max(0, self._value() - 1)))
            plus.clicked.connect(lambda: self._set(self._value() + 1))
            self.controls.addWidget(minus)
            self.controls.addWidget(plus)
        elif t == HabitType.TIMER:
            self.timer_button = QPushButton()
            self.timer_button.clicked.connect(self._toggle_timer)
            self.controls.addWidget(self.timer_button)
            self.ticker = QTimer(self)
            self.ticker.timeout.connect(self.refresh)
            self.ticker.start(1000)
        else:  # QUANTITY e LIMIT: introduzir o valor total do período
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2)
            self.spin.setMaximum(1_000_000)
            self.spin.setSingleStep(max(self.habit.target / 8, 0.25) if self.habit.target else 1)
            self.spin.setValue(self._value())
            self.spin.setFixedWidth(90)
            save = QPushButton("Set")
            save.clicked.connect(lambda: self._set(self.spin.value()))
            self.controls.addWidget(self.spin)
            self.controls.addWidget(save)

    def _value(self) -> float:
        return self.service.value(self.habit.id)

    def _set(self, value: float) -> None:
        self.on_change(self.service.record(self.habit.id, value))

    def _toggle_timer(self) -> None:
        started = self.timers.pop(self.habit.id, None)
        if started is None:
            self.timers[self.habit.id] = time.monotonic()
            self.refresh()
        else:
            minutes = (time.monotonic() - started) / 60
            self._set(round(self._value() + minutes, 1))

    # ---------- aspeto ----------
    def refresh(self) -> None:
        h, value = self.habit, self._value()
        ratio = self.service.ratio(h.id)
        unit = "min" if h.habit_type == HabitType.TIMER else h.unit
        streak = f"   🔥 {h.streak}" if h.streak else ""
        if h.habit_type == HabitType.CHECK:
            progress = "Done" if value >= 1 else "Not done"
            self.check.setText("Undo" if value >= 1 else "Complete")
            self.check.setObjectName("" if value >= 1 else "Primary")
            self.check.setStyleSheet("")   # força o Qt a reaplicar o estilo do novo objectName
        elif h.habit_type == HabitType.LIMIT:
            progress = f"{fmt(value)} / max {fmt(h.target)} {unit}".strip()
        else:
            progress = f"{fmt(value)} / {fmt(h.target)} {unit}".strip()
        if h.habit_type == HabitType.TIMER:
            started = self.timers.get(h.id)
            if started is not None:
                elapsed = int(time.monotonic() - started)
                progress += f"   ⏱ {elapsed // 60:02d}:{elapsed % 60:02d}"
                self.timer_button.setText("Stop")
            else:
                self.timer_button.setText("Start")
        rank = config.HABIT_RANKS[h.rank]
        self.subtitle.setText(f"{progress}   ·   {rank.xp} XP{streak}")
        exceeded = h.habit_type == HabitType.LIMIT and ratio < 1
        self.bar.color = QColor(theme.DANGER if exceeded else theme.SUCCESS if ratio >= 1 else theme.XP)
        self.bar.set_value(ratio, 1, "")

    def _menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Edit quest", self._edit)
        menu.addAction("Archive quest", self._archive)
        menu.exec(QCursor.pos())

    def _edit(self) -> None:
        dialog = HabitDialog(self, self.habit)
        if dialog.exec():
            self.service.update_habit(self.habit.id, **dialog.changes())
            self.on_change()

    def _archive(self) -> None:
        answer = QMessageBox.question(self, "Archive quest",
                                      f"Archive “{self.habit.name}”? Its history and skills are kept.")
        if answer == QMessageBox.Yes:
            self.timers.pop(self.habit.id, None)
            self.service.archive_habit(self.habit.id)
            self.on_change()


# ============================ lista de quests ============================
class QuestBoard(Panel):
    TABS = ((Periodicity.DAILY, "Daily"), (Periodicity.WEEKLY, "Weekly"), (Periodicity.MONTHLY, "Monthly"))

    def __init__(self, service: GameService, on_change):
        super().__init__("Quests")
        self.service, self.on_change = service, on_change
        self.timers: dict[int, float] = {}   # hábitos com cronómetro a correr: id → início

        header = QHBoxLayout()
        self.countdown = QLabel()
        self.countdown.setObjectName("Dim")
        header.addWidget(self.countdown)
        header.addStretch()
        add = QPushButton("+ New Quest")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        header.addWidget(add)
        self.body.addLayout(header)

        self.tabs = QTabWidget()
        self.lists: dict[Periodicity, QVBoxLayout] = {}
        for periodicity, name in self.TABS:
            area = QScrollArea()
            area.setWidgetResizable(True)
            holder = QWidget()
            layout = QVBoxLayout(holder)
            layout.setSpacing(8)
            area.setWidget(holder)
            self.tabs.addTab(area, name)
            self.lists[periodicity] = layout
        self.body.addWidget(self.tabs)

        clock = QTimer(self)
        clock.timeout.connect(self._update_countdown)
        clock.start(1000)
        self._update_countdown()

    def _update_countdown(self) -> None:
        now = datetime.now()
        left = datetime.combine(now.date() + timedelta(days=1), datetime.min.time()) - now
        h, rem = divmod(int(left.total_seconds()), 3600)
        self.countdown.setText(f"Daily reset in {h:02d}:{rem // 60:02d}:{rem % 60:02d}")

    def refresh(self) -> None:
        for periodicity, layout in self.lists.items():
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            habits = [h for h in self.service.state.active_habits() if h.periodicity == periodicity]
            for habit in habits:
                layout.addWidget(QuestCard(habit, self.service, self.timers, self.on_change))
            if not habits:
                empty = QLabel("No quests here yet.\nPress “+ New Quest” to create one.")
                empty.setObjectName("Dim")
                empty.setAlignment(Qt.AlignCenter)
                layout.addWidget(empty)
            layout.addStretch()
        for i, (periodicity, name) in enumerate(self.TABS):
            habits = [h for h in self.service.state.active_habits() if h.periodicity == periodicity]
            done = sum(1 for h in habits if self.service.ratio(h.id) >= 1)
            self.tabs.setTabText(i, f"{name}  {done}/{len(habits)}" if habits else name)

    def _add(self) -> None:
        dialog = HabitDialog(self)
        if dialog.exec():
            self.service.add_habit(dialog.build_habit())
            self.on_change()


class HomePage(QWidget):
    def __init__(self, service: GameService, on_change):
        super().__init__()
        self.setObjectName("Page")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)
        self.status = StatusWindow(service, on_change)
        self.board = QuestBoard(service, on_change)
        layout.addWidget(self.status)
        layout.addWidget(self.board, 1)

    def refresh(self) -> None:
        self.status.refresh()
        self.board.refresh()
