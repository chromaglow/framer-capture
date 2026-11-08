# Framer — where things stand

_Last refreshed: 2026-11-08, after the owner's hands-on check of v1.0.0._

## Status

- ✅ **v1.0.0 shipped and confirmed working by the owner** on real documents (three-monitor, mixed-DPI machine).
- ✅ MVP per `FRAMER_SPEC.md`: Setup window, frame selector (per-monitor overlays, loupe, handles, nudge), border strips, floating bar, toasts, tray, global hotkeys (F8/F9), capture pipeline (mss → ordered save queue, duplicate guard, CSV log, undo to Recycle Bin), Make PDF, settings, crash handler, single instance.
- ✅ 67 unit tests (`uv run pytest`), 7-step `--self-test`, UI harness and exe smoke test all pass (`scripts/`).
- ✅ `release\Framer.exe` (PyInstaller one-file, windowed, PerMonitorV2 manifest, icon, version info).
- ✅ Private repo `chromaglow/framer` (origin). CI for tag `v1.0.0` green on `windows-latest`; exe attached to the release.
- ✅ Public MIT mirror `chromaglow/framer-capture` (remote `public`); same CI, same release.

## Pick-up checklist

1. Read `DEVELOPMENT.md` (architecture + gotchas), then skim `DECISIONS.md`.
2. `uv sync && uv run pytest`.
3. For UI work: `uv run python -m framer`, then `scripts\ui_harness.py` (see DEVELOPMENT §3).
4. To release: bump version in three places (DEVELOPMENT §4), `scripts\build.ps1`, `scripts\exe_smoke_test.py`, tag, push to both remotes.

## Things worth knowing

- Qt 6.12 reports friendly monitor names from `QScreen.name()`; Win32 monitors are matched to Qt screens by geometry (`framer/geometry.py::match_screens`).
- `WDA_EXCLUDEFROMCAPTURE` hides Framer's own windows even from `mss`/BitBlt screenshots. Set `FRAMER_NO_CAPTURE_EXCLUSION=1` for screenshots that should show the border/bar.
- `%APPDATA%\Framer` is shared with an unrelated Electron app named Framer; ours are `settings.json`, `framer.log`, `selftest.txt`.
- The exe is unsigned; SmartScreen asks once per machine.

## Open / next

- Nothing open for v1. v2 candidates: spec §17 (auto page-turn, scrolling capture/stitching, OCR, window-snap framing, installer, code signing).
