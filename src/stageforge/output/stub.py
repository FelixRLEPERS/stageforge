"""Scaffold implementation of :class:`OutputSink`."""

from __future__ import annotations

from stageforge.core.types import AlphaMask, Frame
from stageforge.output.base import DeliveryStats, OutputSink

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubOutputSink(OutputSink):
    """Placeholder sink that raises instead of transmitting."""

    def open(self) -> None:
        """Raise until a real DeckLink/NDI sink exists."""
        raise NotImplementedError(_MESSAGE)

    def send(self, frame: Frame, key: AlphaMask) -> DeliveryStats:
        """Raise until a real DeckLink/NDI sink exists."""
        raise NotImplementedError(_MESSAGE)

    def close(self) -> None:
        """Raise until a real DeckLink/NDI sink exists."""
        raise NotImplementedError(_MESSAGE)
