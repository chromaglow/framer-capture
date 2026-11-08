"""Make PDF: collect images, natural sort, flatten alpha, build losslessly with img2pdf."""
from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Callable, Iterable

import img2pdf
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from . import naming

log = logging.getLogger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
_NUM = re.compile(r"(\d+)")


def natural_key(name: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in _NUM.split(os.path.basename(name))]


def collect_files(folder: str | os.PathLike, prefix: str | None) -> list[str]:
    """prefix given: files matching prefix_NNNN.* sorted by number; None: all images, natural sort."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if prefix is not None:
        pat = naming.prefix_pattern(prefix)
        matched = [(int(pat.match(p.name).group(1)), p) for p in files if pat.match(p.name)]
        matched.sort(key=lambda t: (t[0], t[1].name.lower()))
        return [str(p) for _n, p in matched]
    files.sort(key=lambda p: natural_key(p.name))
    return [str(p) for p in files]


def unique_pdf_name(folder: str | os.PathLike, base: str) -> Path:
    """<base>.pdf, else <base> (2).pdf, (3)... never overwrites."""
    folder = Path(folder)
    cand = folder / f"{base}.pdf"
    n = 2
    while cand.exists():
        cand = folder / f"{base} ({n}).pdf"
        n += 1
    return cand


def has_alpha(path: str) -> bool:
    try:
        with Image.open(path) as im:
            return im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info) or "transparency" in im.info
    except Exception:
        return False


def flatten_to_white(path: str, out_dir: str) -> str:
    with Image.open(path) as im:
        dpi = im.info.get("dpi", (300, 300))
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        out = Path(out_dir) / (Path(path).stem + "_flat.png")
        bg.save(out, format="PNG", compress_level=1, dpi=dpi)
        return str(out)


def build_pdf(files: Iterable[str], out_path: str | os.PathLike, progress: Callable[[int, int], None] | None = None) -> int:
    """Write a PDF with one image per page (lossless). Returns the page count."""
    files = list(files)
    if not files:
        raise ValueError("No images to put in the PDF")
    out_path = Path(out_path)
    with tempfile.TemporaryDirectory(prefix="framer_pdf_") as tmp:
        prepared: list[str] = []
        for i, f in enumerate(files):
            prepared.append(flatten_to_white(f, tmp) if has_alpha(f) else f)
            if progress:
                progress(i + 1, len(files) + 1)
        data = img2pdf.convert(prepared, rotation=img2pdf.Rotation.ifvalid)
        tmp_out = out_path.with_name(out_path.name + ".part")
        tmp_out.write_bytes(data)
        os.replace(tmp_out, out_path)
        if progress:
            progress(len(files) + 1, len(files) + 1)
    return len(files)


_PAGE_RE = re.compile(rb"/Type\s*/Page(?![s/])")


def count_pdf_pages(path: str | os.PathLike) -> int:
    data = Path(path).read_bytes()
    return len(_PAGE_RE.findall(data))


# ---- dialog ----------------------------------------------------------------------
class _Worker(QThread):
    progress = Signal(int, int)
    done = Signal(str, int)
    failed = Signal(str)

    def __init__(self, files: list[str], out_path: str) -> None:
        super().__init__()
        self.files, self.out_path = files, out_path

    def run(self) -> None:
        try:
            n = build_pdf(self.files, self.out_path, lambda a, b: self.progress.emit(a, b))
            self.done.emit(self.out_path, n)
        except Exception as exc:
            log.exception("PDF build failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class PdfDialog(QDialog):
    created = Signal(str, int)  # path, pages

    def __init__(self, folder: str, prefix: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Make PDF")
        self.setModal(False)
        self.folder, self.prefix = folder, prefix
        self._worker: _Worker | None = None
        self._result_path: str | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        self.rb_prefix = QRadioButton(f'All files with prefix "{prefix}"')
        self.rb_all = QRadioButton("All images in folder")
        self.rb_prefix.setChecked(True)
        v.addWidget(self.rb_prefix)
        v.addWidget(self.rb_all)
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("muted")
        v.addWidget(self.lbl_count)
        row = QHBoxLayout()
        row.addWidget(QLabel("Output name"))
        self.ed_name = QLineEdit()
        row.addWidget(self.ed_name, 1)
        row.addWidget(QLabel(".pdf"))
        v.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        v.addWidget(self.progress)
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        v.addWidget(self.lbl_status)
        brow = QHBoxLayout()
        self.btn_open = QPushButton("Open PDF")
        self.btn_open.setEnabled(False)
        self.btn_close = QPushButton("Close")
        self.btn_create = QPushButton("Create PDF")
        self.btn_create.setObjectName("primary")
        brow.addWidget(self.btn_open)
        brow.addStretch(1)
        brow.addWidget(self.btn_close)
        brow.addWidget(self.btn_create)
        v.addLayout(brow)
        self.rb_prefix.toggled.connect(self._refresh)
        self.btn_create.clicked.connect(self._create)
        self.btn_close.clicked.connect(self.close)
        self.btn_open.clicked.connect(self._open)
        self.setFixedWidth(420)
        self._refresh()

    def _files(self) -> list[str]:
        return collect_files(self.folder, self.prefix if self.rb_prefix.isChecked() else None)

    def _refresh(self) -> None:
        files = self._files()
        self.lbl_count.setText(f"{len(files)} image(s) found" if files else "No images found")
        base = self.prefix if self.rb_prefix.isChecked() else (Path(self.folder).name or "Images")
        self.ed_name.setText(unique_pdf_name(self.folder, base).stem)
        self.btn_create.setEnabled(bool(files))

    def _create(self) -> None:
        files = self._files()
        if not files:
            return
        base = naming.sanitize_prefix(self.ed_name.text()) or self.prefix
        out = unique_pdf_name(self.folder, base)
        self.ed_name.setText(out.stem)
        self.btn_create.setEnabled(False)
        self.rb_prefix.setEnabled(False)
        self.rb_all.setEnabled(False)
        self.lbl_status.setText("Building…")
        self._worker = _Worker(files, str(out))
        self._worker.progress.connect(lambda a, b: self.progress.setValue(int(a * 100 / max(1, b))))
        self._worker.done.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _done(self, path: str, pages: int) -> None:
        self._result_path = path
        self.lbl_status.setText(f"Created {Path(path).name} ({pages} pages)")
        self.btn_open.setEnabled(True)
        self.btn_create.setEnabled(True)
        self.rb_prefix.setEnabled(True)
        self.rb_all.setEnabled(True)
        self.created.emit(path, pages)
        self._refresh_name_only()

    def _refresh_name_only(self) -> None:
        base = self.prefix if self.rb_prefix.isChecked() else (Path(self.folder).name or "Images")
        self.ed_name.setText(unique_pdf_name(self.folder, base).stem)

    def _failed(self, msg: str) -> None:
        self.lbl_status.setText(f"Could not create the PDF: {msg}")
        self.btn_create.setEnabled(True)
        self.rb_prefix.setEnabled(True)
        self.rb_all.setEnabled(True)

    def _open(self) -> None:
        if self._result_path:
            try:
                os.startfile(self._result_path)  # type: ignore[attr-defined]
            except OSError as exc:
                self.lbl_status.setText(f"Could not open: {exc}")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
        super().closeEvent(event)
