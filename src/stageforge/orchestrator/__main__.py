"""``python -m stageforge.orchestrator`` entry point.

With ``--config`` (or ``--dry-run``) the real MVP chain runs; without any
arguments the original scaffold is reported, which keeps bare invocations
of the module informative instead of silently opening cameras.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import yaml

from stageforge.core.log import logger
from stageforge.orchestrator.pipeline import PipelineError, RunStats, StageForgePipeline

_MESSAGE = "StageForge scaffold — replace in MVP phase"


def _load_config(path: str | None) -> dict[str, Any]:
    """Read a YAML config file, or return an empty mapping."""
    if not path:
        return {}
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"config root must be a mapping: {path}")
    return data


def _configure_streams() -> None:
    """Make stdout/stderr tolerant of non-ASCII messages on any console."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _report(stats: RunStats) -> None:
    """Print the human-readable end-of-run summary."""
    print(
        f"mode={stats.mode} total_frames={stats.total_frames} "
        f"avg_latency_ms={stats.avg_latency_ms:.1f} fps={stats.fps:.1f} "
        f"desyncs={stats.desyncs}"
    )


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and start the pipeline. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m stageforge.orchestrator",
        description="Run the StageForge capture → depth → key → composite → output chain.",
    )
    parser.add_argument("--config", help="path to a YAML config (e.g. configs/dev.yaml)")
    parser.add_argument("--frames", type=int, default=None, help="stop after N frames")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="force mode=synthetic: no camera, no torch, safe everywhere",
    )
    parser.add_argument(
        "--record-raw",
        action="store_true",
        help="save every Nth raw camera frame to debug.raw_dir (offline debugging)",
    )
    args = parser.parse_args(argv)

    _configure_streams()
    config = _load_config(args.config)
    if args.dry_run and not config:
        config = {"mode": "synthetic", "output": {"mode": "null"}}
    if args.dry_run:
        config["mode"] = "synthetic"

    if not config:
        print(_MESSAGE, file=sys.stderr)
        return 1

    if args.record_raw:
        debug = config.get("debug")
        debug = dict(debug) if isinstance(debug, dict) else {}
        config["debug"] = {**debug, "record_raw": True}

    pipeline = StageForgePipeline(config, dry_run=args.dry_run)
    try:
        stats = pipeline.run(max_frames=args.frames)
    except (PipelineError, RuntimeError, ValueError, NotImplementedError) as exc:
        logger.error(f"{exc}")
        return 1

    _report(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
