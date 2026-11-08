"""Smoke-test release/Framer.exe: GUI subsystem, --self-test, launch (no console), single instance, quit.

    .venv/Scripts/python.exe scripts/exe_smoke_test.py <workdir>
Writes <workdir>/exe_report.txt and exe_setup.webp. PyInstaller one-file runs as two processes
(bootloader + child), so two Framer.exe PIDs per instance is normal. The "foreground is setup window"
check depends on which app is in front when you run it (Windows focus rules); a False there with the
second instance exiting 0 is not a Framer failure.
"""
import ctypes
import os
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

EXE = Path(__file__).resolve().parent.parent / "release" / "Framer.exe"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
u = ctypes.windll.user32
u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
report = []


def log(m):
    print(m)
    report.append(m)
    (OUT / "exe_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")


# 1. PE subsystem (2 = Windows GUI, 3 = console)
data = EXE.read_bytes()
pe = struct.unpack_from("<I", data, 0x3C)[0]
subsystem = struct.unpack_from("<H", data, pe + 4 + 20 + 68)[0]
log(f"exe size: {EXE.stat().st_size / 1e6:.1f} MB; PE subsystem={subsystem} ({'GUI' if subsystem == 2 else 'CONSOLE'})")

# 2. --self-test
t0 = time.time()
rc = subprocess.run([str(EXE), "--self-test"], timeout=120).returncode
log(f"--self-test rc={rc} in {time.time() - t0:.1f}s")
log((Path(os.environ["APPDATA"]) / "Framer" / "selftest.txt").read_text("utf-8"))


def framer_pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Framer.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return [int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"Framer.exe"')]


def find_setup():
    return u.FindWindowW(None, "Framer 1.0.0")


# 3. launch
p1 = subprocess.Popen([str(EXE)])
hwnd = 0
for _ in range(60):
    time.sleep(0.25)
    hwnd = find_setup()
    if hwnd:
        break
log(f"first instance pid={p1.pid} setup hwnd={hwnd} visible={bool(u.IsWindowVisible(hwnd))} after launch; framer pids={framer_pids()}")

# console windows owned by this pid?
consoles = []
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def cb(h, lp):
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value == p1.pid and u.IsWindowVisible(h):
        buf = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, buf, 64)
        tb = ctypes.create_unicode_buffer(128)
        u.GetWindowTextW(h, tb, 128)
        consoles.append((buf.value, tb.value))
    return True


u.EnumWindows(EnumProc(cb), 0)
log(f"visible top-level windows of pid {p1.pid}: {consoles}")
log(f"console window present: {any(c[0] == 'ConsoleWindowClass' for c in consoles)}")

# screenshot of the setup window
r = wintypes.RECT()
u.GetWindowRect(hwnd, ctypes.byref(r))
log(f"setup window rect (physical): {(r.left, r.top, r.right - r.left, r.bottom - r.top)}")
try:
    import mss
    from PIL import Image

    with mss.MSS() as sct:
        s = sct.grab({"left": r.left - 20, "top": r.top - 20, "width": r.right - r.left + 40, "height": r.bottom - r.top + 40})
        img = Image.frombytes("RGB", (s.width, s.height), s.bgra, "raw", "BGRX")
        img.thumbnail((1024, 1024))
        img.save(OUT / "exe_setup.webp", quality=75)
except Exception as exc:
    log(f"screenshot failed: {exc}")

# 4. second instance -> should exit quickly, first comes to front
u.SetForegroundWindow(u.GetDesktopWindow())
time.sleep(0.5)
t0 = time.time()
p2 = subprocess.Popen([str(EXE)])
try:
    rc2 = p2.wait(timeout=15)
except subprocess.TimeoutExpired:
    rc2 = "TIMEOUT"
    p2.kill()
time.sleep(1.0)
fg = u.GetForegroundWindow()
log(f"second instance rc={rc2} in {time.time() - t0:.1f}s; framer pids now={framer_pids()}; foreground is setup window: {fg == hwnd} (fg={fg}, setup={find_setup()})")

# 5. quit via the Setup window's close button (X while not framing = quit)
u.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
try:
    rc1 = p1.wait(timeout=15)
except subprocess.TimeoutExpired:
    rc1 = "TIMEOUT"
    p1.kill()
log(f"first instance exit rc={rc1}; framer pids after quit={framer_pids()}")
log("DONE")
