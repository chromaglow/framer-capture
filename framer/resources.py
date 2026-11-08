"""Asset paths (frozen or source tree) and the app icon."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from . import theme


def asset_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "framer" / "assets"
    return Path(__file__).resolve().parent / "assets"


def asset_path(name: str) -> Path:
    return asset_dir() / name


def draw_icon_pixmap(size: int) -> QPixmap:
    """Dark rounded square with four cyan corner brackets (same design as the .ico)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    radius = size * 0.22
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.fillPath(path, QColor(theme.BG))
    pen = QPen(QColor(theme.ACCENT))
    pen.setWidthF(max(1.0, size * 0.11))
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    m = size * 0.22
    arm = size * 0.20
    s = size
    corners = [
        (QPointF(m, m), QPointF(1, 0), QPointF(0, 1)),
        (QPointF(s - m, m), QPointF(-1, 0), QPointF(0, 1)),
        (QPointF(m, s - m), QPointF(1, 0), QPointF(0, -1)),
        (QPointF(s - m, s - m), QPointF(-1, 0), QPointF(0, -1)),
    ]
    for origin, dx, dy in corners:
        bracket = QPainterPath(origin + dx * arm)
        bracket.lineTo(origin)
        bracket.lineTo(origin + dy * arm)
        p.drawPath(bracket)
    p.end()
    return pm


_ICON: QIcon | None = None


def app_icon() -> QIcon:
    global _ICON
    if _ICON is not None:
        return _ICON
    ico = asset_path("framer.ico")
    icon = QIcon(str(ico)) if ico.exists() else QIcon()
    if icon.isNull() or not icon.availableSizes():
        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 128, 256):
            icon.addPixmap(draw_icon_pixmap(size))
    _ICON = icon
    return icon
