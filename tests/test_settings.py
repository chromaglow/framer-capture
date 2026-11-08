import json
import os

from framer.settings import Settings, atomic_write_text, default_settings, validate


def test_defaults(tmp_path):
    s = Settings(tmp_path / "settings.json").load()
    d = default_settings()
    assert s.data == d
    assert s["prefix"] == "Capture"
    assert s["digits"] == 4
    assert s["format"] == "png"
    assert s["hotkeys"]["set_frame"] == {"modifiers": [], "key": "F8"}
    assert s["hotkeys"]["capture"] == {"modifiers": [], "key": "F9"}
    assert s["last_frame"] is None
    # a clean file was written
    assert (tmp_path / "settings.json").exists()
    assert json.loads((tmp_path / "settings.json").read_text("utf-8")) == d


def test_corrupt_file_recovers(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ this is not json", encoding="utf-8")
    s = Settings(p).load()
    assert s.data == default_settings()
    assert json.loads(p.read_text("utf-8")) == default_settings()


def test_partial_and_bad_values_repaired(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "prefix": 'Bad/Name?',
        "digits": 12,
        "format": "gif",
        "jpg_quality": 10,
        "sound": "yes",
        "hotkeys": {"capture": {"modifiers": ["Hyper", "Ctrl"], "key": "F10"}},
        "last_frame": {"left": 1, "top": 2, "width": 3, "height": 4, "monitor_device": "x", "monitor_rect": [0, 0, 1, 1]},
        "bar_offset": [12, "x"],
    }), encoding="utf-8")
    s = Settings(p).load()
    assert s["prefix"] == "Bad_Name_"
    assert s["digits"] == 4
    assert s["format"] == "png"
    assert s["jpg_quality"] == 95
    assert s["sound"] is True
    assert s["hotkeys"]["capture"] == {"modifiers": ["Ctrl"], "key": "F10"}
    assert s["hotkeys"]["set_frame"] == {"modifiers": [], "key": "F8"}
    assert s["last_frame"] is None  # too small
    assert s["bar_offset"] is None


def test_valid_values_kept(tmp_path):
    p = tmp_path / "settings.json"
    data = default_settings()
    data.update({
        "output_folder": "D:\\Scans",
        "prefix": "ID3 (2001) v1.0",
        "digits": 6,
        "format": "jpg",
        "jpg_quality": 88,
        "duplicate_guard": False,
        "last_frame": {"left": 10, "top": 20, "width": 300, "height": 400,
                       "monitor_device": "\\\\.\\DISPLAY1", "monitor_rect": [0, 0, 3840, 2160]},
        "bar_offset": [820, 0],
        "setup_window_pos": [100, 100],
    })
    p.write_text(json.dumps(data), encoding="utf-8")
    s = Settings(p).load()
    assert s.data == data
    assert s.extension == "jpg"


def test_atomic_write(tmp_path):
    p = tmp_path / "sub" / "settings.json"
    atomic_write_text(p, "hello")
    assert p.read_text("utf-8") == "hello"
    assert not p.with_name(p.name + ".part").exists()
    atomic_write_text(p, "world")
    assert p.read_text("utf-8") == "world"
    assert os.listdir(p.parent) == ["settings.json"]


def test_set_saves(tmp_path):
    p = tmp_path / "settings.json"
    s = Settings(p).load()
    s.set("prefix", "Page")
    assert json.loads(p.read_text("utf-8"))["prefix"] == "Page"


def test_validate_non_dict():
    assert validate(None) == default_settings()
    assert validate([1, 2]) == default_settings()
    assert validate("x") == default_settings()
