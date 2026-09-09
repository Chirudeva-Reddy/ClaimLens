"""Tier 4: Real-World Application Scenarios E2E Tests.

Validates operational customer-facing flows using realistic smartphone photography:
- End-to-end inspection on realistic non-square smartphone photos (3024x4032 / 4032x3024)
- Verification of repairability decision on minor damage (Case A)
- Verification of total loss decision on severe economic damage (Case B)
- Verification of structural safe abstention invariant (Case C)
- FastAPI /api/analyze multipart upload with non-square input & full JSON contract validation
- Gradio analyze_claim UI pipeline execution returning all 7 analytical components
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from claimlens.app import analyze_claim
from claimlens.costing.estimate import estimate_repair_costs
from claimlens.detection.infer import inspect_vehicle
from claimlens.policy.retrieve import retrieve_policy_guidance
from claimlens.triage.decide import TriageOutcome, decide_triage


def test_smartphone_photo_e2e_repairable(
    tmp_path: Path,
    create_sharp_image: Callable[[int, int, int], Image.Image],
) -> None:
    """Verifies end-to-end triage on a realistic smartphone photo (3024x4032 portrait) resulting in PROBABLY_REPAIRABLE."""
    phone_photo_path = tmp_path / "smartphone_bumper_scratch.jpg"
    # Create realistic high-resolution portrait photo with EXIF orientation 1
    phone_img = create_sharp_image(3024, 4032, tile=60)
    phone_exif = phone_img.getexif()
    phone_exif[0x0112] = 1  # Normal orientation
    phone_img.save(phone_photo_path, format="JPEG", quality=92, exif=phone_exif)

    # 1. Inspect vehicle
    inspection = inspect_vehicle(phone_photo_path)
    assert inspection.accepted_by_quality_gate is True
    assert inspection.quality_gate_reason is None

    # 2. Costing with Toyota OEM rates in AED
    estimate = estimate_repair_costs(inspection, brand="Toyota")

    # 3. Decision on high-value vehicle (ACV AED 140,000, UAE 50% statutory threshold)
    decision = decide_triage(inspection, estimate, pre_accident_value=140000.0, preset_id="uae_50")

    # In absence of structural damage and low repair costs, must be repairable or abstention if no damage
    if len(inspection.associated_damages) > 0 and not inspection.structural_flag:
        assert decision.outcome == TriageOutcome.PROBABLY_REPAIRABLE
        assert decision.economic_ratio < 0.50
    else:
        assert decision.outcome in [
            TriageOutcome.PROBABLY_REPAIRABLE,
            TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED,
        ]

    # 4. Policy retrieval confirmation
    policy = retrieve_policy_guidance("bumper scratch cosmetic workshop repair")
    assert policy.is_established is True


def test_smartphone_photo_e2e_total_loss_decision(
    demo_image_paths: dict[str, Path],
) -> None:
    """Verifies that severe collision damage on a depreciated vehicle triggers PROBABLE_TOTAL_LOSS_REVIEW."""
    image_path = demo_image_paths["case_b"]

    inspection = inspect_vehicle(image_path)
    assert inspection.accepted_by_quality_gate is True

    estimate = estimate_repair_costs(inspection, brand="General Market Standard")
    # Low ACV vehicle (AED 12,000)
    decision = decide_triage(inspection, estimate, pre_accident_value=12000.0, preset_id="uae_50")

    assert decision.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW
    assert decision.economic_ratio >= 0.50
    assert "SALVAGE" in decision.reasoning.upper() or "TOTAL LOSS" in decision.reasoning.upper()


def test_smartphone_photo_e2e_structural_hazard_abstention(
    demo_image_paths: dict[str, Path],
) -> None:
    """Verifies that collision damage to load-bearing structural zones triggers safe abstention."""
    image_path = demo_image_paths["case_c"]

    inspection = inspect_vehicle(image_path)
    assert inspection.accepted_by_quality_gate is True
    assert inspection.structural_flag is True, "Case C must flag structural risk"

    estimate = estimate_repair_costs(inspection, brand="Toyota")
    decision = decide_triage(inspection, estimate, pre_accident_value=85000.0, preset_id="uae_50")

    assert decision.outcome == TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
    assert decision.structural_damage_flag is True
    assert len(decision.unknowns) >= 4, "Safety checklist must list unresolvable physical factors"


def test_fastapi_analyze_non_square_multipart_upload(
    api_client: TestClient,
    tmp_path: Path,
    create_sharp_image: Callable[[int, int, int], Image.Image],
) -> None:
    """Tests the /api/analyze endpoint with an uploaded non-square JPEG and verifies full JSON response schema."""
    # Create non-square 1280x720 JPEG buffer
    img = create_sharp_image(1280, 720, tile=30)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = api_client.post(
        "/api/analyze",
        data={
            "brand": "Toyota",
            "acv": "110000.0",
            "jurisdiction": "uae_50",
            "custom_threshold": "50.0",
        },
        files={"image": ("smartphone_capture.jpg", buf, "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()

    # Validate high-level keys
    assert "quality_gate" in data
    assert "triage" in data
    assert "financials" in data
    assert "image_meta" in data
    assert "polygons" in data
    assert "line_items" in data
    assert "assumptions" in data
    assert "unknowns" in data

    # Validate image_meta dimensions match original non-square dimensions
    assert data["image_meta"]["width"] == 1280
    assert data["image_meta"]["height"] == 720
    assert data["quality_gate"]["accepted"] is True

    # Validate financial currency in AED
    assert data["financials"]["currency"] == "AED"
    assert data["financials"]["acv_aed"] == 110000.0

    # Validate polygons boundaries if any detected
    for poly in data["polygons"]:
        for coord in poly["polygon"]:
            assert 0.0 <= coord[0] <= 1280.0
            assert 0.0 <= coord[1] <= 720.0


def test_gradio_app_analyze_claim_pipeline(
    tmp_path: Path,
    create_sharp_image: Callable[[int, int, int], Image.Image],
) -> None:
    """Tests the analyze_claim entrypoint used by the Gradio web interface."""
    test_path = tmp_path / "gradio_test.jpg"
    img = create_sharp_image(960, 640, tile=25)
    img.save(test_path, format="JPEG")

    outputs = analyze_claim(
        image_path=str(test_path),
        brand_label="Toyota",
        pre_accident_value=90000.0,
        jurisdiction_label="UAE Unified Motor Policy (50% Economic Test)",
        custom_threshold_pct=50.0,
    )

    # analyze_claim returns a 7-tuple:
    # (triage_html, kpi_html, annotated_img, cost_table, policy_html, unknowns_md, assumptions_md)
    assert len(outputs) == 7
    triage_html, kpi_html, annotated_img, cost_table, policy_html, unknowns_md, assumptions_md = (
        outputs
    )

    assert '<div class="triage-card' in triage_html
    assert "kpi-row" in kpi_html
    assert isinstance(annotated_img, Image.Image)
    assert isinstance(cost_table, list)
    assert "policy-box" in policy_html
    assert "### 🔍" in unknowns_md
    assert "AED" in assumptions_md
