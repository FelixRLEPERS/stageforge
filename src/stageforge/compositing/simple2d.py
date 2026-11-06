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

__all__ = ["DEFAULT_BACKGROUND_SHADE", "Simple2DCompositor", "dim_background"]


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

        output = dim_background(plate, alpha, self._shade)

        for asset in assets:
            output = place_asset(output, asset)
        return output


def dim_background(
    plate: npt.NDArray[np.uint8],
    alpha: npt.NDArray[np.uint8],
    shade: float,
) -> npt.NDArray[np.uint8]:
    """Dim the plate where ``alpha`` is low, in saturating uint8 OpenCV ops.

    ``out = dim + (plate - dim) * alpha / 255`` is the same linear blend
    the float32 path computed (``shade + (1 - shade) * alpha/255`` scaled
    per pixel), but runs entirely in uint8 SIMD: measured 6.6 ms on
    1920x1080 against 31 ms for the float32 reference and 31 ms for an
    int16 formulation (whose ``diff * alpha`` also overflows int16 for
    ``shade < 0.5``). Equivalent to within 1/255 of the reference — see
    ``tests/test_compositing_simple2d.py``.
    """
    dimmed = cv2.convertScaleAbs(plate, alpha=float(shade), beta=0)
    alpha3 = cv2.cvtColor(alpha, cv2.COLOR_GRAY2BGR)
    diff = cv2.subtract(plate, dimmed)
    scaled = cv2.multiply(diff, alpha3, scale=1.0 / 255.0)
    return np.asarray(cv2.add(dimmed, scaled), dtype=np.uint8)


def _dim_background_reference(
    plate: npt.NDArray[np.uint8],
    alpha: npt.NDArray[np.uint8],
    shade: float,
) -> npt.NDArray[np.uint8]:
    """Float32 reference implementation — kept for the equivalence test."""
    coverage = np.asarray(alpha, dtype=np.float32) / 255.0
    factor = (float(shade) + (1.0 - float(shade)) * coverage)[..., None]
    mixed = plate.astype(np.float32) * factor
    return np.asarray(np.clip(mixed, 0, 255), dtype=np.uint8)
