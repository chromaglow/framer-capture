"""`Framer.exe --self-test`: headless-ish checks, results in %APPDATA%/Framer/selftest.txt, exit 0 on success."""
from __future__ import annotations

import shutil
import sys
import tempfile
import traceback
from pathlib import Path

from PIL import Image


def run(ci_mode: bool = False) -> int:
    from . import win32
    from .settings import app_data_dir

    lines: list[str] = []
    failures = 0

    def ok(name: str, detail: str = "") -> None:
        lines.append(f"PASS  {name}" + (f" — {detail}" if detail else ""))

    def fail(name: str, detail: str) -> None:
        nonlocal failures
        failures += 1
        lines.append(f"FAIL  {name} — {detail}")

    tmp = Path(tempfile.mkdtemp(prefix="framer_selftest_"))
    try:
        # 1. DPI awareness
        if win32.is_per_monitor_v2():
            ok("1 DPI awareness", "PerMonitorV2")
        else:
            fail("1 DPI awareness", "not Per-Monitor V2")

        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv[:1])

        # 2. Monitors
        try:
            from .monitors import MonitorTable

            table = MonitorTable()
            if len(table.monitors) >= 1 and table.all_matched():
                ok("2 Monitor enumeration", f"{len(table.monitors)} monitor(s), all QScreens matched" + (" (positional fallback)" if table.used_fallback else ""))
            else:
                fail("2 Monitor enumeration", f"{len(table.monitors)} monitors, matched={table.all_matched()}")
        except Exception as exc:
            fail("2 Monitor enumeration", repr(exc))
            table = None

        # 3. Capture 200x200 at primary top-left
        if ci_mode:
            lines.append("SKIP  3 Capture (CI mode)")
        else:
            try:
                from .capture import CaptureEngine, save_image_atomic
                from .geometry import Rect

                prim = table.primary() if table else None
                left, top = (prim.phys.left, prim.phys.top) if prim else (0, 0)
                eng = CaptureEngine()
                img = eng.grab(Rect(left, top, 200, 200))
                out = tmp / "capture.png"
                save_image_atomic(img, out, "png")
                with Image.open(out) as im:
                    size = im.size
                eng.close()
                if size == (200, 200):
                    ok("3 Capture", "200x200 PNG")
                else:
                    fail("3 Capture", f"size {size}")
            except Exception as exc:
                fail("3 Capture", repr(exc))

        # 4. Naming
        try:
            from .naming import next_free_name

            Image.new("RGB", (8, 8)).save(tmp / "Test_0001.png")
            name, n, skipped = next_free_name(tmp, "Test", 1, 4, "png")
            if name == "Test_0002.png" and n == 2:
                ok("4 Naming", name)
            else:
                fail("4 Naming", f"got {name}")
        except Exception as exc:
            fail("4 Naming", repr(exc))

        # 5. PDF
        try:
            from .pdf import build_pdf, count_pdf_pages

            a = tmp / "P_0001.png"
            b = tmp / "P_0002.png"
            Image.new("RGB", (300, 200), (200, 30, 30)).save(a, dpi=(300, 300))
            Image.new("RGBA", (300, 200), (30, 200, 30, 128)).save(b, dpi=(300, 300))
            out = tmp / "test.pdf"
            build_pdf([str(a), str(b)], out)
            pages = count_pdf_pages(out)
            if pages == 2:
                ok("5 PDF", "2 pages")
            else:
                fail("5 PDF", f"{pages} pages")
        except Exception as exc:
            fail("5 PDF", repr(exc))

        # 6. Hotkey
        try:
            from .hotkeys import HK_SELFTEST, HotkeyManager

            hk = HotkeyManager()
            spec = {"modifiers": ["Ctrl", "Alt", "Shift"], "key": "F12"}
            if hk.register(HK_SELFTEST, spec, lambda: None):
                hk.unregister(HK_SELFTEST)
                ok("6 Hotkey", "Ctrl+Alt+Shift+F12 registered and unregistered")
            else:
                fail("6 Hotkey", "RegisterHotKey failed")
        except Exception as exc:
            fail("6 Hotkey", repr(exc))
    except Exception:
        fail("self-test", traceback.format_exc())
    finally:
        # 7. Cleanup
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            if not tmp.exists():
                ok("7 Cleanup", str(tmp))
            else:
                fail("7 Cleanup", f"{tmp} still exists")
        except Exception as exc:
            fail("7 Cleanup", repr(exc))

    summary = f"{'OK' if failures == 0 else 'FAILED'} — {len(lines) - failures} passed, {failures} failed"
    lines.append(summary)
    text = "\n".join(lines) + "\n"
    try:
        out_dir = app_data_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "selftest.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except Exception:
        pass
    return 0 if failures == 0 else 1
