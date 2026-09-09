"""Tests for the ClaimLens Gradio application in AED."""

from __future__ import annotations

import gradio as gr
from PIL import Image

from claimlens.app import analyze_claim, create_app


def test_create_app_initialization() -> None:
    """Verifies that Gradio Blocks app builds cleanly without errors."""
    app = create_app()
    assert isinstance(app, gr.Blocks)


def test_analyze_claim_no_image() -> None:
    """Verifies graceful handling when no photo is provided."""
    triage_html, kpi_html, img, table, policy, unknowns, assumptions = analyze_claim(
        image_path=None,
        brand_label="Toyota",
        pre_accident_value=120000,
        jurisdiction_label="UAE Unified Motor Policy (50% Economic Test)",
        custom_threshold_pct=50,
    )
    assert "NO PHOTO PROVIDED" in triage_html
    assert kpi_html == ""
    assert img is None
    assert table == []
    assert policy == ""
    assert unknowns == ""
    assert assumptions == ""


def test_analyze_claim_case_a_repairable() -> None:
    """Verifies end-to-end Gradio pipeline on Demo Case A (Minor Repairable in AED)."""
    triage_html, kpi_html, img, table, policy, unknowns, assumptions = analyze_claim(
        image_path="data/demo_examples/case_a_repairable.jpg",
        brand_label="Toyota",
        pre_accident_value=120000,
        jurisdiction_label="UAE Unified Motor Policy (50% Economic Test)",
        custom_threshold_pct=50,
    )
    assert "PROBABLY REPAIRABLE" in triage_html
    assert "ECONOMIC_REPAIRABLE_WITHIN_THRESHOLD" in triage_html
    assert "Visible Repair Cost" in kpi_html
    assert "AED" in kpi_html
    assert "120,000" in kpi_html
    assert isinstance(img, Image.Image)
    assert len(table) > 0
    assert "AED" in table[0][3]
    assert "Unified Motor" in policy or "CONFIRMED CLAUSE" in policy
    assert "Unresolvable Physical Factors" in unknowns
    assert "Cost Estimator Assumptions" in assumptions


def test_analyze_claim_case_b_total_loss() -> None:
    """Verifies end-to-end Gradio pipeline on Demo Case B (Probable Total Loss in AED)."""
    triage_html, kpi_html, img, table, policy, unknowns, assumptions = analyze_claim(
        image_path="data/demo_examples/case_b_total_loss.jpg",
        brand_label="General Market Standard",
        pre_accident_value=15000,
        jurisdiction_label="UAE Unified Motor Policy (50% Economic Test)",
        custom_threshold_pct=50,
    )
    assert "PROBABLE TOTAL LOSS" in triage_html
    assert "ECONOMIC_THRESHOLD_EXCEEDED" in triage_html
    assert "Visible Repair Cost" in kpi_html
    assert "AED" in kpi_html
    assert isinstance(img, Image.Image)
    assert len(table) > 0
    assert "Constructive Total Loss — 50% Economic Rule" in policy or "CONFIRMED CLAUSE" in policy
    assert "Unresolvable Physical Factors" in unknowns
    assert "Cost Estimator Assumptions" in assumptions


def test_analyze_claim_case_c_structural_inspection() -> None:
    """Verifies end-to-end Gradio pipeline on Demo Case C (Structural Inspection in AED)."""
    triage_html, kpi_html, img, table, policy, unknowns, assumptions = analyze_claim(
        image_path="data/demo_examples/case_c_structural_inspection.jpg",
        brand_label="Toyota",
        pre_accident_value=85000,
        jurisdiction_label="UAE Unified Motor Policy (50% Economic Test)",
        custom_threshold_pct=50,
    )
    assert "INSUFFICIENT EVIDENCE" in triage_html
    assert "STRUCTURAL_INTEGRITY_SAFE_ABSTENTION" in triage_html
    assert "Visible Repair Cost" in kpi_html
    assert "AED" in kpi_html
    assert isinstance(img, Image.Image)
    assert isinstance(table, list)
    assert (
        "Chassis & Structural Frame Roadworthiness Rule" in policy or "CONFIRMED CLAUSE" in policy
    )
    assert "Unresolvable Physical Factors" in unknowns
    assert "Cost Estimator Assumptions" in assumptions
