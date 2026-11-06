"""Scaffold implementation of :class:`DepthProvider`."""

from __future__ import annotations

from stageforge.core.types import DepthMap, Frame
from stageforge.reconstruction.base import DepthProvider

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubDepthProvider(DepthProvider):
    """Placeholder depth provider that raises instead of estimating depth."""

    def calibrate(self) -> None:
        """Raise until a real depth device driver exists."""
        raise NotImplementedError(_MESSAGE)

    def depth_for(self, frame: Frame) -> DepthMap:
        """Raise until a real depth device driver exists."""
        raise NotImplementedError(_MESSAGE)
