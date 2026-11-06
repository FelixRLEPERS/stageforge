"""L2 — depth reconstruction of the studio geometry."""

from stageforge.reconstruction.base import CalibrationError, DepthProvider
from stageforge.reconstruction.monocular import (
    DEFAULT_MODEL_ID,
    ML_HINT,
    MonocularDepthProvider,
    normalise_depth,
)
from stageforge.reconstruction.stub import StubDepthProvider
from stageforge.reconstruction.synthetic import SyntheticDepthProvider, radial_depth

__all__ = [
    "DEFAULT_MODEL_ID",
    "ML_HINT",
    "CalibrationError",
    "DepthProvider",
    "MonocularDepthProvider",
    "StubDepthProvider",
    "SyntheticDepthProvider",
    "normalise_depth",
    "radial_depth",
]
