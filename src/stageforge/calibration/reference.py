"""Reference values for the ColorChecker Classic 24-patch chart.

Numbers are the published sRGB (R, G, B) values of the X-Rite /
ColorChecker Classic chart, in the standard row-major order: the six
colours first (dark skin … orange yellow), then six more (blue …
cyan), then the six neutral patches (white 9.5 … black 2).

No physical chart is needed to *test* anything here:
:func:`generate_colorchecker_image` renders a synthetic one.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

__all__ = ["COLORCHECKER_CLASSIC_SRGB", "GREY_CARD_18_SRGB", "generate_colorchecker_image"]

COLORCHECKER_CLASSIC_SRGB: npt.NDArray[np.float32] = np.array(
    [
        (115, 82, 68),  # dark skin
        (194, 150, 130),  # light skin
        (98, 122, 157),  # blue sky
        (87, 108, 67),  # foliage
        (133, 128, 177),  # blue flower
        (103, 189, 170),  # bluish green
        (214, 126, 44),  # orange
        (80, 91, 166),  # purplish blue
        (193, 90, 99),  # moderate red
        (94, 60, 108),  # purple
        (157, 188, 64),  # yellow green
        (224, 163, 46),  # orange yellow
        (56, 61, 150),  # blue
        (70, 148, 73),  # green
        (175, 54, 60),  # red
        (231, 199, 31),  # yellow
        (187, 86, 149),  # magenta
        (8, 133, 161),  # cyan
        (243, 243, 242),  # white 9.5
        (200, 200, 200),  # neutral 8
        (160, 160, 160),  # neutral 6.5
        (122, 122, 121),  # neutral 5
        (85, 85, 85),  # neutral 3.5
        (52, 52, 52),  # black 2
    ],
    dtype=np.float32,
)

# 18% grey encoded to sRGB: 1.055 * 0.18**(1/2.4) - 0.055 ≈ 0.461 -> *255 ≈ 118.
GREY_CARD_18_SRGB: int = 118


def generate_colorchecker_image(width: int = 600, height: int = 400) -> npt.NDArray[np.uint8]:
    """Render a synthetic chart as a BGR ``uint8`` image (4 rows x 6 cols).

    Black gaps separate the patches so ``find_colorchecker_patches``
    gets one contour per patch. Used by tests and demos; a physical
    chart is only needed for a real one-time studio calibration.
    """
    if width < 60 or height < 40:
        raise ValueError(f"chart image too small: {width}x{height} (min 60x40)")
    image = np.zeros((height, width, 3), dtype=np.uint8)
    gap = max(2, min(width // 60, height // 40))
    cell_w, cell_h = width // 6, height // 4
    for index, rgb in enumerate(COLORCHECKER_CLASSIC_SRGB.astype(np.uint8)):
        row, col = divmod(index, 6)
        x0, y0 = col * cell_w, row * cell_h
        x1 = width if col == 5 else x0 + cell_w
        y1 = height if row == 3 else y0 + cell_h
        image[y0 + gap : y1 - gap, x0 + gap : x1 - gap] = rgb[::-1]  # RGB → BGR
    return image
