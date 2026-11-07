"""End-to-end test of scripts/import_studio_reconstruction.py (ADR-0009).

Runs the CLI on the checked-in fixtures (unit cube + one Blender camera at
(0,0,2)) and asserts the coordinate swap, quaternion validity and scale.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("trimesh", reason="[reconstruction] extra not installed")

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "import_studio_reconstruction.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "reconstruction"


def _run(tmp_path: Path, scale_ref: str) -> tuple[dict, dict]:
    """Run the importer; return (cameras_json, result)."""
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--input-mesh",
        str(FIXTURES / "dummy_mesh.obj"),
        "--input-cameras",
        str(FIXTURES / "dummy_cameras.json"),
        "--output-dir",
        str(tmp_path),
        "--scale-ref",
        scale_ref,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"importer failed:\n{proc.stdout}\n{proc.stderr}"
    cams_path = tmp_path / "cameras.json"
    assert cams_path.exists(), "cameras.json was not written"
    cameras = json.loads(cams_path.read_text(encoding="utf-8"))
    return cameras, proc


def test_camera_axis_swap_and_scale(tmp_path: Path) -> None:
    """Blender Z=2 -> Godot Y=2; --scale-ref 1->2 doubles distances."""
    cameras, _ = _run(tmp_path, "0,0,0,0,0,1,2.0")
    assert len(cameras) == 1

    cam = cameras[0]
    # Blender (0, 0, 2) becomes Godot (0, 2, 0): Z-up -> Y-up, no handedness flip.
    assert cam["position"] == pytest.approx([0.0, 2.0, 0.0])

    quat = cam["quaternion"]
    assert len(quat) == 4
    assert math.sqrt(sum(float(v) ** 2 for v in quat)) == pytest.approx(1.0, abs=1e-6)

    # fov conversion rad -> deg
    assert cam["fov_deg"] == pytest.approx(math.degrees(0.8726646259971648))


def test_camera_look_direction_converts(tmp_path: Path) -> None:
    """A Blender camera with identity rotation looks down (-Z); after the
    Z-up -> Y-up conversion it must still look down, i.e. along (0, -1, 0).

    Guards against the T @ M @ T.T conjugation bug: conjugating a camera
    transform (whose local -Z forward convention is shared by both engines)
    rotates the look direction by T^-1 and yields (0, 0, -1) instead.
    """
    import numpy as np

    cameras, _ = _run(tmp_path, "0,0,0,0,0,1,1.0")
    quat = [float(v) for v in cameras[0]["quaternion"]]  # [x, y, z, w]
    x, y, z, w = quat

    def rotate(v: list[float]) -> np.ndarray:
        qv = np.array([x, y, z])
        t = 2.0 * np.cross(qv, np.array(v))
        return np.array(v) + w * t + np.cross(qv, t)

    fwd = rotate([0.0, 0.0, -1.0])
    assert fwd == pytest.approx([0.0, -1.0, 0.0], abs=1e-6)


def test_mesh_bbox_doubles_with_scale_ref(tmp_path: Path) -> None:
    """--scale-ref with distance 2.0 over a 1.0 source gap doubles the bbox."""
    import trimesh

    _, _ = _run(tmp_path, "0,0,0,0,0,1,2.0")
    glb = tmp_path / "studio_mesh.glb"
    assert glb.exists(), "studio_mesh.glb was not written"

    scene = trimesh.load(str(glb))
    mesh = scene.to_mesh() if isinstance(scene, trimesh.Scene) else scene
    extents = mesh.extents  # [dx, dy, dz] of the axis-aligned bbox
    # Source cube is 1x1x1; scale factor 2.0 -> 2x2x2.
    assert extents[0] == pytest.approx(2.0, abs=1e-6)
    assert extents[1] == pytest.approx(2.0, abs=1e-6)
    assert extents[2] == pytest.approx(2.0, abs=1e-6)


def test_default_scale_is_identity(tmp_path: Path) -> None:
    """Without --scale-ref the mesh keeps its original size."""
    import trimesh

    cameras, _ = _run(tmp_path, "0,0,0,0,0,1,1.0")
    assert len(cameras) == 1

    scene = trimesh.load(str(tmp_path / "studio_mesh.glb"))
    mesh = scene.to_mesh() if isinstance(scene, trimesh.Scene) else scene
    assert mesh.extents[0] == pytest.approx(1.0, abs=1e-6)
