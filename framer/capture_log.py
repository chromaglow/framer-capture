"""framer_log.csv in the output folder: UTF-8 with BOM, header on create, append rows."""
from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

LOG_FILENAME = "framer_log.csv"
COLUMNS = [
    "timestamp_iso",
    "filename",
    "width_px",
    "height_px",
    "frame_left",
    "frame_top",
    "monitor",
    "source_window_title",
    "duplicate_override",
    "note",
]


def log_path(folder: str | os.PathLike) -> Path:
    return Path(folder) / LOG_FILENAME


def _ensure_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerow(COLUMNS)


def append_row(
    folder: str | os.PathLike,
    filename: str,
    width: int,
    height: int,
    frame_left: int,
    frame_top: int,
    monitor: str,
    source_window_title: str = "",
    duplicate_override: bool = False,
    note: str = "",
    timestamp: datetime | None = None,
) -> bool:
    path = log_path(folder)
    ts = (timestamp or datetime.now()).astimezone().isoformat(timespec="seconds")
    row = [
        ts,
        filename,
        int(width),
        int(height),
        int(frame_left),
        int(frame_top),
        monitor,
        (source_window_title or "").replace("\r", " ").replace("\n", " "),
        "yes" if duplicate_override else "",
        note,
    ]
    try:
        _ensure_header(path)
        with open(path, "a", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerow(row)
        return True
    except OSError as exc:
        log.warning("Could not append to %s: %s", path, exc)
        return False


def append_undo_row(folder: str | os.PathLike, filename: str, width: int, height: int,
                    frame_left: int, frame_top: int, monitor: str) -> bool:
    return append_row(
        folder, filename, width, height, frame_left, frame_top, monitor,
        note="undone (moved to Recycle Bin)",
    )


def read_rows(folder: str | os.PathLike) -> list[dict[str, str]]:
    path = log_path(folder)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))
