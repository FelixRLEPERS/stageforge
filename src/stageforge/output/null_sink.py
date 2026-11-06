"""Sink that keeps nothing — for tests, dry runs and benchmarks.

Counting still happens, so a run report can say "N frames went
through"; only the bytes are discarded.
"""

from __future__ import annotations

from stageforge.core.log import logger
from stageforge.core.types import AlphaMask, Frame
from stageforge.output.base import DeliveryStats, OutputSink

__all__ = ["NullOutputSink"]


class NullOutputSink(OutputSink):
    """Accepts every frame, writes nothing, counts what it saw."""

    def __init__(self, name: str = "null") -> None:
        self._name = name
        self._sent = 0
        self._opened = False

    @property
    def sent(self) -> int:
        """Number of fill/key pairs accepted."""
        return self._sent

    def open(self) -> None:
        """Mark ready. Safe to call twice."""
        self._opened = True
        logger.info(f"null sink open: {self._name}")

    def send(self, frame: Frame, key: AlphaMask) -> DeliveryStats:
        """Count the frame and drop it on the floor."""
        if not self._opened:
            raise RuntimeError("NullOutputSink.send() before open()")
        self._sent += 1
        return DeliveryStats(sent_frames=self._sent, last_latency_us=0)

    def close(self) -> None:
        """Report the total. Safe to call twice."""
        if self._opened:
            logger.info(f"null sink closed: accepted {self._sent} frames")
        self._opened = False
