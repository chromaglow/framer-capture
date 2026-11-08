from datetime import datetime

from framer.capture_log import COLUMNS, append_row, append_undo_row, log_path, read_rows


def test_header_created_with_bom(tmp_path):
    assert append_row(tmp_path, "Capture_0001.png", 200, 100, 10, 20, r"\\.\DISPLAY1", "Doc - Viewer")
    raw = log_path(tmp_path).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == ",".join(COLUMNS)
    assert len(lines) == 2
    assert lines[1].startswith("20")  # ISO timestamp
    assert "Capture_0001.png,200,100,10,20," in lines[1]


def test_append_does_not_repeat_header_or_bom(tmp_path):
    append_row(tmp_path, "A_0001.png", 1, 1, 0, 0, "m")
    append_row(tmp_path, "A_0002.png", 1, 1, 0, 0, "m", duplicate_override=True)
    raw = log_path(tmp_path).read_bytes()
    assert raw.count(b"\xef\xbb\xbf") == 1
    rows = read_rows(tmp_path)
    assert [r["filename"] for r in rows] == ["A_0001.png", "A_0002.png"]
    assert rows[0]["duplicate_override"] == ""
    assert rows[1]["duplicate_override"] == "yes"


def test_undo_row(tmp_path):
    append_row(tmp_path, "A_0001.png", 5, 6, 7, 8, "m", "Title")
    append_undo_row(tmp_path, "A_0001.png", 5, 6, 7, 8, "m")
    rows = read_rows(tmp_path)
    assert len(rows) == 2
    assert rows[0]["note"] == ""
    assert rows[1]["filename"] == "A_0001.png"
    assert rows[1]["note"] == "undone (moved to Recycle Bin)"


def test_timestamp_and_title_sanitizing(tmp_path):
    ts = datetime(2026, 11, 8, 9, 30, 15)
    append_row(tmp_path, "A_0001.png", 1, 1, 0, 0, "m", "line1\nline2", timestamp=ts)
    row = read_rows(tmp_path)[0]
    assert row["timestamp_iso"].startswith("2026-11-08T09:30:15")
    assert row["source_window_title"] == "line1 line2"


def test_missing_folder_is_created(tmp_path):
    folder = tmp_path / "deep" / "er"
    assert append_row(folder, "A_0001.png", 1, 1, 0, 0, "m")
    assert log_path(folder).exists()
