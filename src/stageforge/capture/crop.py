"""Black-bar detection and cropping for letterboxed/pillarboxed sources.

A Canon 5D Mark II running Magic Lantern with *Clear Overlays* emits a
1620x1080 (3:2) picture centred inside a 1920x1080 frame, so the left
and right ~150 px are pure black. These helpers find that content box
on the raw frame and cut it away. Every detector is conservative: on a
dark studio set it returns ``None`` and the caller keeps the frame as
is, because a missed crop is harmless while a wrong crop destroys the
picture.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

Rect = tuple[int, int, int, int]

__all__ = [
    "Rect",
    "apply_crop",
    "crop_to_aspect",
    "detect_and_crop",
    "detect_bars",
    "detect_letterbox",
    "detect_pillarbox",
]


def _profiles(
    frame: npt.NDArray[np.uint8],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Mean brightness per column and per row, for BGR or grayscale input."""
    if frame.ndim == 2:
        columns = np.asarray(frame.mean(axis=0), dtype=np.float64)
        rows = np.asarray(frame.mean(axis=1), dtype=np.float64)
    else:
        columns = np.asarray(frame.mean(axis=(0, 2)), dtype=np.float64)
        rows = np.asarray(frame.mean(axis=(1, 2)), dtype=np.float64)
    return columns, rows


def _pillarbox_bounds(
    columns: npt.NDArray[np.float64],
    height: int,
    threshold: float,
    min_content_ratio: float,
) -> Rect | None:
    """Pillarbox rect from a pre-computed column profile."""
    bounds = _content_bounds(columns, threshold, min_content_ratio)
    if bounds is None:
        return None
    x1, x2 = bounds
    return (x1, 0, x2, height)


def _letterbox_bounds(
    rows: npt.NDArray[np.float64],
    width: int,
    threshold: float,
    min_content_ratio: float,
) -> Rect | None:
    """Letterbox rect from a pre-computed row profile."""
    bounds = _content_bounds(rows, threshold, min_content_ratio)
    if bounds is None:
        return None
    y1, y2 = bounds
    return (0, y1, width, y2)


def _content_bounds(
    profile: npt.NDArray[np.float64],
    threshold: float,
    min_content_ratio: float,
) -> tuple[int, int] | None:
    """First/last index of the lit region, or ``None`` when unusable."""
    active = profile > threshold
    if float(active.mean()) < min_content_ratio:
        return None  # too dark to judge — likely a genuinely dark set
    lit = np.flatnonzero(active)
    if lit.size == 0:
        return None
    start, stop = int(lit[0]), int(lit[-1]) + 1
    if start == 0 and stop == profile.size:
        return None  # nothing to crop
    return start, stop


def detect_pillarbox(
    frame: npt.NDArray[np.uint8],
    threshold: int = 10,
    min_content_ratio: float = 0.5,
) -> Rect | None:
    """Content box ``(x1, y1, x2, y2)`` after vertical bars, or ``None``."""
    columns, _ = _profiles(frame)
    return _pillarbox_bounds(columns, frame.shape[0], threshold, min_content_ratio)


def detect_letterbox(
    frame: npt.NDArray[np.uint8],
    threshold: int = 10,
    min_content_ratio: float = 0.5,
) -> Rect | None:
    """Content box after horizontal bars, or ``None``."""
    _, rows = _profiles(frame)
    return _letterbox_bounds(rows, frame.shape[1], threshold, min_content_ratio)


def detect_bars(
    frame: npt.NDArray[np.uint8],
    threshold: int = 10,
    min_content_ratio: float = 0.5,
) -> Rect | None:
    """Intersection of pillarbox and letterbox; ``None`` if nothing found.

    Both profiles are computed once and fed to both detectors, so the
    cost is two ``np.mean`` passes over the frame instead of four.
    """
    columns, rows = _profiles(frame)
    vertical = _pillarbox_bounds(columns, frame.shape[0], threshold, min_content_ratio)
    horizontal = _letterbox_bounds(rows, frame.shape[1], threshold, min_content_ratio)

    if vertical is None and horizontal is None:
        return None
    if vertical is None:
        return horizontal
    if horizontal is None:
        return vertical
    rect = (
        max(vertical[0], horizontal[0]),
        max(vertical[1], horizontal[1]),
        min(vertical[2], horizontal[2]),
        min(vertical[3], horizontal[3]),
    )
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        return None
    return rect


def apply_crop(frame: npt.NDArray[np.uint8], rect: Rect) -> npt.NDArray[np.uint8]:
    """Cut ``rect`` out of ``frame`` and return a C-contiguous copy."""
    x1, y1, x2, y2 = rect
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return frame
    return np.ascontiguousarray(frame[y1:y2, x1:x2])


def crop_to_aspect(
    frame: npt.NDArray[np.uint8],
    target_aspect: float | None = 16 / 9,
) -> npt.NDArray[np.uint8]:
    """Centre-crop towards ``target_aspect`` (width / height)."""
    if not target_aspect or target_aspect <= 0:
        return frame
    height, width = frame.shape[:2]
    current = width / height
    if abs(current - target_aspect) < 1e-6:
        return frame
    # floor() for the outward crop: rounding up could overshoot the raster
    # by one pixel when the aspect is only a hair off the target.
    if current > target_aspect:
        new_width = math.floor(height * target_aspect)
        offset = max(0, (width - new_width) // 2)
        return np.ascontiguousarray(frame[:, offset : offset + new_width])
    new_height = math.floor(width / target_aspect)
    offset = max(0, (height - new_height) // 2)
    return np.ascontiguousarray(frame[offset : offset + new_height, :])


def detect_and_crop(
    frame: npt.NDArray[np.uint8],
    threshold: int = 10,
    target_aspect: float | None = 16 / 9,
) -> tuple[npt.NDArray[np.uint8], Rect | None]:
    """Detect bars, cut them, then normalise the aspect ratio."""
    rect = detect_bars(frame, threshold=threshold)
    cropped = apply_crop(frame, rect) if rect is not None else frame
    return crop_to_aspect(cropped, target_aspect), rect
