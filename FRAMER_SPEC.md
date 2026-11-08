# FRAMER — Complete Build Specification (MVP)

**Owner:** Ezra Shively-Stjarna
**Target:** Windows 10 (2004+) / Windows 11, x64
**Deliverable:** a single double-clickable `Framer.exe`
**Spec version:** 1.0 — 2026-11-08

---

## 0. READ THIS FIRST — Operating rules for the builder (Claude Code)

You are building this application end-to-end **without asking the owner anything**. Every product decision has already been made in this document. Follow these rules:

1. **Do not ask questions.** Do not pause for confirmation, approvals, or preferences. The owner wants to come back to a finished, working `Framer.exe`.
2. **When something is ambiguous or blocked,** pick the simplest option that satisfies the Acceptance Criteria (§14), write the choice and the reason as one line in `DECISIONS.md`, and keep going.
3. **Never reduce scope silently.** If a feature genuinely cannot be implemented, implement the closest working fallback, and record it in `DECISIONS.md` under "Deviations".
4. **Work in milestones (§15).** Commit at the end of each milestone with a clear message. Run the tests after each milestone.
5. **Finish line:** `release/Framer.exe` exists, launches by double-click with no console window, passes every automated test, and the self-check in §14.2 is complete. Then write `README.md` (owner-facing, plain language) and stop.
6. **The owner does not use a terminal.** Nothing in the final product may require command-line steps, installing Python, or editing config files by hand.
7. Do not add telemetry, network calls, auto-update, accounts, or cloud features. Framer is fully offline.

---

## 1. What Framer is (the story)

Ezra has years of artwork and documents from art school in assorted old formats and applications. He wants to turn them into a clean, consistently named set of high-quality images (and later PDFs) without doing screenshot → crop → rename → save hundreds of times.

**Framer's promise: frame once, then press one key per page.**

He opens a file in whatever app can display it, draws a frame around the area to capture, and from then on presses **F9** each time he pages forward (by button, scroll, or whatever that app uses). Every press saves exactly what is inside the frame, at the screen's full native resolution, as a numbered PNG in his chosen folder. The frame stays put and visible until he re-frames.

Framer does **not** turn pages, control other apps, or read file formats. It captures pixels inside a rectangle. That is the whole point: it works with any application.

---

## 2. Locked decisions (do not revisit)

| Topic | Decision |
|---|---|
| Platform | Windows 10 2004+ and Windows 11, x64 only |
| Language | Python 3.12 |
| Env/packaging tool | `uv` for environment + dependencies; PyInstaller for the exe |
| UI toolkit | PySide6 (Qt 6) |
| Screen capture | `mss` (physical pixels, no scaling) |
| Image handling | Pillow, numpy |
| PDF building | `img2pdf` (lossless, embeds PNG/JPG without re-encoding) |
| Safe delete | `send2trash` (Undo sends to Recycle Bin, never hard-deletes) |
| Global hotkeys | Win32 `RegisterHotKey` via `ctypes`, handled through a Qt native event filter. Do **not** use the `keyboard` or `pynput` packages. |
| Win32 access | `ctypes` only (no pywin32 dependency) |
| DPI | Per-Monitor-Aware V2. All capture math in physical pixels. |
| Default image format | PNG, lossless |
| Page advance | Manual by the user. Framer never sends keys or scrolls. |
| Settings storage | `%APPDATA%\Framer\settings.json` |
| Packaging | PyInstaller **one-file**, windowed (no console), custom icon, version info |
| Network | None. Fully offline. |

---

## 3. User flow (end to end)

### 3.1 Launch
- User double-clicks `Framer.exe`.
- If Framer is already running, the existing instance's Setup window comes to the front and the new process exits (single-instance; see §9.6).
- The **Setup window** opens (§5.1), pre-filled with the last-used settings.

### 3.2 Setup
User confirms or changes:
- Output folder (default: `%USERPROFILE%\Pictures\Framer`; created if missing)
- File prefix (default: `Capture`)
- Next number (auto-detected; see §7.2)
- Format (PNG default; JPG optional)
- Sound on/off, duplicate guard on/off
- Hotkeys (defaults: F8 = Set Frame, F9 = Capture)

Clicks **Start Framing** (big primary button). The Setup window hides and the **Frame Selector** opens (§5.2).

### 3.3 Set the frame
- All monitors dim with a frozen snapshot of the screen underneath.
- Crosshair cursor. A magnifier loupe follows the cursor showing pixels zoomed 8× with a center crosshair and the physical cursor coordinates.
- User drags a rectangle. A live label shows the size in **physical pixels** (e.g. `2480 × 3508 px`).
- After release, the rectangle stays editable: drag inside to move; drag the 8 handles to resize; arrow keys move by 1 px, Shift+arrow by 10 px; Ctrl+arrow grows the right/bottom edge by 1 px, Ctrl+Shift+arrow shrinks it by 1 px.
- **Enter** or double-click inside confirms. **Esc** cancels (returns to the previous frame if one existed, otherwise to Setup).
- A small hint strip at the top of the screen with the rectangle: `Drag to frame · Arrows nudge · Enter to confirm · Esc to cancel`.
- Constraints: minimum 16 × 16 physical px; the frame must sit on a single monitor (if the drag crosses monitors, clamp it to the monitor where the drag started).

### 3.4 Framing mode (the main working state)
- The **Frame Border** appears: a thin cyan outline drawn just **outside** the captured rectangle (§5.3). It never appears in captures.
- The **Floating Bar** appears beside the frame (§5.4): shows prefix, next number, last-capture thumbnail, buttons.
- A system tray icon is present throughout (§5.6).
- Focus goes back to whatever app the user was in. Framer never steals focus in this mode.

### 3.5 Capture loop
- User presses **F9** from anywhere (Framer does not need focus).
- Framer captures the frame rectangle at native resolution, runs the duplicate guard (§7.4), saves the file (§7.1–7.3), logs it (§7.5), and gives feedback: border flashes white for 150 ms, an optional short click sound plays, the bar's counter and thumbnail update, and a toast shows `Saved Prefix_0007.png`.
- User pages forward in their app however that app works, and presses F9 again. Repeat.

### 3.6 Reframe / pause / quit
- **F8** (or the bar's Reframe button) reopens the Frame Selector with the current frame pre-loaded for adjustment.
- The bar's **Setup** button (gear) reopens the Setup window; changing the prefix or folder rescans numbering.
- **Stop** on the bar ends framing mode (hides border + bar, keeps the tray icon, unregisters F9, keeps F8 registered so pressing F8 starts a new frame).
- Quit from the tray menu or the Setup window's Quit button. Settings are saved on every change and on exit.

---

## 4. Visual style

- Clean, dark, compact. Background `#16181D`, panels `#1F2229`, text `#E8EAED`, muted text `#9AA0A6`.
- Accent (frame border, primary buttons, focus rings): cyan `#22D3EE`. Warning: amber `#F59E0B`. Error: `#F87171`. Success flash: white.
- Font: Segoe UI (Windows system font), 10pt body, 9pt for bar labels.
- Rounded corners 8 px on windows/panels, 6 px on buttons.
- Icons: use simple Unicode glyphs or Qt-drawn shapes. No external icon packs.
- App icon: generated at build time with Pillow (§12.3): four cyan corner brackets on a dark rounded square.

---

## 5. Components

### 5.1 Setup window
Normal top-level window, ~460 × 520 logical px, not resizable, centered on the primary screen. Title: `Framer` with the version.

Fields, top to bottom:
1. **Output folder:** read-only path field + `Browse…` button (Qt folder dialog) + `Open` button (opens it in Explorer).
2. **Prefix:** text field. Live validation: strip leading/trailing spaces; replace any of `\ / : * ? " < > |` and control characters with `_`; max 80 chars; must not be empty (show inline error, disable Start). Show a live preview line under it: `Next file: Capture_0001.png`.
3. **Next number:** spin box (1–999999), auto-filled by the folder scan (§7.2). If the user sets a number that would collide with an existing file, show an amber notice: `Prefix_0005.png exists — Framer will skip to the next free number.`
4. **Number digits:** spin box 3–6, default 4.
5. **Format:** radio buttons PNG (default) / JPG. When JPG is selected, show a quality slider 80–100, default 95.
6. **Options:** checkboxes: `Play sound on capture` (on), `Warn on duplicate page` (on), `Remember frame between sessions` (on).
7. **Hotkeys:** two key-capture fields: `Set frame` (F8), `Capture` (F9). Clicking a field and pressing a key combination sets it (allow modifiers Ctrl/Alt/Shift/Win + a key). Validate by attempting registration; if Windows refuses (already taken), show inline error `That key is in use by another app — pick another` and keep the old binding.
8. Buttons: **Start Framing** (primary, cyan), **Quit** (secondary).
   - If a remembered frame exists and still fits the current monitor layout, show an extra button **Use last frame** that skips the selector and goes straight to framing mode.

Closing the Setup window with the X while not in framing mode = quit. While in framing mode, the X just hides the window.

### 5.2 Frame Selector (overlay)
- One frameless, always-on-top, full-screen window **per monitor**, each covering exactly its monitor.
- Before showing, grab a snapshot of each monitor with `mss` (physical pixels). Each overlay paints its monitor's snapshot scaled to the window, then a 50% black dim layer, with the selected rectangle cut out (undimmed) and outlined in cyan (2 px) with 8 square handles (8 × 8 logical px, cyan fill, dark outline).
- Size label: a pill just below the rectangle (or above it if no room) showing `W × H px` in physical pixels.
- Loupe: 140 × 140 logical px circle near the cursor (offset to stay on screen), showing a 17 × 17 physical-pixel region magnified, with a thin crosshair and `x, y` physical coordinates beneath.
- Keyboard and mouse behavior as in §3.3.
- The selector must convert logical Qt coordinates to physical pixels exactly (§8). Show the physical size in the label, not logical.

### 5.3 Frame Border
- Four thin, separate, frameless, always-on-top windows (top, bottom, left, right strips) — or one window with a transparent center — forming an outline **3 px thick with a 2 px gap outside the capture rectangle** (so the innermost border pixel sits 2 px outside the capture area). Prefer four strip windows: simplest way to guarantee the capture area contains no Framer pixels.
- Color cyan `#22D3EE`, 100% opaque. During the capture flash, white for 150 ms. During a duplicate warning, amber for 1.5 s.
- **Click-through:** set extended styles `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE` so mouse input passes to the app underneath and the strips never take focus or appear in Alt+Tab or the taskbar.
- **Excluded from capture:** call `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` (0x11) on every border strip. If that call fails (older build), ignore; the geometry already keeps them outside the capture area.
- If part of the border would fall off-screen (frame touches a monitor edge), just clip it.

### 5.4 Floating Bar
- Small frameless, always-on-top tool window (`WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`), ~300 × 76 logical px, rounded, dark panel, draggable by its body. Also apply `WDA_EXCLUDEFROMCAPTURE`.
- Contents:
  - Left: last-capture thumbnail 56 × 56 (letterboxed); empty placeholder before the first capture. Clicking it opens the last file in the default image viewer.
  - Middle: line 1 = prefix (bold, elided if long); line 2 = `Next: 0008 · Saved: 7` ; line 3 (small, muted) = frame size `2480 × 3508 px`.
  - Right: compact icon buttons with tooltips: **Capture** (also shows the hotkey), **Reframe**, **Undo** (disabled when nothing to undo), **Folder** (opens output folder), **More ▾** menu (`Make PDF…`, `Setup…`, `Stop framing`, `Quit`).
- **Placement:** automatically place the bar 12 px outside the frame — first choice right of the frame, top-aligned; else left; else below; else above; else the top-right corner of the frame's monitor. It must never overlap the capture rectangle. If the user drags it, remember that position for this frame; if they drag it *into* the frame area, snap it back out to the nearest valid side.
- Keyboard shortcut inside the bar (when the user clicks it): `Ctrl+Z` = Undo.

### 5.5 Toasts
- Small rounded pill (dark, white text) appearing just below the floating bar for 1.6 s, fading out. Also `WDA_EXCLUDEFROMCAPTURE`, click-through, no focus.
- Types: success (`Saved Capture_0007.png`), warning (amber left stripe), error (red left stripe; stays 4 s).

### 5.6 System tray icon
- Framer icon with tooltip `Framer — Capture_0007 next` (updates).
- Menu: `Capture (F9)`, `Set frame (F8)`, `Show bar`, `Open folder`, `Make PDF…`, `Setup…`, separator, `Quit`.
- Left-click the tray icon = show the Setup window.

---

## 6. Hotkeys

- Register with `RegisterHotKey(hwnd, id, modifiers | MOD_NOREPEAT, vk)` against a hidden message-only Qt window's HWND; receive `WM_HOTKEY` (0x0312) through a `QAbstractNativeEventFilter` installed on the application.
- Defaults: Set frame = `F8` (id 1), Capture = `F9` (id 2). `MOD_NOREPEAT` always on (holding the key must not fire repeatedly).
- F9 is registered only in framing mode; F8 is registered whenever Framer is running.
- On registration failure at startup: show the Setup window with the inline hotkey error (§5.1 item 7) and a toast; framing can still be used via the bar/tray buttons.
- Store hotkeys in settings as `{ "modifiers": [...], "key": "F9" }`. Map key names to virtual-key codes with a table covering F1–F24, A–Z, 0–9, numpad keys, Insert/Home/End/PageUp/PageDown, Pause, ScrollLock, PrintScreen.
- Unregister all hotkeys on exit (also in an `atexit` handler).

---

## 7. Capture, saving, naming

### 7.1 Capture
- Use `mss` with a `{left, top, width, height}` dict in **physical virtual-desktop coordinates** (§8).
- Convert BGRA → RGB with numpy/Pillow (`Image.frombytes("RGB", size, shot.bgra, "raw", "BGRX")`). No resampling, ever. Output pixel dimensions must equal the frame's physical size exactly.
- Capture runs on the main thread (it's fast); encoding and disk writes run on a worker thread (`QThreadPool`) so the UI never stalls. Captures must be saved in order even if triggered quickly (use a single-worker queue).
- Debounce: ignore a capture trigger that arrives less than 150 ms after the previous one.

### 7.2 Numbering
- Filename pattern: `{prefix}_{number:0{digits}d}.{ext}` — e.g. `Capture_0001.png`.
- On Setup open, on prefix/folder change, and before every save: scan the output folder for files matching `^{re.escape(prefix)}_(\d+)\.(png|jpg|jpeg)$` (case-insensitive). Next number = max(found) + 1, or 1 if none — unless the user typed a higher number, which is respected.
- **Never overwrite.** If the target filename exists at save time (e.g. created externally), increment until free, and note it in the log.

### 7.3 Saving
- PNG: Pillow `save(..., format="PNG", compress_level=6, dpi=(300, 300))` (the DPI tag only sets print size metadata; it does not resample).
- JPG: `quality=<setting>`, `subsampling=0` (4:4:4), `optimize=True`, `dpi=(300, 300)`.
- Write atomically: save to `{name}.part` in the same folder, then `os.replace` to the final name.
- If the folder is missing, recreate it. If saving fails (permissions, disk full, folder on a disconnected drive): show an error toast with the reason, flash the border red, do **not** advance the counter, keep the captured image in memory and retry automatically on the next F9 only if the user hasn't reframed (simple approach: just let the next F9 capture fresh — acceptable).

### 7.4 Duplicate guard
- After capture, downscale the new image to 64 × 64 grayscale and compare with the previous saved capture's 64 × 64 grayscale: mean absolute difference over 0–255. If `< 1.0`, treat it as a duplicate.
- On duplicate (and guard enabled): do not save; flash the border amber; toast `Looks the same as the last page — not saved. Press F9 again within 3 s to save anyway.` A second F9 within 3 s saves it regardless.
- The comparison image for "previous" is only kept in memory for the current session and current frame; reframing clears it.

### 7.5 Capture log
- Append a row to `framer_log.csv` in the output folder (create with header if missing). UTF-8 with BOM so Excel opens it cleanly.
- Columns: `timestamp_iso, filename, width_px, height_px, frame_left, frame_top, monitor, source_window_title, duplicate_override, note`.
- `source_window_title` = title of the foreground window at capture time (`GetForegroundWindow` + `GetWindowTextW`). It usually contains the original document's filename — valuable later.
- On Undo, append a row with `note = "undone (moved to Recycle Bin)"` instead of editing earlier rows.

### 7.6 Undo
- Maintain a session stack of saved file paths. Undo sends the most recent one to the Recycle Bin via `send2trash`, pops it, logs it, updates the thumbnail to the previous capture (or placeholder), and sets the next number back to that file's number **only if** no higher-numbered file exists in the folder.
- Undo depth: unlimited within the session.

### 7.7 Make PDF
- Menu item `Make PDF…` (bar and tray). Opens a small dialog:
  - Source: `All files with prefix "Capture"` (default) or `All images in folder`.
  - Output name: default `{prefix}.pdf` in the same folder; if it exists, add ` (2)`, ` (3)`, etc. Never overwrite.
  - Button: **Create PDF**.
- Sort files by their numeric suffix (natural sort for the "all images" option).
- Build with `img2pdf` (lossless, one image per page, page size from the image's 300 DPI tag). PNGs with alpha: flatten onto white first in a temp copy (img2pdf rejects alpha).
- Run on a worker thread with a progress bar; on finish, toast `Created Capture.pdf (42 pages)` with the bar's Folder button highlighted. Offer `Open PDF` in the dialog.

---

## 8. DPI and coordinate mapping (critical — get this exactly right)

Windows display scaling (125%, 150%, 175%…) and mixed-DPI multi-monitor setups are the #1 source of blurry or misaligned capture tools. Requirements:

1. **Process DPI awareness:** first thing in `main()`, before creating `QApplication`, call `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)` (value `-4`); fall back to `SetProcessDpiAwareness(2)` and then `SetProcessDPIAware()`. Also embed a PerMonitorV2 DPI-aware manifest in the PyInstaller build (§12.2).
2. Set `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)` before creating the app.
3. **Source of truth for monitor rectangles:** enumerate monitors with Win32 `EnumDisplayMonitors` + `GetMonitorInfoW` (MONITORINFOEXW) to get each monitor's physical rect (`rcMonitor`) and device name (`szDevice`, e.g. `\\.\DISPLAY1`).
4. Match each `QScreen` to its Win32 monitor by `QScreen.name()` == `szDevice`. If names don't match (unexpected driver behavior), fall back to matching by order of left/top position, and log the fallback to `DECISIONS.md`-style debug log (`%APPDATA%\Framer\framer.log`).
5. **Logical → physical** for a point `(lx, ly)` on a given screen:
   ```
   sx = phys.width  / qgeom.width()
   sy = phys.height / qgeom.height()
   px = phys.left + round((lx - qgeom.x()) * sx)
   py = phys.top  + round((ly - qgeom.y()) * sy)
   ```
   where `qgeom = screen.geometry()` (logical) and `phys` is that monitor's physical rect. Implement the inverse for placing the border/bar windows.
6. Use the same mapping when positioning the border strips and floating bar so they line up pixel-perfectly with the capture rectangle at any scale factor.
7. Put this math in a pure module (`framer/geometry.py`) with no Qt or Win32 imports in the math functions, so it can be unit-tested with fake monitor tables (100%, 125%, 150%, 200%, mixed-DPI side-by-side, monitor to the left with negative coordinates, stacked vertically).
8. **Display changes:** listen to `QGuiApplication.screenAdded`, `screenRemoved`, and each screen's `geometryChanged`/`logicalDotsPerInchChanged`. On any change while in framing mode: rebuild the monitor table; if the frame's monitor is gone or the frame no longer fits, stop framing mode, toast `Display changed — please set the frame again`, and open the selector.

---

## 9. Robustness and edge cases

1. **Secure desktop / locked screen / UAC prompt:** capture fails or returns black → detect an all-black or failed grab, toast an error, don't save.
2. **Protected content (DRM video etc.):** may capture as black — same handling; not a bug to fix.
3. **HDR displays:** captures may look slightly different from the screen. Document in README "Known limitations"; do not attempt to fix.
4. **Frame larger than 16384 px in either dimension:** impossible on real monitors; clamp anyway.
5. **Output folder on a network drive or NAS:** supported; slower saves are fine (worker thread).
6. **Single instance:** use a named Win32 mutex `Local\Framer_SingleInstance_v1` plus a `QLocalServer` named `Framer_v1`; the second instance sends `show` to the first and exits.
7. **Crash safety:** global exception hook writes the traceback to `%APPDATA%\Framer\framer.log` and shows a friendly error dialog with an `Open log folder` button. Log rotation: keep the last 1 MB.
8. **Settings file corrupt or missing:** fall back to defaults and rewrite it.
9. **Remembered frame:** stored as physical rect + monitor device name + that monitor's physical rect. On launch, offer `Use last frame` only if the same device name exists with the same physical rect.
10. **Taskbar identity:** call `SetCurrentProcessExplicitAppUserModelID("Ezra.Framer")` so the icon groups correctly.

---

## 10. Settings file

`%APPDATA%\Framer\settings.json` — written atomically on every change.

```json
{
  "version": 1,
  "output_folder": "C:\\Users\\<user>\\Pictures\\Framer",
  "prefix": "Capture",
  "digits": 4,
  "format": "png",
  "jpg_quality": 95,
  "sound": true,
  "duplicate_guard": true,
  "remember_frame": true,
  "hotkeys": {
    "set_frame": { "modifiers": [], "key": "F8" },
    "capture":   { "modifiers": [], "key": "F9" }
  },
  "last_frame": {
    "left": 0, "top": 0, "width": 0, "height": 0,
    "monitor_device": "\\\\.\\DISPLAY1",
    "monitor_rect": [0, 0, 3840, 2160]
  },
  "bar_offset": null,
  "setup_window_pos": null
}
```

---

## 11. Project structure

```
framer/
  pyproject.toml            # uv-managed; Python 3.12; deps pinned with compatible ranges
  uv.lock
  README.md                 # owner-facing, plain language (§16)
  DECISIONS.md              # builder's decision + deviation log
  framer/
    __init__.py             # __version__ = "1.0.0"
    __main__.py             # entry: DPI setup → single instance → app
    app.py                  # QApplication, state machine (Setup / Selecting / Framing / Stopped)
    settings.py             # load/save/validate settings
    geometry.py             # pure DPI/coordinate math (unit tested)
    monitors.py             # Win32 monitor enumeration + QScreen matching
    win32.py                # ctypes bindings: hotkeys, window styles, display affinity, foreground title, AppUserModelID, mutex
    hotkeys.py              # registration + native event filter
    selector.py             # Frame Selector overlays + loupe
    border.py               # Frame Border strips
    bar.py                  # Floating Bar
    toast.py                # Toasts
    tray.py                 # System tray
    setup_window.py         # Setup window
    capture.py              # mss capture, duplicate guard, save queue
    naming.py               # prefix sanitizing, numbering scan, next-free-name (unit tested)
    capture_log.py          # CSV log
    pdf.py                  # Make PDF
    sounds.py               # capture click (generated WAV bundled as resource, played with QSoundEffect; fallback winsound)
    assets/                 # generated at build: framer.ico, click.wav
  tests/
    test_geometry.py
    test_naming.py
    test_duplicate.py
    test_capture_log.py
    test_pdf.py
    test_settings.py
  scripts/
    make_assets.py          # generates framer.ico (multi-size 16–256) and click.wav (short 30 ms tick) with Pillow + wave
    build.ps1               # one-shot local build (used by the builder, not the owner)
  framer.spec               # PyInstaller spec
  version_info.txt          # Windows file version resource
  .github/workflows/build.yml
  release/
    Framer.exe              # final deliverable (git-ignored except via Releases)
```

---

## 12. Build and packaging

### 12.1 Environment
- If `uv` is not installed on the build machine: install it (`winget install --id astral-sh.uv -e`, or the official PowerShell installer). Use `uv python install 3.12`, `uv sync`.
- Dependencies (runtime): `PySide6`, `mss`, `Pillow`, `numpy`, `img2pdf`, `send2trash`. Dev: `pytest`, `pyinstaller`.
- To keep the exe smaller, PyInstaller should exclude unused Qt modules (QtWebEngine, Qt3D, QtMultimedia except what `QSoundEffect` needs — if including QtMultimedia bloats or breaks the build, drop `QSoundEffect` and use `winsound.PlaySound` with the bundled WAV instead; log it in DECISIONS.md).

### 12.2 PyInstaller
- One-file, windowed (`console=False`), name `Framer`, icon `framer/assets/framer.ico`, `version_info.txt` embedded.
- Embed an application manifest declaring `<dpiAwareness>PerMonitorV2</dpiAwareness>` and `<dpiAware>true/pm</dpiAware>`, and `asInvoker` execution level (no admin prompt, ever).
- Bundle `framer/assets/*`. Resolve resource paths via `sys._MEIPASS` when frozen.
- Output copied to `release/Framer.exe`.

### 12.3 Assets
- `scripts/make_assets.py` generates the icon (dark `#16181D` rounded square, four cyan `#22D3EE` corner brackets, sizes 16/24/32/48/64/128/256) and a 30 ms soft click WAV (synthesized; no copyrighted audio). Run it as the first build step.

### 12.4 Where to build
- **If you (the builder) are running on Windows:** build locally with `scripts/build.ps1`, run the tests, then launch `release/Framer.exe` once to smoke-test startup (it must show the Setup window and exit cleanly when Quit is invoked; automate via a `--self-test` flag, §14.2).
- **Also, if a GitHub remote is available or `gh` is authenticated:** create (if needed) a **private** repo named `framer`, push, and add `.github/workflows/build.yml`:
  - `on: push` (tags `v*`) and `workflow_dispatch`
  - `runs-on: windows-latest`; install uv; `uv sync`; run `scripts/make_assets.py`; `uv run pytest`; build with PyInstaller; upload `Framer.exe` as a workflow artifact; on tag, attach to a GitHub Release.
  - Tag `v1.0.0` when everything passes.
- **If you are not on Windows and no GitHub access exists:** complete all code, tests (the pure-logic ones run anywhere), workflow file, and README; record in DECISIONS.md that the exe must be produced by the workflow.

### 12.5 Unsigned exe note
The exe is not code-signed. README must explain the one-time Windows SmartScreen prompt (`More info → Run anyway`) in plain words.

---

## 13. `--self-test` mode (for the builder's automated smoke test)

`Framer.exe --self-test` runs headless-ish checks and exits with code 0 on success, non-zero on failure, writing results to `%APPDATA%\Framer\selftest.txt`:
1. DPI awareness context is Per-Monitor V2.
2. Monitor enumeration returns ≥ 1 monitor and every QScreen matched a Win32 monitor.
3. Captures a 200 × 200 physical-px region at the primary monitor's top-left via the real capture path into a temp folder; verifies the PNG is exactly 200 × 200.
4. Naming scan and next-free-name work in the temp folder (creates `Test_0001.png`, expects next `Test_0002.png`).
5. Builds a PDF from two generated images; verifies 2 pages.
6. Registers and unregisters a hotkey (`Ctrl+Alt+Shift+F12`).
7. Cleans up the temp folder.

---

## 14. Acceptance criteria

### 14.1 Automated (must pass)
- `test_geometry.py`: logical↔physical round-trips are exact (±0 px after rounding) for 100/125/150/175/200% scales, mixed-DPI dual monitors, negative-coordinate left monitor, vertically stacked monitors.
- `test_naming.py`: sanitizing; scan with gaps (`_0001, _0002, _0007` → next `_0008`); case-insensitive matching; prefix containing regex characters (e.g. `ID3 (2001) v1.0`); never-overwrite behavior; digits 3–6.
- `test_duplicate.py`: identical images → duplicate; one-page-changed images → not duplicate; tiny noise (±1 per pixel) → duplicate.
- `test_capture_log.py`: header creation, BOM, append, undo row.
- `test_pdf.py`: natural sort order, alpha flattening, no-overwrite naming, page count.
- `test_settings.py`: defaults, corrupt file recovery, atomic write.
- `--self-test` exits 0 on the Windows build machine (or in CI on `windows-latest`, if a display is available there; if CI has no usable display, run only steps 1, 4, 5, 6 in CI and note it).

### 14.2 Builder self-check (do it, then record the results in DECISIONS.md)
- [ ] Double-clicking `release/Framer.exe` opens the Setup window with no console window.
- [ ] No admin/UAC prompt.
- [ ] Start Framing → selector covers all monitors, loupe works, size label shows physical px.
- [ ] Enter confirms; border appears outside the area; bar sits beside the frame, not on it.
- [ ] F9 from another app saves `Capture_0001.png` with exactly the shown pixel size; the border, bar and toast are **not** in the image.
- [ ] Repeated F9 with no change → duplicate warning; second F9 within 3 s saves.
- [ ] Undo moves the file to the Recycle Bin and rolls the counter back.
- [ ] F8 reframes with the old frame pre-loaded.
- [ ] Make PDF produces a correctly ordered PDF.
- [ ] Quit, relaunch: settings remembered; `Use last frame` works.
- [ ] Second launch while running brings the first to front.

---

## 15. Milestones (commit after each)

1. **Skeleton:** uv project, package layout, settings, logging, crash handler, single instance, DPI setup, tray icon, Setup window (no framing yet). Tests: settings.
2. **Geometry + monitors:** `geometry.py`, `monitors.py`, full unit tests.
3. **Selector:** overlays, frozen snapshot, drag/handles/nudge, loupe, size label, confirm/cancel.
4. **Framing mode:** border strips (click-through, capture-excluded), floating bar with placement logic, toasts, hotkeys.
5. **Capture pipeline:** mss capture, naming, save queue, duplicate guard, log, undo, feedback (flash + sound). Tests: naming, duplicate, log.
6. **Make PDF** + tests.
7. **Packaging:** assets script, PyInstaller spec + manifest + version info, `--self-test`, `build.ps1`, GitHub workflow.
8. **Polish + docs:** README, DECISIONS.md self-check results, tag `v1.0.0`.

---

## 16. README.md (owner-facing) — required content

Plain language, no jargon, no terminal commands. Sections:
1. **What Framer does** (two sentences).
2. **Getting it:** download `Framer.exe` (from the `release` folder or the GitHub Release), put it anywhere (Desktop is fine), double-click. The SmartScreen note (§12.5).
3. **Your first capture:** five short steps (choose folder → type prefix → Start Framing → drag the frame and press Enter → press F9 for each page).
4. **Tips for the sharpest images:** zoom the document so the artwork fills as much of the frame as possible; the bar shows the pixel size; on a 4K monitor you get roughly 4× the pixels of 1080p.
5. **Buttons and keys** (a small table).
6. **Making a PDF.**
7. **Where things are saved** (images, `framer_log.csv`, settings location).
8. **Known limitations:** protected video captures black; HDR may shift colors slightly; the frame must sit on one monitor.

---

## 17. Out of scope for v1 (do not build)

Auto page-turning or sending keys to other apps; auto-run mode; scrolling capture/stitching; OCR; window-snap framing; cloud upload; code signing; macOS/Linux; installer (MSI). These are candidates for v2.

---

*End of specification. Build it.*
