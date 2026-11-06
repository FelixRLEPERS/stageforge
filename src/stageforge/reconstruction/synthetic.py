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
        self._cache: dict[tuple[int, int], npt.NDArray[np.float32]] = {}

    def calibrate(self) -> None:
        """Nothing to calibrate; present so dry runs log the same stages."""
        logger.info("synthetic depth provider ready (no calibration)")

    def depth_for(self, frame: Frame) -> RelativeDepthFrame:
        """Return a radial ``[0, 1]`` ramp matching this frame's size.

        The ramp depends only on the raster, so it is computed once per
        size and reused (treat the returned buffer as read-only — every
        downstream consumer copies before writing). This takes ``depth``
        from ~47 ms to <0.1 ms per frame in ``--dry-run``.
        """
        if frame.data is None:
            raise ValueError(f"frame {frame.camera_id} carries no image data")
        ramp = self._cache.get((frame.height, frame.width))
        if ramp is None:
            ramp = radial_depth(
                frame.height,
                frame.width,
                focus_x=self._focus_x,
                focus_y=self._focus_y,
            )
            self._cache[(frame.height, frame.width)] = ramp
        return RelativeDepthFrame(
            camera_id=frame.camera_id,
            timestamp_us=frame.timestamp_us,
            data=ramp,
            model_id="synthetic",
        )


def radial_depth(
    height: int,
    width: int,
    focus_x: float = 0.5,
    focus_y: float = 0.6,
) -> npt.NDArray[np.float32]:
    """Unitless near/far map: 0 at the focus, 1 at the frame edge.

    Built from two 1-D coordinate vectors broadcast to the raster — the
    old ``np.mgrid`` path materialised two int64 index grids (23 MB)
    before every subtraction.
    """
    if height <= 0 or width <= 0:
        raise ValueError(f"invalid raster {width}x{height}")

    columns = (np.arange(width, dtype=np.float32) - focus_x * (width - 1)) / max(1.0, width * 0.35)
    rows = (np.arange(height, dtype=np.float32) - focus_y * (height - 1)) / max(1.0, height * 0.55)
    distance = rows[:, None] ** 2 + columns[None, :] ** 2
    np.sqrt(distance, out=distance)
    return np.asarray(np.clip(distance, 0.0, 1.0, out=distance), dtype=np.float32)
