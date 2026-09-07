"""Convert Humans in the Loop car parts dataset into YOLOv8-seg format.

Reads the downloaded Supervisely-format annotations and images from the
Kaggle dataset cache, converts polygon coordinates to normalized YOLO format,
and partitions deterministically into train/valid/test splits.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from PIL import Image

DEFAULT_SOURCE = Path(
    "/Users/tacticalcamel/.cache/kagglehub/datasets/humansintheloop/car-parts-and-car-damages/versions/2/Car damages dataset/File1"
)
DEFAULT_DEST = Path("data/parts")

PART_CLASSES = [
    "front-bumper",
    "back-bumper",
    "hood",
    "trunk",
    "front-door",
    "back-door",
    "fender",
    "quarter-panel",
    "rocker-panel",
    "windshield",
    "back-windshield",
    "front-window",
    "back-window",
    "headlight",
    "tail-light",
    "license-plate",
    "mirror",
    "roof",
    "grille",
    "front-wheel",
    "back-wheel",
]

# Normalization mapping from raw class titles in meta.json
TITLE_TO_CLASS = {
    name.lower().replace(" ", "-"): name.lower().replace(" ", "-") for name in PART_CLASSES
}
TITLE_TO_CLASS.update(
    {
        "quarter-panel": "quarter-panel",
        "front-wheel": "front-wheel",
        "back-window": "back-window",
        "trunk": "trunk",
        "front-door": "front-door",
        "rocker-panel": "rocker-panel",
        "grille": "grille",
        "windshield": "windshield",
        "front-window": "front-window",
        "back-door": "back-door",
        "headlight": "headlight",
        "back-wheel": "back-wheel",
        "back-windshield": "back-windshield",
        "hood": "hood",
        "fender": "fender",
        "tail-light": "tail-light",
        "license-plate": "license-plate",
        "front-bumper": "front-bumper",
        "back-bumper": "back-bumper",
        "mirror": "mirror",
        "roof": "roof",
    }
)

CLASS_TO_IDX = {name: i for i, name in enumerate(PART_CLASSES)}


def convert_annotations_and_images(
    source_dir: Path,
    dest_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, int]:
    img_dir = source_dir / "img"
    ann_dir = source_dir / "ann"

    if not img_dir.exists() or not ann_dir.exists():
        raise FileNotFoundError(f"Missing img or ann dir in {source_dir}")

    ann_files = sorted(ann_dir.glob("*.json"))
    if not ann_files:
        raise FileNotFoundError(f"No annotation JSON files found in {ann_dir}")

    # Build image pairs
    valid_pairs: list[tuple[Path, Path]] = []
    for ann_path in ann_files:
        image_name = ann_path.name.replace(".json", "")
        img_path = img_dir / image_name
        if not img_path.exists():
            img_path = img_dir / ann_path.stem
        if img_path.exists():
            valid_pairs.append((img_path, ann_path))

    random.seed(seed)
    random.shuffle(valid_pairs)

    n_total = len(valid_pairs)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)

    splits = {
        "train": valid_pairs[:n_train],
        "valid": valid_pairs[n_train : n_train + n_val],
        "test": valid_pairs[n_train + n_val :],
    }

    # Prepare directories
    for split in ["train", "valid", "test"]:
        (dest_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (dest_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    counts = {"train": 0, "valid": 0, "test": 0}

    for split_name, pairs in splits.items():
        for img_path, ann_path in pairs:
            clean_stem = f"part_{img_path.stem.replace(' ', '_')}"
            dest_img_path = dest_dir / split_name / "images" / f"{clean_stem}{img_path.suffix}"
            dest_txt_path = dest_dir / split_name / "labels" / f"{clean_stem}.txt"

            shutil.copy2(img_path, dest_img_path)

            with open(ann_path, "r", encoding="utf-8") as f:
                ann_data = json.load(f)

            # Image dimensions
            width = ann_data.get("size", {}).get("width")
            height = ann_data.get("size", {}).get("height")
            if not width or not height:
                with Image.open(img_path) as img:
                    width, height = img.size

            label_lines = []
            for obj in ann_data.get("objects", []):
                raw_title = obj.get("classTitle", "")
                norm_title = TITLE_TO_CLASS.get(raw_title.lower().replace(" ", "-"))
                if not norm_title or norm_title not in CLASS_TO_IDX:
                    continue

                class_idx = CLASS_TO_IDX[norm_title]
                pts = obj.get("points", {}).get("exterior", [])
                if len(pts) < 3:
                    continue

                # Normalize polygon points
                coord_pairs = []
                for pt in pts:
                    x = max(0.0, min(1.0, pt[0] / width))
                    y = max(0.0, min(1.0, pt[1] / height))
                    coord_pairs.append(f"{x:.6f} {y:.6f}")

                label_lines.append(f"{class_idx} {' '.join(coord_pairs)}")

            with open(dest_txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(label_lines) + ("\n" if label_lines else ""))

            counts[split_name] += 1

    # Write data.yaml
    data_yaml_content = f"""path: {dest_dir.resolve()}
train: train/images
val: valid/images
test: test/images

nc: {len(PART_CLASSES)}
names: {PART_CLASSES}
"""
    with open(dest_dir / "data.yaml", "w", encoding="utf-8") as f:
        f.write(data_yaml_content)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()

    print(f"Converting car parts dataset from {args.source} to {args.dest}...")
    counts = convert_annotations_and_images(args.source, args.dest)
    print(f"Done! Splits: {counts}")


if __name__ == "__main__":
    main()
