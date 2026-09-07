"""ClaimLens FastAPI Application.

High-performance REST service providing computer vision inspection,
polygon vector extraction, deterministic AED costing, CBUAE policy retrieval,
and instant economic loss simulation.
"""

from __future__ import annotations

import base64
import contextlib
import io
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from claimlens.costing.estimate import CostEstimate, estimate_repair_costs
from claimlens.detection.infer import inspect_vehicle
from claimlens.detection.schemas import InspectionResult
from claimlens.policy.retrieve import retrieve_policy_guidance
from claimlens.quality_gate.gate import check_image_quality
from claimlens.triage.decide import TriageDecision, TriageOutcome, decide_triage
from claimlens.triage.thresholds import get_preset

SCENARIOS: dict[str, dict[str, Any]] = {
    "case_a": {
        "id": "case_a",
        "title": "Scenario A: Minor Surface Scratch & Dent",
        "badge": "Repairable Benchmark",
        "brand": "Toyota",
        "acv": 120000.0,
        "jurisdiction": "uae_50",
        "custom_threshold": 50.0,
        "image_path": "data/demo_examples/case_a_repairable.jpg",
        "description": "Single bumper scrape on a late-model Toyota Camry. Clear economic repairability under UAE 50% rule.",
    },
    "case_b": {
        "id": "case_b",
        "title": "Scenario B: Multi-Panel Severe Collision",
        "badge": "Total Loss Trigger",
        "brand": "General Market Standard",
        "acv": 15000.0,
        "jurisdiction": "uae_50",
        "custom_threshold": 50.0,
        "image_path": "data/demo_examples/case_b_total_loss.jpg",
        "description": "Multi-panel severe front-end impact on an older vehicle. Repair cost exceeds 80% of ACV.",
    },
    "case_c": {
        "id": "case_c",
        "title": "Scenario C: Quarter-Panel Unibody Impact",
        "badge": "Structural Safe Abstention",
        "brand": "Toyota",
        "acv": 85000.0,
        "jurisdiction": "uae_50",
        "custom_threshold": 50.0,
        "image_path": "data/demo_examples/case_c_structural_inspection.jpg",
        "description": "Impact directly compromising the rear quarter panel and unibody pillar. Requires physical teardown.",
    },
}

app = FastAPI(
    title="ClaimLens Enterprise Insurtech API",
    description="Explainable, two-stage vehicle damage and total-loss triage platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecalculateRequest(BaseModel):
    repair_cost_median_aed: float = Field(ge=0, allow_inf_nan=False)
    acv_aed: float = Field(gt=0, allow_inf_nan=False)
    jurisdiction: Literal["uae_50", "us_70", "us_75", "uk_60", "custom"] = "uae_50"
    custom_threshold: float = Field(default=50.0, ge=10, le=100, allow_inf_nan=False)
    structural_risk_flag: bool = False
    has_line_items: bool = True


def _image_to_base64(img: Image.Image, format: str = "JPEG", quality: int = 85) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format=format, quality=quality)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def _format_triage_ui(decision: TriageDecision) -> dict[str, Any]:
    if decision.outcome == TriageOutcome.PROBABLY_REPAIRABLE:
        return {
            "outcome": decision.outcome.value,
            "headline": "ECONOMICALLY REPAIRABLE",
            "status_color": "emerald",
            "icon": "✅",
            "summary_reason": decision.reasoning,
            "recommended_action": "Issue digital repair authorization to certified bodyshop network.",
        }
    if decision.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW:
        return {
            "outcome": decision.outcome.value,
            "headline": "CONSTRUCTIVE TOTAL LOSS REVIEW",
            "status_color": "ruby",
            "icon": "🚨",
            "summary_reason": decision.reasoning,
            "recommended_action": "Initiate salvage valuation and total-loss settlement workflow.",
        }
    return {
        "outcome": decision.outcome.value,
        "headline": "PHYSICAL TEARDOWN INSPECTION MANDATED",
        "status_color": "amber",
        "icon": "⚠️",
        "summary_reason": decision.reasoning,
        "recommended_action": "Dispatch accredited field appraiser for physical inspection.",
    }


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ClaimLens Insurtech Platform", "version": "1.0.0"}


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "badge": s["badge"],
            "brand": s["brand"],
            "acv": s["acv"],
            "jurisdiction": s["jurisdiction"],
            "custom_threshold": s["custom_threshold"],
            "description": s["description"],
            "image_url": f"/api/scenarios/{s['id']}/image",
        }
        for s in SCENARIOS.values()
    ]


@app.get("/api/scenarios/{case_id}/image")
def get_scenario_image(case_id: str) -> FileResponse:
    scenario = SCENARIOS.get(case_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    path = Path(scenario["image_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image file not found: {path}")
    return FileResponse(path, media_type="image/jpeg")


@app.post("/api/recalculate")
def recalculate_loss_ratio(req: RecalculateRequest) -> dict[str, Any]:
    """Instant 0ms recalculation of total loss thresholds and decision."""
    threshold = (
        req.custom_threshold
        if req.jurisdiction == "custom"
        else get_preset(req.jurisdiction).threshold * 100.0
    )
    acv = req.acv_aed
    loss_ratio_pct = (req.repair_cost_median_aed / acv) * 100.0

    if req.structural_risk_flag:
        outcome = TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
        headline = "PHYSICAL TEARDOWN INSPECTION MANDATED"
        status_color = "amber"
        icon = "⚠️"
        summary = "Potential unibody/structural damage detected. Camera-only estimation cannot guarantee chassis integrity."
        action = "Dispatch accredited field appraiser for laser chassis alignment check."
    elif not req.has_line_items:
        outcome = TriageOutcome.INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED
        headline = "INSUFFICIENT EVIDENCE DETECTED"
        status_color = "amber"
        icon = "⚠️"
        summary = "No visible collision damage associated with recognized body panels."
        action = "Request supplementary collision documentation or physical inspection."
    elif loss_ratio_pct >= threshold:
        outcome = TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW
        headline = "CONSTRUCTIVE TOTAL LOSS REVIEW"
        status_color = "ruby"
        icon = "🚨"
        summary = f"Estimated repair cost of AED {req.repair_cost_median_aed:,.2f} represents {loss_ratio_pct:.1f}% of Pre-Accident Cash Value (threshold: {threshold:.0f}%)."
        action = "Initiate salvage valuation and total-loss settlement workflow."
    else:
        outcome = TriageOutcome.PROBABLY_REPAIRABLE
        headline = "ECONOMICALLY REPAIRABLE"
        status_color = "emerald"
        icon = "✅"
        summary = f"Estimated visible repair cost of AED {req.repair_cost_median_aed:,.2f} represents {loss_ratio_pct:.1f}% of Pre-Accident Cash Value (threshold: {threshold:.0f}%)."
        action = "Issue digital repair authorization to certified bodyshop network."

    return {
        "outcome": outcome.value,
        "headline": headline,
        "status_color": status_color,
        "icon": icon,
        "summary_reason": summary,
        "recommended_action": action,
        "financials": {
            "repair_cost_median_aed": round(req.repair_cost_median_aed, 2),
            "acv_aed": round(acv, 2),
            "loss_ratio_pct": round(loss_ratio_pct, 2),
            "threshold_pct": round(threshold, 2),
            "is_total_loss": outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW,
            "currency": "AED",
        },
    }


@app.post("/api/analyze")
async def analyze_claim_endpoint(
    image: Annotated[UploadFile | None, File()] = None,
    scenario_id: Annotated[str | None, Form()] = None,
    brand: Annotated[str, Form()] = "Toyota",
    acv: Annotated[float, Form()] = 120000.0,
    jurisdiction: Annotated[str, Form()] = "uae_50",
    custom_threshold: Annotated[float, Form()] = 50.0,
) -> JSONResponse:
    """End-to-end multi-stage inspection, polygon extraction, costing, and policy retrieval."""
    temp_path: Path | None = None
    try:
        if scenario_id and scenario_id in SCENARIOS:
            source_path = Path(SCENARIOS[scenario_id]["image_path"])
            if not source_path.exists():
                raise HTTPException(status_code=404, detail=f"Scenario image not found: {source_path}")
            active_image_path = source_path
        elif image is not None:
            suffix = Path(image.filename or "upload.jpg").suffix or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await image.read()
                tmp.write(content)
                temp_path = Path(tmp.name)
            active_image_path = temp_path
        else:
            raise HTTPException(status_code=400, detail="Either an image upload or a scenario_id is required.")

        # Stage 1: Quality Gate
        gate_result = check_image_quality(active_image_path)
        if not gate_result.accepted:
            reason_str = gate_result.reason or "image_quality_failed"
            if reason_str == "too_blurry":
                guidance = "Capture a sharper photo with proper focus and illumination."
            elif reason_str == "resolution_too_low":
                guidance = "Upload an image with at least 640x480 resolution."
            else:
                guidance = "Upload a valid readable collision photograph (JPEG, PNG, WEBP)."

            return JSONResponse(
                status_code=200,
                content={
                    "quality_gate": {
                        "accepted": False,
                        "reason": reason_str,
                        "actionable_guidance": guidance,
                    },
                    "triage": {
                        "outcome": "QUALITY_GATE_REJECTED",
                        "headline": "EVIDENCE REJECTED BY QUALITY GATE",
                        "status_color": "amber",
                        "icon": "⚠️",
                        "summary_reason": f"Forensic quality check failed: {reason_str}.",
                        "recommended_action": guidance,
                    },
                    "financials": {
                        "repair_cost_min_aed": 0.0,
                        "repair_cost_max_aed": 0.0,
                        "repair_cost_median_aed": 0.0,
                        "acv_aed": acv,
                        "loss_ratio_pct": 0.0,
                        "threshold_pct": custom_threshold if jurisdiction == "custom" else get_preset(jurisdiction).threshold * 100.0,
                        "is_total_loss": False,
                        "currency": "AED",
                    },
                    "polygons": [],
                    "line_items": [],
                    "assumptions": [
                        "Automated inspection halted: Photographic evidence fails forensic quality standards."
                    ],
                    "unknowns": [
                        "True extent of damage cannot be analyzed from blurred/dark/low-resolution imagery."
                    ],
                    "policy_guidance": [],
                },
            )

        # Stage 2: Computer Vision Inference (Parts + Damages + Spatial Association)
        inspection: InspectionResult = inspect_vehicle(active_image_path)

        # Open base image for dimensions & base64
        with Image.open(active_image_path) as orig_img:
            rgb_img = orig_img.convert("RGB")
            img_width, img_height = rgb_img.size
            raw_base64 = _image_to_base64(rgb_img)

        annotated_base64 = (
            _image_to_base64(inspection.annotated_image)
            if inspection.annotated_image
            else raw_base64
        )

        # Stage 3: Deterministic OEM Costing in AED
        cost_estimate: CostEstimate = estimate_repair_costs(inspection, brand=brand)

        # Stage 4: Total-Loss Triage Decision
        custom_thresh_frac = (custom_threshold / 100.0) if jurisdiction == "custom" else None
        triage_decision: TriageDecision = decide_triage(
            inspection=inspection,
            estimate=cost_estimate,
            pre_accident_value=acv,
            preset_id=jurisdiction if jurisdiction != "custom" else None,
            custom_threshold=custom_thresh_frac,
        )
        triage_ui = _format_triage_ui(triage_decision)

        # Stage 5: CBUAE Statutory Policy Retrieval
        damaged_parts_query = " ".join(
            [item.part_name for item in cost_estimate.itemized_costs]
            + [assoc.damage.name for assoc in inspection.associated_damages]
        ) or "vehicle total loss collision repair"
        policy_result = retrieve_policy_guidance(damaged_parts_query)

        # Structure polygons for interactive SVG overlay
        polygons: list[dict[str, Any]] = []

        # Export parts polygons
        for idx, part in enumerate(inspection.all_parts):
            p_id = f"part-{idx}"
            polygons.append(
                {
                    "id": p_id,
                    "type": "part",
                    "label": part.name,
                    "confidence": round(part.confidence, 3),
                    "box": [round(c, 1) for c in part.box],
                    "polygon": [[round(x, 1), round(y, 1)] for x, y in part.polygon] if part.polygon else [],
                    "is_structural": part.is_structural,
                }
            )

        # Export damage polygons and link to host parts
        for idx, assoc in enumerate(inspection.associated_damages):
            d_id = f"dmg-{idx}"
            host_p_id = None
            if assoc.host_part:
                # Find matching part
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
                    "line_item_index": idx,
                }
            )

        # Format line items with bidirectional linking IDs
        line_items = [
            {
                "index": i,
                "part_name": item.part_name,
                "damage_type": item.damage_type,
                "action": item.action.upper(),
                "min_cost_aed": round(item.min_cost, 2),
                "max_cost_aed": round(item.max_cost, 2),
                "median_cost_aed": round(item.median_cost, 2),
                "formatted_range": f"AED {item.min_cost:,.0f} – {item.max_cost:,.0f}",
                "description": item.description,
                "is_structural": item.is_structural,
                "damage_polygon_id": f"dmg-{i}" if i < len(inspection.associated_damages) else None,
            }
            for i, item in enumerate(cost_estimate.itemized_costs)
        ]

        # Format CBUAE policy guidance
        policy_clauses: list[dict[str, Any]] = []
        if policy_result.is_established and policy_result.matched_clause:
            cl = policy_result.matched_clause
            policy_clauses.append(
                {
                    "clause_id": cl.id,
                    "title": cl.title,
                    "article": cl.citation,
                    "rule_summary": policy_result.guidance,
                    "relevance_score": round(policy_result.relevance_score, 3),
                    "statutory_text": cl.text,
                }
            )

        # Defensibility Checklist
        unknowns = [
            "Hidden suspension geometry distortion cannot be certified from 2D photographic evidence alone.",
            "SRS airbag sensor readiness, seatbelt pretensioners, and ADAS radar calibration require OBD-II diagnostics.",
            "Sub-surface frame rail micro-cracks or weld-seam tearing require physical undercarriage laser scanning.",
            "Internal fluid lines, radiators, and condenser leaks require pressure testing prior to road release.",
        ]

        return JSONResponse(
            status_code=200,
            content={
                "quality_gate": {
                    "accepted": True,
                    "reason": None,
                },
                "triage": triage_ui,
                "financials": {
                    "repair_cost_min_aed": round(cost_estimate.total_min, 2),
                    "repair_cost_max_aed": round(cost_estimate.total_max, 2),
                    "repair_cost_median_aed": round(cost_estimate.median_estimate, 2),
                    "acv_aed": round(triage_decision.pre_accident_value, 2),
                    "loss_ratio_pct": round(triage_decision.economic_ratio * 100.0, 2),
                    "threshold_pct": round(triage_decision.threshold_applied * 100.0, 2),
                    "is_total_loss": triage_decision.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW,
                    "structural_risk_flag": inspection.structural_flag,
                    "brand": brand,
                    "currency": "AED",
                },
                "image_meta": {
                    "width": img_width,
                    "height": img_height,
                    "raw_base64": f"data:image/jpeg;base64,{raw_base64}",
                    "annotated_base64": f"data:image/jpeg;base64,{annotated_base64}",
                },
                "polygons": polygons,
                "line_items": line_items,
                "assumptions": cost_estimate.assumptions,
                "unknowns": unknowns,
                "policy_guidance": policy_clauses,
            },
        )

    finally:
        if temp_path and temp_path.exists():
            with contextlib.suppress(OSError):
                temp_path.unlink()


# Static assets serving
static_dir = Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def serve_frontend_index() -> FileResponse:
    index_file = static_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not yet initialized")
    return FileResponse(index_file)
