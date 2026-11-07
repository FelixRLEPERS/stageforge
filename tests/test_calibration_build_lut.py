"""CCM solver and artefact writers (numpy lstsq — no scipy in the stack)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stageforge.calibration.apply import load_ccm, load_cube
from stageforge.calibration.build_lut import (
    compute_ccm,
    generate_lut_from_patches,
    write_ccm,
    write_cube,
)
from stageforge.calibration.reference import COLORCHECKER_CLASSIC_SRGB


def test_identity_when_measured_matches_reference() -> None:
    reference = COLORCHECKER_CLASSIC_SRGB
    ccm = compute_ccm(reference, reference)
    np.testing.assert_allclose(ccm, np.eye(3), atol=1e-3)


def test_known_red_shift_is_inverted() -> None:
    reference = COLORCHECKER_CLASSIC_SRGB
    measured = reference.copy()
    measured[:, 0] *= 0.9  # camera renders red 10% dark
    ccm = compute_ccm(measured, reference)
    np.testing.assert_allclose(ccm, np.diag([1 / 0.9, 1.0, 1.0]), atol=1e-3)
    # and the round trip lands back on the reference
    np.testing.assert_allclose(measured @ ccm, reference, atol=1e-2)


def test_rejects_too_few_patch_pairs() -> None:
    with pytest.raises(ValueError):
        compute_ccm(COLORCHECKER_CLASSIC_SRGB[:2], COLORCHECKER_CLASSIC_SRGB[:2])
    with pytest.raises(ValueError):
        compute_ccm(COLORCHECKER_CLASSIC_SRGB[:, :2], COLORCHECKER_CLASSIC_SRGB[:, :2])


def test_generate_lut_identity_cube() -> None:
    reference = COLORCHECKER_CLASSIC_SRGB
    cube = generate_lut_from_patches(reference, reference, grid_size=4)
    assert cube.shape == (4, 4, 4, 3)
    # identity matrix: every node maps to itself ([blue][green][red]
    # axes, value axis (red, green, blue) — Adobe .cube line order)
    axes = np.linspace(0.0, 1.0, 4, dtype=np.float32)
    blue, green, red = np.meshgrid(axes, axes, axes, indexing="ij")
    np.testing.assert_allclose(cube, np.stack((red, green, blue), axis=-1), atol=1e-5)


def test_ccm_and_cube_roundtrip(tmp_path: Path) -> None:
    reference = COLORCHECKER_CLASSIC_SRGB
    ccm = compute_ccm(reference, reference)
    ccm_path = tmp_path / "round.ccm"
    write_ccm(ccm, ccm_path)
    np.testing.assert_allclose(load_ccm(ccm_path), ccm, atol=1e-6)

    cube = generate_lut_from_patches(reference, reference, grid_size=5)
    cube_path = tmp_path / "round.cube"
    write_cube(cube, cube_path, title="roundtrip")
    lines = cube_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == 'TITLE "roundtrip"'
    assert lines[1] == "LUT_3D_SIZE 5"
    assert len(lines) == 4 + 5**3  # header + one RGB line per node
    np.testing.assert_allclose(load_cube(cube_path), cube, atol=1e-6)


def test_writers_reject_bad_shapes(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_ccm(np.eye(2), tmp_path / "bad.ccm")
    with pytest.raises(ValueError):
        write_cube(np.zeros((4, 4, 3)), tmp_path / "bad.cube")
