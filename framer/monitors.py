"""Win32 monitor enumeration + QScreen matching -> list[geometry.Monitor]."""
from __future__ import annotations

import logging

from PySide6.QtGui import QGuiApplication, QScreen

from . import win32
from .geometry import Monitor, RawMonitor, Rect, ScreenInfo, match_screens

log = logging.getLogger(__name__)


class MonitorTable:
    def __init__(self) -> None:
        self.monitors: list[Monitor] = []
        self._screens: dict[str, QScreen] = {}
        self.used_fallback = False
        self.match_method = "name"
        self.rebuild()

    def rebuild(self) -> None:
        raw = [
            RawMonitor(m.device, Rect(m.left, m.top, m.width, m.height), m.primary)
            for m in win32.enumerate_monitors()
        ]
        qscreens = QGuiApplication.screens()
        infos = []
        for i, s in enumerate(qscreens):
            g = s.geometry()
            infos.append(ScreenInfo(s.name(), Rect(g.x(), g.y(), g.width(), g.height()), i, float(s.devicePixelRatio())))
        monitors, method = match_screens(raw, infos)
        self.match_method = method
        self.used_fallback = method == "order"
        if method != "name":
            log.log(
                logging.WARNING if method == "order" else logging.INFO,
                "QScreen names did not match Win32 device names; matched by %s. win32=%s qt=%s",
                method, [r.device for r in raw], [s.name for s in infos],
            )
        # map device -> QScreen through the matched logical rect
        self._screens = {}
        for m in monitors:
            for s in qscreens:
                g = s.geometry()
                if Rect(g.x(), g.y(), g.width(), g.height()) == m.logical and s not in self._screens.values():
                    self._screens[m.device] = s
                    break
        self.monitors = monitors
        log.info("Monitors: %s", [(m.device, m.phys.as_tuple(), m.logical.as_tuple(), round(m.scale, 3)) for m in monitors])

    def screen_for(self, mon: Monitor) -> QScreen | None:
        return self._screens.get(mon.device)

    def monitor_for_screen(self, screen: QScreen) -> Monitor | None:
        for dev, s in self._screens.items():
            if s is screen or s.name() == screen.name():
                for m in self.monitors:
                    if m.device == dev:
                        return m
        return None

    def all_matched(self) -> bool:
        return len(self.monitors) == len(QGuiApplication.screens()) and len(self.monitors) >= 1

    def by_device(self, device: str) -> Monitor | None:
        for m in self.monitors:
            if m.device == device:
                return m
        return None

    def primary(self) -> Monitor | None:
        for m in self.monitors:
            if m.primary:
                return m
        return self.monitors[0] if self.monitors else None
