"""The StageForge pipeline: five layers, one clock, one output.

The pipeline is the only component allowed to know about every layer.
Its job is to start them in order (capture → reconstruction/tracking →
segmentation → compositing → output), to pair ``Frame`` with
``CameraPose``, ``DepthMap`` and ``AlphaMask`` on a common timestamp,
to enforce the ≤ 4 frame latency budget by dropping late work, and to
stop them in reverse order on shutdown. Errors that would leave the
output carrying stale data are surfaced as ``PipelineError`` so the
show caller can switch to the spare chain.
"""

from __future__ import annotations

from typing import Any


class PipelineError(RuntimeError):
    """Raised when a layer fails in a way that cannot be recovered."""


class Pipeline:
    """Owns the lifecycle of the five StageForge layers.

    Usage::

        pipeline = Pipeline(config)
        pipeline.run()   # blocks until stopped; scaffold raises
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Store the validated configuration; no devices are touched yet."""
        self._config: dict[str, Any] = config or {}

    @property
    def layers(self) -> tuple[str, ...]:
        """Layer names in start order."""
        return (
            "capture",
            "reconstruction",
            "tracking",
            "segmentation",
            "compositing",
            "output",
        )

    def run(self) -> None:
        """Start every layer and process frames until stopped."""
        raise NotImplementedError("StageForge scaffold — replace in MVP phase")

    def stop(self) -> None:
        """Stop every layer in reverse order. Idempotent."""
        raise NotImplementedError("StageForge scaffold — replace in MVP phase")
