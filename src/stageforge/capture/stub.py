"""Scaffold implementation of :class:`CaptureSource`."""

from __future__ import annotations

from collections.abc import Iterator

from stageforge.capture.base import CaptureSource
from stageforge.core.types import Frame

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubCaptureSource(CaptureSource):
    """Placeholder capture source that raises instead of producing frames."""

    def open(self) -> None:
        """Raise until a real NDI/SDI source exists."""
        raise NotImplementedError(_MESSAGE)

    def read(self) -> Frame:
        """Raise until a real NDI/SDI source exists."""
        raise NotImplementedError(_MESSAGE)

    def frames(self) -> Iterator[Frame]:
        """Raise until a real NDI/SDI source exists."""
        raise NotImplementedError(_MESSAGE)
        yield  # pragma: no cover — keeps the method an Iterator

    def close(self) -> None:
        """Raise until a real NDI/SDI source exists."""
        raise NotImplementedError(_MESSAGE)
