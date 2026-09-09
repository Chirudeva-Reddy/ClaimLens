"""Shared fixtures and utilities for the ClaimLens E2E test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

from claimlens.api import app

# Progressive testability check: determine if M1 preprocessing module is implemented
try:
    from claimlens.detection.preprocessing import (  # type: ignore
        letterbox_image,
        unletterbox_coords,
    )

    HAS_PREPROCESSING = True
except ImportError:
    HAS_PREPROCESSING = False
    letterbox_image = None
    unletterbox_coords = None


class MockBoxes:
    """Mock Ultralytics Boxes container for deterministic geometric testing."""

    def __init__(
        self,
        xyxy: list[list[float]] | np.ndarray,
        conf: list[float] | np.ndarray,
        cls: list[int] | np.ndarray,
    ) -> None:
        self.xyxy = torch.tensor(xyxy, dtype=torch.float32)
        self.conf = torch.tensor(conf, dtype=torch.float32)
        self.cls = torch.tensor(cls, dtype=torch.int32)

    def __len__(self) -> int:
        return len(self.xyxy)


class MockMasks:
    """Mock Ultralytics Masks container with polygon vertex lists."""

    def __init__(self, xy: list[list[list[float]] | np.ndarray]) -> None:
        self.xy = [np.array(pts, dtype=np.float32) for pts in xy]

    def __len__(self) -> int:
        return len(self.xy)


class MockYOLOResult:
    """Mock Ultralytics Results object mimicking YOLOv8-seg prediction outputs."""

    def __init__(
        self,
        boxes: MockBoxes | None,
        masks: MockMasks | None,
        names: dict[int, str],
        orig_shape: tuple[int, int] = (640, 640),
    ) -> None:
        self.boxes = boxes
        self.masks = masks
        self.names = names
        self.orig_shape = orig_shape


@pytest.fixture
def create_sharp_image() -> Callable[[int, int, int], Image.Image]:
    """Generates a high-contrast checkerboard image that reliably passes the quality gate.

    The quality gate evaluates ImageStat.Stat(interior).var[0] on a 3x3 Laplacian filter.
    Checkerboard edges guarantee high Laplacian variance (>50.0), far exceeding the 15.0 floor.
    """

    def _factory(width: int = 640, height: int = 640, tile: int = 20) -> Image.Image:
        tile_w = max(2, width // tile)
        tile_h = max(2, height // tile)
        small = Image.new("L", (tile_w, tile_h))
        pixels = small.load()
        for y in range(tile_h):
            for x in range(tile_w):
                pixels[x, y] = 255 if (x + y) % 2 == 0 else 0
        return small.resize((width, height), Image.NEAREST).convert("RGB")

    return _factory


@pytest.fixture
def create_image_file(
    tmp_path: Path, create_sharp_image: Callable[[int, int, int], Image.Image]
) -> Callable[..., Path]:
    """Saves a sharp synthetic image to disk for end-to-end file-based inspection."""

    def _factory(
        filename: str = "test_image.jpg",
        width: int = 640,
        height: int = 640,
        orientation: int | None = None,
    ) -> Path:
        path = tmp_path / filename
        img = create_sharp_image(width, height)
        if orientation is not None:
            exif = img.getexif()
            exif[0x0112] = int(orientation)
            img.save(path, format="JPEG", exif=exif)
        else:
            img.save(path, format="JPEG")
        return path

    return _factory


@pytest.fixture
def mock_yolo_result_factory() -> Callable[..., MockYOLOResult]:
    """Factory for creating mock YOLOv8 segmentation results with specific geometry."""

    def _factory(
        boxes_xyxy: list[list[float]],
        scores: list[float],
        class_ids: list[int],
        polygons: list[list[list[float]]],
        names: dict[int, str],
        orig_shape: tuple[int, int] = (640, 640),
    ) -> MockYOLOResult:
        boxes = MockBoxes(boxes_xyxy, scores, class_ids) if boxes_xyxy else None
        masks = MockMasks(polygons) if polygons else None
        return MockYOLOResult(boxes, masks, names, orig_shape)

    return _factory


@pytest.fixture
def api_client() -> TestClient:
    """FastAPI TestClient instance for testing REST API endpoints."""
    return TestClient(app)


@pytest.fixture
def demo_image_paths() -> dict[str, Path]:
    """Returns absolute paths to repository demo case images."""
    base_dir = Path(__file__).parent.parent.parent
    return {
        "case_a": base_dir / "data/demo_examples/case_a_repairable.jpg",
        "case_b": base_dir / "data/demo_examples/case_b_total_loss.jpg",
        "case_c": base_dir / "data/demo_examples/case_c_structural_inspection.jpg",
    }
