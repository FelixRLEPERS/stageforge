"""Backend runners for ``scripts/measure_depth_backends.py``.

Split out so the benchmark entry point stays a readable table printer:
each factory returns ``(runner, describe, cleanup)``; the holder list
inside is the backend's only reference, so ``cleanup`` really releases
VRAM before the next row is measured. Imported as a sibling module
(``sys.path[0]`` is ``scripts/`` while the benchmark runs).

The runners mirror ``MonocularDepthProvider._infer``: ``processor()``
preprocessing, inference, bicubic resize to the frame, min-max normalise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from stageforge.reconstruction.depth_norm import normalise_depth

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
ONNX_MODEL = Path("models/depth_anything_v2_small.onnx")

__all__ = ["MODEL_ID", "frame", "free_gpu", "hf_factory", "normalise", "onnx_factory"]


def frame(width: int = 1920, height: int = 1080) -> np.ndarray:
    """BGR synthetic gradient — generated, never from a camera."""
    blue = np.tile(np.linspace(0, 255, width, dtype=np.uint8), (height, 1))
    green = np.tile(np.linspace(0, 255, height, dtype=np.uint8)[:, None], (1, width))
    return np.stack([blue, green, 255 - blue], axis=-1)


def normalise(raw: np.ndarray) -> np.ndarray:
    """The production min-max step (``MonocularDepthProvider._infer``)."""
    return normalise_depth(raw, near_is_high=True)


def free_gpu() -> None:
    """Release a backend before the next row, so contention cannot inflate it."""
    import gc

    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def hf_factory(common: tuple[Any, ...], device: str, mode: str) -> tuple[Any, Any, Any]:
    """One HF model as fp32 / fp16 / torch.compile; the holder is its only ref."""
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModelForDepthEstimation

    processor, rgb, height, width = common
    grid: dict[str, str] = {}
    holder: list[Any] = [AutoModelForDepthEstimation.from_pretrained(MODEL_ID)]
    if mode == "compile":
        holder[0] = torch.compile(holder[0].to(device).eval(), mode="reduce-overhead")
    else:
        holder[0] = (holder[0].half() if mode == "fp16" else holder[0].float()).to(device).eval()

    def runner() -> np.ndarray:
        batch = processor(images=rgb, return_tensors="pt")
        tensors = {name: t.to(device) for name, t in batch.items()}
        if mode == "fp16":
            tensors = {
                name: (t.half() if t.is_floating_point() else t) for name, t in tensors.items()
            }
        with torch.no_grad():
            outputs = holder[0](**tensors)
        grid["pred"] = str(tuple(outputs.predicted_depth.shape))
        depth = functional.interpolate(
            outputs.predicted_depth.float()[:, None],
            size=(height, width),
            mode="bicubic",
            align_corners=False,
        )
        return normalise(np.asarray(depth[0, 0].detach().cpu().numpy(), dtype=np.float32))

    def describe(output: np.ndarray) -> str:
        suffix = " (compiled)" if mode == "compile" else ""
        return f"pred {grid.get('pred', '?')} -> out {output.shape}{suffix}"

    def cleanup() -> None:
        holder.clear()
        free_gpu()

    return runner, describe, cleanup


def onnx_factory(common: tuple[Any, ...]) -> tuple[Any, Any, Any]:
    """Exported-graph runner; the session is opened exactly like production."""
    import cv2

    from stageforge.reconstruction.onnx_support import open_onnx_session

    processor, rgb, height, width = common
    session, _device = open_onnx_session(str(ONNX_MODEL))
    # get_providers() is what actually runs — the table must not lie.
    active = str(session.get_providers())
    holder: list[Any] = [session]

    def runner() -> np.ndarray:
        batch = processor(images=rgb, return_tensors="np")
        pixel_values = np.asarray(batch["pixel_values"], dtype=np.float32)
        depth = np.asarray(
            holder[0].run(None, {"pixel_values": pixel_values})[0][0], dtype=np.float32
        )
        if depth.shape != (height, width):
            depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_CUBIC)
        return normalise(depth)

    def describe(output: np.ndarray) -> str:
        return f"providers={active} -> out {output.shape}"

    def cleanup() -> None:
        holder.clear()
        free_gpu()

    return runner, describe, cleanup
