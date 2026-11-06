"""Monocular depth for rigs that own no depth sensor.

Depth Anything V2 Small predicts a *relative* depth map from a single
RGB frame: it orders surfaces near-to-far but carries no metric scale
(ADR 0002). Everything downstream therefore works in ``[0, 1]`` and the
conversion to an alpha mask happens in L3.

Dependencies live in the ``[ml]`` extra and are imported lazily, so the
rest of the package — and CI — stays importable without torch.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import Frame, RelativeDepthFrame
from stageforge.reconstruction.base import DepthProvider

DEFAULT_MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
ML_HINT = "monocular depth requires [ml] extras: pip install -e .[ml]"

__all__ = ["DEFAULT_MODEL_ID", "ML_HINT", "MonocularDepthProvider"]


class MonocularDepthProvider(DepthProvider):
    """Runs Depth Anything V2 on each frame and normalises the result.

    ``near_is_high`` records the model's native polarity: Depth Anything
    emits larger values for nearer surfaces, so the default inverts the
    normalised output to satisfy the package-wide convention
    ``0 = nearest, 1 = farthest``. Flip it in config if a different
    checkpoint is used.
    """

    def __init__(
        self,
        device: str = "auto",
        model_id: str = DEFAULT_MODEL_ID,
        near_is_high: bool = True,
    ) -> None:
        self._device = device
        self._model_id = model_id
        self._near_is_high = near_is_high
        self._processor: Any = None
        self._model: Any = None
        self._runtime_device = "cpu"

    @property
    def is_ready(self) -> bool:
        """True once the weights have been loaded."""
        return self._model is not None

    @property
    def runtime_device(self) -> str:
        """Device actually resolved from ``device="auto"``."""
        return self._runtime_device

    @property
    def model_id(self) -> str:
        """Checkpoint identifier, for logs and run reports."""
        return self._model_id

    def calibrate(self) -> None:
        """Load the checkpoint — monocular depth needs no lens calibration."""
        self._load()

    def depth_for(self, frame: Frame) -> RelativeDepthFrame:
        """Estimate relative depth for exactly this frame."""
        if frame.data is None:
            raise ValueError(f"frame {frame.camera_id} carries no image data")
        self._load()
        depth = self._infer(frame.data)
        return RelativeDepthFrame(
            camera_id=frame.camera_id,
            timestamp_us=frame.timestamp_us,
            data=depth,
            model_id=self._model_id,
        )

    def predict(self, frame: Frame) -> RelativeDepthFrame:
        """Inference-flavoured alias of :meth:`depth_for`."""
        return self.depth_for(frame)

    def _load(self) -> None:
        """Import the ``[ml]`` extras and load the model exactly once."""
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        except ImportError as exc:
            raise RuntimeError(ML_HINT) from exc

        device = self._device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"loading depth model {self._model_id} on device={device}")
        self._processor = AutoImageProcessor.from_pretrained(self._model_id)
        self._model = AutoModelForDepthEstimation.from_pretrained(self._model_id).to(device).eval()
        self._runtime_device = device

    def _infer(self, image: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        """BGR frame -> normalised ``[0, 1]`` depth at the same resolution."""
        import torch
        import torch.nn.functional as functional

        height, width = image.shape[:2]
        rgb = np.ascontiguousarray(image[..., ::-1])  # OpenCV is BGR
        batch = self._processor(images=rgb, return_tensors="pt")
        batch = {name: tensor.to(self._runtime_device) for name, tensor in batch.items()}

        with torch.no_grad():
            outputs = self._model(**batch)
        predicted = outputs.predicted_depth
        depth = functional.interpolate(
            predicted[:, None],
            size=(height, width),
            mode="bicubic",
            align_corners=False,
        )
        raw = np.asarray(depth[0, 0].detach().cpu().numpy(), dtype=np.float32)
        return normalise_depth(raw, near_is_high=self._near_is_high)


def normalise_depth(
    raw: npt.NDArray[np.float32],
    near_is_high: bool = True,
) -> npt.NDArray[np.float32]:
    """Min-max stretch to ``[0, 1]`` with the polarity made explicit.

    A flat prediction (single value) maps to all-zeros — "everything at
    the same distance" — rather than to NaN.
    """
    low = float(raw.min())
    high = float(raw.max())
    span = high - low
    if span <= 1e-6:
        return np.zeros_like(raw)
    norm = (raw - low) / span
    relative = 1.0 - norm if near_is_high else norm
    return np.asarray(np.clip(relative, 0.0, 1.0), dtype=np.float32)
