"""``python -m stageforge.orchestrator`` entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import yaml

from stageforge.orchestrator.pipeline import Pipeline

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


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and start the pipeline."""
    _configure_streams()
    parser = argparse.ArgumentParser(prog="stageforge", description=__doc__)
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args(argv)

    pipeline = Pipeline(_load_config(args.config))
    try:
        pipeline.run()
    except NotImplementedError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
