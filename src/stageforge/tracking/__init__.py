"""L2 — camera tracking (Free-D and friends)."""

from stageforge.tracking.base import Tracker, TrackingLostError
from stageforge.tracking.stub import StubTracker

__all__ = ["StubTracker", "Tracker", "TrackingLostError"]
