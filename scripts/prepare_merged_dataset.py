"""Prepare expanded and merged vehicle damage dataset for YOLOv8 segmentation.

Ingests the 814 damage images with Supervisely polygon annotations from the
Kaggle dataset cache, aligns class labels into ClaimLens's canonical 6 categories,
converts polygons to normalized YOLO segmentation format, partitions with zero
leakage (including cross-task alignment with data/parts), merges with CarDD (data/raw),
and generates an updated data.yaml configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

DEFAULT_KAGGLE_SOURCE = Path(
    "/Users/tacticalcamel/.cache/kagglehub/datasets/humansintheloop/car-parts-and-car-damages/versions/2/Car parts dataset/File1"
)
DEFAULT_RAW_SOURCE = Path("data/raw")
DEFAULT_PARTS_SOURCE = Path("data/parts")
DEFAULT_DEST = Path("data/merged")

CANONICAL_CLASSES = [
    "crack",
    "dent",
    "glass shatter",
    "lamp broken",
    "scratch",
    "tire flat",
]

# Mapping from Kaggle damage class titles (case-insensitive) to ClaimLens class IDs
CLASS_MAPPING: dict[str, int] = {
    "scratch": 4,
    "paint chip": 4,
    "flaking": 4,
    "dent": 1,
    "cracked": 0,
    "broken part": 0,
}

# Explicitly ignored non-damage classes in Kaggle dataset
IGNORED_CLASSES: set[str] = {
    "corrosion",
    "missing part",
}


def compute_md5(file_path: Path) -> str:
    """Compute the MD5 hash of a file."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def convert_supervisely_ann_to_yolo(
    ann_path: Path,
    image_path: Path | None = None,
    image_size: tuple[int, int] | None = None,
) -> tuple[list[str], int, int]:
    """Convert Supervisely polygon annotations to normalized YOLO segmentation lines.

    Returns:
        tuple of (label_lines, valid_damage_count, ignored_count)
    """
    with open(ann_path, "r", encoding="utf-8") as f:
        ann_data = json.load(f)

    # Determine image dimensions (width, height)
    width = ann_data.get("size", {}).get("width")
    height = ann_data.get("size", {}).get("height")
    if not width or not height or width <= 0 or height <= 0:
        if image_size:
            width, height = image_size
        elif image_path and image_path.exists():
            with Image.open(image_path) as img:
                width, height = img.size
        else:
            raise ValueError(f"Could not determine dimensions for {ann_path}")

    label_lines: list[str] = []
    valid_count = 0
    ignored_count = 0

    for obj in ann_data.get("objects", []):
        raw_title = str(obj.get("classTitle", "")).strip().lower()
        if raw_title not in CLASS_MAPPING:
            ignored_count += 1
            continue

        class_idx = CLASS_MAPPING[raw_title]
        pts = obj.get("points", {}).get("exterior", [])
        if len(pts) < 3:
            continue

        coord_pairs: list[str] = []
        for pt in pts:
            x = max(0.0, min(1.0, float(pt[0]) / width))
            y = max(0.0, min(1.0, float(pt[1]) / height))
            coord_pairs.append(f"{x:.6f} {y:.6f}")

        label_lines.append(f"{class_idx} {' '.join(coord_pairs)}")
        valid_count += 1

    return label_lines, valid_count, ignored_count


def load_kaggle_image_ann_pairs(
    kaggle_source: Path,
) -> list[tuple[Path, Path, str]]:
    """Discover all matching image and annotation pairs in the Kaggle source directory.

    Returns list of (image_path, ann_path, md5_hash).
    """
    img_dir = kaggle_source / "img"
    ann_dir = kaggle_source / "ann"

    if not img_dir.exists() or not ann_dir.exists():
        raise FileNotFoundError(f"Missing 'img' or 'ann' directory under {kaggle_source}")

    ann_files = sorted(ann_dir.glob("*.json"))
    if not ann_files:
        raise FileNotFoundError(f"No annotation JSON files found in {ann_dir}")

    pairs: list[tuple[Path, Path, str]] = []
    for ann_path in ann_files:
        image_name = ann_path.name.replace(".json", "")
        img_path = img_dir / image_name
        if not img_path.exists():
            img_path = img_dir / ann_path.stem
        if not img_path.exists():
            # Try matching with various extensions
            for ext in [".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"]:
                candidate = img_dir / f"{ann_path.stem}{ext}"
                if candidate.exists():
                    img_path = candidate
                    break

        if img_path.exists():
            file_hash = compute_md5(img_path)
            pairs.append((img_path, ann_path, file_hash))
        else:
            print(f"Warning: No matching image found for annotation {ann_path.name}")

    return pairs


def load_split_hashes(base_dir: Path) -> dict[str, set[str]]:
    """Load MD5 hashes for images in train/valid/test splits of a dataset."""
    split_hashes: dict[str, set[str]] = {"train": set(), "valid": set(), "test": set()}
    for split in ["train", "valid", "test"]:
        split_dir = base_dir / split / "images"
        if not split_dir.exists() and split == "valid":
            split_dir = base_dir / "val" / "images"
        if split_dir.exists():
            for p in split_dir.glob("*.*"):
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                    split_hashes[split].add(compute_md5(p))
    return split_hashes


def partition_kaggle_dataset(
    pairs: list[tuple[Path, Path, str]],
    parts_source: Path | None = DEFAULT_PARTS_SOURCE,
    test_count: int = 160,
    val_ratio: float = 0.10,
    seed: int = 42,
) -> dict[str, list[tuple[Path, Path, str]]]:
    """Partition Kaggle dataset into train, valid, and test sets.

    If parts_source exists, images shared with data/parts follow the parts split
    (parts train -> merged train, parts valid -> merged valid, parts test -> merged test)
    to strictly eliminate cross-task leakage.
    Remaining unique images are allocated to reach test_count for the held-out test
    set and val_ratio for validation.
    """
    rng = random.Random(seed)

    parts_hashes: dict[str, set[str]] | None = None
    if parts_source and parts_source.exists():
        parts_hashes = load_split_hashes(parts_source)

    if parts_hashes and (parts_hashes["train"] or parts_hashes["valid"] or parts_hashes["test"]):
        # Split according to parts alignment
        parts_train_items = [p for p in pairs if p[2] in parts_hashes["train"]]
        parts_val_items = [p for p in pairs if p[2] in parts_hashes["valid"]]
        parts_test_items = [p for p in pairs if p[2] in parts_hashes["test"]]
        disjoint_items = [
            p
            for p in pairs
            if p[2] not in parts_hashes["train"]
            and p[2] not in parts_hashes["valid"]
            and p[2] not in parts_hashes["test"]
        ]

        rng.shuffle(disjoint_items)

        # Allocate test set: start with parts_test_items, top up from disjoint
        needed_test = max(0, test_count - len(parts_test_items))
        needed_test = min(needed_test, len(disjoint_items))

        test_items = list(parts_test_items) + disjoint_items[:needed_test]
        remaining = disjoint_items[needed_test:]

        # Allocate validation set: start with parts_val_items, top up to ~val_ratio
        target_val = int(len(pairs) * val_ratio)
        needed_val = max(0, target_val - len(parts_val_items))
        needed_val = min(needed_val, len(remaining))

        val_items = list(parts_val_items) + remaining[:needed_val]
        train_items = list(parts_train_items) + remaining[needed_val:]
    else:
        # Standalone random split
        shuffled = list(pairs)
        rng.shuffle(shuffled)
        test_items = shuffled[:test_count]
        remaining = shuffled[test_count:]
        n_val = int(len(pairs) * val_ratio)
        val_items = remaining[:n_val]
        train_items = remaining[n_val:]

    # Enforce zero leakage verification
    train_h = {it[2] for it in train_items}
    val_h = {it[2] for it in val_items}
    test_h = {it[2] for it in test_items}

    assert not (train_h & val_h), f"Kaggle train/val leakage: {len(train_h & val_h)} items"
    assert not (train_h & test_h), f"Kaggle train/test leakage: {len(train_h & test_h)} items"
    assert not (val_h & test_h), f"Kaggle val/test leakage: {len(val_h & test_h)} items"
    assert len(train_items) + len(val_items) + len(test_items) == len(pairs)

    return {
        "train": train_items,
        "valid": val_items,
        "test": test_items,
    }


def prepare_merged_dataset(
    kaggle_source: Path = DEFAULT_KAGGLE_SOURCE,
    raw_source: Path = DEFAULT_RAW_SOURCE,
    parts_source: Path | None = DEFAULT_PARTS_SOURCE,
    dest_dir: Path = DEFAULT_DEST,
    test_count: int = 160,
    val_ratio: float = 0.10,
    seed: int = 42,
    clean: bool = True,
) -> dict[str, Any]:
    """Build the merged dataset in dest_dir."""
    if not kaggle_source.exists():
        raise FileNotFoundError(f"Kaggle source not found: {kaggle_source}")
    if not raw_source.exists():
        raise FileNotFoundError(f"Raw CarDD source not found: {raw_source}")

    if clean and dest_dir.exists():
        print(f"Cleaning existing destination directory: {dest_dir}")
        shutil.rmtree(dest_dir)

    for split in ["train", "valid", "test"]:
        (dest_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (dest_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    # 1. Ingest and copy raw CarDD dataset
    print(f"Ingesting raw CarDD dataset from {raw_source}...")
    raw_counts = {"train": 0, "valid": 0}
    for split in ["train", "valid"]:
        raw_img_dir = raw_source / split / "images"
        raw_lbl_dir = raw_source / split / "labels"
        if not raw_img_dir.exists() and split == "valid":
            raw_img_dir = raw_source / "val" / "images"
            raw_lbl_dir = raw_source / "val" / "labels"

        if not raw_img_dir.exists():
            continue

        for img_path in sorted(raw_img_dir.glob("*.*")):
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            lbl_path = raw_lbl_dir / f"{img_path.stem}.txt"
            dest_img = dest_dir / split / "images" / img_path.name
            dest_lbl = dest_dir / split / "labels" / f"{img_path.stem}.txt"

            shutil.copy2(img_path, dest_img)
            if lbl_path.exists():
                shutil.copy2(lbl_path, dest_lbl)
            else:
                # Create empty label file if missing
                dest_lbl.write_text("", encoding="utf-8")
            raw_counts[split] += 1

    print(f"Raw CarDD ingested: train={raw_counts['train']}, valid={raw_counts['valid']}")

    # 2. Ingest and partition Kaggle dataset
    print(f"Ingesting Kaggle damage dataset from {kaggle_source}...")
    pairs = load_kaggle_image_ann_pairs(kaggle_source)
    print(f"Discovered {len(pairs)} Kaggle image-annotation pairs.")

    splits = partition_kaggle_dataset(
        pairs,
        parts_source=parts_source,
        test_count=test_count,
        val_ratio=val_ratio,
        seed=seed,
    )

    kaggle_counts = {"train": 0, "valid": 0, "test": 0}
    class_polygon_counts: dict[int, int] = {i: 0 for i in range(len(CANONICAL_CLASSES))}
    total_ignored_annotations = 0

    for split_name, item_list in splits.items():
        for img_path, ann_path, _ in item_list:
            clean_stem = f"kaggle_dmg_{img_path.stem.replace(' ', '_').lower()}"
            dest_img = dest_dir / split_name / "images" / f"{clean_stem}{img_path.suffix}"
            dest_lbl = dest_dir / split_name / "labels" / f"{clean_stem}.txt"

            shutil.copy2(img_path, dest_img)

            label_lines, _valid_cnt, ign_cnt = convert_supervisely_ann_to_yolo(
                ann_path=ann_path,
                image_path=img_path,
            )
            total_ignored_annotations += ign_cnt

            for line in label_lines:
                parts = line.strip().split()
                if parts:
                    cls_id = int(parts[0])
                    class_polygon_counts[cls_id] += 1

            with open(dest_lbl, "w", encoding="utf-8") as f:
                f.write("\n".join(label_lines) + ("\n" if label_lines else ""))

            kaggle_counts[split_name] += 1

    print(f"Kaggle ingested: {kaggle_counts}")
    print(f"Polygon counts by class: {class_polygon_counts}")
    print(f"Ignored non-damage annotations: {total_ignored_annotations}")

    # 3. Create 'val' symlink for Ultralytics YOLO compatibility
    val_symlink = dest_dir / "val"
    if not val_symlink.exists():
        try:
            val_symlink.symlink_to("valid", target_is_directory=True)
        except OSError:
            pass

    # 4. Generate updated data.yaml
    yaml_path = dest_dir / "data.yaml"
    data_yaml_content = f"""path: {dest_dir.resolve()}
train: train/images
val: valid/images
test: test/images

nc: {len(CANONICAL_CLASSES)}
names:
{yaml_format_names(CANONICAL_CLASSES)}
"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(data_yaml_content)

    print(f"Dataset YAML configuration written to {yaml_path}")

    # 5. Enforce zero leakage across final merged splits
    print("Verifying zero leakage across final merged splits...")
    final_hashes: dict[str, set[str]] = {}
    total_images = {}
    for split in ["train", "valid", "test"]:
        imgs = list((dest_dir / split / "images").glob("*.*"))
        lbls = list((dest_dir / split / "labels").glob("*.txt"))
        assert len(imgs) == len(lbls), (
            f"Image/label count mismatch in {split}: {len(imgs)} images vs {len(lbls)} labels"
        )
        total_images[split] = len(imgs)
        h_set: set[str] = set()
        for img in imgs:
            h_set.add(compute_md5(img))
        final_hashes[split] = h_set

    # Assert no cross-split leakage
    train_valid_leak = final_hashes["train"] & final_hashes["valid"]
    train_test_leak = final_hashes["train"] & final_hashes["test"]
    valid_test_leak = final_hashes["valid"] & final_hashes["test"]

    assert not train_valid_leak, f"Train/Valid leakage detected: {len(train_valid_leak)} images"
    assert not train_test_leak, f"Train/Test leakage detected: {len(train_test_leak)} images"
    assert not valid_test_leak, f"Valid/Test leakage detected: {len(valid_test_leak)} images"

    print("Zero leakage verification passed successfully!")
    print(f"Final merged dataset totals: {total_images}")

    summary = {
        "dest_dir": str(dest_dir.resolve()),
        "data_yaml": str(yaml_path.resolve()),
        "raw_counts": raw_counts,
        "kaggle_counts": kaggle_counts,
        "total_images": total_images,
        "class_polygon_counts": class_polygon_counts,
        "test_held_out_count": total_images["test"],
        "zero_leakage": True,
    }
    return summary


def yaml_format_names(names: list[str]) -> str:
    """Format class names as YAML list with indentation."""
    return "\n".join(f"  - {name}" for name in names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kaggle-source",
        type=Path,
        default=DEFAULT_KAGGLE_SOURCE,
        help="Path to Kaggle damage dataset File1 directory",
    )
    parser.add_argument(
        "--raw-source",
        type=Path,
        default=DEFAULT_RAW_SOURCE,
        help="Path to raw CarDD dataset",
    )
    parser.add_argument(
        "--parts-source",
        type=Path,
        default=DEFAULT_PARTS_SOURCE,
        help="Path to parts dataset for cross-task split alignment",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help="Path to output merged dataset directory",
    )
    parser.add_argument(
        "--test-count",
        type=int,
        default=160,
        help="Number of strictly held-out Kaggle test images",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.10,
        help="Validation ratio for Kaggle images",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible partitioning",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete existing destination directory before preparation",
    )

    args = parser.parse_args()

    summary = prepare_merged_dataset(
        kaggle_source=args.kaggle_source,
        raw_source=args.raw_source,
        parts_source=args.parts_source,
        dest_dir=args.dest,
        test_count=args.test_count,
        val_ratio=args.val_ratio,
        seed=args.seed,
        clean=not args.no_clean,
    )
    print("\nSummary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
