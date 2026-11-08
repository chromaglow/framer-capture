"""ctypes bindings for the Win32 pieces Framer needs. No pywin32."""
from __future__ import annotations

import atexit
import ctypes
import logging
import os
from ctypes import wintypes
from dataclasses import dataclass

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    shcore = ctypes.WinDLL("shcore", use_last_error=True)
except OSError:  # pragma: no cover
    shcore = None
try:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
except OSError:  # pragma: no cover
    shell32 = None

# ---- constants -----------------------------------------------------------
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1

ERROR_ALREADY_EXISTS = 183
MONITORINFOF_PRIMARY = 0x1

# ---- function prototypes ------------------------------------------------
user32.SetWindowLongPtrW.restype = ctypes.c_longlong
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
user32.GetWindowLongPtrW.restype = ctypes.c_longlong
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetMonitorInfoW.restype = wintypes.BOOL
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]

try:
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    _HAS_DISPLAY_AFFINITY = True
except AttributeError:  # pragma: no cover
    _HAS_DISPLAY_AFFINITY = False


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


_MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)


# ---- DPI -----------------------------------------------------------------
def set_process_dpi_awareness() -> str:
    """Per-Monitor-Aware V2, with fallbacks. Returns a label describing what took effect."""
    try:
        fn = user32.SetProcessDpiAwarenessContext
        fn.restype = wintypes.BOOL
        fn.argtypes = [ctypes.c_void_p]
        if fn(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)):
            return "PerMonitorV2"
        # Already set (e.g. by the exe manifest) returns FALSE with ERROR_ACCESS_DENIED - verify.
        if is_per_monitor_v2():
            return "PerMonitorV2"
    except AttributeError:
        pass
    try:
        if shcore is not None and shcore.SetProcessDpiAwareness(2) == 0:
            return "PerMonitor"
    except Exception:
        pass
    try:
        if user32.SetProcessDPIAware():
            return "System"
    except Exception:
        pass
    return "Unaware"


def is_per_monitor_v2() -> bool:
    try:
        user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.AreDpiAwarenessContextsEqual.restype = wintypes.BOOL
        user32.AreDpiAwarenessContextsEqual.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ctx = user32.GetThreadDpiAwarenessContext()
        return bool(
            user32.AreDpiAwarenessContextsEqual(
                ctypes.c_void_p(ctx), ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            )
        )
    except Exception:
        return False


# ---- monitors ------------------------------------------------------------
@dataclass(frozen=True)
class Win32Monitor:
    device: str
    left: int
    top: int
    width: int
    height: int
    primary: bool
    dpi: int

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


def enumerate_monitors() -> list[Win32Monitor]:
    result: list[Win32Monitor] = []

    def cb(hmon, hdc, lprect, lparam):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            dpi = 96
            if shcore is not None:
                dx, dy = ctypes.c_uint(), ctypes.c_uint()
                try:
                    if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
                        dpi = dx.value
                except Exception:
                    pass
            result.append(
                Win32Monitor(
                    device=mi.szDevice,
                    left=r.left,
                    top=r.top,
                    width=r.right - r.left,
                    height=r.bottom - r.top,
                    primary=bool(mi.dwFlags & MONITORINFOF_PRIMARY),
                    dpi=dpi,
                )
            )
        return True

    user32.EnumDisplayMonitors(None, None, _MONITORENUMPROC(cb), 0)
    return result


# ---- window styles -------------------------------------------------------
def add_ex_styles(hwnd: int, styles: int) -> None:
    cur = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, cur | styles)


def make_click_through(hwnd: int) -> None:
    add_ex_styles(hwnd, WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)


def make_tool_noactivate(hwnd: int) -> None:
    add_ex_styles(hwnd, WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)


def exclude_from_capture(hwnd: int) -> bool:
    if not _HAS_DISPLAY_AFFINITY:
        return False
    if os.environ.get("FRAMER_NO_CAPTURE_EXCLUSION"):  # debug aid: lets screenshots show Framer's own windows
        return False
    try:
        ok = bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
        if not ok:
            log.debug("SetWindowDisplayAffinity failed: %s", ctypes.get_last_error())
        return ok
    except Exception as exc:  # pragma: no cover
        log.debug("SetWindowDisplayAffinity raised: %s", exc)
        return False


def set_window_pos_physical(hwnd: int, left: int, top: int, width: int, height: int, topmost: bool = True) -> None:
    """Position a window in physical pixels (process is PerMonitorV2-aware, so this is exact)."""
    flags = SWP_NOACTIVATE | SWP_SHOWWINDOW
    insert_after = HWND_TOPMOST if topmost else 0
    if not topmost:
        flags |= SWP_NOZORDER
    user32.SetWindowPos(hwnd, insert_after, int(left), int(top), int(width), int(height), flags)


# ---- hotkeys -------------------------------------------------------------
def register_hotkey(hwnd: int, hk_id: int, modifiers: int, vk: int) -> bool:
    ok = bool(user32.RegisterHotKey(hwnd, hk_id, modifiers | MOD_NOREPEAT, vk))
    if not ok:
        log.info("RegisterHotKey(id=%s mods=%#x vk=%#x) failed: %s", hk_id, modifiers, vk, ctypes.get_last_error())
    return ok


def unregister_hotkey(hwnd: int, hk_id: int) -> bool:
    return bool(user32.UnregisterHotKey(hwnd, hk_id))


# ---- foreground window ---------------------------------------------------
def get_foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow() or 0)


def set_foreground(hwnd: int) -> None:
    if hwnd:
        try:
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass


def get_window_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def get_foreground_title() -> str:
    return get_window_title(get_foreground_hwnd())


# ---- app identity / single instance -------------------------------------
def set_app_user_model_id(app_id: str) -> None:
    if shell32 is None:
        return
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
        shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as exc:  # pragma: no cover
        log.debug("SetCurrentProcessExplicitAppUserModelID failed: %s", exc)


_mutex_handle: int | None = None


def acquire_single_instance_mutex(name: str) -> bool:
    """Returns True if we are the first instance."""
    global _mutex_handle
    handle = kernel32.CreateMutexW(None, True, name)
    err = ctypes.get_last_error()
    if not handle:
        return True  # cannot tell; let it run
    _mutex_handle = handle
    if err == ERROR_ALREADY_EXISTS:
        return False
    atexit.register(release_single_instance_mutex)
    return True


def release_single_instance_mutex() -> None:
    global _mutex_handle
    if _mutex_handle:
        try:
            kernel32.ReleaseMutex(_mutex_handle)
            kernel32.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None


# ---- virtual-key table ---------------------------------------------------
VK_TABLE: dict[str, int] = {}
for _i in range(1, 25):
    VK_TABLE[f"F{_i}"] = 0x6F + _i  # F1 = 0x70
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    VK_TABLE[_c] = ord(_c)
for _d in "0123456789":
    VK_TABLE[_d] = ord(_d)
for _n in range(10):
    VK_TABLE[f"Num{_n}"] = 0x60 + _n
VK_TABLE.update(
    {
        "NumMultiply": 0x6A,
        "NumAdd": 0x6B,
        "NumSubtract": 0x6D,
        "NumDecimal": 0x6E,
        "NumDivide": 0x6F,
        "Insert": 0x2D,
        "Delete": 0x2E,
        "Home": 0x24,
        "End": 0x23,
        "PageUp": 0x21,
        "PageDown": 0x22,
        "Pause": 0x13,
        "ScrollLock": 0x91,
        "PrintScreen": 0x2C,
        "Space": 0x20,
    }
)
VK_TO_NAME: dict[int, str] = {v: k for k, v in VK_TABLE.items()}

MODIFIER_FLAGS = {"Ctrl": MOD_CONTROL, "Alt": MOD_ALT, "Shift": MOD_SHIFT, "Win": MOD_WIN}
