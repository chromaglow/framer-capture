# Framer

## What Framer does

Framer captures the same rectangle of your screen every time you press one key, and saves each capture as a numbered, full-resolution PNG. You draw the frame once, then page through any document or artwork in any program and press **F9** for each page.

## Getting it

1. Download `Framer.exe` from the latest release at https://github.com/chromaglow/framer-capture/releases (or take it from the `release` folder of a local build) and put it anywhere you like. The Desktop is fine.
2. Double-click it. The Setup window opens. Nothing else to install.

**The first time**, Windows may show a blue "Windows protected your PC" box because the program is not signed. Click **More info**, then **Run anyway**. Windows only asks once.

Framer is fully offline. It never connects to the internet.

## Your first capture

1. **Choose a folder.** The default is `Pictures\Framer`. Use **Browse…** to pick another.
2. **Type a prefix.** For example `Sketchbook2009`. Files will be named `Sketchbook2009_0001.png`, `_0002`, and so on.
3. Click **Start Framing.** The screen dims and freezes.
4. **Drag a rectangle** around the area you want. Use the handles or the arrow keys to adjust it. The label under the frame shows the exact pixel size. Press **Enter**.
5. Go back to your document and press **F9** for each page. Turn pages however that program does it (click, scroll, arrow keys); Framer never touches the other program.

A thin cyan border shows the frame. A small bar beside it shows the next file number, how many you have saved, and a thumbnail of the last capture.

## Tips for the sharpest images

- Zoom the document in its own program so the artwork fills as much of the frame as possible. Framer saves exactly the screen pixels inside the frame, no more and no less.
- The bar shows the pixel size of the frame. Bigger is better: on a 4K monitor you get roughly four times the pixels of a 1080p monitor.
- Keep the document in the same place while you page through. If you move it, press **F8** and adjust the frame.
- If you press F9 and nothing on the page changed, Framer warns you instead of saving a duplicate. Press F9 again within 3 seconds if you really want it.

## Buttons and keys

| Where | What | Does |
|---|---|---|
| Anywhere | **F9** | Capture the frame |
| Anywhere | **F8** | Set or adjust the frame |
| Frame selector | Drag · handles | Draw and resize the frame |
| Frame selector | Arrow keys · Shift+arrows | Nudge the frame by 1 px · by 10 px |
| Frame selector | Ctrl+arrows · Ctrl+Shift+arrows | Grow · shrink the frame by 1 px |
| Frame selector | **Enter** or double-click | Confirm the frame |
| Frame selector | **Esc** | Cancel |
| Bar | ● | Capture |
| Bar | ⛶ | Reframe |
| Bar | ↶ | Undo the last capture (moves it to the Recycle Bin) |
| Bar | 🗀 | Open the output folder |
| Bar | ⋯ | Make PDF… · Setup… · Stop framing · Quit |
| Bar | thumbnail | Open the last capture |
| Tray icon | left-click | Open the Setup window |
| Tray icon | right-click | Capture · Set frame · Show bar · Open folder · Make PDF · Setup · Quit |

You can change the F8 and F9 keys in the Setup window: click the field and press the key combination you want.

**Use last frame:** when you start Framer again on the same monitors, the Setup window offers this button so you can skip drawing the frame.

## Making a PDF

1. Click **⋯ → Make PDF…** on the bar (or in the tray menu).
2. Keep *All files with prefix* to collect the images of the current prefix, in number order. *All images in folder* takes everything in the folder instead.
3. Click **Create PDF**. The file is named after the prefix, for example `Sketchbook2009.pdf`, and never overwrites an existing PDF (it adds ` (2)`, ` (3)` …).
4. Click **Open PDF** to look at it.

Images go into the PDF as they are, without recompression. Page size follows the 300 dpi setting Framer writes into every image.

## Where things are saved

- **Images:** the folder you chose in Setup (default `C:\Users\<you>\Pictures\Framer`).
- **Capture list:** `framer_log.csv` in the same folder. One row per capture with the time, file name, pixel size, frame position, monitor, and the title of the window that was in front (usually the document's name). Opens in Excel.
- **Settings:** `C:\Users\<you>\AppData\Roaming\Framer\settings.json` (folder, prefix, hotkeys, last frame). You never need to edit it.
- **Log file:** `C:\Users\<you>\AppData\Roaming\Framer\framer.log`, useful only if something goes wrong.

## Known limitations

- Protected video (streaming services, DRM) captures as black. Framer notices an all-black capture and does not save it.
- On HDR displays the colors in a capture can differ slightly from what you see on screen.
- The frame must sit on one monitor. If you drag across two, Framer keeps it on the monitor where you started.
- Framer does not turn pages, scroll, or read file formats. It captures pixels; the other program does the rest.
- Windows only (10 version 2004 or newer, and 11).

## For developers

Python 3.12, PySide6, `mss`, Pillow, `img2pdf`; built with `uv` and PyInstaller. Start with `DEVELOPMENT.md` (architecture, coordinate model, tests, release steps, gotchas), then `FRAMER_SPEC.md` for the intended behavior and `DECISIONS.md` for the judgment calls. Quick start:

```
uv sync
uv run pytest
uv run python -m framer
```

## License

MIT. See `LICENSE`.
