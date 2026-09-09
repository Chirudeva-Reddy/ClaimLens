"""Constant-resolution image preprocessing and coordinate transformation utilities."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageOps


def letterbox_image(
    image: Image.Image,
    target_size: tuple[int, int] = (640, 640),
    fill: tuple[int, int, int] = (114, 114, 114),
) -> tuple[Image.Image, dict[str, Any]]:
    """Transform an arbitrary-dimension image to a constant resolution using letterboxing.

    Applies EXIF orientation normalization, computes an aspect-ratio-preserving
    scale factor, resizes with bilinear resampling, and center-pads onto a neutral
    fill canvas of size `target_size`.

    Args:
        image: Source PIL image.
        target_size: Desired (width, height) output canvas, defaults to (640, 640).
        fill: RGB color tuple for padding bars, defaults to neutral gray (114, 114, 114).

    Returns:
        A tuple of (letterboxed_image, metadata_dict) where metadata contains:
        - scale: float scaling factor applied to original image
        - pad_left: int horizontal padding offset in pixels
        - pad_top: int vertical padding offset in pixels
        - orig_width: int width of image after EXIF normalization
        - orig_height: int height of image after EXIF normalization
        - width: int alias for orig_width
        - height: int alias for orig_height
        - target_width: int target canvas width
        - target_height: int target canvas height
    """
    if image.size[0] <= 0 or image.size[1] <= 0:
        raise ValueError(f"Invalid image dimensions: {image.size[0]}x{image.size[1]}")

    target_w, target_h = int(target_size[0]), int(target_size[1])
    if target_w <= 0 or target_h <= 0:
        raise ValueError(f"Invalid target_size: {target_size}. Dimensions must be positive.")

    # 1. Normalize EXIF orientation tags
    normalized_image = ImageOps.exif_transpose(image)
    if normalized_image is None:
        normalized_image = image

    if normalized_image.mode != "RGB":
        normalized_image = normalized_image.convert("RGB")

    orig_width, orig_height = normalized_image.size
    if orig_width <= 0 or orig_height <= 0:
        raise ValueError(f"Invalid image dimensions: {orig_width}x{orig_height}")

    # 2. Compute aspect-ratio preserving scale factor
    scale = min(target_w / orig_width, target_h / orig_height)

    # 3. Resize with bilinear interpolation
    new_w = min(target_w, max(1, round(orig_width * scale)))
    new_h = min(target_h, max(1, round(orig_height * scale)))

    resample_mode = getattr(Image.Resampling, "BILINEAR", Image.BILINEAR)
    resized_image = normalized_image.resize((new_w, new_h), resample=resample_mode)

    # 4. Center-pad onto constant canvas with neutral fill
    pad_left = (target_w - new_w) // 2
    pad_top = (target_h - new_h) // 2

    canvas = Image.new("RGB", (target_w, target_h), color=fill)
    canvas.paste(resized_image, (pad_left, pad_top))

    meta: dict[str, Any] = {
        "scale": float(scale),
        "pad_left": int(pad_left),
        "pad_top": int(pad_top),
        "orig_width": int(orig_width),
        "orig_height": int(orig_height),
        "width": int(orig_width),
        "height": int(orig_height),
        "target_width": int(target_w),
        "target_height": int(target_h),
        "new_width": int(new_w),
        "new_height": int(new_h),
    }

    return canvas, meta


def unletterbox_coords(coords: np.ndarray, meta: dict[str, Any]) -> np.ndarray:
    """Invert letterboxed coordinates back into original image pixel space.

    Inverts coordinates by removing padding and scaling by 1 / scale:
        x_orig = (x_pad - pad_left) / scale
        y_orig = (y_pad - pad_top) / scale
    Then clamps coordinates strictly to original image dimensions [0, W_0] and [0, H_0].

    Supports:
        - 1D bounding box: [x1, y1, x2, y2]
        - 2D bounding boxes: [[x1, y1, x2, y2], ...]
        - 1D single point: [x, y]
        - 2D polygon vertices / points: [[x_i, y_i], ...]
        - 3D contour arrays: [[[x_i, y_i], ...]]

    Args:
        coords: Numpy array or sequence of coordinates in letterbox canvas space.
        meta: Letterbox metadata dictionary containing 'scale', 'pad_left',
              'pad_top', and 'orig_width'/'orig_height'.

    Returns:
        Numpy array of coordinates mapped to original image pixel coordinates.
    """
    arr = np.asarray(coords, dtype=np.float32).copy()
    if arr.size == 0:
        return arr

    scale = float(meta.get("scale", 1.0))
    if scale <= 0:
        scale = 1.0

    pad_left = float(meta.get("pad_left", 0.0))
    pad_top = float(meta.get("pad_top", 0.0))

    orig_width = float(meta.get("orig_width", meta.get("width", 0.0)))
    orig_height = float(meta.get("orig_height", meta.get("height", 0.0)))

    if arr.shape == (4,) or (arr.ndim == 2 and arr.shape[1] == 4):
        # Bounding boxes [x1, y1, x2, y2]
        arr[..., 0] = np.clip((arr[..., 0] - pad_left) / scale, 0.0, orig_width)
        arr[..., 1] = np.clip((arr[..., 1] - pad_top) / scale, 0.0, orig_height)
        arr[..., 2] = np.clip((arr[..., 2] - pad_left) / scale, 0.0, orig_width)
        arr[..., 3] = np.clip((arr[..., 3] - pad_top) / scale, 0.0, orig_height)
    elif arr.shape == (2,) or arr.shape[-1] == 2:
        # Single point [x, y] or polygon vertices (..., 2)
        arr[..., 0] = np.clip((arr[..., 0] - pad_left) / scale, 0.0, orig_width)
        arr[..., 1] = np.clip((arr[..., 1] - pad_top) / scale, 0.0, orig_height)
    else:
        raise ValueError(
            f"Unsupported coords shape: {arr.shape}. "
            "Expected 1D/2D bounding boxes (..., 4) or 1D/2D/3D points (..., 2)."
        )

    return arr
