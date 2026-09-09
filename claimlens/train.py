"""Model fine-tuning entrypoint for YOLOv8 segmentation.

Supports fine-tuning on vehicle damage detection (merged CarDD + Kaggle) and
vehicle part segmentation (Humans in the Loop) with Apple Silicon MPS acceleration,
hyperparameter optimization (AdamW, Cosine LR, Mosaic tuning, scale jitter),
and verified ONNX model export with dynamic batching.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import onnx
import torch
from ultralytics import YOLO

DEFAULT_MODELS_DIR = Path("models")
MERGED_DAMAGES_DATA_YAML = Path("data/merged/data.yaml")
RAW_DAMAGES_DATA_YAML = Path("data/raw/data.yaml")
DAMAGES_DATA_YAML = (
    MERGED_DAMAGES_DATA_YAML if MERGED_DAMAGES_DATA_YAML.exists() else RAW_DAMAGES_DATA_YAML
)
PARTS_DATA_YAML = Path("data/parts/data.yaml")


def get_optimal_device(requested_device: str | None = None) -> str:
    """Selects the optimal execution device, prioritizing Apple Silicon MPS."""
    if requested_device:
        if requested_device == "mps" and not torch.backends.mps.is_available():
            print("MPS requested but not available; falling back to CPU")
            return "cpu"
        return requested_device
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def export_onnx(
    model_or_path: YOLO | Path | str,
    output_path: Path | str | None = None,
    dynamic: bool = True,
    imgsz: int = 640,
) -> Path:
    """Exports a YOLO model to ONNX with dynamic batching and validates via onnx.checker."""
    if isinstance(model_or_path, YOLO):
        model = model_or_path
    else:
        model = YOLO(str(model_or_path))

    exported = model.export(format="onnx", dynamic=dynamic, imgsz=imgsz)
    exported_path = Path(exported)

    if output_path is not None:
        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if exported_path.resolve() != target_path.resolve():
            shutil.copy2(exported_path, target_path)
            dest = target_path
        else:
            dest = exported_path
    else:
        dest = exported_path

    # Verify ONNX model integrity with onnx.checker
    onnx_model = onnx.load(str(dest))
    onnx.checker.check_model(onnx_model)
    print(f"Verified ONNX model export: {dest}")
    return dest


def train_task(
    task: str,
    data_yaml: Path | str | None = None,
    epochs: int = 12,
    imgsz: int = 640,
    batch: int = 16,
    device: str | None = None,
    output_dir: Path | str = DEFAULT_MODELS_DIR,
    base_weights: str | Path | None = None,
    optimizer: str = "AdamW",
    lr0: float = 0.001,
    lrf: float = 0.01,
    cos_lr: bool = True,
    close_mosaic: int = 3,
    scale: float = 0.5,
    box: float = 7.5,
    cls: float = 0.5,
    dfl: float = 1.5,
    mosaic: float = 1.0,
    export_onnx_model: bool = True,
    **extra_train_kwargs: Any,
) -> dict[str, Any]:
    """Fine-tunes a YOLOv8-seg model with hyperparameter tuning on the target dataset."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if data_yaml is None:
        if task == "damages":
            data_yaml = (
                MERGED_DAMAGES_DATA_YAML
                if MERGED_DAMAGES_DATA_YAML.exists()
                else RAW_DAMAGES_DATA_YAML
            )
        else:
            data_yaml = PARTS_DATA_YAML
    data_yaml = Path(data_yaml)

    if not data_yaml.exists():
        raise FileNotFoundError(f"Data config not found: {data_yaml}")

    if base_weights is None:
        if task == "damages":
            baseline_weights = output_dir / "damages_best_baseline.pt"
            base_weights = str(baseline_weights) if baseline_weights.exists() else "yolov8n-seg.pt"
        else:
            base_weights = "yolov8n-seg.pt"
    base_weights = str(base_weights)

    device = get_optimal_device(device)
    run_name = f"{task}_run"

    print(f"=== Starting training for task '{task}' ===")
    print(f"  Data: {data_yaml}")
    print(f"  Base weights: {base_weights}")
    print(f"  Epochs: {epochs}, Imgsz: {imgsz}, Batch: {batch}, Device: {device}")
    print(f"  Optimizer: {optimizer}, lr0: {lr0}, lrf: {lrf}, cos_lr: {cos_lr}")
    print(f"  Close mosaic: {close_mosaic}, Scale: {scale}, Mosaic: {mosaic}")
    print(f"  Loss weights: box={box}, cls={cls}, dfl={dfl}")

    model = YOLO(base_weights)

    def on_fit_epoch_end(trainer: Any) -> None:
        try:
            epoch = trainer.epoch + 1
            total = trainer.epochs
            pct = (epoch / total) * 100
            bar_len = 20
            filled = int(bar_len * (epoch / total))
            bar = "█" * filled + "─" * (bar_len - filled)

            loss_val = 0.0
            if hasattr(trainer, "tloss") and trainer.tloss is not None:
                tloss = trainer.tloss
                if isinstance(tloss, dict):
                    vals = [
                        float(v)
                        for v in tloss.values()
                        if isinstance(v, (int, float, torch.Tensor))
                    ]
                    loss_val = sum(vals) / max(1, len(vals))
                elif isinstance(tloss, (list, tuple)):
                    vals = [float(v) for v in tloss if isinstance(v, (int, float, torch.Tensor))]
                    loss_val = sum(vals) / max(1, len(vals))
                elif hasattr(tloss, "item"):
                    loss_val = float(tloss.item())
                elif isinstance(tloss, (int, float)):
                    loss_val = float(tloss)

            b_map = (
                float(trainer.metrics.get("metrics/mAP50(B)", 0.0))
                if hasattr(trainer, "metrics")
                else 0.0
            )
            m_map = (
                float(trainer.metrics.get("metrics/mAP50(M)", 0.0))
                if hasattr(trainer, "metrics")
                else 0.0
            )

            print(
                f"\n>>> [TRAIN PROGRESS] Epoch {epoch:2d}/{total:2d} |{bar}| {pct:5.1f}% "
                f"| Loss: {loss_val:.4f} | Box mAP50: {b_map:.3f} | Mask mAP50: {m_map:.3f}",
                flush=True,
            )
        except Exception:  # noqa: BLE001, S110
            pass

    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

    train_kwargs: dict[str, Any] = {
        "data": str(data_yaml.resolve()),
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "project": str(output_dir.resolve()),
        "name": run_name,
        "exist_ok": True,
        "verbose": True,
        "optimizer": optimizer,
        "lr0": lr0,
        "lrf": lrf,
        "cos_lr": cos_lr,
        "close_mosaic": close_mosaic,
        "scale": scale,
        "box": box,
        "cls": cls,
        "dfl": dfl,
        "mosaic": mosaic,
    }
    train_kwargs.update(extra_train_kwargs)

    model.train(**train_kwargs)

    # Validate best model on the dataset validation split
    val_results = model.val(
        data=str(data_yaml.resolve()),
        split="val",
        batch=batch,
        imgsz=imgsz,
        device=device,
    )

    # Extract metrics summary
    metrics_summary: dict[str, Any] = {
        "task": task,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "optimizer": optimizer,
        "lr0": lr0,
        "lrf": lrf,
        "cos_lr": cos_lr,
        "close_mosaic": close_mosaic,
        "scale": scale,
        "box_weight": box,
        "cls_weight": cls,
        "dfl_weight": dfl,
        "box": {
            "map50": float(val_results.box.map50),
            "map50_95": float(val_results.box.map),
            "precision": float(val_results.box.mp),
            "recall": float(val_results.box.mr),
        },
        "mask": {
            "map50": float(val_results.seg.map50),
            "map50_95": float(val_results.seg.map),
            "precision": float(val_results.seg.mp),
            "recall": float(val_results.seg.mr),
        },
    }

    # Save metrics JSON
    metrics_path = output_dir / f"{task}_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)
    print(f"Metrics written to {metrics_path}")

    # Copy best weights
    best_pt = output_dir / run_name / "weights" / "best.pt"
    if not best_pt.exists():
        best_pt = output_dir / run_name / "weights" / "last.pt"
    dest_pt = output_dir / f"{task}_best.pt"
    if best_pt.exists():
        shutil.copy2(best_pt, dest_pt)
        print(f"Best PyTorch weights saved to {dest_pt}")

    # Export to ONNX with dynamic batching and validation
    if export_onnx_model and dest_pt.exists():
        dest_onnx = output_dir / f"{task}_best.onnx"
        try:
            export_onnx(dest_pt, output_path=dest_onnx, dynamic=True, imgsz=imgsz)
        except Exception as e:  # noqa: BLE001
            print(f"Warning: ONNX export failed: {e}")

    return metrics_summary


def train_damages(
    data_yaml: Path | str | None = None,
    epochs: int = 12,
    imgsz: int = 640,
    batch: int = 16,
    device: str | None = None,
    output_dir: Path | str = DEFAULT_MODELS_DIR,
    base_weights: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience wrapper to train damage segmentation model."""
    return train_task(
        task="damages",
        data_yaml=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        output_dir=output_dir,
        base_weights=base_weights,
        **kwargs,
    )


def train_parts(
    data_yaml: Path | str | None = None,
    epochs: int = 15,
    imgsz: int = 640,
    batch: int = 16,
    device: str | None = None,
    output_dir: Path | str = DEFAULT_MODELS_DIR,
    base_weights: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience wrapper to train parts segmentation model."""
    return train_task(
        task="parts",
        data_yaml=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        output_dir=output_dir,
        base_weights=base_weights,
        **kwargs,
    )


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser with comprehensive hyperparameter flags."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        choices=["damages", "parts", "all"],
        default="all",
        help="Task to train ('damages', 'parts', or 'all')",
    )
    parser.add_argument(
        "--data-yaml",
        type=Path,
        default=None,
        help="Path to data.yaml dataset config",
    )
    parser.add_argument("--epochs", type=int, default=12, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", type=str, default=None, help="Device ('mps', 'cuda', 'cpu')")
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_MODELS_DIR, help="Output directory"
    )
    parser.add_argument(
        "--base-weights", type=str, default=None, help="Base weights checkpoint path"
    )
    parser.add_argument(
        "--optimizer", type=str, default="AdamW", help="Optimizer ('AdamW', 'SGD', 'auto')"
    )
    parser.add_argument("--lr0", type=float, default=0.001, help="Initial learning rate")
    parser.add_argument("--lrf", type=float, default=0.01, help="Final learning rate fraction")
    parser.add_argument(
        "--cos-lr",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use cosine learning rate scheduler",
    )
    parser.add_argument(
        "--close-mosaic", type=int, default=3, help="Epochs before end to disable Mosaic"
    )
    parser.add_argument(
        "--scale", type=float, default=0.5, help="Multiscale image scale jitter gain"
    )
    parser.add_argument("--box", type=float, default=7.5, help="Bounding box loss gain")
    parser.add_argument("--cls", type=float, default=0.5, help="Classification loss gain")
    parser.add_argument("--dfl", type=float, default=1.5, help="Distribution Focal Loss gain")
    parser.add_argument("--mosaic", type=float, default=1.0, help="Mosaic augmentation probability")
    parser.add_argument(
        "--no-export", action="store_true", help="Disable automatic ONNX model export"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    tasks_to_run = ["damages", "parts"] if args.task == "all" else [args.task]

    for t in tasks_to_run:
        train_task(
            task=t,
            data_yaml=args.data_yaml,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            output_dir=args.output_dir,
            base_weights=args.base_weights,
            optimizer=args.optimizer,
            lr0=args.lr0,
            lrf=args.lrf,
            cos_lr=args.cos_lr,
            close_mosaic=args.close_mosaic,
            scale=args.scale,
            box=args.box,
            cls=args.cls,
            dfl=args.dfl,
            mosaic=args.mosaic,
            export_onnx_model=not args.no_export,
        )


if __name__ == "__main__":
    main()
