import re
from pathlib import Path

import pytest

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SPLITS = ["train", "valid", "test"]

# Roboflow export names images "<source-id>_<ext>.rf.<hash>.<ext>";
# the part before "_<ext>.rf." is the original source image's identity.
_SOURCE_ID_RE = re.compile(r"^(.*)_(?:jpg|jpeg|png)\.rf\.", re.IGNORECASE)


def _source_ids(split: str) -> set[str]:
    images_dir = DATA_RAW / split / "images"
    ids = set()
    for path in images_dir.iterdir():
        match = _SOURCE_ID_RE.match(path.stem + path.suffix)
        ids.add(match.group(1) if match else path.stem)
    return ids


def test_no_source_image_appears_in_more_than_one_split():
    if not DATA_RAW.exists():
        pytest.skip("data/raw not present — run scripts/download_data.py first")

    ids_by_split = {split: _source_ids(split) for split in SPLITS}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1 :]:
            overlap = ids_by_split[a] & ids_by_split[b]
            assert not overlap, (
                f"{len(overlap)} source images in both {a} and {b}: {sorted(overlap)[:5]}"
            )
