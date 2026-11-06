"""L3 — foreground segmentation and alpha generation."""

from stageforge.segmentation.base import SegmentationError, Segmenter
from stageforge.segmentation.depth_alpha import DepthAlphaSegmenter
from stageforge.segmentation.metric import depth_to_alpha
from stageforge.segmentation.stub import StubSegmenter

__all__ = [
    "DepthAlphaSegmenter",
    "SegmentationError",
    "Segmenter",
    "StubSegmenter",
    "depth_to_alpha",
]
