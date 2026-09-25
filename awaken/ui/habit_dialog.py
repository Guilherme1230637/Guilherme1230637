"""Criar / editar uma Quest (hábito)."""

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QHBoxLayout,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..engine import config
from ..engine.achievements import LANGUAGE_TAG
from ..engine.habits import Habit, HabitType, Periodicity, validate_weights
from ..engine.templates import WEIGHT_TEMPLATES
from . import theme

TYPE_LABELS = {
    HabitType.CHECK: "Yes / No",
    HabitType.QUANTITY: "Quantity (e.g. 2 L of water)",
    HabitType.COUNTER: "Counter (e.g. 3× stretching)",
    HabitType.TIMER: "Timer (e.g. 60 min of study)",
    HabitType.LIMIT: "Limit — avoid (e.g. max 60 min social media)",
}
PERIOD_LABELS = {Periodicity.DAILY: "Daily", Periodicity.WEEKLY: "Weekly", Periodicity.MONTHLY: "Monthly"}


class HabitDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, habit: Habit | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Quest" if habit else "New Quest")
        self.setMinimumWidth(480)
        form = QFormLayout()

        self.name = QLineEdit()
        self.periodicity = QComboBox()
        for p, label in PERIOD_LABELS.items():
            self.periodicity.addItem(label, p)
        self.type = QComboBox()
        for t, label in TYPE_LABELS.items():
            self.type.addItem(label, t)
        self.target = QDoubleSpinBox()
        self.target.setDecimals(2)
        self.target.setRange(0, 1_000_000)
        self.target.setValue(1)
        self.unit = QLineEdit()
        self.unit.setPlaceholderText("e.g. L, pages, km")
        self.rank = QComboBox()
        for r, v in config.HABIT_RANKS.items():
            self.rank.addItem(f"Rank {r} — {v.xp} XP · {v.gold} Gold · -{v.hp_penalty} HP if missed", r)
        self.threshold = QSpinBox()
        self.threshold.setRange(1, 100)
        self.threshold.setSuffix(" %")
        self.threshold.setValue(100)
        self.language = QCheckBox("Language practice (Polyglot achievement)")
        self.remind = QCheckBox("Remind me at")
        self.remind_time = QTimeEdit(QTime(8, 0))
        self.remind_time.setDisplayFormat("HH:mm")
        self.remind_time.setEnabled(False)
        self.remind.toggled.connect(self.remind_time.setEnabled)
        remind_row = QHBoxLayout()
        remind_row.addWidget(self.remind)
        remind_row.addWidget(self.remind_time)
        remind_row.addStretch()

        form.addRow("Name", self.name)
        form.addRow("Repeats", self.periodicity)
        form.addRow("Type", self.type)
        self.target_label = QLabel("Target")
        form.addRow(self.target_label, self.target)
        form.addRow("Unit", self.unit)
        form.addRow("Difficulty", self.rank)
        form.addRow("Streak counts from", self.threshold)
        form.addRow("", self.language)
        form.addRow("Reminder", remind_row)

        # ---- pesos dos atributos ----
        self.template = QComboBox()
        self.template.addItem("Suggest weights from a category…", None)
        for name in WEIGHT_TEMPLATES:
            self.template.addItem(name, name)
        self.template.currentIndexChanged.connect(self._apply_template)
        weights_grid = QGridLayout()
        self.weights: dict[str, QSpinBox] = {}
        for i, attr in enumerate(config.ATTRIBUTES):
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setSuffix(" %")
            spin.valueChanged.connect(self._update_sum)
            row, col = divmod(i, 3)
            weights_grid.addWidget(QLabel(attr), row, col * 2)
            weights_grid.addWidget(spin, row, col * 2 + 1)
            self.weights[attr] = spin
        self.sum_label = QLabel()
        self.error = QLabel()
        self.error.setStyleSheet(f"color: {theme.DANGER};")
        self.error.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Attributes this quest trains (must add up to 100 %)"))
        layout.addWidget(self.template)
        layout.addLayout(weights_grid)
        layout.addWidget(self.sum_label)
        layout.addWidget(self.error)
        layout.addWidget(buttons)

        self.type.currentIndexChanged.connect(self._update_type)
        if habit:
            self._load(habit)
        self._update_type()
        self._update_sum()

    def _load(self, h: Habit) -> None:
        self.name.setText(h.name)
        self.periodicity.setCurrentIndex(self.periodicity.findData(h.periodicity))
        self.type.setCurrentIndex(self.type.findData(h.habit_type))
        self.target.setValue(h.target)
        self.unit.setText(h.unit)
        self.rank.setCurrentIndex(self.rank.findData(h.rank))
        self.threshold.setValue(round(h.streak_threshold * 100))
        self.language.setChecked(LANGUAGE_TAG in h.tags)
        if h.reminder:
            self.remind.setChecked(True)
            self.remind_time.setTime(QTime(h.reminder.hour, h.reminder.minute))
        for attr, w in h.attribute_weights.items():
            self.weights[attr].setValue(round(w * 100))

    def _apply_template(self) -> None:
        name = self.template.currentData()
        if name:
            for attr, spin in self.weights.items():
                spin.setValue(round(WEIGHT_TEMPLATES[name].get(attr, 0) * 100))

    def _update_type(self) -> None:
        t = self.type.currentData()
        self.target.setEnabled(t != HabitType.CHECK)
        self.unit.setEnabled(t in (HabitType.QUANTITY, HabitType.LIMIT, HabitType.COUNTER))
        self.target_label.setText({HabitType.LIMIT: "Maximum allowed", HabitType.TIMER: "Minutes",
                                   HabitType.COUNTER: "Times"}.get(t, "Target"))

    def _update_sum(self) -> None:
        total = sum(s.value() for s in self.weights.values())
        color = theme.SUCCESS if total == 100 else theme.DANGER
        self.sum_label.setText(f"Total: {total} %")
        self.sum_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def changes(self) -> dict:
        """Campos editáveis, prontos para Habit(...) ou GameService.update_habit(...)."""
        t = self.type.currentData()
        return dict(
            name=self.name.text().strip(),
            habit_type=t,
            rank=self.rank.currentData(),
            attribute_weights={a: s.value() / 100 for a, s in self.weights.items() if s.value() > 0},
            target=1.0 if t == HabitType.CHECK else self.target.value(),
            periodicity=self.periodicity.currentData(),
            streak_threshold=self.threshold.value() / 100,
            tags=[LANGUAGE_TAG] if self.language.isChecked() else [],
            unit="min" if t == HabitType.TIMER else self.unit.text().strip(),
            reminder=self.remind_time.time().toPython() if self.remind.isChecked() else None,
        )

    def build_habit(self) -> Habit:
        return Habit(**self.changes())

    def _accept(self) -> None:
        """Valida com as mesmas regras do motor antes de fechar."""
        try:
            if not self.name.text().strip():
                raise ValueError("Please give the quest a name.")
            validate_weights(self.changes()["attribute_weights"])
            self.build_habit()
        except ValueError as e:
            self.error.setText(str(e))
            return
        self.accept()
