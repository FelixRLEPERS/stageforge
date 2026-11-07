"""The StageForge pipeline: five layers, one clock, one output.

The pipeline is the only component allowed to know about every layer.
Its job is to start them in order (capture → reconstruction/tracking →
segmentation → compositing → output), to pair ``Frame`` with
``CameraPose``, ``DepthMap`` and ``AlphaMask`` on a common timestamp, to
enforce the ≤ 4 frame latency budget by dropping late work, and to stop
them in reverse order on shutdown. Errors that would leave the output
carrying stale data are surfaced as ``PipelineError`` so the show caller
can switch to the spare chain.

Two orchestrators live here: :class:`Pipeline` is the original scaffold
contract (still exercised by ``tests/test_pipeline.py``), and
:class:`StageForgePipeline` is the MVP that actually runs the chain built
by :mod:`stageforge.orchestrator.builder`.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from stageforge.compositing.base import RendererUnavailableError
from stageforge.core.log import logger
from stageforge.core.types import CameraPose, Frame
from stageforge.orchestrator.builder import MODES, Chain, build_chain
from stageforge.output.base import SinkWriteError

_LOG_EVERY = 30

__all__ = ["Pipeline", "PipelineError", "RunStats", "StageForgePipeline"]


class PipelineError(RuntimeError):
    """Raised when a layer fails in a way that cannot be recovered."""


class Pipeline:
    """Owns the lifecycle of the five StageForge layers.

    Usage::

        pipeline = Pipeline(config)
        pipeline.run()   # blocks until stopped; scaffold raises
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Store the validated configuration for the layers to read."""
        self.config = config or {}

    @property
    def layers(self) -> tuple[str, ...]:
        """Layer names in the order they must be started."""
        return (
            "capture",
            "reconstruction",
            "tracking",
            "segmentation",
            "compositing",
            "output",
        )

    def run(self) -> None:
        """Start every layer; scaffold raises until the MVP wires them."""
        raise NotImplementedError("StageForge scaffold — replace in MVP phase")

    def stop(self) -> None:
        """Stop every layer in reverse order; scaffold raises."""
        raise NotImplementedError("StageForge scaffold — replace in MVP phase")


@dataclass(frozen=True, slots=True)
class RunStats:
    """Summary of one :meth:`StageForgePipeline.run` call."""

    mode: str
    total_frames: int
    avg_latency_ms: float
    fps: float
    desyncs: int


class StageForgePipeline:
    """Runs the wired chain: capture → depth → key → composite → output.

    Usage::

        stats = StageForgePipeline(config).run(max_frames=300)
    """

    def __init__(self, config: dict[str, Any] | None = None, dry_run: bool = False) -> None:
        """Keep the config; the chain itself is built inside :meth:`run`."""
        self._config: dict[str, Any] = config or {}
        self._dry_run = dry_run
        self._chain: Chain | None = None
        self._running = False

    @property
    def layers(self) -> tuple[str, ...]:
        """Layer names in start order (no separate tracker in the MVP)."""
        return ("capture", "reconstruction", "segmentation", "compositing", "output")

    @property
    def running(self) -> bool:
        """True while the frame loop is active."""
        return self._running

    @property
    def mode(self) -> str:
        """Effective mode after applying ``--dry-run``."""
        return "synthetic" if self._dry_run else str(self._config.get("mode", "monocular"))

    def run(self, max_frames: int | None = None) -> RunStats:
        """Build, start and stop the chain; returns a run summary.

        ``max_frames=None`` blocks until :meth:`stop` is called from
        another thread or a layer raises.
        """
        if self.mode not in MODES:
            raise PipelineError(f"unknown mode {self.mode!r}, expected one of {MODES}")

        chain = build_chain(self._config, dry_run=self._dry_run)
        self._chain = chain
        logger.info(f"mode={chain.mode} topic={chain.topic!r} max_frames={max_frames}")

        chain.prepare()
        chain.open()
        self._running = True

        processed = 0
        latencies: list[float] = []
        started = perf_counter()
        try:
            while self._running and (max_frames is None or processed < max_frames):
                before = perf_counter()
                frames = chain.pull()
                if max_frames is not None:
                    # Never process more than requested, even when a round
                    # carries one frame per camera.
                    frames = frames[: max_frames - processed]
                for frame in frames:
                    self._process(chain, chain.calibrate(frame))
                latencies.append((perf_counter() - before) * 1000.0 / max(1, len(frames)))
                processed += len(frames)
                if processed % _LOG_EVERY == 0:
                    logger.info(_progress(latencies, processed, started, chain.desyncs))
        finally:
            self._running = False
            chain.close()

        elapsed = max(1e-9, perf_counter() - started)
        stats = RunStats(
            mode=chain.mode,
            total_frames=processed,
            avg_latency_ms=_mean(latencies),
            fps=processed / elapsed,
            desyncs=chain.desyncs,
        )
        logger.info(
            f"run complete: mode={stats.mode} total_frames={stats.total_frames} "
            f"avg_latency_ms={stats.avg_latency_ms:.1f} fps={stats.fps:.1f} "
            f"desyncs={stats.desyncs}"
        )
        return stats

    def stop(self) -> None:
        """Ask the frame loop to exit after the current batch."""
        self._running = False

    def _process(self, chain: Chain, frame: Frame) -> None:
        """Run one frame through L2 → L5 and surface unrecoverable errors."""
        try:
            depth = chain.depth.depth_for(frame)
            mask = chain.segmenter.segment(frame, depth)
            pose = CameraPose.identity(frame.camera_id, frame.timestamp_us)
            assets = chain.storylink.assets_for_topic(chain.topic)
            fill = chain.compositor.render(frame, mask, pose, assets)
            chain.sink.send(fill, mask)
        except (RendererUnavailableError, SinkWriteError) as exc:
            raise PipelineError(f"layer failed on frame {frame.sequence}: {exc}") from exc


def _mean(values: list[float]) -> float:
    """Arithmetic mean, 0.0 for an empty list."""
    return sum(values) / len(values) if values else 0.0


def _progress(
    latencies: list[float],
    processed: int,
    started: float,
    desyncs: int,
) -> str:
    """One-line heartbeat matching the run report format."""
    elapsed = max(1e-9, perf_counter() - started)
    return (
        f"avg_latency_ms={_mean(latencies):.1f}, fps={processed / elapsed:.1f}, desyncs={desyncs}"
    )
