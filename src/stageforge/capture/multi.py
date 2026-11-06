"""Multi-camera alignment without genlock.

Two USB capture cards on two different host controllers will not deliver
frames in lock-step: their counters drift by a frame or two depending on
USB scheduling. Rather than pretending we have genlock, this source
reads every camera once per round and *reports* how far apart the frame
ids are. A skew above ``max_skew`` is logged and counted, so drift shows
up in the run summary instead of silently degrading the composite.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from stageforge.capture.base import CaptureSource, SourceUnavailableError
from stageforge.core.log import logger
from stageforge.core.types import Frame

__all__ = ["MultiCameraSource"]


class MultiCameraSource(CaptureSource):
    """Reads several :class:`CaptureSource` objects as aligned rounds."""

    def __init__(
        self,
        sources: list[CaptureSource],
        max_skew: int = 2,
        max_frames: int | None = None,
    ) -> None:
        if not sources:
            raise ValueError("MultiCameraSource requires at least one source")
        self._sources = list(sources)
        self._max_skew = max_skew
        self.max_frames = max_frames
        self._desyncs = 0
        self._rounds = 0

    @property
    def desyncs(self) -> int:
        """Number of rounds whose frame-id spread exceeded ``max_skew``."""
        return self._desyncs

    @property
    def rounds(self) -> int:
        """Number of completed read rounds."""
        return self._rounds

    @property
    def sources(self) -> tuple[CaptureSource, ...]:
        """The underlying sources, in read order."""
        return tuple(self._sources)

    def open(self) -> None:
        """Open every source; roll back the ones already opened on failure."""
        opened: list[CaptureSource] = []
        try:
            for source in self._sources:
                source.open()
                opened.append(source)
        except Exception:
            for source in reversed(opened):
                source.close()
            raise
        logger.info(f"multi-camera opened: {len(self._sources)} sources")

    def read(self) -> Frame:
        """Contract-compatible single frame: the primary camera's picture.

        Use :meth:`read_round` when you need every camera at once.
        """
        return self.read_round()[0]

    def read_round(self) -> list[Frame]:
        """Read one frame per camera and check the frame-id spread."""
        frames = [source.read() for source in self._sources]
        if not frames:
            raise SourceUnavailableError("multi-camera read produced no frames")

        self._rounds += 1
        sequence = [frame.sequence for frame in frames]
        spread = max(sequence) - min(sequence)
        if spread > self._max_skew:
            self._desyncs += 1
            logger.warning(
                f"camera desync: frame_ids={sequence} spread={spread} max_skew={self._max_skew}"
            )
        return frames

    def frames(self) -> Iterator[Frame]:
        """Yield every camera's frame, round by round (flat iterator).

        Bounded by ``max_frames`` so an unattended consumer cannot spin
        forever once every source has delivered that many rounds.
        """
        produced = 0
        while self._sources and (self.max_frames is None or produced < self.max_frames):
            for frame in self.read_round():
                yield frame
                produced += 1
                if self.max_frames is not None and produced >= self.max_frames:
                    return

    def close(self) -> None:
        """Close every source. Safe to call twice, never raises."""
        for source in self._sources:
            try:
                source.close()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"close failed for {type(source).__name__}: {exc}")

    def now_us(self) -> int:
        """Shared monotonic timestamp for a round, in microseconds."""
        return int(time.monotonic() * 1_000_000)
