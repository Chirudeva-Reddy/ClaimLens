"""ClaimLens Gradio Application.

Explainable, two-stage vehicle damage and total-loss triage system.
Option C: Part Detection + Damage Detection + Spatial Association +
Rule-Based Costing (AED) + Total-Loss Decision Engine + CBUAE Policy Retrieval.
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

AVAILABLE_BRANDS = [
    "Toyota",
    "Nissan",
    "Hyundai",
    "Ford",
    "Lexus",
    "Mercedes-Benz",
    "General Market Standard",
]

APP_CSS = """
/* ClaimLens Modern Executive Theme */
:root {
    --bg-main: #070b14;
    --card-bg: #0f172a;
    --card-border: #1e293b;
    --accent-blue: #38bdf8;
    --accent-indigo: #818cf8;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
}

body {
    background-color: var(--bg-main) !important;
}

.claimlens-container {
    max-width: 1440px;
    margin: 0 auto;
    padding: 12px 20px 48px 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Header Banner */
.claimlens-header {
    background: linear-gradient(135deg, #0b1329 0%, #172554 50%, #0f172a 100%);
    border: 1px solid #1e3a8a50;
    border-radius: 20px;
    padding: 32px 40px;
    margin-bottom: 28px;
    box-shadow: 0 16px 36px -8px rgba(0, 0, 0, 0.6);
}

.claimlens-header h1 {
    margin: 0 0 10px 0;
    font-size: 2.6rem;
    font-weight: 850;
    letter-spacing: -0.03em;
    background: linear-gradient(to right, #38bdf8, #818cf8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.claimlens-header p {
    margin: 0;
    color: #cbd5e1;
    font-size: 1.15rem;
    line-height: 1.6;
    max-width: 960px;
}

.claimlens-badge-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 18px;
}

.claimlens-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    background: rgba(15, 23, 42, 0.85);
    color: #38bdf8;
    border: 1px solid #38bdf840;
    backdrop-filter: blur(8px);
}

/* Section Containers */
.surface-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 18px;
    padding: 24px 28px;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.4);
}

.section-title {
    font-size: 1.25rem;
    font-weight: 750;
    color: #f8fafc;
    letter-spacing: -0.01em;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* Curated Scenario Bar */
.scenario-box {
    background: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 28px;
}

.scenario-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 14px;
}

/* Triage Outcome Banner */
.triage-card {
    border-radius: 16px;
    padding: 26px 32px;
    margin-bottom: 24px;
    box-shadow: 0 12px 30px -6px rgba(0, 0, 0, 0.5);
    transition: all 0.25s ease;
}

.triage-card-repairable {
    background: linear-gradient(135deg, rgba(6, 78, 59, 0.95) 0%, rgba(6, 95, 70, 0.9) 100%);
    border: 1.5px solid #10b981;
    color: #ecfdf5;
}

.triage-card-totalloss {
    background: linear-gradient(135deg, rgba(127, 29, 29, 0.95) 0%, rgba(153, 27, 27, 0.9) 100%);
    border: 1.5px solid #ef4444;
    color: #fef2f2;
}

.triage-card-inspection {
    background: linear-gradient(135deg, rgba(120, 53, 15, 0.95) 0%, rgba(146, 64, 14, 0.9) 100%);
    border: 1.5px solid #f59e0b;
    color: #fffbeb;
}

.triage-card-title {
    font-size: 1.65rem;
    font-weight: 850;
    letter-spacing: -0.02em;
    margin: 0 0 8px 0;
    display: flex;
    align-items: center;
    gap: 12px;
}

.triage-rule-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-weight: 750;
    margin-bottom: 14px;
    background: rgba(0, 0, 0, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.triage-reason {
    font-size: 1.05rem;
    line-height: 1.65;
    margin: 0;
    opacity: 0.96;
}

/* Metric KPI Cards */
.kpi-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    margin-bottom: 26px;
}

.kpi-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 16px;
    padding: 22px 24px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.kpi-label {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94a3b8;
    margin-bottom: 8px;
    font-weight: 700;
}

.kpi-value {
    font-size: 1.85rem;
    font-weight: 850;
    color: #f8fafc;
    margin-bottom: 6px;
    letter-spacing: -0.02em;
}

.kpi-subtext {
    font-size: 0.84rem;
    color: #64748b;
    font-weight: 500;
}

/* Policy Card */
.policy-box {
    background: #0b1120;
    border: 1px solid #1e293b;
    border-left: 5px solid #38bdf8;
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 18px;
}

.policy-title {
    font-size: 1.25rem;
    font-weight: 750;
    color: #38bdf8;
    margin-bottom: 6px;
}

.policy-citation {
    font-size: 0.9rem;
    color: #a5b4fc;
    font-weight: 650;
    margin-bottom: 14px;
}

.policy-text {
    font-size: 0.96rem;
    line-height: 1.65;
    color: #cbd5e1;
    background: rgba(15, 23, 42, 0.85);
    padding: 16px 18px;
    border-radius: 8px;
    border: 1px dashed #334155;
    margin-bottom: 14px;
}

.policy-guidance {
    font-size: 0.92rem;
    color: #94a3b8;
    line-height: 1.55;
}

.policy-disclaimer {
    margin-top: 14px;
    font-size: 0.78rem;
    color: #64748b;
    font-style: italic;
}

/* Legend Row */
.legend-row {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    align-items: center;
    padding: 12px 16px;
    background: #0b1120;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin-top: 12px;
    font-size: 0.85rem;
    color: #cbd5e1;
}

.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    display: inline-block;
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
        <div style="font-size:0.95rem; opacity:0.92; margin-bottom:12px;">{sub}</div>
        <div class="triage-rule-pill">RULE: {decision.rule_applied}</div>
        <p class="triage-reason">{decision.reasoning}</p>
    </div>
    """
    return html


def _format_kpi_cards(decision: TriageDecision, estimate: CostEstimate) -> str:
    """Renders 3-column key performance indicator metric cards in AED."""
    repair_val = f"AED {estimate.median_estimate:,.2f}"
    repair_range = f"Range: AED {estimate.total_min:,.0f} – {estimate.total_max:,.0f}"

    acv_val = f"AED {decision.pre_accident_value:,.2f}"
    acv_sub = f"Pre-Accident Valuation ({estimate.brand})"

    ratio_val = f"{decision.economic_ratio:.1%}"
    threshold_val = f"Statutory Floor: {decision.threshold_applied:.0%}"

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
        f'<span style="background:#065f46;color:#34d399;padding:3px 10px;border-radius:6px;font-size:0.75rem;font-weight:750;">CONFIRMED STATUTORY CLAUSE (Similarity: {retrieval.relevance_score:.1%})</span>'
        if retrieval.is_established
        else '<span style="background:#78350f;color:#fcd34d;padding:3px 10px;border-radius:6px;font-size:0.75rem;font-weight:750;">NOT ESTABLISHED</span>'
    )

    return f"""
    <div class="policy-box">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
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
    """Formats explicit costing assumptions and transparent rules in AED."""
    md = [
        "### 📋 Cost Estimator Assumptions & Transparency Rules",
        "",
        (
            f"ClaimLens calculates deterministic repair costs in **AED**, fusing the curated UAE collision "
            f"table with empirical OEM catalog prices for **{estimate.brand}**:"
        ),
        "",
    ]
    for asm in estimate.assumptions:
        md.append(f"- {asm}")
    return "\n".join(md)


def _build_cost_table(estimate: CostEstimate) -> list[list[str]]:
    """Builds tabular representation of itemized repair operations in AED."""
    rows: list[list[str]] = []
    for item in estimate.itemized_costs:
        struct_flag = "⚠️ Yes (Load-Bearing)" if item.is_structural else "No (Cosmetic)"
        rows.append(
            [
                item.part_name,
                item.damage_type,
                item.action.capitalize(),
                f"AED {item.min_cost:,.0f} – {item.max_cost:,.0f}",
                f"AED {item.median_cost:,.2f}",
                struct_flag,
                item.description,
            ]
        )
    return rows


def analyze_claim(
    image_path: str | None,
    brand_label: str,
    pre_accident_value: float,
    jurisdiction_label: str,
    custom_threshold_pct: float,
) -> tuple[str, str, Any, list[list[str]], str, str, str]:
    """Orchestrates end-to-end ClaimLens triage pipeline in AED."""
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

    # 3. Calculate Rule-Based Visible Repair Costs in AED with Brand OEM Calibration
    estimate: CostEstimate = estimate_repair_costs(inspection, brand=brand_label)

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
        has_glass = any(
            "glass" in (a.damage.name or "").lower() for a in inspection.associated_damages
        )
        if has_glass:
            policy_query = "windshield glass damage comprehensive excess waiver"

    policy_result = retrieve_policy_guidance(policy_query)

    # 6. Render UI Components
    triage_html = _format_triage_card(decision)
    kpi_html = _format_kpi_cards(decision, estimate)
    annotated_img = (
        inspection.annotated_image if inspection.annotated_image else Image.open(image_path)
    )
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


def load_demo_case_a():
    return (
        "data/demo_examples/case_a_repairable.jpg",
        "Toyota",
        120000,
        "UAE Unified Motor Policy (50% Economic Test)",
        50,
    )


def load_demo_case_b():
    return (
        "data/demo_examples/case_b_total_loss.jpg",
        "General Market Standard",
        15000,
        "UAE Unified Motor Policy (50% Economic Test)",
        50,
    )


def load_demo_case_c():
    return (
        "data/demo_examples/case_c_structural_inspection.jpg",
        "Toyota",
        85000,
        "UAE Unified Motor Policy (50% Economic Test)",
        50,
    )


def create_app() -> gr.Blocks:
    """Builds and wires the Gradio Blocks UI."""
    with (
        gr.Blocks(title="ClaimLens — Explainable Vehicle Damage Triage") as demo,
        gr.Column(elem_classes=["claimlens-container"]),
    ):
        # Header & Styles
        gr.HTML(
            f"""
            <style>{APP_CSS}</style>
            <div class="claimlens-header">
                <h1>ClaimLens</h1>
                <p>Explainable Vehicle Damage & Total-Loss Triage System. Decomposes collision triage into spatial part association, empirical UAE OEM repair costing (AED), and CBUAE statutory policy retrieval.</p>
                <div class="claimlens-badge-row">
                    <span class="claimlens-tag">Option C Two-Stage Vision</span>
                    <span class="claimlens-tag">YOLOv8-Seg Fine-Tuned</span>
                    <span class="claimlens-tag">AED Cost Engine</span>
                    <span class="claimlens-tag">Scraped UAE OEM Parts</span>
                    <span class="claimlens-tag">CBUAE Statutory Policy</span>
                    <span class="claimlens-tag">Safe Abstention Invariant</span>
                </div>
            </div>
            """
        )

        # Interactive Benchmark Scenarios Bar
        with gr.Column(elem_classes=["scenario-box"]):
            gr.HTML(
                """
                <div class="scenario-title">⚡ Quick-Launch Blueprint §13 Demonstration Scenarios</div>
                """
            )
            with gr.Row():
                btn_case_a = gr.Button(
                    "🟢 Scenario A: Minor Cosmetic Repairable (Toyota Corolla · AED 120k)",
                    variant="secondary",
                )
                btn_case_b = gr.Button(
                    "🔴 Scenario B: Economic Constructive Total Loss (Multi-Panel · AED 15k)",
                    variant="secondary",
                )
                btn_case_c = gr.Button(
                    "⚠️ Scenario C: Unibody Structural Hazard (Quarter Panel · AED 85k)",
                    variant="secondary",
                )

        # Section 1: Inspection & Parameter Console
        with gr.Row():
            with gr.Column(scale=5, elem_classes=["surface-card"]):
                gr.HTML('<div class="section-title">📸 1. Collision Photographic Evidence</div>')
                input_image = gr.Image(
                    type="filepath",
                    label="Upload Vehicle Damage Photograph",
                    sources=["upload", "clipboard"],
                    height=340,
                )

            with gr.Column(scale=7, elem_classes=["surface-card"]):
                gr.HTML('<div class="section-title">⚙️ 2. Policy & Valuation Parameters</div>')

                with gr.Row():
                    input_brand = gr.Dropdown(
                        choices=AVAILABLE_BRANDS,
                        value="Toyota",
                        label="Vehicle Make / Brand (UAE OEM Benchmark)",
                        info="Applies scraped UAE OEM catalog replacement rates.",
                        scale=6,
                    )
                    input_acv = gr.Number(
                        value=120000,
                        label="Pre-Accident Vehicle Cash Value (AED)",
                        info="Agreed policy schedule or depreciated market value.",
                        scale=6,
                    )

                with gr.Row():
                    input_jurisdiction = gr.Dropdown(
                        choices=list(JURISDICTION_PRESETS.keys()),
                        value="UAE Unified Motor Policy (50% Economic Test)",
                        label="Regulatory Jurisdiction / Total-Loss Rule",
                        info="Statutory standard applied to determine economic total loss.",
                        scale=7,
                    )
                    input_custom_thresh = gr.Slider(
                        minimum=10,
                        maximum=100,
                        value=50,
                        step=5,
                        label="Custom Economic Threshold (%)",
                        info="Active only when 'Custom Threshold (%)' is selected.",
                        scale=5,
                    )

                btn_submit = gr.Button(
                    "🔍 Run AI Inspection & Total-Loss Triage",
                    variant="primary",
                    size="lg",
                )

        # Section 2: Triage Assessment & Analytical Findings
        gr.HTML('<div style="margin-top: 14px;"></div>')
        out_triage_card = gr.HTML(
            label="Triage Decision",
            value="""
            <div class="triage-card" style="background:#0f172a; border:1px solid #1e293b; color:#94a3b8;">
                <div class="triage-card-title"><span>⏳</span><span>Awaiting Collision Evidence</span></div>
                <p class="triage-reason">Upload an accident photograph and click 'Run AI Inspection & Total-Loss Triage' or select one of the Quick-Launch Scenarios above.</p>
            </div>
            """,
        )

        out_kpi_cards = gr.HTML(label="Financial Summary")

        # Split Deep-Dive View (Visual Studio & Intelligence Tabs)
        with gr.Row():
            with gr.Column(scale=5, elem_classes=["surface-card"]):
                gr.HTML(
                    '<div class="section-title">🔬 3. Computer Vision Segmentation Studio</div>'
                )
                out_annotated_image = gr.Image(
                    label="Annotated Parts & Damages Segmentation Overlay",
                    interactive=False,
                    height=420,
                )
                gr.HTML(
                    """
                    <div class="legend-row">
                        <span class="legend-item"><span class="legend-dot" style="background:#0ea5e9;"></span> <strong>Vehicle Components</strong></span>
                        <span class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span> <strong>Collision Damage</strong></span>
                        <span class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span> <strong>Structural Zones</strong></span>
                    </div>
                    """
                )

            with gr.Column(scale=7, elem_classes=["surface-card"]):
                gr.HTML(
                    '<div class="section-title">⚖️ 4. Explainable Decision & Policy Audit Trail</div>'
                )
                with gr.Tabs():
                    with gr.TabItem("📊 Itemized Repair Estimate"):
                        out_cost_table = gr.Dataframe(
                            headers=[
                                "Component",
                                "Damage Type",
                                "Action",
                                "Cost Range (AED)",
                                "Median (AED)",
                                "Structural?",
                                "Description",
                            ],
                            datatype=["str", "str", "str", "str", "str", "str", "str"],
                            interactive=False,
                            label="Deterministic Collision Line Items (AED)",
                        )
                        out_assumptions = gr.Markdown()

                    with gr.TabItem("📜 Statutory Policy Guidance"):
                        out_policy_card = gr.HTML()

                    with gr.TabItem("🛡️ 'What Isn't Known' Checklist"):
                        out_unknowns = gr.Markdown()

        # Wire the interaction
        all_inputs = [
            input_image,
            input_brand,
            input_acv,
            input_jurisdiction,
            input_custom_thresh,
        ]
        all_outputs = [
            out_triage_card,
            out_kpi_cards,
            out_annotated_image,
            out_cost_table,
            out_policy_card,
            out_unknowns,
            out_assumptions,
        ]

        btn_submit.click(
            fn=analyze_claim,
            inputs=all_inputs,
            outputs=all_outputs,
        )

        # Wire the Quick-Launch Scenario Buttons
        btn_case_a.click(
            fn=load_demo_case_a,
            inputs=[],
            outputs=all_inputs,
        ).then(
            fn=analyze_claim,
            inputs=all_inputs,
            outputs=all_outputs,
        )

        btn_case_b.click(
            fn=load_demo_case_b,
            inputs=[],
            outputs=all_inputs,
        ).then(
            fn=analyze_claim,
            inputs=all_inputs,
            outputs=all_outputs,
        )

        btn_case_c.click(
            fn=load_demo_case_c,
            inputs=[],
            outputs=all_inputs,
        ).then(
            fn=analyze_claim,
            inputs=all_inputs,
            outputs=all_outputs,
        )

    return demo


def main() -> None:
    """Launches the local Gradio development server."""
    demo = create_app()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, css=APP_CSS)


if __name__ == "__main__":
    main()
