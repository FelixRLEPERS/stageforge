"""Depth Anything V2 contract — skipped unless the [ml] extra is installed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stageforge.core.types import Frame
from stageforge.reconstruction.monocular import (
    DEFAULT_ONNX_PATH,
    ML_HINT,
    MonocularDepthProvider,
    normalise_depth,
)
from stageforge.reconstruction.onnx_support import ONNX_MISSING


def _has_ml() -> bool:
    """Both torch and transformers importable (find_spec lies if a dep is missing)."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:
        return False
    return True


def _has_onnx() -> bool:
    """onnxruntime importable, an exported model present, and the processor available."""
    if not _has_ml() or not Path(DEFAULT_ONNX_PATH).is_file():
        return False
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return False
    return True


requires_ml = pytest.mark.skipif(not _has_ml(), reason="requires [ml] extras")
requires_onnx = pytest.mark.skipif(not _has_onnx(), reason="requires [ml,onnx-gpu] and export")


@requires_ml
def test_predict_shape_and_range() -> None:
    provider = MonocularDepthProvider(device="cpu", precision="fp32")
    provider.calibrate()
    frame = Frame(
        timestamp_us=1,
        camera_id="5D-IV",
        width=256,
        height=256,
        data=np.random.default_rng(0).integers(0, 255, (256, 256, 3), dtype=np.uint8),
    )
    depth = provider.predict(frame)
    assert depth.data.shape == (256, 256)
    assert depth.data.dtype == np.float32
    assert float(depth.data.min()) >= 0.0
    assert float(depth.data.max()) <= 1.0
    assert depth.camera_id == frame.camera_id
    assert depth.timestamp_us == frame.timestamp_us


def test_missing_extras_raise_actionable_hint() -> None:
    if _has_ml():
        pytest.skip("[ml] extras are installed here")
    with pytest.raises(RuntimeError, match=r"pip install -e \.\[ml\]"):
        MonocularDepthProvider().calibrate()
    assert "[ml]" in ML_HINT


def test_normalise_depth_polarity_and_flat_input() -> None:
    raw = np.array([[1.0, 3.0], [2.0, 5.0]], dtype=np.float32)
    near_high = normalise_depth(raw, near_is_high=True)
    # 5.0 is the largest model value = nearest → flips to 0;
    # 1.0 is the smallest = farthest → flips to 1.
    assert float(near_high[1, 1]) == 0.0
    assert float(near_high[0, 0]) == 1.0
    assert float(normalise_depth(raw, near_is_high=False).min()) == 0.0

    flat = normalise_depth(np.full((2, 2), 7.0, dtype=np.float32))
    assert float(np.abs(flat).max()) == 0.0  # no NaNs from a constant map


def test_provider_starts_unloaded() -> None:
    """The model is loaded lazily, so importing the package is cheap."""
    provider = MonocularDepthProvider(model_id="some/other-checkpoint")
    assert provider.is_ready is False
    assert provider.model_id == "some/other-checkpoint"
    assert provider.runtime_device == "cpu"
    assert provider.precision == "fp16"  # fastest available ships as default


def test_unknown_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="backend"):
        MonocularDepthProvider(backend="tensorrt")


def test_unknown_precision_is_rejected() -> None:
    with pytest.raises(ValueError, match="precision"):
        MonocularDepthProvider(precision="bf16")


@requires_ml
def test_fp16_requires_cuda() -> None:
    """fp16 without a CUDA device must say so instead of failing in half()."""
    provider = MonocularDepthProvider(device="cpu", precision="fp16")
    with pytest.raises(RuntimeError, match="fp16 requires CUDA"):
        provider.calibrate()


def test_onnx_missing_model_points_at_export_script() -> None:
    """A missing export must say how to produce it, not crash with FileNotFoundError."""
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        pytest.skip("requires onnxruntime ([onnx-gpu] extras)")
    if not _has_ml():
        pytest.skip("requires [ml] extras for the image processor")
    with pytest.raises(RuntimeError) as excinfo:
        MonocularDepthProvider(backend="onnx", onnx_path="models/does-not-exist.onnx").calibrate()
    assert str(excinfo.value) == ONNX_MISSING


@requires_onnx
def test_onnx_output_shape() -> None:
    """518x294 in (16:9, divisible by 14) must come back (294, 518) float32."""
    provider = MonocularDepthProvider(backend="onnx")
    provider.calibrate()
    assert provider.is_ready is True
    frame = Frame(
        timestamp_us=2,
        camera_id="5D-IV",
        width=518,
        height=294,
        data=np.random.default_rng(1).integers(0, 255, (294, 518, 3), dtype=np.uint8),
    )
    depth = provider.depth_for(frame)
    assert depth.data.shape == (294, 518)
    assert depth.data.dtype == np.float32
    assert float(depth.data.min()) >= 0.0
    assert float(depth.data.max()) <= 1.0


@requires_onnx
def test_onnx_backend_matches_transformers() -> None:
    """Both backends on one processor-grid frame must agree within 5 %."""
    rng = np.random.default_rng(2)
    frame = Frame(
        timestamp_us=3,
        camera_id="5D-IV",
        width=924,
        height=518,
        data=rng.integers(0, 255, (518, 924, 3), dtype=np.uint8),
    )
    onnx_depth = MonocularDepthProvider(backend="onnx").depth_for(frame).data
    hf_depth = (
        MonocularDepthProvider(backend="transformers", device="cpu", precision="fp32")
        .depth_for(frame)
        .data
    )
    assert onnx_depth.shape == hf_depth.shape
    # Both are min-max normalised to [0, 1], so 5 % of the range is the bar.
    difference = float(np.abs(onnx_depth - hf_depth).max())
    assert difference <= 0.05, f"backends diverged by {difference:.4f}"
