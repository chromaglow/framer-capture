"""Pure DPI / coordinate math. No Qt, no Win32 imports - unit tested with fake monitor tables.

Conventions
- "physical": Windows virtual-desktop pixels (what mss and SetWindowPos use).
- "logical": Qt device-independent coordinates (QScreen.geometry(), widget positions).
- Rect is (left, top, width, height); right/bottom are exclusive.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

MIN_FRAME = 16
MAX_FRAME = 16384


def round_half_up(v: float) -> int:
    return int(math.floor(v + 0.5))


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def contains_point(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def contains_rect(self, other: "Rect") -> bool:
        return (
            other.left >= self.left
            and other.top >= self.top
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def intersects(self, other: "Rect") -> bool:
        return not self.intersection(other).is_empty

    def intersection(self, other: "Rect") -> "Rect":
        l = max(self.left, other.left)
        t = max(self.top, other.top)
        r = min(self.right, other.right)
        b = min(self.bottom, other.bottom)
        return Rect(l, t, max(0, r - l), max(0, b - t))

    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def moved(self, dx: int, dy: int) -> "Rect":
        return Rect(self.left + dx, self.top + dy, self.width, self.height)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

    @staticmethod
    def from_tuple(t: Sequence[int]) -> "Rect":
        return Rect(int(t[0]), int(t[1]), int(t[2]), int(t[3]))

    @staticmethod
    def from_points(x0: int, y0: int, x1: int, y1: int) -> "Rect":
        """Normalized rect from two corner points (inclusive-exclusive)."""
        l, r = (x0, x1) if x0 <= x1 else (x1, x0)
        t, b = (y0, y1) if y0 <= y1 else (y1, y0)
        return Rect(l, t, r - l, b - t)


@dataclass(frozen=True)
class FRect:
    """Float rect in logical coordinates (for sub-pixel exact drawing)."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Monitor:
    device: str
    phys: Rect
    logical: Rect
    primary: bool = False

    @property
    def scale_x(self) -> float:
        return self.phys.width / self.logical.width if self.logical.width else 1.0

    @property
    def scale_y(self) -> float:
        return self.phys.height / self.logical.height if self.logical.height else 1.0

    @property
    def scale(self) -> float:
        return self.scale_x


# ---- point / rect mapping -------------------------------------------------
def logical_to_physical(mon: Monitor, lx: float, ly: float) -> tuple[int, int]:
    px = mon.phys.left + round_half_up((lx - mon.logical.left) * mon.scale_x)
    py = mon.phys.top + round_half_up((ly - mon.logical.top) * mon.scale_y)
    return px, py


def physical_to_logical(mon: Monitor, px: float, py: float) -> tuple[float, float]:
    lx = mon.logical.left + (px - mon.phys.left) / mon.scale_x
    ly = mon.logical.top + (py - mon.phys.top) / mon.scale_y
    return lx, ly


def physical_to_logical_rounded(mon: Monitor, px: int, py: int) -> tuple[int, int]:
    lx, ly = physical_to_logical(mon, px, py)
    return round_half_up(lx), round_half_up(ly)


def logical_rect_to_physical(mon: Monitor, x: float, y: float, w: float, h: float) -> Rect:
    l, t = logical_to_physical(mon, x, y)
    r, b = logical_to_physical(mon, x + w, y + h)
    return Rect(l, t, r - l, b - t)


def physical_rect_to_logical(mon: Monitor, rect: Rect) -> FRect:
    x0, y0 = physical_to_logical(mon, rect.left, rect.top)
    x1, y1 = physical_to_logical(mon, rect.right, rect.bottom)
    return FRect(x0, y0, x1 - x0, y1 - y0)


def physical_rect_to_logical_rounded(mon: Monitor, rect: Rect) -> Rect:
    f = physical_rect_to_logical(mon, rect)
    x0, y0 = round_half_up(f.x), round_half_up(f.y)
    x1, y1 = round_half_up(f.x + f.w), round_half_up(f.y + f.h)
    return Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))


def physical_length_to_logical(mon: Monitor, length: float) -> float:
    return length / mon.scale_x


def logical_length_to_physical(mon: Monitor, length: float) -> int:
    return round_half_up(length * mon.scale_x)


# ---- monitor lookup -------------------------------------------------------
def monitor_at_physical_point(monitors: Iterable[Monitor], px: int, py: int) -> Monitor | None:
    for m in monitors:
        if m.phys.contains_point(px, py):
            return m
    return None


def monitor_at_logical_point(monitors: Iterable[Monitor], lx: float, ly: float) -> Monitor | None:
    for m in monitors:
        lg = m.logical
        if lg.left <= lx < lg.right and lg.top <= ly < lg.bottom:
            return m
    return None


def monitor_for_rect(monitors: Iterable[Monitor], rect: Rect) -> Monitor | None:
    """Monitor with the largest overlap with rect (None if no overlap)."""
    best, best_area = None, 0
    for m in monitors:
        a = m.phys.intersection(rect).area()
        if a > best_area:
            best, best_area = m, a
    return best


def monitor_by_device(monitors: Iterable[Monitor], device: str) -> Monitor | None:
    for m in monitors:
        if m.device == device:
            return m
    return None


def primary_monitor(monitors: Sequence[Monitor]) -> Monitor | None:
    for m in monitors:
        if m.primary:
            return m
    return monitors[0] if monitors else None


def frame_fits(frame: Rect, monitors: Iterable[Monitor]) -> Monitor | None:
    """The monitor that fully contains frame, or None."""
    for m in monitors:
        if m.phys.contains_rect(frame):
            return m
    return None


def remembered_frame_valid(last_frame: dict | None, monitors: Iterable[Monitor]) -> Monitor | None:
    """Spec 9.9: same device name must exist with the same physical rect, and the frame must fit."""
    if not last_frame:
        return None
    mon = monitor_by_device(monitors, last_frame.get("monitor_device", ""))
    if mon is None:
        return None
    try:
        if list(mon.phys.as_tuple()) != [int(v) for v in last_frame["monitor_rect"]]:
            return None
        frame = Rect(int(last_frame["left"]), int(last_frame["top"]), int(last_frame["width"]), int(last_frame["height"]))
    except (KeyError, TypeError, ValueError):
        return None
    if frame.width < MIN_FRAME or frame.height < MIN_FRAME or not mon.phys.contains_rect(frame):
        return None
    return mon


# ---- frame constraints ----------------------------------------------------
def clamp_point_to_rect(x: int, y: int, bounds: Rect) -> tuple[int, int]:
    return (min(max(x, bounds.left), bounds.right), min(max(y, bounds.top), bounds.bottom))


def clamp_rect_to_bounds(rect: Rect, bounds: Rect) -> Rect:
    """Clip rect to bounds (may shrink it)."""
    return rect.intersection(bounds)


def fit_rect_in_bounds(rect: Rect, bounds: Rect) -> Rect:
    """Move rect so it lies inside bounds without changing size (size clipped if too big)."""
    w = min(rect.width, bounds.width)
    h = min(rect.height, bounds.height)
    l = min(max(rect.left, bounds.left), bounds.right - w)
    t = min(max(rect.top, bounds.top), bounds.bottom - h)
    return Rect(l, t, w, h)


def constrain_frame(rect: Rect, bounds: Rect, min_size: int = MIN_FRAME, max_size: int = MAX_FRAME) -> Rect:
    """Clip to the monitor, enforce min 16x16 and max 16384, keep inside bounds."""
    r = clamp_rect_to_bounds(rect, bounds)
    w = min(max(r.width, min_size), max_size, bounds.width)
    h = min(max(r.height, min_size), max_size, bounds.height)
    return fit_rect_in_bounds(Rect(r.left, r.top, w, h), bounds)


# ---- frame border strips -------------------------------------------------
def border_strips(frame: Rect, bounds: Rect, gap: int = 2, thick: int = 3) -> list[Rect]:
    """Four strips forming an outline `thick` px wide with `gap` px between frame and outline.

    Order: top, bottom, left, right. Each is clipped to `bounds`; strips that vanish are
    returned empty (width or height 0) so callers can hide the corresponding window.
    """
    outer = Rect(
        frame.left - gap - thick,
        frame.top - gap - thick,
        frame.width + 2 * (gap + thick),
        frame.height + 2 * (gap + thick),
    )
    top = Rect(outer.left, outer.top, outer.width, thick)
    bottom = Rect(outer.left, outer.bottom - thick, outer.width, thick)
    left = Rect(outer.left, outer.top + thick, thick, outer.height - 2 * thick)
    right = Rect(outer.right - thick, outer.top + thick, thick, outer.height - 2 * thick)
    return [s.intersection(bounds) for s in (top, bottom, left, right)]


# ---- floating bar placement ----------------------------------------------
def bar_candidates(frame: Rect, bar_w: int, bar_h: int, gap: int) -> list[Rect]:
    """Right (top-aligned), left, below (left-aligned), above."""
    return [
        Rect(frame.right + gap, frame.top, bar_w, bar_h),
        Rect(frame.left - gap - bar_w, frame.top, bar_w, bar_h),
        Rect(frame.left, frame.bottom + gap, bar_w, bar_h),
        Rect(frame.left, frame.top - gap - bar_h, bar_w, bar_h),
    ]


def place_bar(frame: Rect, bar_w: int, bar_h: int, bounds: Rect, gap: int) -> Rect:
    """First candidate fully inside bounds and not overlapping the frame; else monitor top-right.

    When the frame fills the monitor no non-overlapping spot exists; the corner is then the
    least-bad answer (it is also excluded from capture by display affinity).
    """
    for c in bar_candidates(frame, bar_w, bar_h, gap):
        if bounds.contains_rect(c) and not c.intersects(frame):
            return c
    corner = Rect(bounds.right - bar_w - gap, bounds.top + gap, bar_w, bar_h)
    return fit_rect_in_bounds(corner, bounds)


def snap_bar_outside(bar: Rect, frame: Rect, bounds: Rect, gap: int) -> Rect:
    """If bar overlaps frame, push it out to the nearest side that still fits in bounds."""
    if not bar.intersects(frame):
        return fit_rect_in_bounds(bar, bounds)
    options = [
        Rect(frame.right + gap, bar.top, bar.width, bar.height),  # right
        Rect(frame.left - gap - bar.width, bar.top, bar.width, bar.height),  # left
        Rect(bar.left, frame.bottom + gap, bar.width, bar.height),  # below
        Rect(bar.left, frame.top - gap - bar.height, bar.width, bar.height),  # above
    ]
    # distance moved, prefer options that fit entirely
    scored: list[tuple[int, int, Rect]] = []
    for o in options:
        fitted = fit_rect_in_bounds(o, bounds)
        fits = 0 if (bounds.contains_rect(o) and not fitted.intersects(frame)) else 1
        if fitted.intersects(frame):
            continue
        dist = abs(fitted.left - bar.left) + abs(fitted.top - bar.top)
        scored.append((fits, dist, fitted))
    if not scored:
        return fit_rect_in_bounds(bar, bounds)
    scored.sort(key=lambda s: (s[0], s[1]))
    return scored[0][2]


# ---- screen matching ------------------------------------------------------
@dataclass(frozen=True)
class ScreenInfo:
    """Minimal description of a Qt screen so matching stays Qt-free."""

    name: str
    logical: Rect
    index: int
    dpr: float = 1.0

    @property
    def derived_phys(self) -> Rect:
        """Qt keeps native origins for screens and scales only the size, so this is the physical rect."""
        return Rect(self.logical.left, self.logical.top, round_half_up(self.logical.width * self.dpr), round_half_up(self.logical.height * self.dpr))


@dataclass(frozen=True)
class RawMonitor:
    device: str
    phys: Rect
    primary: bool


def _rects_close(a: Rect, b: Rect, tol: int = 2) -> bool:
    return (
        abs(a.left - b.left) <= tol and abs(a.top - b.top) <= tol
        and abs(a.width - b.width) <= tol and abs(a.height - b.height) <= tol
    )


def match_screens(raw: Sequence[RawMonitor], screens: Sequence[ScreenInfo]) -> tuple[list[Monitor], str]:
    """Match Win32 monitors with Qt screens. Returns (monitors, method).

    method: "name" (QScreen.name() == szDevice), "geometry" (physical rect derived from the
    screen's logical geometry and device pixel ratio), or "order" (sorted by left/top; last resort).
    """
    by_name = {s.name: s for s in screens}
    if raw and all(r.device in by_name for r in raw) and len(by_name) == len(screens):
        return [Monitor(r.device, r.phys, by_name[r.device].logical, r.primary) for r in raw], "name"
    # geometry
    out: list[Monitor] = []
    remaining = list(screens)
    for r in raw:
        hit = next((s for s in remaining if _rects_close(s.derived_phys, r.phys)), None)
        if hit is None:
            break
        remaining.remove(hit)
        out.append(Monitor(r.device, r.phys, hit.logical, r.primary))
    if len(out) == len(raw) and raw:
        return out, "geometry"
    # order
    raw_sorted = sorted(raw, key=lambda r: (r.phys.left, r.phys.top))
    scr_sorted = sorted(screens, key=lambda s: (s.logical.left, s.logical.top))
    out = [Monitor(r.device, r.phys, s.logical, r.primary) for r, s in zip(raw_sorted, scr_sorted)]
    return out, "order"
