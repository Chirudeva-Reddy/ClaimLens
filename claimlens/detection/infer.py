"""Inference and vehicle damage inspection wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO

from claimlens.detection.association import associate_damages_with_parts
from claimlens.detection.schemas import (
    STRUCTURAL_PART_NAMES,
    DetectedDamage,
    DetectedPart,
    InspectionResult,
)
from claimlens.quality_gate.gate import check_image_quality

DEFAULT_DAMAGES_WEIGHTS = Path("models/damages_best.pt")
DEFAULT_PARTS_WEIGHTS = Path("models/parts_best.pt")


def _get_model(model_or_path: YOLO | Path | str | None, default_path: Path) -> YOLO | None:
    if isinstance(model_or_path, YOLO):
        return model_or_path
    path = Path(model_or_path) if model_or_path else default_path
    if path.exists():
        return YOLO(str(path))
    return None


def extract_parts_from_results(results: Any) -> list[DetectedPart]:
    parts: list[DetectedPart] = []
    if not results or len(results) == 0:
        return parts

    r = results[0]
    boxes = r.boxes
    masks = r.masks
    names = r.names

    if boxes is None or len(boxes) == 0:
        return parts

    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    cls_ids = boxes.cls.cpu().numpy().astype(int)

    for i in range(len(boxes)):
        cid = int(cls_ids[i])
        cname = str(names.get(cid, f"part_{cid}"))
        conf = float(confs[i])
        box = tuple(float(x) for x in xyxy[i])

        polygon_pts: list[tuple[float, float]] | None = None
        if masks is not None and len(masks.xy) > i:
            pts = masks.xy[i]
            if len(pts) >= 3:
                polygon_pts = [(float(x), float(y)) for x, y in pts]

        is_structural = cname.lower() in STRUCTURAL_PART_NAMES
        parts.append(
            DetectedPart(
                part_id=cid,
                name=cname,
                confidence=conf,
                box=box,  # type: ignore[arg-type]
                polygon=polygon_pts,
                is_structural=is_structural,
            )
        )
    return parts


def extract_damages_from_results(results: Any, image_size: tuple[int, int]) -> list[DetectedDamage]:
    damages: list[DetectedDamage] = []
    if not results or len(results) == 0:
        return damages

    r = results[0]
    boxes = r.boxes
    masks = r.masks
    names = r.names

    if boxes is None or len(boxes) == 0:
        return damages

    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    cls_ids = boxes.cls.cpu().numpy().astype(int)
    img_w, img_h = image_size
    img_area = max(1.0, float(img_w * img_h))

    for i in range(len(boxes)):
        cid = int(cls_ids[i])
        cname = str(names.get(cid, f"damage_{cid}"))
        conf = float(confs[i])
        box = tuple(float(x) for x in xyxy[i])

        polygon_pts: list[tuple[float, float]] | None = None
        area_ratio = 0.0

        if masks is not None and len(masks.xy) > i:
            pts = masks.xy[i]
            if len(pts) >= 3:
                polygon_pts = [(float(x), float(y)) for x, y in pts]
                # Approximate polygon area via shoelace formula
                x_coords = np.array([p[0] for p in polygon_pts])
                y_coords = np.array([p[1] for p in polygon_pts])
                poly_area = 0.5 * np.abs(
                    np.dot(x_coords, np.roll(y_coords, 1)) - np.dot(y_coords, np.roll(x_coords, 1))
                )
                area_ratio = float(poly_area / img_area)

        if area_ratio == 0.0:
            bw = max(0.0, box[2] - box[0])
            bh = max(0.0, box[3] - box[1])
            area_ratio = float((bw * bh) / img_area)

        damages.append(
            DetectedDamage(
                damage_id=cid,
                name=cname,
                confidence=conf,
                box=box,  # type: ignore[arg-type]
                polygon=polygon_pts,
                area_ratio=area_ratio,
            )
        )
    return damages


def annotate_inspection(
    image: Image.Image,
    parts: list[DetectedPart],
    damages: list[DetectedDamage],
) -> Image.Image:
    canvas = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Draw parts in subtle blue/cyan
    for part in parts:
        if part.polygon and len(part.polygon) >= 3:
            draw.polygon(part.polygon, outline=(40, 140, 240, 200), width=2)
        else:
            draw.rectangle(part.box, outline=(40, 140, 240, 200), width=2)
        draw.text(
            (part.box[0], max(0, part.box[1] - 12)),
            f"{part.name} ({part.confidence:.2f})",
            fill=(40, 140, 240, 255),
        )

    # Draw damages in vibrant red/orange
    for dmg in damages:
        outline_color = (255, 60, 60, 255)
        if dmg.polygon and len(dmg.polygon) >= 3:
            draw.polygon(dmg.polygon, outline=outline_color, width=3)
        else:
            draw.rectangle(dmg.box, outline=outline_color, width=3)
        draw.text(
            (dmg.box[0], dmg.box[1]),
            f"DAMAGE: {dmg.name} ({dmg.confidence:.2f})",
            fill=outline_color,
        )

    return canvas.convert("RGB")


def inspect_vehicle(
    image_path: Path | str,
    parts_model: YOLO | Path | str | None = None,
    damages_model: YOLO | Path | str | None = None,
    conf_threshold: float = 0.25,
) -> InspectionResult:
    """End-to-end vehicle inspection: quality gate -> detection -> association."""
    path = Path(image_path)
    verdict = check_image_quality(path)
    if not verdict.accepted:
        return InspectionResult(
            accepted_by_quality_gate=False,
            quality_gate_reason=verdict.reason,
        )

    with Image.open(path) as img:
        img_rgb = img.convert("RGB")
        size = img_rgb.size

    p_model = _get_model(parts_model, DEFAULT_PARTS_WEIGHTS)
    d_model = _get_model(damages_model, DEFAULT_DAMAGES_WEIGHTS)

    detected_parts: list[DetectedPart] = []
    detected_damages: list[DetectedDamage] = []

    if p_model is not None:
        p_res = p_model(img_rgb, conf=conf_threshold, verbose=False)
        detected_parts = extract_parts_from_results(p_res)

    if d_model is not None:
        d_res = d_model(img_rgb, conf=conf_threshold, verbose=False)
        detected_damages = extract_damages_from_results(d_res, size)

    associated, unassociated, structural_flag = associate_damages_with_parts(
        detected_damages, detected_parts
    )

    annotated = annotate_inspection(img_rgb, detected_parts, detected_damages)

    return InspectionResult(
        accepted_by_quality_gate=True,
        quality_gate_reason=None,
        associated_damages=associated,
        unassociated_damages=unassociated,
        all_parts=detected_parts,
        structural_flag=structural_flag,
        annotated_image=annotated,
    )
