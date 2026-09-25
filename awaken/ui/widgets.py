"""Componentes visuais reutilizáveis: painéis, barras, emblemas de rank e popups [SYSTEM]."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme


def glow(widget: QWidget, color: str = theme.GLOW, radius: int = 18) -> None:
    """Brilho azul à volta do widget (o "neon" das janelas do System)."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(radius)
    effect.setOffset(0, 0)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


class Panel(QFrame):
    """Painel com título ao estilo "[ STATUS ]"."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 12, 16, 14)
        self.body.setSpacing(8)
        if title:
            label = QLabel(f"[ {title.upper()} ]")
            label.setObjectName("PanelTitle")
            label.setAlignment(Qt.AlignCenter)
            self.body.addWidget(label)
        glow(self, radius=14)


class Bar(QWidget):
    """Barra de progresso desenhada à mão (HP, XP, cumprimento de um hábito)."""

    def __init__(self, color: str, height: int = 16, parent: QWidget | None = None):
        super().__init__(parent)
        self.color = QColor(color)
        self.fraction = 0.0
        self.text = ""
        self.setFixedHeight(height)
        self.setMinimumWidth(80)

    def set_value(self, current: float, maximum: float, text: str | None = None) -> None:
        self.fraction = max(0.0, min(1.0, current / maximum)) if maximum else 0.0
        self.text = text if text is not None else f"{current:g} / {maximum:g}"
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor(theme.PANEL_ALT))
        p.drawRoundedRect(rect, radius, radius)
        if self.fraction > 0:
            fill = QRectF(rect.x(), rect.y(), max(rect.height(), rect.width() * self.fraction), rect.height())
            path = QPainterPath()
            path.addRoundedRect(fill, radius, radius)
            p.fillPath(path, self.color)
        if self.text and self.height() >= 14:
            p.setPen(QColor("white"))
            font = QFont(self.font())
            font.setPointSizeF(max(7.0, self.height() * 0.5))
            font.setBold(True)
            p.setFont(font)
            p.drawText(rect, Qt.AlignCenter, self.text)


def rank_badge(rank: str) -> QLabel:
    """Pequeno emblema colorido com o rank de dificuldade (E a S)."""
    color = theme.HABIT_RANK_COLORS[rank]
    label = QLabel(rank)
    label.setAlignment(Qt.AlignCenter)
    label.setFixedSize(26, 26)
    label.setStyleSheet(f"color: {color}; border: 2px solid {color}; border-radius: 13px; font-weight: bold;")
    return label


class SystemPopup(QDialog):
    """Janela de notificação do System: "[SYSTEM] ..." com um botão de confirmar."""

    KIND_COLORS = {
        "level_up": theme.GLOW, "breakthrough": theme.GOLD, "skill": "#b07cff", "loot": theme.SUCCESS,
        "achievement": theme.GOLD, "penalty": theme.DANGER, "warning": theme.DANGER,
        "report": theme.GLOW, "info": theme.GLOW,
    }

    def __init__(self, title: str, message: str, kind: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("System")
        self.setModal(True)
        color = self.KIND_COLORS.get(kind, theme.GLOW)
        frame = QFrame(self)
        frame.setObjectName("Panel")
        frame.setStyleSheet(f"QFrame#Panel {{ border: 2px solid {color}; background: {theme.PANEL}; }}")
        glow(frame, color, 30)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(28, 22, 28, 20)
        inner.setSpacing(12)

        header = QLabel("⚠  NOTIFICATION" if kind in ("penalty", "warning") else "ⓘ  NOTIFICATION")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"color: {color}; font-size: 12px; letter-spacing: 4px;")
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        heading.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
        body = QLabel(message)
        body.setAlignment(Qt.AlignCenter)
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 14px;")
        ok = QPushButton("OK")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(ok)
        row.addStretch()
        for w in (header, heading, body):
            inner.addWidget(w)
        inner.addLayout(row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addWidget(frame)
        self.setMinimumWidth(460)
