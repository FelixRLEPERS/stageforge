"""Core types and contracts shared by all StageForge layers."""

from stageforge.core.base import Layer
from stageforge.core.stub import StubLayer
from stageforge.core.types import (
    AlphaMask,
    ARAsset,
    CameraPose,
    DepthMap,
    Frame,
    RelativeDepthFrame,
    RundownCue,
)

__all__ = [
    "ARAsset",
    "AlphaMask",
    "CameraPose",
    "DepthMap",
    "Frame",
    "Layer",
    "RelativeDepthFrame",
    "RundownCue",
    "StubLayer",
]
