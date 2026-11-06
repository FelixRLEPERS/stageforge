"""Depth Anything V2 contract — skipped unless the [ml] extra is installed."""

from __future__ import annotations

import numpy as np
import pytest

from stageforge.core.types import Frame
from stageforge.reconstruction.monocular import (
    ML_HINT,
    MonocularDepthProvider,
    normalise_depth,
)


def _has_ml() -> bool:
    """Both torch and transformers importable (find_spec lies if a dep is missing)."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:
        return False
    return True


requires_ml = pytest.mark.skipif(not _has_ml(), reason="requires [ml] extras")


@requires_ml
def test_predict_shape_and_range() -> None:
    provider = MonocularDepthProvider(device="cpu")
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
