"""Benchmark monocular-depth backends on one synthetic 1920x1080 frame.

Usage::

    python scripts/measure_depth_backends.py [--frames 20] [--warmup 3]

Each row runs ``MonocularDepthProvider._infer``'s exact steps —
``processor()`` preprocessing, inference, bicubic resize, min-max
normalise — and a failing backend becomes a row with its error instead of
aborting the table. The runners live in ``scripts/_depth_backends.py``;
their cleanup frees VRAM before the next row is measured. No camera.
"""

from __future__ import annotations

import argparse
import sys
from time import perf_counter
from typing import Any

import numpy as np
from _depth_backends import MODEL_ID, frame, hf_factory, onnx_factory

BUDGET_MS = 33.0

__all__ = ["main"]


def _measure(runner: Any, warmup: int, frames: int) -> tuple[list[float], np.ndarray]:
    """Warm up, then time ``frames`` runs; returns (ms samples, last output)."""
    output = runner()
    for _ in range(max(0, warmup - 1)):
        output = runner()
    samples: list[float] = []
    for _ in range(frames):
        start = perf_counter()
        output = runner()
        samples.append((perf_counter() - start) * 1000.0)
    return samples, np.asarray(output)


def _row(label: str, samples: list[float], shape: str) -> dict[str, Any]:
    values = np.asarray(samples, dtype=np.float64)
    return {
        "backend": label,
        "avg": f"{values.mean():8.2f}",
        "min": f"{values.min():8.2f}",
        "max": f"{values.max():8.2f}",
        "p95": f"{np.percentile(values, 95):8.2f}",
        "shape": shape,
        "ms": float(values.mean()),
    }


def _skip(label: str, reason: str) -> dict[str, Any]:
    na = "     n/a"
    return {
        "backend": label,
        "avg": na,
        "min": na,
        "max": na,
        "p95": na,
        "shape": reason[:60],
        "ms": float("inf"),
    }


def _attempt(label: str, factory: Any, args: argparse.Namespace) -> dict[str, Any]:
    """Build one backend and time it; failures become table rows."""
    try:
        runner, describe, cleanup = factory()
        try:
            samples, output = _measure(runner, args.warmup, args.frames)
            return _row(label, samples, describe(output))
        finally:
            cleanup()
    except Exception as exc:
        return _skip(label, f"failed: {type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    """Load every backend that works here and print the comparison table."""
    parser = argparse.ArgumentParser(description="StageForge depth backend benchmark")
    parser.add_argument("--frames", type=int, default=20, help="measured iterations")
    parser.add_argument("--warmup", type=int, default=3, help="unmeasured warm-up runs")
    args = parser.parse_args(argv)

    try:
        import torch

        cuda = torch.cuda.is_available()
        print(f"torch {torch.__version__}  cuda_available={cuda}")
    except ImportError as exc:
        print(f'{exc} — install with: pip install -e ".[ml]"', file=sys.stderr)
        return 1

    rgb = frame()
    height, width = rgb.shape[:2]
    print(f"frame {width}x{height} (synthetic gradient), warmup={args.warmup} iters={args.frames}")

    from transformers import AutoImageProcessor

    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    print(f"processor.image_mean={processor.image_mean} image_std={processor.image_std}")

    device = "cuda" if cuda else "cpu"
    common = (processor, rgb, height, width)

    def att(label: str, factory: Any) -> dict[str, Any]:
        return _attempt(label, factory, args)

    rows = [
        att("transformers fp32 (device=auto)", lambda: hf_factory(common, device, "fp32")),
        att("transformers fp16 (cuda)", lambda: hf_factory(common, "cuda", "fp16"))
        if cuda
        else _skip("transformers fp16 (cuda)", "skipped: no CUDA"),
        att("torch.compile fp32", lambda: hf_factory(common, device, "compile")),
        att(f"onnx ({'cuda' if cuda else 'cpu'})", lambda: onnx_factory(common)),
    ]

    print(f"{'backend':<34}{'avg':>9}{'min':>9}{'max':>9}{'p95':>9}  shape")
    for row in rows:
        print(
            f"{row['backend']:<34}{row['avg']:>9}{row['min']:>9}"
            f"{row['max']:>9}{row['p95']:>9}  {row['shape']}"
        )

    best = min(rows, key=lambda row: row["ms"])
    verdict = "OK" if best["ms"] <= BUDGET_MS else "FAIL"
    print(f"recommended: {best['backend']}, {best['ms']:.1f} ms -> budget 33 ms: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
