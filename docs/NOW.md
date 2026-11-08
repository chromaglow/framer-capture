# Framer — where things stand

_Last refreshed: 2026-11-08 (first build session)._

## Status

- ✅ MVP per `FRAMER_SPEC.md` implemented: Setup window, frame selector (per-monitor overlays, loupe, handles, nudge), border strips, floating bar, toasts, tray, global hotkeys (F8/F9), capture pipeline (mss → ordered save queue, duplicate guard, CSV log, undo to Recycle Bin), Make PDF, settings, crash handler, single instance.
- ✅ 67 unit tests pass (`uv run pytest`).
- ✅ `release\Framer.exe` built with PyInstaller (one-file, windowed, PerMonitorV2 manifest, icon, version info); `Framer.exe --self-test` exits 0.
- ✅ End-to-end harness (scratch script, not in repo) drove the real app on the 3-monitor mixed-DPI setup: border strips land pixel-exact, captures are exactly the frame size, duplicate guard / override / undo / reframe / PDF all behave.
- ✅ Private GitHub repo `chromaglow/framer`, workflow `.github/workflows/build.yml` builds on tag `v*`.

## How to build again

Run `scripts\build.ps1` in PowerShell (installs uv if needed, syncs, makes assets, tests, PyInstaller, copies to `release\`, runs the exe self-test).

## Things worth knowing

- Qt 6.12 reports friendly monitor names from `QScreen.name()`, so Win32 monitors are matched to Qt screens by geometry (see `framer/geometry.py::match_screens`).
- `WDA_EXCLUDEFROMCAPTURE` hides Framer's own windows even from `mss`/BitBlt screenshots. Set `FRAMER_NO_CAPTURE_EXCLUSION=1` when you need screenshots that show the border/bar.
- `%APPDATA%\Framer` is shared with an unrelated Electron app named Framer; our files are `settings.json`, `framer.log`, `selftest.txt`.

## Open / next

- v2 candidates are listed in spec §17 (auto page-turn, scrolling capture, OCR, installer, code signing).
- A manual pass by the owner over spec §14.2 on real documents is the remaining human check (everything automatable was automated).
