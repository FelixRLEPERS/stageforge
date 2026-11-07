"""Apply the correction to frames: CCM, .cube LUT, grey-card EV.

Everything here is pure numpy/cv2 array maths with an explicit
``(H, W, 3) uint8`` BGR contract, so the tests can exercise it without
a camera. Loaders read the artefacts written by
:mod:`stageforge.calibration.build_lut`.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.calibration.build_lut import FloatArray

__all__ = [
    "apply_ccm_to_frame",
    "apply_cube_lut_to_frame",
    "apply_ev_offset",
    "load_ccm",
    "load_cube",
]


def apply_ccm_to_frame(frame_bgr: npt.NDArray[np.uint8], ccm: FloatArray) -> npt.NDArray[np.uint8]:
    """Mix every pixel through the 3x3 matrix (``out = in @ ccm``).

    Returns a new array; an identity matrix reproduces the input
    bit-for-bit (integer values up to 255 are exact in float32).
    """
    _check_frame(frame_bgr)
    rgb = np.asarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), dtype=np.uint8)
    mixed = rgb.reshape(-1, 3).astype(np.float32) @ np.asarray(ccm, dtype=np.float32)
    np.clip(mixed, 0.0, 255.0, out=mixed)
    converted = cv2.cvtColor(mixed.reshape(rgb.shape).astype(np.uint8), cv2.COLOR_RGB2BGR)
    return np.asarray(converted, dtype=np.uint8)


def apply_cube_lut_to_frame(
    frame_bgr: npt.NDArray[np.uint8], cube_lut: FloatArray
) -> npt.NDArray[np.uint8]:
    """Resample a ``(S, S, S, 3)`` cube (blue, green, red axes) per pixel.

    Trilinear: eight neighbours per pixel, blended along red, then
    green, then blue — the same sampling a broadcast LUT box does.
    """
    _check_frame(frame_bgr)
    cube = np.asarray(cube_lut, dtype=np.float32)
    if cube.ndim != 4 or cube.shape[3] != 3 or len(set(cube.shape[:3])) != 1:
        raise ValueError(f"expected (S, S, S, 3) cube, got {cube.shape}")
    size = cube.shape[0]
    rgb = np.asarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), dtype=np.float32)
    position = rgb * ((size - 1) / 255.0)
    base = np.floor(position)
    low = np.clip(base.astype(np.intp), 0, size - 1)
    high = np.minimum(low + 1, size - 1)
    # per-channel blend weight, broadcast over the three colour components
    fraction = position - base
    tr = fraction[..., 0:1]
    tg = fraction[..., 1:2]
    tb = fraction[..., 2:3]
    r0, g0, b0 = low[..., 0], low[..., 1], low[..., 2]
    r1, g1, b1 = high[..., 0], high[..., 1], high[..., 2]
    c00 = cube[r0, g0, b0] + (cube[r0, g0, b1] - cube[r0, g0, b0]) * tb
    c01 = cube[r0, g1, b0] + (cube[r0, g1, b1] - cube[r0, g1, b0]) * tb
    c10 = cube[r1, g0, b0] + (cube[r1, g0, b1] - cube[r1, g0, b0]) * tb
    c11 = cube[r1, g1, b0] + (cube[r1, g1, b1] - cube[r1, g1, b0]) * tb
    c0 = c00 + (c01 - c00) * tg
    c1 = c10 + (c11 - c10) * tg
    out = c0 + (c1 - c0) * tr
    return np.asarray(np.clip(out, 0.0, 255.0), dtype=np.uint8)


def apply_ev_offset(frame_bgr: npt.NDArray[np.uint8], ev: float) -> npt.NDArray[np.uint8]:
    """Grey-card exposure trim: multiply by ``2**ev``, clip to 0..255.

    ``ev = +1`` is twice as bright, ``ev = -1`` twice as dark;
    ``ev = 0.0`` returns the input unchanged.
    """
    if ev == 0.0:
        return frame_bgr
    scaled = frame_bgr.astype(np.float32) * float(2.0**ev)
    return np.asarray(np.clip(scaled, 0.0, 255.0), dtype=np.uint8)


def load_ccm(path: str | Path) -> npt.NDArray[np.float32]:
    """Read a ``.ccm`` text file: comment line + three rows of floats."""
    raw = np.loadtxt(Path(path), dtype=np.float64, comments="#")
    return np.asarray(raw, dtype=np.float64).reshape(3, 3).astype(np.float32)


def load_cube(path: str | Path) -> npt.NDArray[np.float32]:
    """Read an Adobe ``.cube`` (3D): keywords + ``S^3`` ``R G B`` lines."""
    size = 0
    rows: list[tuple[float, float, float]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keyword = stripped.upper()
        if keyword.startswith("LUT_3D_SIZE"):
            size = int(stripped.split()[-1])
            continue
        if keyword.startswith(("TITLE", "DOMAIN_MIN", "DOMAIN_MAX")):
            continue
        parts = stripped.split()
        if len(parts) == 3:
            rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
    if size < 2 or len(rows) != size**3:
        raise ValueError(f"{path}: expected a {size}^3 cube, got {len(rows)} entries")
    return np.asarray(rows, dtype=np.float32).reshape(size, size, size, 3)


def _check_frame(frame: npt.NDArray[np.uint8]) -> None:
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(f"expected BGR frame (H, W, 3), got shape {frame.shape}")
