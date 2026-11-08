"""Frame Selector: one full-screen overlay per monitor with a frozen snapshot, drag/handles/nudge, loupe."""
from __future__ import annotations

import logging
from typing import Optional

import mss
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from . import theme, win32
from .geometry import (
    MIN_FRAME,
    Monitor,
    Rect,
    constrain_frame,
    fit_rect_in_bounds,
    logical_to_physical,
    monitor_at_logical_point,
    physical_rect_to_logical,
    physical_to_logical,
)
from .monitors import MonitorTable

log = logging.getLogger(__name__)

HANDLE_LOGICAL = 8
HANDLE_HIT_LOGICAL = 7
LOUPE_SIZE = 140
LOUPE_SRC = 17
HINT_TEXT = "Drag to frame · Arrows nudge · Enter to confirm · Esc to cancel"

# handle ids: corners and edges
H_TL, H_T, H_TR, H_R, H_BR, H_B, H_BL, H_L = range(8)
_HANDLE_CURSORS = {
    H_TL: Qt.CursorShape.SizeFDiagCursor,
    H_BR: Qt.CursorShape.SizeFDiagCursor,
    H_TR: Qt.CursorShape.SizeBDiagCursor,
    H_BL: Qt.CursorShape.SizeBDiagCursor,
    H_T: Qt.CursorShape.SizeVerCursor,
    H_B: Qt.CursorShape.SizeVerCursor,
    H_L: Qt.CursorShape.SizeHorCursor,
    H_R: Qt.CursorShape.SizeHorCursor,
}


def grab_monitor_image(sct: mss.base.MSSBase, mon: Monitor) -> QImage:
    shot = sct.grab({"left": mon.phys.left, "top": mon.phys.top, "width": mon.phys.width, "height": mon.phys.height})
    raw = bytes(shot.raw)  # BGRA
    img = QImage(raw, shot.width, shot.height, shot.width * 4, QImage.Format.Format_RGB32).copy()
    return img


class _Overlay(QWidget):
    def __init__(self, ctrl: "FrameSelector", mon: Monitor, snapshot: QImage) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.ctrl = ctrl
        self.mon = mon
        self.snapshot = snapshot
        self.snapshot.setDevicePixelRatio(mon.scale)
        self._dimmed = self._make_dimmed(snapshot)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hover_phys: tuple[int, int] | None = None
        self._font = QFont(theme.FONT_FAMILY, theme.FONT_PT_BODY)
        self._font_small = QFont(theme.FONT_FAMILY, theme.FONT_PT_SMALL)

    def _make_dimmed(self, snapshot: QImage) -> QPixmap:
        img = snapshot.copy()
        p = QPainter(img)
        p.fillRect(img.rect(), QColor(0, 0, 0, 128))
        p.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self.mon.scale)
        return pm

    # -- coordinate helpers --------------------------------------------------
    def to_phys(self, pos: QPointF) -> tuple[int, int]:
        lx = self.mon.logical.left + pos.x()
        ly = self.mon.logical.top + pos.y()
        return logical_to_physical(self.mon, lx, ly)

    def to_local(self, px: float, py: float) -> QPointF:
        lx, ly = physical_to_logical(self.mon, px, py)
        return QPointF(lx - self.mon.logical.left, ly - self.mon.logical.top)

    def rect_to_local(self, r: Rect) -> QRectF:
        f = physical_rect_to_logical(self.mon, r)
        return QRectF(f.x - self.mon.logical.left, f.y - self.mon.logical.top, f.w, f.h)

    # -- events ----------------------------------------------------------------
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctrl.on_press(self, self.to_phys(e.position()))
        elif e.button() == Qt.MouseButton.RightButton:
            self.ctrl.cancel()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self.hover_phys = self.to_phys(e.position())
        self.ctrl.on_move(self, self.hover_phys, bool(e.buttons() & Qt.MouseButton.LeftButton))

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctrl.on_release(self, self.to_phys(e.position()))

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctrl.on_double_click(self, self.to_phys(e.position()))

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.hover_phys = None
        self.update()

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        self.ctrl.on_key(e)

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.drawPixmap(0, 0, self._dimmed)
        sel = self.ctrl.sel
        sel_here = sel is not None and self.ctrl.sel_mon is not None and self.ctrl.sel_mon.device == self.mon.device
        if sel_here:
            self._paint_selection(p, sel)
        if self.ctrl.sel is None or sel_here:
            self._paint_hint(p)
        if self.hover_phys is not None and self.ctrl.show_loupe:
            self._paint_loupe(p, self.hover_phys)
        p.end()

    def _paint_selection(self, p: QPainter, sel: Rect) -> None:
        target = self.rect_to_local(sel)
        src = QRectF(sel.left - self.mon.phys.left, sel.top - self.mon.phys.top, sel.width, sel.height)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawImage(target, self.snapshot, src)
        # outline
        pen = QPen(QColor(theme.ACCENT))
        pen.setWidthF(2.0)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(target.adjusted(-1, -1, 1, 1))
        # handles
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        hs = HANDLE_LOGICAL
        for hid, (hx, hy) in self.ctrl.handle_centers_local(self).items():
            r = QRectF(hx - hs / 2, hy - hs / 2, hs, hs)
            p.fillRect(r, QColor(theme.ACCENT))
            p.setPen(QPen(QColor(theme.BG), 1))
            p.drawRect(r)
        # size label
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        label = f"{sel.width} × {sel.height} px"
        fm = QFontMetrics(self._font)
        tw, th = fm.horizontalAdvance(label) + 20, fm.height() + 8
        lx = target.center().x() - tw / 2
        ly = target.bottom() + 10
        if ly + th > self.height() - 4:
            ly = target.top() - 10 - th
        lx = max(4.0, min(lx, self.width() - tw - 4))
        ly = max(4.0, ly)
        self._pill(p, QRectF(lx, ly, tw, th), label, self._font)

    def _paint_hint(self, p: QPainter) -> None:
        fm = QFontMetrics(self._font)
        tw, th = fm.horizontalAdvance(HINT_TEXT) + 28, fm.height() + 12
        r = QRectF((self.width() - tw) / 2, 14, tw, th)
        self._pill(p, r, HINT_TEXT, self._font)

    def _pill(self, p: QPainter, r: QRectF, text: str, font: QFont) -> None:
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, QColor(theme.PANEL))
        p.setPen(QPen(QColor(theme.BORDER_LINE), 1))
        p.drawPath(path)
        p.setPen(QColor(theme.TEXT))
        p.setFont(font)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_loupe(self, p: QPainter, phys: tuple[int, int]) -> None:
        px, py = phys
        cursor_local = self.to_local(px, py)
        size = LOUPE_SIZE
        text_h = 18
        off = 24
        x = cursor_local.x() + off
        y = cursor_local.y() + off
        if x + size > self.width() - 4:
            x = cursor_local.x() - off - size
        if y + size + text_h > self.height() - 4:
            y = cursor_local.y() - off - size - text_h
        x = max(4.0, x)
        y = max(4.0, y)
        circle = QRectF(x, y, size, size)
        half = LOUPE_SRC // 2
        sx = px - self.mon.phys.left - half
        sy = py - self.mon.phys.top - half
        src = QRectF(sx, sy, LOUPE_SRC, LOUPE_SRC)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        clip = QPainterPath()
        clip.addEllipse(circle)
        p.setClipPath(clip)
        p.fillRect(circle, QColor(theme.BG))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawImage(circle, self.snapshot, src)
        # crosshair: one source pixel wide, centered
        cell = size / LOUPE_SRC
        cx = circle.left() + cell * half
        cy = circle.top() + cell * half
        p.setPen(QPen(QColor(theme.ACCENT), 1))
        p.drawLine(QPointF(circle.left(), cy + cell / 2), QPointF(circle.right(), cy + cell / 2))
        p.drawLine(QPointF(cx + cell / 2, circle.top()), QPointF(cx + cell / 2, circle.bottom()))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(cx, cy, cell, cell))
        p.restore()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(circle)
        # coordinates
        label = f"{px}, {py}"
        fm = QFontMetrics(self._font_small)
        tw = fm.horizontalAdvance(label) + 14
        r = QRectF(circle.center().x() - tw / 2, circle.bottom() + 4, tw, text_h)
        self._pill(p, r, label, self._font_small)


class FrameSelector(QObject):
    confirmed = Signal(object, object)  # Rect, Monitor
    cancelled = Signal()

    def __init__(self, table: MonitorTable) -> None:
        super().__init__()
        self.table = table
        self.overlays: list[_Overlay] = []
        self.sel: Optional[Rect] = None
        self.sel_mon: Optional[Monitor] = None
        self.show_loupe = True
        self._mode: str | None = None  # new | move | resize
        self._handle: int | None = None
        self._anchor: tuple[int, int] | None = None
        self._start_rect: Optional[Rect] = None
        self._drag_mon: Optional[Monitor] = None
        self._prev_sel: Optional[Rect] = None
        self._prev_mon: Optional[Monitor] = None
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    # -- lifecycle -----------------------------------------------------------
    def open(self, initial: Optional[Rect] = None, initial_mon: Optional[Monitor] = None) -> None:
        if self._open:
            self.close()
        self.sel, self.sel_mon = (initial, initial_mon) if (initial and initial_mon) else (None, None)
        self._prev_sel, self._prev_mon = self.sel, self.sel_mon
        self._mode = None
        with mss.mss() as sct:
            for mon in self.table.monitors:
                try:
                    img = grab_monitor_image(sct, mon)
                except Exception:
                    log.exception("Snapshot failed for %s", mon.device)
                    img = QImage(mon.phys.width, mon.phys.height, QImage.Format.Format_RGB32)
                    img.fill(QColor(theme.BG))
                ov = _Overlay(self, mon, img)
                screen = self.table.screen_for(mon)
                if screen is not None:
                    ov.setScreen(screen)
                lg = mon.logical
                ov.setGeometry(lg.left, lg.top, lg.width, lg.height)
                self.overlays.append(ov)
        for ov in self.overlays:
            ov.show()
            win32.set_window_pos_physical(int(ov.winId()), ov.mon.phys.left, ov.mon.phys.top, ov.mon.phys.width, ov.mon.phys.height)
        self._open = True
        # focus the overlay under the cursor
        cp = QCursor.pos()
        mon = monitor_at_logical_point(self.table.monitors, cp.x(), cp.y()) or self.table.primary()
        target = next((o for o in self.overlays if mon and o.mon.device == mon.device), self.overlays[0] if self.overlays else None)
        if target is not None:
            target.raise_()
            target.activateWindow()
            target.setFocus(Qt.FocusReason.OtherFocusReason)
            win32.set_foreground(int(target.winId()))
        self._repaint_all()

    def close(self) -> None:
        for ov in self.overlays:
            ov.hide()
            ov.deleteLater()
        self.overlays = []
        self._open = False

    def _repaint_all(self) -> None:
        for ov in self.overlays:
            ov.update()

    # -- handles -------------------------------------------------------------
    def handle_centers_local(self, ov: _Overlay) -> dict[int, tuple[float, float]]:
        if self.sel is None:
            return {}
        r = ov.rect_to_local(self.sel).adjusted(-1, -1, 1, 1)
        cx, cy = r.center().x(), r.center().y()
        return {
            H_TL: (r.left(), r.top()),
            H_T: (cx, r.top()),
            H_TR: (r.right(), r.top()),
            H_R: (r.right(), cy),
            H_BR: (r.right(), r.bottom()),
            H_B: (cx, r.bottom()),
            H_BL: (r.left(), r.bottom()),
            H_L: (r.left(), cy),
        }

    def _hit_handle(self, ov: _Overlay, phys: tuple[int, int]) -> int | None:
        if self.sel is None or self.sel_mon is None or self.sel_mon.device != ov.mon.device:
            return None
        local = ov.to_local(*phys)
        for hid, (hx, hy) in self.handle_centers_local(ov).items():
            if abs(local.x() - hx) <= HANDLE_HIT_LOGICAL and abs(local.y() - hy) <= HANDLE_HIT_LOGICAL:
                return hid
        return None

    def _inside_sel(self, ov: _Overlay, phys: tuple[int, int]) -> bool:
        return (
            self.sel is not None
            and self.sel_mon is not None
            and self.sel_mon.device == ov.mon.device
            and self.sel.contains_point(*phys)
        )

    # -- mouse -----------------------------------------------------------------
    def on_press(self, ov: _Overlay, phys: tuple[int, int]) -> None:
        ov.activateWindow()
        ov.setFocus(Qt.FocusReason.MouseFocusReason)
        hid = self._hit_handle(ov, phys)
        if hid is not None:
            self._mode, self._handle = "resize", hid
            self._start_rect = self.sel
            self._anchor = phys
            self._drag_mon = ov.mon
        elif self._inside_sel(ov, phys):
            self._mode = "move"
            self._start_rect = self.sel
            self._anchor = phys
            self._drag_mon = ov.mon
        else:
            self._mode = "new"
            self._anchor = phys
            self._drag_mon = ov.mon
            self._start_rect = self.sel
            self.show_loupe = True
        self._repaint_all()

    def on_move(self, ov: _Overlay, phys: tuple[int, int], dragging: bool) -> None:
        if self._mode is None or not dragging or self._drag_mon is None or self._anchor is None:
            self._update_cursor(ov, phys)
            ov.update()
            return
        mon = self._drag_mon
        bounds = mon.phys
        px = min(max(phys[0], bounds.left), bounds.right)
        py = min(max(phys[1], bounds.top), bounds.bottom)
        if self._mode == "new":
            r = Rect.from_points(self._anchor[0], self._anchor[1], px, py)
            self.sel, self.sel_mon = r.intersection(bounds), mon
        elif self._mode == "move" and self._start_rect is not None:
            dx, dy = px - self._anchor[0], py - self._anchor[1]
            self.sel = fit_rect_in_bounds(self._start_rect.moved(dx, dy), bounds)
            self.sel_mon = mon
        elif self._mode == "resize" and self._start_rect is not None and self._handle is not None:
            self.sel = self._resize(self._start_rect, self._handle, px - self._anchor[0], py - self._anchor[1], bounds)
            self.sel_mon = mon
        self._repaint_all()

    def on_release(self, ov: _Overlay, phys: tuple[int, int]) -> None:
        if self._mode is None:
            return
        mode = self._mode
        self._mode = None
        mon = self._drag_mon or ov.mon
        if mode == "new":
            if self.sel is None or (self.sel.width < 4 and self.sel.height < 4):
                # a plain click: keep the previous frame if there was one
                self.sel, self.sel_mon = self._start_rect, (self.sel_mon if self._start_rect else None)
                if self._start_rect is not None and self.sel_mon is None:
                    self.sel_mon = mon
            else:
                self.sel = constrain_frame(self.sel, mon.phys)
                self.sel_mon = mon
        elif self.sel is not None:
            self.sel = constrain_frame(self.sel, mon.phys)
        self._repaint_all()

    def on_double_click(self, ov: _Overlay, phys: tuple[int, int]) -> None:
        if self._inside_sel(ov, phys):
            self._mode = None
            self.confirm()

    def _update_cursor(self, ov: _Overlay, phys: tuple[int, int]) -> None:
        hid = self._hit_handle(ov, phys)
        if hid is not None:
            ov.setCursor(_HANDLE_CURSORS[hid])
        elif self._inside_sel(ov, phys):
            ov.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            ov.setCursor(Qt.CursorShape.CrossCursor)

    @staticmethod
    def _resize(start: Rect, hid: int, dx: int, dy: int, bounds: Rect) -> Rect:
        l, t, r, b = start.left, start.top, start.right, start.bottom
        if hid in (H_TL, H_L, H_BL):
            l = min(l + dx, r - MIN_FRAME)
        if hid in (H_TR, H_R, H_BR):
            r = max(r + dx, l + MIN_FRAME)
        if hid in (H_TL, H_T, H_TR):
            t = min(t + dy, b - MIN_FRAME)
        if hid in (H_BL, H_B, H_BR):
            b = max(b + dy, t + MIN_FRAME)
        l, t = max(l, bounds.left), max(t, bounds.top)
        r, b = min(r, bounds.right), min(b, bounds.bottom)
        return Rect(l, t, max(MIN_FRAME, r - l), max(MIN_FRAME, b - t))

    # -- keyboard --------------------------------------------------------------
    def on_key(self, e: QKeyEvent) -> None:
        key = e.key()
        mods = e.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirm()
            return
        if key == Qt.Key.Key_Escape:
            self.cancel()
            return
        if self.sel is None or self.sel_mon is None:
            return
        arrows = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }
        if key not in arrows:
            return
        dx, dy = arrows[key]
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        bounds = self.sel_mon.phys
        s = self.sel
        if ctrl:
            # Ctrl+arrow grows the right/bottom edge by 1 px; Ctrl+Shift+arrow shrinks it by 1 px.
            # Right/Down act on width/height respectively; Left/Up are the natural inverses.
            grow = -1 if shift else 1
            if dx != 0:
                w = s.width + grow * (1 if dx > 0 else -1)
                s = Rect(s.left, s.top, max(MIN_FRAME, min(w, bounds.right - s.left)), s.height)
            else:
                h = s.height + grow * (1 if dy > 0 else -1)
                s = Rect(s.left, s.top, s.width, max(MIN_FRAME, min(h, bounds.bottom - s.top)))
        else:
            step = 10 if shift else 1
            s = fit_rect_in_bounds(s.moved(dx * step, dy * step), bounds)
        self.sel = s
        self._repaint_all()

    # -- outcomes --------------------------------------------------------------
    def confirm(self) -> None:
        if self.sel is None or self.sel_mon is None:
            return
        rect = constrain_frame(self.sel, self.sel_mon.phys)
        mon = self.sel_mon
        self.close()
        self.confirmed.emit(rect, mon)

    def cancel(self) -> None:
        self.close()
        self.cancelled.emit()
