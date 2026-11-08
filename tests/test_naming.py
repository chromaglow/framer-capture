from pathlib import Path

from framer.naming import (
    format_name,
    next_free_name,
    next_number,
    number_exists,
    parse_number,
    sanitize_prefix,
    scan_numbers,
)


def touch(folder: Path, name: str):
    (folder / name).write_bytes(b"x")


def test_sanitize_prefix():
    assert sanitize_prefix("  Capture  ") == "Capture"
    assert sanitize_prefix('a\\b/c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"
    assert sanitize_prefix("tab\there\x01x") == "tab_here_x"
    assert sanitize_prefix("") == ""
    assert sanitize_prefix("   ") == ""
    assert sanitize_prefix("x" * 100) == "x" * 80
    assert sanitize_prefix("ID3 (2001) v1.0") == "ID3 (2001) v1.0"
    assert sanitize_prefix("ends with dot.") == "ends with dot"


def test_scan_with_gaps(tmp_path):
    for n in (1, 2, 7):
        touch(tmp_path, f"Capture_{n:04d}.png")
    assert sorted(scan_numbers(tmp_path, "Capture")) == [1, 2, 7]
    assert next_number(tmp_path, "Capture") == 8
    assert next_free_name(tmp_path, "Capture", 8, 4, "png") == ("Capture_0008.png", 8, False)


def test_scan_case_insensitive_and_extensions(tmp_path):
    touch(tmp_path, "capture_0003.PNG")
    touch(tmp_path, "CAPTURE_0005.jpeg")
    touch(tmp_path, "Capture_0004.JPG")
    touch(tmp_path, "Capture_0009.txt")  # ignored
    touch(tmp_path, "Capture-0010.png")  # ignored (wrong separator)
    touch(tmp_path, "Captured_0011.png")  # ignored (different prefix)
    assert sorted(scan_numbers(tmp_path, "Capture")) == [3, 4, 5]
    assert next_number(tmp_path, "Capture") == 6


def test_prefix_with_regex_characters(tmp_path):
    prefix = "ID3 (2001) v1.0"
    touch(tmp_path, f"{prefix}_0001.png")
    touch(tmp_path, "ID3 (2001) v1x0_0002.png")  # '.' must not act as a wildcard
    assert scan_numbers(tmp_path, prefix) == [1]
    assert next_number(tmp_path, prefix) == 2
    assert parse_number(f"{prefix}_0042.png", prefix) == 42
    assert parse_number("ID3 (2001) v1x0_0042.png", prefix) is None


def test_empty_or_missing_folder(tmp_path):
    assert scan_numbers(tmp_path / "nope", "Capture") == []
    assert next_number(tmp_path, "Capture") == 1
    assert next_number(tmp_path, "Capture", user_number=12) == 12


def test_user_number_respected_only_if_higher(tmp_path):
    touch(tmp_path, "Capture_0010.png")
    assert next_number(tmp_path, "Capture", user_number=5) == 11
    assert next_number(tmp_path, "Capture", user_number=20) == 20


def test_never_overwrite(tmp_path):
    touch(tmp_path, "Capture_0005.png")
    touch(tmp_path, "Capture_0006.jpg")  # other extension still blocks the number
    touch(tmp_path, "Capture_0007.png.part")  # in-flight write blocks too
    name, n, skipped = next_free_name(tmp_path, "Capture", 5, 4, "png")
    assert (name, n, skipped) == ("Capture_0008.png", 8, True)
    assert number_exists(tmp_path, "Capture", 5)
    assert not number_exists(tmp_path, "Capture", 8)


def test_digits_3_to_6():
    assert format_name("P", 7, 3, "png") == "P_007.png"
    assert format_name("P", 7, 4, "png") == "P_0007.png"
    assert format_name("P", 7, 5, "jpg") == "P_00007.jpg"
    assert format_name("P", 7, 6, "png") == "P_000007.png"
    assert format_name("P", 1234567, 4, "png") == "P_1234567.png"  # wider than digits: no truncation
    assert format_name("P", 7, 2, "png") == "P_007.png"  # clamped to 3
    assert format_name("P", 7, 9, "png") == "P_000007.png"  # clamped to 6


def test_scan_accepts_other_digit_widths(tmp_path):
    touch(tmp_path, "Capture_1.png")
    touch(tmp_path, "Capture_000012.png")
    assert sorted(scan_numbers(tmp_path, "Capture")) == [1, 12]
    assert next_number(tmp_path, "Capture") == 13
