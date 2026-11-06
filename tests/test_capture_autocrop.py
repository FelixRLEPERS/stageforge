"""Bar detection must cut the 5D Mark II pillarbox and never guess wrong."""

from __future__ import annotations

import numpy as np

from stageforge.capture.crop import (
    apply_crop,
    crop_to_aspect,
    detect_bars,
    detect_pillarbox,
)
from stageforge.capture.synthetic import SyntheticCameraSource


def _pillarbox_frame(width: int = 1920, height: int = 1080, content: int = 1620) -> np.ndarray:
    """Black raster with a centred white content box (the 5D Mark II case)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    offset = (width - content) // 2
    frame[:, offset : offset + content] = 255
    return frame


def test_detect_pillarbox_on_synthetic() -> None:
    rect = detect_pillarbox(_pillarbox_frame())
    assert rect is not None
    x1, y1, x2, y2 = rect
    assert abs(x1 - 150) <= 2
    assert abs(x2 - 1770) <= 2
    assert (y1, y2) == (0, 1080)


def test_detect_pillarbox_none_when_no_bars() -> None:
    uniform = np.full((1080, 1920, 3), 120, dtype=np.uint8)
    assert detect_pillarbox(uniform) is None
    assert detect_bars(uniform) is None


def test_detect_pillarbox_rejects_tiny_content() -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[:, 900:1000] = 255
    assert detect_pillarbox(frame) is None


def test_apply_crop_slices_correctly() -> None:
    frame = _pillarbox_frame()
    cropped = apply_crop(frame, (150, 0, 1770, 1080))
    assert cropped.shape == (1080, 1620, 3)
    assert cropped.flags["C_CONTIGUOUS"]


def test_crop_to_aspect_16_9_from_3_2() -> None:
    frame = np.zeros((1080, 1620, 3), dtype=np.uint8)
    cropped = crop_to_aspect(frame, 16 / 9)
    assert cropped.shape == (911, 1620, 3)
    # floor() leaves the result a hair *wider* than 16:9 rather than
    # rounding past the source raster; the error stays under 1 %.
    ratio = cropped.shape[1] / cropped.shape[0]
    assert ratio >= 16 / 9
    assert ratio - 16 / 9 < 0.01


def test_camera_source_caches_crop() -> None:
    source = SyntheticCameraSource(pattern="pillarbox", autocrop_refresh=300)
    source.open()
    try:
        assert source.crop_rect is None
        source.read()
        first = source.crop_rect
        assert first is not None
        source.read()
        assert source.crop_rect == first
    finally:
        source.close()


def test_camera_source_detects_5d_mk2_pattern() -> None:
    source = SyntheticCameraSource(pattern="pillarbox", target_aspect=None)
    source.open()
    try:
        frame = source.read()
        assert frame.width < 1920
        assert (frame.height, frame.width) == (1080, 1620)
    finally:
        source.close()
