"""The Setup window (spec 5.1)."""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Protocol

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import __version__, naming
from .hotkeys import qt_event_to_spec, spec_label
from .resources import app_icon
from .settings import Settings

log = logging.getLogger(__name__)


class SetupController(Protocol):
    def try_set_hotkey(self, name: str, spec: dict) -> bool: ...
    def can_use_last_frame(self) -> bool: ...
    def in_framing_mode(self) -> bool: ...
    def on_settings_changed(self, what: str) -> None: ...


def open_in_explorer(path: str) -> None:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # type: ignore[attr-defined]
    except OSError as exc:
        log.warning("Could not open %s: %s", path, exc)


def open_file_default(path: str) -> None:
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except OSError as exc:
        log.warning("Could not open %s: %s", path, exc)


def reveal_in_explorer(path: str) -> None:
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)], creationflags=0x08000000)
    except OSError:
        open_in_explorer(os.path.dirname(path))


class HotkeyEdit(QLineEdit):
    """Click, press a key combination, done."""

    chosen = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click, then press a key")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spec: dict = {}

    def set_spec(self, spec: dict) -> None:
        self.spec = dict(spec)
        self.setText(spec_label(spec))

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.setText("Press a key…")

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.setText(spec_label(self.spec))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.clearFocus()
            return
        spec = qt_event_to_spec(event)
        if spec is None:
            return
        self.chosen.emit(spec)
        self.clearFocus()


class SetupWindow(QWidget):
    start_framing = Signal()
    use_last_frame = Signal()
    quit_requested = Signal()

    def __init__(self, settings: Settings, controller: SetupController) -> None:
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        self.settings = settings
        self.controller = controller
        self._loading = True
        self.setWindowTitle(f"Framer {__version__}")
        self.setWindowIcon(app_icon())
        self.setFixedSize(460, 560)
        self._build()
        self.load_from_settings()
        self._loading = False
        self._place()

    # -- layout ------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Output folder
        g_out = QGroupBox("Output")
        f_out = QFormLayout(g_out)
        f_out.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        f_out.setHorizontalSpacing(10)
        row = QHBoxLayout()
        self.ed_folder = QLineEdit()
        self.ed_folder.setReadOnly(True)
        self.btn_browse = QPushButton("Browse…")
        self.btn_open = QPushButton("Open")
        row.addWidget(self.ed_folder, 1)
        row.addWidget(self.btn_browse)
        row.addWidget(self.btn_open)
        f_out.addRow("Folder", row)

        self.ed_prefix = QLineEdit()
        self.ed_prefix.setMaxLength(naming.MAX_PREFIX_LEN)
        f_out.addRow("Prefix", self.ed_prefix)
        self.lbl_preview = QLabel("")
        self.lbl_preview.setObjectName("muted")
        f_out.addRow("", self.lbl_preview)

        row2 = QHBoxLayout()
        self.sp_number = QSpinBox()
        self.sp_number.setRange(1, 999999)
        self.sp_number.setFixedWidth(110)
        self.sp_digits = QSpinBox()
        self.sp_digits.setRange(3, 6)
        self.sp_digits.setFixedWidth(60)
        row2.addWidget(self.sp_number)
        row2.addSpacing(12)
        lbl_d = QLabel("Digits")
        lbl_d.setObjectName("muted")
        row2.addWidget(lbl_d)
        row2.addWidget(self.sp_digits)
        row2.addStretch(1)
        f_out.addRow("Next number", row2)
        self.lbl_collision = QLabel("")
        self.lbl_collision.setObjectName("warning")
        self.lbl_collision.setWordWrap(True)
        self.lbl_collision.hide()
        f_out.addRow("", self.lbl_collision)

        row3 = QHBoxLayout()
        self.rb_png = QRadioButton("PNG (lossless)")
        self.rb_jpg = QRadioButton("JPG")
        self.fmt_group = QButtonGroup(self)
        self.fmt_group.addButton(self.rb_png)
        self.fmt_group.addButton(self.rb_jpg)
        row3.addWidget(self.rb_png)
        row3.addWidget(self.rb_jpg)
        row3.addStretch(1)
        f_out.addRow("Format", row3)
        self.quality_row = QWidget()
        qrow = QHBoxLayout(self.quality_row)
        qrow.setContentsMargins(0, 0, 0, 0)
        self.sl_quality = QSlider(Qt.Orientation.Horizontal)
        self.sl_quality.setRange(80, 100)
        self.lbl_quality = QLabel("95")
        self.lbl_quality.setFixedWidth(28)
        qrow.addWidget(self.sl_quality, 1)
        qrow.addWidget(self.lbl_quality)
        f_out.addRow("Quality", self.quality_row)
        root.addWidget(g_out)

        # Options
        g_opt = QGroupBox("Options")
        v_opt = QVBoxLayout(g_opt)
        self.cb_sound = QCheckBox("Play sound on capture")
        self.cb_dup = QCheckBox("Warn on duplicate page")
        self.cb_remember = QCheckBox("Remember frame between sessions")
        for cb in (self.cb_sound, self.cb_dup, self.cb_remember):
            v_opt.addWidget(cb)
        root.addWidget(g_opt)

        # Hotkeys
        g_hk = QGroupBox("Hotkeys")
        f_hk = QFormLayout(g_hk)
        f_hk.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.hk_set_frame = HotkeyEdit()
        self.hk_capture = HotkeyEdit()
        f_hk.addRow("Set frame", self.hk_set_frame)
        f_hk.addRow("Capture", self.hk_capture)
        self.lbl_hk_error = QLabel("")
        self.lbl_hk_error.setObjectName("error")
        self.lbl_hk_error.setWordWrap(True)
        self.lbl_hk_error.hide()
        f_hk.addRow("", self.lbl_hk_error)
        root.addWidget(g_hk)

        root.addStretch(1)

        # Buttons
        brow = QHBoxLayout()
        self.btn_quit = QPushButton("Quit")
        self.btn_last = QPushButton("Use last frame")
        self.btn_start = QPushButton("Start Framing")
        self.btn_start.setObjectName("primary")
        self.btn_start.setDefault(True)
        brow.addWidget(self.btn_quit)
        brow.addStretch(1)
        brow.addWidget(self.btn_last)
        brow.addWidget(self.btn_start)
        root.addLayout(brow)

        # Wiring
        self.btn_browse.clicked.connect(self._browse)
        self.btn_open.clicked.connect(lambda: open_in_explorer(self.settings["output_folder"]))
        self.ed_prefix.textEdited.connect(self._on_prefix_edited)
        self.ed_prefix.editingFinished.connect(self._on_prefix_finished)
        self.sp_number.valueChanged.connect(self._on_number_changed)
        self.sp_digits.valueChanged.connect(self._on_digits_changed)
        self.rb_png.toggled.connect(self._on_format_changed)
        self.sl_quality.valueChanged.connect(self._on_quality_changed)
        self.cb_sound.toggled.connect(lambda v: self._set_bool("sound", v))
        self.cb_dup.toggled.connect(lambda v: self._set_bool("duplicate_guard", v))
        self.cb_remember.toggled.connect(lambda v: self._set_bool("remember_frame", v))
        self.hk_set_frame.chosen.connect(lambda s: self._on_hotkey_chosen("set_frame", s))
        self.hk_capture.chosen.connect(lambda s: self._on_hotkey_chosen("capture", s))
        self.btn_start.clicked.connect(self.start_framing)
        self.btn_last.clicked.connect(self.use_last_frame)
        self.btn_quit.clicked.connect(self.quit_requested)

    def _place(self) -> None:
        pos = self.settings.get("setup_window_pos")
        screen = QGuiApplication.primaryScreen()
        if pos and screen is not None:
            pt = QPoint(int(pos[0]), int(pos[1]))
            for s in QGuiApplication.screens():
                if s.availableGeometry().contains(pt):
                    self.move(pt)
                    return
        if screen is not None:
            g = screen.availableGeometry()
            self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)

    # -- settings <-> widgets ----------------------------------------------
    def load_from_settings(self) -> None:
        s = self.settings
        self._loading = True
        self.ed_folder.setText(s["output_folder"])
        self.ed_folder.setToolTip(s["output_folder"])
        self.ed_prefix.setText(s["prefix"])
        self.sp_digits.setValue(s["digits"])
        (self.rb_png if s["format"] == "png" else self.rb_jpg).setChecked(True)
        self.sl_quality.setValue(s["jpg_quality"])
        self.lbl_quality.setText(str(s["jpg_quality"]))
        self.quality_row.setVisible(s["format"] == "jpg")
        self.cb_sound.setChecked(s["sound"])
        self.cb_dup.setChecked(s["duplicate_guard"])
        self.cb_remember.setChecked(s["remember_frame"])
        self.hk_set_frame.set_spec(s["hotkeys"]["set_frame"])
        self.hk_capture.set_spec(s["hotkeys"]["capture"])
        self._loading = False
        self.rescan_numbering(user_number=None)
        self.refresh_last_frame_button()

    def rescan_numbering(self, user_number: int | None = None) -> None:
        """Folder scan -> next number spin; respects a higher user-chosen number."""
        prefix = naming.sanitize_prefix(self.ed_prefix.text())
        n = naming.next_number(self.settings["output_folder"], prefix, user_number) if prefix else 1
        self._loading = True
        self.sp_number.setValue(n)
        self._loading = False
        self._refresh_preview()

    def current_number(self) -> int:
        return int(self.sp_number.value())

    def set_current_number(self, n: int) -> None:
        self._loading = True
        self.sp_number.setValue(max(1, min(999999, int(n))))
        self._loading = False
        self._refresh_preview()

    def refresh_last_frame_button(self) -> None:
        self.btn_last.setVisible(self.controller.can_use_last_frame())

    def show_hotkey_error(self, message: str) -> None:
        self.lbl_hk_error.setText(message)
        self.lbl_hk_error.show()

    def clear_hotkey_error(self) -> None:
        self.lbl_hk_error.hide()

    def _refresh_preview(self) -> None:
        prefix = naming.sanitize_prefix(self.ed_prefix.text())
        valid = bool(prefix)
        self.ed_prefix.setProperty("invalid", not valid)
        self.ed_prefix.style().unpolish(self.ed_prefix)
        self.ed_prefix.style().polish(self.ed_prefix)
        self.btn_start.setEnabled(valid)
        self.btn_last.setEnabled(valid)
        if not valid:
            self.lbl_preview.setText("Prefix can’t be empty")
            self.lbl_preview.setObjectName("error")
            self.lbl_collision.hide()
        else:
            self.lbl_preview.setObjectName("muted")
            name = naming.format_name(prefix, self.sp_number.value(), self.sp_digits.value(), self.settings.extension)
            self.lbl_preview.setText(f"Next file: {name}")
            if naming.number_exists(self.settings["output_folder"], prefix, self.sp_number.value()):
                self.lbl_collision.setText(f"{name} exists — Framer will skip to the next free number.")
                self.lbl_collision.show()
            else:
                self.lbl_collision.hide()
        self.lbl_preview.style().unpolish(self.lbl_preview)
        self.lbl_preview.style().polish(self.lbl_preview)

    # -- handlers ----------------------------------------------------------
    def _browse(self) -> None:
        start = self.settings["output_folder"]
        folder = QFileDialog.getExistingDirectory(self, "Choose the output folder", start)
        if folder:
            folder = os.path.normpath(folder)
            self.settings.set("output_folder", folder)
            self.ed_folder.setText(folder)
            self.ed_folder.setToolTip(folder)
            self.rescan_numbering()
            self.controller.on_settings_changed("output_folder")

    def _on_prefix_edited(self, text: str) -> None:
        clean = naming.sanitize_prefix(text)
        if clean:
            self.settings.set("prefix", clean)
        self.rescan_numbering()
        self.controller.on_settings_changed("prefix")

    def _on_prefix_finished(self) -> None:
        clean = naming.sanitize_prefix(self.ed_prefix.text())
        if clean and clean != self.ed_prefix.text():
            self.ed_prefix.setText(clean)
            self._refresh_preview()

    def _on_number_changed(self, value: int) -> None:
        if self._loading:
            return
        self._refresh_preview()
        self.controller.on_settings_changed("next_number")

    def _on_digits_changed(self, value: int) -> None:
        if self._loading:
            return
        self.settings.set("digits", int(value))
        self._refresh_preview()
        self.controller.on_settings_changed("digits")

    def _on_format_changed(self, png_checked: bool) -> None:
        if self._loading:
            return
        self.settings.set("format", "png" if png_checked else "jpg")
        self.quality_row.setVisible(not png_checked)
        self._refresh_preview()
        self.controller.on_settings_changed("format")

    def _on_quality_changed(self, value: int) -> None:
        self.lbl_quality.setText(str(value))
        if self._loading:
            return
        self.settings.set("jpg_quality", int(value))

    def _set_bool(self, key: str, value: bool) -> None:
        if self._loading:
            return
        self.settings.set(key, bool(value))
        self.controller.on_settings_changed(key)

    def _on_hotkey_chosen(self, name: str, spec: dict) -> None:
        field = self.hk_set_frame if name == "set_frame" else self.hk_capture
        other = self.settings["hotkeys"]["capture" if name == "set_frame" else "set_frame"]
        if spec_label(spec) == spec_label(other):
            self.show_hotkey_error("That key is already used by the other hotkey — pick another")
            field.set_spec(self.settings["hotkeys"][name])
            return
        if self.controller.try_set_hotkey(name, spec):
            self.clear_hotkey_error()
            field.set_spec(spec)
        else:
            self.show_hotkey_error("That key is in use by another app — pick another")
            field.set_spec(self.settings["hotkeys"][name])

    # -- window events -----------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        self._remember_pos()
        if self.controller.in_framing_mode():
            event.ignore()
            self.hide()
        else:
            event.ignore()
            self.quit_requested.emit()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._remember_pos()
        super().hideEvent(event)

    def _remember_pos(self) -> None:
        try:
            p = self.pos()
            self.settings.set("setup_window_pos", [p.x(), p.y()])
        except Exception:
            pass

    def bring_to_front(self) -> None:
        self.load_from_settings()
        self.showNormal()
        self.raise_()
        self.activateWindow()
