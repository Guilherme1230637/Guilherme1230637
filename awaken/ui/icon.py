"""Ícone da app desenhado em código (sem ficheiros de imagem): um "A" azul dentro de um losango luminoso."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF

from . import theme


def make_pixmap(size: int = 256) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    c, r = size / 2, size * 0.46
    diamond = QPolygonF([QPointF(c, c - r), QPointF(c + r, c), QPointF(c, c + r), QPointF(c - r, c)])
    p.setBrush(QColor(theme.PANEL))
    p.setPen(QPen(QColor(theme.GLOW), size * 0.05))
    p.drawPolygon(diamond)
    font = QFont(theme.FONT_FAMILY.split(",")[0])
    font.setBold(True)
    font.setPixelSize(int(size * 0.5))
    p.setFont(font)
    p.setPen(QColor(theme.GLOW))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "A")
    p.end()
    return pixmap


def make_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(size))
    return icon
