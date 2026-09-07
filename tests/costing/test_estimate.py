from claimlens.costing.estimate import estimate_repair_costs
from claimlens.detection.schemas import (
    AssociatedDamage,
    DetectedDamage,
    DetectedPart,
    InspectionResult,
)


def test_estimate_empty_damages():
    inspection = InspectionResult(accepted_by_quality_gate=True)
    estimate = estimate_repair_costs(inspection)

    assert estimate.total_min == 0.0
    assert estimate.total_max == 0.0
    assert estimate.median_estimate == 0.0
    assert not estimate.has_structural_repair
    assert any("No visible damage" in a for a in estimate.assumptions)


def test_estimate_single_component_damage():
    part = DetectedPart(
        part_id=0,
        name="front-bumper",
        confidence=0.92,
        box=(0.0, 0.0, 100.0, 100.0),
        is_structural=False,
    )
    damage = DetectedDamage(
        damage_id=4,
        name="scratch",
        confidence=0.88,
        box=(10.0, 10.0, 50.0, 50.0),
    )
    assoc = AssociatedDamage(damage=damage, host_part=part, is_structural=False)

    inspection = InspectionResult(
        accepted_by_quality_gate=True,
        associated_damages=[assoc],
    )
    estimate = estimate_repair_costs(inspection)

    assert len(estimate.itemized_costs) == 1
    item = estimate.itemized_costs[0]
    assert item.part_name == "front-bumper"
    assert item.damage_type == "scratch"
    assert item.min_cost == 180.0
    assert item.max_cost == 380.0
    assert item.action == "repair"
    assert estimate.total_min == 180.0
    assert estimate.total_max == 380.0
    assert estimate.median_estimate == 280.0
    assert not estimate.has_structural_repair


def test_estimate_structural_damage_flags_and_costs():
    part = DetectedPart(
        part_id=7,
        name="quarter-panel",
        confidence=0.85,
        box=(0.0, 0.0, 100.0, 100.0),
        is_structural=True,
    )
    damage = DetectedDamage(
        damage_id=0,
        name="crack",
        confidence=0.80,
        box=(20.0, 20.0, 60.0, 60.0),
    )
    assoc = AssociatedDamage(damage=damage, host_part=part, is_structural=True)

    inspection = InspectionResult(
        accepted_by_quality_gate=True,
        associated_damages=[assoc],
        structural_flag=True,
    )
    estimate = estimate_repair_costs(inspection)

    assert estimate.has_structural_repair
    assert estimate.total_min == 2500.0
    assert estimate.total_max == 4800.0
    assert estimate.itemized_costs[0].action == "replace"
    assert any("WARNING: Damage detected on structural" in a for a in estimate.assumptions)


def test_estimate_unassociated_damage_fallback():
    unassoc_damage = DetectedDamage(
        damage_id=1,
        name="dent",
        confidence=0.78,
        box=(100.0, 100.0, 150.0, 150.0),
    )
    inspection = InspectionResult(
        accepted_by_quality_gate=True,
        unassociated_damages=[unassoc_damage],
    )
    estimate = estimate_repair_costs(inspection)

    assert len(estimate.itemized_costs) == 1
    assert estimate.itemized_costs[0].part_name == "unidentified_panel"
    assert estimate.total_min == 250.0
    assert estimate.total_max == 600.0
    assert any("Unidentified panel damage" in a for a in estimate.assumptions)


def test_estimate_rejected_quality_gate():
    inspection = InspectionResult(
        accepted_by_quality_gate=False,
        quality_gate_reason="too_blurry",
    )
    estimate = estimate_repair_costs(inspection)

    assert estimate.total_min == 0.0
    assert estimate.total_max == 0.0
    assert any("rejected by quality gate" in a for a in estimate.assumptions)
