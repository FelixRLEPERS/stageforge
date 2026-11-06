"""Opening the exported ONNX depth graph on Windows.

``open_onnx_session`` is the one place a session is created (used by the
provider *and* by ``scripts/measure_depth_backends.py``): it checks the
extras, the exported file, and the Windows CUDA DLL quirk below.

ORT resolves the CUDA/cuDNN DLLs by bare name when the first Conv node
executes — a failed lookup surfaces *at run time*
(``cuDNN is unavailable ... LoadLibrary failed for cudnn64_9.dll``, error 2),
not at session creation, so the provider happily lists itself as active and
then crashes on frame 1. On Windows the ``[ml]`` extra ships those DLLs
inside ``torch/lib``; prepending that directory to ``PATH`` before the
session is created makes the resolution succeed.

Measured 2026-11-06 on the reference machine (see CHANGELOG): without this,
an isolated onnx CUDA run raises ``NOT_IMPLEMENTED`` on every Conv; with it,
inference runs on the GPU.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from stageforge.core.log import logger

ONNX_HINT = 'monocular onnx backend requires [onnx-gpu] extras: pip install -e ".[ml,onnx-gpu]"'
ONNX_MISSING = "ONNX model not found. Run scripts/export_depth_onnx.py first."

__all__ = ["ONNX_HINT", "ONNX_MISSING", "enable_bundled_cuda_dlls", "open_onnx_session"]


def enable_bundled_cuda_dlls() -> None:
    """Prepend torch's ``lib`` dir (cudnn/cublas DLLs) to the DLL search path.

    Uses ``find_spec`` instead of ``import torch`` — locating the directory
    must not cost a full torch import. No-op off Windows, without torch, or
    when the directory is already on ``PATH``.
    """
    if sys.platform != "win32":
        return
    spec = importlib.util.find_spec("torch")
    if spec is None or not spec.submodule_search_locations:
        return
    torch_lib = Path(next(iter(spec.submodule_search_locations))) / "lib"
    if not torch_lib.is_dir():
        return
    current = os.environ.get("PATH", "")
    if str(torch_lib) not in current.split(os.pathsep):
        os.environ["PATH"] = f"{torch_lib}{os.pathsep}{current}"


def open_onnx_session(model_path: str) -> tuple[Any, str]:
    """Create the depth session; returns ``(session, runtime device name)``.

    Missing extras and a missing file explain themselves; the Windows CUDA
    DLL fix runs first, so the provider can actually execute its Convs.
    """
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError(ONNX_HINT) from exc
    path = Path(model_path)
    if not path.is_file():
        raise RuntimeError(ONNX_MISSING)
    enable_bundled_cuda_dlls()  # else ORT fails every Conv: cudnn64_9.dll not on PATH
    available = ort.get_available_providers()
    providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]
    logger.info(f"loading onnx depth model {path} providers={providers}")
    session = ort.InferenceSession(str(path), providers=providers)
    return session, "cuda" if providers[0] == "CUDAExecutionProvider" else "cpu"
