"""Alpha from *relative* depth — the no-green-screen path (L3).

Monocular depth orders surfaces but has no scale (ADR 0002), so the
foreground is defined statistically: the nearest ``low_pct`` percent of
the frame is fully keyed, the farthest ``high_pct`` is fully clear, and
everything between ramps linearly. This adapts to a wide shot and a
close-up without a per-show distance threshold.
"""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import AlphaMask, DepthMap, Frame, RelativeDepthFrame
from stageforge.segmentation.base import SegmentationError, Segmenter

_DEPTH = DepthMap | RelativeDepthFrame

__all__ = ["DepthAlphaSegmenter"]


class DepthAlphaSegmenter(Segmenter):
    """Percentile-stretches relative depth into a uint8 foreground matte.

    ``invert=True`` encodes the package-wide convention that near is
    foreground: low depth values become 255. Morphology is optional and
    off the hot path by default because a large kernel on a 1080p CPU
    pass is the one thing here that can break the 30 fps budget.
    """

    def __init__(
        self,
        low_pct: float = 5.0,
        high_pct: float = 95.0,
        morphology_kernel: int = 3,
        invert: bool = True,
    ) -> None:
        if not 0 <= low_pct < high_pct <= 100:
            raise ValueError(f"expected 0 <= low_pct < high_pct <= 100, got {low_pct}/{high_pct}")
        self._low_pct = low_pct
        self._high_pct = high_pct
        kernel = max(0, int(morphology_kernel))
        self._kernel = kernel if kernel <= 1 or kernel % 2 else kernel + 1
        self._invert = invert
        self._warned = False

    @property
    def low_pct(self) -> float:
        """Percentile treated as fully foreground."""
        return self._low_pct

    @property
    def high_pct(self) -> float:
        """Percentile treated as fully background."""
        return self._high_pct

    def warmup(self) -> None:
        """No model to load — kept for contract symmetry with the AI keyer."""
        return None

    def segment(self, frame: Frame, depth: _DEPTH | None = None) -> AlphaMask:
        """Build the foreground matte for this frame."""
        if depth is None:
            raise SegmentationError(
                f"segment() needs a depth buffer for {frame.camera_id}; "
                "wire a DepthProvider upstream"
            )
        alpha = self.relative_to_alpha(depth.data)
        return AlphaMask(
            camera_id=frame.camera_id,
            timestamp_us=frame.timestamp_us,
            data=alpha,
            source="depth",
        )

    def relative_to_alpha(self, depth_rel: npt.NDArray[np.float32]) -> npt.NDArray[np.uint8]:
        """``[0, 1]`` relative depth -> ``[0, 255]`` foreground coverage."""
        if depth_rel.size == 0:
            raise SegmentationError("empty depth buffer")

        low = float(np.percentile(depth_rel, self._low_pct))
        high = float(np.percentile(depth_rel, self._high_pct))
        span = high - low
        if span <= 1e-6:
            norm = np.zeros_like(depth_rel, dtype=np.float32)
        else:
            clipped = np.clip(depth_rel, low, high)
            norm = np.asarray((clipped - low) / span, dtype=np.float32)

        coverage = 1.0 - norm if self._invert else norm
        alpha = np.asarray(np.round(coverage * 255.0), dtype=np.uint8)
        return self._morphology(alpha, depth_rel.shape)

    def _morphology(
        self,
        alpha: npt.NDArray[np.uint8],
        shape: tuple[int, ...],
    ) -> npt.NDArray[np.uint8]:
        """Close holes then drop speckle; no-op when the kernel is off."""
        if self._kernel <= 1:
            return alpha

        height = shape[0]
        if height >= 720 and self._kernel >= 5 and not self._warned:
            self._warned = True
            logger.warning(
                f"segmentation: {self._kernel}px morphology on {height}p may not "
                "sustain 30+ fps on CPU; consider a smaller kernel or cv2.cuda"
            )

        element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self._kernel, self._kernel))
        closed = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, element)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, element)
        return np.asarray(opened, dtype=np.uint8)
