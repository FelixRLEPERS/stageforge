"""Dual-camera timing: arrival stamps, per-camera cadence, cross-camera skew.

Two USB capture cards share no genlock, so the rig's real question is
*how far apart* the two frames captured for the same moment actually
arrive. Each index therefore gets its own reader thread — their
``cap.read()`` calls block independently, and one thread would
serialise the two devices and destroy the very skew being measured —
and every delivered frame is stamped with ``time.monotonic()`` on
arrival. Afterwards each stamp of one camera is matched to the nearest
stamp of the other, in both directions; the largest gap is the max
skew. Measurement only: this module never resynchronises anything
(p02 — desync is measured, not fixed).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from stageforge.capture.diag import count_drops

DUAL_SECONDS = 30.0
INDICES = (0, 1)
JOIN_TIMEOUT = 5.0  # a blocked read can outlive the window

__all__ = ["CamTiming", "DualStats", "dual_measure"]


@dataclass(frozen=True)
class CamTiming:
    """Cadence of one camera inside the shared window."""

    label: str
    frames: int
    avg_interval_ms: float
    drops: int


@dataclass(frozen=True)
class DualStats:
    """Both cameras' timing plus the largest nearest-arrival gap."""

    cams: tuple[CamTiming, CamTiming]
    max_skew_ms: float


def _reader(
    index: int,
    stop: threading.Event,
    stamps: list[float],
    opened: list[int],
) -> None:
    """Open *index*, stamp every frame's arrival, release on *stop*."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return
    opened.append(index)
    # same request as capture/source.py UsbCameraSource.open()
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920.0)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080.0)
    cap.set(cv2.CAP_PROP_FPS, 30.0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
    while not stop.is_set():
        try:
            ok, image = cap.read()
        except cv2.error:
            ok, image = False, None
        if not ok or image is None:
            stop.wait(0.01)  # failed read: back off, still interruptible
        elif not stop.is_set():
            stamps.append(time.monotonic())  # frame arrived inside the window
    cap.release()


def _nearest_ms(stamps: list[float], others: list[float]) -> float:
    """Largest |ms| between a stamp and the nearest stamp of *others*."""
    if not stamps or not others:
        return 0.0
    values = np.asarray(stamps, dtype=np.float64)
    ref = np.asarray(others, dtype=np.float64)
    if ref.size == 1:
        return float(np.abs(values - ref[0]).max() * 1000.0)
    index = np.clip(np.searchsorted(ref, values), 1, ref.size - 1)
    delta = np.minimum(np.abs(values - ref[index]), np.abs(values - ref[index - 1]))
    return float(delta.max() * 1000.0)


def _timing(label: str, stamps: list[float]) -> CamTiming:
    """Frames, mean interval (ms) and drop count for one camera."""
    avg_ms = 0.0
    if len(stamps) > 1:
        avg_ms = (stamps[-1] - stamps[0]) / (len(stamps) - 1) * 1000.0
    return CamTiming(
        label=label,
        frames=len(stamps),
        avg_interval_ms=avg_ms,
        drops=count_drops(stamps),
    )


def dual_measure(
    seconds: float = DUAL_SECONDS,
    indices: tuple[int, ...] = INDICES,
) -> tuple[int, DualStats | None]:
    """Read *indices* simultaneously for *seconds*; return ``(opened, stats)``.

    ``stats`` is ``None`` unless **both** cameras delivered at least two
    stamps: one silent camera has no skew to report, and the caller
    turns that into ``only 1 camera found`` instead of a guess. The
    window ends early when every device fails to open, so a box
    without cameras does not sit through the full run.
    """
    stop = threading.Event()
    opened: list[int] = []
    stamps: dict[int, list[float]] = {index: [] for index in indices}
    threads = [
        threading.Thread(target=_reader, args=(index, stop, stamps[index], opened), daemon=True)
        for index in indices
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline and any(t.is_alive() for t in threads):
            stop.wait(0.1)
    finally:
        stop.set()
    for thread in threads:
        thread.join(timeout=JOIN_TIMEOUT)

    timings = tuple(_timing(f"cam{index}", list(stamps[index])) for index in indices)
    if len(timings) == 2 and all(timing.frames >= 2 for timing in timings):
        left, right = list(stamps[indices[0]]), list(stamps[indices[1]])
        skew_ms = max(_nearest_ms(left, right), _nearest_ms(right, left))
        return len(opened), DualStats(cams=(timings[0], timings[1]), max_skew_ms=skew_ms)
    return len(opened), None
