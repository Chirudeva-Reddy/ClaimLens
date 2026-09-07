from pathlib import Path

import pytest
import yaml

PARTS_DIR = Path("data/parts")


@pytest.mark.skipif(not PARTS_DIR.exists(), reason="data/parts not yet generated")
def test_parts_splits_exist_and_non_empty():
    for split in ["train", "valid", "test"]:
        img_dir = PARTS_DIR / split / "images"
        lbl_dir = PARTS_DIR / split / "labels"
        assert img_dir.exists(), f"Missing {img_dir}"
        assert lbl_dir.exists(), f"Missing {lbl_dir}"
        images = list(img_dir.glob("*.*"))
        labels = list(lbl_dir.glob("*.txt"))
        assert len(images) > 0, f"Split {split} images empty"
        assert len(images) == len(labels), f"Image and label count mismatch in {split}"


@pytest.mark.skipif(not PARTS_DIR.exists(), reason="data/parts not yet generated")
def test_parts_no_split_leakage():
    train_stems = {p.stem for p in (PARTS_DIR / "train" / "images").glob("*.*")}
    valid_stems = {p.stem for p in (PARTS_DIR / "valid" / "images").glob("*.*")}
    test_stems = {p.stem for p in (PARTS_DIR / "test" / "images").glob("*.*")}

    assert not (train_stems & valid_stems), f"Train/Valid leakage: {train_stems & valid_stems}"
    assert not (train_stems & test_stems), f"Train/Test leakage: {train_stems & test_stems}"
    assert not (valid_stems & test_stems), f"Valid/Test leakage: {valid_stems & test_stems}"


@pytest.mark.skipif(not PARTS_DIR.exists(), reason="data/parts not yet generated")
def test_parts_data_yaml_valid():
    yaml_path = PARTS_DIR / "data.yaml"
    assert yaml_path.exists()
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)

    assert config["nc"] == 21
    assert len(config["names"]) == 21
    assert "front-bumper" in config["names"]
    assert "quarter-panel" in config["names"]
    assert "rocker-panel" in config["names"]


@pytest.mark.skipif(not PARTS_DIR.exists(), reason="data/parts not yet generated")
def test_parts_label_coordinates_normalized():
    # Sample 20 label files and verify coordinates are within [0, 1]
    lbl_files = list((PARTS_DIR / "train" / "labels").glob("*.txt"))[:20]
    for lbl_file in lbl_files:
        with open(lbl_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                class_id = int(parts[0])
                assert 0 <= class_id < 21
                coords = [float(x) for x in parts[1:]]
                assert len(coords) >= 6  # At least 3 pairs (x, y)
                assert len(coords) % 2 == 0
                for c in coords:
                    assert 0.0 <= c <= 1.0, f"Coordinate {c} out of bounds in {lbl_file}"
