"""Radar widget: draws the Mirage layout, the sweep effect and the ten markers.

The widget owns the single frame timer of the radar screen. Every frame it
advances the simulation by the real elapsed time and paints positions
interpolated between simulation ticks.
"""

from __future__ import annotations

import logging
import math
import os
from typing import List, Optional, Tuple

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
    QResizeEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import map_data, theme
from .simulation import Player, Simulation, Team

log = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
MAP_IMAGE_NAMES = ("de_mirage_radar.png", "de_mirage_radar.jpg", "mirage.png")


def load_map_image() -> Optional[QPixmap]:
    """Load an optional local radar image. Never downloads anything."""
    for name in MAP_IMAGE_NAMES:
        path = os.path.join(ASSETS_DIR, name)
        if os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                log.info("Using map image %s", path)
                return pix
            log.warning("Map image %s could not be decoded, using stylised map", path)
    return None


class RadarView(QWidget):
    fpsChanged = Signal(float)
    frameTick = Signal()

    def __init__(self, simulation: Simulation, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.sim = simulation
        self.setMouseTracking(True)
        self.setMinimumSize(420, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._map_image = load_map_image()
        self._static: Optional[QPixmap] = None
        self._static_key: Tuple[int, int, float] = (0, 0, 0.0)
        self._map_rect = QRectF()
        self._alpha = 1.0
        self._sweep = 0.0
        self._hover: Optional[Player] = None
        self._mouse = QPointF()
        self._screen_pos: List[Tuple[Player, QPointF]] = []

        self._clock = QElapsedTimer()
        self._fps_clock = QElapsedTimer()
        self._frames = 0
        self.fps = 0.0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._on_frame)

    @property
    def has_map_image(self) -> bool:
        return self._map_image is not None

    # ---------------------------------------------------------------- lifecycle
    def start_loop(self) -> None:
        """Start the frame loop. Calling it twice never creates a second loop."""
        if self._timer.isActive():
            return
        self._clock.start()
        self._fps_clock.start()
        self._frames = 0
        self._timer.start()

    def stop_loop(self) -> None:
        self._timer.stop()

    def invalidate_map(self) -> None:
        self._static = None
        self.update()

    def _on_frame(self) -> None:
        dt = self._clock.restart() / 1000.0
        try:
            self._alpha = self.sim.advance(dt)
        except Exception:  # keep the UI alive, but stop the broken run
            log.exception("Simulation step failed; pausing")
            self.sim.pause()
        self._sweep = (self._sweep + dt * 70.0) % 360.0
        self._frames += 1
        elapsed = self._fps_clock.elapsed()
        if elapsed >= 500:
            self.fps = self._frames * 1000.0 / elapsed
            self._frames = 0
            self._fps_clock.restart()
            self.fpsChanged.emit(self.fps)
        if self.underMouse():
            # Markers move under a still cursor, so refresh the hover target too.
            hover = self.player_at(self._mouse)
            if hover is not self._hover:
                self._hover = hover
                self.setCursor(Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor)
        self.frameTick.emit()
        self.update()

    # ----------------------------------------------------------------- geometry
    def _compute_map_rect(self) -> QRectF:
        pad = 18.0
        side = max(10.0, min(self.width(), self.height()) - pad * 2)
        return QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

    def _to_screen(self, x: float, y: float) -> QPointF:
        r = self._map_rect
        return QPointF(r.left() + x * r.width(), r.top() + y * r.height())

    def _norm_rect(self, rect: Tuple[float, float, float, float]) -> QRectF:
        x0, y0, x1, y1 = rect
        a = self._to_screen(x0, y0)
        b = self._to_screen(x1, y1)
        return QRectF(a, b)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._static = None
        super().resizeEvent(event)

    # ----------------------------------------------------------- static layer
    def _build_static(self) -> QPixmap:
        dpr = self.devicePixelRatioF()
        pix = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = self._map_rect
        side = r.width()

        # Panel and grid.
        frame = QPainterPath()
        frame.addRoundedRect(r, 18, 18)
        bg = QRadialGradient(r.center(), side * 0.75)
        bg.setColorAt(0.0, QColor("#0f141d"))
        bg.setColorAt(1.0, QColor("#08090d"))
        p.fillPath(frame, bg)
        p.save()
        p.setClipPath(frame)
        grid_pen = QPen(QColor(255, 255, 255, 10), 1)
        p.setPen(grid_pen)
        for i in range(1, 20):
            t = i / 20.0
            p.drawLine(QPointF(r.left() + t * side, r.top()), QPointF(r.left() + t * side, r.bottom()))
            p.drawLine(QPointF(r.left(), r.top() + t * side), QPointF(r.right(), r.top() + t * side))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        for k in (1, 2, 3):
            p.drawEllipse(r.center(), side * 0.16 * k, side * 0.16 * k)

        if self._map_image is not None:
            p.setOpacity(0.92)
            p.drawPixmap(r, self._map_image, QRectF(self._map_image.rect()))
            p.setOpacity(1.0)
        p.restore()

        # Walkable floor as one merged outline.
        radius = side * 0.008
        floor = QPainterPath()
        for z in map_data.ZONES:
            part = QPainterPath()
            part.addRoundedRect(self._norm_rect(z.rect), radius, radius)
            floor = floor.united(part)
        floor = floor.simplified()

        floor_alpha = 0.35 if self._map_image is not None else 1.0
        p.setOpacity(floor_alpha)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor("#1b2231"))
        grad.setColorAt(1.0, QColor("#151a25"))
        p.fillPath(floor, grad)
        for width, alpha in ((7.0, 18), (3.5, 40)):
            p.strokePath(floor, QPen(QColor(120, 160, 255, alpha), width))
        p.strokePath(floor, QPen(QColor("#4a5878"), 1.4))
        p.setOpacity(1.0)

        # Special zones.
        for z in map_data.ZONES:
            zr = self._norm_rect(z.rect).adjusted(3, 3, -3, -3)
            if z.kind == "site":
                path = QPainterPath()
                path.addRoundedRect(zr, radius, radius)
                p.fillPath(path, QColor(255, 196, 74, 22))
                pen = QPen(QColor(255, 210, 120, 140), 1.6, Qt.PenStyle.DashLine)
                p.strokePath(path, pen)
            elif z.kind in ("ct_spawn", "t_spawn"):
                col = QColor(theme.CT_BLUE if z.kind == "ct_spawn" else theme.T_RED)
                path = QPainterPath()
                path.addRoundedRect(zr, radius, radius)
                fill = QColor(col)
                fill.setAlpha(34)
                p.fillPath(path, fill)
                edge = QColor(col)
                edge.setAlpha(150)
                p.strokePath(path, QPen(edge, 1.4))

        # Labels.
        small = theme.make_font(max(6.5, side * 0.0115), QFont.Weight.DemiBold, 1.2)
        for z in map_data.ZONES:
            if not z.show_label:
                continue
            zr = self._norm_rect(z.rect)
            if z.kind == "site":
                letter = z.label[0]
                big = theme.make_font(max(16.0, side * 0.06), QFont.Weight.Black)
                p.setFont(big)
                p.setPen(QColor(255, 220, 150, 60))
                p.drawText(zr.translated(0, 2), Qt.AlignmentFlag.AlignCenter, letter)
                p.setPen(QColor(255, 236, 200, 225))
                p.drawText(zr, Qt.AlignmentFlag.AlignCenter, letter)
                p.setFont(small)
                p.setPen(QColor(255, 220, 160, 200))
                fm = QFontMetricsF(big)
                below = QRectF(zr.left(), zr.center().y() + fm.height() * 0.42, zr.width(), fm.height() * 0.5)
                p.drawText(below, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, z.label)
            else:
                p.setFont(small)
                if z.kind == "ct_spawn":
                    p.setPen(QColor(150, 190, 255, 210))
                    box = QRectF(zr.left(), zr.bottom() - side * 0.035, zr.width(), side * 0.03)
                elif z.kind == "t_spawn":
                    p.setPen(QColor(255, 150, 160, 210))
                    box = QRectF(zr.left(), zr.bottom() - side * 0.035, zr.width(), side * 0.03)
                else:
                    p.setPen(QColor(150, 162, 186, 150))
                    box = zr
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, z.label)

        # Frame border.
        p.setPen(QPen(QColor(theme.BORDER), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(frame)
        p.end()
        return pix

    # ------------------------------------------------------------------- paint
    def paintEvent(self, event: QPaintEvent) -> None:
        self._map_rect = self._compute_map_rect()
        key = (self.width(), self.height(), self.devicePixelRatioF())
        if self._static is None or key != self._static_key:
            self._static = self._build_static()
            self._static_key = key

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.drawPixmap(0, 0, self._static)
        r = self._map_rect
        side = r.width()

        # Rotating radar sweep.
        frame = QPainterPath()
        frame.addRoundedRect(r, 18, 18)
        p.save()
        p.setClipPath(frame)
        cone = QConicalGradient(r.center(), -self._sweep)
        cone.setColorAt(0.0, QColor(90, 150, 255, 46))
        cone.setColorAt(0.10, QColor(90, 150, 255, 0))
        cone.setColorAt(1.0, QColor(90, 150, 255, 0))
        p.fillRect(r, QBrush(cone))
        p.restore()

        marker_r = max(7.0, side * 0.0155)
        alpha = self._alpha
        self._screen_pos = []

        # Trails.
        for pl in self.sim.players:
            if len(pl.trail) < 2:
                continue
            base = QColor(theme.CT_BLUE if pl.team is Team.CT else theme.T_RED)
            pts = list(pl.trail)
            n = len(pts)
            for i in range(1, n):
                c = QColor(base)
                c.setAlpha(int(110 * i / n))
                p.setPen(QPen(c, max(1.2, marker_r * 0.28), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(self._to_screen(*pts[i - 1]), self._to_screen(*pts[i]))

        # Markers.
        num_font = theme.make_font(max(6.0, marker_r * 0.82), QFont.Weight.Bold)
        p.setFont(num_font)
        for pl in self.sim.players:
            x, y = self.sim.interpolated(pl, alpha)
            c = self._to_screen(x, y)
            self._screen_pos.append((pl, c))
            col = QColor(theme.CT_BLUE if pl.team is Team.CT else theme.T_RED)
            hovered = pl is self._hover

            glow = QRadialGradient(c, marker_r * (3.4 if hovered else 2.7))
            g0 = QColor(col)
            g0.setAlpha(150 if hovered else 110)
            g1 = QColor(col)
            g1.setAlpha(0)
            glow.setColorAt(0.0, g0)
            glow.setColorAt(1.0, g1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(c, marker_r * 3.4, marker_r * 3.4)

            # Heading tick.
            if pl.speed > 1e-4:
                tip = QPointF(c.x() + math.cos(pl.heading) * marker_r * 1.75,
                              c.y() + math.sin(pl.heading) * marker_r * 1.75)
                p.setPen(QPen(QColor(255, 255, 255, 170), max(1.5, marker_r * 0.22),
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(c, tip)

            body = QRadialGradient(QPointF(c.x() - marker_r * 0.35, c.y() - marker_r * 0.35), marker_r * 1.4)
            body.setColorAt(0.0, col.lighter(145))
            body.setColorAt(1.0, col.darker(115))
            p.setBrush(body)
            p.setPen(QPen(QColor(255, 255, 255, 235), 2.0 if hovered else 1.6))
            rr = marker_r * (1.18 if hovered else 1.0)
            p.drawEllipse(c, rr, rr)
            p.setPen(QColor("white"))
            p.drawText(QRectF(c.x() - rr, c.y() - rr, rr * 2, rr * 2), Qt.AlignmentFlag.AlignCenter, str(pl.number))

        if self._hover is not None:
            self._draw_tooltip(p, self._hover, marker_r)
        p.end()

    def _draw_tooltip(self, p: QPainter, pl: Player, marker_r: float) -> None:
        pos = next((c for player, c in self._screen_pos if player is pl), None)
        if pos is None:
            return
        team = "Counter-Terrorist" if pl.team is Team.CT else "Terrorist"
        title = f"{pl.team.value} · PLAYER {pl.number}"
        f1 = theme.make_font(9.5, QFont.Weight.Bold, 1.0)
        f2 = theme.make_font(8.0, QFont.Weight.Normal)
        fm1, fm2 = QFontMetricsF(f1), QFontMetricsF(f2)
        w = max(fm1.horizontalAdvance(title), fm2.horizontalAdvance(team)) + 22
        h = fm1.height() + fm2.height() + 14
        x = pos.x() + marker_r * 1.8
        y = pos.y() - h - marker_r * 0.8
        if x + w > self.width() - 4:
            x = pos.x() - marker_r * 1.8 - w
        if y < 4:
            y = pos.y() + marker_r * 1.6
        box = QRectF(x, y, w, h)
        col = QColor(theme.CT_BLUE if pl.team is Team.CT else theme.T_RED)
        path = QPainterPath()
        path.addRoundedRect(box, 8, 8)
        p.fillPath(path, QColor(14, 17, 23, 238))
        p.strokePath(path, QPen(col, 1.2))
        p.fillRect(QRectF(box.left() + 1, box.top() + 7, 3, box.height() - 14), col)
        p.setPen(QColor("white"))
        p.setFont(f1)
        p.drawText(QPointF(box.left() + 12, box.top() + 6 + fm1.ascent()), title)
        p.setPen(QColor(theme.TEXT_DIM))
        p.setFont(f2)
        p.drawText(QPointF(box.left() + 12, box.top() + 8 + fm1.height() + fm2.ascent()), team)

    # ------------------------------------------------------------------- mouse
    def player_at(self, point: QPointF) -> Optional[Player]:
        marker_r = max(7.0, self._map_rect.width() * 0.0155)
        best, best_d = None, marker_r * 1.5
        for pl, c in self._screen_pos:
            d = math.hypot(c.x() - point.x(), c.y() - point.y())
            if d <= best_d:
                best, best_d = pl, d
        return best

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._mouse = event.position()
        hover = self.player_at(self._mouse)
        if hover is not self._hover:
            self._hover = hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)
