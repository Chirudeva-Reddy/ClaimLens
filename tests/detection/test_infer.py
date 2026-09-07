from PIL import Image, ImageFilter

from claimlens.detection.infer import inspect_vehicle


def _checkerboard(size=(640, 640), tile=20) -> Image.Image:
    small = Image.new("L", (size[0] // tile, size[1] // tile))
    pixels = small.load()
    for y in range(small.height):
        for x in range(small.width):
            pixels[x, y] = 255 if (x + y) % 2 == 0 else 0
    return small.resize(size, Image.NEAREST).convert("RGB")


def test_inspect_vehicle_rejects_blurry_image(tmp_path):
    path = tmp_path / "blurry.jpg"
    _checkerboard().filter(ImageFilter.GaussianBlur(radius=15)).save(path)

    result = inspect_vehicle(path)

    assert not result.accepted_by_quality_gate
    assert result.quality_gate_reason == "too_blurry"
    assert len(result.associated_damages) == 0


def test_inspect_vehicle_accepts_clean_image_without_models(tmp_path):
    path = tmp_path / "clean.jpg"
    _checkerboard().save(path)

    # When no model weights exist, inspect_vehicle should still safely return
    # an accepted result with empty detections, not crash.
    result = inspect_vehicle(path, parts_model=None, damages_model=None)

    assert result.accepted_by_quality_gate
    assert result.quality_gate_reason is None
    assert len(result.associated_damages) == 0
    assert not result.structural_flag
