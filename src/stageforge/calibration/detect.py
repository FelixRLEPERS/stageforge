"""Find the ColorChecker 4x6 patch grid in a photo (pure OpenCV, no ML).

Detection is best-effort: when the automatic path finds no grid it
returns ``None`` and the caller falls back to
:func:`sample_grid_in_rect` with hand-picked coordinates (the CLI's
``--rect``). That is the whole point of ADR-0005 — no 125-point
manual grid, one chart, one shot.
"""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

__all__ = ["find_colorchecker_patches", "sample_grid_in_rect"]

_ROWS, _COLS = 4, 6
_PATCHES = _ROWS * _COLS
_Box = tuple[int, int, int, int]


def find_colorchecker_patches(image: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32] | None:
    """Sample the chart's 24 patches as sRGB float32 ``(24, 3)``.

    Canny edges -> quadrilateral contours -> keep the 24 largest
    squares -> sort row-major (top-left to bottom-right) -> average
    the centre of each patch. ``None`` means "no grid found".
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"expected BGR image (H, W, 3), got shape {image.shape}")
    height, width = image.shape[:2]
    edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), dtype=np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = width * height * 0.0005
    max_area = width * height * 0.30  # a whole-chart outline is not a patch
    boxes: list[_Box] = []
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.03 * cv2.arcLength(contour, True), True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if not min_area <= w * h <= max_area or not 0.4 <= w / max(1, h) <= 2.5:
            continue
        boxes.append((x, y, w, h))
    if len(boxes) < _PATCHES:
        return None

    boxes.sort(key=lambda box: box[2] * box[3], reverse=True)
    boxes = boxes[:_PATCHES]
    # rows are y-bands: sort by centre-y, chunk into _ROWS groups of _COLS
    boxes.sort(key=lambda box: box[1] + box[3] / 2)
    ordered: list[_Box] = []
    for start in range(0, _PATCHES, _COLS):
        ordered.extend(sorted(boxes[start : start + _COLS], key=lambda box: box[0]))
    return np.array([_mean_srgb(image, box) for box in ordered], dtype=np.float32)


def sample_grid_in_rect(
    image: npt.NDArray[np.uint8], rect: tuple[int, int, int, int]
) -> npt.NDArray[np.float32]:
    """Sample a hand-picked chart rectangle as a 4x6 grid (CLI fallback).

    ``rect`` is ``(x, y, width, height)`` in pixels; patches come back
    in the same row-major order as ``COLORCHECKER_CLASSIC_SRGB``.
    """
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        raise ValueError(f"rect must be positive, got {rect}")
    cell_w, cell_h = w // _COLS, h // _ROWS
    boxes = [
        (x + col * cell_w, y + row * cell_h, cell_w, cell_h)
        for row in range(_ROWS)
        for col in range(_COLS)
    ]
    return np.array([_mean_srgb(image, box) for box in boxes], dtype=np.float32)


def _mean_srgb(image: npt.NDArray[np.uint8], box: _Box) -> tuple[float, float, float]:
    """Average the inner half of a patch box, returned as (R, G, B)."""
    x, y, w, h = box
    inset = max(1, min(w, h) // 4)
    patch = image[y + inset : y + h - inset, x + inset : x + w - inset]
    if patch.size == 0:
        patch = image[y : y + h, x : x + w]
    if patch.size == 0:
        raise ValueError(f"patch box {box} lies outside the image")
    blue, green, red = (float(value) for value in patch.reshape(-1, 3).mean(axis=0))
    return (red, green, blue)
