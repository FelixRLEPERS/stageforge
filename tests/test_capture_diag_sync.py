"""Skew math behind ``--dual``: nearest-neighbour matching and empty inputs.

``dual_measure`` itself opens two real devices, so that part stays in
the manual sweep; what runs here is the maths it is built from.
"""

from __future__ import annotations

import time

import numpy as np
import numpy.typing as npt
import pytest

from stageforge.capture import diag_sync
from stageforge.capture.diag_sync import _nearest_ms, _timing, dual_measure

TOL = 1e-9


class _FakeCapture:
    """Stand-in device: opens instantly, delivers a frame every 5 ms."""

    def __init__(self, index: int) -> None:
        self.index = index

    def isOpened(self) -> bool:  # noqa: N802 - must match the cv2 API name
        return True

    def set(self, prop: int, value: float) -> bool:
        return True

    def read(self) -> tuple[bool, npt.NDArray[np.uint8] | None]:
        time.sleep(0.005)
        return True, np.zeros((8, 8, 3), dtype=np.uint8)

    def release(self) -> None:
        return None


def test_skew_zero_for_identical_stamps() -> None:
    """Two cameras stamping in lockstep report no skew."""
    stamps = [0.0, 0.1, 0.2, 0.3]
    assert _nearest_ms(stamps, stamps) == 0.0


def test_skew_reports_a_constant_offset() -> None:
    """A constant 50 ms lead reads as 50 ms, never as zero."""
    left = [0.0, 0.1, 0.2]
    right = [0.05, 0.15, 0.25]
    assert abs(_nearest_ms(left, right) - 50.0) < TOL
    assert abs(_nearest_ms(right, left) - 50.0) < TOL


def test_skew_matches_the_nearest_neighbour() -> None:
    """Each stamp pairs with its closest partner, not with index 0."""
    left = [0.0, 0.2]
    right = [0.05, 0.25]
    assert abs(_nearest_ms(left, right) - 50.0) < TOL
    assert abs(_nearest_ms(right, left) - 50.0) < TOL


def test_skew_is_measured_in_both_directions() -> None:
    """An extra frame on one side only shows up run the other way round."""
    left = [0.0, 1.0]
    right = [0.0, 0.5, 1.0]
    assert _nearest_ms(left, right) == 0.0  # every left stamp has an exact match
    assert abs(_nearest_ms(right, left) - 500.0) < TOL  # 0.5 matches 0.0 or 1.0


def test_skew_tolerates_one_or_no_partner_stamps() -> None:
    """One partner (or none) still yields a defined number."""
    assert abs(_nearest_ms([0.0, 1.0], [5.0]) - 5000.0) < TOL
    assert _nearest_ms([], [1.0]) == 0.0
    assert _nearest_ms([1.0], []) == 0.0


def test_dual_measure_without_indices_returns_nothing() -> None:
    """No devices asked for: no wait, nothing opened, no stats."""
    opened, stats = dual_measure(seconds=0.05, indices=())
    assert opened == 0
    assert stats is None


def test_timing_reports_cadence_and_drops() -> None:
    """Mean interval comes from first/last stamp; a stall shows up as a drop."""
    steady = [i * 0.033 for i in range(6)]
    timing = _timing("cam0", steady)
    assert timing.frames == 6
    assert abs(timing.avg_interval_ms - 33.0) < 0.1
    assert timing.drops == 0
    assert _timing("cam0", [*steady, steady[-1] + 0.3]).drops == 1


def test_dual_measure_assembles_stats_from_two_live_readers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two delivering devices open, stream and produce a skew."""
    monkeypatch.setattr(diag_sync.cv2, "VideoCapture", _FakeCapture)
    opened, stats = dual_measure(seconds=0.3)
    assert opened == 2
    assert stats is not None
    assert stats.cams[0].label == "cam0"
    assert stats.cams[1].label == "cam1"
    for cam in stats.cams:
        assert cam.frames >= 2
        assert cam.avg_interval_ms > 0.0
    assert stats.max_skew_ms >= 0.0
