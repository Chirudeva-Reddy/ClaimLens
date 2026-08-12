"""Download a Roboflow Universe dataset into data/raw/.

Find --workspace/--project/--version on the target Roboflow Universe
project page: click "Download this Dataset", pick the YOLOv8 format,
choose "show download code", and copy the three values from the
generated snippet. For ClaimLens this should be the CarDD mirror
described in PROJECT_BLUEPRINT.md §7 (CC BY 4.0 licensed).

Usage:
    ROBOFLOW_API_KEY=... python scripts/download_data.py \\
        --workspace <workspace> --project <project> --version <version>
"""

import argparse
import os

from roboflow import Roboflow


def download(workspace: str, project: str, version: int, dest: str) -> str:
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        raise SystemExit("ROBOFLOW_API_KEY is not set")
    rf = Roboflow(api_key=api_key)
    proj = rf.workspace(workspace).project(project)
    dataset = proj.version(version).download("yolov8", location=dest)
    return dataset.location


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--dest", default="data/raw")
    args = parser.parse_args()
    location = download(args.workspace, args.project, args.version, args.dest)
    print(f"Downloaded dataset to {location}")


if __name__ == "__main__":
    main()
