"""Unit and integration tests for dataset expansion and merging (Requirement R2).

Verifies:
- Merged dataset exists with valid images and label files in train, valid, and test splits.
- All polygon coordinates are strictly normalized in [0, 1] with canonical class IDs in [0, 5].
- Zero image ID or image hash leakage across train, val, and test splits.
- Zero cross-task leakage with parts test imagery.
- Dataset YAML configuration is valid and consumable by YOLO (Ultralytics).
- Unit tests for Supervisely-to-YOLO conversion and class alignment logic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from PIL import Image
from ultralytics.data.utils import check_det_dataset

from scripts.prepare_merged_dataset import (
    CANONICAL_CLASSES,
    CLASS_MAPPING,
    compute_md5,
    convert_supervisely_ann_to_yolo,
    partition_kaggle_dataset,
)

MERGED_DIR = Path("data/merged")
PARTS_DIR = Path("data/parts")
RAW_DIR = Path("data/raw")
SPLITS = ["train", "valid", "test"]

_ROBOFLOW_SOURCE_ID_RE = re.compile(r"^(.*)_(?:jpg|jpeg|png)\.rf\.", re.IGNORECASE)


def _extract_source_id(file_path: Path) -> str:
    """Extract canonical source identifier regardless of CarDD or Kaggle prefix."""
    stem = file_path.stem
    match = _ROBOFLOW_SOURCE_ID_RE.match(stem + file_path.suffix)
    if match:
        return match.group(1)
    if stem.startswith("kaggle_dmg_"):
        return stem[len("kaggle_dmg_") :]
    return stem


@pytest.mark.skipif(not MERGED_DIR.exists(), reason="data/merged not yet generated")
def test_merged_splits_exist_and_counts():
    """Verify that train, valid, and test splits exist with matched images and labels."""
    counts = {}
    for split in SPLITS:
        img_dir = MERGED_DIR / split / "images"
        lbl_dir = MERGED_DIR / split / "labels"

        assert img_dir.is_dir(), f"Missing images directory: {img_dir}"
        assert lbl_dir.is_dir(), f"Missing labels directory: {lbl_dir}"

        imgs = sorted(
            p for p in img_dir.glob("*.*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        lbls = sorted(lbl_dir.glob("*.txt"))

        assert len(imgs) > 0, f"Split {split} has no images"
        assert len(imgs) == len(lbls), (
            f"Image/label count mismatch in {split}: {len(imgs)} images vs {len(lbls)} labels"
        )

        # Verify 1-to-1 stem alignment
        img_stems = {p.stem for p in imgs}
        lbl_stems = {p.stem for p in lbls}
        assert img_stems == lbl_stems, f"Mismatch between image and label stems in {split}"

        counts[split] = len(imgs)

    # Verify counts reflect merged CarDD + Kaggle and held-out test split
    # CarDD train (1995) + Kaggle train (~573) = ~2568
    assert counts["train"] >= 2500, f"Expected train >= 2500, got {counts['train']}"
    # CarDD valid (655) + Kaggle valid (~81) = ~736
    assert counts["valid"] >= 700, f"Expected valid >= 700, got {counts['valid']}"
    # Strictly held-out test set (~160 images)
    assert 150 <= counts["test"] <= 170, f"Expected test in [150, 170], got {counts['test']}"


@pytest.mark.skipif(not MERGED_DIR.exists(), reason="data/merged not yet generated")
def test_merged_images_valid_and_openable():
    """Verify that sample images across all splits can be opened without corruption."""
    for split in SPLITS:
        img_dir = MERGED_DIR / split / "images"
        imgs = list(img_dir.glob("*.*"))[:25]  # sample 25 per split
        assert len(imgs) > 0
        for img_path in imgs:
            with Image.open(img_path) as im:
                w, h = im.size
                assert w > 0 and h > 0, f"Invalid dimensions for {img_path}: {im.size}"


@pytest.mark.skipif(not MERGED_DIR.exists(), reason="data/merged not yet generated")
def test_all_polygon_coordinates_normalized_and_classes_canonical():
    """Verify all polygon coordinates in label files are normalized in [0, 1] with class in [0, 5]."""
    for split in SPLITS:
        lbl_dir = MERGED_DIR / split / "labels"
        lbl_files = sorted(lbl_dir.glob("*.txt"))

        # Check all test label files and a broad sample of train/valid
        sample_files = lbl_files if split == "test" else lbl_files[:100]
        total_objects_checked = 0

        for lbl_path in sample_files:
            content = lbl_path.read_text(encoding="utf-8").strip()
            if not content:
                continue

            for line_idx, line in enumerate(content.splitlines()):
                parts = line.strip().split()
                if not parts:
                    continue

                class_id_str = parts[0]
                assert class_id_str.isdigit(), (
                    f"Non-integer class ID '{class_id_str}' in {lbl_path}:{line_idx}"
                )
                class_id = int(class_id_str)
                assert 0 <= class_id < len(CANONICAL_CLASSES), (
                    f"Class ID {class_id} out of bounds [0, 5] in {lbl_path}:{line_idx}"
                )

                coords = [float(x) for x in parts[1:]]
                assert len(coords) >= 6, (
                    f"Polygon in {lbl_path}:{line_idx} has fewer than 3 vertices ({len(coords)} coordinates)"
                )
                assert len(coords) % 2 == 0, (
                    f"Polygon in {lbl_path}:{line_idx} has odd number of coordinates ({len(coords)})"
                )

                for c in coords:
                    assert 0.0 <= c <= 1.0, (
                        f"Coordinate {c} outside [0, 1] in {lbl_path}:{line_idx}"
                    )

                total_objects_checked += 1

        assert total_objects_checked > 0, f"No damage annotations found in split {split}"


@pytest.mark.skipif(not MERGED_DIR.exists(), reason="data/merged not yet generated")
def test_zero_image_hash_leakage_across_splits():
    """Verify zero image content (MD5 hash) overlap between train, valid, and test splits."""
    hashes_by_split: dict[str, set[str]] = {}

    for split in SPLITS:
        img_dir = MERGED_DIR / split / "images"
        split_hashes = set()
        for img_path in img_dir.glob("*.*"):
            if img_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                split_hashes.add(compute_md5(img_path))
        hashes_by_split[split] = split_hashes

    # Test pairwise intersections
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1 :]:
            overlap = hashes_by_split[a] & hashes_by_split[b]
            assert not overlap, (
                f"Data leakage detected! {len(overlap)} images shared between {a} and {b} splits"
            )


@pytest.mark.skipif(not MERGED_DIR.exists(), reason="data/merged not yet generated")
def test_zero_source_id_leakage_across_splits():
    """Verify zero source image ID overlap across train, valid, and test splits."""
    ids_by_split: dict[str, set[str]] = {}

    for split in SPLITS:
        img_dir = MERGED_DIR / split / "images"
        split_ids = set()
        for img_path in img_dir.glob("*.*"):
            if img_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                split_ids.add(_extract_source_id(img_path))
        ids_by_split[split] = split_ids

    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1 :]:
            overlap = ids_by_split[a] & ids_by_split[b]
            assert not overlap, (
                f"Source ID leakage detected! {len(overlap)} IDs shared between {a} and {b}: {sorted(overlap)[:5]}"
            )


@pytest.mark.skipif(
    not MERGED_DIR.exists() or not PARTS_DIR.exists(), reason="Datasets not present"
)
def test_zero_cross_task_leakage_with_parts_test():
    """Verify that no image from data/parts/test appears in data/merged/train or valid."""
    parts_test_dir = PARTS_DIR / "test" / "images"
    if not parts_test_dir.exists():
        pytest.skip("data/parts/test/images not found")

    parts_test_hashes = {compute_md5(p) for p in parts_test_dir.glob("*.*")}

    merged_train_hashes = {compute_md5(p) for p in (MERGED_DIR / "train" / "images").glob("*.*")}
    merged_valid_hashes = {compute_md5(p) for p in (MERGED_DIR / "valid" / "images").glob("*.*")}

    train_leak = parts_test_hashes & merged_train_hashes
    valid_leak = parts_test_hashes & merged_valid_hashes

    assert not train_leak, (
        f"Cross-task leakage: {len(train_leak)} parts test images found in merged train!"
    )
    assert not valid_leak, (
        f"Cross-task leakage: {len(valid_leak)} parts test images found in merged valid!"
    )


@pytest.mark.skipif(not MERGED_DIR.exists(), reason="data/merged not yet generated")
def test_data_yaml_valid_and_yolo_consumable():
    """Verify data.yaml exists, matches schema, and is successfully parsed by Ultralytics."""
    yaml_path = MERGED_DIR / "data.yaml"
    assert yaml_path.is_file(), f"Missing dataset configuration at {yaml_path}"

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert config["nc"] == 6
    assert config["names"] == CANONICAL_CLASSES
    assert "train" in config
    assert "val" in config
    assert "test" in config

    # Consumability test by Ultralytics YOLO dataset checker
    parsed_config = check_det_dataset(str(yaml_path))
    assert parsed_config["nc"] == 6
    assert Path(parsed_config["train"]).exists()
    assert Path(parsed_config["val"]).exists()
    assert Path(parsed_config["test"]).exists()


def test_convert_supervisely_ann_unit(tmp_path: Path):
    """Unit test polygon normalization and class title alignment logic."""
    mock_ann = {
        "size": {"width": 1000, "height": 500},
        "objects": [
            {
                "classTitle": "Scratch",
                "points": {"exterior": [[100, 50], [200, 50], [150, 100]]},
            },
            {
                "classTitle": "Paint chip",
                "points": {"exterior": [[300, 100], [400, 100], [350, 200]]},
            },
            {
                "classTitle": "Dent",
                "points": {"exterior": [[500, 250], [600, 250], [550, 300]]},
            },
            {
                "classTitle": "Broken part",
                "points": {"exterior": [[700, 350], [800, 350], [750, 400]]},
            },
            {
                "classTitle": "Corrosion",  # Should be ignored
                "points": {"exterior": [[10, 10], [20, 10], [15, 20]]},
            },
            {
                "classTitle": "Missing part",  # Should be ignored
                "points": {"exterior": [[30, 30], [40, 30], [35, 40]]},
            },
            {
                "classTitle": "Dent",  # Degenerate: only 2 points, should be skipped
                "points": {"exterior": [[50, 50], [60, 60]]},
            },
        ],
    }

    mock_ann_path = tmp_path / "mock.json"
    with open(mock_ann_path, "w", encoding="utf-8") as f:
        json.dump(mock_ann, f)

    # Verify canonical class alignment mapping
    assert CLASS_MAPPING["scratch"] == 4
    assert CLASS_MAPPING["paint chip"] == 4
    assert CLASS_MAPPING["flaking"] == 4
    assert CLASS_MAPPING["dent"] == 1
    assert CLASS_MAPPING["cracked"] == 0
    assert CLASS_MAPPING["broken part"] == 0

    lines, valid_cnt, ign_cnt = convert_supervisely_ann_to_yolo(mock_ann_path)

    assert valid_cnt == 4
    assert ign_cnt == 2
    assert len(lines) == 4

    # Verify line 0: Scratch -> class 4
    p0 = lines[0].split()
    assert p0[0] == "4"
    assert [float(x) for x in p0[1:]] == [0.1, 0.1, 0.2, 0.1, 0.15, 0.2]

    # Verify line 1: Paint chip -> class 4
    p1 = lines[1].split()
    assert p1[0] == "4"

    # Verify line 2: Dent -> class 1
    p2 = lines[2].split()
    assert p2[0] == "1"

    # Verify line 3: Broken part -> class 0
    p3 = lines[3].split()
    assert p3[0] == "0"


def test_partition_kaggle_dataset_leakage_free_unit(tmp_path: Path):
    """Unit test partition_kaggle_dataset with synthetic pairs."""
    mock_pairs = [
        (tmp_path / f"img_{i}.jpg", tmp_path / f"ann_{i}.json", f"hash_{i}") for i in range(100)
    ]

    splits = partition_kaggle_dataset(
        mock_pairs,
        parts_source=None,
        test_count=20,
        val_ratio=0.10,
        seed=123,
    )

    assert len(splits["test"]) == 20
    assert len(splits["valid"]) == 10
    assert len(splits["train"]) == 70

    h_train = {p[2] for p in splits["train"]}
    h_val = {p[2] for p in splits["valid"]}
    h_test = {p[2] for p in splits["test"]}

    assert not (h_train & h_val)
    assert not (h_train & h_test)
    assert not (h_val & h_test)
