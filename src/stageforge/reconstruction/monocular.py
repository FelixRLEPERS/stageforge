"""Monocular depth for rigs that own no depth sensor.

Depth Anything V2 Small predicts a *relative* depth map (ADR 0002):
near-to-far, no metric scale, ``[0, 1]`` downstream, L3 -> alpha mask,
``[ml]`` extras import lazily (CI-safe without torch).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import Frame, RelativeDepthFrame
from stageforge.reconstruction.base import DepthProvider
from stageforge.reconstruction.depth_norm import normalise_depth
from stageforge.reconstruction.onnx_support import open_onnx_session

DEFAULT_MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
DEFAULT_ONNX_PATH = "models/depth_anything_v2_small.onnx"
ML_HINT = "monocular depth requires [ml] extras: pip install -e .[ml]"
BACKENDS = ("onnx", "transformers")

__all__ = [
    "BACKENDS",
    "DEFAULT_MODEL_ID",
    "DEFAULT_ONNX_PATH",
    "ML_HINT",
    "MonocularDepthProvider",
    "normalise_depth",
]


class MonocularDepthProvider(DepthProvider):
    """Runs Depth Anything V2 on each frame and normalises the result.

    ``near_is_high`` records native polarity (larger = nearer), so the
    default inverts output to the package convention ``0 = nearest,
    1 = farthest``. Flip it in config for a different checkpoint.
    """

    def __init__(
        self,
        device: str = "auto",
        model_id: str = DEFAULT_MODEL_ID,
        near_is_high: bool = True,
        backend: str = "transformers",
        onnx_path: str = DEFAULT_ONNX_PATH,
        precision: str = "fp16",
    ) -> None:
        if backend not in BACKENDS:
            raise ValueError(f"unknown backend {backend!r}, expected one of {BACKENDS}")
        if precision not in ("fp16", "fp32"):
            raise ValueError(f"unknown precision {precision!r}, expected 'fp16' or 'fp32'")
        self._device = device
        self._model_id = model_id
        self._near_is_high = near_is_high
        self._backend = backend
        self._onnx_path = onnx_path
        self._precision = precision
        self._processor: Any = None
        self._model: Any = None
        self._session: Any = None
        self._runtime_device = "cpu"

    @property
    def is_ready(self) -> bool:
        """True once the weights (or the ONNX session) have been loaded."""
        return self._model is not None or self._session is not None

    @property
    def backend(self) -> str:
        """Which inference path this provider was built for."""
        return self._backend

    @property
    def precision(self) -> str:
        """Weights precision for the transformers path (ONNX is fixed at export)."""
        return self._precision

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
        if self._model is not None or self._session is not None:
            return
        try:
            from transformers import AutoImageProcessor
        except ImportError as exc:
            raise RuntimeError(ML_HINT) from exc
        # transformers 5.x leaves this factory untyped (decorator-generated).
        self._processor = AutoImageProcessor.from_pretrained(  # type: ignore[no-untyped-call]
            self._model_id
        )
        if self._backend == "onnx":
            self._load_onnx()
            return

        try:
            import torch
            from transformers import AutoModelForDepthEstimation
        except ImportError as exc:
            raise RuntimeError(ML_HINT) from exc

        device = self._device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if self._precision == "fp16" and device != "cuda":
            raise RuntimeError("fp16 requires CUDA; use fp32 on CPU")
        logger.info(f"loading depth {self._model_id} device={device} precision={self._precision}")
        model = AutoModelForDepthEstimation.from_pretrained(self._model_id).to(device).eval()
        self._model = model.half() if self._precision == "fp16" else model
        self._runtime_device = device

    def _load_onnx(self) -> None:
        """Open the exported graph; extras, file and DLL quirks explain themselves."""
        self._session, self._runtime_device = open_onnx_session(self._onnx_path)

    def _infer(self, image: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        """BGR frame -> normalised ``[0, 1]`` depth at the same resolution."""
        height, width = image.shape[:2]
        rgb = np.ascontiguousarray(image[..., ::-1])  # OpenCV is BGR
        if self._backend == "onnx":
            raw = self._infer_onnx(rgb, height, width)
        else:
            raw = self._infer_transformers(rgb, height, width)
        return normalise_depth(raw, near_is_high=self._near_is_high)

    def _infer_transformers(self, rgb: npt.NDArray[np.uint8], height: int, width: int) -> Any:
        """HF path: predict at the processor grid, bicubic up to the frame."""
        import torch
        import torch.nn.functional as functional

        batch = self._processor(images=rgb, return_tensors="pt")
        batch = {name: tensor.to(self._runtime_device) for name, tensor in batch.items()}
        if self._precision == "fp16":
            batch = {name: (t.half() if t.is_floating_point() else t) for name, t in batch.items()}

        with torch.no_grad():
            outputs = self._model(**batch)
        predicted = outputs.predicted_depth
        depth = functional.interpolate(
            predicted[:, None],
            size=(height, width),
            mode="bicubic",
            align_corners=False,
        )
        return np.asarray(depth[0, 0].detach().cpu().numpy(), dtype=np.float32)

    def _infer_onnx(
        self, rgb: npt.NDArray[np.uint8], height: int, width: int
    ) -> npt.NDArray[np.float32]:
        """onnxruntime path — same processor preprocessing, same contract.

        ``scripts/export_depth_onnx.py`` verified the graph emits
        ``(1, h, w)`` — ``tensor[0]`` is the 2-D map; NaN/Inf are zeroed first.
        """
        import cv2

        batch = self._processor(images=rgb, return_tensors="np")
        pixel_values = np.asarray(batch["pixel_values"], dtype=np.float32)
        tensor = self._session.run(None, {"pixel_values": pixel_values})[0]
        depth = tensor[0]
        assert depth.ndim == 2, f"Unexpected depth shape: {depth.shape}"
        depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
        if depth.shape != (height, width):
            depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_CUBIC)
        return np.asarray(depth, dtype=np.float32)
