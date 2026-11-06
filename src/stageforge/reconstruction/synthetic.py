"""Synthetic depth for ``--dry-run`` and CI.

Emits the same ``RelativeDepthFrame`` contract as the monocular network
but with a closed-form ramp: a blob near the frame centre reads as
"close" and the edges read as "far". That is enough for the alpha layer
to produce a plausible matte, which is all a dry run needs to prove the
wiring end to end.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import Frame, RelativeDepthFrame
from stageforge.reconstruction.base import DepthProvider

__all__ = ["SyntheticDepthProvider"]


class SyntheticDepthProvider(DepthProvider):
    """Radial near-to-far ramp centred on the frame's 'presenter'."""

    def __init__(self, focus_x: float = 0.5, focus_y: float = 0.6) -> None:
        if not 0.0 <= focus_x <= 1.0 or not 0.0 <= focus_y <= 1.0:
            raise ValueError(f"focus must be inside the frame, got ({focus_x}, {focus_y})")
        self._focus_x = focus_x
        self._focus_y = focus_y

    def calibrate(self) -> None:
        """Nothing to calibrate; present so dry runs log the same stages."""
        logger.info("synthetic depth provider ready (no calibration)")

    def depth_for(self, frame: Frame) -> RelativeDepthFrame:
        """Return a radial ``[0, 1]`` ramp matching this frame's size."""
        if frame.data is None:
            raise ValueError(f"frame {frame.camera_id} carries no image data")
        return RelativeDepthFrame(
            camera_id=frame.camera_id,
            timestamp_us=frame.timestamp_us,
            data=radial_depth(
                frame.height,
                frame.width,
                focus_x=self._focus_x,
                focus_y=self._focus_y,
            ),
            model_id="synthetic",
        )


def radial_depth(
    height: int,
    width: int,
    focus_x: float = 0.5,
    focus_y: float = 0.6,
) -> npt.NDArray[np.float32]:
    """Unitless near/far map: 0 at the focus, 1 at the frame edge."""
    if height <= 0 or width <= 0:
        raise ValueError(f"invalid raster {width}x{height}")

    rows, columns = np.mgrid[0:height, 0:width].astype(np.float32)
    delta_x = (columns - focus_x * (width - 1)) / max(1.0, width * 0.35)
    delta_y = (rows - focus_y * (height - 1)) / max(1.0, height * 0.55)
    distance = np.sqrt(delta_x * delta_x + delta_y * delta_y)
    return np.asarray(np.clip(distance, 0.0, 1.0), dtype=np.float32)
