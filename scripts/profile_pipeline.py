"""Per-stage latency profile for one synthetic frame — the 33 ms gate.

Usage::

    python scripts/profile_pipeline.py [--config configs/dev.yaml] [--frames 5]

Loads the config, forces ``mode=synthetic`` and ``output.mode=null`` (no
hardware touched, no files written), runs one warm-up frame so caches and
cv2 code paths are hot, then times every stage of the chain with
``time.perf_counter``. ``--pattern plain`` (default) keeps the full
1920x1080 raster — the 5D Mark IV no-bars case; ``pillarbox`` reproduces
the 5D Mark II geometry. The sum of the stage rows is the per-frame
budget that must stay <= 33 ms to hold 1080p30.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from stageforge.core.types import CameraPose, Frame
from stageforge.orchestrator.builder import Chain, build_chain

BUDGET_MS = 33.0

STAGES = (
    "capture.read",
    "depth.predict",
    "segment",
    "assets_for_topic",
    "composite",
    "sink.send",
)


def _load_config(path: Path) -> dict[str, Any]:
    """Read the YAML config and force the hardware-free synthetic path."""
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"config root must be a mapping: {path}")
    data["mode"] = "synthetic"
    output = data.get("output")
    if not isinstance(output, dict):
        output = {}
        data["output"] = output
    output["mode"] = "null"
    return data


def _time_frame(chain: Chain) -> tuple[dict[str, float], Frame, Frame]:
    """Run one frame through L1 → L5, returning per-stage seconds."""
    marks: dict[str, float] = {}

    start = perf_counter()
    frames = chain.pull()
    frame = frames[0]
    marks["capture.read"] = perf_counter() - start

    start = perf_counter()
    depth = chain.depth.depth_for(frame)
    marks["depth.predict"] = perf_counter() - start

    start = perf_counter()
    mask = chain.segmenter.segment(frame, depth)
    marks["segment"] = perf_counter() - start

    start = perf_counter()
    assets = chain.storylink.assets_for_topic(chain.topic)
    marks["assets_for_topic"] = perf_counter() - start

    start = perf_counter()
    pose = CameraPose.identity(frame.camera_id, frame.timestamp_us)
    fill = chain.compositor.render(frame, mask, pose, assets)
    marks["composite"] = perf_counter() - start

    start = perf_counter()
    chain.sink.send(fill, mask)
    marks["sink.send"] = perf_counter() - start
    return marks, frame, mask


def main(argv: list[str] | None = None) -> int:
    """Profile N frames and print the per-stage table."""
    parser = argparse.ArgumentParser(description="StageForge per-stage latency profile")
    parser.add_argument("--config", default="configs/dev.yaml", help="YAML config to load")
    parser.add_argument("--frames", type=int, default=5, help="frames to measure (after warm-up)")
    parser.add_argument(
        "--pattern",
        default="plain",
        choices=("plain", "bars", "pillarbox"),
        help="synthetic pattern; plain keeps the full 1920x1080 (5D Mark IV, no bars)",
    )
    args = parser.parse_args(argv)

    config = _load_config(Path(args.config))
    camera = config.get("camera")
    if isinstance(camera, dict):
        synthetic = camera.setdefault("synthetic", {})
        if isinstance(synthetic, dict):
            synthetic["pattern"] = args.pattern
    chain = build_chain(config)
    chain.prepare()
    chain.open()
    totals = {stage: 0.0 for stage in STAGES}
    frame: Frame | None = None
    mask: Frame | None = None
    try:
        _time_frame(chain)  # warm-up: not measured
        for _ in range(max(1, args.frames)):
            marks, frame, mask = _time_frame(chain)
            for stage, seconds in marks.items():
                totals[stage] += seconds
    finally:
        chain.close()

    count = max(1, args.frames)
    raster = (
        f"{frame.data.shape[1]}x{frame.data.shape[0]}"
        if frame is not None and frame.data is not None
        else "?"
    )
    print(f"stage latency @{raster} synthetic, {count} frame(s), ms per frame:")
    total_ms = 0.0
    for stage in STAGES:
        ms = totals[stage] * 1000.0 / count
        total_ms += ms
        print(f"  {stage:<18} {ms:8.2f}")
    print(
        f"  {'TOTAL':<18} {total_ms:8.2f}   budget {BUDGET_MS:.0f} ms -> "
        + ("OK" if total_ms <= BUDGET_MS else "OVER")
    )
    if frame is not None and frame.data is not None and mask is not None:
        print(f"frame.image.shape={frame.data.shape} alpha.data.shape={mask.data.shape}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
