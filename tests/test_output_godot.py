"""GodotOutputSink — the file-backed RGBA stream into the Godot layer.

Stdlib + numpy against ``tmp_path``: no Godot, no NDI runtime, no GPU.
Covers the writer side of the seqlock protocol documented in
``docs/06-compositing-ar.md``; the reader side is exercised by the
headless Godot smoke run (``godot/README.md``).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from stageforge.core.types import AlphaMask, Frame
from stageforge.output.base import SinkWriteError
from stageforge.output.godot_sink import (
    FORMAT_RGBA8,
    HEADER_SIZE,
    SHM_MAGIC,
    GodotOutputSink,
)

_WIDTH, _HEIGHT = 4, 3
_TS = 1_700_000_000_000


def _fill() -> np.ndarray:
    """BGR test pattern: one pixel carries distinct channel values."""
    data = np.zeros((_HEIGHT, _WIDTH, 3), dtype=np.uint8)
    data[0, 0] = (10, 20, 30)  # B, G, R
    return data


def _frame() -> Frame:
    return Frame(
        timestamp_us=_TS,
        camera_id="cam_a",
        width=_WIDTH,
        height=_HEIGHT,
        data=_fill(),
    )


def _key(value: int = 200) -> AlphaMask:
    return AlphaMask(
        camera_id="cam_a",
        timestamp_us=_TS,
        data=np.full((_HEIGHT, _WIDTH), value, dtype=np.uint8),
    )


def _header(path: Path) -> tuple[bytes, int, int, int, int, int]:
    with path.open("rb") as handle:
        raw = handle.read(HEADER_SIZE)
    magic, width, height, seq, ts, fmt = struct.unpack("<8sIIQQI4x", raw)
    return magic, width, height, seq, ts, fmt


def _pixels(path: Path) -> np.ndarray:
    with path.open("rb") as handle:
        handle.seek(HEADER_SIZE)
        raw = handle.read()
    return np.frombuffer(raw, dtype=np.uint8).reshape(_HEIGHT, _WIDTH, 4)


def test_publishes_rgba_with_swizzled_pixels(tmp_path: Path) -> None:
    path = tmp_path / "frame.rgba"
    sink = GodotOutputSink(shm_path=str(path))
    sink.open()
    stats = sink.send(_frame(), _key())
    sink.close()

    assert stats.sent_frames == 1
    assert path.stat().st_size == HEADER_SIZE + _WIDTH * _HEIGHT * 4

    magic, width, height, seq, ts, fmt = _header(path)
    assert magic == SHM_MAGIC
    assert (width, height) == (_WIDTH, _HEIGHT)
    assert seq == 2 and seq % 2 == 0  # even = coherent slot
    assert ts == _TS
    assert fmt == FORMAT_RGBA8

    pixel = _pixels(path)[0, 0]
    # BGR fill → RGB, key → alpha (255 = foreground)
    assert pixel.tolist() == [30, 20, 10, 200]


def test_seq_advances_by_two_per_frame(tmp_path: Path) -> None:
    path = tmp_path / "frame.rgba"
    sink = GodotOutputSink(shm_path=str(path))
    sink.open()
    for _ in range(3):
        sink.send(_frame(), _key())
    sink.close()

    _, _, _, seq, _, _ = _header(path)
    assert seq == 6  # odd mid-write + even publish, per frame


def test_send_before_open_raises(tmp_path: Path) -> None:
    sink = GodotOutputSink(shm_path=str(tmp_path / "never.rgba"))
    with pytest.raises(SinkWriteError, match="before open"):
        sink.send(_frame(), _key())


def test_shape_mismatch_raises(tmp_path: Path) -> None:
    sink = GodotOutputSink(shm_path=str(tmp_path / "frame.rgba"))
    sink.open()

    bad_key = AlphaMask(
        camera_id="cam_a",
        timestamp_us=_TS,
        data=np.zeros((_HEIGHT, _WIDTH + 1), dtype=np.uint8),
    )
    with pytest.raises(SinkWriteError, match="key shape"):
        sink.send(_frame(), bad_key)

    wrong_fill = Frame(
        timestamp_us=_TS,
        camera_id="cam_a",
        width=_WIDTH + 1,
        height=_HEIGHT,
        data=_fill(),
    )
    with pytest.raises(SinkWriteError, match="fill shape"):
        sink.send(wrong_fill, _key())
    sink.close()


def test_missing_pixels_raise(tmp_path: Path) -> None:
    sink = GodotOutputSink(shm_path=str(tmp_path / "frame.rgba"))
    sink.open()
    empty = Frame(
        timestamp_us=_TS,
        camera_id="cam_a",
        width=_WIDTH,
        height=_HEIGHT,
        data=None,
    )
    with pytest.raises(SinkWriteError, match="no pixels"):
        sink.send(empty, _key())
    sink.close()


def test_close_is_idempotent_and_reopen_works(tmp_path: Path) -> None:
    path = tmp_path / "frame.rgba"
    sink = GodotOutputSink(shm_path=str(path))
    sink.open()
    sink.send(_frame(), _key())
    sink.close()
    sink.close()  # second close must not raise

    sink.open()
    sink.send(_frame(), _key())
    sink.close()

    _, _, _, seq, _, _ = _header(path)
    assert seq == 2  # slot rebuilt from scratch after reopen


def test_builder_selects_godot_sink() -> None:
    """`output.mode: "godot"` must wire GodotOutputSink, nothing else."""
    from stageforge.orchestrator.builder import OUTPUT_MODES, build_chain

    assert "godot" in OUTPUT_MODES
    chain = build_chain(
        {
            "mode": "synthetic",
            "camera": {"num_cameras": 1},
            "compositing": {"topic": "military_tech"},
            "output": {"mode": "godot"},
        }
    )
    assert isinstance(chain.sink, GodotOutputSink)
