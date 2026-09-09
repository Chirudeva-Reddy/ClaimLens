"""Unit and integration tests for letterbox preprocessing and coordinate inversion."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from claimlens.detection.infer import (
    extract_damages_from_results,
    extract_parts_from_results,
    inspect_vehicle,
)
from claimlens.detection.preprocessing import letterbox_image, unletterbox_coords


def _create_test_image(
    width: int, height: int, color: tuple[int, int, int] = (200, 50, 50)
) -> Image.Image:
    """Helper to create a solid test image."""
    return Image.new("RGB", (width, height), color=color)


def _create_exif_image(width: int, height: int, orientation: int) -> Image.Image:
    """Helper to create an in-memory JPEG image with EXIF orientation tag."""
    img = Image.new("RGB", (width, height), color=(50, 150, 200))
    exif = img.getexif()
    exif[0x0112] = orientation  # 0x0112 is EXIF Orientation tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    buf.seek(0)
    return Image.open(buf)


# ---------------------------------------------------------------------------
# Letterbox Image Tests
# ---------------------------------------------------------------------------


def test_letterbox_square_image() -> None:
    """A square 640x640 image should scale with s=1.0 and zero padding."""
    img = _create_test_image(640, 640, color=(100, 150, 200))
    letterboxed, meta = letterbox_image(img, target_size=(640, 640))

    assert letterboxed.size == (640, 640)
    assert meta["scale"] == pytest.approx(1.0)
    assert meta["pad_left"] == 0
    assert meta["pad_top"] == 0
    assert meta["orig_width"] == 640
    assert meta["orig_height"] == 640
    assert meta["width"] == 640
    assert meta["height"] == 640
    # Pixel check at center
    assert letterboxed.getpixel((320, 320)) == (100, 150, 200)


def test_letterbox_wide_aspect_ratio() -> None:
    """A 1280x640 wide image should have s=0.5, pad_left=0, and pad_top=160."""
    img = _create_test_image(1280, 640, color=(220, 20, 60))
    letterboxed, meta = letterbox_image(img, target_size=(640, 640), fill=(114, 114, 114))

    assert letterboxed.size == (640, 640)
    assert meta["scale"] == pytest.approx(0.5)
    assert meta["pad_left"] == 0
    assert meta["pad_top"] == 160
    assert meta["orig_width"] == 1280
    assert meta["orig_height"] == 640
    assert meta["new_width"] == 640
    assert meta["new_height"] == 320

    # Top padding region must be neutral gray fill
    assert letterboxed.getpixel((320, 50)) == (114, 114, 114)
    # Bottom padding region must be neutral gray fill
    assert letterboxed.getpixel((320, 550)) == (114, 114, 114)
    # Center region should have the resized image content
    assert letterboxed.getpixel((320, 320)) == (220, 20, 60)


def test_letterbox_tall_aspect_ratio() -> None:
    """A 640x1280 tall image should have s=0.5, pad_left=160, and pad_top=0."""
    img = _create_test_image(640, 1280, color=(34, 139, 34))
    letterboxed, meta = letterbox_image(img, target_size=(640, 640), fill=(114, 114, 114))

    assert letterboxed.size == (640, 640)
    assert meta["scale"] == pytest.approx(0.5)
    assert meta["pad_left"] == 160
    assert meta["pad_top"] == 0
    assert meta["orig_width"] == 640
    assert meta["orig_height"] == 1280
    assert meta["new_width"] == 320
    assert meta["new_height"] == 640

    # Left padding region must be neutral gray fill
    assert letterboxed.getpixel((50, 320)) == (114, 114, 114)
    # Right padding region must be neutral gray fill
    assert letterboxed.getpixel((550, 320)) == (114, 114, 114)
    # Center region should have the resized image content
    assert letterboxed.getpixel((320, 320)) == (34, 139, 34)


def test_letterbox_arbitrary_resolutions() -> None:
    """Arbitrary image dimensions should all normalize to constant target size."""
    test_dimensions = [
        (1920, 1080),
        (800, 600),
        (480, 720),
        (1024, 768),
        (300, 300),
        (1200, 300),
    ]
    for w, h in test_dimensions:
        img = _create_test_image(w, h)
        letterboxed, meta = letterbox_image(img, target_size=(640, 640))
        assert letterboxed.size == (640, 640)
        assert meta["orig_width"] == w
        assert meta["orig_height"] == h
        assert 0 <= meta["pad_left"] <= 320
        assert 0 <= meta["pad_top"] <= 320
        assert meta["scale"] > 0


def test_letterbox_exif_orientation_normalization() -> None:
    """EXIF orientation tag 6 (Rotate 90 CW) must be normalized by exif_transpose."""
    # A 400x200 image with orientation 6 represents an image that is 200x400 upright
    exif_img = _create_exif_image(400, 200, orientation=6)
    letterboxed, meta = letterbox_image(exif_img, target_size=(640, 640))

    assert letterboxed.size == (640, 640)
    assert meta["orig_width"] == 200
    assert meta["orig_height"] == 400
    # For 200x400 on 640x640: scale = 640/400 = 1.6; new_w = 320, new_h = 640
    assert meta["scale"] == pytest.approx(1.6)
    assert meta["pad_left"] == (640 - 320) // 2  # 160
    assert meta["pad_top"] == 0


def test_letterbox_custom_target_and_fill() -> None:
    """Custom target size and fill colors should be respected."""
    img = _create_test_image(800, 400)
    letterboxed, meta = letterbox_image(img, target_size=(320, 320), fill=(0, 0, 0))

    assert letterboxed.size == (320, 320)
    assert meta["scale"] == pytest.approx(320 / 800)  # 0.4
    assert meta["new_width"] == 320
    assert meta["new_height"] == 160
    assert meta["pad_top"] == 80
    assert letterboxed.getpixel((160, 20)) == (0, 0, 0)


def test_letterbox_invalid_dimensions() -> None:
    """Zero or negative dimensions must raise ValueError."""
    img = Image.new("RGB", (1, 1))
    img._size = (0, 100)
    with pytest.raises(ValueError, match="Invalid image dimensions"):
        letterbox_image(img)

    valid_img = Image.new("RGB", (100, 100))
    with pytest.raises(ValueError, match="Invalid target_size"):
        letterbox_image(valid_img, target_size=(0, 640))


# ---------------------------------------------------------------------------
# Coordinate Unletterboxing Tests
# ---------------------------------------------------------------------------


def test_unletterbox_coords_1d_bounding_box() -> None:
    """1D bounding box [x1, y1, x2, y2] maps back accurately."""
    meta = {
        "scale": 0.5,
        "pad_left": 0,
        "pad_top": 160,
        "orig_width": 1280,
        "orig_height": 640,
    }
    # Box covering the full resized content in 640x640 space:
    letterbox_box = np.array([0, 160, 640, 480], dtype=np.float32)
    orig_box = unletterbox_coords(letterbox_box, meta)

    assert orig_box.shape == (4,)
    np.testing.assert_allclose(orig_box, [0.0, 0.0, 1280.0, 640.0], atol=1e-3)


def test_unletterbox_coords_2d_bounding_boxes() -> None:
    """2D batch of bounding boxes (N, 4) maps back accurately."""
    meta = {
        "scale": 0.5,
        "pad_left": 160,
        "pad_top": 0,
        "orig_width": 640,
        "orig_height": 1280,
    }
    boxes = np.array(
        [
            [160, 0, 480, 640],
            [200, 100, 400, 500],
        ],
        dtype=np.float32,
    )

    orig_boxes = unletterbox_coords(boxes, meta)
    assert orig_boxes.shape == (2, 4)
    np.testing.assert_allclose(orig_boxes[0], [0.0, 0.0, 640.0, 1280.0], atol=1e-3)
    np.testing.assert_allclose(orig_boxes[1], [80.0, 200.0, 480.0, 1000.0], atol=1e-3)


def test_unletterbox_coords_polygon_vertices() -> None:
    """2D polygon vertex arrays (N, 2) map back accurately."""
    meta = {
        "scale": 0.5,
        "pad_left": 0,
        "pad_top": 160,
        "orig_width": 1280,
        "orig_height": 640,
    }
    pts = np.array(
        [
            [0.0, 160.0],
            [320.0, 320.0],
            [640.0, 480.0],
        ],
        dtype=np.float32,
    )

    orig_pts = unletterbox_coords(pts, meta)
    assert orig_pts.shape == (3, 2)
    expected = np.array(
        [
            [0.0, 0.0],
            [640.0, 320.0],
            [1280.0, 640.0],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(orig_pts, expected, atol=1e-3)


def test_unletterbox_coords_contour_3d() -> None:
    """3D contour arrays (1, N, 2) map back accurately."""
    meta = {
        "scale": 0.5,
        "pad_left": 0,
        "pad_top": 160,
        "orig_width": 1280,
        "orig_height": 640,
    }
    contour = np.array([[[100.0, 200.0], [200.0, 300.0]]], dtype=np.float32)
    orig_contour = unletterbox_coords(contour, meta)

    assert orig_contour.shape == (1, 2, 2)
    expected = np.array([[[200.0, 80.0], [400.0, 280.0]]], dtype=np.float32)
    np.testing.assert_allclose(orig_contour, expected, atol=1e-3)


def test_unletterbox_coords_clamping() -> None:
    """Coordinates falling into letterbox padding or negative range must clamp to image bounds."""
    meta = {
        "scale": 0.5,
        "pad_left": 0,
        "pad_top": 160,
        "orig_width": 1280,
        "orig_height": 640,
    }
    # x1 is negative, y1 is inside top padding (< 160),
    # x2 exceeds 640, y2 is inside bottom padding (> 480)
    out_of_bounds_box = np.array([-50.0, 80.0, 700.0, 600.0], dtype=np.float32)
    clamped = unletterbox_coords(out_of_bounds_box, meta)

    assert clamped[0] == 0.0
    assert clamped[1] == 0.0
    assert clamped[2] == 1280.0
    assert clamped[3] == 640.0


def test_unletterbox_coords_roundtrip_precision() -> None:
    """Forward letterboxing projection followed by unletterboxing must restore original points."""
    meta = {
        "scale": 0.45,
        "pad_left": 40,
        "pad_top": 85,
        "orig_width": 1100,
        "orig_height": 900,
    }
    # Original test points within (1100, 900)
    np.random.seed(42)
    orig_x = np.random.uniform(10, 1090, size=50)
    orig_y = np.random.uniform(10, 890, size=50)
    orig_points = np.stack([orig_x, orig_y], axis=-1).astype(np.float32)

    # Forward projection into canvas:
    pad_x = orig_points[:, 0] * meta["scale"] + meta["pad_left"]
    pad_y = orig_points[:, 1] * meta["scale"] + meta["pad_top"]
    canvas_points = np.stack([pad_x, pad_y], axis=-1)

    # Invert back:
    restored = unletterbox_coords(canvas_points, meta)
    np.testing.assert_allclose(restored, orig_points, atol=1e-3)


def test_unletterbox_coords_empty_array() -> None:
    """Empty coordinate array returns empty array with unchanged shape."""
    meta = {"scale": 1.0, "pad_left": 0, "pad_top": 0, "orig_width": 640, "orig_height": 640}
    empty_boxes = np.zeros((0, 4), dtype=np.float32)
    result = unletterbox_coords(empty_boxes, meta)
    assert result.shape == (0, 4)

    empty_pts = np.zeros((0, 2), dtype=np.float32)
    result_pts = unletterbox_coords(empty_pts, meta)
    assert result_pts.shape == (0, 2)


def test_unletterbox_coords_unsupported_shape() -> None:
    """Invalid coordinate array shape raises ValueError."""
    meta = {"scale": 1.0, "pad_left": 0, "pad_top": 0, "orig_width": 640, "orig_height": 640}
    invalid = np.zeros((3, 5), dtype=np.float32)
    with pytest.raises(ValueError, match="Unsupported coords shape"):
        unletterbox_coords(invalid, meta)


# ---------------------------------------------------------------------------
# Extraction Helpers Integration Tests
# ---------------------------------------------------------------------------


def test_extract_parts_and_damages_coordinate_unletterboxing() -> None:
    """Verify extract_parts and extract_damages properly map coordinates using letterbox_meta."""
    meta = {
        "scale": 0.5,
        "pad_left": 0,
        "pad_top": 160,
        "orig_width": 1280,
        "orig_height": 640,
    }

    # Create dummy Ultralytics result container
    import torch

    class DummyBoxes:
        def __init__(self) -> None:
            self.xyxy = torch.tensor([[0.0, 160.0, 320.0, 480.0]])
            self.conf = torch.tensor([0.95])
            self.cls = torch.tensor([0])

        def __len__(self) -> int:
            return 1

    class DummyMasks:
        def __init__(self) -> None:
            self.xy = [np.array([[0.0, 160.0], [320.0, 160.0], [320.0, 480.0], [0.0, 480.0]])]

        def __len__(self) -> int:
            return 1

    class DummyResult:
        def __init__(self) -> None:
            self.boxes = DummyBoxes()
            self.masks = DummyMasks()
            self.names = {0: "hood"}

    results = [DummyResult()]

    # 1. Extract parts with metadata
    parts = extract_parts_from_results(results, letterbox_meta=meta)
    assert len(parts) == 1
    part = parts[0]
    # Box should be mapped to original [0, 0, 640, 640]
    np.testing.assert_allclose(part.box, (0.0, 0.0, 640.0, 640.0), atol=1e-3)
    assert part.polygon is not None
    np.testing.assert_allclose(
        part.polygon,
        [(0.0, 0.0), (640.0, 0.0), (640.0, 640.0), (0.0, 640.0)],
        atol=1e-3,
    )

    # 2. Extract damages with metadata
    damages = extract_damages_from_results(results, image_size=(1280, 640), letterbox_meta=meta)
    assert len(damages) == 1
    dmg = damages[0]
    np.testing.assert_allclose(dmg.box, (0.0, 0.0, 640.0, 640.0), atol=1e-3)
    assert dmg.polygon is not None
    np.testing.assert_allclose(
        dmg.polygon,
        [(0.0, 0.0), (640.0, 0.0), (640.0, 640.0), (0.0, 640.0)],
        atol=1e-3,
    )
    # Area ratio: polygon is 640x640 = 409600. Total image is 1280x640 = 819200. Ratio = 0.5
    assert dmg.area_ratio == pytest.approx(0.5, abs=1e-3)


# ---------------------------------------------------------------------------
# End-to-End inspect_vehicle Tests on Non-Square Images
# ---------------------------------------------------------------------------


def test_inspect_vehicle_on_wide_image(tmp_path: Path) -> None:
    """End-to-end test verifying inspect_vehicle processes non-square wide image with damage."""
    base_fixture = Path("data/demo_examples/case_a_repairable.jpg")
    if not base_fixture.exists():
        pytest.skip(f"Base demo fixture {base_fixture} not found")

    with Image.open(base_fixture) as orig:
        orig_rgb = orig.convert("RGB")
        # Create a wide 1280x640 canvas and embed the square car image at x=320
        wide_img = Image.new("RGB", (1280, 640), color=(128, 128, 128))
        wide_img.paste(orig_rgb, (320, 0))

    img_path = tmp_path / "wide_vehicle.jpg"
    wide_img.save(img_path)

    # Run inspection
    inspection = inspect_vehicle(img_path)

    assert inspection.accepted_by_quality_gate
    assert inspection.quality_gate_reason is None
    assert inspection.image_meta is not None
    assert inspection.image_meta["width"] == 1280
    assert inspection.image_meta["height"] == 640
    assert inspection.image_meta["orig_width"] == 1280
    assert inspection.image_meta["orig_height"] == 640
    assert inspection.image_meta["scale"] == pytest.approx(0.5)
    assert inspection.image_meta["pad_left"] == 0
    assert inspection.image_meta["pad_top"] == 160

    # Verify damages were detected (recovering the false negative on wide images!)
    total_damages = len(inspection.associated_damages) + len(inspection.unassociated_damages)
    assert total_damages > 0

    all_damages = [assoc.damage for assoc in inspection.associated_damages] + list(
        inspection.unassociated_damages
    )

    # Verify detected coordinates lie strictly in the embedded car region [300, 980] x [0, 640]
    for dmg in all_damages:
        x1, y1, x2, y2 = dmg.box
        assert 300 <= x1 <= 980, f"Damage x1={x1} should align with embedded vehicle"
        assert 300 <= x2 <= 980, f"Damage x2={x2} should align with embedded vehicle"
        assert 0 <= y1 <= 640
        assert 0 <= y2 <= 640
        if dmg.polygon:
            for px, py in dmg.polygon:
                assert 300 <= px <= 980
                assert 0 <= py <= 640

    # Verify annotated image has original canvas dimensions
    assert inspection.annotated_image is not None
    assert inspection.annotated_image.size == (1280, 640)


def test_inspect_vehicle_on_tall_image(tmp_path: Path) -> None:
    """End-to-end test verifying inspect_vehicle processes non-square tall image with damage."""
    base_fixture = Path("data/demo_examples/case_a_repairable.jpg")
    if not base_fixture.exists():
        pytest.skip(f"Base demo fixture {base_fixture} not found")

    with Image.open(base_fixture) as orig:
        orig_rgb = orig.convert("RGB")
        # Create a tall 640x1280 canvas and embed the square car image at y=320
        tall_img = Image.new("RGB", (640, 1280), color=(128, 128, 128))
        tall_img.paste(orig_rgb, (0, 320))

    img_path = tmp_path / "tall_vehicle.jpg"
    tall_img.save(img_path)

    # Run inspection
    inspection = inspect_vehicle(img_path)

    assert inspection.accepted_by_quality_gate
    assert inspection.image_meta["width"] == 640
    assert inspection.image_meta["height"] == 1280
    assert inspection.image_meta["scale"] == pytest.approx(0.5)
    assert inspection.image_meta["pad_left"] == 160
    assert inspection.image_meta["pad_top"] == 0

    total_damages = len(inspection.associated_damages) + len(inspection.unassociated_damages)
    assert total_damages > 0

    all_damages = [assoc.damage for assoc in inspection.associated_damages] + list(
        inspection.unassociated_damages
    )

    # Verify detected coordinates lie in the embedded region y in [300, 980]
    for dmg in all_damages:
        y1, y2 = dmg.box[1], dmg.box[3]
        assert 300 <= y1 <= 980
        assert 300 <= y2 <= 980

    assert inspection.annotated_image is not None
    assert inspection.annotated_image.size == (640, 1280)


def test_inspect_vehicle_preserves_standard_square_fixtures() -> None:
    """Standard 640x640 demo fixtures continue to work with identity mapping."""
    base_fixture = Path("data/demo_examples/case_a_repairable.jpg")
    if not base_fixture.exists():
        pytest.skip(f"Base demo fixture {base_fixture} not found")

    inspection = inspect_vehicle(base_fixture)
    assert inspection.accepted_by_quality_gate
    assert inspection.image_meta["width"] == 640
    assert inspection.image_meta["height"] == 640
    assert inspection.image_meta["scale"] == pytest.approx(1.0)
    assert inspection.image_meta["pad_left"] == 0
    assert inspection.image_meta["pad_top"] == 0
    assert len(inspection.associated_damages) > 0
    assert inspection.annotated_image.size == (640, 640)
