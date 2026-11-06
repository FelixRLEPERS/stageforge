"""Contract for L2b: knowing where each camera is."""

from __future__ import annotations

from abc import ABC, abstractmethod

from stageforge.core.types import CameraPose, Frame


class TrackingLostError(RuntimeError):
    """Raised when no tracking packet arrives before the deadline."""


class Tracker(ABC):
    """Resolves the world pose of a camera for each incoming frame.

    Input: a Free-D stream (pan/tilt/zoom/focus/position) plus the
    camera calibration, selected by the ``tracker`` config section.
    Output: a :class:`CameraPose` carrying a 4x4 world-from-camera
    matrix valid for the paired ``Frame``.
    Raises: ``TrackingLostError`` when packets stop arriving; callers
    must then hold the last known pose rather than guessing.
    """

    @abstractmethod
    def connect(self) -> None:
        """Open the tracking socket and load the lens calibration."""

    @abstractmethod
    def pose_for(self, frame: Frame) -> CameraPose:
        """Return the pose that matches this frame's timestamp."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the socket. Safe to call twice."""
