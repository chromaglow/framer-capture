"""Settings: load / validate / save (atomic) to %APPDATA%/Framer/settings.json."""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SETTINGS_VERSION = 1


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Framer"


def default_output_folder() -> str:
    return str(Path(os.environ.get("USERPROFILE") or Path.home()) / "Pictures" / "Framer")


def default_settings() -> dict[str, Any]:
    return {
        "version": SETTINGS_VERSION,
        "output_folder": default_output_folder(),
        "prefix": "Capture",
        "digits": 4,
        "format": "png",
        "jpg_quality": 95,
        "sound": True,
        "duplicate_guard": True,
        "remember_frame": True,
        "hotkeys": {
            "set_frame": {"modifiers": [], "key": "F8"},
            "capture": {"modifiers": [], "key": "F9"},
        },
        "last_frame": None,
        "bar_offset": None,
        "setup_window_pos": None,
    }


_VALID_MODIFIERS = {"Ctrl", "Alt", "Shift", "Win"}


def _validate_hotkey(value: Any, fallback: dict) -> dict:
    if not isinstance(value, dict):
        return copy.deepcopy(fallback)
    key = value.get("key")
    mods = value.get("modifiers", [])
    if not isinstance(key, str) or not key:
        return copy.deepcopy(fallback)
    if not isinstance(mods, list):
        mods = []
    mods = [m for m in mods if m in _VALID_MODIFIERS]
    # de-duplicate, keep canonical order
    mods = [m for m in ("Ctrl", "Alt", "Shift", "Win") if m in mods]
    return {"modifiers": mods, "key": key}


def _validate_last_frame(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    try:
        lf = {
            "left": int(value["left"]),
            "top": int(value["top"]),
            "width": int(value["width"]),
            "height": int(value["height"]),
            "monitor_device": str(value["monitor_device"]),
            "monitor_rect": [int(v) for v in value["monitor_rect"]],
        }
    except (KeyError, TypeError, ValueError):
        return None
    if lf["width"] < 16 or lf["height"] < 16 or len(lf["monitor_rect"]) != 4:
        return None
    return lf


def _validate_pair(value: Any) -> list[int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return [int(value[0]), int(value[1])]
        except (TypeError, ValueError):
            return None
    return None


def validate(data: Any) -> dict[str, Any]:
    """Return a complete, well-typed settings dict, repairing anything odd."""
    d = default_settings()
    if not isinstance(data, dict):
        return d
    out = d
    if isinstance(data.get("output_folder"), str) and data["output_folder"].strip():
        out["output_folder"] = data["output_folder"]
    from .naming import sanitize_prefix

    if isinstance(data.get("prefix"), str):
        p = sanitize_prefix(data["prefix"])
        if p:
            out["prefix"] = p
    if isinstance(data.get("digits"), int) and 3 <= data["digits"] <= 6:
        out["digits"] = data["digits"]
    if data.get("format") in ("png", "jpg"):
        out["format"] = data["format"]
    if isinstance(data.get("jpg_quality"), int) and 80 <= data["jpg_quality"] <= 100:
        out["jpg_quality"] = data["jpg_quality"]
    for key in ("sound", "duplicate_guard", "remember_frame"):
        if isinstance(data.get(key), bool):
            out[key] = data[key]
    hk = data.get("hotkeys") if isinstance(data.get("hotkeys"), dict) else {}
    out["hotkeys"] = {
        "set_frame": _validate_hotkey(hk.get("set_frame"), d["hotkeys"]["set_frame"]),
        "capture": _validate_hotkey(hk.get("capture"), d["hotkeys"]["capture"]),
    }
    out["last_frame"] = _validate_last_frame(data.get("last_frame"))
    out["bar_offset"] = _validate_pair(data.get("bar_offset"))
    out["setup_window_pos"] = _validate_pair(data.get("setup_window_pos"))
    return out


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    os.replace(tmp, path)


class Settings:
    """Dict-like settings object that persists atomically on every save()."""

    def __init__(self, path: Path | None = None):
        self.path = path or (app_data_dir() / "settings.json")
        self.data: dict[str, Any] = default_settings()

    def load(self) -> "Settings":
        raw: Any = None
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Settings unreadable (%s); using defaults", exc)
            raw = None
        self.data = validate(raw)
        if raw is None or self.data != raw:
            # missing/corrupt/partial -> rewrite a clean file
            try:
                self.save()
            except OSError as exc:
                log.warning("Could not rewrite settings: %s", exc)
        return self

    def save(self) -> None:
        atomic_write_text(self.path, json.dumps(self.data, indent=2, ensure_ascii=False))

    # convenience accessors
    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()

    @property
    def extension(self) -> str:
        return "png" if self.data["format"] == "png" else "jpg"
