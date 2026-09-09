"""Run the real pipeline once per scenario and freeze the responses.

GitHub Pages cannot run the models, so the published demo replays these.
Regenerate with:  python scripts/bake-site-fixtures.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from claimlens.api import SCENARIOS, app

OUT = Path("site")


def main() -> None:
    client = TestClient(app)
    (OUT / "fixtures").mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)

    index: dict[str, dict[str, object]] = {}
    for case_id, scenario in SCENARIOS.items():
        response = client.post(
            "/api/analyze",
            data={
                "scenario_id": case_id,
                "brand": scenario["brand"],
                "acv": scenario["acv"],
                "jurisdiction": scenario["jurisdiction"],
                "custom_threshold": scenario["custom_threshold"],
            },
        )
        response.raise_for_status()
        payload = response.json()
        (OUT / "fixtures" / f"{case_id}.json").write_text(
            json.dumps(payload, separators=(",", ":"))
        )
        shutil.copyfile(scenario["image_path"], OUT / "assets" / f"{case_id}.jpg")
        index[case_id] = {"brand": scenario["brand"], "acv": scenario["acv"]}
        print(
            f"{case_id}: {payload['triage']['headline']} "
            f"({payload['financials']['loss_ratio_pct']}% of AED {payload['financials']['acv_aed']:,.0f})"
        )

    (OUT / "fixtures" / "index.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
