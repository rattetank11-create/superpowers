"""Main window: holds both screens, fades between them and owns the hotkeys."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QGraphicsOpacityEffect, QMainWindow, QStackedWidget, QWidget

from .connect_screen import ConnectScreen
from .radar_screen import RadarScreen
from .sound import SoundManager


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FACEFUNNY — CS2 Radar Simulator")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 900)

        self.sounds = SoundManager(self)

        self.stack = QStackedWidget()
        self.stack.setObjectName("Root")
        self.setCentralWidget(self.stack)

        self.connect_screen = ConnectScreen(self.sounds)
        self.radar_screen = RadarScreen(self.sounds)
        self.stack.addWidget(self.connect_screen)
        self.stack.addWidget(self.radar_screen)

        self.connect_screen.connectRequested.connect(self.show_radar)
        self.radar_screen.disconnectRequested.connect(self.show_connect)

        self._fade: Optional[QPropertyAnimation] = None

        # Hotkeys work while the window is active, on the radar screen only.
        # Auto-repeat is disabled so holding F9 does not flip the state repeatedly.
        self._f9 = QShortcut(QKeySequence(Qt.Key.Key_F9), self)
        self._f9.setContext(Qt.ShortcutContext.WindowShortcut)
        self._f9.setAutoRepeat(False)
        self._f9.activated.connect(self._on_f9)

        self._f10 = QShortcut(QKeySequence(Qt.Key.Key_F10), self)
        self._f10.setContext(Qt.ShortcutContext.WindowShortcut)
        self._f10.setAutoRepeat(False)
        self._f10.activated.connect(self._on_f10)

        self.connect_screen.input.setFocus()

    # ------------------------------------------------------------ navigation
    def show_radar(self, server: str) -> None:
        self.radar_screen.activate(server)
        self._switch_to(self.radar_screen)

    def show_connect(self) -> None:
        self.radar_screen.deactivate()
        self.connect_screen.reset()
        self._switch_to(self.connect_screen)

    def _switch_to(self, widget: QWidget) -> None:
        if self._fade is not None:
            self._fade.stop()
            self._finish_fade()
        self.stack.setCurrentWidget(widget)
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(420)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self._finish_fade)
        self._fade = anim
        self._fade_target = widget
        anim.start()

    def _finish_fade(self) -> None:
        # Drop the effect afterwards: it would slow down every radar frame.
        target = getattr(self, "_fade_target", None)
        if target is not None:
            target.setGraphicsEffect(None)
        self._fade = None
        self._fade_target = None
        if self.stack.currentWidget() is self.radar_screen:
            self.radar_screen.radar.setFocus()

    # --------------------------------------------------------------- hotkeys
    def _on_f9(self) -> None:
        if self.stack.currentWidget() is self.radar_screen:
            self.radar_screen.toggle_movement()

    def _on_f10(self) -> None:
        if self.stack.currentWidget() is self.radar_screen:
            self.radar_screen.reset_to_bases()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.radar_screen.deactivate()
        self.sounds.close()
        super().closeEvent(event)
