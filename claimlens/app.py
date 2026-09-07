"""ClaimLens Gradio Application.

Explainable, two-stage vehicle damage and total-loss triage system.
Option C: Part Detection + Damage Detection + Spatial Association +
Rule-Based Costing + Total-Loss Decision Engine + CBUAE Policy Retrieval.
"""

from __future__ import annotations

from typing import Any

import gradio as gr
from PIL import Image

from claimlens.costing.estimate import CostEstimate, estimate_repair_costs
from claimlens.detection.infer import inspect_vehicle
from claimlens.detection.schemas import InspectionResult
from claimlens.policy.retrieve import PolicyRetrievalResult, retrieve_policy_guidance
from claimlens.triage.decide import TriageDecision, TriageOutcome, decide_triage

JURISDICTION_PRESETS = {
    "UAE Unified Motor Policy (50% Economic Test)": "uae_50",
    "US Total Loss Formula (70% Market Standard)": "us_70",
    "US Standard Total Loss (75% Threshold)": "us_75",
    "UK / European Market Reference (60% Threshold)": "uk_60",
    "Custom Threshold (%)": "custom",
}

APP_CSS = """
/* ClaimLens Theme Styling */
.claimlens-container {
    max-width: 1280px;
    margin: 0 auto;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.claimlens-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
}

.claimlens-header h1 {
    margin: 0 0 8px 0;
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    background: linear-gradient(to right, #38bdf8, #818cf8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.claimlens-header p {
    margin: 0;
    color: #94a3b8;
    font-size: 1.05rem;
    line-height: 1.5;
}

.claimlens-badge-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 14px;
}

.claimlens-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    background: #1e293b;
    color: #38bdf8;
    border: 1px solid #38bdf840;
}

/* Triage Outcome Cards */
.triage-card {
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 8px 20px -4px rgba(0, 0, 0, 0.3);
    transition: all 0.2s ease;
}

.triage-card-repairable {
    background: linear-gradient(135deg, rgba(6, 78, 59, 0.9) 0%, rgba(6, 95, 70, 0.8) 100%);
    border: 1px solid #10b981;
    color: #ecfdf5;
}

.triage-card-totalloss {
    background: linear-gradient(135deg, rgba(127, 29, 29, 0.9) 0%, rgba(153, 27, 27, 0.8) 100%);
    border: 1px solid #ef4444;
    color: #fef2f2;
}

.triage-card-inspection {
    background: linear-gradient(135deg, rgba(120, 53, 15, 0.9) 0%, rgba(146, 64, 14, 0.8) 100%);
    border: 1px solid #f59e0b;
    color: #fffbeb;
}

.triage-card-title {
    font-size: 1.45rem;
    font-weight: 800;
    letter-spacing: -0.01em;
    margin: 0 0 6px 0;
    display: flex;
    align-items: center;
    gap: 10px;
}

.triage-rule-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-weight: 700;
    margin-bottom: 12px;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.25);
}

.triage-reason {
    font-size: 0.98rem;
    line-height: 1.55;
    margin: 0;
    opacity: 0.95;
}

/* Metric KPI Cards */
.kpi-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.kpi-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
}

.kpi-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
    margin-bottom: 6px;
    font-weight: 600;
}

.kpi-value {
    font-size: 1.5rem;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 4px;
}

.kpi-subtext {
    font-size: 0.78rem;
    color: #64748b;
}

/* Policy Card */
.policy-box {
    background: #0f172a;
    border: 1px solid #334155;
    border-left: 4px solid #38bdf8;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 16px;
}

.policy-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 6px;
}

.policy-citation {
    font-size: 0.85rem;
    color: #a5b4fc;
    font-weight: 600;
    margin-bottom: 12px;
}

.policy-text {
    font-size: 0.92rem;
    line-height: 1.6;
    color: #cbd5e1;
    background: #1e293b80;
    padding: 12px 14px;
    border-radius: 6px;
    border: 1px dashed #475569;
    margin-bottom: 12px;
}

.policy-guidance {
    font-size: 0.88rem;
    color: #94a3b8;
    line-height: 1.5;
}

.policy-disclaimer {
    margin-top: 10px;
    font-size: 0.75rem;
    color: #64748b;
    font-style: italic;
}
"""


def _format_triage_card(decision: TriageDecision) -> str:
    """Renders high-visibility triage outcome card with semantic color coding."""
    if decision.outcome == TriageOutcome.PROBABLY_REPAIRABLE:
        css_class = "triage-card-repairable"
        icon = "🟢"
        title = "PROBABLY REPAIRABLE"
        sub = "Visible repair cost remains comfortably below statutory total-loss threshold."
    elif decision.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW:
        css_class = "triage-card-totalloss"
        icon = "🔴"
        title = "PROBABLE TOTAL LOSS — FORMAL SALVAGE REVIEW RECOMMENDED"
        sub = "Visible repair cost exceeds statutory total-loss threshold."
    else:
        css_class = "triage-card-inspection"
        icon = "⚠️"
        title = "INSUFFICIENT EVIDENCE — PHYSICAL INSPECTION MANDATORY"
        sub = "Structural safety zone or calibrated confidence floor requires in-person adjuster inspection."

    html = f"""
    <div class="triage-card {css_class}">
        <div class="triage-card-title">
            <span>{icon}</span>
            <span>{title}</span>
        </div>
        <div style="font-size:0.88rem; opacity:0.9; margin-bottom:10px;">{sub}</div>
        <div class="triage-rule-pill">RULE: {decision.rule_applied}</div>
        <p class="triage-reason">{decision.reasoning}</p>
    </div>
    """
    return html


def _format_kpi_cards(decision: TriageDecision, estimate: CostEstimate) -> str:
    """Renders 3-column key performance indicator metric cards."""
    repair_val = f"${estimate.median_estimate:,.2f}"
    repair_range = f"Range: ${estimate.total_min:,.0f} – ${estimate.total_max:,.0f}"

    acv_val = f"${decision.pre_accident_value:,.2f}"
    acv_sub = "Pre-Accident Cash Value"

    ratio_val = f"{decision.economic_ratio:.1%}"
    threshold_val = f"Threshold: {decision.threshold_applied:.0%}"

    return f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Visible Repair Cost</div>
            <div class="kpi-value">{repair_val}</div>
            <div class="kpi-subtext">{repair_range}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Vehicle Valuation</div>
            <div class="kpi-value">{acv_val}</div>
            <div class="kpi-subtext">{acv_sub}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Economic Loss Ratio</div>
            <div class="kpi-value">{ratio_val}</div>
            <div class="kpi-subtext">{threshold_val}</div>
        </div>
    </div>
    """


def _format_policy_card(retrieval: PolicyRetrievalResult) -> str:
    """Renders retrieved statutory policy clause card."""
    established_badge = (
        f'<span style="background:#065f46;color:#34d399;padding:2px 8px;border-radius:6px;font-size:0.75rem;font-weight:700;">CONFIRMED CLAUSE (Similarity: {retrieval.relevance_score:.1%})</span>'
        if retrieval.is_established
        else '<span style="background:#78350f;color:#fcd34d;padding:2px 8px;border-radius:6px;font-size:0.75rem;font-weight:700;">NOT ESTABLISHED</span>'
    )

    return f"""
    <div class="policy-box">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <div class="policy-title">{retrieval.title}</div>
            <div>{established_badge}</div>
        </div>
        <div class="policy-citation">Citation: {retrieval.citation}</div>
        <div class="policy-text">"{retrieval.text}"</div>
        <div class="policy-guidance"><strong>Regulatory Guidance:</strong> {retrieval.guidance}</div>
        <div class="policy-disclaimer">Notice: {retrieval.disclaimer}</div>
    </div>
    """


def _format_unknowns_markdown(decision: TriageDecision) -> str:
    """Formats the explicit 'what isn't known' safety checklist."""
    md = [
        "### 🔍 Unresolvable Physical Factors (Safe Abstention Checklist)",
        "",
        (
            "The automated vision pipeline inspects **visible 2D exterior panel damage only**. "
            "The following critical roadworthiness and safety parameters **cannot be established from photos** "
            "and require mandatory bench physical inspection before issuing final legal determination:"
        ),
        "",
    ]
    for unk in decision.unknowns:
        md.append(f"- **{unk}**")
    return "\n".join(md)


def _format_assumptions_markdown(estimate: CostEstimate) -> str:
    """Formats explicit costing assumptions and transparent rules."""
    md = [
        "### 📋 Cost Estimator Assumptions & Transparency Rules",
        "",
        (
            "ClaimLens does **not** query unstructured LLMs for pricing. All repair amounts are deterministic, "
            "derived from the curated reference price table (`data/price_table.json`) using the following rules:"
        ),
        "",
    ]
    for asm in estimate.assumptions:
        md.append(f"- {asm}")
    return "\n".join(md)


def _build_cost_table(estimate: CostEstimate) -> list[list[str]]:
    """Builds tabular representation of itemized repair operations."""
    rows: list[list[str]] = []
    for item in estimate.itemized_costs:
        struct_flag = "⚠️ Yes (Load-Bearing)" if item.is_structural else "No (Cosmetic)"
        rows.append(
            [
                item.part_name,
                item.damage_type,
                item.action.capitalize(),
                f"${item.min_cost:,.0f} – ${item.max_cost:,.0f}",
                f"${item.median_cost:,.2f}",
                struct_flag,
                item.description,
            ]
        )
    return rows


def analyze_claim(
    image_path: str | None,
    pre_accident_value: float,
    jurisdiction_label: str,
    custom_threshold_pct: float,
) -> tuple[str, str, Any, list[list[str]], str, str, str]:
    """Orchestrates end-to-end ClaimLens triage pipeline."""
    if not image_path:
        error_card = """
        <div class="triage-card triage-card-inspection">
            <div class="triage-card-title"><span>⚠️</span><span>NO PHOTO PROVIDED</span></div>
            <p class="triage-reason">Please upload a vehicle damage photograph or select one of the curated demonstration cases below.</p>
        </div>
        """
        return error_card, "", None, [], "", "", ""

    # 1. Resolve threshold preset
    preset_id = JURISDICTION_PRESETS.get(jurisdiction_label, "uae_50")
    custom_thresh_val = (custom_threshold_pct / 100.0) if preset_id == "custom" else None

    # 2. Run Quality Gate + Two-Stage Detection + Spatial Association
    inspection: InspectionResult = inspect_vehicle(image_path)

    # 3. Calculate Rule-Based Visible Repair Costs
    estimate: CostEstimate = estimate_repair_costs(inspection)

    # 4. Total-Loss Triage Decision Engine
    decision: TriageDecision = decide_triage(
        inspection=inspection,
        estimate=estimate,
        pre_accident_value=float(pre_accident_value),
        preset_id=preset_id,
        custom_threshold=custom_thresh_val,
    )

    # 5. Policy Retrieval based on Decision & Detected Damage
    policy_query = "car body scratch dent repair workshop depreciation spare parts"
    if not inspection.accepted_by_quality_gate:
        policy_query = "vehicle damage quality evidence inspection documentation"
    elif decision.structural_damage_flag:
        policy_query = "chassis structural unibody damage repair safety roadworthiness"
    elif decision.outcome == TriageOutcome.PROBABLE_TOTAL_LOSS_REVIEW:
        policy_query = "economic total loss 50 percent threshold vehicle market value repair"
    else:
        # Check if glass was damaged
        has_glass = any("glass" in (a.damage.name or "").lower() for a in inspection.associated_damages)
        if has_glass:
            policy_query = "windshield glass damage comprehensive excess waiver"

    policy_result = retrieve_policy_guidance(policy_query)

    # 6. Render UI Components
    triage_html = _format_triage_card(decision)
    kpi_html = _format_kpi_cards(decision, estimate)
    annotated_img = inspection.annotated_image if inspection.annotated_image else Image.open(image_path)
    cost_table = _build_cost_table(estimate)
    policy_html = _format_policy_card(policy_result)
    unknowns_md = _format_unknowns_markdown(decision)
    assumptions_md = _format_assumptions_markdown(estimate)

    return (
        triage_html,
        kpi_html,
        annotated_img,
        cost_table,
        policy_html,
        unknowns_md,
        assumptions_md,
    )


def create_app() -> gr.Blocks:
    """Builds and wires the Gradio Blocks UI."""
    with gr.Blocks(
        title="ClaimLens — Explainable Vehicle Damage Triage"
    ) as demo, gr.Column(elem_classes=["claimlens-container"]):
        # Header & Styles
        gr.HTML(
            f"""
            <style>{APP_CSS}</style>
            <div class="claimlens-header">
                <h1>ClaimLens</h1>
                <p>Explainable Vehicle Damage & Total-Loss Triage System with Spatial Association, Rule-Based Costing, and Statutory Policy Retrieval.</p>
                <div class="claimlens-badge-row">
                    <span class="claimlens-tag">Option C Two-Stage Vision</span>
                    <span class="claimlens-tag">YOLOv8-Seg Fine-Tuned</span>
                    <span class="claimlens-tag">Deterministic Cost Engine</span>
                    <span class="claimlens-tag">CBUAE Motor Policy Standard</span>
                    <span class="claimlens-tag">Safe Abstention Logic</span>
                </div>
            </div>
            """
        )

        with gr.Row():
            # Left Column: Inputs
            with gr.Column(scale=5):
                gr.Markdown("### 📸 1. Vehicle Collision Evidence")
                input_image = gr.Image(
                    type="filepath",
                    label="Vehicle Damage Photograph",
                    sources=["upload", "clipboard"],
                )

                gr.Markdown("### ⚙️ 2. Policy & Valuation Parameters")
                input_acv = gr.Number(
                    value=35000,
                    label="Pre-Accident Vehicle Cash Value ($ / AED)",
                    info="Agreed policy schedule value or market depreciated value.",
                )

                input_jurisdiction = gr.Dropdown(
                    choices=list(JURISDICTION_PRESETS.keys()),
                    value="UAE Unified Motor Policy (50% Economic Test)",
                    label="Regulatory Jurisdiction / Total-Loss Rule",
                    info="Statutory standard applied to determine economic constructive total loss.",
                )

                input_custom_thresh = gr.Slider(
                    minimum=10,
                    maximum=100,
                    value=50,
                    step=5,
                    label="Custom Economic Threshold (%)",
                    info="Applied only when 'Custom Threshold (%)' is selected above.",
                )

                btn_submit = gr.Button(
                    "🔍 Analyze Claim & Run Triage",
                    variant="primary",
                    size="lg",
                )

                gr.Markdown("### 🧪 Curated Demonstration Cases")
                gr.Markdown(
                    "*Click any scenario to load authentic validation images illustrating specific triage branches:*"
                )
                gr.Examples(
                    examples=[
                        [
                            "data/demo_examples/case_a_repairable.jpg",
                            35000,
                            "UAE Unified Motor Policy (50% Economic Test)",
                            50,
                        ],
                        [
                            "data/demo_examples/case_b_total_loss.jpg",
                            4500,
                            "UAE Unified Motor Policy (50% Economic Test)",
                            50,
                        ],
                        [
                            "data/demo_examples/case_c_structural_inspection.jpg",
                            25000,
                            "UAE Unified Motor Policy (50% Economic Test)",
                            50,
                        ],
                    ],
                    inputs=[
                        input_image,
                        input_acv,
                        input_jurisdiction,
                        input_custom_thresh,
                    ],
                    label="Blueprint §13 Validation Scenarios",
                )

            # Right Column: Outputs
            with gr.Column(scale=7):
                gr.Markdown("### ⚖️ 3. Triage Assessment & Decision Trail")
                out_triage_card = gr.HTML(
                    label="Triage Decision",
                    value="""
                    <div class="triage-card" style="background:#1e293b; border:1px solid #334155; color:#94a3b8;">
                        <div class="triage-card-title"><span>⏳</span><span>Awaiting Claim Input</span></div>
                        <p class="triage-reason">Upload a collision photograph and click 'Analyze Claim' or select one of the curated demonstration cases.</p>
                    </div>
                    """,
                )

                out_kpi_cards = gr.HTML(label="Financial Summary")

                gr.Markdown("### 🔬 4. Computer Vision Detections & Spatial Overlays")
                out_annotated_image = gr.Image(
                    label="Annotated Parts & Damages Segmentation",
                    interactive=False,
                )

                # Tabs for detailed reasoning trails
                with gr.Tabs():
                    with gr.TabItem("📊 Itemized Repair Estimate"):
                        out_cost_table = gr.Dataframe(
                            headers=[
                                "Component",
                                "Damage Type",
                                "Action",
                                "Cost Range ($)",
                                "Median ($)",
                                "Structural?",
                                "Description",
                            ],
                            datatype=["str", "str", "str", "str", "str", "str", "str"],
                            interactive=False,
                            label="Deterministic Line Items",
                        )
                        out_assumptions = gr.Markdown()

                    with gr.TabItem("📜 Regulatory Policy Guidance"):
                        out_policy_card = gr.HTML()

                    with gr.TabItem("🛡️ 'What Isn't Known' Checklist"):
                        out_unknowns = gr.Markdown()

        # Wire the interaction
        btn_submit.click(
            fn=analyze_claim,
            inputs=[
                input_image,
                input_acv,
                input_jurisdiction,
                input_custom_thresh,
            ],
            outputs=[
                out_triage_card,
                out_kpi_cards,
                out_annotated_image,
                out_cost_table,
                out_policy_card,
                out_unknowns,
                out_assumptions,
            ],
        )

    return demo


def main() -> None:
    """Launches the local Gradio development server."""
    demo = create_app()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, css=APP_CSS)


if __name__ == "__main__":
    main()
