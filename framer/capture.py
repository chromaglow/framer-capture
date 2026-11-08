"""mss capture, duplicate guard, ordered save queue (single worker thread)."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import mss
import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage

from . import capture_log, naming
from .geometry import Rect

log = logging.getLogger(__name__)

DUPLICATE_THRESHOLD = 1.0
THUMB_SIZE = 112


# ---- pure helpers (unit tested) --------------------------------------------
def to_gray64(img: Image.Image) -> np.ndarray:
    """64x64 grayscale float array for duplicate comparison."""
    g = img.convert("L").resize((64, 64), Image.Resampling.BOX)
    return np.asarray(g, dtype=np.float32)


def duplicate_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def is_duplicate(a: np.ndarray | None, b: np.ndarray | None, threshold: float = DUPLICATE_THRESHOLD) -> bool:
    if a is None or b is None or a.shape != b.shape:
        return False
    return duplicate_distance(a, b) < threshold


def is_black(img: Image.Image) -> bool:
    extrema = img.getextrema()
    if isinstance(extrema[0], tuple):
        return all(hi == 0 for _lo, hi in extrema)
    return extrema[1] == 0


def save_image_atomic(img: Image.Image, path: Path, fmt: str, quality: int = 95) -> None:
    """PNG (compress 6) or JPG (quality, 4:4:4, optimize) with a 300 DPI tag; .part then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    try:
        if fmt == "jpg":
            img.convert("RGB").save(tmp, format="JPEG", quality=int(quality), subsampling=0, optimize=True, dpi=(300, 300))
        else:
            img.save(tmp, format="PNG", compress_level=6, dpi=(300, 300))
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def shot_to_image(shot) -> Image.Image:
    return Image.frombytes("RGB", (shot.width, shot.height), shot.bgra, "raw", "BGRX")


# ---- data ---------------------------------------------------------------------
@dataclass
class SaveJob:
    image: Image.Image
    folder: str
    prefix: str
    start_number: int
    digits: int
    fmt: str
    quality: int
    frame: Rect
    monitor: str
    source_title: str
    duplicate_override: bool = False
    submitted_at: float = field(default_factory=time.monotonic)


@dataclass
class SaveResult:
    path: str
    filename: str
    number: int
    width: int
    height: int
    thumbnail: QImage
    skipped: bool
    frame: Rect
    monitor: str


class _Signals(QObject):
    saved = Signal(object)  # SaveResult
    failed = Signal(str)


class _SaveRunnable(QRunnable):
    def __init__(self, job: SaveJob, signals: _Signals) -> None:
        super().__init__()
        self.job = job
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        j = self.job
        try:
            folder = Path(j.folder)
            folder.mkdir(parents=True, exist_ok=True)
            name, number, skipped = naming.next_free_name(folder, j.prefix, j.start_number, j.digits, j.fmt)
            path = folder / name
            save_image_atomic(j.image, path, j.fmt, j.quality)
            note = "number skipped: target existed" if skipped else ""
            capture_log.append_row(
                folder, name, j.image.width, j.image.height, j.frame.left, j.frame.top, j.monitor,
                j.source_title, j.duplicate_override, note,
            )
            thumb = j.image.copy()
            thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            thumb = thumb.convert("RGBA")
            qimg = QImage(thumb.tobytes("raw", "RGBA"), thumb.width, thumb.height, thumb.width * 4, QImage.Format.Format_RGBA8888).copy()
            self.signals.saved.emit(
                SaveResult(str(path), name, number, j.image.width, j.image.height, qimg, skipped, j.frame, j.monitor)
            )
        except Exception as exc:
            log.exception("Save failed")
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class CaptureEngine(QObject):
    """Grab on the main thread; encode + write on one worker so saves land in order."""

    saved = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._sct: mss.base.MSSBase | None = None
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._signals = _Signals()
        self._signals.saved.connect(self.saved)
        self._signals.failed.connect(self.failed)
        self.pending = 0
        self._signals.saved.connect(lambda _r: self._dec())
        self._signals.failed.connect(lambda _m: self._dec())

    def _dec(self) -> None:
        self.pending = max(0, self.pending - 1)

    def _mss(self) -> mss.base.MSSBase:
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def grab(self, rect: Rect) -> Image.Image:
        """Physical-pixel grab. Raises on failure. Output size == rect size exactly."""
        try:
            shot = self._mss().grab({"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height})
        except Exception:
            # mss handles can go stale after display changes: recreate once
            self.close()
            shot = self._mss().grab({"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height})
        img = shot_to_image(shot)
        if img.size != (rect.width, rect.height):
            img = img.crop((0, 0, rect.width, rect.height)) if img.width >= rect.width and img.height >= rect.height else img
            if img.size != (rect.width, rect.height):
                raise RuntimeError(f"Capture size mismatch: got {img.size}, wanted {(rect.width, rect.height)}")
        return img

    def submit(self, job: SaveJob) -> None:
        self.pending += 1
        self._pool.start(_SaveRunnable(job, self._signals))

    def wait(self, ms: int = 10000) -> bool:
        return self._pool.waitForDone(ms)

    def close(self) -> None:
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
