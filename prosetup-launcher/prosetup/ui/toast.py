"""Всплывающие уведомления внутри окна (правый нижний угол)."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget
from shiboken6 import isValid

ICONS = {"success": "✔", "error": "✖", "warning": "⚠", "info": "ℹ"}
MAX_TOASTS = 4


class Toast(QFrame):
    def __init__(self, parent: QWidget, title: str, text: str, kind: str, timeout_ms: int) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("kind", kind)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        head = QLabel(f"{ICONS.get(kind, '')}  {title}")
        head.setObjectName("toastTitle")
        layout.addWidget(head)
        if text:
            body = QLabel(text)
            body.setObjectName("toastText")
            body.setWordWrap(True)
            layout.addWidget(body)
        self.adjustSize()

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._closing = False
        QTimer.singleShot(timeout_ms, self.dismiss)

    def appear(self) -> None:
        self.show()
        self.raise_()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def dismiss(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._anim.stop()
        self._anim.setStartValue(self._opacity.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.dismiss()
        super().mousePressEvent(event)


class ToastManager:
    def __init__(self, host: QWidget) -> None:
        self.host = host
        self.toasts: list[Toast] = []

    def show(self, title: str, text: str = "", kind: str = "info") -> None:
        timeout = 6500 if kind in ("error", "warning") else 3800
        toast = Toast(self.host, title, text, kind, timeout)
        toast.destroyed.connect(lambda *_: self._forget(toast))
        self.toasts.append(toast)
        while len(self.toasts) > MAX_TOASTS:
            self.toasts.pop(0).dismiss()
        toast.appear()
        self.reposition()

    def _forget(self, toast: Toast) -> None:
        if toast in self.toasts:
            self.toasts.remove(toast)
        self.reposition()

    def reposition(self) -> None:
        if not isValid(self.host):  # окно уже закрывается
            return
        self.toasts = [t for t in self.toasts if isValid(t)]
        margin = 18
        y = self.host.height() - margin
        for toast in reversed(self.toasts):
            toast.adjustSize()
            y -= toast.height()
            toast.move(self.host.width() - toast.width() - margin, y)
            toast.raise_()
            y -= 8
