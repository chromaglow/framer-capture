"""Frame Border: four click-through, capture-excluded strips just outside the capture rectangle."""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from . import theme, win32
from .geometry import Monitor, Rect, border_strips, physical_rect_to_logical_rounded


class _Strip(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.color = QColor(theme.ACCENT)
        self._styled = False

    def ensure_styles(self) -> None:
        if self._styled:
            return
        hwnd = int(self.winId())
        win32.make_click_through(hwnd)
        win32.exclude_from_capture(hwnd)
        self._styled = True

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), self.color)
        p.end()


class FrameBorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.strips = [_Strip() for _ in range(4)]
        self._phys: list[Rect] = []
        self._frame: Rect | None = None
        self._mon: Monitor | None = None
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._restore_color)
        self.visible = False

    def show_for(self, frame: Rect, mon: Monitor) -> None:
        self._frame, self._mon = frame, mon
        self._phys = border_strips(frame, mon.phys, theme.BORDER_GAP, theme.BORDER_THICKNESS)
        screen = None
        for strip, r in zip(self.strips, self._phys):
            if r.is_empty:
                strip.hide()
                continue
            lg = physical_rect_to_logical_rounded(mon, r)
            strip.setGeometry(lg.left, lg.top, lg.width, lg.height)
            strip.show()
            strip.ensure_styles()
            win32.set_window_pos_physical(int(strip.winId()), r.left, r.top, r.width, r.height)
            strip.update()
        del screen
        self.visible = True

    def reapply(self) -> None:
        """Re-pin exact physical geometry (after Qt may have nudged windows)."""
        if self._frame and self._mon and self.visible:
            self.show_for(self._frame, self._mon)

    def hide(self) -> None:
        for s in self.strips:
            s.hide()
        self.visible = False

    def set_color(self, color: str) -> None:
        for s in self.strips:
            s.color = QColor(color)
            s.update()

    def flash(self, color: str, ms: int) -> None:
        self._flash_timer.stop()
        self.set_color(color)
        self._flash_timer.start(ms)

    def _restore_color(self) -> None:
        self.set_color(theme.ACCENT)
