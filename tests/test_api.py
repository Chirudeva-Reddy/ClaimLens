"""Tests for ClaimLens FastAPI REST API endpoints."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from claimlens.api import app

client = TestClient(app)


def test_api_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "ClaimLens" in data["service"]


def test_api_list_scenarios() -> None:
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 3
    ids = {s["id"] for s in scenarios}
    assert ids == {"case_a", "case_b", "case_c"}


def test_api_get_scenario_image() -> None:
    response = client.get("/api/scenarios/case_a/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 1000


def test_api_recalculate_economic_threshold() -> None:
    # 1. Below 50% threshold -> Repairable
    payload = {
        "repair_cost_median_aed": 5000.0,
        "acv_aed": 50000.0,
        "jurisdiction": "uae_50",
        "custom_threshold": 50.0,
        "structural_risk_flag": False,
        "has_line_items": True,
    }
    res = client.post("/api/recalculate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["outcome"] == "PROBABLY_REPAIRABLE"
    assert data["status_color"] == "emerald"
    assert data["financials"]["loss_ratio_pct"] == 10.0

    # 2. Above 50% threshold -> Total Loss
    payload["repair_cost_median_aed"] = 30000.0
    res2 = client.post("/api/recalculate", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["outcome"] == "PROBABLE_TOTAL_LOSS_REVIEW"
    assert data2["status_color"] == "ruby"
    assert data2["financials"]["loss_ratio_pct"] == 60.0

    # 3. Structural risk flag -> Safe Abstention
    payload["structural_risk_flag"] = True
    res3 = client.post("/api/recalculate", json=payload)
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["outcome"] == "INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED"
    assert data3["status_color"] == "amber"


def test_api_analyze_scenario_a() -> None:
    response = client.post(
        "/api/analyze",
        data={
            "scenario_id": "case_a",
            "brand": "Toyota",
            "acv": "120000",
            "jurisdiction": "uae_50",
            "custom_threshold": "50",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quality_gate"]["accepted"] is True
    assert data["triage"]["outcome"] == "PROBABLY_REPAIRABLE"
    assert data["triage"]["status_color"] == "emerald"
    assert data["financials"]["currency"] == "AED"
    assert len(data["polygons"]) > 0
    assert len(data["line_items"]) > 0
    assert len(data["policy_guidance"]) > 0


def test_api_analyze_quality_gate_rejection(tmp_path: Path) -> None:
    # Generate tiny 50x50 black image which fails quality gate
    bad_img = Image.new("RGB", (50, 50), color="black")
    buf = io.BytesIO()
    bad_img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/api/analyze",
        files={"image": ("dark_small.jpg", buf, "image/jpeg")},
        data={
            "brand": "Toyota",
            "acv": "100000",
            "jurisdiction": "uae_50",
            "custom_threshold": "50",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quality_gate"]["accepted"] is False
    assert data["triage"]["outcome"] == "QUALITY_GATE_REJECTED"


def test_frontend_index_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "ClaimLens" in response.text
    assert "CBUAE Unified Motor Policy Aligned" in response.text
