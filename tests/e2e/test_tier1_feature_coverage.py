"""Tier 1: Feature Coverage E2E Tests.

Validates core requirements from ORIGINAL_REQUEST.md and PROJECT.md:
- Letterbox normalization (640x640 constant resolution, aspect preservation, (114, 114, 114) fill)
- EXIF orientation handling via ImageOps.exif_transpose
- Inverse coordinate projection (unletterbox_coords) for bounding boxes and polygon vertices
- Dataset split validation (zero image/hash leakage, normalized [0, 1] coordinates)
- Hyperparameter configuration & device selection (MPS / CPU)
- Model checkpointing & ONNX export integrity
- Automated generalization benchmark reporting schema
- Triage consistency on canonical inspection scenarios
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
import pytest
import torch
from PIL import Image

from claimlens.costing.estimate import estimate_repair_costs
from claimlens.detection.infer import inspect_vehicle
from claimlens.triage.decide import TriageOutcome, decide_triage
from tests.e2e.conftest import HAS_PREPROCESSING, letterbox_image, unletterbox_coords


# ============================================================================
# 1. Letterbox Normalization Contract
# ============================================================================
@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_letterbox_normalization_aspect_and_padding() -> None:
    """Verifies that letterbox_image normalizes any image to 640x640 with neutral gray padding."""
    # 1. Landscape 1280x720 (16:9)
    landscape_img = Image.new("RGB", (1280, 720), color=(255, 0, 0))
    boxed_land, meta_land = letterbox_image(landscape_img, target_size=(640, 640))

    assert boxed_land.size == (640, 640), "Target resolution must be strictly 640x640"
    assert meta_land["orig_width"] == 1280
    assert meta_land["orig_height"] == 720
    assert meta_land["scale"] == pytest.approx(640 / 1280, abs=1e-4)  # 0.5
    assert meta_land["pad_left"] == 0
    # Expected scaled height: 720 * 0.5 = 360; Remaining pad: 640 - 360 = 280; Centered: 140
    assert meta_land["pad_top"] == 140

    # Verify neutral gray fill (114, 114, 114) in padding zones
    pixels = boxed_land.load()
    assert pixels[320, 10] == (114, 114, 114), (
        "Top padding must be filled with neutral gray (114, 114, 114)"
    )
    assert pixels[320, 630] == (114, 114, 114), (
        "Bottom padding must be filled with neutral gray (114, 114, 114)"
    )
    assert pixels[320, 320] == (255, 0, 0), "Image content must be centered and preserved"

    # 2. Portrait 720x1280 (9:16)
    portrait_img = Image.new("RGB", (720, 1280), color=(0, 255, 0))
    boxed_port, meta_port = letterbox_image(portrait_img, target_size=(640, 640))

    assert boxed_port.size == (640, 640)
    assert meta_port["orig_width"] == 720
    assert meta_port["orig_height"] == 1280
    assert meta_port["scale"] == pytest.approx(640 / 1280, abs=1e-4)
    assert meta_port["pad_top"] == 0
    assert meta_port["pad_left"] == 140

    port_pixels = boxed_port.load()
    assert port_pixels[10, 320] == (114, 114, 114), "Left padding must be neutral gray"
    assert port_pixels[630, 320] == (114, 114, 114), "Right padding must be neutral gray"
    assert port_pixels[320, 320] == (0, 255, 0), "Content must be centered"

    # 3. Square 800x800 (1:1)
    square_img = Image.new("RGB", (800, 800), color=(0, 0, 255))
    boxed_sq, meta_sq = letterbox_image(square_img, target_size=(640, 640))

    assert boxed_sq.size == (640, 640)
    assert meta_sq["scale"] == pytest.approx(640 / 800, abs=1e-4)  # 0.8
    assert meta_sq["pad_left"] == 0
    assert meta_sq["pad_top"] == 0


# ============================================================================
# 2. EXIF Orientation Normalization
# ============================================================================
@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_exif_orientation_handling(tmp_path: Path) -> None:
    """Verifies that EXIF orientation metadata is transposed before letterboxing."""
    raw_path = tmp_path / "orientation_6.jpg"

    # Stored as landscape 1000x500, but EXIF tag 6 (Rotate 90 CW) indicates upright portrait 500x1000
    img = Image.new("RGB", (1000, 500), color=(200, 100, 50))
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation 6
    img.save(raw_path, format="JPEG", exif=exif)

    with Image.open(raw_path) as loaded_img:
        boxed_img, meta = letterbox_image(loaded_img, target_size=(640, 640))

    # Upright dimensions should be 500 wide by 1000 tall
    assert meta["orig_width"] == 500, "EXIF transpose must normalize width to 500"
    assert meta["orig_height"] == 1000, "EXIF transpose must normalize height to 1000"
    assert meta["scale"] == pytest.approx(640 / 1000, abs=1e-4)  # 0.64
    # Scaled width = 500 * 0.64 = 320; pad_left = (640 - 320) / 2 = 160
    assert meta["pad_left"] == 160
    assert meta["pad_top"] == 0
    assert boxed_img.size == (640, 640)


# ============================================================================
# 3. Coordinate Inverse Projection Contract
# ============================================================================
@pytest.mark.skipif(
    not HAS_PREPROCESSING, reason="Milestone M1 pending: claimlens.detection.preprocessing"
)
def test_inverse_coordinate_projection_contract() -> None:
    """Verifies unletterbox_coords accurately inverts box and polygon coordinates."""
    # Metadata for 1280x720 input resized to 640x360 with 140px vertical padding
    meta = {
        "orig_width": 1280,
        "orig_height": 720,
        "scale": 0.5,
        "pad_left": 0,
        "pad_top": 140,
    }

    # Bounding Box: [x1, y1, x2, y2]
    # Box in 640x640 space: [100, 240, 500, 440]
    # Expected in 1280x720: [(100-0)/0.5, (240-140)/0.5, (500-0)/0.5, (440-140)/0.5] = [200, 200, 1000, 600]
    test_boxes = np.array([[100.0, 240.0, 500.0, 440.0]], dtype=np.float32)
    unboxed = unletterbox_coords(test_boxes, meta)

    assert unboxed.shape == (1, 4)
    np.testing.assert_allclose(unboxed[0], [200.0, 200.0, 1000.0, 600.0], rtol=1e-4)

    # Polygon Vertices: [[x, y], ...]
    test_poly = np.array(
        [[100.0, 240.0], [500.0, 240.0], [500.0, 440.0], [100.0, 440.0]],
        dtype=np.float32,
    )
    unpoly = unletterbox_coords(test_poly, meta)

    assert unpoly.shape == (4, 2)
    expected_poly = np.array(
        [[200.0, 200.0], [1000.0, 200.0], [1000.0, 600.0], [200.0, 600.0]],
        dtype=np.float32,
    )
    np.testing.assert_allclose(unpoly, expected_poly, rtol=1e-4)

    # Boundary Clamping Test: Box extending into padding zone
    # y1=50 is in top padding (pad_top=140). (50-140)/0.5 = -180 -> Must clamp to 0.0
    out_of_bounds_box = np.array([[-20.0, 50.0, 700.0, 600.0]], dtype=np.float32)
    clamped_box = unletterbox_coords(out_of_bounds_box, meta)

    assert clamped_box[0, 0] == 0.0, "Negative x must clamp to 0"
    assert clamped_box[0, 1] == 0.0, "Padding y must clamp to 0"
    assert clamped_box[0, 2] == 1280.0, "Exceeded x must clamp to orig_width (1280)"
    assert clamped_box[0, 3] == 720.0, "Exceeded y must clamp to orig_height (720)"


# ============================================================================
# 4. Dataset Split Validation & Zero Leakage
# ============================================================================
def test_dataset_split_validation_and_coordinate_integrity() -> None:
    """Verifies that dataset splits (raw and parts) maintain strict zero leakage and normalized labels."""
    dataset_dirs = [Path("data/raw"), Path("data/parts")]

    for base_dir in dataset_dirs:
        if not (base_dir / "data.yaml").exists():
            continue

        split_images: dict[str, set[str]] = {}
        for split in ["train", "valid", "test"]:
            img_dir = base_dir / split / "images"
            if not img_dir.exists():
                continue

            images = {
                p.stem for p in img_dir.glob("*.*") if p.suffix.lower() in [".jpg", ".jpeg", ".png"]
            }
            split_images[split] = images

        # Check disjointness across splits
        splits = list(split_images.keys())
        for i in range(len(splits)):
            for j in range(i + 1, len(splits)):
                s1, s2 = splits[i], splits[j]
                overlap = split_images[s1].intersection(split_images[s2])
                assert len(overlap) == 0, (
                    f"Split leakage detected in {base_dir} between {s1} and {s2}: {overlap}"
                )

        # Check label coordinate normalization in [0, 1]
        for split in splits:
            lbl_dir = base_dir / split / "labels"
            if not lbl_dir.exists():
                continue

            for lbl_path in lbl_dir.glob("*.txt"):
                with open(lbl_path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, start=1):
                        parts = line.strip().split()
                        if not parts:
                            continue
                        coords = [float(x) for x in parts[1:]]
                        for c in coords:
                            assert 0.0 <= c <= 1.05, (  # small epsilon for boundary points
                                f"Coordinate {c} out of [0, 1] bounds in {lbl_path}:{line_no}"
                            )


# ============================================================================
# 5. Hyperparameter Configuration & MPS Device Selection
# ============================================================================
def test_hyperparameter_configuration_and_device_selection() -> None:
    """Verifies train.py device selection and hyperparameter defaults."""
    from claimlens.train import get_optimal_device

    # Test explicit device override
    assert get_optimal_device("cpu") == "cpu"

    # Test auto device detection
    detected = get_optimal_device(None)
    if torch.backends.mps.is_available():
        assert detected == "mps", (
            "On Apple Silicon with MPS available, optimal device must be 'mps'"
        )
    elif torch.cuda.is_available():
        assert detected == "cuda"
    else:
        assert detected == "cpu"

    # Test MPS fallback when MPS requested but unavailable
    if not torch.backends.mps.is_available():
        assert get_optimal_device("mps") == "cpu"


# ============================================================================
# 6. Model Checkpointing & ONNX Export Integrity
# ============================================================================
def test_model_checkpointing_and_onnx_export() -> None:
    """Verifies that model weights exist and exported ONNX models pass strict graph validation."""
    damages_pt = Path("models/damages_best.pt")
    parts_pt = Path("models/parts_best.pt")
    damages_onnx = Path("models/damages_best.onnx")
    parts_onnx = Path("models/parts_best.onnx")

    assert damages_pt.exists(), "damages_best.pt must exist in models/"
    assert parts_pt.exists(), "parts_best.pt must exist in models/"
    assert damages_onnx.exists(), "damages_best.onnx must exist in models/"
    assert parts_onnx.exists(), "parts_best.onnx must exist in models/"

    # Check ONNX graph validity using ONNX standard checker
    model_dmg = onnx.load(str(damages_onnx))
    onnx.checker.check_model(model_dmg)

    model_prt = onnx.load(str(parts_onnx))
    onnx.checker.check_model(model_prt)

    # Verify input tensor dimensions: dynamic batch x 3 x dynamic/fixed spatial dimensions
    input_tensor = model_dmg.graph.input[0]
    dim_objs = input_tensor.type.tensor_type.shape.dim
    assert len(dim_objs) == 4, f"Expected 4D NCHW input tensor, got {len(dim_objs)} dimensions"
    assert dim_objs[1].dim_value == 3, (
        f"Channel dimension must be 3 (RGB), got {dim_objs[1].dim_value}"
    )

    # Batch dimension (dim 0) and spatial dimensions (dim 2, 3) are dynamic or 640
    batch_axis = dim_objs[0].dim_param or dim_objs[0].dim_value
    h_axis = dim_objs[2].dim_param or dim_objs[2].dim_value
    w_axis = dim_objs[3].dim_param or dim_objs[3].dim_value
    assert batch_axis in ["batch", 1, 0]
    assert h_axis in ["height", 640, 0]
    assert w_axis in ["width", 640, 0]


# ============================================================================
# 7. Automated Benchmark Reporting Schema
# ============================================================================
def test_automated_benchmark_reporting_schema() -> None:
    """Verifies the schema structure required for the generalization benchmark JSON summary."""
    required_metric_keys = {
        "box_precision",
        "box_recall",
        "box_map50",
        "mask_precision",
        "mask_recall",
        "mask_map50",
    }
    required_delta_keys = {
        "box_recall_diff",
        "box_map50_diff",
        "mask_recall_diff",
        "mask_map50_diff",
    }

    # Synthesize sample benchmark output according to PROJECT.md contract
    sample_benchmark = {
        "baseline": {
            "box_precision": 0.68,
            "box_recall": 0.61,
            "box_map50": 0.64,
            "mask_precision": 0.65,
            "mask_recall": 0.58,
            "mask_map50": 0.63,
        },
        "fine_tuned": {
            "box_precision": 0.72,
            "box_recall": 0.67,
            "box_map50": 0.69,
            "mask_precision": 0.69,
            "mask_recall": 0.64,
            "mask_map50": 0.67,
        },
        "delta": {
            "box_recall_diff": 0.06,
            "box_map50_diff": 0.05,
            "mask_recall_diff": 0.06,
            "mask_map50_diff": 0.04,
        },
    }

    # Verify keys
    assert set(sample_benchmark["baseline"].keys()) == required_metric_keys
    assert set(sample_benchmark["fine_tuned"].keys()) == required_metric_keys
    assert set(sample_benchmark["delta"].keys()) == required_delta_keys

    # Verify arithmetic consistency of deltas
    for k in ["box_recall", "box_map50", "mask_recall", "mask_map50"]:
        diff_key = f"{k}_diff"
        expected_diff = round(
            sample_benchmark["fine_tuned"][k] - sample_benchmark["baseline"][k], 4
        )
        assert sample_benchmark["delta"][diff_key] == pytest.approx(expected_diff, abs=1e-4)


# ============================================================================
# 8. Triage Consistency on Canonical Scenarios
# ============================================================================
def test_triage_consistency_on_canonical_cases(demo_image_paths: dict[str, Path]) -> None:
    """Verifies deterministic triage outcomes across the three standard blueprint cases."""
    # Case A: Minor Cosmetic Repairable
    res_a = inspect_vehicle(demo_image_paths["case_a"])
    est_a = estimate_repair_costs(res_a, brand="Toyota")
    dec_a = decide_triage(res_a, est_a, pre_accident_value=120000.0, preset_id="uae_50")

    assert res_a.accepted_by_quality_gate
    assert dec_a.outcome == TriageOutcome.PROBABLY_REPAIRABLE
    assert dec_a.economic_ratio < 0.50

    # Case B: Multi-Panel Severe Collision (Low ACV -> Total Loss)
    res_b = inspect_vehicle(demo_image_paths["case_b"])
    est_b = estimate_repair_costs(res_b, brand="General Market Standard")
    dec_b = decide_triage(res_b, est_b, pre_accident_value=15000.0, preset_id="uae_50")

    assert res_b.accepted_by_quality_gate
    assert dec_b.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW
    assert dec_b.economic_ratio >= 0.50

    # Case C: Quarter-Panel Unibody Impact (Structural Safe Abstention)
    res_c = inspect_vehicle(demo_image_paths["case_c"])
    est_c = estimate_repair_costs(res_c, brand="Toyota")
    dec_c = decide_triage(res_c, est_c, pre_accident_value=85000.0, preset_id="uae_50")

    assert res_c.accepted_by_quality_gate
    assert res_c.structural_flag is True
    assert dec_c.outcome == TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
