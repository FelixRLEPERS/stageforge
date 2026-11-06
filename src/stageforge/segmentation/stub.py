"""Scaffold implementation of :class:`Segmenter`."""

from __future__ import annotations

from stageforge.core.types import AlphaMask, DepthMap, Frame, RelativeDepthFrame
from stageforge.segmentation.base import Segmenter

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubSegmenter(Segmenter):
    """Placeholder segmenter that raises instead of keying."""

    def warmup(self) -> None:
        """Raise until a real depth/AI keyer exists."""
        raise NotImplementedError(_MESSAGE)

    def segment(
        self,
        frame: Frame,
        depth: DepthMap | RelativeDepthFrame | None = None,
    ) -> AlphaMask:
        """Raise until a real depth/AI keyer exists."""
        raise NotImplementedError(_MESSAGE)
