"""Shared data contracts passed between pipeline layers.

These dataclasses are the *only* vocabulary layers may share; nothing
in the package is allowed to import vendor SDK types across a layer
boundary. All buffers are numpy arrays and all timestamps are integer
microseconds on a monotonic (genlock/PTP derived) clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

MaskArray = npt.NDArray[np.uint8]
DepthArray = npt.NDArray[np.float32]
FrameArray = npt.NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class Frame:
    """One video frame plus the identity needed to align it with peers."""

    timestamp_us: int
    camera_id: str
    width: int
    height: int
    data: FrameArray | None
    sequence: int = 0

    @property
    def shape(self) -> tuple[int, int]:
        """Spatial size as ``(height, width)``."""
        return (self.height, self.width)


@dataclass(frozen=True, slots=True)
class CameraPose:
    """Rigid transform of a camera in world space for a single frame."""

    camera_id: str
    timestamp_us: int
    matrix: npt.NDArray[np.float64]
    is_valid: bool = True

    @staticmethod
    def identity(camera_id: str, timestamp_us: int) -> CameraPose:
        """Return a world-aligned pose (used when tracking is lost)."""
        return CameraPose(camera_id, timestamp_us, np.eye(4, dtype=np.float64))


@dataclass(frozen=True, slots=True)
class DepthMap:
    """Metric depth buffer aligned with the frame that produced it."""

    camera_id: str
    timestamp_us: int
    data: DepthArray
    unit: Literal["m"] = "m"
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class AlphaMask:
    """Foreground coverage in ``[0, 255]`` matching the source frame."""

    camera_id: str
    timestamp_us: int
    data: MaskArray
    confidence: float = 1.0
    source: Literal["depth", "ai", "none"] = "none"


@dataclass(frozen=True, slots=True)
class ARAsset:
    """A renderable piece of AR content bound to an editorial topic."""

    asset_id: str
    kind: Literal["model", "video", "graphic", "chart"]
    uri: str
    anchor: str = "stage_center"
    scale: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RundownCue:
    """One rundown entry received from the newsroom computer system."""

    cue_id: str
    topic: str
    title: str
    starts_at_us: int
    duration_us: int = 0
    keywords: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()

    def matches(self, needle: str) -> bool:
        """Cheap substring match against topic, title and keywords."""
        target = needle.casefold()
        haystack = (self.topic, self.title, *self.keywords)
        return any(target in value.casefold() for value in haystack)
