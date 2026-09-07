import pytest

from claimlens.costing.estimate import CostEstimate, ItemizedCost
from claimlens.detection.schemas import (
    AssociatedDamage,
    DetectedDamage,
    DetectedPart,
    InspectionResult,
)
from claimlens.triage.decide import (
    TriageOutcome,
    compute_economic_ratio,
    decide_triage,
)


def _make_sample_inspection(
    damage_name="scratch",
    part_name="front-bumper",
    confidence=0.90,
    is_structural=False,
    accepted=True,
    quality_reason=None,
) -> InspectionResult:
    if not accepted:
        return InspectionResult(accepted_by_quality_gate=False, quality_gate_reason=quality_reason)

    part = DetectedPart(
        part_id=0,
        name=part_name,
        confidence=0.95,
        box=(0.0, 0.0, 100.0, 100.0),
        is_structural=is_structural,
    )
    damage = DetectedDamage(
        damage_id=1,
        name=damage_name,
        confidence=confidence,
        box=(10.0, 10.0, 50.0, 50.0),
    )
    assoc = AssociatedDamage(
        damage=damage,
        host_part=part,
        overlap_ratio=1.0,
        is_structural=is_structural,
    )
    return InspectionResult(
        accepted_by_quality_gate=True,
        associated_damages=[assoc],
        structural_flag=is_structural,
    )


def test_invalid_vehicle_value_raises_value_error():
    inspection = _make_sample_inspection()
    estimate = CostEstimate(total_min=100.0, total_max=300.0, median_estimate=200.0)

    with pytest.raises(ValueError, match="pre_accident_value must be positive"):
        decide_triage(inspection, estimate, pre_accident_value=0.0)

    with pytest.raises(ValueError, match="pre_accident_value must be positive"):
        decide_triage(inspection, estimate, pre_accident_value=-5000.0)


def test_compute_economic_ratio():
    assert compute_economic_ratio(5000.0, 10000.0) == 0.50
    assert compute_economic_ratio(7500.0, 10000.0) == 0.75
    assert compute_economic_ratio(1200.0, 20000.0) == 0.06


def test_quality_gate_rejection_triggers_insufficient_evidence():
    inspection = _make_sample_inspection(accepted=False, quality_reason="too_blurry")
    estimate = CostEstimate(assumptions=["Image rejected"])

    decision = decide_triage(inspection, estimate, pre_accident_value=15000.0)

    assert decision.outcome == TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
    assert decision.rule_applied == "IMAGE_QUALITY_GATE_REJECTION"
    assert "too_blurry" in decision.reasoning
    assert len(decision.unknowns) > 0


def test_structural_damage_triggers_safe_abstention():
    # Damage on load-bearing quarter panel
    inspection = _make_sample_inspection(
        damage_name="dent",
        part_name="quarter-panel",
        is_structural=True,
    )
    item = ItemizedCost(
        part_name="quarter-panel",
        damage_type="dent",
        action="repair",
        min_cost=600.0,
        max_cost=1400.0,
        median_cost=1000.0,
        description="Unibody metalwork",
        is_structural=True,
    )
    estimate = CostEstimate(
        itemized_costs=[item],
        total_min=600.0,
        total_max=1400.0,
        median_estimate=1000.0,
        has_structural_repair=True,
    )

    # Even though $1,000 on a $50,000 car is only 2%, structural damage requires abstention
    decision = decide_triage(inspection, estimate, pre_accident_value=50000.0)

    assert decision.outcome == TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
    assert decision.structural_damage_flag
    assert decision.rule_applied == "STRUCTURAL_INTEGRITY_SAFE_ABSTENTION"
    assert "quarter-panel" in decision.reasoning or "structural" in decision.reasoning
    assert any("Chassis" in u for u in decision.unknowns)


def test_confidence_floor_abstention():
    # Damage detected with very low confidence (e.g. 0.22 < 0.30 floor)
    inspection = _make_sample_inspection(confidence=0.22)
    estimate = CostEstimate(total_min=200.0, total_max=400.0, median_estimate=300.0)

    decision = decide_triage(inspection, estimate, pre_accident_value=20000.0)

    assert decision.outcome == TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
    assert decision.confidence_floor_tripped
    assert decision.rule_applied == "CALIBRATED_CONFIDENCE_FLOOR_ABSTENTION"
    assert "calibrated certainty floor" in decision.reasoning


def test_economic_total_loss_review_when_ratio_exceeds_threshold():
    # Minor front bumper, but repair cost is $6,000 on a $10,000 car (60% > 50% UAE threshold)
    inspection = _make_sample_inspection(damage_name="dent", part_name="front-bumper")
    estimate = CostEstimate(
        total_min=5000.0,
        total_max=7000.0,
        median_estimate=6000.0,
        has_structural_repair=False,
    )

    decision = decide_triage(
        inspection,
        estimate,
        pre_accident_value=10000.0,
        preset_id="uae_50",
    )

    assert decision.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW
    assert decision.economic_ratio == 0.60
    assert decision.threshold_applied == 0.50
    assert decision.rule_applied == "ECONOMIC_THRESHOLD_EXCEEDED"
    assert "60.0%" in decision.reasoning
    assert len(decision.unknowns) > 0


def test_probably_repairable_when_within_threshold():
    # Visible repair cost is $1,200 on a $25,000 car (4.8% << 50%)
    inspection = _make_sample_inspection(damage_name="scratch", part_name="front-door")
    estimate = CostEstimate(
        total_min=800.0,
        total_max=1600.0,
        median_estimate=1200.0,
        has_structural_repair=False,
    )

    decision = decide_triage(
        inspection,
        estimate,
        pre_accident_value=25000.0,
        preset_id="uae_50",
    )

    assert decision.outcome == TriageOutcome.PROBABLY_REPAIRABLE
    assert decision.economic_ratio == 0.048
    assert decision.rule_applied == "ECONOMIC_REPAIRABLE_WITHIN_THRESHOLD"
    assert "comfortably below" in decision.reasoning
    assert not decision.structural_damage_flag


def test_regional_presets_and_custom_threshold():
    inspection = _make_sample_inspection(damage_name="dent", part_name="hood")
    # Repair estimate = $6,500 on $10,000 car (ratio = 65%)
    estimate = CostEstimate(
        total_min=6000.0,
        total_max=7000.0,
        median_estimate=6500.0,
        has_structural_repair=False,
    )

    # 1. Under UAE 50%: 65% >= 50% -> TOTAL LOSS
    uae_dec = decide_triage(inspection, estimate, pre_accident_value=10000.0, preset_id="uae_50")
    assert uae_dec.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW

    # 2. Under US 70%: 65% < 70% -> REPAIRABLE
    us_dec = decide_triage(inspection, estimate, pre_accident_value=10000.0, preset_id="us_70")
    assert us_dec.outcome == TriageOutcome.PROBABLY_REPAIRABLE

    # 3. Custom threshold 60%: 65% >= 60% -> TOTAL LOSS
    custom_dec = decide_triage(
        inspection, estimate, pre_accident_value=10000.0, custom_threshold=0.60
    )
    assert custom_dec.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW
    assert custom_dec.threshold_applied == 0.60
