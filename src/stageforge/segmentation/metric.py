"""Metric depth -> alpha, for the future depth-sensor pilot.

Kept separate from :mod:`stageforge.segmentation.depth_alpha` because
the two make different promises: this one takes metres and therefore
needs a real depth sensor, while the MVP path takes relative depth from
a monocular network (ADR 0002). Nothing in the MVP calls it yet — it
exists so the ToF/stereo pilot has a drop-in replacement.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

__all__ = ["depth_to_alpha"]


def depth_to_alpha(
    depth_m: npt.NDArray[np.float32],
    near_m: float = 1.0,
    far_m: float = 4.0,
    softness: float = 0.0,
) -> npt.NDArray[np.uint8]:
    """Map metric depth to foreground coverage in ``[0, 255]``.

    Anything at or closer than ``near_m`` is fully foreground (255), at
    or beyond ``far_m`` fully background (0), with a linear ramp between
    the two. ``softness`` widens that ramp by the given number of metres
    on both ends, which is how a feathered key would be expressed.
    """
    if far_m <= near_m:
        raise ValueError(f"far_m ({far_m}) must be greater than near_m ({near_m})")

    near = max(0.0, near_m - softness)
    far = far_m + softness
    span = far - near
    if span <= 1e-6:
        return np.zeros_like(depth_m, dtype=np.uint8)

    # 0 at the near plane, 1 at the far plane, then invert: near = foreground.
    normalised = np.asarray(np.clip((depth_m - near) / span, 0.0, 1.0), dtype=np.float32)
    coverage = 1.0 - normalised
    return np.asarray(np.round(coverage * 255.0), dtype=np.uint8)
