"""Floating Bar beside the frame (spec 5.4)."""
from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QMouseEvent, QPainter, QPainterPath, QPixmap, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from . import theme, win32
from .geometry import (
    Monitor,
    Rect,
    fit_rect_in_bounds,
    logical_length_to_physical,
    logical_rect_to_physical,
    physical_rect_to_logical_rounded,
    place_bar,
    snap_bar_outside,
)

log = logging.getLogger(__name__)

BAR_W, BAR_H = 330, 76
THUMB = 56
GLYPH_FONT = "Segoe UI Symbol"


class _Thumb(QLabel):
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(THUMB, THUMB)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Open the last capture")
        self._pix: QPixmap | None = None

    def set_image(self, pix: QPixmap | None) -> None:
        self._pix = pix
        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self._pix is not None:
            self.clicked.emit()
        e.accept()

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        e.accept()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 6, 6)
        p.fillPath(path, QColor(theme.PANEL_RAISED))
        if self._pix is None:
            pen = p.pen()
            pen.setColor(QColor(theme.BORDER_LINE))
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawPath(path)
            p.setPen(QColor(theme.TEXT_MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
        else:
            p.setClipPath(path)
            scaled = self._pix.scaled(
                int(THUMB * self.devicePixelRatioF()), int(THUMB * self.devicePixelRatioF()),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(self.devicePixelRatioF())
            w = scaled.width() / scaled.devicePixelRatio()
            h = scaled.height() / scaled.devicePixelRatio()
            p.drawPixmap(QRectF((THUMB - w) / 2, (THUMB - h) / 2, w, h).toRect(), scaled)
        p.end()


def _glyph_button(glyph: str, tip: str) -> QPushButton:
    b = QPushButton(glyph)
    b.setObjectName("bar")
    b.setToolTip(tip)
    b.setFont(QFont(GLYPH_FONT, 12))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


class FloatingBar(QWidget):
    capture = Signal()
    reframe = Signal()
    undo = Signal()
    open_folder = Signal()
    make_pdf = Signal()
    setup = Signal()
    stop = Signal()
    quit = Signal()
    open_last = Signal()
    moved_by_user = Signal(object)  # Rect (physical)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(BAR_W, BAR_H)
        self._styled = False
        self._drag_origin: QPoint | None = None
        self._drag_start_pos: QPoint | None = None
        self._dragged = False
        self._frame: Rect | None = None
        self._mon: Monitor | None = None
        self._phys: Rect | None = None
        self._build()
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo.emit)

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 8, 10)
        root.setSpacing(10)
        self.thumb = _Thumb()
        self.thumb.clicked.connect(self.open_last)
        root.addWidget(self.thumb)

        mid = QVBoxLayout()
        mid.setSpacing(1)
        mid.setContentsMargins(0, 0, 0, 0)
        self.lbl_prefix = QLabel("Capture")
        f = QFont(theme.FONT_FAMILY, theme.FONT_PT_SMALL)
        f.setBold(True)
        self.lbl_prefix.setFont(f)
        self.lbl_prefix.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_counts = QLabel("Next: 0001 · Saved: 0")
        self.lbl_counts.setFont(QFont(theme.FONT_FAMILY, theme.FONT_PT_SMALL))
        self.lbl_size = QLabel("")
        self.lbl_size.setObjectName("muted")
        self.lbl_size.setFont(QFont(theme.FONT_FAMILY, 8))
        for w in (self.lbl_prefix, self.lbl_counts, self.lbl_size):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            mid.addWidget(w)
        root.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(0)
        right.setContentsMargins(0, 0, 0, 0)
        row1 = QHBoxLayout()
        row1.setSpacing(0)
        row2 = QHBoxLayout()
        row2.setSpacing(0)
        self.btn_capture = _glyph_button("●", "Capture (F9)")
        self.btn_reframe = _glyph_button("⛶", "Reframe (F8)")
        self.btn_undo = _glyph_button("↶", "Undo last capture (moves it to the Recycle Bin)")
        self.btn_folder = _glyph_button("🗀", "Open output folder")
        self.btn_more = _glyph_button("⋯", "More")
        self.btn_undo.setEnabled(False)
        row1.addWidget(self.btn_capture)
        row1.addWidget(self.btn_reframe)
        row1.addWidget(self.btn_undo)
        row2.addWidget(self.btn_folder)
        row2.addWidget(self.btn_more)
        row2.addStretch(1)
        right.addLayout(row1)
        right.addLayout(row2)
        root.addLayout(right)

        self.btn_capture.clicked.connect(self.capture)
        self.btn_reframe.clicked.connect(self.reframe)
        self.btn_undo.clicked.connect(self.undo)
        self.btn_folder.clicked.connect(self.open_folder)
        self.btn_more.clicked.connect(self._show_menu)

        self.menu = QMenu(self)
        self.menu.addAction("Make PDF…", self.make_pdf.emit)
        self.menu.addAction("Setup…", self.setup.emit)
        self.menu.addSeparator()
        self.menu.addAction("Stop framing", self.stop.emit)
        self.menu.addAction("Quit", self.quit.emit)

    def _show_menu(self) -> None:
        self.menu.exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))

    # -- state ---------------------------------------------------------------
    def set_hotkey_labels(self, set_frame: str, capture: str) -> None:
        self.btn_capture.setToolTip(f"Capture ({capture})")
        self.btn_reframe.setToolTip(f"Reframe ({set_frame})")

    def set_info(self, prefix: str, next_label: str, saved: int, frame: Rect | None) -> None:
        fm = self.lbl_prefix.fontMetrics()
        self.lbl_prefix.setText(fm.elidedText(prefix, Qt.TextElideMode.ElideMiddle, 160))
        self.lbl_prefix.setToolTip(prefix)
        self.lbl_counts.setText(f"Next: {next_label} · Saved: {saved}")
        self.lbl_size.setText(f"{frame.width} × {frame.height} px" if frame else "")

    def set_thumbnail(self, pix: QPixmap | None) -> None:
        self.thumb.set_image(pix)

    def set_undo_enabled(self, enabled: bool) -> None:
        self.btn_undo.setEnabled(enabled)

    def highlight_folder(self) -> None:
        self.btn_folder.setStyleSheet(f"QPushButton#bar {{ background: {theme.ACCENT}; color: {theme.BG}; }}")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(2500, lambda: self.btn_folder.setStyleSheet(""))

    @property
    def phys_rect(self) -> Rect | None:
        return self._phys

    # -- placement -------------------------------------------------------------
    def place_for_frame(self, frame: Rect, mon: Monitor, offset: list[int] | None) -> None:
        """Position beside the frame (physical), honoring a remembered offset when still valid."""
        self._frame, self._mon = frame, mon
        bw = logical_length_to_physical(mon, BAR_W)
        bh = logical_length_to_physical(mon, BAR_H)
        gap = logical_length_to_physical(mon, theme.BAR_GAP_LOGICAL)
        target: Rect | None = None
        if offset is not None:
            cand = Rect(frame.left + int(offset[0]), frame.top + int(offset[1]), bw, bh)
            cand = fit_rect_in_bounds(cand, mon.phys)
            if not cand.intersects(frame):
                target = cand
        if target is None:
            target = place_bar(frame, bw, bh, mon.phys, gap)
        self._apply_phys(target)

    def _apply_phys(self, target: Rect) -> None:
        assert self._mon is not None
        self._phys = target
        lg = physical_rect_to_logical_rounded(self._mon, target)
        screen = None
        self.move(lg.left, lg.top)
        self.show()
        if not self._styled:
            hwnd = int(self.winId())
            win32.make_tool_noactivate(hwnd)
            win32.exclude_from_capture(hwnd)
            self._styled = True
        win32.set_window_pos_physical(int(self.winId()), target.left, target.top, target.width, target.height)
        del screen

    def reapply(self) -> None:
        if self._phys is not None and self.isVisible():
            self._apply_phys(self._phys)

    # -- dragging --------------------------------------------------------------
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = e.globalPosition().toPoint()
            self._drag_start_pos = self.pos()
            self._dragged = False
        e.accept()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._drag_origin is not None and e.buttons() & Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self._drag_origin
            if delta.manhattanLength() > 2:
                self._dragged = True
            self.move(self._drag_start_pos + delta)
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            self._drag_origin = None
            if self._dragged and self._frame is not None and self._mon is not None:
                mon = self._mon
                g = self.geometry()
                phys = logical_rect_to_physical(mon, g.x(), g.y(), g.width(), g.height())
                bw = logical_length_to_physical(mon, BAR_W)
                bh = logical_length_to_physical(mon, BAR_H)
                phys = Rect(phys.left, phys.top, bw, bh)
                gap = logical_length_to_physical(mon, theme.BAR_GAP_LOGICAL)
                phys = snap_bar_outside(phys, self._frame, mon.phys, gap)
                self._apply_phys(phys)
                self.moved_by_user.emit(phys)
        e.accept()

    # -- painting ----------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, theme.RADIUS_WINDOW, theme.RADIUS_WINDOW)
        p.fillPath(path, QColor(theme.PANEL))
        p.setPen(QColor(theme.BORDER_LINE))
        p.drawPath(path)
        p.end()
