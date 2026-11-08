"""FramerApp: the state machine (Setup / Selecting / Framing / Stopped) wiring every component."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QApplication
from send2trash import send2trash

from . import capture_log, naming, sounds, theme, win32
from .bar import FloatingBar
from .border import FrameBorder
from .capture import CaptureEngine, SaveJob, SaveResult, is_black, is_duplicate, to_gray64
from .geometry import Monitor, Rect, frame_fits, remembered_frame_valid
from .hotkeys import HK_CAPTURE, HK_SET_FRAME, HotkeyManager, spec_label
from .monitors import MonitorTable
from .pdf import PdfDialog
from .selector import FrameSelector
from .settings import Settings
from .setup_window import SetupWindow, open_file_default, open_in_explorer
from .toast import ERROR, SUCCESS, WARNING, Toast
from .tray import Tray

log = logging.getLogger(__name__)

SETUP, SELECTING, FRAMING, STOPPED = "setup", "selecting", "framing", "stopped"
DEBOUNCE_S = 0.150
DUP_OVERRIDE_WINDOW_S = 3.0
FLASH_MS = 150
WARN_FLASH_MS = 1500


class FramerApp(QObject):
    def __init__(self, qapp: QApplication, settings: Settings) -> None:
        super().__init__()
        self.qapp = qapp
        self.settings = settings
        self.state = SETUP
        self.table = MonitorTable()
        self.hotkeys = HotkeyManager()
        self.tray = Tray(self)
        self.selector = FrameSelector(self.table)
        self.border = FrameBorder()
        self.bar = FloatingBar()
        self.toast = Toast()
        self.engine = CaptureEngine()
        self.setup = SetupWindow(settings, self)
        self.pdf_dialog: Optional[PdfDialog] = None

        # session state
        self.frame: Optional[Rect] = None
        self.frame_mon: Optional[Monitor] = None
        self.saved_count = 0
        self.undo_stack: list[SaveResult] = []
        self._gray_by_path: dict[str, np.ndarray] = {}
        self.last_gray: Optional[np.ndarray] = None
        self.next_number = 1
        self._last_trigger = 0.0
        self._dup_override_until = 0.0
        self._prev_foreground = 0
        self._prev_frame_for_cancel: tuple[Rect, Monitor] | None = None
        self._display_timer = QTimer(self)
        self._display_timer.setSingleShot(True)
        self._display_timer.setInterval(400)
        self._display_timer.timeout.connect(self._on_display_changed)

        self._wire()

    # ---- wiring -------------------------------------------------------------
    def _wire(self) -> None:
        s = self.setup
        s.start_framing.connect(self.start_framing_from_setup)
        s.use_last_frame.connect(self.use_last_frame)
        s.quit_requested.connect(self.quit)

        self.selector.confirmed.connect(self._on_frame_confirmed)
        self.selector.cancelled.connect(self._on_frame_cancelled)

        b = self.bar
        b.capture.connect(self.capture)
        b.reframe.connect(self.open_selector)
        b.undo.connect(self.undo)
        b.open_folder.connect(self.open_folder)
        b.make_pdf.connect(self.make_pdf)
        b.setup.connect(self.show_setup)
        b.stop.connect(self.stop_framing)
        b.quit.connect(self.quit)
        b.open_last.connect(self.open_last)
        b.moved_by_user.connect(self._on_bar_moved)

        t = self.tray
        t.capture.connect(self.capture)
        t.set_frame.connect(self.open_selector)
        t.show_bar.connect(self.show_bar)
        t.open_folder.connect(self.open_folder)
        t.make_pdf.connect(self.make_pdf)
        t.setup.connect(self.show_setup)
        t.quit.connect(self.quit)
        t.activated_left.connect(self.show_setup)

        self.engine.saved.connect(self._on_saved)
        self.engine.failed.connect(self._on_save_failed)

        gui = QGuiApplication.instance()
        gui.screenAdded.connect(self._screen_added)
        gui.screenRemoved.connect(lambda _s: self._display_timer.start())
        for sc in QGuiApplication.screens():
            self._watch_screen(sc)

    def _screen_added(self, screen) -> None:
        self._watch_screen(screen)
        self._display_timer.start()

    def _watch_screen(self, screen) -> None:
        try:
            screen.geometryChanged.connect(lambda _g: self._display_timer.start())
            screen.logicalDotsPerInchChanged.connect(lambda _d: self._display_timer.start())
        except Exception:
            pass

    # ---- startup ------------------------------------------------------------
    def start(self) -> None:
        self.tray.show()
        self._refresh_hotkey_labels()
        ok = self.hotkeys.register(HK_SET_FRAME, self.settings["hotkeys"]["set_frame"], self.open_selector)
        self.next_number = naming.next_number(self.settings["output_folder"], self.settings["prefix"])
        self._refresh_counters()
        self.setup.show()
        if not ok:
            self.setup.show_hotkey_error(
                f"Set-frame hotkey {spec_label(self.settings['hotkeys']['set_frame'])} is in use by another app — pick another"
            )
            self._toast("Hotkey unavailable — you can still use the buttons", WARNING)
        if self.table.used_fallback:
            log.warning("Monitor matching used positional fallback")

    # ---- SetupController protocol ------------------------------------------
    def try_set_hotkey(self, name: str, spec: dict) -> bool:
        hk_id = HK_SET_FRAME if name == "set_frame" else HK_CAPTURE
        old = self.settings["hotkeys"][name]
        if hk_id == HK_SET_FRAME or self.state == FRAMING:
            cb = self.open_selector if hk_id == HK_SET_FRAME else self.capture
            if self.hotkeys.register(hk_id, spec, cb):
                ok = True
            else:
                self.hotkeys.register(hk_id, old, cb)
                ok = False
        else:
            ok = self.hotkeys.probe(spec)
        if ok:
            hks = dict(self.settings["hotkeys"])
            hks[name] = dict(spec)
            self.settings.set("hotkeys", hks)
            self._refresh_hotkey_labels()
            self.setup.clear_hotkey_error()
        return ok

    def can_use_last_frame(self) -> bool:
        return bool(self.settings["remember_frame"]) and remembered_frame_valid(self.settings["last_frame"], self.table.monitors) is not None

    def in_framing_mode(self) -> bool:
        return self.state in (FRAMING, STOPPED, SELECTING)

    def on_settings_changed(self, what: str) -> None:
        if what in ("prefix", "output_folder", "digits", "format", "next_number"):
            self.next_number = self.setup.current_number()
            if what in ("prefix", "output_folder"):
                self.last_gray = None
        self._refresh_counters()

    # ---- state transitions ---------------------------------------------------
    def start_framing_from_setup(self) -> None:
        self.next_number = self.setup.current_number()
        self.setup.hide()
        initial = (self.frame, self.frame_mon) if (self.frame and self.frame_mon) else None
        if initial is None:
            mon = remembered_frame_valid(self.settings["last_frame"], self.table.monitors)
            if mon is not None and self.settings["remember_frame"]:
                lf = self.settings["last_frame"]
                initial = (Rect(lf["left"], lf["top"], lf["width"], lf["height"]), mon)
        self.open_selector(initial)

    def use_last_frame(self) -> None:
        mon = remembered_frame_valid(self.settings["last_frame"], self.table.monitors)
        if mon is None:
            self.start_framing_from_setup()
            return
        self.next_number = self.setup.current_number()
        lf = self.settings["last_frame"]
        self.setup.hide()
        self._prev_foreground = 0
        self.enter_framing(Rect(lf["left"], lf["top"], lf["width"], lf["height"]), mon)

    def open_selector(self, initial: tuple[Rect, Monitor] | None = None) -> None:
        if self.state == SELECTING:
            return
        if initial is None and self.frame is not None and self.frame_mon is not None:
            initial = (self.frame, self.frame_mon)
        self._prev_frame_for_cancel = (self.frame, self.frame_mon) if (self.frame and self.frame_mon and self.state == FRAMING) else None
        was_framing = self.state == FRAMING
        self.state = SELECTING
        self._prev_foreground = win32.get_foreground_hwnd()
        self.hotkeys.unregister(HK_CAPTURE)
        self.border.hide()
        self.bar.hide()
        self.toast.hide_now()
        self.tray.set_framing(False)
        if self.setup.isVisible():
            self.setup.hide()
        self.table.rebuild()
        init_rect, init_mon = (None, None)
        if initial:
            init_rect, init_mon = initial
            init_mon = self.table.by_device(init_mon.device) or init_mon
            if frame_fits(init_rect, [init_mon]) is None:
                init_rect, init_mon = None, None
        delay = 160 if was_framing else 60
        QTimer.singleShot(delay, lambda: self.selector.open(init_rect, init_mon))

    def _on_frame_confirmed(self, rect: Rect, mon: Monitor) -> None:
        changed = rect != self.frame or (self.frame_mon is not None and mon.device != self.frame_mon.device)
        if changed:
            self.settings.set("bar_offset", None, save=False)
        self.enter_framing(rect, mon)

    def _on_frame_cancelled(self) -> None:
        if self._prev_frame_for_cancel is not None:
            rect, mon = self._prev_frame_for_cancel
            self._prev_frame_for_cancel = None
            self.enter_framing(rect, mon)
        elif self.frame is not None and self.frame_mon is not None and self.state != SETUP:
            self.state = STOPPED
            self.tray.set_framing(False)
            self.show_setup()
        else:
            self.state = SETUP
            self.show_setup()

    def enter_framing(self, rect: Rect, mon: Monitor) -> None:
        if rect != self.frame:
            self.last_gray = None
        self.frame, self.frame_mon = rect, mon
        self.state = FRAMING
        if self.settings["remember_frame"]:
            self.settings.set(
                "last_frame",
                {
                    "left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height,
                    "monitor_device": mon.device, "monitor_rect": list(mon.phys.as_tuple()),
                },
                save=False,
            )
        self.settings.save()
        self.border.show_for(rect, mon)
        self.bar.place_for_frame(rect, mon, self.settings.get("bar_offset"))
        self._refresh_counters()
        self.bar.set_undo_enabled(bool(self.undo_stack))
        self.tray.set_framing(True)
        if not self.hotkeys.register(HK_CAPTURE, self.settings["hotkeys"]["capture"], self.capture):
            self._toast(f"Capture hotkey {spec_label(self.settings['hotkeys']['capture'])} is in use by another app — use the bar button or change it in Setup", WARNING)
        # Give focus back to the app the user was working in.
        prev = self._prev_foreground
        self._prev_foreground = 0
        if prev:
            QTimer.singleShot(30, lambda: win32.set_foreground(prev))
        QTimer.singleShot(250, self._repin)

    def _repin(self) -> None:
        if self.state == FRAMING:
            self.border.reapply()
            self.bar.reapply()

    def stop_framing(self) -> None:
        if self.state not in (FRAMING,):
            return
        self.state = STOPPED
        self.hotkeys.unregister(HK_CAPTURE)
        self.border.hide()
        self.bar.hide()
        self.toast.hide_now()
        self.tray.set_framing(False)
        self.settings.save()

    def show_setup(self) -> None:
        self.setup.bring_to_front()

    def show_bar(self) -> None:
        if self.state == FRAMING and self.frame and self.frame_mon:
            self.bar.place_for_frame(self.frame, self.frame_mon, self.settings.get("bar_offset"))

    def quit(self) -> None:
        log.info("Quit requested")
        try:
            self.settings.save()
        except OSError:
            pass
        self.hotkeys.unregister_all()
        self.border.hide()
        self.bar.hide()
        self.toast.hide_now()
        self.selector.close()
        self.engine.wait(15000)
        self.engine.close()
        self.tray.hide()
        self.qapp.quit()

    # ---- capture loop ----------------------------------------------------------
    def capture(self) -> None:
        if self.state != FRAMING or self.frame is None or self.frame_mon is None:
            return
        now = time.monotonic()
        if now - self._last_trigger < DEBOUNCE_S:
            return
        self._last_trigger = now
        try:
            img = self.engine.grab(self.frame)
        except Exception as exc:
            log.exception("Capture failed")
            self.border.flash(theme.ERROR, WARN_FLASH_MS)
            self._toast(f"Capture failed: {exc}", ERROR)
            return
        if is_black(img):
            self.border.flash(theme.ERROR, WARN_FLASH_MS)
            self._toast("Capture came back black (locked screen or protected content) — not saved", ERROR)
            return
        gray = to_gray64(img)
        override = False
        if self.settings["duplicate_guard"] and self.last_gray is not None and is_duplicate(gray, self.last_gray):
            if now <= self._dup_override_until:
                override = True
            else:
                self._dup_override_until = now + DUP_OVERRIDE_WINDOW_S
                self.border.flash(theme.WARNING, WARN_FLASH_MS)
                self._toast("Looks the same as the last page — not saved. Press F9 again within 3 s to save anyway.", WARNING)
                return
        self._dup_override_until = 0.0
        self.last_gray = gray
        s = self.settings
        job = SaveJob(
            image=img,
            folder=s["output_folder"],
            prefix=s["prefix"],
            start_number=self.next_number,
            digits=s["digits"],
            fmt=s.extension,
            quality=s["jpg_quality"],
            frame=self.frame,
            monitor=self.frame_mon.device,
            source_title=win32.get_foreground_title(),
            duplicate_override=override,
        )
        self._pending_gray = gray
        self._gray_by_path[f"pending:{self.next_number}"] = gray
        self.engine.submit(job)
        self.next_number += 1
        self.border.flash(theme.FLASH, FLASH_MS)
        if s["sound"]:
            sounds.play_click()
        self._refresh_counters()

    def _on_saved(self, r: SaveResult) -> None:
        self.saved_count += 1
        self.undo_stack.append(r)
        gray = self._gray_by_path.pop(f"pending:{r.number}", None)
        if gray is None:
            # numbering skipped ahead; adopt the most recent pending gray
            pend = [k for k in self._gray_by_path if k.startswith("pending:")]
            if pend:
                gray = self._gray_by_path.pop(sorted(pend)[0])
        if gray is not None:
            self._gray_by_path[r.path] = gray
        self.next_number = max(self.next_number, r.number + 1)
        self.bar.set_thumbnail(QPixmap.fromImage(r.thumbnail))
        self.bar.set_undo_enabled(True)
        self._refresh_counters()
        self._toast(f"Saved {r.filename}", SUCCESS)
        log.info("Saved %s (%sx%s)%s", r.path, r.width, r.height, " [skipped ahead]" if r.skipped else "")

    def _on_save_failed(self, msg: str) -> None:
        self.border.flash(theme.ERROR, WARN_FLASH_MS)
        self._toast(f"Couldn’t save: {msg}", ERROR)
        self.next_number = naming.next_number(self.settings["output_folder"], self.settings["prefix"], self.setup.current_number())
        self._refresh_counters()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        r = self.undo_stack.pop()
        try:
            if Path(r.path).exists():
                send2trash(r.path)
        except Exception as exc:
            log.exception("Undo failed")
            self._toast(f"Couldn’t move {r.filename} to the Recycle Bin: {exc}", ERROR)
            self.undo_stack.append(r)
            return
        capture_log.append_undo_row(self.settings["output_folder"], r.filename, r.width, r.height, r.frame.left, r.frame.top, r.monitor)
        self.saved_count = max(0, self.saved_count - 1)
        self._gray_by_path.pop(r.path, None)
        used = naming.scan_numbers(self.settings["output_folder"], self.settings["prefix"])
        if not any(n > r.number for n in used):
            self.next_number = r.number
        if self.undo_stack:
            prev = self.undo_stack[-1]
            self.bar.set_thumbnail(QPixmap.fromImage(prev.thumbnail))
            self.last_gray = self._gray_by_path.get(prev.path)
        else:
            self.bar.set_thumbnail(None)
            self.last_gray = None
        self.bar.set_undo_enabled(bool(self.undo_stack))
        self._refresh_counters()
        self._toast(f"Undid {r.filename} — moved to the Recycle Bin", WARNING)

    # ---- helpers -------------------------------------------------------------------
    def _next_stem(self) -> str:
        return f"{self.settings['prefix']}_{self.next_number:0{self.settings['digits']}d}"

    def _refresh_counters(self) -> None:
        digits = self.settings["digits"]
        self.bar.set_info(self.settings["prefix"], f"{self.next_number:0{digits}d}", self.saved_count, self.frame)
        self.tray.set_next_name(self._next_stem())
        if self.setup.isVisible() and self.setup.current_number() != self.next_number:
            self.setup.set_current_number(self.next_number)

    def _refresh_hotkey_labels(self) -> None:
        sf = spec_label(self.settings["hotkeys"]["set_frame"])
        cp = spec_label(self.settings["hotkeys"]["capture"])
        self.tray.set_hotkey_labels(sf, cp)
        self.bar.set_hotkey_labels(sf, cp)

    def _toast(self, text: str, kind: str) -> None:
        if self.state == FRAMING and self.frame_mon is not None:
            self.toast.show_message(text, kind, self.bar.phys_rect, self.frame, self.frame_mon)
        else:
            self.toast.show_message(text, kind, None, None, self.table.primary())

    def _on_bar_moved(self, phys: Rect) -> None:
        if self.frame is not None:
            self.settings.set("bar_offset", [phys.left - self.frame.left, phys.top - self.frame.top])

    def open_folder(self) -> None:
        open_in_explorer(self.settings["output_folder"])

    def open_last(self) -> None:
        if self.undo_stack:
            open_file_default(self.undo_stack[-1].path)

    def make_pdf(self) -> None:
        if self.pdf_dialog is not None and self.pdf_dialog.isVisible():
            self.pdf_dialog.raise_()
            self.pdf_dialog.activateWindow()
            return
        self.pdf_dialog = PdfDialog(self.settings["output_folder"], self.settings["prefix"])
        self.pdf_dialog.setWindowIcon(self.setup.windowIcon())
        self.pdf_dialog.created.connect(self._on_pdf_created)
        self.pdf_dialog.show()
        self.pdf_dialog.raise_()
        self.pdf_dialog.activateWindow()

    def _on_pdf_created(self, path: str, pages: int) -> None:
        self._toast(f"Created {Path(path).name} ({pages} pages)", SUCCESS)
        self.bar.highlight_folder()

    def _on_display_changed(self) -> None:
        log.info("Display configuration changed")
        self.table.rebuild()
        if self.state == FRAMING and self.frame is not None and self.frame_mon is not None:
            mon = self.table.by_device(self.frame_mon.device)
            if mon is None or mon.phys != self.frame_mon.phys or frame_fits(self.frame, [mon]) is None:
                self.stop_framing()
                self._toast("Display changed — please set the frame again", WARNING)
                self.frame, self.frame_mon = None, None
                QTimer.singleShot(400, lambda: self.open_selector(None))
            else:
                self.frame_mon = mon
                self.border.show_for(self.frame, mon)
                self.bar.place_for_frame(self.frame, mon, self.settings.get("bar_offset"))
        self.setup.refresh_last_frame_button()
