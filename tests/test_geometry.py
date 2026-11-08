import pytest

from framer.geometry import (
    FRect,
    Monitor,
    RawMonitor,
    Rect,
    ScreenInfo,
    border_strips,
    constrain_frame,
    frame_fits,
    logical_rect_to_physical,
    logical_to_physical,
    match_screens,
    monitor_at_physical_point,
    monitor_for_rect,
    physical_rect_to_logical,
    physical_to_logical,
    place_bar,
    remembered_frame_valid,
    round_half_up,
    snap_bar_outside,
)


def mon(device, phys, logical, primary=False):
    return Monitor(device, Rect(*phys), Rect(*logical), primary)


# Fake tables ---------------------------------------------------------------
M100 = mon(r"\\.\DISPLAY1", (0, 0, 1920, 1080), (0, 0, 1920, 1080), True)
M125 = mon(r"\\.\DISPLAY1", (0, 0, 1920, 1080), (0, 0, 1536, 864), True)
M150 = mon(r"\\.\DISPLAY1", (0, 0, 3840, 2160), (0, 0, 2560, 1440), True)
M175 = mon(r"\\.\DISPLAY1", (0, 0, 3840, 2160), (0, 0, 2194, 1234), True)  # Qt rounds; still exact round trip
M200 = mon(r"\\.\DISPLAY1", (0, 0, 3840, 2160), (0, 0, 1920, 1080), True)

# Mixed DPI side-by-side: 4K@150% primary, 1440p@100% to the right (Qt logical offset is Qt's business)
MIXED = [
    mon(r"\\.\DISPLAY1", (0, 0, 3840, 2160), (0, 0, 2560, 1440), True),
    mon(r"\\.\DISPLAY2", (3840, 0, 2560, 1440), (2560, 0, 2560, 1440)),
]
# Left monitor with negative coordinates @125%
NEG = [
    mon(r"\\.\DISPLAY1", (0, 0, 3840, 2160), (0, 0, 2560, 1440), True),
    mon(r"\\.\DISPLAY2", (-3440, 839, 3440, 1440), (-2752, 671, 2752, 1152)),
]
# Vertically stacked @100% above @200%
STACK = [
    mon(r"\\.\DISPLAY1", (0, 0, 1920, 1080), (0, 0, 1920, 1080), True),
    mon(r"\\.\DISPLAY2", (0, 1080, 3840, 2160), (0, 1080, 1920, 1080)),
]
# Ezra's real layout: 150% / 125% / 100%
REAL = [
    mon(r"\\.\DISPLAY1", (0, 0, 3840, 2160), (0, 0, 2560, 1440), True),
    mon(r"\\.\DISPLAY2", (-3440, 839, 3440, 1440), (-2752, 671, 2752, 1152)),
    mon(r"\\.\DISPLAY3", (-2959, -601, 2560, 1440), (-2959, -601, 2560, 1440)),
]

ALL_SINGLE = [M100, M125, M150, M175, M200]
ALL_TABLES = [[m] for m in ALL_SINGLE] + [MIXED, NEG, STACK, REAL]


def test_round_half_up():
    assert round_half_up(0.5) == 1
    assert round_half_up(1.5) == 2
    assert round_half_up(2.5) == 3
    assert round_half_up(-0.5) == 0
    assert round_half_up(-1.5) == -1
    assert round_half_up(2.49) == 2


@pytest.mark.parametrize("table", ALL_TABLES)
def test_physical_to_logical_and_back_is_exact(table):
    for m in table:
        step_x = max(1, m.phys.width // 97)
        step_y = max(1, m.phys.height // 89)
        for px in range(m.phys.left, m.phys.right + 1, step_x):
            for py in range(m.phys.top, m.phys.bottom + 1, step_y):
                lx, ly = physical_to_logical(m, px, py)
                assert logical_to_physical(m, lx, ly) == (px, py)


@pytest.mark.parametrize("table", ALL_TABLES)
def test_logical_to_physical_and_back_rounds_exact(table):
    for m in table:
        for lx in range(m.logical.left, m.logical.right + 1, 7):
            for ly in range(m.logical.top, m.logical.bottom + 1, 11):
                px, py = logical_to_physical(m, lx, ly)
                bx, by = physical_to_logical(m, px, py)
                assert round_half_up(bx) == lx
                assert round_half_up(by) == ly


@pytest.mark.parametrize("m", ALL_SINGLE)
def test_corners_map_to_corners(m):
    assert logical_to_physical(m, m.logical.left, m.logical.top) == (m.phys.left, m.phys.top)
    assert logical_to_physical(m, m.logical.right, m.logical.bottom) == (m.phys.right, m.phys.bottom)
    assert physical_to_logical(m, m.phys.right, m.phys.bottom) == (m.logical.right, m.logical.bottom)


def test_rect_round_trip_physical_logical_physical():
    for table in ALL_TABLES:
        for m in table:
            r = Rect(m.phys.left + 101, m.phys.top + 37, 1234, 567)
            f = physical_rect_to_logical(m, r)
            assert isinstance(f, FRect)
            back = logical_rect_to_physical(m, f.x, f.y, f.w, f.h)
            assert back == r


def test_negative_monitor_point_lookup():
    assert monitor_at_physical_point(NEG, -1, 900).device == r"\\.\DISPLAY2"
    assert monitor_at_physical_point(NEG, 0, 0).device == r"\\.\DISPLAY1"
    assert monitor_at_physical_point(NEG, -3441, 900) is None
    # a logical point on the left monitor maps into its physical rect
    m2 = NEG[1]
    px, py = logical_to_physical(m2, -2752, 671)
    assert (px, py) == (-3440, 839)
    px, py = logical_to_physical(m2, -2752 + 2752, 671 + 1152)
    assert (px, py) == (0, 839 + 1440)


def test_stacked_lookup_and_scale():
    assert monitor_at_physical_point(STACK, 10, 1079).device == r"\\.\DISPLAY1"
    assert monitor_at_physical_point(STACK, 10, 1080).device == r"\\.\DISPLAY2"
    assert STACK[1].scale == 2.0
    assert logical_to_physical(STACK[1], 100, 1180) == (200, 1280)


def test_monitor_for_rect_prefers_largest_overlap():
    r = Rect(3000, 100, 1500, 500)  # 840 on DISPLAY1, 660 on DISPLAY2
    assert monitor_for_rect(MIXED, r).device == r"\\.\DISPLAY1"
    assert frame_fits(r, MIXED) is None
    assert frame_fits(Rect(3900, 100, 100, 100), MIXED).device == r"\\.\DISPLAY2"


def test_constrain_frame():
    b = Rect(0, 0, 3840, 2160)
    assert constrain_frame(Rect(10, 10, 5, 5), b) == Rect(10, 10, 16, 16)
    assert constrain_frame(Rect(-50, -50, 100, 100), b) == Rect(0, 0, 50, 50)
    assert constrain_frame(Rect(3830, 2150, 100, 100), b) == Rect(3824, 2144, 16, 16)
    big = constrain_frame(Rect(0, 0, 50000, 50000), b)
    assert big == b
    # negative-coordinate monitor
    b2 = Rect(-3440, 839, 3440, 1440)
    assert constrain_frame(Rect(-3500, 800, 200, 200), b2) == Rect(-3440, 839, 140, 161)


def test_border_strips_geometry_and_clipping():
    frame = Rect(100, 100, 200, 150)
    strips = border_strips(frame, Rect(0, 0, 1000, 1000), gap=2, thick=3)
    top, bottom, left, right = strips
    assert top == Rect(95, 95, 210, 3)
    assert bottom == Rect(95, 252, 210, 3)
    assert left == Rect(95, 98, 3, 154)
    assert right == Rect(302, 98, 3, 154)
    # innermost border pixel is exactly 2 px outside the frame
    assert top.bottom == frame.top - 2
    assert left.right == frame.left - 2
    assert right.left == frame.right + 2
    assert bottom.top == frame.bottom + 2
    for s in strips:
        assert not s.intersects(frame)
    # frame touching the monitor edge: strips clip (left strip vanishes)
    clipped = border_strips(Rect(0, 0, 200, 150), Rect(0, 0, 1000, 1000))
    assert clipped[2].is_empty
    assert clipped[0] == Rect(0, 0, 205, 0) or clipped[0].is_empty
    assert clipped[3] == Rect(202, 0, 3, 150 + 2)


def test_place_bar_order_and_fallback():
    bounds = Rect(0, 0, 3840, 2160)
    bar_w, bar_h, gap = 450, 114, 18
    frame = Rect(1000, 500, 800, 600)
    assert place_bar(frame, bar_w, bar_h, bounds, gap) == Rect(1818, 500, bar_w, bar_h)
    # frame against the right edge -> left
    frame = Rect(3040, 500, 800, 600)
    assert place_bar(frame, bar_w, bar_h, bounds, gap) == Rect(3040 - gap - bar_w, 500, bar_w, bar_h)
    # full-width frame -> below
    frame = Rect(0, 500, 3840, 600)
    assert place_bar(frame, bar_w, bar_h, bounds, gap) == Rect(0, 1118, bar_w, bar_h)
    # full-width frame at the bottom -> above
    frame = Rect(0, 1560, 3840, 600)
    assert place_bar(frame, bar_w, bar_h, bounds, gap) == Rect(0, 1560 - gap - bar_h, bar_w, bar_h)
    # frame covers the whole monitor -> corner fallback, never overlapping is impossible; still inside bounds
    frame = Rect(0, 0, 3840, 2160)
    r = place_bar(frame, bar_w, bar_h, bounds, gap)
    assert bounds.contains_rect(r)
    # never overlaps the frame when any side has room
    for frame in (Rect(500, 500, 2000, 1000), Rect(0, 0, 3000, 2000), Rect(840, 160, 3000, 2000)):
        r = place_bar(frame, bar_w, bar_h, bounds, gap)
        assert not r.intersects(frame)
        assert bounds.contains_rect(r)


def test_snap_bar_outside():
    bounds = Rect(0, 0, 3840, 2160)
    frame = Rect(1000, 500, 800, 600)
    inside = Rect(1700, 520, 450, 114)  # overlaps right part of frame
    out = snap_bar_outside(inside, frame, bounds, 18)
    assert not out.intersects(frame)
    assert out == Rect(1818, 520, 450, 114)
    # already outside -> unchanged
    assert snap_bar_outside(Rect(10, 10, 450, 114), frame, bounds, 18) == Rect(10, 10, 450, 114)


def test_remembered_frame_valid():
    lf = {"left": 100, "top": 100, "width": 500, "height": 400,
          "monitor_device": r"\\.\DISPLAY2", "monitor_rect": [-3440, 839, 3440, 1440]}
    assert remembered_frame_valid(lf, NEG) is None  # frame not inside that monitor
    lf2 = dict(lf, left=-3000, top=900)
    assert remembered_frame_valid(lf2, NEG).device == r"\\.\DISPLAY2"
    assert remembered_frame_valid(dict(lf2, monitor_rect=[0, 0, 1, 1]), NEG) is None
    assert remembered_frame_valid(dict(lf2, monitor_device=r"\\.\DISPLAY9"), NEG) is None
    assert remembered_frame_valid(None, NEG) is None


def test_match_screens_by_name_then_fallback():
    raw = [RawMonitor(r"\\.\DISPLAY1", Rect(0, 0, 3840, 2160), True),
           RawMonitor(r"\\.\DISPLAY2", Rect(-3440, 839, 3440, 1440), False)]
    screens = [ScreenInfo(r"\\.\DISPLAY2", Rect(-2752, 671, 2752, 1152), 0),
               ScreenInfo(r"\\.\DISPLAY1", Rect(0, 0, 2560, 1440), 1)]
    mons, method = match_screens(raw, screens)
    assert method == "name"
    assert mons[0].device == r"\\.\DISPLAY1" and mons[0].logical == Rect(0, 0, 2560, 1440)
    assert mons[1].scale == pytest.approx(1.25)
    # names mismatch (Qt 6 reports friendly names) -> geometry match via native origin + DPR
    screens2 = [ScreenInfo("G34WQC A", Rect(-3440, 839, 2752, 1152), 0, 1.25),
                ScreenInfo("LEN P32p-20", Rect(0, 0, 2560, 1440), 1, 1.5)]
    mons2, method2 = match_screens(raw, screens2)
    assert method2 == "geometry"
    by_dev = {m.device: m for m in mons2}
    assert by_dev[r"\\.\DISPLAY2"].logical == Rect(-3440, 839, 2752, 1152)
    assert by_dev[r"\\.\DISPLAY1"].logical == Rect(0, 0, 2560, 1440)
    # 175%: Qt rounds the logical size; the derived physical rect is within tolerance
    raw3 = [RawMonitor(r"\\.\DISPLAY1", Rect(0, 0, 3840, 2160), True)]
    mons3, method3 = match_screens(raw3, [ScreenInfo("X", Rect(0, 0, 2194, 1234), 0, 1.75)])
    assert method3 == "geometry" and mons3[0].device == r"\\.\DISPLAY1"
    # nothing matches -> positional order as a last resort
    screens4 = [ScreenInfo("A", Rect(0, 0, 2560, 1440), 0, 1.0),
                ScreenInfo("B", Rect(-2752, 671, 2752, 1152), 1, 1.0)]
    mons4, method4 = match_screens(raw, screens4)
    assert method4 == "order"
    by_dev4 = {m.device: m for m in mons4}
    assert by_dev4[r"\\.\DISPLAY2"].logical == Rect(-2752, 671, 2752, 1152)
    assert by_dev4[r"\\.\DISPLAY1"].logical == Rect(0, 0, 2560, 1440)
