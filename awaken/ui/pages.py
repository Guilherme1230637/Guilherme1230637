"""Ecrãs secundários: Skills, Inventory, Ranking, Calendar, Report, Achievements, Settings."""

import calendar as cal
from datetime import date

from PySide6.QtCore import QDate, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..engine import achievements as ach
from ..engine import config, cultivation, items
from ..engine.skills import SKILL_MAX_LEVEL
from ..services.game_service import GameService
from . import theme
from .widgets import Bar, Panel


class ScrollBody(QWidget):
    """Conteúdo com scroll que nunca é comprimido abaixo do tamanho ideal.

    Por defeito, com widgetResizable, o QScrollArea pode encolher o conteúdo até ao tamanho *mínimo*, que num
    cartão com texto é muito menor do que o necessário (texto cortado). Dizendo que o mínimo é o tamanho ideal,
    o Qt passa a mostrar a barra de scroll em vez de esmagar os cartões.
    """

    def minimumSizeHint(self):
        return self.sizeHint()


class Page(QWidget):
    """Página com um painel principal que ocupa o ecrã e pode fazer scroll."""

    def __init__(self, service: GameService, on_change, title: str):
        super().__init__()
        self.setObjectName("Page")
        self.service, self.on_change = service, on_change
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        self.panel = Panel(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = ScrollBody()
        self.content = QVBoxLayout(holder)
        self.content.setSpacing(10)
        scroll.setWidget(holder)
        self.panel.body.addWidget(scroll)
        outer.addWidget(self.panel)

    def clear(self) -> None:
        def wipe(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    wipe(item.layout())
        wipe(self.content)

    def dim(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Dim")
        label.setWordWrap(True)
        return label


# ============================ Skills ============================
class SkillsPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Skills")

    def refresh(self) -> None:
        self.clear()
        state = self.service.state
        if not state.skills:
            self.content.addWidget(self.dim(
                "No skills yet. Skills awaken on their own: complete a quest 10 times, keep a 7-day streak, "
                "or finish 25 quests of the same attribute."))
        names = {h.id: h.name for h in state.habits.values()}
        for skill in state.skills:
            card = Panel()
            card.setGraphicsEffect(None)
            head = QHBoxLayout()
            name = QLabel(skill.name)
            name.setStyleSheet("font-size: 16px; font-weight: bold; color: #b07cff;")
            level = QLabel("Lv.MAX" if skill.level >= SKILL_MAX_LEVEL else f"Lv.{skill.level}")
            level.setStyleSheet("font-weight: bold;")
            head.addWidget(name)
            head.addStretch()
            head.addWidget(level)
            card.body.addLayout(head)
            card.body.addWidget(self.dim(skill.description))
            target = names.get(skill.linked_habit_id) or f"all {skill.linked_attribute} quests"
            card.body.addWidget(self.dim(f"Active: +{skill.xp_bonus:.0%} XP on {target}"))
            if skill.level < SKILL_MAX_LEVEL:
                bar = Bar("#b07cff", 16)
                need = 10 * skill.level
                bar.set_value(skill.proficiency, need, f"Proficiency {skill.proficiency:.1f} / {need}")
                card.body.addWidget(bar)
            self.content.addWidget(card)
        self.content.addStretch()


# ============================ Inventory ============================
ITEM_DESCRIPTIONS = {
    items.Item.HP_POTION: f"Restores {items.HP_POTION_HEAL} HP.",
    items.Item.XP_SCROLL: f"Doubles the XP of your next {items.XP_SCROLL_CHARGES} quests.",
    items.Item.STREAK_SHIELD: "Used automatically to protect a streak when you miss a quest.",
    items.Item.GOLD_POUCH: f"Contains {items.GOLD_POUCH_RANGE[0]}–{items.GOLD_POUCH_RANGE[1]} Gold.",
}


class InventoryPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Inventory")

    def refresh(self) -> None:
        self.clear()
        state = self.service.state
        if state.xp_scroll_charges:
            active = QLabel(f"XP Scroll active: ×2 XP on the next {state.xp_scroll_charges} quests")
            active.setStyleSheet(f"color: {theme.SUCCESS}; font-weight: bold;")
            self.content.addWidget(active)
        owned = [(i, n) for i, n in state.inventory.items() if n > 0]
        if not owned:
            self.content.addWidget(self.dim("Your inventory is empty. Completed quests can drop items."))
        for item, count in owned:
            row = QHBoxLayout()
            text = QVBoxLayout()
            name = QLabel(f"{item.value}  ×{count}")
            name.setStyleSheet("font-size: 15px; font-weight: bold;")
            text.addWidget(name)
            text.addWidget(self.dim(ITEM_DESCRIPTIONS[item]))
            row.addLayout(text, 1)
            if item != items.Item.STREAK_SHIELD:
                use = QPushButton("Use")
                use.clicked.connect(lambda _=False, it=item: self._use(it))
                row.addWidget(use)
            self.content.addLayout(row)
        self.content.addStretch()

    def _use(self, item: items.Item) -> None:
        try:
            self.on_change(self.service.use_item(item))
        except ValueError as e:
            QMessageBox.warning(self, "Inventory", str(e))


# ============================ Ranking ============================
class RankingPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Cultivation Ranking")

    def refresh(self) -> None:
        self.clear()
        p = self.service.state.player
        current = QLabel(p.rank_label)
        current.setAlignment(Qt.AlignCenter)
        current.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {theme.CULTIVATION_COLORS[p.rank.name]};")
        self.content.addWidget(current)
        blocker = cultivation.breakthrough_blocker(p.rank_index, p.level, p.gold, p.in_penalty_zone)
        nxt = cultivation.next_rank(p.rank_index)
        button = QPushButton(f"Breakthrough to {nxt.name}" if nxt else "Peak reached")
        button.setObjectName("Primary")
        button.setEnabled(blocker is None)
        button.clicked.connect(lambda: self.on_change(self.service.breakthrough()))
        self.content.addWidget(button, alignment=Qt.AlignCenter)
        if blocker:
            reason = self.dim(blocker)
            reason.setAlignment(Qt.AlignCenter)
            self.content.addWidget(reason)

        grid = QGridLayout()
        for col, header in enumerate(("Rank", "Requires", "Divisions", "Bonus")):
            h = QLabel(header)
            h.setObjectName("Dim")
            grid.addWidget(h, 0, col)
        for i, rank in enumerate(config.CULTIVATION_RANKS[1:], start=1):
            color = theme.CULTIVATION_COLORS[rank.name]
            reached = i <= p.rank_index
            marker = "▶ " if i == p.rank_index else ("✓ " if reached else "")
            name = QLabel(marker + rank.name)
            name.setStyleSheet(f"color: {color}; font-weight: bold;" + ("" if reached or i == p.rank_index + 1
                                                                        else " color: #3d5270;"))
            grid.addWidget(name, i, 0)
            grid.addWidget(QLabel(f"Lv {rank.min_level} + {rank.gold_cost:,} Gold"), i, 1)
            grid.addWidget(QLabel("★1–★5" if rank.divisions == config.STARS else "Stage 1–10"), i, 2)
            grid.addWidget(QLabel(f"+{rank.bonus_points} points · +{rank.xp_bonus:.0%} XP"), i, 3)
        self.content.addLayout(grid)
        self.content.addStretch()


# ============================ Calendar ============================
class HeatmapMonth(QWidget):
    """Mês em grelha (segunda a domingo); a intensidade da cor = % de cumprimento do dia."""

    CELL, GAP = 44, 6

    def __init__(self):
        super().__init__()
        self.ratios: dict[date, float | None] = {}
        self.year, self.month = date.today().year, date.today().month
        self.setMinimumSize(7 * (self.CELL + self.GAP), 26 + 6 * (self.CELL + self.GAP))  # cabeçalho + até 6 semanas

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        step = self.CELL + self.GAP
        p.setPen(QColor(theme.TEXT_DIM))
        for i, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            p.drawText(QRectF(i * step, 0, self.CELL, 20), Qt.AlignCenter, name)
        base = QColor(theme.GLOW)
        for week, days in enumerate(cal.Calendar().monthdatescalendar(self.year, self.month)):
            for wd, day in enumerate(days):
                rect = QRectF(wd * step, 26 + week * step, self.CELL, self.CELL)
                ratio = self.ratios.get(day)
                if day.month != self.month:
                    continue
                if ratio is None:        # sem dados (futuro ou antes do hábito existir)
                    fill = QColor(theme.PANEL_ALT)
                else:                    # 0 % → quase transparente; 100 % → azul total
                    fill = QColor(base)
                    fill.setAlphaF(0.12 + 0.88 * ratio)
                p.setPen(QPen(QColor(theme.BORDER), 1))
                p.setBrush(fill)
                p.drawRoundedRect(rect, 6, 6)
                p.setPen(QColor("white") if ratio and ratio > 0.5 else QColor(theme.TEXT_DIM))
                p.drawText(rect, Qt.AlignCenter, str(day.day))


class CalendarPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Calendar")
        controls = QHBoxLayout()
        self.habit = QComboBox()
        self.habit.currentIndexChanged.connect(self._draw)
        prev, nxt = QPushButton("◀"), QPushButton("▶")
        prev.clicked.connect(lambda: self._shift(-1))
        nxt.clicked.connect(lambda: self._shift(1))
        self.month_label = QLabel()
        self.month_label.setStyleSheet("font-weight: bold; font-size: 15px;")
        controls.addWidget(self.habit, 1)
        controls.addWidget(prev)
        controls.addWidget(self.month_label)
        controls.addWidget(nxt)
        self.heatmap = HeatmapMonth()
        self.summary = QLabel()
        self.panel.body.insertLayout(1, controls)
        note = self.dim("Colour intensity = how much of the quest you completed that day. "
                        "For weekly and monthly quests every day shows the period's result.")
        # centrar o TEXTO (não o widget): um widget centrado com quebra de linha fica estreito e corta o texto
        for label in (self.summary, note):
            label.setAlignment(Qt.AlignCenter)
        self.content.addWidget(self.heatmap, alignment=Qt.AlignHCenter)
        self.content.addWidget(self.summary)
        self.content.addWidget(note)
        self.content.addStretch()

    def refresh(self) -> None:
        selected = self.habit.currentData()
        self.habit.blockSignals(True)
        self.habit.clear()
        for h in self.service.state.habits.values():
            self.habit.addItem(h.name + (" (archived)" if h.archived else ""), h.id)
        if selected is not None and self.habit.findData(selected) >= 0:
            self.habit.setCurrentIndex(self.habit.findData(selected))
        self.habit.blockSignals(False)
        self._draw()

    def _shift(self, months: int) -> None:
        m = self.heatmap.month - 1 + months
        self.heatmap.year += m // 12
        self.heatmap.month = m % 12 + 1
        self._draw()

    def _draw(self) -> None:
        hm = self.heatmap
        self.month_label.setText(f"{cal.month_name[hm.month]} {hm.year}")
        hid = self.habit.currentData()
        hm.ratios = {}
        if hid is not None:
            state, today = self.service.state, self.service.today
            habit = state.habits[hid]
            days = [d for week in cal.Calendar().monthdatescalendar(hm.year, hm.month) for d in week
                    if d.month == hm.month]
            for d in days:
                if d <= today and (habit.created_on is None or d >= habit.created_on):
                    hm.ratios[d] = state.ratio_of(hid, d)
            known = [r for r in hm.ratios.values() if r is not None]
            self.summary.setText(f"Month average: {sum(known) / len(known):.0%}" if known else "")
        hm.update()


# ============================ Weekly Report ============================
class ReportPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Weekly Report")

    def refresh(self) -> None:
        self.clear()
        r = self.service.last_weekly_report()
        if r is None:
            self.content.addWidget(self.dim("Your first report will appear after your first full week (Monday)."))
            self.content.addStretch()
            return
        head = QLabel(f"[SYSTEM] Week of {r.week_start:%d/%m/%Y}")
        head.setStyleSheet(f"color: {theme.GLOW}; font-size: 18px; font-weight: bold;")
        self.content.addWidget(head)
        grid = QGridLayout()
        facts = [
            ("XP earned", f"{r.xp_earned:,}"), ("Gold earned", f"{r.gold_earned:,}"),
            ("Levels gained", str(r.levels_gained)), ("Overall completion", f"{r.overall_completion:.0%}"),
            ("HP lost", str(r.hp_lost)), ("Penalty Zone entries", str(r.penalty_entries)),
            ("Best quest", r.best_habit or "—"), ("Needs attention", r.worst_habit or "—"),
        ]
        for i, (label, value) in enumerate(facts):
            row, col = divmod(i, 2)
            grid.addWidget(self.dim(label), row, col * 2)
            v = QLabel(value)
            v.setStyleSheet("font-weight: bold; font-size: 15px;")
            grid.addWidget(v, row, col * 2 + 1)
        self.content.addLayout(grid)
        self.content.addWidget(self.dim("Completion by quest"))
        for name, ratio in sorted(r.completion_by_habit.items(), key=lambda kv: -kv[1]):
            row = QHBoxLayout()
            label = QLabel(f"{name}   🔥 {r.streaks.get(name, 0)}")
            label.setFixedWidth(220)
            bar = Bar(theme.SUCCESS if ratio >= 1 else theme.XP, 14)
            bar.set_value(ratio, 1, f"{ratio:.0%}")
            row.addWidget(label)
            row.addWidget(bar, 1)
            self.content.addLayout(row)
        if r.new_skills:
            self.content.addWidget(self.dim("New skills: " + ", ".join(r.new_skills)))
        if r.skill_level_ups:
            self.content.addWidget(self.dim(f"Skill level-ups: {r.skill_level_ups}"))
        if r.loot:
            self.content.addWidget(self.dim("Loot: " + ", ".join(f"{n}× {i}" for i, n in r.loot.items())))
        self.content.addStretch()


# ============================ Achievements ============================
class AchievementsPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Achievements")

    def refresh(self) -> None:
        self.clear()
        state = self.service.state
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Active title:"))
        combo = QComboBox()
        combo.addItem("None", None)
        for t in state.unlocked_titles:
            combo.addItem(t, t)
        combo.setCurrentIndex(max(0, combo.findData(state.active_title)))
        combo.currentIndexChanged.connect(lambda: self._set_title(combo.currentData()))
        title_row.addWidget(combo, 1)
        self.content.addLayout(title_row)
        for a in ach.ACHIEVEMENTS:
            unlocked = a.id in state.unlocked_achievements
            name = QLabel(("🏆 " if unlocked else "🔒 ") + a.name)
            name.setStyleSheet(f"font-weight: bold; font-size: 15px; color: "
                               f"{theme.GOLD if unlocked else '#3d5270'};")
            self.content.addWidget(name)
            extra = f'  —  Title: “{a.title}”' if a.title else ""
            self.content.addWidget(self.dim(a.description + extra))
        self.content.addStretch()

    def _set_title(self, title) -> None:
        self.service.set_title(title)
        self.on_change()


# ============================ Settings ============================
class SettingsPage(Page):
    def __init__(self, service, on_change):
        super().__init__(service, on_change, "Settings")
        self.content.addWidget(QLabel("Pause mode (holidays, illness) — paused days don't count"))
        row = QHBoxLayout()
        self.start, self.end = QDateEdit(), QDateEdit()
        for w in (self.start, self.end):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
        row.addWidget(QLabel("From"))
        row.addWidget(self.start)
        row.addWidget(QLabel("to"))
        row.addWidget(self.end)
        pause = QPushButton("Pause")
        pause.clicked.connect(self._pause)
        row.addWidget(pause)
        row.addStretch()
        self.content.addLayout(row)
        self.paused = self.dim("")
        self.content.addWidget(self.paused)
        self.content.addWidget(self.dim("PIN, reminders and optional AI skill names arrive in the next phase."))
        self.content.addStretch()

    def refresh(self) -> None:
        today = QDate(self.service.today.year, self.service.today.month, self.service.today.day)
        for w in (self.start, self.end):
            w.setMinimumDate(today)
            if w.date() < today:
                w.setDate(today)
        upcoming = sorted(d for d in self.service.state.paused_days if d >= self.service.today)
        self.paused.setText("Paused days: " + ", ".join(f"{d:%d/%m}" for d in upcoming) if upcoming
                            else "No pauses scheduled.")

    def _pause(self) -> None:
        start, end = self.start.date().toPython(), self.end.date().toPython()
        try:
            self.service.pause(start, end)
        except ValueError as e:
            QMessageBox.warning(self, "Pause", str(e))
            return
        self.on_change()
