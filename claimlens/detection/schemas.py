"""Typed data schemas for vehicle damage, car parts, and inspection results."""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

# Load-bearing or structural vehicle zones where damage cannot easily be verified
# or indicates potential chassis/frame compromise.
STRUCTURAL_PART_NAMES: set[str] = {
    "quarter-panel",
    "rocker-panel",
    "roof",
    "back-window",  # Structural glass/pillar adjacent
    "windshield",  # Structural A-pillar integrity
}


@dataclass(frozen=True)
class DetectedPart:
    part_id: int
    name: str
    confidence: float
    box: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    polygon: list[tuple[float, float]] | None = None
    is_structural: bool = False


@dataclass(frozen=True)
class DetectedDamage:
    damage_id: int
    name: str
    confidence: float
    box: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    polygon: list[tuple[float, float]] | None = None
    area_ratio: float = 0.0  # Fraction of image or part area covered by damage


@dataclass(frozen=True)
class AssociatedDamage:
    damage: DetectedDamage
    host_part: DetectedPart | None = None
    overlap_ratio: float = 0.0
    is_structural: bool = False


@dataclass
class InspectionResult:
    accepted_by_quality_gate: bool
    quality_gate_reason: str | None = None
    associated_damages: list[AssociatedDamage] = field(default_factory=list)
    unassociated_damages: list[DetectedDamage] = field(default_factory=list)
    all_parts: list[DetectedPart] = field(default_factory=list)
    structural_flag: bool = False
    annotated_image: Image.Image | None = None
