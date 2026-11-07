"""Build the correction: least-squares CCM 3x3, optional .cube export.

Decision (ADR-0005): the default artefact is a 3x3 colour correction
matrix — nine coefficients from 24 patch pairs via ``numpy.linalg.lstsq``
(scipy is not a dependency). A 17^3 .cube LUT can be sampled from the
same matrix for tools that insist on one, but shipping it is deferred
to the pilot: 4913 numbers cannot be validated any better than nine
with a single chart shot.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt

__all__ = ["FloatArray", "compute_ccm", "generate_lut_from_patches", "write_ccm", "write_cube"]

FloatArray = npt.NDArray[np.float32] | npt.NDArray[np.float64]


def compute_ccm(measured_srgb: FloatArray, reference_srgb: FloatArray) -> npt.NDArray[np.float32]:
    """Least-squares 3x3 colour matrix with ``out = measured @ ccm``.

    Pure linear model through the origin (nine coefficients, no bias)
    — scale-invariant, so the same matrix serves 0..255 and 0..1 data.
    """
    measured = np.asarray(measured_srgb, dtype=np.float64)
    reference = np.asarray(reference_srgb, dtype=np.float64)
    if measured.ndim != 2 or measured.shape != reference.shape or measured.shape[1] != 3:
        raise ValueError(
            f"expected matching (N, 3) arrays, got {measured.shape} vs {reference.shape}"
        )
    if measured.shape[0] < 3:
        raise ValueError(f"need >= 3 patch pairs for a 3x3 matrix, got {measured.shape[0]}")
    result = np.linalg.lstsq(measured, reference, rcond=None)
    solution = np.asarray(result[0], dtype=np.float64)
    return solution.astype(np.float32)


def generate_lut_from_patches(
    measured_srgb: FloatArray,
    reference_srgb: FloatArray,
    grid_size: int = 17,
) -> npt.NDArray[np.float32]:
    """Sample the CCM over a regular grid -> ``(S, S, S, 3)`` .cube data.

    Layout is ``[blue][green][red]`` so a flat C-order walk reproduces
    the Adobe .cube order (red changes fastest).
    """
    if grid_size < 2:
        raise ValueError(f"grid_size must be >= 2, got {grid_size}")
    ccm = compute_ccm(measured_srgb, reference_srgb)
    axes = np.linspace(0.0, 1.0, grid_size, dtype=np.float64)
    count = grid_size * grid_size
    red = np.repeat(axes, count)  # fastest axis, per .cube spec
    green = np.tile(np.repeat(axes, grid_size), grid_size)
    blue = np.tile(axes, count)
    nodes = np.stack((red, green, blue), axis=-1)
    corrected = np.clip(nodes @ ccm.astype(np.float64), 0.0, 1.0)
    return corrected.reshape(grid_size, grid_size, grid_size, 3).astype(np.float32)


def write_ccm(ccm: FloatArray, path: str | Path) -> None:
    """Persist the matrix as a text ``.ccm``: a comment line + 3 rows."""
    matrix = np.asarray(ccm, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError(f"CCM must be 3x3, got {matrix.shape}")
    rows = [" ".join(f"{value:.8f}" for value in row) for row in matrix]
    _write(path, "# StageForge CCM: out_srgb = in_srgb @ ccm\n" + "\n".join(rows) + "\n")


def write_cube(lut: FloatArray, path: str | Path, title: str = "StageForge CCM cube") -> None:
    """Write an Adobe .cube (3D): header + S^3 ``R G B`` lines, R fastest."""
    grid = np.asarray(lut, dtype=np.float64)
    if grid.ndim != 4 or grid.shape[3] != 3 or len(set(grid.shape[:3])) != 1:
        raise ValueError(f"expected (S, S, S, 3) LUT, got {grid.shape}")
    size = grid.shape[0]
    lines = [
        f'TITLE "{title}"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    lines.extend(f"{red:.6f} {green:.6f} {blue:.6f}" for red, green, blue in grid.reshape(-1, 3))
    _write(path, "\n".join(lines) + "\n")


def _write(path: str | Path, payload: str) -> None:
    """Write text, creating parent folders (profiles dir may be new)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload, encoding="utf-8")
