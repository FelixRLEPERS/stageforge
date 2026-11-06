"""End-to-end: synthetic capture → depth → key → composite → sink."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from stageforge.orchestrator.builder import build_chain
from stageforge.orchestrator.pipeline import StageForgePipeline


def _config(output_mode: str, out_dir: Path | None = None) -> dict[str, Any]:
    """Minimal synthetic config; everything else falls back to defaults."""
    config: dict[str, Any] = {
        "mode": "synthetic",
        "camera": {"num_cameras": 1, "synthetic": {"pattern": "pillarbox"}},
        "compositing": {"topic": "military_tech"},
        "output": {"mode": output_mode},
    }
    if out_dir is not None:
        config["output"]["out_dir"] = str(out_dir)
    return config


def test_pipeline_synthetic_runs(tmp_path: Path) -> None:
    pipeline = StageForgePipeline(_config("null"), dry_run=False)
    stats = pipeline.run(max_frames=3)

    assert stats.mode == "synthetic"
    assert stats.total_frames == 3
    assert stats.avg_latency_ms >= 0.0
    assert stats.fps > 0.0
    assert stats.desyncs == 0
    assert not pipeline.running


def test_pipeline_synthetic_writes_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "frames"
    pipeline = StageForgePipeline(_config("file", out_dir))
    stats = pipeline.run(max_frames=1)

    assert stats.total_frames == 1
    fill = out_dir / "fill_0000.png"
    key = out_dir / "key_0000.png"
    assert fill.is_file()
    assert key.is_file()

    plate = cv2.imread(str(fill))
    matte = cv2.imread(str(key), cv2.IMREAD_GRAYSCALE)
    assert plate is not None and plate.ndim == 3
    assert matte is not None and matte.ndim == 2
    assert plate.shape[:2] == matte.shape[:2]


def test_builder_selects_synthetic_layers() -> None:
    """The synthetic mode must never touch a device or a model."""
    from stageforge.capture.synthetic import SyntheticCameraSource
    from stageforge.reconstruction.synthetic import SyntheticDepthProvider

    chain = build_chain(_config("null"))
    assert chain.mode == "synthetic"
    assert isinstance(chain.capture, SyntheticCameraSource)
    assert isinstance(chain.depth, SyntheticDepthProvider)
    assert chain.topic == "military_tech"
