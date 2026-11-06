"""Export Depth Anything V2 Small to ONNX for the monocular depth backend.

Usage::

    python scripts/export_depth_onnx.py

Three things this script deliberately gets right:

- ``model.eval()`` **before** ``torch.onnx.export`` — otherwise
  BatchNorm/Dropout emit training-behaviour outputs.
- Preprocessing goes through ``processor()`` exactly as inference does,
  and ``image_mean``/``image_std`` are printed rather than assumed
  (they turn out to be ImageNet values for this checkpoint — printed as
  a fact, never hand-inlined).
- Dynamic axes on batch/height/width, so any raster whose sides are
  divisible by 14 can be served without aspect distortion (518x294 for
  16:9 keeps the network on its native 14-px patch grid).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
ONNX_PATH = Path("models/depth_anything_v2_small.onnx")
OPSET = 17

__all__ = ["main"]


def _gradient(width: int = 1920, height: int = 1080) -> np.ndarray:
    """BGR synthetic gradient — export never needs a camera."""
    blue = np.tile(np.linspace(0, 255, width, dtype=np.uint8), (height, 1))
    green = np.tile(np.linspace(0, 255, height, dtype=np.uint8)[:, None], (1, width))
    return np.stack([blue, green, 255 - blue], axis=-1)


def main(argv: list[str] | None = None) -> int:
    """Export the checkpoint, then round-trip it through onnxruntime."""
    del argv  # no options; kept for CLI symmetry with the other scripts
    try:
        import onnxruntime as ort
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except ImportError as exc:
        print(f'{exc} — install with: pip install -e ".[ml,onnx-gpu]"', file=sys.stderr)
        return 1

    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    print(f"processor.image_mean={processor.image_mean} image_std={processor.image_std}")

    model = AutoModelForDepthEstimation.from_pretrained(MODEL_ID)
    model.eval()  # BEFORE export — training-mode BatchNorm would corrupt outputs

    pixel_values = processor(images=_gradient(), return_tensors="pt")["pixel_values"]
    print(f"export input pixel_values={tuple(pixel_values.shape)} dtype={pixel_values.dtype}")

    class _DepthOnly(torch.nn.Module):
        """Return the raw tensor so output_names can name a plain output."""

        def __init__(self) -> None:
            super().__init__()
            self._inner = model

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            return self._inner(pixel_values=pixel_values).predicted_depth

    ONNX_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        _DepthOnly(),
        (pixel_values,),
        str(ONNX_PATH),
        input_names=["pixel_values"],
        output_names=["predicted_depth"],
        dynamic_axes={
            "pixel_values": {0: "batch", 2: "height", 3: "width"},
            "predicted_depth": {0: "batch", 1: "height", 2: "width"},
        },
        opset_version=OPSET,
        do_constant_folding=True,
        dynamo=False,
    )
    print(f"exported {ONNX_PATH} ({ONNX_PATH.stat().st_size / 1e6:.1f} MB, opset {OPSET})")

    session = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    onnx_out = session.run(None, {"pixel_values": pixel_values.numpy()})[0]
    with torch.no_grad():
        torch_out = _DepthOnly()(pixel_values).numpy()
    print(f"onnx predicted_depth.shape={onnx_out.shape} dtype={onnx_out.dtype}")
    print(f"torch predicted_depth.shape={torch_out.shape}")
    delta = float(np.abs(onnx_out - torch_out).max())
    print(f"max |onnx - torch| = {delta:.6f}")
    if onnx_out.shape != torch_out.shape:
        print("FAIL: shape mismatch between torch and onnx exports", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
