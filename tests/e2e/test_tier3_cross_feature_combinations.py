"""Tier 3: Cross-Feature Combinations E2E Tests.

Validates multi-feature interactions across non-square inputs:
- Full pipeline integration on non-square portrait (1080x1920, 9:16)
- Full pipeline integration on non-square landscape (1920x1080, 16:9)
- Geometric containment: damage polygon contained within host part in original image space
- Coordinate preservation through spatial association -> shoelace area ratio -> AED costing -> triage
- SVG vector overlay coordinates alignment with original image dimensions (no padding artifacts)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from claimlens.costing.estimate import estimate_repair_costs
from claimlens.detection.association import associate_damages_with_parts
from claimlens.detection.infer import (
    extract_damages_from_results,
    extract_parts_from_results,
)
from claimlens.detection.schemas import InspectionResult
from claimlens.triage.decide import TriageOutcome, decide_triage
from tests.e2e.conftest import MockYOLOResult


def _build_svg_polygon_payload(
    inspection: InspectionResult, orig_width: int, orig_height: int
) -> list[dict[str, Any]]:
    """Mirrors the interactive SVG polygon payload format generated in claimlens/api.py."""
    polygons: list[dict[str, Any]] = []

    # 1. Export parts
    for idx, part in enumerate(inspection.all_parts):
        p_id = f"part-{idx}"
        polygons.append(
            {
                "id": p_id,
                "type": "part",
                "label": part.name,
                "confidence": round(part.confidence, 3),
                "box": [round(c, 1) for c in part.box],
                "polygon": (
                    [[round(x, 1), round(y, 1)] for x, y in part.polygon] if part.polygon else []
                ),
                "is_structural": part.is_structural,
            }
        )

    # 2. Export associated damages with host part links
    for idx, assoc in enumerate(inspection.associated_damages):
        d_id = f"dmg-{idx}"
        host_p_id = None
        if assoc.host_part:
            for p_idx, p in enumerate(inspection.all_parts):
                if p.name == assoc.host_part.name and p.box == assoc.host_part.box:
                    host_p_id = f"part-{p_idx}"
                    break

        polygons.append(
            {
                "id": d_id,
                "type": "damage",
                "label": assoc.damage.name,
                "confidence": round(assoc.damage.confidence, 3),
                "box": [round(c, 1) for c in assoc.damage.box],
                "polygon": (
                    [[round(x, 1), round(y, 1)] for x, y in assoc.damage.polygon]
                    if assoc.damage.polygon
                    else []
                ),
                "area_ratio": round(assoc.damage.area_ratio, 4),
                "host_part_id": host_p_id,
                "is_structural": assoc.is_structural,
            }
        )

    return polygons


def test_portrait_full_flow_inspect_to_svg(
    tmp_path: Path,
    create_sharp_image: Callable[[int, int, int], Image.Image],
    mock_yolo_result_factory: Callable[..., MockYOLOResult],
) -> None:
    """Verifies complete portrait (1080x1920) flow: inspection -> association -> costing -> SVG."""
    # 1. Create a sharp portrait image (1080x1920)
    portrait_path = tmp_path / "portrait_vehicle.jpg"
    img = create_sharp_image(1080, 1920, tile=40)
    img.save(portrait_path, format="JPEG")

    # 2. Mock part (hood) in original portrait coordinate space [100, 300, 980, 1100]
    hood_box = [100.0, 300.0, 980.0, 1100.0]
    hood_poly = [
        [100.0, 300.0],
        [980.0, 300.0],
        [980.0, 1100.0],
        [100.0, 1100.0],
    ]
    parts_res = mock_yolo_result_factory(
        boxes_xyxy=[hood_box],
        scores=[0.92],
        class_ids=[1],
        polygons=[hood_poly],
        names={1: "hood"},
    )
    parts = extract_parts_from_results([parts_res])

    # 3. Mock damage (dent) located squarely on the hood [300, 500, 600, 800]
    dent_box = [300.0, 500.0, 600.0, 800.0]
    dent_poly = [
        [300.0, 500.0],
        [600.0, 500.0],
        [600.0, 800.0],
        [300.0, 800.0],
    ]
    damages_res = mock_yolo_result_factory(
        boxes_xyxy=[dent_box],
        scores=[0.88],
        class_ids=[1],
        polygons=[dent_poly],
        names={1: "dent"},
    )
    damages = extract_damages_from_results([damages_res], (1080, 1920))

    # 4. Spatial Association in portrait space
    associated, unassociated, structural_flag = associate_damages_with_parts(damages, parts)

    assert len(associated) == 1, "Dent on hood must be successfully associated"
    assert len(unassociated) == 0
    assert associated[0].host_part is not None
    assert associated[0].host_part.name == "hood"
    assert structural_flag is False

    # 5. Area ratio validation in portrait space
    # Shoelace area: (600-300) * (800-500) = 300 * 300 = 90,000 px^2
    # Image area: 1080 * 1920 = 2,073,600 px^2 -> ratio = 90,000 / 2,073,600 ~= 0.0434
    expected_ratio = 90000.0 / (1080.0 * 1920.0)
    assert associated[0].damage.area_ratio == pytest.approx(expected_ratio, rel=1e-3)

    # 6. Costing and Triage
    inspection = InspectionResult(
        accepted_by_quality_gate=True,
        associated_damages=associated,
        unassociated_damages=unassociated,
        all_parts=parts,
        structural_flag=structural_flag,
    )
    estimate = estimate_repair_costs(inspection, brand="Toyota")
    assert estimate.median_estimate > 0.0

    decision = decide_triage(inspection, estimate, pre_accident_value=120000.0, preset_id="uae_50")
    assert decision.outcome == TriageOutcome.PROBABLY_REPAIRABLE

    # 7. Interactive SVG Overlay Output Payload Verification
    svg_payload = _build_svg_polygon_payload(inspection, 1080, 1920)
    assert len(svg_payload) == 2  # 1 part, 1 damage

    part_svg = next(p for p in svg_payload if p["type"] == "part")
    dmg_svg = next(p for p in svg_payload if p["type"] == "damage")

    # Verify coordinates respect portrait dimensions [0, 1080] x [0, 1920]
    for pt in part_svg["polygon"]:
        assert 0.0 <= pt[0] <= 1080.0
        assert 0.0 <= pt[1] <= 1920.0

    for pt in dmg_svg["polygon"]:
        assert 0.0 <= pt[0] <= 1080.0
        assert 0.0 <= pt[1] <= 1920.0

    assert dmg_svg["host_part_id"] == part_svg["id"]


def test_landscape_full_flow_inspect_to_svg(
    tmp_path: Path,
    create_sharp_image: Callable[[int, int, int], Image.Image],
    mock_yolo_result_factory: Callable[..., MockYOLOResult],
) -> None:
    """Verifies complete landscape (1920x1080, 16:9) flow with multiple damaged panels."""
    img_size = (1920, 1080)

    # Parts: front-bumper [200, 600, 1720, 1000] and hood [400, 200, 1520, 650]
    parts_res = mock_yolo_result_factory(
        boxes_xyxy=[
            [200.0, 600.0, 1720.0, 1000.0],
            [400.0, 200.0, 1520.0, 650.0],
        ],
        scores=[0.95, 0.91],
        class_ids=[0, 1],
        polygons=[
            [[200.0, 600.0], [1720.0, 600.0], [1720.0, 1000.0], [200.0, 1000.0]],
            [[400.0, 200.0], [1520.0, 200.0], [1520.0, 650.0], [400.0, 650.0]],
        ],
        names={0: "front-bumper", 1: "hood"},
    )
    parts = extract_parts_from_results([parts_res])

    # Damages: scratch on bumper [500, 700, 900, 800] and dent on hood [800, 300, 1100, 500]
    damages_res = mock_yolo_result_factory(
        boxes_xyxy=[
            [500.0, 700.0, 900.0, 800.0],
            [800.0, 300.0, 1100.0, 500.0],
        ],
        scores=[0.89, 0.84],
        class_ids=[4, 1],  # 4=scratch, 1=dent
        polygons=[
            [[500.0, 700.0], [900.0, 700.0], [900.0, 800.0], [500.0, 800.0]],
            [[800.0, 300.0], [1100.0, 300.0], [1100.0, 500.0], [800.0, 500.0]],
        ],
        names={4: "scratch", 1: "dent"},
    )
    damages = extract_damages_from_results([damages_res], img_size)

    associated, unassociated, structural_flag = associate_damages_with_parts(damages, parts)
    assert len(associated) == 2
    assert len(unassociated) == 0

    inspection = InspectionResult(
        accepted_by_quality_gate=True,
        associated_damages=associated,
        unassociated_damages=unassociated,
        all_parts=parts,
        structural_flag=structural_flag,
    )
    estimate = estimate_repair_costs(inspection, brand="Nissan")
    assert len(estimate.itemized_costs) == 2

    # Verify SVG payload links both damages to their distinct host parts
    svg_payload = _build_svg_polygon_payload(inspection, 1920, 1080)
    dmg_items = [p for p in svg_payload if p["type"] == "damage"]
    assert len(dmg_items) == 2
    host_ids = {d["host_part_id"] for d in dmg_items}
    assert len(host_ids) == 2, "Each damage should map to its respective host part"
