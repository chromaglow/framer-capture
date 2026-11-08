"""System tray icon and menu."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .resources import app_icon


class Tray(QObject):
    capture = Signal()
    set_frame = Signal()
    show_bar = Signal()
    open_folder = Signal()
    make_pdf = Signal()
    setup = Signal()
    quit = Signal()
    activated_left = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.icon = QSystemTrayIcon(app_icon())
        self.menu = QMenu()
        self.act_capture = QAction("Capture (F9)", self.menu)
        self.act_set_frame = QAction("Set frame (F8)", self.menu)
        self.act_show_bar = QAction("Show bar", self.menu)
        self.act_open_folder = QAction("Open folder", self.menu)
        self.act_make_pdf = QAction("Make PDF…", self.menu)
        self.act_setup = QAction("Setup…", self.menu)
        self.act_quit = QAction("Quit", self.menu)
        for a in (self.act_capture, self.act_set_frame, self.act_show_bar, self.act_open_folder,
                  self.act_make_pdf, self.act_setup):
            self.menu.addAction(a)
        self.menu.addSeparator()
        self.menu.addAction(self.act_quit)
        self.icon.setContextMenu(self.menu)

        self.act_capture.triggered.connect(self.capture)
        self.act_set_frame.triggered.connect(self.set_frame)
        self.act_show_bar.triggered.connect(self.show_bar)
        self.act_open_folder.triggered.connect(self.open_folder)
        self.act_make_pdf.triggered.connect(self.make_pdf)
        self.act_setup.triggered.connect(self.setup)
        self.act_quit.triggered.connect(self.quit)
        self.icon.activated.connect(self._on_activated)
        self.icon.setToolTip("Framer")

    def show(self) -> None:
        self.icon.show()

    def hide(self) -> None:
        self.icon.hide()

    def set_hotkey_labels(self, set_frame: str, capture: str) -> None:
        self.act_capture.setText(f"Capture ({capture})")
        self.act_set_frame.setText(f"Set frame ({set_frame})")

    def set_next_name(self, stem: str) -> None:
        self.icon.setToolTip(f"Framer — {stem} next")

    def set_framing(self, framing: bool) -> None:
        self.act_capture.setEnabled(framing)
        self.act_show_bar.setEnabled(framing)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.activated_left.emit()
