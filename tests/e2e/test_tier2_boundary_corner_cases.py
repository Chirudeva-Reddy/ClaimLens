"""Tier 2: Boundary & Corner Cases E2E Tests.

Validates robust system behavior under adverse geometric, resolution, and data extremes:
- Extreme aspect ratios (ultrawide panoramic bumper 12:1, ultratall pillar 1:12)
- Tiny images (<480x480 quality gate enforcement & numerical stability)
- Massive high-resolution images (4000+ px smartphone captures)
- Zero detections (clean panel, empty parts/damages list, safe triage fallback)
- Single-pixel coordinates (micro-chip damage, non-zero area calculation)
- Edge boundaries & out-of-bounds clamping
- Empty & degenerate polygon protections (empty, 1-pt, 2-pt, collinear points)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from claimlens.costing.estimate import estimate_repair_costs
from claimlens.detection.association import associate_damages_with_parts
from claimlens.detection.infer import (
    annotate_inspection,
    extract_damages_from_results,
    inspect_vehicle,
)
from claimlens.detection.schemas import DetectedDamage, DetectedPart, InspectionResult
from claimlens.quality_gate.gate import check_image_quality
from claimlens.triage.decide import TriageOutcome, decide_triage
from tests.e2e.conftest import (
    HAS_PREPROCESSING,
    MockYOLOResult,
    letterbox_image,
    unletterbox_coords,
)


# ============================================================================
# 1. Extreme Aspect Ratios (Ultrawide & Ultratall)
# ============================================================================
@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_extreme_aspect_ratio_ultrawide() -> None:
    """Verifies letterbox normalization and coordinate inversion on a 12:1 ultrawide image (2400x200)."""
    # 2400 wide x 200 tall
    img = Image.new("RGB", (2400, 200), color=(180, 20, 20))
    boxed, meta = letterbox_image(img, target_size=(640, 640))

    assert boxed.size == (640, 640)
    assert meta["orig_width"] == 2400
    assert meta["orig_height"] == 200
    assert meta["scale"] == pytest.approx(640 / 2400, abs=1e-4)
    # Scaled height = 200 * (640/2400) = 53.33 -> centered vertical padding ~293px
    assert meta["pad_left"] == 0
    assert meta["pad_top"] == (640 - round(200 * (640 / 2400))) // 2

    # Coordinate inversion check across width
    test_box = np.array([[100.0, meta["pad_top"] + 10.0, 500.0, meta["pad_top"] + 40.0]])
    unboxed = unletterbox_coords(test_box, meta)

    assert 0.0 <= unboxed[0, 0] <= unboxed[0, 2] <= 2400.0
    assert 0.0 <= unboxed[0, 1] <= unboxed[0, 3] <= 200.0


@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_extreme_aspect_ratio_ultratall() -> None:
    """Verifies letterbox normalization and coordinate inversion on a 1:12 ultratall image (200x2400)."""
    # 200 wide x 2400 tall
    img = Image.new("RGB", (200, 2400), color=(20, 180, 20))
    boxed, meta = letterbox_image(img, target_size=(640, 640))

    assert boxed.size == (640, 640)
    assert meta["orig_width"] == 200
    assert meta["orig_height"] == 2400
    assert meta["scale"] == pytest.approx(640 / 2400, abs=1e-4)
    assert meta["pad_top"] == 0
    assert meta["pad_left"] == (640 - round(200 * (640 / 2400))) // 2

    test_box = np.array([[meta["pad_left"] + 5.0, 200.0, meta["pad_left"] + 45.0, 1800.0]])
    unboxed = unletterbox_coords(test_box, meta)

    assert 0.0 <= unboxed[0, 0] <= unboxed[0, 2] <= 200.0
    assert 0.0 <= unboxed[0, 1] <= unboxed[0, 3] <= 2400.0


# ============================================================================
# 2. Tiny Images (<480x480) & Resolution Protection
# ============================================================================
def test_tiny_image_quality_gate_rejection(tmp_path: Path) -> None:
    """Verifies that tiny images below the 480px resolution floor are strictly rejected by the Quality Gate."""
    tiny_path = tmp_path / "tiny_thumbnail.jpg"
    img = Image.new("RGB", (320, 240), color=(120, 120, 120))
    img.save(tiny_path)

    verdict = check_image_quality(tiny_path)
    assert not verdict.accepted
    assert verdict.reason == "resolution_too_low"

    # End-to-end inspect_vehicle safety
    inspection = inspect_vehicle(tiny_path)
    assert not inspection.accepted_by_quality_gate
    assert inspection.quality_gate_reason == "resolution_too_low"
    assert len(inspection.associated_damages) == 0


@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_tiny_image_letterbox_numerical_stability() -> None:
    """Verifies that letterbox_image scales tiny images cleanly without division by zero or NaN."""
    tiny_img = Image.new("RGB", (64, 64), color=(50, 50, 50))
    boxed, meta = letterbox_image(tiny_img, target_size=(640, 640))

    assert boxed.size == (640, 640)
    assert meta["scale"] == pytest.approx(10.0, abs=1e-4)
    assert not np.isnan(meta["scale"])
    assert not np.isinf(meta["scale"])


# ============================================================================
# 3. Massive / High-Resolution Images (Smartphone 12MP)
# ============================================================================
def test_massive_high_resolution_image_processing(
    tmp_path: Path, create_sharp_image: Callable[[int, int, int], Image.Image]
) -> None:
    """Verifies stability, quality gate acceptance, and coordinate precision on 12-megapixel images (4032x3024)."""
    massive_path = tmp_path / "smartphone_12mp.jpg"
    sharp_img = create_sharp_image(4032, 3024, tile=40)
    sharp_img.save(massive_path, format="JPEG", quality=90)

    # Must pass quality gate
    verdict = check_image_quality(massive_path)
    assert verdict.accepted, f"Massive sharp image must pass quality gate, got {verdict.reason}"

    # If preprocessing available, test coordinate invert round-trip precision
    if HAS_PREPROCESSING and letterbox_image and unletterbox_coords:
        with Image.open(massive_path) as loaded:
            boxed, meta = letterbox_image(loaded, target_size=(640, 640))

        assert boxed.size == (640, 640)
        assert meta["orig_width"] == 4032
        assert meta["orig_height"] == 3024

        # Point at (2016, 1512) in original space
        scale = meta["scale"]
        pad_left = meta["pad_left"]
        pad_top = meta["pad_top"]
        x_pad = 2016.0 * scale + pad_left
        y_pad = 1512.0 * scale + pad_top

        box_pad = np.array([[x_pad, y_pad, x_pad + 50.0, y_pad + 50.0]])
        unboxed = unletterbox_coords(box_pad, meta)

        assert unboxed[0, 0] == pytest.approx(2016.0, abs=1.5)
        assert unboxed[0, 1] == pytest.approx(1512.0, abs=1.5)


# ============================================================================
# 4. Zero Detections (Clean Panel / Empty Detections)
# ============================================================================
def test_zero_detections_pipeline_gracefulness(tmp_path: Path) -> None:
    """Verifies that an image with 0 detections completes the full pipeline without division by zero or crash."""
    empty_parts: list[DetectedPart] = []
    empty_damages: list[DetectedDamage] = []

    # 1. Association layer
    assoc, unassoc, struct_flag = associate_damages_with_parts(empty_damages, empty_parts)
    assert len(assoc) == 0
    assert len(unassoc) == 0
    assert struct_flag is False

    # 2. Costing layer
    dummy_inspection = InspectionResult(
        accepted_by_quality_gate=True,
        associated_damages=assoc,
        unassociated_damages=unassoc,
        all_parts=empty_parts,
        structural_flag=struct_flag,
    )
    estimate = estimate_repair_costs(dummy_inspection, brand="Toyota")
    assert estimate.total_min == 0.0
    assert estimate.total_max == 0.0
    assert estimate.median_estimate == 0.0
    assert len(estimate.itemized_costs) == 0

    # 3. Triage layer (Zero repair cost on AED 100k vehicle)
    decision = decide_triage(
        dummy_inspection,
        estimate,
        pre_accident_value=100000.0,
        preset_id="uae_50",
    )
    assert decision.economic_ratio == 0.0
    # With 0 damage detected and no structural risk, loss ratio remains safely within threshold
    assert decision.outcome == TriageOutcome.PROBABLY_REPAIRABLE

    # 4. Annotation layer
    canvas = Image.new("RGB", (640, 640), color=(255, 255, 255))
    annotated = annotate_inspection(canvas, empty_parts, empty_damages)
    assert annotated.size == (640, 640)


# ============================================================================
# 5. Single-Pixel Coordinates & Micro-Damage
# ============================================================================
def test_single_pixel_coordinates_and_micro_damage(
    mock_yolo_result_factory: Callable[..., MockYOLOResult],
) -> None:
    """Verifies that single-pixel micro-damage results in positive, non-zero area ratio without numerical underflow."""
    img_size = (1000, 1000)

    # 1-pixel bounding box [100.0, 100.0, 101.0, 101.0] (width=1, height=1)
    mock_res = mock_yolo_result_factory(
        boxes_xyxy=[[100.0, 100.0, 101.0, 101.0]],
        scores=[0.85],
        class_ids=[4],  # scratch
        polygons=[],
        names={4: "scratch"},
    )

    damages = extract_damages_from_results([mock_res], img_size)
    assert len(damages) == 1
    dmg = damages[0]

    expected_area_ratio = (1.0 * 1.0) / (1000.0 * 1000.0)  # 1e-6
    assert dmg.area_ratio > 0.0
    assert dmg.area_ratio == pytest.approx(expected_area_ratio, rel=1e-3)
    assert not np.isnan(dmg.area_ratio)


# ============================================================================
# 6. Edge Boundaries & Out-of-Bounds Clamping
# ============================================================================
@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_edge_boundaries_and_out_of_bounds_clamping() -> None:
    """Verifies that coordinates at or beyond canvas edges are strictly clamped to original dimensions."""
    meta = {
        "orig_width": 800,
        "orig_height": 600,
        "scale": 0.8,
        "pad_left": 0,
        "pad_top": 80,
    }

    # Boxes with extreme out-of-bounds negative and exceeding coordinates
    extreme_boxes = np.array(
        [
            [-100.0, -50.0, 50.0, 70.0],  # negative top-left, y in padding
            [750.0, 500.0, 950.0, 800.0],  # exceeding bottom-right
        ],
        dtype=np.float32,
    )

    clamped = unletterbox_coords(extreme_boxes, meta)

    # Box 0: x1 must clamp to 0, y1 in padding must clamp to 0
    assert clamped[0, 0] == 0.0
    assert clamped[0, 1] == 0.0

    # Box 1: x2 must clamp to orig_width (800), y2 must clamp to orig_height (600)
    assert clamped[1, 2] == 800.0
    assert clamped[1, 3] == 600.0


# ============================================================================
# 7. Empty & Degenerate Polygon Protections
# ============================================================================
def test_empty_and_degenerate_polygon_protections(
    mock_yolo_result_factory: Callable[..., MockYOLOResult],
) -> None:
    """Verifies that empty, 1-point, 2-point, and collinear polygons fall back to box area without crashing."""
    img_size = (640, 640)
    box = [50.0, 50.0, 150.0, 150.0]  # width=100, height=100 -> box area = 10,000

    # Case 1: Empty polygon list []
    res_empty = mock_yolo_result_factory(
        boxes_xyxy=[box],
        scores=[0.9],
        class_ids=[1],
        polygons=[[]],
        names={1: "dent"},
    )
    dmg_empty = extract_damages_from_results([res_empty], img_size)[0]
    expected_box_ratio = (100.0 * 100.0) / (640.0 * 640.0)
    assert dmg_empty.area_ratio == pytest.approx(expected_box_ratio, rel=1e-3)
    assert dmg_empty.polygon is None

    # Case 2: 1-point polygon [(50.0, 50.0)] (<3 points, invalid polygon)
    res_1pt = mock_yolo_result_factory(
        boxes_xyxy=[box],
        scores=[0.9],
        class_ids=[1],
        polygons=[[[50.0, 50.0]]],
        names={1: "dent"},
    )
    dmg_1pt = extract_damages_from_results([res_1pt], img_size)[0]
    assert dmg_1pt.area_ratio == pytest.approx(expected_box_ratio, rel=1e-3)

    # Case 3: 2-point line segment [[50.0, 50.0], [150.0, 150.0]] (<3 points)
    res_2pt = mock_yolo_result_factory(
        boxes_xyxy=[box],
        scores=[0.9],
        class_ids=[1],
        polygons=[[[50.0, 50.0], [150.0, 150.0]]],
        names={1: "dent"},
    )
    dmg_2pt = extract_damages_from_results([res_2pt], img_size)[0]
    assert dmg_2pt.area_ratio == pytest.approx(expected_box_ratio, rel=1e-3)

    # Case 4: 3 collinear points [[50.0, 50.0], [100.0, 100.0], [150.0, 150.0]] (shoelace area = 0.0)
    res_collinear = mock_yolo_result_factory(
        boxes_xyxy=[box],
        scores=[0.9],
        class_ids=[1],
        polygons=[[[50.0, 50.0], [100.0, 100.0], [150.0, 150.0]]],
        names={1: "dent"},
    )
    dmg_collinear = extract_damages_from_results([res_collinear], img_size)[0]
    # Because shoelace area is 0.0, code must fall back to bounding box area ratio
    assert dmg_collinear.area_ratio == pytest.approx(expected_box_ratio, rel=1e-3)
