from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

MIN_WIDTH = 480
MIN_HEIGHT = 480
# ponytail: heuristic variance-of-Laplacian threshold. The textbook ~100
# starting point rejected 30% of real CarDD training images (640x640,
# stretch-resized by Roboflow) as "too blurry" — recalibrated against a
# 30-image sample of that set (min observed variance ~29) to a much lower
# floor that only catches genuinely unusable frames. Revisit once real user
# submissions (not resized training data) are available to test against.
BLUR_VARIANCE_THRESHOLD = 15.0

_LAPLACIAN_KERNEL = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)


@dataclass(frozen=True)
class QualityVerdict:
    accepted: bool
    reason: str | None = None


def check_image_quality(path: Path) -> QualityVerdict:
    try:
        image = Image.open(path)
        image.load()
    except Exception:  # noqa: BLE001 — untrusted upload, PIL raises varied error types
        return QualityVerdict(accepted=False, reason="unreadable_file")

    width, height = image.size
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return QualityVerdict(accepted=False, reason="resolution_too_low")

    if _laplacian_variance(image) < BLUR_VARIANCE_THRESHOLD:
        return QualityVerdict(accepted=False, reason="too_blurry")

    return QualityVerdict(accepted=True)


def _laplacian_variance(image: Image.Image) -> float:
    edges = image.convert("L").filter(_LAPLACIAN_KERNEL)
    # Pillow's Kernel filter leaves the 1px border unfiltered (copies the
    # source pixel), which would otherwise inject phantom edge variance.
    width, height = edges.size
    interior = edges.crop((1, 1, width - 1, height - 1))
    return ImageStat.Stat(interior).var[0]
