import numpy as np
from PIL import Image, ImageDraw

from framer.capture import DUPLICATE_THRESHOLD, duplicate_distance, is_black, is_duplicate, to_gray64


def page(text_rows: int, seed: int = 0, size=(600, 800)) -> Image.Image:
    """A fake document page: white with some black 'text' bars."""
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(seed)
    for i in range(text_rows):
        y = 40 + i * 28
        w = int(rng.integers(200, size[0] - 80))
        d.rectangle([40, y, 40 + w, y + 12], fill=(0, 0, 0))
    return img


def test_identical_is_duplicate():
    a = page(20, seed=1)
    ga, gb = to_gray64(a), to_gray64(a.copy())
    assert ga.shape == (64, 64)
    assert duplicate_distance(ga, gb) == 0.0
    assert is_duplicate(ga, gb)


def test_different_page_is_not_duplicate():
    a, b = page(20, seed=1), page(20, seed=2)
    ga, gb = to_gray64(a), to_gray64(b)
    assert duplicate_distance(ga, gb) >= DUPLICATE_THRESHOLD
    assert not is_duplicate(ga, gb)


def test_one_line_changed_is_not_duplicate():
    a = page(20, seed=1)
    b = a.copy()
    d = ImageDraw.Draw(b)
    # change roughly one text line's worth of pixels (a 500x14 block = ~1.5% of the page)
    d.rectangle([40, 40, 540, 54], fill=(255, 255, 255))
    d.rectangle([40, 300, 540, 314], fill=(0, 0, 0))
    ga, gb = to_gray64(a), to_gray64(b)
    assert not is_duplicate(ga, gb)


def test_tiny_noise_is_duplicate():
    a = page(20, seed=3)
    arr = np.asarray(a).astype(np.int16)
    rng = np.random.default_rng(7)
    noise = rng.integers(-1, 2, size=arr.shape, dtype=np.int16)
    b = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")
    ga, gb = to_gray64(a), to_gray64(b)
    assert duplicate_distance(ga, gb) < DUPLICATE_THRESHOLD
    assert is_duplicate(ga, gb)


def test_none_or_shape_mismatch_not_duplicate():
    g = to_gray64(page(3))
    assert not is_duplicate(None, g)
    assert not is_duplicate(g, None)
    assert not is_duplicate(g, np.zeros((32, 32), dtype=np.float32))


def test_is_black():
    assert is_black(Image.new("RGB", (10, 10), (0, 0, 0)))
    assert not is_black(Image.new("RGB", (10, 10), (0, 0, 1)))
    assert is_black(Image.new("L", (10, 10), 0))
