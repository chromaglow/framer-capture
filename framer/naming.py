"""Prefix sanitizing, folder numbering scan, next-free-name. Pure functions (unit tested)."""
from __future__ import annotations

import os
import re
from pathlib import Path

_ILLEGAL = re.compile(r'[\\/:*?"<>|]|[\x00-\x1f\x7f]')
MAX_PREFIX_LEN = 80
IMAGE_EXTS = ("png", "jpg", "jpeg")


def sanitize_prefix(text: str) -> str:
    """Strip, replace illegal filename characters with '_', cap at 80 chars."""
    if text is None:
        return ""
    cleaned = _ILLEGAL.sub("_", text).strip()
    cleaned = cleaned[:MAX_PREFIX_LEN].rstrip()
    # Avoid trailing dots (Windows strips them silently)
    cleaned = cleaned.rstrip(".").rstrip()
    return cleaned


def prefix_pattern(prefix: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(prefix)}_(\d+)\.(png|jpe?g)$", re.IGNORECASE)


def scan_numbers(folder: str | os.PathLike, prefix: str) -> list[int]:
    """All numbers used by files matching prefix_NNNN.(png|jpg|jpeg) in folder."""
    pat = prefix_pattern(prefix)
    found: list[int] = []
    try:
        with os.scandir(folder) as it:
            for entry in it:
                m = pat.match(entry.name)
                if m:
                    try:
                        found.append(int(m.group(1)))
                    except ValueError:
                        pass
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return []
    return found


def next_number(folder: str | os.PathLike, prefix: str, user_number: int | None = None) -> int:
    """max(found)+1 or 1; a user-chosen higher number is respected."""
    found = scan_numbers(folder, prefix)
    n = (max(found) + 1) if found else 1
    if user_number is not None and user_number > n:
        n = user_number
    return max(1, n)


def format_name(prefix: str, number: int, digits: int, ext: str) -> str:
    digits = min(6, max(3, int(digits)))
    return f"{prefix}_{number:0{digits}d}.{ext}"


def number_exists(folder: str | os.PathLike, prefix: str, number: int) -> bool:
    """True if any image with this prefix and number exists (any extension, any digit width)."""
    return number in set(scan_numbers(folder, prefix))


def next_free_name(
    folder: str | os.PathLike, prefix: str, start_number: int, digits: int, ext: str
) -> tuple[str, int, bool]:
    """Return (filename, number, skipped) where the file does not yet exist in folder.

    Never overwrites: if the candidate exists (in any image extension), increment until free.
    """
    used = set(scan_numbers(folder, prefix))
    n = max(1, int(start_number))
    skipped = False
    while True:
        name = format_name(prefix, n, digits, ext)
        if n not in used and not Path(folder, name).exists() and not Path(folder, name + ".part").exists():
            return name, n, skipped
        n += 1
        skipped = True


def parse_number(filename: str, prefix: str) -> int | None:
    m = prefix_pattern(prefix).match(os.path.basename(filename))
    return int(m.group(1)) if m else None
