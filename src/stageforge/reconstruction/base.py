"""Contract for L2a: recovering depth for the studio scene."""

from __future__ import annotations

from abc import ABC, abstractmethod

from stageforge.core.types import DepthMap, Frame, RelativeDepthFrame


class CalibrationError(RuntimeError):
    """Raised when depth extrinsics/intrinsics are missing or stale."""


class DepthProvider(ABC):
    """Turns sensor or network input into a depth buffer for one frame.

    Input: a calibrated depth device (ToF, stereo), an SfM point cloud,
    or — for the MVP — a single RGB frame fed to a monocular network.
    Output: a ``DepthMap`` in metres when a real sensor is present, or a
    ``RelativeDepthFrame`` in ``[0, 1]`` when depth is estimated from
    the picture alone (0 = nearest, 1 = farthest). Either way the
    timestamp matches the paired ``Frame`` within one frame period.
    Raises: ``CalibrationError`` when calibration is absent, expired or
    belongs to another camera id, and ``RuntimeError`` when a required
    optional dependency is missing.
    """

    @abstractmethod
    def calibrate(self) -> None:
        """Load calibration — or, for monocular depth, the model weights."""

    @abstractmethod
    def depth_for(self, frame: Frame) -> DepthMap | RelativeDepthFrame:
        """Return the depth buffer for exactly this frame."""
