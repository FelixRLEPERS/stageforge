"""Min-max normalisation of relative depth to the package-wide ``[0, 1]``.

Split out of ``monocular.py`` so both backends, the benchmark script and
the tests share one pure function without importing the provider class
(and its lazily-loaded extras) for it.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

__all__ = ["normalise_depth"]


def normalise_depth(
    raw: npt.NDArray[np.float32],
    near_is_high: bool = True,
) -> npt.NDArray[np.float32]:
    """Min-max stretch to ``[0, 1]`` with the polarity made explicit.

    A flat prediction (single value) maps to all-zeros — "everything at
    the same distance" — rather than to NaN.
    """
    low = float(raw.min())
    high = float(raw.max())
    span = high - low
    if span <= 1e-6:
        return np.zeros_like(raw)
    norm = (raw - low) / span
    relative = 1.0 - norm if near_is_high else norm
    return np.asarray(np.clip(relative, 0.0, 1.0), dtype=np.float32)
