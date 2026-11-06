"""L1 — video capture from SDI and NDI sources."""

from stageforge.capture.base import CaptureSource, SourceUnavailableError
from stageforge.capture.stub import StubCaptureSource

__all__ = ["CaptureSource", "SourceUnavailableError", "StubCaptureSource"]
