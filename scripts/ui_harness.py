"""End-to-end UI harness: drives the real FramerApp through the whole flow and takes screenshots.

Run with the project's pythonw (no console) and keep hands off the keyboard and mouse for ~20 s:
    .venv/Scripts/pythonw.exe scripts/ui_harness.py <workdir>
Set FRAMER_NO_CAPTURE_EXCLUSION=1 first if the screenshots should show the border, bar and toast.
Writes <workdir>/report.txt, <workdir>/out/ (captures) and <workdir>/*.webp (screenshots).
The frame is drawn on the primary monitor at (+600, +400) with size 800x600 physical px.
"""
import ctypes
import json
import os
import sys
import time
import traceback
from pathlib import Path

WORK = Path(sys.argv[1])
WORK.mkdir(parents=True, exist_ok=True)
OUT = WORK / "out"
OUT.mkdir(exist_ok=True)
REPORT = []


def log(msg):
    REPORT.append(f"{time.strftime('%H:%M:%S')} {msg}")
    (WORK / "report.txt").write_text("\n".join(REPORT) + "\n", encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from framer import win32  # noqa: E402

win32.set_process_dpi_awareness()
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
from PySide6.QtWidgets import QApplication  # noqa: E402

import mss  # noqa: E402
from PIL import Image  # noqa: E402

from framer import theme  # noqa: E402
from framer.__main__ import setup_logging  # noqa: E402
from framer.app import FramerApp  # noqa: E402
from framer.geometry import Rect  # noqa: E402
from framer.settings import Settings  # noqa: E402

setup_logging()
app = QApplication(sys.argv[:1])
app.setQuitOnLastWindowClosed(False)
app.setStyleSheet(theme.STYLESHEET)

settings = Settings(WORK / "settings.json").load()
settings.set("output_folder", str(OUT))
settings.set("prefix", "Test")
framer = FramerApp(app, settings)

SCT = mss.MSS()


def shot(name, rect, scale=1.0):
    try:
        s = SCT.grab({"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]})
        img = Image.frombytes("RGB", (s.width, s.height), s.bgra, "raw", "BGRX")
        if scale != 1.0:
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
        img.thumbnail((1024, 1024))
        img.save(WORK / f"{name}.webp", quality=75)
        log(f"shot {name} {rect} -> {img.size}")
    except Exception as exc:
        log(f"shot {name} FAILED {exc}")


def press(vk):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


VK_F8, VK_F9 = 0x77, 0x78
PRIM = framer.table.primary()
PRIMARY_DEVICE = PRIM.device
FRAME = Rect(PRIM.phys.left + 600, PRIM.phys.top + 400, 800, 600)
VIEW = (PRIM.phys.left + 400, PRIM.phys.top + 200, 1600, 1000)  # screenshot crop around the frame
VIEW_TALL = (PRIM.phys.left + 400, PRIM.phys.top + 200, 1400, 1100)
SETUP_VIEW = (PRIM.phys.left + PRIM.phys.width // 2 - 720, PRIM.phys.top + PRIM.phys.height // 2 - 580, 1440, 1160)
steps = []


def at(ms, fn, name):
    steps.append((ms, fn, name))


def run_step(fn, name):
    try:
        log(f"step {name}")
        fn()
    except Exception:
        log(f"step {name} EXC {traceback.format_exc()}")


def files():
    return sorted(p.name for p in OUT.iterdir())


at(0, framer.start, "start")
at(1200, lambda: shot("01_setup", SETUP_VIEW, 0.6), "shot setup")
at(1500, framer.start_framing_from_setup, "start framing")
at(3000, lambda: log(f"selector open={framer.selector.is_open} overlays={len(framer.selector.overlays)} state={framer.state}"), "selector state")
def shot_all():
    v = SCT.monitors[0]  # the whole virtual desktop
    shot("02_selector_all", (v["left"], v["top"], v["width"], v["height"]), min(1.0, 1024 / v["width"]))


at(3100, shot_all, "shot all monitors")


def do_drag():
    ov = next(o for o in framer.selector.overlays if o.mon.device == PRIMARY_DEVICE)
    framer.selector.on_press(ov, (FRAME.left, FRAME.top))
    framer.selector.on_move(ov, (FRAME.right, FRAME.bottom), True)
    framer.selector.on_release(ov, (FRAME.right, FRAME.bottom))
    ov.hover_phys = (FRAME.right + 40, FRAME.bottom + 40)
    ov.update()
    log(f"sel={framer.selector.sel} mon={framer.selector.sel_mon.device if framer.selector.sel_mon else None}")


at(3300, do_drag, "drag")
at(3800, lambda: shot("03_selection", VIEW_TALL, 0.7), "shot selection")
at(4000, framer.selector.confirm, "confirm")
at(4800, lambda: log(f"state={framer.state} frame={framer.frame} bar={framer.bar.phys_rect} border_visible={framer.border.visible}"), "framing state")
def check_windows():
    from ctypes import wintypes
    from framer.geometry import border_strips
    u = ctypes.windll.user32
    def wr(hwnd):
        r = wintypes.RECT(); u.GetWindowRect(hwnd, ctypes.byref(r)); return (r.left, r.top, r.right - r.left, r.bottom - r.top)
    exp = border_strips(FRAME, framer.frame_mon.phys, 2, 3)
    for name, strip, e in zip(("top", "bottom", "left", "right"), framer.border.strips, exp):
        hwnd = int(strip.winId())
        log(f"strip {name}: visible={bool(u.IsWindowVisible(hwnd))} rect={wr(hwnd)} expected={e.as_tuple()} match={wr(hwnd) == e.as_tuple()}")
    bh = int(framer.bar.winId())
    log(f"bar: visible={bool(u.IsWindowVisible(bh))} rect={wr(bh)} expected={framer.bar.phys_rect.as_tuple()} intersects_frame={framer.bar.phys_rect.intersects(FRAME)}")
    ex = u.GetWindowLongPtrW(int(framer.border.strips[0].winId()), -20)
    log(f"strip exstyle={ex:#x} layered={bool(ex & 0x80000)} transparent={bool(ex & 0x20)} toolwindow={bool(ex & 0x80)} noactivate={bool(ex & 0x8000000)}")
    bex = u.GetWindowLongPtrW(bh, -20)
    log(f"bar exstyle={bex:#x} toolwindow={bool(bex & 0x80)} noactivate={bool(bex & 0x8000000)}")
    log(f"foreground title now: {win32.get_foreground_title()!r}")


at(4850, check_windows, "check windows")
at(4900, lambda: shot("04_framing", VIEW, 0.7), "shot framing")
at(5100, lambda: press(VK_F9), "F9 #1")
at(6300, lambda: log(f"files after F9#1: {files()} next={framer.next_number} saved={framer.saved_count}"), "check 1")
at(6400, lambda: shot("05_after_save", VIEW, 0.7), "shot after save")
at(6600, lambda: press(VK_F9), "F9 #2 (dup)")
at(7200, lambda: log(f"files after dup: {files()} dup_until={framer._dup_override_until:.1f} now={time.monotonic():.1f}"), "check dup")
at(7300, lambda: shot("06_dup_toast", VIEW, 0.7), "shot dup toast")
at(7500, lambda: press(VK_F9), "F9 #3 (override)")
at(8600, lambda: log(f"files after override: {files()} next={framer.next_number}"), "check override")
at(8700, framer.undo, "undo")
at(9500, lambda: log(f"files after undo: {files()} next={framer.next_number} saved={framer.saved_count} undo_enabled={framer.bar.btn_undo.isEnabled()}"), "check undo")
at(9700, lambda: press(VK_F8), "F8 reframe")
at(11000, lambda: log(f"reframe: selector open={framer.selector.is_open} sel={framer.selector.sel} state={framer.state}"), "check reframe")
at(11100, lambda: shot("07_reframe", VIEW_TALL, 0.7), "shot reframe")
at(11300, framer.selector.cancel, "cancel reframe (Esc)")
at(12000, lambda: log(f"after cancel: state={framer.state} frame={framer.frame}"), "check cancel")


def pdf():
    framer.make_pdf()
    QTimer.singleShot(400, framer.pdf_dialog._create)


at(12200, pdf, "make pdf")
at(14500, lambda: log(f"pdf files: {files()} status={framer.pdf_dialog.lbl_status.text()}"), "check pdf")
at(14600, lambda: shot("08_pdf_dialog", SETUP_VIEW, 0.6), "shot pdf dialog")


def check_image():
    pngs = sorted(OUT.glob("Test_*.png"))
    for p in pngs:
        with Image.open(p) as im:
            log(f"{p.name}: {im.size} dpi={im.info.get('dpi')}")
    log("log.csv:\n" + (OUT / "framer_log.csv").read_text("utf-8-sig"))
    log("settings: " + json.dumps(settings.data)[:600])


at(14800, check_image, "check images")
at(15000, framer.stop_framing, "stop framing")
at(15300, lambda: log(f"stopped: state={framer.state} hk_capture={framer.hotkeys.is_registered(2)} hk_set={framer.hotkeys.is_registered(1)}"), "check stopped")
at(15400, lambda: log(f"can_use_last_frame={framer.can_use_last_frame()} btn_visible={framer.setup.btn_last.isVisibleTo(framer.setup)}"), "check use-last-frame availability")
at(15500, framer.use_last_frame, "use last frame")
at(16300, lambda: log(f"after use_last_frame: state={framer.state} frame={framer.frame} bar={framer.bar.phys_rect}"), "check use last frame")
at(16400, lambda: shot("09_use_last_frame", VIEW, 0.7), "shot use last frame")
at(16600, framer.quit, "quit")

for ms, fn, name in steps:
    QTimer.singleShot(ms, lambda fn=fn, name=name: run_step(fn, name))

rc = app.exec()
log(f"exit {rc}")
