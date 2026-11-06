"""USB (UVC) capture — how the Canon 5D HDMI feeds actually arrive.

The customer rig has no SDI and no frame grabber: two FHD USB capture
cards expose the cameras as plain UVC devices, readable with
``cv2.VideoCapture(index)``. There is no genlock, so timestamps come
from a monotonic clock at read time and cameras are aligned after the
fact by frame id (see :mod:`stageforge.capture.multi`).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.capture.base import CaptureSource, SourceUnavailableError
from stageforge.capture.crop import Rect, apply_crop, crop_to_aspect, detect_bars
from stageforge.core.log import logger
from stageforge.core.types import Frame

_READ_RETRIES = 3

__all__ = ["UsbCameraSource"]


class UsbCameraSource(CaptureSource):
    """Reads one UVC device, optionally stripping its black bars.

    The pillarbox rectangle is detected on the raw frame and then
    *cached* for ``autocrop_refresh`` frames, because searching every
    frame costs more than the crop itself and a locked-off studio
    camera does not change its geometry mid-show. Detection returning
    ``None`` (dark set, no bars at all) simply means "do not crop".
    """

    def __init__(
        self,
        index: int,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        autocrop: bool = True,
        autocrop_threshold: int = 10,
        autocrop_refresh: int = 300,
        target_aspect: float | None = 16 / 9,
        name: str = "",
        max_frames: int | None = None,
    ) -> None:
        self._index = index
        self._width = width
        self._height = height
        self._fps = fps
        self._autocrop = autocrop
        self._autocrop_threshold = autocrop_threshold
        self._refresh = max(1, autocrop_refresh)
        self._target_aspect = target_aspect
        self._name = name or f"cam{index}"
        self.max_frames = max_frames
        self._cap: cv2.VideoCapture | None = None
        self._rect: Rect | None = None
        self._frame_id = 0
        self._detected_once: bool = False
        self._since_detect: int = 0

    @property
    def crop_rect(self) -> Rect | None:
        """Last detected bar rectangle, for diagnostics and logs."""
        return self._rect

    @property
    def frame_id(self) -> int:
        """Number of frames delivered since ``open``."""
        return self._frame_id

    def open(self) -> None:
        """Open the UVC device and nudge it towards the requested format."""
        capture = cv2.VideoCapture(self._index)
        if not capture.isOpened():
            capture.release()
            raise SourceUnavailableError(
                f"cannot open UVC device index={self._index} name={self._name}"
            )
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._height))
        capture.set(cv2.CAP_PROP_FPS, float(self._fps))
        # MJPG keeps USB 2.0 links at 1080p; the driver may refuse it,
        # which is not fatal — the camera simply stays on its default.
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
        self._cap = capture
        logger.info(f"capture opened: {self._name} index={self._index}")

    def read(self) -> Frame:
        """Grab, autocrop and timestamp a single frame."""
        capture = self._cap
        if capture is None:
            raise SourceUnavailableError(f"{self._name}: read() before open()")

        raw: npt.NDArray[np.uint8] | None = None
        for _attempt in range(_READ_RETRIES):
            ok, grabbed = capture.read()
            if ok and grabbed is not None:
                raw = cast("npt.NDArray[np.uint8]", np.asarray(grabbed))
                break
        if raw is None:
            raise SourceUnavailableError(f"{self._name}: device stopped delivering frames")

        self._frame_id += 1
        image = self._autocropped(raw)
        return Frame(
            timestamp_us=int(time.monotonic() * 1_000_000),
            camera_id=self._name,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            data=image,
            sequence=self._frame_id,
        )

    def frames(self) -> Iterator[Frame]:
        """Yield frames until the source closes, fails or hits ``max_frames``."""
        produced = 0
        while self._cap is not None and (self.max_frames is None or produced < self.max_frames):
            yield self.read()
            produced += 1

    def close(self) -> None:
        """Release the device. Safe to call twice."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info(f"capture closed: {self._name}")

    def _autocropped(self, raw: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Refresh the cached rectangle on schedule, then cut it out."""
        if not self._autocrop:
            return crop_to_aspect(raw, self._target_aspect)

        self._since_detect += 1
        if not self._detected_once or self._since_detect >= self._refresh:
            detected = detect_bars(raw, threshold=self._autocrop_threshold)
            if detected != self._rect:
                logger.info(f"autocrop updated: {self._name} {self._rect} -> {detected}")
            self._rect = detected
            self._detected_once = True
            self._since_detect = 0

        cropped = apply_crop(raw, self._rect) if self._rect is not None else raw
        return crop_to_aspect(cropped, self._target_aspect)
