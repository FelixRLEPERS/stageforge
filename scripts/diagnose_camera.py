"""One-shot camera diagnostics for the 1 fps capture question.

Read-only: enumerates capture indices 0..3 with the same request the
pipeline makes (1920x1080, fps 30, MJPG — ``capture/source.py:87-92``),
times 10 real ``cap.read()`` calls, saves the first good frame to
``out/diag_cam_{i}.png`` for visual inspection and measures the
first-vs-last frame difference (live signal vs frozen picture). USB bus
speed is not readable from OpenCV — check Device Manager / USBView.

Usage::

    python scripts/diagnose_camera.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

INDICES = range(4)
SAMPLES = 10
WIDTH = 1920
HEIGHT = 1080
FPS = 30.0


def _fourcc(value: float) -> str:
    code = int(value)
    raw = bytes((code >> (8 * i)) & 0xFF for i in range(4))
    return "".join(chr(b) if 32 <= b < 127 else f"\\x{b:02x}" for b in raw)


def _props(cap: cv2.VideoCapture) -> tuple[int, int, float, str]:
    return (
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        float(cap.get(cv2.CAP_PROP_FPS)),
        _fourcc(cap.get(cv2.CAP_PROP_FOURCC)),
    )


def diagnose(index: int) -> dict[str, object] | None:
    """Return measurements for *index*; None when the index does not open."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return None
    default = _props(cap)
    # same request as capture/source.py build_capture()
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(WIDTH))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(HEIGHT))
    cap.set(cv2.CAP_PROP_FPS, FPS)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
    negotiated = _props(cap)
    timings: list[float] = []
    first: np.ndarray | None = None
    last: np.ndarray | None = None
    ok_count = 0
    for _ in range(SAMPLES):
        start = perf_counter()
        ok, img = cap.read()
        timings.append((perf_counter() - start) * 1000.0)
        if not ok:
            break
        ok_count += 1
        if first is None:
            first = img
        last = img
    cap.release()
    avg_ms = sum(timings) / len(timings)
    png: str | None = None
    if first is not None:
        Path("out").mkdir(exist_ok=True)
        png = f"out/diag_cam_{index}.png"
        cv2.imwrite(png, first)
    diff: float | None = None
    if first is not None and last is not None and ok_count > 1:
        diff = float(np.mean(np.abs(first.astype(np.int16) - last.astype(np.int16))))
    return {
        "default": default,
        "negotiated": negotiated,
        "ok": ok_count,
        "avg_ms": avg_ms,
        "min_ms": min(timings),
        "max_ms": max(timings),
        "diff": diff,
        "shape": None if first is None else tuple(first.shape),
        "png": png,
    }


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    rows: list[tuple[int, tuple[int, int, float, str], dict[str, object]]] = []
    for index in INDICES:
        result = diagnose(index)
        if result is None:
            print(f"[{index}] not opened (no device / refused)")
            continue
        default = result["default"]
        negotiated = result["negotiated"]
        assert isinstance(default, tuple) and isinstance(negotiated, tuple)
        diff = result["diff"]
        verdict = "n/a (single read)"
        if isinstance(diff, float):
            verdict = f"{diff:.2f} {'-> LIVE' if diff >= 0.5 else '-> FROZEN/static'}"
        print(f"[{index}] opened")
        print(f"    default : {default[0]}x{default[1]} fps={default[2]:.2f} fourcc={default[3]!r}")
        print(
            f"    request : {negotiated[0]}x{negotiated[1]} fps={negotiated[2]:.2f} "
            f"fourcc={negotiated[3]!r}  (pipeline parity, source.py)"
        )
        print(
            f"    reads   : {result['ok']}/{SAMPLES} ok, "
            f"avg {result['avg_ms']:.1f} ms (min {result['min_ms']:.1f} / "
            f"max {result['max_ms']:.1f}) -> {1000.0 / float(result['avg_ms']):.2f} fps"
        )
        print(f"    frame   : {result['shape']} -> {result['png']}")
        print(f"    diff    : first vs last frame: {verdict}")
        print("    usb     : not readable from OpenCV; check Device Manager -> USBView")
        rows.append((index, negotiated, result))

    if not rows:
        print("no capture device opened")
        return
    print()
    print(
        f"{'idx':>3}  {'opened':<6} {'WxH':<10} {'reported_fps':>12} "
        f"{'real_fps':>8} {'fourcc':>6} {'avg_ms':>8} {'min_ms':>8} {'max_ms':>8}"
    )
    for index, negotiated, result in rows:
        avg_ms = float(result["avg_ms"])
        print(
            f"{index:>3}  {'yes':<6} {negotiated[0]}x{negotiated[1]:<6} "
            f"{negotiated[2]:>12.2f} {1000.0 / avg_ms:>8.2f} {negotiated[3]:>6} "
            f"{avg_ms:>8.1f} {float(result['min_ms']):>8.1f} "
            f"{float(result['max_ms']):>8.1f}"
        )


if __name__ == "__main__":
    main()
