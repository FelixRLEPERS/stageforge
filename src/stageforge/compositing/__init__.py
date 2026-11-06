"""L4 — AR rendering and plate compositing."""

from stageforge.compositing.assets import anchor_point, load_asset, place_asset
from stageforge.compositing.base import Compositor, RendererUnavailableError
from stageforge.compositing.simple2d import DEFAULT_BACKGROUND_SHADE, Simple2DCompositor
from stageforge.compositing.stub import StubCompositor

__all__ = [
    "DEFAULT_BACKGROUND_SHADE",
    "Compositor",
    "RendererUnavailableError",
    "Simple2DCompositor",
    "StubCompositor",
    "anchor_point",
    "load_asset",
    "place_asset",
]
