"""Filesystem sink: Fill and Key dumped as numbered PNG pairs.

The cheapest possible way to *look* at what the pipeline produced —
open the folder, flip through frames, check the key. It is also the
sink the synthetic end-to-end test uses, so CI proves the whole chain
without any broadcast hardware.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import AlphaMask, Frame
from stageforge.output.base import DeliveryStats, OutputSink, SinkWriteError

__all__ = ["FileOutputSink"]


class FileOutputSink(OutputSink):
    """Writes ``fill_NNNN.png`` and ``key_NNNN.png`` into ``out_dir``."""

    def __init__(
        self, out_dir: str = "out", fill_prefix: str = "fill", key_prefix: str = "key"
    ) -> None:
        self._dir = Path(out_dir)
        self._fill_prefix = fill_prefix
        self._key_prefix = key_prefix
        self._index = 0
        self._sent = 0
        self._opened = False

    @property
    def index(self) -> int:
        """Number of pairs written so far."""
        return self._index

    @property
    def directory(self) -> Path:
        """Directory the pairs land in."""
        return self._dir

    def open(self) -> None:
        """Create the output directory. Safe to call twice."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self._opened = True
        logger.info(f"file sink open: {self._dir.resolve()}")

    def send(self, frame: Frame, key: AlphaMask) -> DeliveryStats:
        """Write one fill/key pair and report what was delivered."""
        if not self._opened:
            raise SinkWriteError("FileOutputSink.send() before open()")
        if frame.data is None:
            raise SinkWriteError(f"frame {frame.camera_id} has no pixels to write")

        self.write(frame.data, key.data, self._index)
        self._index += 1
        self._sent += 1
        return DeliveryStats(sent_frames=self._sent, last_latency_us=0)

    def write(self, fill: npt.NDArray[np.uint8], key: npt.NDArray[np.uint8], index: int) -> None:
        """Persist one raw pair; raises ``SinkWriteError`` if a write fails."""
        fill_path = self._dir / f"{self._fill_prefix}_{index:04d}.png"
        key_path = self._dir / f"{self._key_prefix}_{index:04d}.png"
        if not cv2.imwrite(str(fill_path), np.ascontiguousarray(fill)):
            raise SinkWriteError(f"could not write {fill_path}")
        if not cv2.imwrite(str(key_path), np.ascontiguousarray(key)):
            raise SinkWriteError(f"could not write {key_path}")

    def close(self) -> None:
        """Flush nothing (PNG is written synchronously). Safe to call twice."""
        if self._opened:
            logger.info(f"file sink closed: {self._sent} pairs in {self._dir.resolve()}")
        self._opened = False
