"""Global hotkeys: Win32 RegisterHotKey on a hidden Qt window + QAbstractNativeEventFilter."""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from . import win32

log = logging.getLogger(__name__)

HK_SET_FRAME = 1
HK_CAPTURE = 2
HK_SELFTEST = 99

MOD_ORDER = ("Ctrl", "Alt", "Shift", "Win")


def spec_to_win32(spec: dict) -> tuple[int, int] | None:
    """{'modifiers': [...], 'key': 'F9'} -> (modifier flags, vk) or None if unknown."""
    if not isinstance(spec, dict):
        return None
    vk = win32.VK_TABLE.get(str(spec.get("key", "")))
    if vk is None:
        return None
    flags = 0
    for m in spec.get("modifiers", []) or []:
        flags |= win32.MODIFIER_FLAGS.get(m, 0)
    return flags, vk


def spec_label(spec: dict | None) -> str:
    if not spec or not spec.get("key"):
        return "none"
    mods = [m for m in MOD_ORDER if m in (spec.get("modifiers") or [])]
    return "+".join(mods + [str(spec["key"])])


_QT_KEY_NAMES: dict[int, str] = {}
for _i in range(1, 25):
    _QT_KEY_NAMES[int(getattr(Qt.Key, f"Key_F{_i}"))] = f"F{_i}"
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _QT_KEY_NAMES[int(getattr(Qt.Key, f"Key_{_c}"))] = _c
for _d in "0123456789":
    _QT_KEY_NAMES[int(getattr(Qt.Key, f"Key_{_d}"))] = _d
_QT_KEY_NAMES.update(
    {
        int(Qt.Key.Key_Insert): "Insert",
        int(Qt.Key.Key_Delete): "Delete",
        int(Qt.Key.Key_Home): "Home",
        int(Qt.Key.Key_End): "End",
        int(Qt.Key.Key_PageUp): "PageUp",
        int(Qt.Key.Key_PageDown): "PageDown",
        int(Qt.Key.Key_Pause): "Pause",
        int(Qt.Key.Key_ScrollLock): "ScrollLock",
        int(Qt.Key.Key_Print): "PrintScreen",
        int(Qt.Key.Key_Space): "Space",
        int(Qt.Key.Key_Asterisk): "NumMultiply",
        int(Qt.Key.Key_Plus): "NumAdd",
        int(Qt.Key.Key_Minus): "NumSubtract",
        int(Qt.Key.Key_Slash): "NumDivide",
    }
)


def qt_event_to_spec(event: QKeyEvent) -> dict | None:
    """Translate a key press in the Setup window into a hotkey spec. None for bare modifiers / unknown."""
    key = int(event.key())
    if key in (
        int(Qt.Key.Key_Control), int(Qt.Key.Key_Shift), int(Qt.Key.Key_Alt), int(Qt.Key.Key_Meta),
        int(Qt.Key.Key_AltGr), int(Qt.Key.Key_unknown),
    ):
        return None
    name = _QT_KEY_NAMES.get(key)
    if name is None:
        return None
    mods = event.modifiers()
    out = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        out.append("Ctrl")
    if mods & Qt.KeyboardModifier.AltModifier:
        out.append("Alt")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        out.append("Shift")
    if mods & Qt.KeyboardModifier.MetaModifier:
        out.append("Win")
    if mods & Qt.KeyboardModifier.KeypadModifier and name in "0123456789" and len(name) == 1:
        name = f"Num{name}"
    return {"modifiers": out, "key": name}


class HotkeyManager(QAbstractNativeEventFilter):
    """Owns a hidden window HWND, registers/unregisters hotkeys, dispatches WM_HOTKEY."""

    def __init__(self) -> None:
        super().__init__()
        self._window = QWidget(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self._window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self._window.setWindowTitle("Framer hotkeys")
        self._window.resize(1, 1)
        self.hwnd = int(self._window.winId())
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._registered: dict[int, dict] = {}
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)

    # -- registration ------------------------------------------------------
    def register(self, hk_id: int, spec: dict, callback: Callable[[], None]) -> bool:
        parsed = spec_to_win32(spec)
        if parsed is None:
            log.warning("Unknown hotkey spec %r", spec)
            return False
        if hk_id in self._registered:
            self.unregister(hk_id)
        flags, vk = parsed
        ok = win32.register_hotkey(self.hwnd, hk_id, flags, vk)
        if ok:
            self._registered[hk_id] = dict(spec)
            self._callbacks[hk_id] = callback
            log.info("Hotkey %s registered as %s", hk_id, spec_label(spec))
        return ok

    def unregister(self, hk_id: int) -> None:
        if hk_id in self._registered:
            win32.unregister_hotkey(self.hwnd, hk_id)
            self._registered.pop(hk_id, None)
            self._callbacks.pop(hk_id, None)

    def unregister_all(self) -> None:
        for hk_id in list(self._registered):
            self.unregister(hk_id)

    def is_registered(self, hk_id: int) -> bool:
        return hk_id in self._registered

    def probe(self, spec: dict, hk_id: int = 50) -> bool:
        """Try registering a spec temporarily to see whether Windows allows it."""
        parsed = spec_to_win32(spec)
        if parsed is None:
            return False
        flags, vk = parsed
        # If the same spec is already ours, it is available to us.
        for rid, s in self._registered.items():
            if spec_to_win32(s) == parsed:
                return True
        ok = win32.register_hotkey(self.hwnd, hk_id, flags, vk)
        if ok:
            win32.unregister_hotkey(self.hwnd, hk_id)
        return ok

    # -- dispatch ----------------------------------------------------------
    def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt API)
        try:
            if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == win32.WM_HOTKEY:
                    hk_id = int(msg.wParam)
                    cb = self._callbacks.get(hk_id)
                    if cb is not None:
                        QTimer.singleShot(0, cb)
                        return True, 0
        except Exception:  # pragma: no cover - never let a filter exception kill the loop
            log.exception("nativeEventFilter failed")
        return False, 0
