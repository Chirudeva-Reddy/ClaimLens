"""Configurable economic total-loss thresholds and regional regulatory presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdPreset:
    id: str
    name: str
    threshold: float  # Fraction of pre-accident value (e.g. 0.50 = 50%)
    jurisdiction: str
    citation: str
    description: str


PRESETS: dict[str, ThresholdPreset] = {
    "uae_50": ThresholdPreset(
        id="uae_50",
        name="UAE Unified Motor Policy (50%)",
        threshold=0.50,
        jurisdiction="United Arab Emirates",
        citation="CBUAE Unified Motor Vehicle Insurance Policy (Comprehensive), Chapter 1, Article 7",
        description=(
            "Vehicle is deemed a constructive total loss if estimated repair costs exceed 50% "
            "of the insured vehicle value, or if damage causes irreparable chassis/structural deformation."
        ),
    ),
    "us_70": ThresholdPreset(
        id="us_70",
        name="US Common Total Loss Formula (70%)",
        threshold=0.70,
        jurisdiction="United States (Multi-State Standard)",
        citation="Common State Insurance Code Benchmark (e.g. TX, CA salvage benchmarks)",
        description=(
            "Standard economic threshold flagging vehicles for total-loss salvage review when "
            "repair cost exceeds 70% of actual cash value (ACV)."
        ),
    ),
    "us_75": ThresholdPreset(
        id="us_75",
        name="US Strict Statutory Threshold (75%)",
        threshold=0.75,
        jurisdiction="United States (FL, NY, OH)",
        citation="State Insurance Statutes (e.g. Florida Stat. § 319.30, New York Title 11)",
        description=(
            "Strict statutory ceiling requiring total-loss declaration once repair estimates "
            "reach or exceed 75% of pre-accident vehicle valuation."
        ),
    ),
    "uk_60": ThresholdPreset(
        id="uk_60",
        name="UK Market Guideline (60%)",
        threshold=0.60,
        jurisdiction="United Kingdom",
        citation="Association of British Insurers (ABI) Code of Practice for Motor Salvage",
        description=(
            "Guideline threshold where repair costs approaching 60% of pre-accident value "
            "trigger Category S (structurally repairable) or Category N total-loss write-off review."
        ),
    ),
}

DEFAULT_PRESET_ID = "uae_50"


def get_preset(preset_id: str | None = None) -> ThresholdPreset:
    """Retrieve a threshold preset by ID, falling back to the default."""
    if not preset_id:
        return PRESETS[DEFAULT_PRESET_ID]
    key = preset_id.lower().strip()
    if key not in PRESETS:
        raise ValueError(
            f"Unknown threshold preset '{preset_id}'. Available presets: {list(PRESETS.keys())}"
        )
    return PRESETS[key]
