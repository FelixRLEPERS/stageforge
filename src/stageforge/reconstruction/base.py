"""Contract for L2a: recovering metric depth of the studio."""

from __future__ import annotations

from abc import ABC, abstractmethod

from stageforge.core.types import DepthMap, Frame


class CalibrationError(RuntimeError):
    """Raised when depth extrinsics/intrinsics are missing or stale."""


class DepthProvider(ABC):
    """Turns sensor input into a :class:`DepthMap` aligned with a frame.

    Input: a calibrated depth device (ToF, stereo) or an SfM point
    cloud, selected by the ``depth`` config section.
    Output: ``DepthMap`` whose timestamp matches the paired ``Frame``
    within one frame period, values in metres.
    Raises: ``CalibrationError`` when the calibration file is absent,
    expired, or belongs to another camera id.
    """

    @abstractmethod
    def calibrate(self) -> None:
        """Load and verify calibration for every configured device."""

    @abstractmethod
    def depth_for(self, frame: Frame) -> DepthMap:
        """Return the depth buffer for exactly this frame."""
