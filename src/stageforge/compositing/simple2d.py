"""2D compositing — the MVP path that needs no render bridge.

Instead of an Unreal Engine render, this layer does two things that are
enough to prove the pipeline on air: it dims the background in
proportion to the matte (so a director can *see* the key working), and
it stamps the assets Story-Link selected onto their stage anchors.
"""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.compositing.assets import place_asset
from stageforge.compositing.base import Compositor, RendererUnavailableError
from stageforge.core.log import logger
from stageforge.core.types import AlphaMask, ARAsset, CameraPose, Frame

DEFAULT_BACKGROUND_SHADE = 0.55

__all__ = ["DEFAULT_BACKGROUND_SHADE", "Simple2DCompositor"]


class Simple2DCompositor(Compositor):
    """Mixes plate + matte + assets on the CPU with OpenCV.

    ``background_shade`` is the fraction of brightness the background
    keeps: 1.0 means no visible feedback at all, 0.0 blacks it out.
    """

    def __init__(self, background_shade: float = DEFAULT_BACKGROUND_SHADE) -> None:
        if not 0.0 <= background_shade <= 1.0:
            raise ValueError(f"background_shade must be within [0, 1], got {background_shade}")
        self._shade = float(background_shade)
        self._connected = False

    @property
    def connected(self) -> bool:
        """Whether :meth:`connect` has been called."""
        return self._connected

    def connect(self) -> None:
        """Nothing to attach to in 2D; recorded for lifecycle symmetry."""
        self._connected = True
        logger.info("compositor connected: 2D (no render bridge)")

    def disconnect(self) -> None:
        """Release the flag. Safe to call twice."""
        self._connected = False

    def render(
        self,
        frame: Frame,
        mask: AlphaMask,
        pose: CameraPose,
        assets: tuple[ARAsset, ...],
    ) -> Frame:
        """Produce the composited Fill for this frame."""
        if not pose.is_valid:
            logger.warning(f"{frame.camera_id}: pose invalid, AR placed in screen space")
        filled = self.composite(frame, mask.data, list(assets))
        return Frame(
            timestamp_us=frame.timestamp_us,
            camera_id=frame.camera_id,
            width=int(filled.shape[1]),
            height=int(filled.shape[0]),
            data=filled,
            sequence=frame.sequence,
        )

    def composite(
        self,
        frame: Frame,
        alpha: npt.NDArray[np.uint8],
        assets: list[ARAsset],
    ) -> npt.NDArray[np.uint8]:
        """Dim the background by ``1 - alpha`` and stamp the assets on top."""
        plate = frame.data
        if plate is None:
            raise RendererUnavailableError(f"plate {frame.camera_id} carries no pixels")
        if alpha.shape[:2] != plate.shape[:2]:
            alpha = np.asarray(
                cv2.resize(
                    alpha,
                    (plate.shape[1], plate.shape[0]),
                    interpolation=cv2.INTER_LINEAR,
                ),
                dtype=np.uint8,
            )

        coverage = np.asarray(alpha, dtype=np.float32) / 255.0
        factor = (self._shade + (1.0 - self._shade) * coverage)[..., None]
        mixed = plate.astype(np.float32) * factor
        output = np.asarray(np.clip(mixed, 0, 255), dtype=np.uint8)

        for asset in assets:
            output = place_asset(output, asset)
        return output
