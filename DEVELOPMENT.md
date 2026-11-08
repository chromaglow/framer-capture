# Framer — developer guide

Everything you need to pick the project up cold. The owner-facing manual is `README.md`; the original build spec is `FRAMER_SPEC.md` (still the best description of intended behavior); judgment calls made during the build are in `DECISIONS.md`; the latest status is in `docs/NOW.md`.

## 1. Toolchain

| Thing | Choice | Notes |
|---|---|---|
| Python | 3.12 (pinned in `pyproject.toml`) | `uv python install 3.12` |
| Env / deps | `uv` | `uv sync` creates `.venv`. On Windows, winget installs uv to `%LOCALAPPDATA%\Microsoft\WinGet\Links`, which Git Bash does not have on `PATH` by default. |
| UI | PySide6 (Qt 6.12 at the time of writing) | |
| Capture | `mss` | Physical pixels, BGRA. |
| Images | Pillow, numpy | |
| PDF | `img2pdf` (imports `pikepdf`) | Lossless embedding. |
| Delete | `send2trash` | Undo goes to the Recycle Bin. |
| Win32 | `ctypes` only | `framer/win32.py`. No pywin32. |
| Packaging | PyInstaller one-file, windowed | `framer.spec`, `framer.manifest`, `version_info.txt`. |

Commands:

```powershell
uv sync                                  # environment
uv run pytest                            # 67 unit tests, < 2 s
uv run python -m framer                  # run from source
uv run python -m framer --self-test      # the 7-step self-check (writes %APPDATA%\Framer\selftest.txt)
scripts\build.ps1                        # full build: assets, tests, PyInstaller, copy to release\, exe self-test
```

## 2. Architecture

The app is a small state machine around a handful of top-level windows. All coordinate math is in physical pixels; Qt's logical coordinates are converted at the edges.

```
__main__.py        DPI awareness -> logging + crash hook -> single instance -> QApplication -> FramerApp
framer_launcher.py PyInstaller entry (imports framer.__main__.main; see gotcha 5.1)
app.py             FramerApp: states SETUP / SELECTING / FRAMING / STOPPED; wires every component
settings.py        %APPDATA%\Framer\settings.json, validated + atomically written
geometry.py        PURE math: Rect, Monitor, logical<->physical, border strips, bar placement, screen matching
monitors.py        Win32 EnumDisplayMonitors + QScreen matching -> MonitorTable
win32.py           ctypes: DPI, monitors, ex-styles, display affinity, SetWindowPos, hotkeys, foreground, mutex, VK table
hotkeys.py         RegisterHotKey on a hidden window + QAbstractNativeEventFilter for WM_HOTKEY
selector.py        Frame Selector: one overlay per monitor, frozen snapshot, drag/handles/nudge, loupe
border.py          Four click-through, capture-excluded strips 2 px outside the frame
bar.py             Floating bar (thumbnail, counters, buttons, drag + snap-outside)
toast.py           Toast pill under the bar
tray.py            QSystemTrayIcon + menu
setup_window.py    The Setup window (fields, hotkey capture, validation)
capture.py         mss grab (main thread), duplicate guard, single-worker save queue (QThreadPool, max 1)
naming.py          Prefix sanitizing, folder scan, next-free-name (never overwrite)
capture_log.py     framer_log.csv (UTF-8 BOM)
pdf.py             collect/sort/flatten/build PDF + the Make PDF dialog
sounds.py          Synthesized 30 ms click, played with winsound
resources.py       Asset paths (sys._MEIPASS when frozen) and the app icon
theme.py           Palette as named roles + the one QSS stylesheet
```

### State flow

1. **Launch** → `FramerApp.start()`: tray shown, F8 registered, Setup window shown.
2. **Start Framing / F8 / Reframe** → `open_selector()`: hides border + bar + toast, remembers the foreground HWND, waits 220 ms (compositor), then `FrameSelector.open()` grabs one `mss` snapshot per monitor and shows the overlays.
3. **Enter / double-click** → `confirmed(rect, mon)` → `enter_framing()`: saves `last_frame`, shows border + bar, registers F9, gives focus back to the previous foreground window.
4. **F9** → `capture()`: debounce 150 ms → `engine.grab()` on the main thread → black check → duplicate guard (64×64 gray MAD < 1.0, 3 s override window) → `SaveJob` to the single worker → border flash + click. The worker scans the folder, picks the next free name, writes `.part` then `os.replace`, appends the CSV row, emits `SaveResult` (with a thumbnail QImage) back to the main thread.
5. **Undo** → `send2trash`, undo CSV row, counter rollback only if no higher number exists, thumbnail + duplicate fingerprint revert.
6. **Stop** → unregister F9, hide border/bar; F8 stays live. **Quit** → unregister all, wait for the save queue, exit.

### Coordinate model (read before touching geometry)

- `Monitor` = Win32 device name + physical rect (`rcMonitor`) + Qt logical rect (`QScreen.geometry()`).
- `logical_to_physical` / `physical_to_logical` are per-monitor linear maps using `phys.width / logical.width`. Round-trips are exact; `tests/test_geometry.py` proves it for 100/125/150/175/200 % and mixed layouts, including negative origins.
- Windows that must line up with the capture rectangle (strips, bar, toast, overlays) are positioned twice: `setGeometry` in logical pixels so Qt is happy, then `SetWindowPos` in physical pixels so they are exact. The process is Per-Monitor-V2 aware, so `SetWindowPos` takes physical pixels.
- `border_strips()` yields the four strip rects (gap 2, thickness 3) clipped to the monitor. `place_bar()` tries right, left, below, above, then the monitor's top-right corner. `snap_bar_outside()` handles drags that end on the frame.

## 3. Testing

- **Unit tests** (`tests/`): geometry, naming, duplicate guard, CSV log, PDF, settings. Run anywhere.
- **Self-test** (`framer/selftest.py`, `--self-test`): DPI context, monitor matching, a real 200×200 grab, naming, PDF, hotkey. `--ci` skips the grab (GitHub runners have no usable display).
- **UI harness** (`scripts/ui_harness.py`): drives the *real* app from source: opens the selector, draws a frame on the primary monitor, confirms, presses F9/F8 through `keybd_event` (so the real `RegisterHotKey` path is exercised), checks files, CSV rows, duplicate guard, undo, reframe, PDF, remembered frame, and checks strip/bar positions with `GetWindowRect`. Writes `report.txt` and screenshots. Run it with `pythonw` (no console) and keep your hands off the mouse for ~20 s:
  ```powershell
  $env:FRAMER_NO_CAPTURE_EXCLUSION = "1"      # so the screenshots show Framer's own windows
  .venv\Scripts\pythonw.exe scripts\ui_harness.py C:\temp\framer-harness
  ```
- **Exe smoke test** (`scripts/exe_smoke_test.py`): PE subsystem (GUI), `--self-test`, launch, no console window, second-instance behavior, quit via WM_CLOSE.

## 4. Release process

1. Bump `__version__` in `framer/__init__.py`, `version` in `pyproject.toml`, and `version_info.txt`.
2. `scripts\build.ps1` → `release\Framer.exe`; run `scripts\exe_smoke_test.py`.
3. Commit, `git tag -a vX.Y.Z`, push with tags. `.github/workflows/build.yml` builds on `windows-latest`, runs tests + the CI-subset self-test, and attaches `Framer.exe` to a GitHub Release for the tag.
4. The exe is **not code-signed**; SmartScreen shows "More info → Run anyway" once per machine. Documented in the README.

## 5. Gotchas (each one cost real time)

1. **PyInstaller entry file.** Pointing the spec at `framer/__main__.py` produces "attempted relative import with no known parent package" at runtime, because PyInstaller runs the entry as a top-level script. Use `framer_launcher.py`.
2. **`QScreen.name()` is not `\\.\DISPLAYn`** on Qt 6.12; it is the monitor's friendly name (`LEN P32p-20`). `match_screens()` matches by name, then by geometry (native origin + logical size × DPR), then by position order. The method used is logged.
3. **`WDA_EXCLUDEFROMCAPTURE` also hides windows from GDI/`mss` screenshots.** Great for captures, confusing for debugging: your screenshots will not show the border, bar or toast. Set `FRAMER_NO_CAPTURE_EXCLUSION=1` to see them.
4. **Snapshots can contain stale windows.** Hiding a Qt window and grabbing the screen immediately still shows it; the compositor needs ~2 frames. The selector waits 220 ms after hiding Framer's windows.
5. **`version_info.txt` needs lists.** `StringFileInfo([StringTable(...)])` and `VarFileInfo([VarStruct(...)])`; without the brackets PyInstaller fails with "'StringTable' object is not iterable".
6. **Foreground stealing.** A background process cannot `SetForegroundWindow`. The second instance calls `AllowSetForegroundWindow(ASFW_ANY)` and the first uses `AttachThreadInput` to the current foreground thread (`win32.force_foreground`). Some foreground apps still win; Framer then flashes its taskbar button.
7. **`%APPDATA%\Framer` is shared** with an unrelated Electron app that is also called Framer (the design tool). Our files are only `settings.json`, `framer.log`, `selftest.txt`. Do not delete the folder.
8. **PyInstaller one-file shows two processes** (bootloader + child). Process counts in tests must allow for it.
9. **Qt rounds logical geometry.** At 150 % a window positioned only through Qt can be off by one physical pixel. Always follow up with `win32.set_window_pos_physical`.
10. **The hidden hotkey window** must be created on the main thread and must exist for the life of the app; `RegisterHotKey` is tied to its HWND. `MOD_NOREPEAT` is always set so holding F9 does not fire repeatedly.
11. **Duplicate guard memory.** `last_gray` is cleared on reframe and prefix/folder change, and reverted on undo via `_gray_by_path`. If saves skip numbers (file existed), the pending fingerprint is matched by order.
12. **Bash on Windows.** `uv` is at `%LOCALAPPDATA%\Microsoft\WinGet\Links`; add it to `PATH` in scripts. Killing processes by matching command lines can match your own shell; filter by image name.

## 6. Conventions

- Colors only through `theme.py` role names. Frame border geometry constants live there too.
- No network calls, no telemetry, no auto-update, no admin. Keep it that way.
- Every judgment call that is not obvious from the code goes into `DECISIONS.md` as one line.
- Keep `geometry.py` and `naming.py` free of Qt/Win32 imports so they stay unit-testable.

## 7. Ideas for v2 (from spec §17, not started)

Auto page-turn / sending keys, auto-run mode, scrolling capture and stitching, OCR, window-snap framing, installer, code signing.
