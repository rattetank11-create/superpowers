"""First screen: the FACEFUNNY logo, a connection string field and CONNECT.

The connection string is only displayed on the radar screen; no network
connection is ever made.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QPoint,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .sound import SoundManager

HANDSHAKE_STEPS = [
    "Resolving host…",
    "Starting local simulation…",
    "Loading Mirage layout…",
    "Spawning 10 markers…",
]


class GlowTitle(QLabel):
    """Large logo whose glow softly pulses."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A stylesheet is needed here: the app-wide one would override setFont().
        self.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 48pt; font-weight: 900; letter-spacing: 14px;"
        )
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(theme.CT_BLUE))
        self._glow.setBlurRadius(40)
        self.setGraphicsEffect(self._glow)
        self._t = QElapsedTimer()
        self._t.start()

    def animate(self) -> None:
        phase = self._t.elapsed() / 1000.0
        self._glow.setBlurRadius(34 + 18 * (0.5 + 0.5 * math.sin(phase * 2.0)))
        mix = 0.5 + 0.5 * math.sin(phase * 0.7)
        blue, red = QColor(theme.CT_BLUE), QColor(theme.T_RED)
        self._glow.setColor(QColor(
            int(blue.red() * mix + red.red() * (1 - mix)),
            int(blue.green() * mix + red.green() * (1 - mix)),
            int(blue.blue() * mix + red.blue() * (1 - mix)),
        ))


class ConnectScreen(QWidget):
    connectRequested = Signal(str)

    def __init__(self, sounds: SoundManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.sounds = sounds
        self._busy = False
        self._step = 0
        self._clock = QElapsedTimer()
        self._clock.start()

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 30)
        root.addStretch(3)

        self.title = GlowTitle("FACEFUNNY")
        root.addWidget(self.title)

        sub = QLabel("CS2 RADAR SIMULATOR  ·  FOR FUN ONLY")
        sub.setObjectName("Dim")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 10pt; font-weight: 600; letter-spacing: 5px;")
        root.addWidget(sub)
        root.addSpacing(46)

        box = QWidget()
        box.setFixedWidth(460)
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)

        self.input = QLineEdit()
        self.input.setObjectName("ServerInput")
        self.input.setPlaceholderText("Connect to server...")
        self.input.setMaxLength(120)
        self.input.returnPressed.connect(self.try_connect)
        self.input.textEdited.connect(self._clear_error)
        col.addWidget(self.input)

        self.button = QPushButton("CONNECT")
        self.button.setObjectName("ConnectButton")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.try_connect)
        btn_glow = QGraphicsDropShadowEffect(self.button)
        btn_glow.setOffset(0, 0)
        btn_glow.setBlurRadius(28)
        btn_glow.setColor(QColor(61, 139, 255, 150))
        self.button.setGraphicsEffect(btn_glow)
        col.addWidget(self.button)

        self.status = QLabel(" ")
        self.status.setObjectName("Dim")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.status)

        root.addWidget(box, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(4)

        foot = QLabel("Standalone visual simulation · does not read, modify or connect to CS2")
        foot.setObjectName("Dim")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(foot)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start()

        self._step_timer = QTimer(self)
        self._step_timer.setInterval(320)
        self._step_timer.timeout.connect(self._advance_handshake)

        self._shake: Optional[QSequentialAnimationGroup] = None

    # ------------------------------------------------------------- behaviour
    def reset(self) -> None:
        """Called when the user comes back from the radar screen."""
        self._busy = False
        self._step_timer.stop()
        self.button.setEnabled(True)
        self.button.setText("CONNECT")
        self.input.setEnabled(True)
        self.status.setText(" ")
        self.input.setFocus()
        self.input.selectAll()

    def try_connect(self) -> None:
        if self._busy:
            return  # ignore double clicks / repeated Enter
        text = self.input.text().strip()
        if not text:
            self._show_error("Enter any server string to start the demo")
            return
        self._busy = True
        self.sounds.play("click")
        self.button.setEnabled(False)
        self.button.setText("CONNECTING…")
        self.input.setEnabled(False)
        self._step = 0
        self.status.setStyleSheet(f"color: {theme.TEXT_DIM};")
        self.status.setText(HANDSHAKE_STEPS[0])
        self._step_timer.start()

    def _advance_handshake(self) -> None:
        self._step += 1
        if self._step < len(HANDSHAKE_STEPS):
            self.status.setText(HANDSHAKE_STEPS[self._step])
            return
        self._step_timer.stop()
        self.status.setStyleSheet(f"color: {theme.OK_GREEN};")
        self.status.setText("Simulation ready")
        self.sounds.play("connect")
        self.connectRequested.emit(self.input.text().strip())

    def _show_error(self, message: str) -> None:
        self.sounds.play("error")
        self.status.setStyleSheet(f"color: {theme.T_RED};")
        self.status.setText(message)
        self.input.setProperty("error", True)
        self.input.style().unpolish(self.input)
        self.input.style().polish(self.input)
        self._shake_input()
        self.input.setFocus()

    def _clear_error(self) -> None:
        if self.input.property("error"):
            self.input.setProperty("error", False)
            self.input.style().unpolish(self.input)
            self.input.style().polish(self.input)
            self.status.setText(" ")

    def _shake_input(self) -> None:
        box = self.input.parentWidget()
        if self._shake is not None and self._shake.state() == QSequentialAnimationGroup.State.Running:
            return
        origin = box.pos()
        group = QSequentialAnimationGroup(self)
        for dx in (-10, 9, -6, 4, 0):
            a = QPropertyAnimation(box, b"pos", group)
            a.setDuration(45)
            a.setEndValue(origin + QPoint(dx, 0))
            a.setEasingCurve(QEasingCurve.Type.OutQuad)
            group.addAnimation(a)
        self._shake = group
        group.start()

    def _animate(self) -> None:
        if self.isVisible():
            self.title.animate()
            self.update()

    # ---------------------------------------------------------------- paint
    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(theme.BG))
        t = self._clock.elapsed() / 1000.0

        for cx, cy, col in ((0.18, 0.25, theme.CT_BLUE), (0.82, 0.78, theme.T_RED)):
            g = QRadialGradient(cx * w + math.sin(t * 0.4) * 30, cy * h + math.cos(t * 0.3) * 20, max(w, h) * 0.55)
            c0 = QColor(col)
            c0.setAlpha(38)
            c1 = QColor(col)
            c1.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(1.0, c1)
            p.fillRect(self.rect(), g)

        # Perspective-free grid with a slow scan line.
        p.setPen(QPen(QColor(255, 255, 255, 9), 1))
        step = 48
        offset = int(t * 12) % step
        for x in range(-step + offset, w + step, step):
            p.drawLine(x, 0, x, h)
        for y in range(-step + offset, h + step, step):
            p.drawLine(0, y, w, y)
        scan_y = (t * 90) % (h + 200) - 100
        sg = QLinearGradient(0, scan_y - 60, 0, scan_y + 2)
        sg.setColorAt(0.0, QColor(61, 139, 255, 0))
        sg.setColorAt(1.0, QColor(61, 139, 255, 28))
        p.fillRect(0, int(scan_y - 60), w, 62, sg)
        p.end()
