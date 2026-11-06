"""Scaffold implementation of :class:`Tracker`."""

from __future__ import annotations

from stageforge.core.types import CameraPose, Frame
from stageforge.tracking.base import Tracker

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubTracker(Tracker):
    """Placeholder tracker that raises instead of solving poses."""

    def connect(self) -> None:
        """Raise until a real Free-D client exists."""
        raise NotImplementedError(_MESSAGE)

    def pose_for(self, frame: Frame) -> CameraPose:
        """Raise until a real Free-D client exists."""
        raise NotImplementedError(_MESSAGE)

    def disconnect(self) -> None:
        """Raise until a real Free-D client exists."""
        raise NotImplementedError(_MESSAGE)
