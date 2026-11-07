"""Reference values and the synthetic chart image (no physical chart)."""

from __future__ import annotations

import numpy as np
import pytest

from stageforge.calibration.reference import (
    COLORCHECKER_CLASSIC_SRGB,
    GREY_CARD_18_SRGB,
    generate_colorchecker_image,
)


def test_reference_is_24_distinct_srgb_rows() -> None:
    assert COLORCHECKER_CLASSIC_SRGB.shape == (24, 3)
    assert COLORCHECKER_CLASSIC_SRGB.dtype == np.float32
    assert 0.0 <= COLORCHECKER_CLASSIC_SRGB.min() <= COLORCHECKER_CLASSIC_SRGB.max() <= 255.0
    assert np.unique(COLORCHECKER_CLASSIC_SRGB, axis=0).shape == (24, 3)


def test_reference_leading_patches_match_published_values() -> None:
    expected = np.array(
        [
            (115, 82, 68),  # dark skin
            (194, 150, 130),  # light skin
            (98, 122, 157),  # blue sky
            (87, 108, 67),  # foliage
            (133, 128, 177),  # blue flower
        ],
        dtype=np.float32,
    )
    np.testing.assert_array_equal(COLORCHECKER_CLASSIC_SRGB[:5], expected)


def test_grey_card_is_18_percent_srgb() -> None:
    assert GREY_CARD_18_SRGB == 118


def test_generated_image_is_row_major_bgr() -> None:
    image = generate_colorchecker_image(600, 400)
    assert image.shape == (400, 600, 3)
    assert image.dtype == np.uint8
    sampled = [
        image[row * 100 + 50, col * 100 + 50][::-1]  # cell centre, BGR -> RGB
        for row in range(4)
        for col in range(6)
    ]
    np.testing.assert_array_equal(np.array(sampled, dtype=np.float32), COLORCHECKER_CLASSIC_SRGB)
    # exactly the 24 patches plus the black background
    assert np.unique(image.reshape(-1, 3), axis=0).shape == (25, 3)


def test_generated_image_rejects_tiny_sizes() -> None:
    with pytest.raises(ValueError):
        generate_colorchecker_image(20, 20)
