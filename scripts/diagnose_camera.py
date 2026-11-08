"""Camera diagnostics CLI: modes, real fps, drops, live/frozen, dual skew.

Read-only sweep over capture indices 0..3. Per index it first probes
the candidate mode table from :mod:`stageforge.capture.diag` (one
frame read per mode — an unsupported mode may block for seconds, which
is exactly the information being collected), then streams the
pipeline's own request (1920x1080, fps 30, MJPG — the same request
``capture/source.py`` makes) for a few seconds and reports the
*measured* frame rate, stalls, the live/frozen verdict, an identity
hint for the two rig bodies and a sample PNG under ``out/diag/``.

``--dual`` swaps the sweep for :mod:`stageforge.capture.diag_sync`:
both cameras read at once on their own threads for 30 s, printing
per-camera cadence and the max nearest-arrival skew between them —
the desync is *measured*, never corrected here (p02).

Usage::

    python scripts/diagnose_camera.py
    python scripts/diagnose_camera.py --seconds 10
    python scripts/diagnose_camera.py --stress     # 30 s window
    python scripts/diagnose_camera.py --dual       # 30 s skew test
"""

from __future__ import annotations

import argparse
import sys

from stageforge.capture.diag import StreamStats, measure, probe_modes
from stageforge.capture.diag_sync import dual_measure

INDICES = range(4)
DEFAULT_SECONDS = 5.0
STRESS_SECONDS = 30.0


def _configure_stdout() -> None:
    """Make stdout tolerant of non-ASCII verdicts on any console."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def _print_modes(index: int) -> None:
    """One line per candidate mode: what the device negotiated."""
    for probe in probe_modes(index):
        if probe.read_ok:
            width, height, fps, fourcc = probe.negotiated
            print(
                f"    mode    : {probe.label:<28} -> {width}x{height} "
                f"fps={fps:.2f} fourcc={fourcc} ({probe.read_ms:.0f} ms)"
            )
        else:
            print(
                f"    mode    : {probe.label:<28} -> FAIL: {probe.error} ({probe.read_ms:.0f} ms)"
            )


def _print_stream(stats: StreamStats) -> None:
    """The behaviour of the pipeline's own request on this device."""
    width, height, fps, fourcc = stats.negotiated
    print(
        f"    request : {width}x{height} fps={fps:.2f} fourcc={fourcc}  (pipeline parity, source.py)"
    )
    print(
        f"    stream  : {stats.seconds:.1f} s, {stats.frames} frames, "
        f"{stats.measured_fps:.2f} fps, {stats.failed} failed reads"
    )
    print(f"    stalls  : {stats.drops} beyond 1.5x the median interval")
    if stats.raw_diff is None or stats.edge_diff is None:
        print("    live    : n/a (needs 2+ frames in the window)")
    else:
        state = "n/a" if stats.frozen is None else ("FROZEN/static" if stats.frozen else "LIVE")
        print(f"    live    : raw={stats.raw_diff:.2f} canny={stats.edge_diff:.3f} -> {state}")
    print(f"    frame   : {stats.resolution or 'none'} -> {stats.sample or 'none'}")
    print(f"    ident   : {stats.verdict}")
    print("    usb     : not readable from OpenCV; check Device Manager -> USBView")


def _print_table(rows: list[StreamStats]) -> None:
    print()
    print(f"{'idx':>3}  {'WxH':<10} {'real_fps':>8} {'drops':>5} {'frozen':>6}  identify")
    for stats in rows:
        frozen = "n/a" if stats.frozen is None else ("yes" if stats.frozen else "no")
        resolution = (
            "-" if stats.resolution is None else f"{stats.resolution[0]}x{stats.resolution[1]}"
        )
        print(
            f"{stats.index:>3}  {resolution:<10} {stats.measured_fps:>8.2f} "
            f"{stats.drops:>5} {frozen:>6}  {stats.verdict}"
        )


def _run_dual(seconds: float) -> int:
    """The two-camera skew test; exact strings are the test-day contract."""
    print(f"[dual] reading cam0+cam1 for {seconds:.0f} s ...")
    opened, stats = dual_measure(seconds)
    if opened == 0:
        print("no cameras found")
        return 1
    if stats is None:  # one camera silent — nothing to compare against
        print("only 1 camera found, dual skipped")
        return 1
    for cam in stats.cams:
        print(
            f"{cam.label}: {cam.frames} frames, "
            f"avg interval {cam.avg_interval_ms:.1f} ms, drops {cam.drops}"
        )
    print(f"max skew: {stats.max_skew_ms:.1f} ms")
    print("recommendation: genlock unavailable, use software sync")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="StageForge camera diagnostics (read-only).")
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="streaming window per camera in seconds (default: 5, 30 with --stress/--dual)",
    )
    parser.add_argument(
        "--stress",
        action="store_true",
        help=f"use a {STRESS_SECONDS:.0f} s window instead of --seconds",
    )
    parser.add_argument(
        "--dual",
        action="store_true",
        help="read both cameras at once and report max arrival skew (default 30 s)",
    )
    args = parser.parse_args(argv)
    _configure_stdout()

    if args.seconds is not None:
        seconds = args.seconds
    elif args.stress or args.dual:
        seconds = STRESS_SECONDS
    else:
        seconds = DEFAULT_SECONDS
    if args.dual:
        return _run_dual(seconds)

    rows: list[StreamStats] = []
    for index in INDICES:
        print(f"[{index}] probing ...")
        stats = measure(index, seconds)
        if stats is None:
            print(f"[{index}] not opened (no device / refused)")
            continue
        print(f"[{index}] opened")
        _print_modes(index)
        _print_stream(stats)
        rows.append(stats)

    if not rows:
        print("no cameras found")
        return 1
    _print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
