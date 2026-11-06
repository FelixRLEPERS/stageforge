"""Contract for L1: bringing studio video into the pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from stageforge.core.types import Frame


class SourceUnavailableError(RuntimeError):
    """Raised when a capture device disappears or never becomes ready."""


class CaptureSource(ABC):
    """Produces timestamped :class:`Frame` objects from one video device.

    Input: a source descriptor from the ``cameras`` config section
    (transport, endpoint, expected frame rate).
    Output: an iterator of ``Frame`` ordered by capture timestamp, with
    the timestamp taken from genlock/PTP where available.
    Raises: ``SourceUnavailableError`` if the device cannot be opened or
    is lost mid-stream; late frames are dropped, never delayed.
    """

    @abstractmethod
    def open(self) -> None:
        """Acquire the device and wait until it delivers frames."""

    @abstractmethod
    def frames(self) -> Iterator[Frame]:
        """Yield frames until the source is closed or fails."""

    @abstractmethod
    def close(self) -> None:
        """Release the device. Safe to call twice."""
