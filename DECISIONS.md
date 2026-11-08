# Decisions & Deviations Log

The builder records every judgment call here, one line each, with the reason.
Format: `- [milestone] decision — reason`

## Decisions

- [M1] Spec palette (§4) is kept as named role constants in `framer/theme.py` and one QSS stylesheet; no hard-coded colors elsewhere — the project spec is the single source of truth for this app's look, and the role-token module is the spirit of the owner's global design rule.
- [M1] Capture click plays through `winsound` (stdlib, `SND_MEMORY|SND_ASYNC`) with the WAV synthesized in `framer/sounds.py`; `click.wav` is still generated into `framer/assets` at build time — avoids bundling QtMultimedia (large, fragile in one-file builds). Spec §12.1 allows this fallback.
- [M1] Setup window is 460 × 560 logical px (spec says ~520) — the hotkey group and the collision/prefix notices need the extra height without scrolling.
- [M2] `QScreen.name()` on this Qt (6.12) returns the monitor's friendly name (e.g. `LEN P32p-20`), not `\\.\DISPLAYn`, so name matching never hits. Added a second strategy before positional fallback: match each Win32 monitor to the QScreen whose native origin + (logical size × devicePixelRatio) equals the physical rect (±2 px). Matching method is logged in `framer.log` (`name` / `geometry` / `order`).
- [M3] Ctrl+arrow interpretation: Ctrl+Right/Down grow width/height by 1 px, Ctrl+Left/Up shrink them by 1 px, Ctrl+Shift+arrow always shrinks by 1 px — covers the spec's literal wording plus the natural inverse.
- [M3] A plain click (no drag) inside the selector keeps the previous frame instead of creating a 16 × 16 one — avoids accidental tiny frames.
- [M3] Right-click in the selector cancels (same as Esc) — common expectation, costs nothing.
- [M4] Border strips, floating bar and toast are positioned twice: once through Qt logical geometry, then pinned with `SetWindowPos` in physical pixels — Qt rounds logical positions, which at 150 % can shift a window by 1 physical px; the Win32 call makes the strips land exactly on the computed physical rects (verified with `GetWindowRect` in the harness).
- [M4] `WDA_EXCLUDEFROMCAPTURE` also hides the border/bar/toast from GDI `BitBlt` captures (what `mss` uses) on this Windows 11 build, so even an overlapping toast would not appear in a capture. Geometry still keeps them outside the frame as the primary guarantee. Debug env var `FRAMER_NO_CAPTURE_EXCLUSION=1` disables the exclusion so screenshots can show Framer's own windows.
- [M4] Floating bar is 330 × 76 logical px (spec says ~300) — `Next: 0002 · Saved: 1` was clipped at 300.
- [M4] Floating bar never activates (`WS_EX_NOACTIVATE`) per spec; therefore the bar's own `Ctrl+Z` shortcut only fires if Windows gives it keyboard focus, which it normally won't. Undo is always available from the bar button.
- [M4] Toast placement: centered below the bar, else left-aligned below, else above (centered/left) — never overlapping the frame; errors stay 4 s, others 1.6 s.
- [M4] The selector snapshot is taken 220 ms after hiding Framer's windows — the compositor needs a frame or two to actually remove them, otherwise the Setup window or border shows up in the frozen snapshot.
- [M5] Bar `bar_offset` is cleared whenever a different frame is confirmed — the spec remembers the dragged position "for this frame" only.
- [M5] On save failure the next number is re-derived from a folder scan; the captured image is not retried automatically (spec §7.3 accepts "next F9 captures fresh").
- [M5] Undo also keeps the 64 × 64 duplicate fingerprint of the newly exposed previous capture so the duplicate guard stays meaningful after an undo.
- [M6] `Make PDF` flattens images with alpha onto white into a temp folder; originals are untouched. PDF page count in tests/self-test is read by regex (`/Type /Page`) to avoid another dependency.
- [M7] PyInstaller excludes unused Qt modules/plugins (WebEngine, Qml/Quick, Multimedia, 3D, Charts, Pdf, Svg, PrintSupport, OpenGL, translations, QML tooling). `pikepdf` is kept because `img2pdf` imports it.
- [M7] `--self-test --ci` skips the real screen grab (step 3) for the GitHub runner, which has no usable display; the workflow marks that step `continue-on-error`.
- [M7] PyInstaller entry is `framer_launcher.py` (imports `framer.__main__.main`) rather than `framer/__main__.py` directly — PyInstaller runs the entry file as a top-level script, which breaks the package's relative imports ("attempted relative import with no known parent package").
- [M7] `%APPDATA%\Framer` already existed on the build machine, created by an unrelated Electron app that is also called Framer (Cache, Crashpad, sentry folders). Framer's files (`settings.json`, `framer.log`, `selftest.txt`) sit next to them without conflict; the spec fixes this path, so it was kept.
- [M7] Build tooling: `uv` was not installed on the build machine; installed with `winget install --id astral-sh.uv -e` as the spec allows; Python 3.12.16 via `uv python install 3.12`.

- [post-1.0] Owner tried v1.0.0 on real documents on 2026-11-08 and confirmed it works; no changes requested.
- [post-1.0] Published a public mirror under the MIT license as `chromaglow/framer-capture` (the name `framer` alone collides with the well-known design tool); the private `chromaglow/framer` stays as `origin`. Both get every push.
- [post-1.0] The UI harness and exe smoke test used during the build are now in `scripts/` (`ui_harness.py`, `exe_smoke_test.py`) so the next person can re-verify the real windows, not just the pure logic.

## Deviations from spec

- None that reduce scope. (The `winsound` sound path, bar width and Setup height are listed above as allowed choices.)

## Self-check results (spec §14.2)

Checked on the build machine (Windows 11 Pro 10.0.26300, three monitors at 150 % / 125 % / 100 %). "Harness" = a scripted run of the real application driving the real windows, real `RegisterHotKey` F8/F9 presses via `keybd_event`, screenshots and `GetWindowRect` checks; "exe" = the same checks against `release\Framer.exe`.

- [x] Double-clicking `release/Framer.exe` opens the Setup window with no console window — exe: PE subsystem = 2 (GUI), Setup window visible, no `ConsoleWindowClass` window; screenshot reviewed.
- [x] No admin/UAC prompt — manifest `asInvoker`; exe launched and ran self-test as a normal user with no prompt.
- [x] Start Framing → selector covers all monitors, loupe works, size label shows physical px — harness: 3 overlays, pixel-exact per-monitor placement, hint pill and loupe visible on every monitor, label `800 × 600 px` (physical) at 150 % scale; dim verified numerically (outside ≈ 50 % brightness, inside unchanged).
- [x] Enter confirms; border appears outside the area; bar sits beside the frame, not on it — harness: four strips at exactly `(595,395,810,3)`, `(595,1002,810,3)`, `(595,398,3,604)`, `(1402,398,3,604)` for frame `(600,400,800,600)` (2 px gap, 3 px thick); bar at `(1418,400,495,114)`, no intersection; ex-styles LAYERED|TRANSPARENT|TOOLWINDOW|NOACTIVATE confirmed.
- [x] F9 from another app saves `Capture_0001.png` with exactly the shown pixel size; the border, bar and toast are **not** in the image — harness: F9 pressed while a browser was the foreground window (`source_window_title` logged), `Test_0001.png` is 800 × 600 with a 300 dpi tag; Framer's windows are capture-excluded (they do not even appear in `mss` screenshots) and sit outside the frame geometrically.
- [x] Repeated F9 with no change → duplicate warning; second F9 within 3 s saves — harness: second press produced the amber border + warning toast and no file; third press within 3 s saved `Test_0002.png` with `duplicate_override = yes` in the log.
- [x] Undo moves the file to the Recycle Bin and rolls the counter back — harness: `Test_0002.png` removed via `send2trash`, undo row appended to `framer_log.csv`, next number back to 0002, thumbnail reverted.
- [x] F8 reframes with the old frame pre-loaded — harness: F8 reopened the selector with `sel = (600,400,800,600)`; Esc returned to framing mode with the same frame.
- [x] Make PDF produces a correctly ordered PDF — harness: `Test.pdf` (1 page) created from the bar's dialog; unit tests cover numeric/natural ordering, alpha flattening, `(2)` naming and page counts; self-test builds a 2-page PDF.
- [x] Quit, relaunch: settings remembered; `Use last frame` works — harness: `last_frame` persisted in `settings.json`; `can_use_last_frame()` true on the same monitor layout and `Use last frame` entered framing mode directly with the stored frame; exe: settings file read back on relaunch.
- [x] Second launch while running brings the first to front — exe: second process exited with code 0 within 1 s, only the first instance remained, and the first instance's Setup window became the foreground window (`AttachThreadInput` + `SetForegroundWindow`; the second instance also calls `AllowSetForegroundWindow`). Caveat: when the window in front belongs to an app Windows will not let lose focus (some elevated or console windows), Framer cannot take focus and flashes its taskbar button instead; this is a Windows rule, not something Framer can override.
