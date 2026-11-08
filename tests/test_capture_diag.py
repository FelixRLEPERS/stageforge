"""Offline parts of the diagnostics: drop counting and camera identity.

``probe_modes``/``measure`` are excluded on purpose — they open real
devices, so they stay in the manual ``scripts/diagnose_camera.py``
sweep. What can run hermetically is the math and the geometry guesses.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from stageforge.capture.diag import (
    MODES,
    VERDICT_5D2,
    VERDICT_5D4,
    count_drops,
    identify,
    is_frozen,
)


def _gradient(width: int, height: int, bars: int = 0) -> npt.NDArray[np.uint8]:
    """Lit 40..200 gradient, optionally flanked by *bars* pure-black columns each side."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    content = np.linspace(40, 200, width - 2 * bars, dtype=np.uint8)
    if bars:
        frame[:, bars : width - bars] = content[None, :, None]
    else:
        frame[:, :] = content[None, :, None]
    return frame


def test_count_drops_on_even_stream_is_zero() -> None:
    """A steady 33 ms stream has no gaps beyond 1.5x its own cadence."""
    stamps = [i * 0.0333 for i in range(60)]
    assert count_drops(stamps) == 0


def test_count_drops_flags_one_stall() -> None:
    """A quarter-second freeze inside a fast stream counts as one drop."""
    stamps = [i * 0.0333 for i in range(10)]
    stamps += [stamps[-1] + 0.25]  # the stall: 7x the cadence
    stamps += [stamps[-1] + i * 0.0333 for i in (1, 2, 3)]
    assert count_drops(stamps) == 1


def test_count_drops_slow_but_steady_reports_zero() -> None:
    """Drops are relative to the stream's own cadence, not to 30 fps."""
    assert count_drops([0.0, 0.5, 1.0, 1.5, 2.0]) == 0


def test_count_drops_needs_three_stamps() -> None:
    """One or two frames carry no cadence at all."""
    assert count_drops([]) == 0
    assert count_drops([1.0]) == 0
    assert count_drops([1.0, 2.0]) == 0


def test_is_frozen_needs_two_frames() -> None:
    """One frame (or none) carries no live/frozen verdict at all."""
    assert is_frozen(None, 0.0) is None
    assert is_frozen(0.0, None) is None


def test_is_frozen_quiet_picture_is_frozen() -> None:
    """Bit-identical frames — the virtual-camera case — are FROZEN."""
    assert is_frozen(0.0, 0.0) is True
    assert is_frozen(0.2, 0.001) is True


def test_is_frozen_either_live_signal_reads_live() -> None:
    """Sensor noise or moving edges each mean LIVE on their own."""
    assert is_frozen(2.5, 0.0) is False  # noise on a locked-off shot
    assert is_frozen(0.1, 0.05) is False  # structure moved in the frame


def test_identify_pillarbox_is_5d2() -> None:
    """1620x1080 of content centred in 1920x1080 is the 5D Mark II."""
    frame = _gradient(1920, 1080, bars=150)
    assert identify(frame) == VERDICT_5D2


def test_identify_clean_raster_is_5d4() -> None:
    """A full-width 1920x1080 picture with no bars is the 5D Mark IV."""
    frame = _gradient(1920, 1080)
    assert identify(frame) == VERDICT_5D4


def test_identify_black_frame_is_not_guessed() -> None:
    """A dead feed reports black instead of being called a 5D IV."""
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    assert identify(frame).startswith("black/static frame")


def test_identify_foreign_geometry_is_reported_as_such() -> None:
    """Anything else is stated as geometry, never guessed at."""
    frame = _gradient(640, 480)
    assert identify(frame) == "unrecognised geometry (640x480, no bars)"


def test_modes_table_starts_with_the_pipeline_request() -> None:
    """The second candidate is exactly what capture/source.py asks for."""
    assert MODES[1][:4] == (1920, 1080, 30.0, "MJPG")
    assert MODES[0][:4] == (0, 0, 0.0, "")
