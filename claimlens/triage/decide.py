"""Explainable Total-Loss Triage Decision Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from claimlens.costing.estimate import CostEstimate
from claimlens.detection.schemas import InspectionResult
from claimlens.triage.thresholds import ThresholdPreset, get_preset


class TriageOutcome(str, Enum):
    PROBABLY_REPAIRABLE = "PROBABLY_REPAIRABLE"
    PROBABLE_TOTAL_LOSS_REVIEW = "PROBABLE_TOTAL_LOSS_REVIEW"
    INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED = "INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED"


STANDARD_UNKNOWN_FACTORS: list[str] = [
    "Underlying unibody frame rail straightness and laser alignment",
    "Suspension geometry, steering linkage, and subframe integrity",
    "Internal powertrain, radiator core, and cooling line damage",
    "Supplemental Restraint System (SRS) airbag sensors and pretensioners",
    "Hidden electrical wiring harnesses and ADAS sensor calibration",
]


@dataclass
class TriageDecision:
    outcome: TriageOutcome
    economic_ratio: float
    threshold_applied: float
    preset_used: ThresholdPreset
    pre_accident_value: float
    estimated_cost_range: tuple[float, float]
    median_estimate: float
    structural_damage_flag: bool
    confidence_floor_tripped: bool
    rule_applied: str
    reasoning: str
    unknowns: list[str] = field(default_factory=list)
    detected_components: list[str] = field(default_factory=list)


def compute_economic_ratio(estimated_repair_cost: float, pre_accident_value: float) -> float:
    """Repair cost as a fraction of pre-accident value; the core economic input."""
    if pre_accident_value <= 0:
        raise ValueError("pre_accident_value must be positive and greater than zero")
    return round(estimated_repair_cost / pre_accident_value, 4)


def decide_triage(
    inspection: InspectionResult,
    estimate: CostEstimate,
    pre_accident_value: float,
    preset_id: str | None = None,
    custom_threshold: float | None = None,
    confidence_floor: float = 0.30,
) -> TriageDecision:
    """Evaluates triage decision following Blueprint §4 and §9.

    Branching Hierarchy:
    1. Input validation (positive vehicle value).
    2. Quality Gate check (reject unusable/blurry photos).
    3. Structural / Load-bearing damage check (quarter-panel, rocker-panel, roof, pillars).
    4. Model confidence floor check (abstain on ambiguous detections).
    5. Economic ratio vs. configured regulatory threshold.
    """
    if pre_accident_value <= 0:
        raise ValueError("pre_accident_value must be positive and greater than zero")

    preset = get_preset(preset_id)
    threshold = custom_threshold if custom_threshold is not None else preset.threshold

    economic_ratio = compute_economic_ratio(estimate.median_estimate, pre_accident_value)
    cost_range = (estimate.total_min, estimate.total_max)
    detected_summary: list[str] = []

    for assoc in inspection.associated_damages:
        part_str = assoc.host_part.name if assoc.host_part else "unknown panel"
        detected_summary.append(
            f"{assoc.damage.name} on {part_str} (conf={assoc.damage.confidence:.2f})"
        )
    for unassoc in inspection.unassociated_damages:
        detected_summary.append(
            f"{unassoc.name} on unidentified panel (conf={unassoc.confidence:.2f})"
        )

    unknowns = list(STANDARD_UNKNOWN_FACTORS)

    # 1. Quality Gate Failure Path
    if not inspection.accepted_by_quality_gate:
        reason = inspection.quality_gate_reason or "unspecified quality failure"
        return TriageDecision(
            outcome=TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED,
            economic_ratio=0.0,
            threshold_applied=threshold,
            preset_used=preset,
            pre_accident_value=pre_accident_value,
            estimated_cost_range=(0.0, 0.0),
            median_estimate=0.0,
            structural_damage_flag=False,
            confidence_floor_tripped=False,
            rule_applied="IMAGE_QUALITY_GATE_REJECTION",
            reasoning=(
                f"Photo evidence rejected by quality gate ({reason}). "
                "Clear, high-resolution photographs are mandatory for automated triage assessment."
            ),
            unknowns=unknowns + ["Entire exterior condition unresolvable due to image rejection"],
            detected_components=[],
        )

    # 2. Structural Damage / Safe Abstention Path
    if inspection.structural_flag or estimate.has_structural_repair:
        return TriageDecision(
            outcome=TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED,
            economic_ratio=economic_ratio,
            threshold_applied=threshold,
            preset_used=preset,
            pre_accident_value=pre_accident_value,
            estimated_cost_range=cost_range,
            median_estimate=estimate.median_estimate,
            structural_damage_flag=True,
            confidence_floor_tripped=False,
            rule_applied="STRUCTURAL_INTEGRITY_SAFE_ABSTENTION",
            reasoning=(
                "Visible collision damage intersects load-bearing structural zones (e.g. quarter-panel, "
                "rocker-panel, roof, or unibody pillars). Structural chassis straightness and crumple zone "
                "integrity cannot be confirmed from 2D photographs; physical laser-measured bench inspection "
                "is strictly recommended before any total-loss or repair determination."
            ),
            unknowns=unknowns
            + ["Chassis rail deformation degree", "C-pillar / D-pillar structural weld integrity"],
            detected_components=detected_summary,
        )

    # 3. Calibrated Confidence Floor Path
    low_confidence_detections = [
        assoc.damage
        for assoc in inspection.associated_damages
        if assoc.damage.confidence < confidence_floor
    ] + [
        unassoc
        for unassoc in inspection.unassociated_damages
        if unassoc.confidence < confidence_floor
    ]

    if low_confidence_detections:
        names = ", ".join(d.name for d in low_confidence_detections)
        return TriageDecision(
            outcome=TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED,
            economic_ratio=economic_ratio,
            threshold_applied=threshold,
            preset_used=preset,
            pre_accident_value=pre_accident_value,
            estimated_cost_range=cost_range,
            median_estimate=estimate.median_estimate,
            structural_damage_flag=False,
            confidence_floor_tripped=True,
            rule_applied="CALIBRATED_CONFIDENCE_FLOOR_ABSTENTION",
            reasoning=(
                f"Model detection confidence on damage category ({names}) is below the calibrated certainty "
                f"floor ({confidence_floor:.0%}). Visual glare, lighting, or resolution ambiguity requires "
                "in-person adjuster verification to avoid premature automated classification."
            ),
            unknowns=unknowns + [f"True severity of low-confidence features ({names})"],
            detected_components=detected_summary,
        )

    # 4. Economic Total Loss Review Path
    if economic_ratio >= threshold:
        return TriageDecision(
            outcome=TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW,
            economic_ratio=economic_ratio,
            threshold_applied=threshold,
            preset_used=preset,
            pre_accident_value=pre_accident_value,
            estimated_cost_range=cost_range,
            median_estimate=estimate.median_estimate,
            structural_damage_flag=False,
            confidence_floor_tripped=False,
            rule_applied="ECONOMIC_THRESHOLD_EXCEEDED",
            reasoning=(
                f"Estimated visible repair cost (${estimate.median_estimate:,.2f}) represents {economic_ratio:.1%} "
                f"of the pre-accident vehicle value (${pre_accident_value:,.2f}), crossing the {threshold:.0%} "
                f"economic threshold specified under {preset.name}. Formal total-loss salvage review is recommended."
            ),
            unknowns=unknowns,
            detected_components=detected_summary,
        )

    # 5. Probably Repairable Path
    return TriageDecision(
        outcome=TriageOutcome.PROBABLY_REPAIRABLE,
        economic_ratio=economic_ratio,
        threshold_applied=threshold,
        preset_used=preset,
        pre_accident_value=pre_accident_value,
        estimated_cost_range=cost_range,
        median_estimate=estimate.median_estimate,
        structural_damage_flag=False,
        confidence_floor_tripped=False,
        rule_applied="ECONOMIC_REPAIRABLE_WITHIN_THRESHOLD",
        reasoning=(
            f"Estimated visible repair cost (${estimate.median_estimate:,.2f}) represents {economic_ratio:.1%} "
            f"of vehicle value (${pre_accident_value:,.2f}), remaining comfortably below the {threshold:.0%} "
            f"total-loss review threshold under {preset.name}, with no structural load-bearing compromises observed."
        ),
        unknowns=unknowns,
        detected_components=detected_summary,
    )
