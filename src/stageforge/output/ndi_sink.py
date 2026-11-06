"""NDI sink — the MVP's route into a production system (or OBS).

``ndi-python`` lives in the optional ``[ndi]`` extra. A missing or
broken NDI runtime must never take a show down, so this sink degrades
to a counted no-op, records the reason, and logs it once instead of
raising mid-transmission. Callers can inspect :attr:`reason` to decide
whether they are actually on air.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import AlphaMask, Frame
from stageforge.output.base import DeliveryStats, OutputSink, SinkWriteError

# Preferred first: these carry real alpha, the last one does not.
_FOURCC_PREFERENCE = (
    ("FOURCC_VIDEO_TYPE_RGBA", cv2.COLOR_BGR2RGBA),
    ("FOURCC_VIDEO_TYPE_BGRA", cv2.COLOR_BGR2BGRA),
    ("FOURCC_VIDEO_TYPE_RGBX", cv2.COLOR_BGR2RGBA),
)

__all__ = ["NDIOutputSink"]


class NDIOutputSink(OutputSink):
    """Sends the composited fill as an RGBA NDI stream."""

    def __init__(self, name: str = "StageForge Preview") -> None:
        self._name = name
        self._ndi: Any = None
        self._sender: Any = None
        self._frame: Any = None
        self._conversion = cv2.COLOR_BGR2RGBA
        self._buffer: npt.NDArray[np.uint8] | None = None
        self._opened = False
        self._degraded = False
        self._reason = ""
        self._sent = 0
        self._dropped = 0

    @property
    def is_streaming(self) -> bool:
        """True only while frames really leave the machine."""
        return self._opened

    @property
    def reason(self) -> str:
        """Empty when streaming, otherwise why the sink degraded."""
        return self._reason

    @property
    def stats(self) -> DeliveryStats:
        """Cumulative delivery counters."""
        return DeliveryStats(sent_frames=self._sent, dropped_frames=self._dropped)

    def open(self) -> None:
        """Create the NDI sender, or degrade and remember why."""
        try:
            import NDIlib
        except ImportError as exc:
            self._disable(f'ndi-python is not installed ({exc}); run: pip install -e ".[ndi]"')
            return

        if not NDIlib.initialize():
            self._disable("NDI runtime failed to initialise on this host")
            return

        settings = NDIlib.SendCreate()
        settings.ndi_name = self._name
        sender = NDIlib.send_create(settings)
        if sender is None:
            NDIlib.destroy()
            self._disable("NDI runtime could not create a sender")
            return

        frame = NDIlib.VideoFrameV2()
        fourcc_name, self._conversion = _pick_fourcc(NDIlib)
        frame.FourCC = getattr(NDIlib, fourcc_name)

        self._ndi, self._sender, self._frame = NDIlib, sender, frame
        self._opened, self._degraded = True, False
        logger.info(f"NDI sink open: {self._name} fourcc={fourcc_name}")

    def send(self, frame: Frame, key: AlphaMask) -> DeliveryStats:
        """Transmit one fill; the key travels inside the RGBA channel."""
        if self._degraded:
            self._dropped += 1
            return self.stats
        if not self._opened or self._frame is None:
            raise SinkWriteError("NDIOutputSink.send() before open()")

        if frame.data is None:
            raise SinkWriteError(f"frame {frame.camera_id} has no pixels to send")

        try:
            self._transmit(frame.data)
        except Exception as exc:  # pragma: no cover - needs live NDI
            self._disable(f"NDI transmit failed: {exc}")
            self._dropped += 1
            return self.stats

        self._sent += 1
        return self.stats

    def close(self) -> None:
        """Destroy the sender and the runtime. Safe to call twice."""
        if self._ndi is not None and self._sender is not None:
            self._ndi.send_destroy(self._sender)
            self._ndi.destroy()
        self._ndi = self._sender = self._frame = None
        self._opened = False
        logger.info(f"NDI sink closed after {self._sent} frames")

    def _transmit(self, fill: npt.NDArray[np.uint8]) -> None:
        """Convert to the negotiated FourCC and hand it to the runtime."""
        converted = cv2.cvtColor(fill, self._conversion)
        self._buffer = np.ascontiguousarray(converted)
        self._frame.data = self._buffer
        self._ndi.send_send_video_v2(self._sender, self._frame)

    def _disable(self, reason: str) -> None:
        """Switch to counted no-op mode and explain once."""
        if not self._degraded:
            logger.warning(f"NDI sink degraded to null: {reason}")
        self._reason = reason
        self._degraded = True
        self._opened = False


def _pick_fourcc(runtime: Any) -> tuple[str, int]:
    """First FourCC the runtime exposes, with its matching conversion."""
    for name, conversion in _FOURCC_PREFERENCE:
        if getattr(runtime, name, None) is not None:
            return name, conversion
    raise AttributeError("NDI runtime exposes no supported FourCC constant")
