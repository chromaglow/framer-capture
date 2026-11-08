from pathlib import Path

from PIL import Image

from framer.pdf import build_pdf, collect_files, count_pdf_pages, has_alpha, natural_key, unique_pdf_name


def make(folder: Path, name: str, mode="RGB", size=(120, 80), color=None):
    color = color or ((255, 0, 0) if mode == "RGB" else (255, 0, 0, 128))
    Image.new(mode, size, color).save(folder / name, dpi=(300, 300))
    return folder / name


def test_natural_sort_all_images(tmp_path):
    for n in ("img10.png", "img2.png", "img1.png", "other_0003.jpg", "Other_0002.JPG", "notes.txt"):
        make(tmp_path, n) if not n.endswith(".txt") else (tmp_path / n).write_text("x")
    files = [Path(f).name for f in collect_files(tmp_path, None)]
    assert files == ["img1.png", "img2.png", "img10.png", "Other_0002.JPG", "other_0003.jpg"]
    assert natural_key("a10b2") == ["a", 10, "b", 2, ""]


def test_prefix_files_sorted_by_number(tmp_path):
    for n in ("Capture_0010.png", "Capture_0002.png", "Capture_0001.jpg", "Captures_0001.png", "Capture_x.png"):
        make(tmp_path, n)
    files = [Path(f).name for f in collect_files(tmp_path, "Capture")]
    assert files == ["Capture_0001.jpg", "Capture_0002.png", "Capture_0010.png"]
    assert collect_files(tmp_path / "missing", "Capture") == []


def test_unique_pdf_name(tmp_path):
    assert unique_pdf_name(tmp_path, "Capture") == tmp_path / "Capture.pdf"
    (tmp_path / "Capture.pdf").write_bytes(b"x")
    assert unique_pdf_name(tmp_path, "Capture") == tmp_path / "Capture (2).pdf"
    (tmp_path / "Capture (2).pdf").write_bytes(b"x")
    assert unique_pdf_name(tmp_path, "Capture") == tmp_path / "Capture (3).pdf"


def test_alpha_detection_and_flatten_in_build(tmp_path):
    rgb = make(tmp_path, "A_0001.png")
    rgba = make(tmp_path, "A_0002.png", mode="RGBA")
    pal = Image.new("P", (50, 50))
    pal.info["transparency"] = 0
    pal.save(tmp_path / "A_0003.png", transparency=0)
    assert not has_alpha(str(rgb))
    assert has_alpha(str(rgba))
    assert has_alpha(str(tmp_path / "A_0003.png"))
    out = tmp_path / "out.pdf"
    n = build_pdf(collect_files(tmp_path, "A"), out)
    assert n == 3
    assert out.exists()
    assert count_pdf_pages(out) == 3
    assert not out.with_name(out.name + ".part").exists()
    # originals untouched
    with Image.open(rgba) as im:
        assert im.mode == "RGBA"


def test_page_count_and_progress(tmp_path):
    files = [str(make(tmp_path, f"B_{i:04d}.png", size=(100 + i, 100))) for i in range(1, 6)]
    seen = []
    out = tmp_path / "B.pdf"
    assert build_pdf(files, out, progress=lambda a, b: seen.append((a, b))) == 5
    assert count_pdf_pages(out) == 5
    assert seen[-1] == (6, 6)
    assert out.stat().st_size > 0
    # page order follows the input order (first page is the 101-wide image)
    data = out.read_bytes()
    assert data.index(b"/Width 101") < data.index(b"/Width 105")


def test_jpg_input_embeds_without_error(tmp_path):
    Image.new("RGB", (64, 64), (10, 20, 30)).save(tmp_path / "C_0001.jpg", quality=95, dpi=(300, 300))
    out = tmp_path / "C.pdf"
    assert build_pdf(collect_files(tmp_path, "C"), out) == 1
    assert count_pdf_pages(out) == 1
