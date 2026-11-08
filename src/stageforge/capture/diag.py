"""Camera diagnostics: mode probing, stream measurement, identity hints.

Read-only helpers for ``scripts/diagnose_camera.py``: which candidate
modes a device accepts (``probe_modes``), how fast it really streams
and whether the picture is live or frozen (``measure`` — Canny edges
plus the raw difference, so exposure flicker cannot be mistaken for
motion), and which rig body is likely attached (``identify``) — a
geometry heuristic for this rig: the 5D Mark II pillarboxes 1620x1080
of 3:2 content inside 1920x1080, the 5D Mark IV is clean. USB bus
speed is not readable from OpenCV: check Device Manager."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.capture.crop import detect_bars

# Test-day output contract: these exact strings end up in the report.
VERDICT_5D2 = "5D II detected (pillarbox 1620×1080 in 1920×1080)"  # noqa: RUF001
VERDICT_5D4 = "5D IV detected (clean 1920×1080)"  # noqa: RUF001

# Frozen heuristics: both signals must stay quiet to call a picture frozen.
LIVE_RAW_MIN = 0.5  # mean |delta px|; a live sensor exceeds this
FROZEN_EDGE_MAX = 0.002  # mean |delta Canny| / 255; no structure change
DARK_STD_MAX = 2.0  # below this spread the frame is effectively black

# (width, height, fps, fourcc, label); 0x0 = open with no request.
MODES: tuple[tuple[int, int, float, str, str], ...] = (
    (0, 0, 0.0, "", "default (no request)"),
    (1920, 1080, 30.0, "MJPG", "pipeline request (source.py)"),
    (1920, 1080, 60.0, "MJPG", "1080p60 MJPG"),
    (1280, 720, 30.0, "MJPG", "720p30 MJPG"),
    (640, 480, 30.0, "MJPG", "VGA30 MJPG"),
)

__all__ = ["StreamStats", "count_drops", "identify", "is_frozen", "measure", "probe_modes"]


def _negotiated(cap: cv2.VideoCapture) -> tuple[int, int, float, str]:
    """(width, height, fps, fourcc) the device settled on."""
    code = int(cap.get(cv2.CAP_PROP_FOURCC))
    raw = bytes((code >> (8 * i)) & 0xFF for i in range(4))
    fourcc = "".join(chr(b) if 32 <= b < 127 else f"\\x{b:02x}" for b in raw)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return width, height, float(cap.get(cv2.CAP_PROP_FPS)), fourcc


@dataclass(frozen=True)
class ModeProbe:
    """One candidate mode tried on one capture index."""

    label: str
    negotiated: tuple[int, int, float, str]
    read_ok: bool
    read_ms: float
    error: str


@dataclass(frozen=True)
class StreamStats:
    """One capture index streamed for a fixed window."""

    index: int
    frames: int
    failed: int
    seconds: float
    negotiated: tuple[int, int, float, str]
    measured_fps: float
    drops: int
    raw_diff: float | None
    edge_diff: float | None
    frozen: bool | None
    resolution: tuple[int, int] | None
    sample: str | None
    verdict: str


def is_frozen(raw_diff: float | None, edge_diff: float | None) -> bool | None:
    """True only when pixels *and* edges both stay put; None without two frames."""
    if raw_diff is None or edge_diff is None:
        return None
    return not (raw_diff >= LIVE_RAW_MIN or edge_diff > FROZEN_EDGE_MAX)


def probe_modes(index: int) -> list[ModeProbe]:
    """Try every candidate mode; one frame read each. A read may block for seconds."""
    probes: list[ModeProbe] = []
    for width, height, fps, fourcc, label in MODES:
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            probes.append(ModeProbe(label, (0, 0, 0.0, ""), False, 0.0, "device not opened"))
            continue
        if width:  # 0x0 = keep whatever the device opens with
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
            cap.set(cv2.CAP_PROP_FPS, fps)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*fourcc))
        negotiated = _negotiated(cap)
        started = time.perf_counter()
        read_ok, error = False, ""
        try:
            ok, image = cap.read()
            read_ok = bool(ok and image is not None)
            error = "" if read_ok else "read returned no frame"
        except cv2.error as exc:  # unsupported modes do raise
            error = str(exc).splitlines()[0] if str(exc) else "cv2.error"
        cap.release()
        probes.append(
            ModeProbe(label, negotiated, read_ok, (time.perf_counter() - started) * 1e3, error)
        )
    return probes


def count_drops(stamps: list[float]) -> int:
    """Gaps longer than 1.5x the stream's own cadence (median interval).

    Stalls, not slowness: a steady-but-slow device reports zero drops
    and its low rate shows up in the measured fps instead.
    """
    if len(stamps) < 3:
        return 0
    gaps = np.diff(np.asarray(stamps, dtype=np.float64))
    period = float(np.median(gaps))
    if period <= 0:
        return 0
    return int(np.count_nonzero(gaps > 1.5 * period))


def _edge_diff(first: npt.NDArray[np.uint8], last: npt.NDArray[np.uint8]) -> float:
    """Mean |delta| of the Canny edge maps, normalised to 0..1."""

    def edges(frame: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cast("npt.NDArray[np.uint8]", cv2.Canny(gray, 80, 160))

    delta = np.abs(edges(first).astype(np.int16) - edges(last).astype(np.int16))
    return float(delta.mean()) / 255.0


def identify(frame: npt.NDArray[np.uint8]) -> str:
    """Guess which rig body produced *frame* from its geometry alone."""
    height, width = frame.shape[:2]
    if float(frame.std()) < DARK_STD_MAX:
        return f"black/static frame {width}x{height} (nothing to identify)"
    rect = detect_bars(frame)
    if rect is None:
        if (width, height) == (1920, 1080):
            return VERDICT_5D4
        return f"unrecognised geometry ({width}x{height}, no bars)"
    x1, y1, x2, y2 = rect
    if (width, height) == (1920, 1080) and (y1, y2) == (0, 1080) and abs(x2 - x1 - 1620) <= 60:
        return VERDICT_5D2
    return f"bars found ({x1},{y1})-({x2},{y2}) in {width}x{height}"


def measure(index: int, seconds: float = 5.0, sample_dir: str = "out/diag") -> StreamStats | None:
    """Stream *index* for *seconds* with the pipeline's own request; None if it won't open.

    One blocking read can overrun the window on an unsupported mode,
    so the report carries the real elapsed time.
    """
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return None
    # same request as capture/source.py UsbCameraSource.open()
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920.0)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080.0)
    cap.set(cv2.CAP_PROP_FPS, 30.0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
    negotiated = _negotiated(cap)

    started = time.perf_counter()
    deadline = started + seconds
    stamps: list[float] = []
    first: npt.NDArray[np.uint8] | None = None
    last: npt.NDArray[np.uint8] | None = None
    failed = 0
    while time.perf_counter() < deadline and failed < 200:
        try:
            ok, image = cap.read()
        except cv2.error:
            ok, image = False, None
        if not ok or image is None:
            failed += 1
            continue
        frame = cast("npt.NDArray[np.uint8]", np.asarray(image))
        stamps.append(time.perf_counter())
        if first is None:
            first = frame
        last = frame
    cap.release()

    raw_diff: float | None = None
    edge_diff: float | None = None
    if first is not None and last is not None and len(stamps) > 1 and first.shape == last.shape:
        raw_diff = float(np.mean(np.abs(first.astype(np.int16) - last.astype(np.int16))))
        edge_diff = _edge_diff(first, last)
    frozen = is_frozen(raw_diff, edge_diff)

    sample: str | None = None
    identity = "no frames"
    if first is not None:
        path = Path(sample_dir) / f"cam{index}.png"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            sample = str(path) if cv2.imwrite(str(path), first) else None
        except OSError:
            sample = None
        identity = identify(first)

    span = stamps[-1] - stamps[0] if len(stamps) > 1 else 0.0
    measured_fps = (len(stamps) - 1) / span if span > 0 else 0.0
    return StreamStats(
        index=index,
        frames=len(stamps),
        failed=failed,
        seconds=time.perf_counter() - started,
        negotiated=negotiated,
        measured_fps=measured_fps,
        drops=count_drops(stamps),
        raw_diff=raw_diff,
        edge_diff=edge_diff,
        frozen=frozen,
        resolution=None if first is None else (int(first.shape[1]), int(first.shape[0])),
        sample=sample,
        verdict=identity,
    )
