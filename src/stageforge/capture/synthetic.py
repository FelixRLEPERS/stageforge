"""Hardware-free capture: the same contract, generated pixels.

Two jobs: it keeps ``--dry-run`` (and therefore CI) working on machines
with no camera attached, and it reproduces the exact 5D Mark II
geometry — 1620x1080 of content centred in a 1920x1080 raster — so the
autocrop logic can be tested deterministically instead of on air.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.capture.base import CaptureSource, SourceUnavailableError
from stageforge.capture.crop import Rect, apply_crop, crop_to_aspect, detect_bars
from stageforge.core.log import logger
from stageforge.core.types import Frame

PATTERNS = ("plain", "bars", "pillarbox")

__all__ = ["PATTERNS", "SyntheticCameraSource"]


class SyntheticCameraSource(CaptureSource):
    """Generates frames locally instead of reading a UVC device."""

    def __init__(
        self,
        index: int = 0,
        width: int = 1920,
        height: int = 1080,
        pattern: str = "pillarbox",
        autocrop: bool = True,
        autocrop_threshold: int = 10,
        autocrop_refresh: int = 300,
        target_aspect: float | None = 16 / 9,
        name: str = "",
        max_frames: int | None = None,
    ) -> None:
        if pattern not in PATTERNS:
            raise ValueError(f"unknown pattern {pattern!r}, expected one of {PATTERNS}")
        self._index = index
        self._width = width
        self._height = height
        self._pattern = pattern
        self._autocrop = autocrop
        self._threshold = autocrop_threshold
        self._refresh = max(1, autocrop_refresh)
        self._target_aspect = target_aspect
        self._name = name or f"synthetic{index}"
        self.max_frames = max_frames
        self._rect: Rect | None = None
        self._frame_id = 0
        self._opened = False

    @property
    def crop_rect(self) -> Rect | None:
        """Last detected bar rectangle, mirroring :class:`UsbCameraSource`."""
        return self._rect

    @property
    def frame_id(self) -> int:
        """Number of frames delivered since ``open``."""
        return self._frame_id

    def open(self) -> None:
        """Mark the source as ready; nothing to allocate."""
        self._opened = True
        logger.info(f"capture opened: {self._name} pattern={self._pattern} (synthetic)")

    def read(self) -> Frame:
        """Produce the next synthetic frame, applying autocrop if enabled."""
        if not self._opened:
            raise SourceUnavailableError(f"{self._name}: read() before open()")

        self._frame_id += 1
        raw = self._render()
        if self._autocrop:
            due = self._rect is None or self._frame_id % self._refresh == 0
            if due:
                self._rect = detect_bars(raw, threshold=self._threshold)
            image = apply_crop(raw, self._rect) if self._rect is not None else raw
            image = crop_to_aspect(image, self._target_aspect)
        else:
            image = raw

        return Frame(
            timestamp_us=int(time.monotonic() * 1_000_000),
            camera_id=self._name,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            data=image,
            sequence=self._frame_id,
        )

    def frames(self) -> Iterator[Frame]:
        """Yield frames up to ``max_frames`` (None = unbounded)."""
        produced = 0
        while self._opened and (self.max_frames is None or produced < self.max_frames):
            yield self.read()
            produced += 1

    def close(self) -> None:
        """Release the (non-existent) device. Safe to call twice."""
        self._opened = False

    def _render(self) -> npt.NDArray[np.uint8]:
        """Rasterise the configured pattern at full sensor size."""
        if self._pattern == "pillarbox":
            return self._render_pillarbox()
        if self._pattern == "bars":
            return self._render_bars()
        return np.full((self._height, self._width, 3), 110, dtype=np.uint8)

    def _render_pillarbox(self) -> npt.NDArray[np.uint8]:
        """3:2 content centred in the 16:9 raster — the 5D Mark II case."""
        content_height = self._height
        content_width = round(content_height * 3 / 2)
        content_width = min(content_width, self._width)
        offset = max(0, (self._width - content_width) // 2)

        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        frame[:, offset : offset + content_width] = self._subject(content_width, content_height)
        return frame

    def _render_bars(self) -> npt.NDArray[np.uint8]:
        """Eight lit colour bars: no black, so no crop is detected."""
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        stripe = max(1, self._width // 8)
        colours = [
            (180, 180, 180),
            (40, 40, 220),
            (40, 220, 40),
            (220, 40, 40),
            (40, 220, 220),
            (220, 40, 220),
            (220, 220, 40),
            (160, 160, 160),
        ]
        for index, colour in enumerate(colours):
            frame[:, index * stripe : (index + 1) * stripe] = colour
        return frame

    def _subject(self, width: int, height: int) -> npt.NDArray[np.uint8]:
        """A backdrop plus a centred 'presenter' shape, all above threshold."""
        scene = np.full((height, width, 3), 70, dtype=np.uint8)
        cv2.ellipse(
            scene,
            (width // 2, int(height * 0.62)),
            (max(1, width // 6), max(1, height // 3)),
            0,
            0,
            360,
            (170, 165, 160),
            -1,
        )
        cv2.circle(
            scene, (width // 2, int(height * 0.26)), max(1, width // 14), (205, 200, 195), -1
        )
        return scene
