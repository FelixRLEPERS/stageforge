"""Chart detection and the manual rect fallback, on synthetic input."""

from __future__ import annotations

import numpy as np
import pytest

from stageforge.calibration.detect import find_colorchecker_patches, sample_grid_in_rect
from stageforge.calibration.reference import COLORCHECKER_CLASSIC_SRGB, generate_colorchecker_image


def test_finds_grid_in_synthetic_chart() -> None:
    image = generate_colorchecker_image(600, 400)
    found = find_colorchecker_patches(image)
    assert found is not None
    assert found.shape == (24, 3)
    assert found.dtype == np.float32
    np.testing.assert_allclose(found, COLORCHECKER_CLASSIC_SRGB, atol=1.0)


def test_blank_frame_yields_none() -> None:
    assert find_colorchecker_patches(np.zeros((64, 64, 3), dtype=np.uint8)) is None


def test_non_bgr_frame_raises() -> None:
    with pytest.raises(ValueError):
        find_colorchecker_patches(np.zeros((64, 64), dtype=np.uint8))


def test_rect_fallback_matches_reference() -> None:
    image = generate_colorchecker_image(600, 400)
    patches = sample_grid_in_rect(image, (0, 0, 600, 400))
    np.testing.assert_allclose(patches, COLORCHECKER_CLASSIC_SRGB, atol=1.0)


def test_rect_rejects_bad_boxes() -> None:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        sample_grid_in_rect(image, (10, 10, 0, 20))  # not positive
    with pytest.raises(ValueError):
        sample_grid_in_rect(image, (100, 100, 32, 16))  # lies outside
