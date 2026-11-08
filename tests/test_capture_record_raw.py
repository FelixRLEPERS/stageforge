"""Raw-frame recording (debug.record_raw): files on disk + a valid manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from stageforge.capture.record import RawFrameRecorder
from stageforge.capture.synthetic import SyntheticCameraSource
from stageforge.orchestrator.cameras import build_capture


def _read_frames(source: SyntheticCameraSource, count: int) -> None:
    source.open()
    try:
        for _ in range(count):
            source.read()
    finally:
        source.close()


def test_record_raw_writes_every_nth_frame(tmp_path: Path) -> None:
    """Frames 5 and 10 land on disk; the rest are only counted."""
    source = SyntheticCameraSource(
        pattern="plain",
        target_aspect=None,
        record_raw=True,
        raw_dir=str(tmp_path),
        raw_every_n=5,
    )
    _read_frames(source, 12)

    files = sorted(p.name for p in tmp_path.glob("*.png"))
    assert files == ["cam0_frame000005.png", "cam0_frame000010.png"]


def test_record_raw_manifest_is_valid_json(tmp_path: Path) -> None:
    """manifest.json carries fps, resolution and one entry per saved frame."""
    source = SyntheticCameraSource(
        pattern="pillarbox",
        target_aspect=None,
        record_raw=True,
        raw_dir=str(tmp_path),
        raw_every_n=3,
        name="5D Mark II (ML)",
    )
    _read_frames(source, 7)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    block = manifest["cam0"]
    assert block["name"] == "5D Mark II (ML)"
    assert block["fps_reported"] == 30.0
    assert block["fps_actual"] > 0.0
    # every 3rd frame of 7: 3 and 6
    assert [entry["frame_id"] for entry in block["frames"]] == [3, 6]
    for entry in block["frames"]:
        assert entry["resolution"] == [1920, 1080]
        assert entry["timestamp_us"] > 0
        assert (tmp_path / entry["file"]).is_file()


def test_record_raw_off_by_default(tmp_path: Path) -> None:
    """Without the flag nothing is written — the pipeline stays untouched."""
    source = SyntheticCameraSource(pattern="plain", raw_dir=str(tmp_path))
    _read_frames(source, 5)
    assert list(tmp_path.iterdir()) == []


def test_record_raw_wired_from_debug_config(tmp_path: Path) -> None:
    """build_capture passes debug.* through to both source kinds."""
    config: dict[str, Any] = {
        "num_cameras": 1,
        "width": 64,
        "height": 48,
        "cameras": [{"name": "synthetic-test", "source": 0}],
        "synthetic": {"pattern": "plain"},
    }
    debug = {"record_raw": True, "raw_dir": str(tmp_path), "raw_every_n": 1}
    capture, multi = build_capture("synthetic", config, debug)
    assert multi is None
    capture.open()
    try:
        capture.read()
    finally:
        capture.close()

    assert (tmp_path / "manifest.json").is_file()


def test_record_raw_rejects_unknown_format() -> None:
    """A typo in raw_format fails fast instead of silently not recording."""
    with pytest.raises(ValueError, match="raw_format"):
        RawFrameRecorder(index=0, fmt="webp")
