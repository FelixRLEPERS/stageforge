"""Assembling the five pipeline layers from a config mapping.

The builder is the only place that knows which concrete class each
abstract contract maps to, which is what makes ``mode`` a single switch:
``monocular`` wires the real USB cameras and Depth Anything, ``synthetic``
wires generated frames so ``--dry-run`` and CI need no hardware.
Camera construction itself lives in :mod:`stageforge.orchestrator.cameras`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stageforge.capture.base import CaptureSource
from stageforge.capture.multi import MultiCameraSource
from stageforge.compositing.base import Compositor
from stageforge.compositing.simple2d import DEFAULT_BACKGROUND_SHADE, Simple2DCompositor
from stageforge.core.log import logger
from stageforge.core.types import Frame
from stageforge.orchestrator.cameras import build_capture, mapping
from stageforge.output.base import OutputSink
from stageforge.output.file_sink import FileOutputSink
from stageforge.output.ndi_sink import NDIOutputSink
from stageforge.output.null_sink import NullOutputSink
from stageforge.reconstruction.base import DepthProvider
from stageforge.reconstruction.monocular import DEFAULT_MODEL_ID, MonocularDepthProvider
from stageforge.reconstruction.synthetic import SyntheticDepthProvider
from stageforge.segmentation.base import Segmenter
from stageforge.segmentation.depth_alpha import DepthAlphaSegmenter
from stageforge.storylink.yaml_provider import YamlStoryLink

MODES = ("monocular", "synthetic")
OUTPUT_MODES = ("file", "ndi", "null")
DEFAULT_STORYLINK = "configs/storylink.yaml"

__all__ = ["DEFAULT_STORYLINK", "MODES", "OUTPUT_MODES", "Chain", "build_chain"]


@dataclass
class Chain:
    """One fully wired pass through the pipeline, ready to run."""

    mode: str
    capture: CaptureSource
    depth: DepthProvider
    segmenter: Segmenter
    compositor: Compositor
    sink: OutputSink
    storylink: YamlStoryLink
    topic: str
    multi: MultiCameraSource | None = None

    @property
    def desyncs(self) -> int:
        """Frame-id spread violations counted by the multi-camera reader."""
        return self.multi.desyncs if self.multi is not None else 0

    def prepare(self) -> None:
        """Load models and attach layers — before any device is opened."""
        self.depth.calibrate()
        self.segmenter.warmup()
        self.compositor.connect()

    def open(self) -> None:
        """Open capture first, then the sink."""
        self.capture.open()
        self.sink.open()

    def close(self) -> None:
        """Tear down in reverse order; one failing layer never blocks the rest."""
        for name, closer in (
            ("sink", self.sink.close),
            ("capture", self.capture.close),
            ("compositor", self.compositor.disconnect),
        ):
            try:
                closer()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"close failed for {name}: {exc}")

    def pull(self) -> list[Frame]:
        """Read one aligned batch: one frame, or one round per camera."""
        if self.multi is not None:
            return self.multi.read_round()
        return [self.capture.read()]


def build_chain(config: Mapping[str, Any], dry_run: bool = False) -> Chain:
    """Instantiate every layer described by ``config`` (or force synthetic)."""
    mode = "synthetic" if dry_run else str(config.get("mode", "monocular"))
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}, expected one of {MODES}")

    capture, multi = build_capture(mode, mapping(config, "camera"))
    segmenter_cfg = mapping(mapping(config, "segmentation"), "depth_alpha")
    compositor_cfg = mapping(config, "compositing")
    shade = compositor_cfg.get("background_shade")

    return Chain(
        mode=mode,
        capture=capture,
        multi=multi,
        depth=_build_depth(mode, config),
        segmenter=DepthAlphaSegmenter(
            low_pct=float(segmenter_cfg.get("low_pct", 5.0)),
            high_pct=float(segmenter_cfg.get("high_pct", 95.0)),
            morphology_kernel=int(segmenter_cfg.get("morphology_kernel", 3)),
            invert=bool(segmenter_cfg.get("invert", True)),
            percentile_scale=float(segmenter_cfg.get("percentile_scale", 0.25)),
        ),
        compositor=Simple2DCompositor(
            background_shade=(
                float(shade) if isinstance(shade, (int, float)) else DEFAULT_BACKGROUND_SHADE
            )
        ),
        sink=_build_output(mapping(config, "output")),
        storylink=_build_storylink(config),
        topic=str(compositor_cfg.get("topic", "")),
    )


def _build_depth(mode: str, config: Mapping[str, Any]) -> DepthProvider:
    """Monocular network for real cameras, radial ramp for dry runs."""
    if mode != "monocular":
        return SyntheticDepthProvider()
    monocular = mapping(mapping(config, "reconstruction"), "monocular")
    return MonocularDepthProvider(
        device=str(monocular.get("device", "auto")),
        model_id=str(monocular.get("model_id", DEFAULT_MODEL_ID)),
        near_is_high=bool(monocular.get("near_is_high", True)),
    )


def _build_output(output_cfg: Mapping[str, Any]) -> OutputSink:
    """Pick the delivery path; ``ndi`` degrades internally if unavailable."""
    mode = str(output_cfg.get("mode", "null"))
    if mode == "file":
        return FileOutputSink(out_dir=str(output_cfg.get("out_dir", "out")))
    if mode == "ndi":
        return NDIOutputSink(name=str(output_cfg.get("ndi_name", "StageForge Preview")))
    if mode == "null":
        return NullOutputSink()
    raise ValueError(f"unknown output.mode {mode!r}, expected one of {OUTPUT_MODES}")


def _build_storylink(config: Mapping[str, Any]) -> YamlStoryLink:
    """Load the rule table when it exists; an absent file is not fatal."""
    storylink_cfg = mapping(config, "storylink")
    path = str(storylink_cfg.get("rules", DEFAULT_STORYLINK))
    link = YamlStoryLink(strict=bool(storylink_cfg.get("strict", False)))
    if Path(path).is_file():
        link.load(path)
    else:
        logger.warning(f"story-link rules not found at {path}; running without AR rules")
    return link
