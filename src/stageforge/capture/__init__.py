"""L1 — video capture from SDI and NDI sources."""

from stageforge.capture.base import CaptureSource, SourceUnavailableError
from stageforge.capture.crop import (
    Rect,
    apply_crop,
    crop_to_aspect,
    detect_and_crop,
    detect_bars,
    detect_letterbox,
    detect_pillarbox,
)
from stageforge.capture.multi import MultiCameraSource
from stageforge.capture.source import UsbCameraSource
from stageforge.capture.stub import StubCaptureSource
from stageforge.capture.synthetic import PATTERNS, SyntheticCameraSource

__all__ = [
    "PATTERNS",
    "CaptureSource",
    "MultiCameraSource",
    "Rect",
    "SourceUnavailableError",
    "StubCaptureSource",
    "SyntheticCameraSource",
    "UsbCameraSource",
    "apply_crop",
    "crop_to_aspect",
    "detect_and_crop",
    "detect_bars",
    "detect_letterbox",
    "detect_pillarbox",
]
