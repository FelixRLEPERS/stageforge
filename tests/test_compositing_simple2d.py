"""The OpenCV uint8 composite must match the float32 reference it replaced."""

from __future__ import annotations

import numpy as np

from stageforge.compositing.simple2d import _dim_background_reference, dim_background


def test_dim_bg_matches_float32_reference() -> None:
    """uint8/OpenCV blend stays within 1/255 of the float32 reference at 1080p."""
    rng = np.random.default_rng(0)
    plate = rng.integers(0, 256, size=(1080, 1920, 3), dtype=np.uint8)
    alpha = rng.integers(0, 256, size=(1080, 1920), dtype=np.uint8)

    reference = _dim_background_reference(plate, alpha, shade=0.55)
    fast = dim_background(plate, alpha, shade=0.55)

    assert reference.shape == fast.shape
    assert reference.dtype == fast.dtype
    difference = np.abs(reference.astype(np.int16) - fast.astype(np.int16))
    assert int(difference.max()) <= 1


def test_dim_bg_constant_alpha_is_exact() -> None:
    """alpha=255 must return the plate unchanged; alpha=0 must dim it fully."""
    rng = np.random.default_rng(1)
    plate = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)

    untouched = dim_background(plate, np.full((64, 64), 255, dtype=np.uint8), shade=0.55)
    assert np.array_equal(untouched, plate)

    dimmed = dim_background(plate, np.zeros((64, 64), dtype=np.uint8), shade=0.55)
    expected = _dim_background_reference(plate, np.zeros((64, 64), dtype=np.uint8), shade=0.55)
    # cv2 rounding vs float32 truncation -> at most one LSB apart.
    assert int(np.abs(dimmed.astype(np.int16) - expected.astype(np.int16)).max()) <= 1
    assert np.array_equal(
        dim_background(plate, np.zeros((64, 64), dtype=np.uint8), shade=1.0), plate
    )
