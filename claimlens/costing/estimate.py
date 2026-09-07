"""Transparent, rule-based vehicle visible repair cost estimator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from claimlens.detection.schemas import InspectionResult

DEFAULT_PRICE_TABLE_PATH = Path("data/price_table.json")


@dataclass(frozen=True)
class ItemizedCost:
    part_name: str
    damage_type: str
    action: str  # "repair" or "replace"
    min_cost: float
    max_cost: float
    median_cost: float
    description: str
    is_structural: bool = False


@dataclass
class CostEstimate:
    itemized_costs: list[ItemizedCost] = field(default_factory=list)
    total_min: float = 0.0
    total_max: float = 0.0
    median_estimate: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    has_structural_repair: bool = False


def load_price_table(path: Path | str | None = None) -> dict:
    file_path = Path(path) if path else DEFAULT_PRICE_TABLE_PATH
    if not file_path.exists():
        raise FileNotFoundError(f"Price table not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def estimate_repair_costs(
    inspection: InspectionResult,
    price_table_path: Path | str | None = None,
) -> CostEstimate:
    """Computes transparent, itemized repair cost range from inspection detections.

    Guarantees:
    - Pure rule-based calculation against curated reference pricing.
    - No LLM hallucinations or ungrounded predictions.
    - Every missing or unassociated component is explicitly flagged in assumptions.
    """
    if not inspection.accepted_by_quality_gate:
        return CostEstimate(
            assumptions=[
                f"Image rejected by quality gate ({inspection.quality_gate_reason}). Repair costs cannot be estimated."
            ]
        )

    price_data = load_price_table(price_table_path)
    components_pricing = price_data.get("components", {})
    fallback_pricing = price_data.get("default_fallback", {})

    itemized: list[ItemizedCost] = []
    assumptions: list[str] = []
    has_structural = False

    # Process damages associated with specific components
    for assoc in inspection.associated_damages:
        part = assoc.host_part
        damage = assoc.damage
        part_name = part.name.lower() if part else "unknown"
        dmg_type = damage.name.lower()

        pricing_info = None
        if part_name in components_pricing:
            comp_damages = components_pricing[part_name].get("damages", {})
            pricing_info = comp_damages.get(dmg_type)

        if pricing_info is None:
            pricing_info = fallback_pricing.get(
                dmg_type,
                {
                    "min_cost": 200.0,
                    "max_cost": 500.0,
                    "action": "repair",
                    "description": f"Standard repair for {dmg_type}",
                },
            )
            assumptions.append(
                f"Component '{part_name}' lacks specific tier for '{dmg_type}'; applied default fallback rate."
            )

        min_c = float(pricing_info["min_cost"])
        max_c = float(pricing_info["max_cost"])
        med_c = round((min_c + max_c) / 2.0, 2)
        is_struct = assoc.is_structural

        if is_struct:
            has_structural = True

        itemized.append(
            ItemizedCost(
                part_name=part_name,
                damage_type=dmg_type,
                action=pricing_info.get("action", "repair"),
                min_cost=min_c,
                max_cost=max_c,
                median_cost=med_c,
                description=pricing_info.get("description", ""),
                is_structural=is_struct,
            )
        )

    # Process unassociated damages (detected damage where host part could not be matched)
    for unassoc in inspection.unassociated_damages:
        dmg_type = unassoc.name.lower()
        pricing_info = fallback_pricing.get(
            dmg_type,
            {
                "min_cost": 250.0,
                "max_cost": 600.0,
                "action": "repair",
                "description": f"Standard repair for {dmg_type}",
            },
        )

        min_c = float(pricing_info["min_cost"])
        max_c = float(pricing_info["max_cost"])
        med_c = round((min_c + max_c) / 2.0, 2)

        assumptions.append(
            f"Unidentified panel damage: '{dmg_type}' could not be matched to an identified component; "
            f"priced using average exterior collision repair rates."
        )

        itemized.append(
            ItemizedCost(
                part_name="unidentified_panel",
                damage_type=dmg_type,
                action=pricing_info.get("action", "repair"),
                min_cost=min_c,
                max_cost=max_c,
                median_cost=med_c,
                description=pricing_info.get("description", ""),
                is_structural=False,
            )
        )

    if not itemized:
        return CostEstimate(
            itemized_costs=[],
            total_min=0.0,
            total_max=0.0,
            median_estimate=0.0,
            assumptions=["No visible damage detected on the submitted photo(s)."],
            has_structural_repair=False,
        )

    total_min = round(sum(item.min_cost for item in itemized), 2)
    total_max = round(sum(item.max_cost for item in itemized), 2)
    median_total = round((total_min + total_max) / 2.0, 2)

    # Baseline domain assumptions
    assumptions.append("All estimates reflect visible surface collision damage only.")
    assumptions.append("Paint operations assume standard color blending into adjacent panels.")
    if has_structural:
        assumptions.append(
            "WARNING: Damage detected on structural load-bearing components (e.g. quarter-panel, rocker-panel). Frame pull / unibody alignment may increase costs substantially."
        )
    else:
        assumptions.append("Assumes no underlying mechanical or suspension compromise.")

    return CostEstimate(
        itemized_costs=itemized,
        total_min=total_min,
        total_max=total_max,
        median_estimate=median_total,
        assumptions=assumptions,
        has_structural_repair=has_structural,
    )
