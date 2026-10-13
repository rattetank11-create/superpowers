"""Собственные виджеты: анимированный переключатель, светящаяся кнопка, карточка действия."""

from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ..actions import ActionDef
from ..engine import ActionStatus
from . import theme


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


# ---------------------------------------------------------------------------
class ToggleSwitch(QAbstractButton):
    """iOS-подобный переключатель с плавной анимацией."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._offset = 0.0
        self._hover = False
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt API)
        super().setChecked(checked)
        self._anim.stop()
        self._offset = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(46, 26)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off = QColor("#33363d") if not self._hover else QColor("#41454d")
        on = QColor(theme.ACCENT_HOVER if self._hover else theme.ACCENT)
        t = self._offset
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        d = rect.height() - 6
        x = rect.left() + 3 + (rect.width() - d - 6) * t
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, rect.top() + 3, d, d))
        p.end()


# ---------------------------------------------------------------------------
class GlowButton(QPushButton):
    """Кнопка с анимированным свечением при наведении."""

    def __init__(self, text: str, parent: QWidget | None = None,
                 color: str = theme.ACCENT, rest: float = 14.0, hover: float = 38.0) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._rest, self._hover = rest, hover
        self._shadow = QGraphicsDropShadowEffect(self)
        glow = QColor(color)
        glow.setAlpha(150)
        self._shadow.setColor(glow)
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(rest)
        self.setGraphicsEffect(self._shadow)
        self._anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _glow_to(self, value: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._shadow.blurRadius())
        self._anim.setEndValue(value)
        self._anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802
        if self.isEnabled():
            self._glow_to(self._hover)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._glow_to(self._rest)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._glow_to(self._rest * 0.6)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._glow_to(self._hover if self.underMouse() else self._rest)
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
class StatusBadge(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("badge")
        self.setAlignment(Qt.AlignCenter)
        self.set_state("idle", "…")

    def set_state(self, state: str, text: str) -> None:
        self.setText(f"●  {text}")
        if self.property("state") != state:
            self.setProperty("state", state)
            repolish(self)


class ElidedLabel(QLabel):
    """Длинные пути обрезаются многоточием посередине, полный текст — в подсказке."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._update_elide()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        fm = QFontMetrics(self.font())
        super().setText(fm.elidedText(self._full, Qt.ElideMiddle, max(20, self.width())))


# ---------------------------------------------------------------------------
class ActionCard(QFrame):
    toggled = Signal(str, bool)
    launch_requested = Signal(str)
    browse_requested = Signal(str)

    def __init__(self, action: ActionDef, enabled: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action = action
        self.setObjectName("card")
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumHeight(150)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 160))
        self._shadow.setBlurRadius(14)
        self.setGraphicsEffect(self._shadow)
        self._shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._shadow_anim.setDuration(200)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # --- верхняя строка: иконка, название, переключатель
        top = QHBoxLayout()
        top.setSpacing(12)
        mono = QLabel(action.monogram)
        mono.setObjectName("monogram")
        mono.setAlignment(Qt.AlignCenter)
        mono.setFixedSize(42, 42)
        mono.setStyleSheet(f"background: {action.color};")
        top.addWidget(mono)

        names = QVBoxLayout()
        names.setSpacing(0)
        self.title = QLabel(action.title)
        self.title.setObjectName("cardTitle")
        subtitle = QLabel(action.subtitle)
        subtitle.setObjectName("cardSubtitle")
        names.addWidget(self.title)
        names.addWidget(subtitle)
        top.addLayout(names, 1)

        self.toggle = ToggleSwitch()
        self.toggle.setChecked(enabled)
        self.toggle.setToolTip("Включить это действие в «Мой сетап»")
        self.toggle.toggled.connect(self._on_toggled)
        top.addWidget(self.toggle, 0, Qt.AlignTop)
        root.addLayout(top)

        # --- путь / цель
        self.path_label = ElidedLabel()
        self.path_label.setObjectName("cardPath")
        root.addWidget(self.path_label)

        # --- нижняя строка: статус и кнопки
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.badge = StatusBadge()
        bottom.addWidget(self.badge)
        bottom.addStretch(1)
        self.browse_btn = None
        if action.kind == "exe":
            self.browse_btn = QPushButton("Путь…")
            self.browse_btn.setObjectName("cardTool")
            self.browse_btn.setCursor(Qt.PointingHandCursor)
            self.browse_btn.setToolTip(f"Указать {action.exe_name} вручную")
            self.browse_btn.clicked.connect(lambda: self.browse_requested.emit(action.id))
            bottom.addWidget(self.browse_btn)
        launch_text = "Открыть" if action.kind in ("cpl", "url") else "Запустить"
        self.launch_btn = QPushButton(launch_text)
        self.launch_btn.setObjectName("cardLaunch")
        self.launch_btn.setCursor(Qt.PointingHandCursor)
        self.launch_btn.clicked.connect(lambda: self.launch_requested.emit(action.id))
        bottom.addWidget(self.launch_btn)
        root.addLayout(bottom)

        self._apply_off(not enabled)

    # --- состояние
    def set_status(self, status: ActionStatus, target: str) -> None:
        self.badge.set_state(status.state, status.text)
        self.badge.setToolTip(status.detail)
        self.path_label.set_full_text(target)

    def set_busy(self, busy: bool) -> None:
        self.launch_btn.setEnabled(not busy)
        if self.browse_btn:
            self.browse_btn.setEnabled(not busy)

    def _on_toggled(self, checked: bool) -> None:
        self._apply_off(not checked)
        self.toggled.emit(self.action.id, checked)

    def _apply_off(self, off: bool) -> None:
        self.title.setProperty("off", "true" if off else "false")
        repolish(self.title)

    # --- анимация наведения
    def enterEvent(self, event) -> None:  # noqa: N802
        self._animate_shadow(28, QColor(255, 85, 0, 70))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._animate_shadow(14, QColor(0, 0, 0, 160))
        super().leaveEvent(event)

    def _animate_shadow(self, blur: float, color: QColor) -> None:
        self._shadow.setColor(color)
        self._shadow_anim.stop()
        self._shadow_anim.setStartValue(self._shadow.blurRadius())
        self._shadow_anim.setEndValue(blur)
        self._shadow_anim.start()
