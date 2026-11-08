# Framer — instructions for Claude Code

This folder is the repo for **Framer**, a Windows repeat-frame screen capture app (frame once, press F9 per page). The MVP shipped as v1.0.0 on 2026-11-08 and works on the owner's machine.

## Start here
1. `docs/NOW.md` — current status and open items.
2. `DEVELOPMENT.md` — architecture, coordinate model, tests, release process, gotchas. Read §5 before touching windows, DPI or packaging.
3. `FRAMER_SPEC.md` — the original specification; still the source of truth for intended behavior.
4. `DECISIONS.md` — every judgment call so far; append one line per new one.

## How to work
- Work autonomously; the owner does not use a terminal and should never need one. Anything they run must be a double-click.
- Run `uv run pytest` after changes; run `scripts\ui_harness.py` when you touch the selector, border, bar, toast, hotkeys or capture path; run `scripts\build.ps1` + `scripts\exe_smoke_test.py` before tagging a release.
- Commit per logical step; tag `vX.Y.Z` to release (CI builds and attaches the exe).
- Colors come from `framer/theme.py` roles only. No network, telemetry, auto-update or admin, ever.
- `uv` lives at `%LOCALAPPDATA%\Microsoft\WinGet\Links` (not on Git Bash's PATH).

## Repos
- Private: https://github.com/chromaglow/framer (origin)
- Public, MIT: https://github.com/chromaglow/framer-capture (remote `public`)
Push both.
