"""Spatial association between detected car damages and car components."""

from __future__ import annotations

from shapely.geometry import Polygon
from shapely.validation import make_valid

from claimlens.detection.schemas import (
    STRUCTURAL_PART_NAMES,
    AssociatedDamage,
    DetectedDamage,
    DetectedPart,
)

MIN_OVERLAP_THRESHOLD = 0.05  # 5% overlap threshold to associate damage to a part


def _box_to_polygon(box: tuple[float, float, float, float]) -> Polygon:
    x1, y1, x2, y2 = box
    return Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])


def _safe_polygon(
    pts: list[tuple[float, float]] | None, fallback_box: tuple[float, float, float, float]
) -> Polygon:
    if pts and len(pts) >= 3:
        try:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = make_valid(poly)
            if poly.area > 0:
                return poly
        except (ValueError, TypeError, AttributeError):
            return _box_to_polygon(fallback_box)
    return _box_to_polygon(fallback_box)


def associate_damages_with_parts(
    damages: list[DetectedDamage],
    parts: list[DetectedPart],
    min_overlap: float = MIN_OVERLAP_THRESHOLD,
) -> tuple[list[AssociatedDamage], list[DetectedDamage], bool]:
    """Associate each detected damage with the vehicle part it overlaps most.

    Returns:
        (associated_damages, unassociated_damages, structural_flag)
    """
    associated: list[AssociatedDamage] = []
    unassociated: list[DetectedDamage] = []
    has_structural_damage = False

    part_polygons = [_safe_polygon(p.polygon, p.box) for p in parts]

    for damage in damages:
        dmg_poly = _safe_polygon(damage.polygon, damage.box)
        dmg_area = dmg_poly.area
        if dmg_area <= 0:
            unassociated.append(damage)
            continue

        best_part: DetectedPart | None = None
        best_overlap_ratio = 0.0

        for part, part_poly in zip(parts, part_polygons, strict=False):
            if not dmg_poly.intersects(part_poly):
                continue

            try:
                intersection_area = dmg_poly.intersection(part_poly).area
                overlap_ratio = intersection_area / dmg_area
            except (ValueError, TypeError, AttributeError):
                overlap_ratio = 0.0

            if overlap_ratio > best_overlap_ratio and overlap_ratio >= min_overlap:
                best_overlap_ratio = overlap_ratio
                best_part = part

        if best_part is not None:
            is_structural = (
                best_part.name.lower() in STRUCTURAL_PART_NAMES
            ) or best_part.is_structural
            if is_structural:
                has_structural_damage = True

            associated.append(
                AssociatedDamage(
                    damage=damage,
                    host_part=best_part,
                    overlap_ratio=best_overlap_ratio,
                    is_structural=is_structural,
                )
            )
        else:
            unassociated.append(damage)

    return associated, unassociated, has_structural_damage
