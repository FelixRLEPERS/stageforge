"""Bar detection must cut the 5D Mark II pillarbox and never guess wrong."""

from __future__ import annotations

import numpy as np
import pytest

import stageforge.capture.source as source_module
import stageforge.capture.synthetic as synthetic_module
from stageforge.capture.crop import apply_crop, crop_to_aspect, detect_bars, detect_pillarbox
from stageforge.capture.source import UsbCameraSource
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


def _count_detect_calls(monkeypatch: pytest.MonkeyPatch, frames: int, refresh: int) -> int:
    """Read ``frames`` frames from a synthetic source, counting detect_bars."""
    source = SyntheticCameraSource(pattern="plain", autocrop_refresh=refresh, target_aspect=None)
    source.open()
    calls = 0
    original = synthetic_module.detect_bars

    def counting_detect(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(synthetic_module, "detect_bars", counting_detect)
    try:
        for _ in range(frames):
            source.read()
    finally:
        source.close()
    return calls


def test_autocrop_cache_no_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bar-free camera (5D Mark IV) must detect once, not every frame."""
    assert _count_detect_calls(monkeypatch, frames=10, refresh=300) == 1


def test_autocrop_cache_with_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    """With refresh=5, detection runs on frame 1 then every 5th frame."""
    # frame 1 (first) + frames 6, 11 -> 3 detections over 12 frames.
    assert _count_detect_calls(monkeypatch, frames=12, refresh=5) == 3


class _FakeUvc:
    """Stands in for ``cv2.VideoCapture`` on a machine with no capture card."""

    def __init__(self, index: int) -> None:
        self._index = index

    def isOpened(self) -> bool:  # noqa: N802 - mirrors the OpenCV API
        return True

    def set(self, *_args: object, **_kwargs: object) -> bool:
        return True

    def read(self) -> tuple[bool, np.ndarray]:
        return True, np.full((1080, 1920, 3), 120, dtype=np.uint8)

    def release(self) -> None:
        return None


def test_autocrop_cache_usb_source_no_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    """The USB path carries the same cache contract as the synthetic one."""
    calls = 0
    original = source_module.detect_bars

    def counting_detect(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(source_module, "detect_bars", counting_detect)
    monkeypatch.setattr(source_module.cv2, "VideoCapture", _FakeUvc)

    source = UsbCameraSource(index=0, autocrop_refresh=300, target_aspect=None)
    source.open()
    try:
        for _ in range(10):
            source.read()
    finally:
        source.close()
    assert calls == 1


def test_detect_bars_profiles_called_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_bars must compute _profiles once, not four np.mean passes."""
    import stageforge.capture.crop as crop_module

    calls = 0
    original = crop_module._profiles

    def counting_profiles(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(crop_module, "_profiles", counting_profiles)
    detect_bars(_pillarbox_frame())
    assert calls == 1

    calls = 0
    detect_bars(np.full((64, 64, 3), 120, dtype=np.uint8))
    assert calls == 1
