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
from stageforge.calibration.reference import GREY_CARD_18_SRGB

__all__ = [
    "apply_ccm_to_frame",
    "apply_cube_lut_to_frame",
    "apply_ev_offset",
    "compute_ev_offset_from_grey_card",
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
    """Resample a ``(S, S, S, 3)`` cube (``[blue][green][red]`` axes) per pixel.

    Trilinear: eight neighbours per pixel, blended along red (the
    fastest axis), then green, then blue — the same sampling a broadcast
    LUT box does. Cube values are 0..1 with a ``(red, green, blue)``
    value axis, matching ``write_cube`` / ``load_cube``; the result is
    scaled back to 0..255 and rounded to the nearest level.
    """
    _check_frame(frame_bgr)
    cube = np.asarray(cube_lut, dtype=np.float32)
    if cube.ndim != 4 or cube.shape[3] != 3 or len(set(cube.shape[:3])) != 1:
        raise ValueError(f"expected (S, S, S, 3) cube, got {cube.shape}")
    size = cube.shape[0]
    # frame is BGR; position/weights are in (red, green, blue) to match
    # the cube's value axis, while the cube itself is indexed blue-first
    rgb = np.asarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), dtype=np.float32)
    position = rgb * ((size - 1) / 255.0)
    base = np.floor(position)
    lo = np.clip(base.astype(np.intp), 0, size - 1)
    hi = np.minimum(lo + 1, size - 1)
    weight = position - base  # (H, W, 3) -> red, green, blue fractions
    r_lo, g_lo, b_lo = lo[..., 0], lo[..., 1], lo[..., 2]
    r_hi, g_hi, b_hi = hi[..., 0], hi[..., 1], hi[..., 2]
    fr = weight[..., 0:1]
    fg = weight[..., 1:2]
    fb = weight[..., 2:3]
    # blend the fastest axis (red) first, then green, then blue
    c00 = cube[b_lo, g_lo, r_lo] + (cube[b_lo, g_lo, r_hi] - cube[b_lo, g_lo, r_lo]) * fr
    c01 = cube[b_lo, g_hi, r_lo] + (cube[b_lo, g_hi, r_hi] - cube[b_lo, g_hi, r_lo]) * fr
    c10 = cube[b_hi, g_lo, r_lo] + (cube[b_hi, g_lo, r_hi] - cube[b_hi, g_lo, r_lo]) * fr
    c11 = cube[b_hi, g_hi, r_lo] + (cube[b_hi, g_hi, r_hi] - cube[b_hi, g_hi, r_lo]) * fr
    c0 = c00 + (c01 - c00) * fg
    c1 = c10 + (c11 - c10) * fg
    out = (c0 + (c1 - c0) * fb) * 255.0
    clipped = np.rint(np.clip(out, 0.0, 255.0)).astype(np.uint8)
    return np.asarray(cv2.cvtColor(clipped, cv2.COLOR_RGB2BGR), dtype=np.uint8)


def apply_ev_offset(frame_bgr: npt.NDArray[np.uint8], ev: float) -> npt.NDArray[np.uint8]:
    """Grey-card exposure trim: multiply by ``2**ev``, clip to 0..255.

    ``ev = +1`` is twice as bright, ``ev = -1`` twice as dark;
    ``ev = 0.0`` returns the input unchanged.
    """
    if ev == 0.0:
        return frame_bgr
    scaled = frame_bgr.astype(np.float32) * float(2.0**ev)
    return np.asarray(np.clip(scaled, 0.0, 255.0), dtype=np.uint8)


def compute_ev_offset_from_grey_card(
    image_bgr: npt.NDArray[np.uint8], target_srgb: float = GREY_CARD_18_SRGB
) -> float:
    """EV offset from an 18% grey card: ``log2(target / measured)``.

    The centre half of the frame is assumed to be the card (the CLI
    frames it that way). Returns ``0.0`` for an already-correct card
    and clamps to +/-3 EV; raises ``ValueError`` if the card reads as
    pure black. Extracted from ``scripts/calibrate.py --grey`` so tests
    and a future live mode can share it.
    """
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError(f"expected BGR frame (H, W, 3), got shape {image_bgr.shape}")
    height, width = image_bgr.shape[:2]
    patch = image_bgr[height // 4 : 3 * height // 4, width // 4 : 3 * width // 4]
    level = float(np.asarray(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY), dtype=np.float64).mean())
    if level <= 0:
        raise ValueError("grey card reads as pure black - check the exposure")
    return float(np.clip(np.log2(target_srgb / level), -3.0, 3.0))


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
