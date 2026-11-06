"""Relative depth must map to a correct, stable foreground matte."""

from __future__ import annotations

import numpy as np
import pytest

from stageforge.core.types import Frame, RelativeDepthFrame
from stageforge.segmentation.base import SegmentationError
from stageforge.segmentation.depth_alpha import DepthAlphaSegmenter
from stageforge.segmentation.metric import depth_to_alpha


def _frame(width: int = 8, height: int = 8) -> Frame:
    return Frame(
        timestamp_us=1,
        camera_id="5D-IV",
        width=width,
        height=height,
        data=np.full((height, width, 3), 100, dtype=np.uint8),
    )


def _depth(frame: Frame, values: np.ndarray) -> RelativeDepthFrame:
    return RelativeDepthFrame(
        camera_id=frame.camera_id,
        timestamp_us=frame.timestamp_us,
        data=np.asarray(values, dtype=np.float32),
    )


def test_foreground_is_255() -> None:
    frame = _frame()
    depth = np.zeros((8, 8), dtype=np.float32)  # everything near
    mask = DepthAlphaSegmenter(low_pct=0.0, high_pct=100.0, morphology_kernel=0).segment(
        frame, _depth(frame, depth)
    )
    assert int(mask.data.max()) == 255
    assert bool(mask.data.all())
    assert mask.source == "depth"


def test_background_is_0() -> None:
    frame = _frame()
    # Mixed scene: a near subject and a far background.
    depth = np.ones((8, 8), dtype=np.float32)
    depth[:4] = 0.0
    mask = DepthAlphaSegmenter(low_pct=5.0, high_pct=95.0, morphology_kernel=0).segment(
        frame, _depth(frame, depth)
    )
    assert int(mask.data[7, 0]) == 0  # far → clear background
    assert int(mask.data[0, 0]) == 255  # near → opaque foreground


def test_percentiles_clip() -> None:
    # Varying background with two extreme outliers.
    rng = np.random.default_rng(0)
    depth = np.asarray(rng.uniform(0.4, 0.6, size=(100, 100)), dtype=np.float32)
    depth[0, 0] = 0.0  # outlier below the 5th percentile
    depth[99, 99] = 1.0  # outlier above the 95th percentile

    segmenter = DepthAlphaSegmenter(low_pct=5.0, high_pct=95.0, morphology_kernel=0, invert=False)
    alpha = segmenter.relative_to_alpha(depth)
    # The outliers are clipped: min → 0, max → 255, mid → mid.
    assert int(alpha[0, 0]) == 0
    assert int(alpha[99, 99]) == 255
    assert 100 <= int(alpha[50, 50]) <= 155

    # With a constant buffer there is no stretch at all, so everything
    # collapses to the clip minimum — no NaNs, no wrap-around.
    flat_segmenter = DepthAlphaSegmenter(
        low_pct=5.0, high_pct=95.0, morphology_kernel=0, invert=False
    )
    flat = flat_segmenter.relative_to_alpha(np.full((8, 8), 0.5, dtype=np.float32))
    assert int(flat.max()) == 0
    assert int(flat.min()) == 0


def test_morphology_keeps_shape() -> None:
    segmenter = DepthAlphaSegmenter(morphology_kernel=3)
    depth = np.ones((64, 64), dtype=np.float32)
    depth[30:34, 30:34] = 0.0
    alpha = segmenter.relative_to_alpha(depth)
    assert alpha.shape == (64, 64)
    assert alpha.dtype == np.uint8
    assert int(alpha[31, 31]) == 255


def test_segment_without_depth_raises() -> None:
    with pytest.raises(SegmentationError, match="needs a depth buffer"):
        DepthAlphaSegmenter().segment(_frame(), None)


def test_metric_path_stays_available_for_the_pilot() -> None:
    depth_m = np.array([[0.5, 2.5, 9.0]], dtype=np.float32)
    alpha = depth_to_alpha(depth_m, near_m=1.0, far_m=4.0)
    assert alpha[0, 0] == 255  # closer than the near plane
    assert alpha[0, 2] == 0  # beyond the far plane
    assert 0 < int(alpha[0, 1]) < 255  # inside the ramp


def test_percentile_scale_matches_full() -> None:
    """Downscaled percentile window must stay within 2 uint8 of full."""
    rng = np.random.default_rng(0)
    depth = np.asarray(rng.uniform(0.0, 1.0, size=(512, 512)), dtype=np.float32)

    full = DepthAlphaSegmenter(
        low_pct=5.0, high_pct=95.0, morphology_kernel=0, percentile_scale=1.0
    )
    sampled = DepthAlphaSegmenter(
        low_pct=5.0, high_pct=95.0, morphology_kernel=0, percentile_scale=0.25
    )
    alpha_full = full.relative_to_alpha(depth)
    alpha_sampled = sampled.relative_to_alpha(depth)
    assert alpha_full.shape == alpha_sampled.shape
    assert int(np.abs(alpha_full.astype(np.int16) - alpha_sampled.astype(np.int16)).max()) <= 2


def test_percentile_scale_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="percentile_scale"):
        DepthAlphaSegmenter(percentile_scale=0.0)
    with pytest.raises(ValueError, match="percentile_scale"):
        DepthAlphaSegmenter(percentile_scale=1.5)
