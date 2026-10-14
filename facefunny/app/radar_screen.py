"""Second screen: top status bar, the radar and the control bar."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .radar_view import RadarView
from .simulation import Simulation, SimState
from .sound import SoundManager


class Dot(QWidget):
    """Small glowing colour dot used in the legend and status chips."""

    def __init__(self, color: str, size: int = 12, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size + 6, size + 6)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QColor(self._color)
        glow.setAlpha(70)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(self.rect())
        p.setBrush(self._color)
        p.setPen(QColor(255, 255, 255, 220))
        p.drawEllipse(self.rect().adjusted(3, 3, -3, -3))
        p.end()


def _chip(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Chip")
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lbl


def _tool_button(text: str, danger: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("ToolButton")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep F9/F10 going to the window
    if danger:
        b.setProperty("danger", True)
    return b


class RadarScreen(QWidget):
    disconnectRequested = Signal()

    def __init__(self, sounds: SoundManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.sounds = sounds
        self.sim = Simulation()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # ---------------------------------------------------------- top bar
        top = QFrame()
        top.setObjectName("Panel")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(18, 10, 14, 10)
        tl.setSpacing(10)

        logo = QLabel("FACEFUNNY")
        logo.setObjectName("Logo")
        logo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tl.addWidget(logo)
        tl.addSpacing(8)

        self.map_chip = _chip("MAP · MIRAGE")
        tl.addWidget(self.map_chip)

        sim_box = QWidget()
        sl = QHBoxLayout(sim_box)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(2)
        sl.addWidget(Dot(theme.OK_GREEN, 8))
        self.sim_chip = _chip("SIMULATION: ACTIVE")
        sl.addWidget(self.sim_chip)
        tl.addWidget(sim_box)

        self.players_chip = _chip(f"PLAYERS {len(self.sim.players)}/10")
        tl.addWidget(self.players_chip)

        move_box = QWidget()
        ml = QHBoxLayout(move_box)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(2)
        self.move_dot = Dot(theme.TEXT_DIM, 8)
        ml.addWidget(self.move_dot)
        self.move_chip = _chip("MOVEMENT: STANDBY")
        ml.addWidget(self.move_chip)
        tl.addWidget(move_box)

        tl.addStretch(1)
        self.server_label = QLabel("")
        self.server_label.setObjectName("Dim")
        self.server_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.server_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tl.addWidget(self.server_label)
        self.fps_chip = _chip("FPS --")
        self.fps_chip.setMinimumWidth(78)
        self.fps_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(self.fps_chip)
        root.addWidget(top)

        # ------------------------------------------------------------ radar
        self.radar = RadarView(self.sim)
        self.radar.fpsChanged.connect(self._on_fps)
        self.radar.frameTick.connect(self._refresh_movement_status)
        root.addWidget(self.radar, 1)

        # ---------------------------------------------------------- bottom bar
        bottom = QFrame()
        bottom.setObjectName("Panel")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(18, 8, 12, 8)
        bl.setSpacing(8)

        for color, text in ((theme.CT_BLUE, "CT · COUNTER-TERRORISTS"), (theme.T_RED, "T · TERRORISTS")):
            bl.addWidget(Dot(color, 11))
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 9pt; font-weight: 600; letter-spacing: 1px;")
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            bl.addWidget(lbl)
            bl.addSpacing(14)

        hint = QLabel("F9  START / PAUSE     F10  RESET TO BASES")
        hint.setObjectName("Dim")
        hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        bl.addWidget(hint, 1)

        self.pause_btn = _tool_button("PAUSE")
        self.pause_btn.setToolTip("Pause / resume movement (F9 also toggles)")
        self.pause_btn.clicked.connect(self.on_pause_clicked)
        bl.addWidget(self.pause_btn)

        self.reset_btn = _tool_button("RESET")
        self.reset_btn.setToolTip("Restart the simulation from the bases")
        self.reset_btn.clicked.connect(self.restart_simulation)
        bl.addWidget(self.reset_btn)

        self.sound_btn = _tool_button("SOUND ON")
        self.sound_btn.setToolTip("Toggle interface sounds")
        self.sound_btn.clicked.connect(self.toggle_sound)
        if not self.sounds.available:
            self.sound_btn.setText("SOUND N/A")
            self.sound_btn.setEnabled(False)
            self.sound_btn.setToolTip("Qt Multimedia is not available on this system")
        bl.addWidget(self.sound_btn)

        self.disc_btn = _tool_button("DISCONNECT", danger=True)
        self.disc_btn.clicked.connect(self._on_disconnect)
        bl.addWidget(self.disc_btn)
        root.addWidget(bottom)

        self._last_state: Optional[SimState] = None
        self._last_arrived = False
        self._refresh_movement_status()

    # ----------------------------------------------------------- lifecycle
    def activate(self, server: str) -> None:
        shown = server if len(server) <= 42 else server[:39] + "…"
        self.server_label.setText(f"DEMO LINK  ›  {shown}")
        self.server_label.setToolTip(f"Display only — no connection is made: {server}")
        self.sim.reset()
        self.radar.start_loop()
        self.radar.setFocus()
        self._refresh_movement_status()

    def deactivate(self) -> None:
        self.sim.reset()
        self.radar.stop_loop()

    # ------------------------------------------------------------ actions
    def toggle_movement(self) -> None:
        """F9: start, pause or resume. One timer drives everything, so a second
        movement loop can never be started."""
        state = self.sim.toggle()
        self.sounds.play("start" if state is SimState.RUNNING else "pause")
        self._refresh_movement_status()

    def on_pause_clicked(self) -> None:
        if self.sim.state is SimState.RUNNING:
            self.sim.pause()
            self.sounds.play("pause")
        elif self.sim.state is SimState.PAUSED:
            self.sim.start()
            self.sounds.play("start")
        else:
            self.sounds.play("error")  # nothing to pause yet
        self._refresh_movement_status()

    def reset_to_bases(self) -> None:
        """F10: put everyone back to their spawn and stop."""
        self.sim.reset()
        self.sounds.play("reset")
        self._refresh_movement_status()

    def restart_simulation(self) -> None:
        """RESET button: back to the bases and immediately start a new run."""
        self.sim.restart()
        self.sounds.play("reset")
        self._refresh_movement_status()

    def toggle_sound(self) -> None:
        enabled = self.sounds.toggle()
        self.sound_btn.setText("SOUND ON" if enabled else "SOUND OFF")
        self.sounds.play("click")

    def _on_disconnect(self) -> None:
        self.sounds.play("click")
        self.disconnectRequested.emit()

    # --------------------------------------------------------------- status
    def _on_fps(self, fps: float) -> None:
        self.fps_chip.setText(f"FPS {fps:4.0f}")

    def _refresh_movement_status(self) -> None:
        state = self.sim.state
        arrived = self.sim.all_arrived
        if state is self._last_state and arrived == self._last_arrived:
            return
        self._last_state, self._last_arrived = state, arrived
        if state is SimState.RUNNING:
            text, color = ("MOVEMENT: HOLDING A" if arrived else "MOVEMENT: → A SITE"), theme.OK_GREEN
            self.pause_btn.setText("PAUSE")
        elif state is SimState.PAUSED:
            text, color = "MOVEMENT: PAUSED", theme.WARN
            self.pause_btn.setText("RESUME")
        else:
            text, color = "MOVEMENT: STANDBY (F9)", theme.TEXT_DIM
            self.pause_btn.setText("PAUSE")
        self.move_chip.setText(text)
        self.move_dot.set_color(color)
