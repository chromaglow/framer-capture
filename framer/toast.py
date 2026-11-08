"""Toasts: small rounded pills below the floating bar. Click-through, no focus, capture-excluded."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from . import theme, win32
from .geometry import Monitor, Rect, fit_rect_in_bounds, physical_rect_to_logical_rounded

SUCCESS, WARNING, ERROR = "success", "warning", "error"
DURATIONS_MS = {SUCCESS: 1600, WARNING: 1600, ERROR: 4000}
FADE_MS = 300
STRIPE_W = 4


class Toast(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._text = ""
        self._kind = SUCCESS
        self._font = QFont(theme.FONT_FAMILY, theme.FONT_PT_BODY)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(FADE_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_fade_done)
        self._styled = False

    def _apply_win32(self) -> None:
        hwnd = int(self.winId())
        win32.make_click_through(hwnd)
        win32.exclude_from_capture(hwnd)
        self._styled = True

    # -- public ------------------------------------------------------------
    def show_message(self, text: str, kind: str, anchor: Rect | None, avoid: Rect | None, mon: Monitor | None) -> None:
        """anchor / avoid / mon are in physical pixels. anchor = bar rect, avoid = frame rect."""
        self._anim.stop()
        self._text = text
        self._kind = kind
        fm = QFontMetrics(self._font)
        pad_x, pad_y = 14, 8
        w = fm.horizontalAdvance(text) + 2 * pad_x + (STRIPE_W + 6 if kind != SUCCESS else 0)
        h = fm.height() + 2 * pad_y
        self.resize(w, h)
        self.setWindowOpacity(1.0)
        if mon is not None:
            scale = mon.scale
            pw, ph = int(round(w * scale)), int(round(h * scale))
            gap = int(round(6 * scale))
            if anchor is not None:
                cx = anchor.left + (anchor.width - pw) // 2
                candidates = [
                    Rect(cx, anchor.bottom + gap, pw, ph),            # centered below
                    Rect(anchor.left, anchor.bottom + gap, pw, ph),   # left-aligned below
                    Rect(cx, anchor.top - gap - ph, pw, ph),          # centered above
                    Rect(anchor.left, anchor.top - gap - ph, pw, ph), # left-aligned above
                ]
                target = fit_rect_in_bounds(candidates[0], mon.phys)
                if avoid is not None:
                    for c in candidates:
                        fitted = fit_rect_in_bounds(c, mon.phys)
                        if not fitted.intersects(avoid):
                            target = fitted
                            break
            else:
                target = Rect(mon.phys.left + (mon.phys.width - pw) // 2, mon.phys.top + int(80 * scale), pw, ph)
            lg = physical_rect_to_logical_rounded(mon, target)
            self.setGeometry(lg.left, lg.top, lg.width, lg.height)
            self.show()
            if not self._styled:
                self._apply_win32()
            win32.set_window_pos_physical(int(self.winId()), target.left, target.top, target.width, target.height)
        else:
            self.show()
            if not self._styled:
                self._apply_win32()
        self.raise_()
        self.update()
        self._timer.start(DURATIONS_MS.get(kind, 1600))

    def hide_now(self) -> None:
        self._timer.stop()
        self._anim.stop()
        self.hide()

    # -- internals ---------------------------------------------------------
    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_fade_done(self) -> None:
        if self.windowOpacity() < 0.05:
            self.hide()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, QColor(theme.PANEL))
        p.setClipPath(path)
        text_x = 14
        if self._kind != SUCCESS:
            color = QColor(theme.WARNING if self._kind == WARNING else theme.ERROR)
            p.fillRect(QRectF(0, 0, STRIPE_W + 6, r.height() + 1), color)
            text_x += STRIPE_W + 6
        p.setPen(QColor(theme.TEXT))
        p.setFont(self._font)
        p.drawText(QRectF(text_x, 0, self.width() - text_x, self.height()), Qt.AlignmentFlag.AlignVCenter, self._text)
        p.end()
