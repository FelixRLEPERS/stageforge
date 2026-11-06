"""L4 — AR rendering and plate compositing."""

from stageforge.compositing.base import Compositor, RendererUnavailableError
from stageforge.compositing.stub import StubCompositor

__all__ = ["Compositor", "RendererUnavailableError", "StubCompositor"]
