"""Backplate contract - panorama depth tiles + sphere projection.

The depth-model tests skip unless ``[ml]`` is installed (same policy as
``test_reconstruction_monocular.py``); the sphere projection is pure
numpy and always runs, so CI still covers the geometry that Godot
consumes (ADR-0006).
"""

from __future__ import annotations

import numpy as np
import pytest

from stageforge.reconstruction.backplate import (
    compute_panorama_depth,
    project_depth_to_sphere,
)


def _has_ml() -> bool:
    """Both torch and transformers importable (find_spec lies if a dep is missing)."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:
        return False
    return True


requires_ml = pytest.mark.skipif(not _has_ml(), reason="requires [ml] extras")


def test_sphere_points_lie_on_radius() -> None:
    xyz, uv = project_depth_to_sphere(n_points=50_000, radius=2.5, radius_tol=1e-3)
    assert xyz.shape == (50_000, 3)
    assert uv.shape == (50_000, 2)
    norms = np.linalg.norm(xyz, axis=1)
    assert float(np.max(np.abs(norms - 2.5))) <= 1e-3
    # equirectangular coords stay in [0, 1]
    assert float(uv.min()) >= 0.0
    assert float(uv.max()) <= 1.0


def test_sphere_defaults_are_unit_radius_100k() -> None:
    xyz, _ = project_depth_to_sphere()
    assert xyz.shape == (100_000, 3)
    assert float(np.max(np.abs(np.linalg.norm(xyz, axis=1) - 1.0))) <= 1e-3


def test_sphere_uv_covers_both_poles() -> None:
    """v = phi/pi: 0 at +Y pole, 1 at -Y pole, so both extremes appear."""
    _, uv = project_depth_to_sphere(n_points=10_000)
    v = uv[:, 1]
    assert float(v.min()) < 0.05
    assert float(v.max()) > 0.95


def test_sphere_rejects_bad_args() -> None:
    with pytest.raises(ValueError, match="n_points"):
        project_depth_to_sphere(n_points=1)
    with pytest.raises(ValueError, match="radius"):
        project_depth_to_sphere(radius=0.0)


def test_compute_panorama_depth_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="panorama"):
        compute_panorama_depth(np.zeros((4, 4), dtype=np.uint8))
    with pytest.raises(ValueError, match="tile_size"):
        compute_panorama_depth(np.zeros((8, 8, 3), dtype=np.uint8), tile_size=0)


@requires_ml
def test_compute_panorama_depth_tiles_uint8() -> None:
    """A small 2:1 panorama comes back as (H, W) uint8 in [0, 255]."""
    panorama = np.random.default_rng(0).integers(0, 255, (64, 128, 3), dtype=np.uint8)
    depth = compute_panorama_depth(panorama, tile_size=32)
    assert depth.shape == (64, 128)
    assert depth.dtype == np.uint8
    assert int(depth.min()) >= 0
    assert int(depth.max()) <= 255


@requires_ml
def test_compute_panorama_depth_handles_stereo_map() -> None:
    """A flat-colour tile has zero span -> all-zeros, never NaN/255."""
    panorama = np.full((32, 64, 3), 128, dtype=np.uint8)
    depth = compute_panorama_depth(panorama, tile_size=16)
    assert depth.shape == (32, 64)
    assert int(depth.max()) <= 255
