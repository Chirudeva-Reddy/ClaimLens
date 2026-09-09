"""Tests for YOLOv8 segmentation training pipeline and hyperparameter tuning.

Validates device selection, hyperparameter parameterization, CLI argument parsing,
convenience wrappers, and ONNX model export integrity.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import onnx
import pytest
import torch

from claimlens.train import (
    DAMAGES_DATA_YAML,
    DEFAULT_MODELS_DIR,
    MERGED_DAMAGES_DATA_YAML,
    PARTS_DATA_YAML,
    RAW_DAMAGES_DATA_YAML,
    build_parser,
    export_onnx,
    get_optimal_device,
    train_damages,
    train_parts,
    train_task,
)


class TestDeviceSelection:
    """Validates device selection logic across platforms and user overrides."""

    def test_explicit_cpu_override(self) -> None:
        assert get_optimal_device("cpu") == "cpu"

    def test_explicit_cuda_selection(self) -> None:
        assert get_optimal_device("cuda") == "cuda"

    def test_auto_device_detection(self) -> None:
        detected = get_optimal_device(None)
        if torch.backends.mps.is_available():
            assert detected == "mps"
        elif torch.cuda.is_available():
            assert detected == "cuda"
        else:
            assert detected == "cpu"

    def test_mps_unavailable_fallback(self) -> None:
        with patch.object(torch.backends.mps, "is_available", return_value=False):
            fallback = get_optimal_device("mps")
            assert fallback == "cpu"

    def test_mps_available_when_requested(self) -> None:
        with patch.object(torch.backends.mps, "is_available", return_value=True):
            device = get_optimal_device("mps")
            assert device == "mps"


class TestDatasetDefaults:
    """Validates dataset YAML path resolutions for damages and parts."""

    def test_damages_prefers_merged_dataset_if_exists(self) -> None:
        if MERGED_DAMAGES_DATA_YAML.exists():
            assert DAMAGES_DATA_YAML == MERGED_DAMAGES_DATA_YAML
        else:
            assert DAMAGES_DATA_YAML == RAW_DAMAGES_DATA_YAML

    def test_parts_dataset_path(self) -> None:
        assert PARTS_DATA_YAML == Path("data/parts/data.yaml")
        assert PARTS_DATA_YAML.exists()

    def test_missing_data_yaml_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Data config not found"):
            train_task("damages", data_yaml=Path("non_existent_data.yaml"))


class TestHyperparameterParameterization:
    """Validates that training hyperparameters are properly routed to Ultralytics YOLO.train()."""

    @patch("claimlens.train.YOLO")
    @patch("claimlens.train.export_onnx")
    def test_train_task_routes_hyperparameters(
        self,
        mock_export_onnx: MagicMock,
        mock_yolo_class: MagicMock,
    ) -> None:
        mock_model = MagicMock()
        mock_yolo_class.return_value = mock_model

        # Mock val results
        mock_val = MagicMock()
        mock_val.box.map50 = 0.65
        mock_val.box.map = 0.48
        mock_val.box.mp = 0.68
        mock_val.box.mr = 0.62
        mock_val.seg.map50 = 0.64
        mock_val.seg.map = 0.47
        mock_val.seg.mp = 0.70
        mock_val.seg.mr = 0.59
        mock_model.val.return_value = mock_val

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            metrics = train_task(
                task="damages",
                data_yaml=PARTS_DATA_YAML,  # Use existing yaml for test
                epochs=10,
                imgsz=640,
                batch=8,
                device="cpu",
                output_dir=out_dir,
                base_weights="yolov8n-seg.pt",
                optimizer="AdamW",
                lr0=0.001,
                lrf=0.01,
                cos_lr=True,
                close_mosaic=3,
                scale=0.5,
                box=7.5,
                cls=0.5,
                dfl=1.5,
                mosaic=1.0,
                export_onnx_model=False,
            )

            mock_model.train.assert_called_once()
            called_kwargs = mock_model.train.call_args.kwargs

            assert called_kwargs["optimizer"] == "AdamW"
            assert called_kwargs["lr0"] == 0.001
            assert called_kwargs["lrf"] == 0.01
            assert called_kwargs["cos_lr"] is True
            assert called_kwargs["close_mosaic"] == 3
            assert called_kwargs["scale"] == 0.5
            assert called_kwargs["box"] == 7.5
            assert called_kwargs["cls"] == 0.5
            assert called_kwargs["dfl"] == 1.5
            assert called_kwargs["mosaic"] == 1.0
            assert called_kwargs["epochs"] == 10
            assert called_kwargs["batch"] == 8
            assert called_kwargs["device"] == "cpu"

            assert metrics["task"] == "damages"
            assert metrics["epochs"] == 10
            assert metrics["optimizer"] == "AdamW"
            assert metrics["box"]["map50"] == 0.65
            assert metrics["mask"]["map50"] == 0.64

            # Verify metrics file written
            metrics_file = out_dir / "damages_metrics.json"
            assert metrics_file.exists()


class TestCLIParsing:
    """Validates CLI argument parsing and flags."""

    def test_default_cli_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])

        assert args.task == "all"
        assert args.epochs == 12
        assert args.imgsz == 640
        assert args.batch == 16
        assert args.optimizer == "AdamW"
        assert args.lr0 == 0.001
        assert args.lrf == 0.01
        assert args.cos_lr is True
        assert args.close_mosaic == 3
        assert args.scale == 0.5
        assert args.box == 7.5
        assert args.cls == 0.5
        assert args.dfl == 1.5
        assert args.mosaic == 1.0
        assert args.no_export is False

    def test_custom_hyperparameter_cli_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--task",
                "damages",
                "--epochs",
                "20",
                "--batch",
                "32",
                "--optimizer",
                "SGD",
                "--lr0",
                "0.005",
                "--lrf",
                "0.02",
                "--no-cos-lr",
                "--close-mosaic",
                "5",
                "--scale",
                "0.3",
                "--box",
                "8.0",
                "--cls",
                "0.8",
                "--dfl",
                "1.2",
                "--mosaic",
                "0.8",
                "--no-export",
            ]
        )

        assert args.task == "damages"
        assert args.epochs == 20
        assert args.batch == 32
        assert args.optimizer == "SGD"
        assert args.lr0 == 0.005
        assert args.lrf == 0.02
        assert args.cos_lr is False
        assert args.close_mosaic == 5
        assert args.scale == 0.3
        assert args.box == 8.0
        assert args.cls == 0.8
        assert args.dfl == 1.2
        assert args.mosaic == 0.8
        assert args.no_export is True


class TestConvenienceWrappers:
    """Validates train_damages and train_parts wrappers."""

    @patch("claimlens.train.train_task")
    def test_train_damages_wrapper(self, mock_train_task: MagicMock) -> None:
        mock_train_task.return_value = {"task": "damages"}
        res = train_damages(epochs=5, batch=8)
        assert res == {"task": "damages"}
        mock_train_task.assert_called_once_with(
            task="damages",
            data_yaml=None,
            epochs=5,
            imgsz=640,
            batch=8,
            device=None,
            output_dir=DEFAULT_MODELS_DIR,
            base_weights=None,
        )

    @patch("claimlens.train.train_task")
    def test_train_parts_wrapper(self, mock_train_task: MagicMock) -> None:
        mock_train_task.return_value = {"task": "parts"}
        res = train_parts(epochs=8, batch=16)
        assert res == {"task": "parts"}
        mock_train_task.assert_called_once_with(
            task="parts",
            data_yaml=None,
            epochs=8,
            imgsz=640,
            batch=16,
            device=None,
            output_dir=DEFAULT_MODELS_DIR,
            base_weights=None,
        )


class TestExportONNX:
    """Validates export_onnx functionality and graph validation."""

    def test_export_onnx_validates_and_produces_dynamic_model(self) -> None:
        baseline_pt = Path("models/damages_best_baseline.pt")
        assert baseline_pt.exists(), "Baseline weights must exist for export test"

        with tempfile.TemporaryDirectory() as tmpdir:
            out_onnx = Path(tmpdir) / "test_export.onnx"
            result_path = export_onnx(
                model_or_path=baseline_pt,
                output_path=out_onnx,
                dynamic=True,
                imgsz=640,
            )

            assert result_path.exists()
            assert result_path == out_onnx

            # Verify with onnx.checker
            loaded_model = onnx.load(str(result_path))
            onnx.checker.check_model(loaded_model)

            # Check input tensor dimensions
            input_tensor = loaded_model.graph.input[0]
            dims = input_tensor.type.tensor_type.shape.dim
            assert len(dims) == 4
            assert dims[1].dim_value == 3  # RGB
            batch_axis = dims[0].dim_param or dims[0].dim_value
            assert batch_axis in ["batch", 1, 0]
