from PIL import Image, ImageFilter

from claimlens.quality_gate.gate import check_image_quality


def _checkerboard(size=(640, 640), tile=20) -> Image.Image:
    small = Image.new("L", (size[0] // tile, size[1] // tile))
    pixels = small.load()
    for y in range(small.height):
        for x in range(small.width):
            pixels[x, y] = 255 if (x + y) % 2 == 0 else 0
    return small.resize(size, Image.NEAREST).convert("RGB")


def test_accepts_sharp_high_resolution_image(tmp_path):
    path = tmp_path / "sharp.jpg"
    _checkerboard().save(path)

    verdict = check_image_quality(path)

    assert verdict.accepted


def test_rejects_blurry_image(tmp_path):
    path = tmp_path / "blurry.jpg"
    _checkerboard().filter(ImageFilter.GaussianBlur(radius=15)).save(path)

    verdict = check_image_quality(path)

    assert not verdict.accepted
    assert verdict.reason == "too_blurry"


def test_rejects_low_resolution_image(tmp_path):
    path = tmp_path / "small.jpg"
    _checkerboard(size=(50, 50), tile=5).save(path)

    verdict = check_image_quality(path)

    assert not verdict.accepted
    assert verdict.reason == "resolution_too_low"


def test_rejects_unreadable_file(tmp_path):
    path = tmp_path / "corrupt.jpg"
    path.write_bytes(b"not an image")

    verdict = check_image_quality(path)

    assert not verdict.accepted
    assert verdict.reason == "unreadable_file"
