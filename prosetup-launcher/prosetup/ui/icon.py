"""Иконка приложения рисуется кодом — не нужны внешние файлы-ресурсы."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def draw_icon(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    rect = QRectF(0, 0, size, size).adjusted(size * 0.04, size * 0.04, -size * 0.04, -size * 0.04)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, QColor("#ff7a2a"))
    grad.setColorAt(1, QColor("#e03d00"))
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.22, size * 0.22)
    p.fillPath(path, QBrush(grad))

    # кольцо прицела
    c = rect.center()
    pen = QPen(QColor(255, 255, 255, 90), max(1.0, size * 0.045))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, size * 0.31, size * 0.31)

    # треугольник «play»
    s = size * 0.19
    tri = QPolygonF([
        QPointF(c.x() - s * 0.75, c.y() - s),
        QPointF(c.x() - s * 0.75, c.y() + s),
        QPointF(c.x() + s * 1.05, c.y()),
    ])
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    p.drawPolygon(tri)
    p.end()
    return pix


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(draw_icon(size))
    return icon
