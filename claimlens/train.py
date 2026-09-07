"""Model fine-tuning entrypoint for YOLOv8 segmentation.

Supports fine-tuning on vehicle damage detection (CarDD) and vehicle part
segmentation (Humans in the Loop) with Apple Silicon MPS acceleration.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import torch
from ultralytics import YOLO

DEFAULT_MODELS_DIR = Path("models")
DAMAGES_DATA_YAML = Path("data/raw/data.yaml")
PARTS_DATA_YAML = Path("data/parts/data.yaml")


def get_optimal_device(requested_device: str | None = None) -> str:
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


def train_task(
    task: str,
    data_yaml: Path,
    epochs: int = 15,
    imgsz: int = 640,
    batch: int = 16,
    device: str | None = None,
    output_dir: Path = DEFAULT_MODELS_DIR,
    base_weights: str = "yolov8n-seg.pt",
) -> dict[str, Any]:
    if not data_yaml.exists():
        raise FileNotFoundError(f"Data config not found: {data_yaml}")

    device = get_optimal_device(device)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_name = f"{task}_run"

    print(f"=== Starting training for task '{task}' ===")
    print(f"  Data: {data_yaml}")
    print(f"  Epochs: {epochs}, Imgsz: {imgsz}, Batch: {batch}, Device: {device}")

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

    model.train(
        data=str(data_yaml.resolve()),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(output_dir.resolve()),
        name=run_name,
        exist_ok=True,
        verbose=True,
    )

    # Validate best model
    val_results = model.val()

    # Extract metrics summary
    metrics_summary: dict[str, Any] = {
        "task": task,
        "epochs": epochs,
        "imgsz": imgsz,
        "device": device,
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
    dest_pt = output_dir / f"{task}_best.pt"
    if best_pt.exists():
        shutil.copy2(best_pt, dest_pt)
        print(f"Best PyTorch weights saved to {dest_pt}")

    # Export to ONNX
    try:
        exported_onnx = model.export(format="onnx", dynamic=True)
        dest_onnx = output_dir / f"{task}_best.onnx"
        if Path(exported_onnx).exists():
            shutil.copy2(exported_onnx, dest_onnx)
            print(f"ONNX export saved to {dest_onnx}")
    except Exception as e:  # noqa: BLE001
        print(f"Warning: ONNX export failed: {e}")

    return metrics_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        choices=["damages", "parts", "all"],
        default="all",
        help="Task to train ('damages', 'parts', or 'all')",
    )
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", type=str, default=None, help="Device (mps, cpu, cuda)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODELS_DIR)
    args = parser.parse_args()

    tasks_to_run = ["damages", "parts"] if args.task == "all" else [args.task]

    for t in tasks_to_run:
        yaml_path = DAMAGES_DATA_YAML if t == "damages" else PARTS_DATA_YAML
        train_task(
            task=t,
            data_yaml=yaml_path,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
