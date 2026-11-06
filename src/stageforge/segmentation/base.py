"""Contract for L3: producing an alpha channel without a green screen."""

from __future__ import annotations

from abc import ABC, abstractmethod

from stageforge.core.types import AlphaMask, DepthMap, Frame, RelativeDepthFrame


class SegmentationError(RuntimeError):
    """Raised when the keyer cannot produce a usable matte."""


class Segmenter(ABC):
    """Builds an :class:`AlphaMask` for the foreground of one frame.

    Input: the plate ``Frame`` plus, when available, the matching
    ``DepthMap`` (metric, from a depth sensor) or ``RelativeDepthFrame``
    (from a monocular network — see ADR 0002); behaviour is chosen by
    ``segmentation.engine``.
    Output: a uint8 mask of the same spatial size, with a confidence
    value so quality can be logged and compared between engines.
    Raises: ``SegmentationError`` on inference failure — the compositor
    then decides between holding the last matte and passing through.
    """

    @abstractmethod
    def warmup(self) -> None:
        """Load models/weights and run one dry inference."""

    @abstractmethod
    def segment(
        self,
        frame: Frame,
        depth: DepthMap | RelativeDepthFrame | None = None,
    ) -> AlphaMask:
        """Return the foreground matte for this frame."""
