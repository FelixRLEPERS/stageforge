"""Contract for L1: bringing studio video into the pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from stageforge.core.types import Frame


class SourceUnavailableError(RuntimeError):
    """Raised when a capture device disappears or never becomes ready."""


class CaptureSource(ABC):
    """Produces timestamped :class:`Frame` objects from one video device.

    Input: a source descriptor from the config ``camera`` section
    (device index or endpoint, expected raster and frame rate).
    Output: ``Frame`` objects carrying a monotonic capture timestamp in
    microseconds plus a per-source sequence id used for multi-camera
    alignment; ``read()`` is the pull API the orchestrator uses and
    ``frames()`` is its iterator form.
    Raises: ``SourceUnavailableError`` if the device cannot be opened or
    is lost mid-stream; late frames are dropped, never delayed.
    """

    @abstractmethod
    def open(self) -> None:
        """Acquire the device and wait until it delivers frames."""

    @abstractmethod
    def read(self) -> Frame:
        """Return exactly one frame, or raise ``SourceUnavailableError``."""

    @abstractmethod
    def frames(self) -> Iterator[Frame]:
        """Yield frames until the source is closed or fails."""

    @abstractmethod
    def close(self) -> None:
        """Release the device. Safe to call twice."""
