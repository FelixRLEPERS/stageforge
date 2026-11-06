"""Contract for L5: getting the composited frame to air."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from stageforge.core.types import AlphaMask, Frame


class SinkWriteError(RuntimeError):
    """Raised when the output device drops frames or overruns its buffer."""


@dataclass(frozen=True, slots=True)
class DeliveryStats:
    """Per-interval counters published by an :class:`OutputSink`."""

    sent_frames: int = 0
    dropped_frames: int = 0
    last_latency_us: int = 0


class OutputSink(ABC):
    """Sends a composited :class:`Frame` plus its ``AlphaMask`` to a device.

    Input: the composited plate and the key, both already aligned to the
    configured scan mode (``output.scan_mode``).
    Output: nothing on the wire-agnostic side; returns
    ``DeliveryStats`` so the orchestrator can log drops and latency.
    Raises: ``SinkWriteError`` on buffer overrun or device loss — the
    caller must not retry inside the show, it must switch to the spare.
    """

    @abstractmethod
    def open(self) -> None:
        """Configure the device for the requested scan mode."""

    @abstractmethod
    def send(self, frame: Frame, key: AlphaMask) -> DeliveryStats:
        """Transmit one fill/key pair."""

    @abstractmethod
    def close(self) -> None:
        """Flush and release the device. Safe to call twice."""
