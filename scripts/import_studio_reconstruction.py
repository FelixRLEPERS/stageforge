"""Convert an offline Blender reconstruction (mesh + camera rig) into Godot assets.

Reads a mesh (any format ``trimesh`` understands) plus a ``cameras.json``
produced by the Blender helper snippet, applies a uniform scale derived from a
reference measurement, converts every camera transform from Blender's Z-up to
Godot's Y-up coordinate system, and writes ``studio_mesh.glb`` +
``cameras.json`` into the output directory.

Dependencies: ``trimesh`` + ``numpy`` only (install with the
``reconstruction`` extra).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, cast

import numpy as np
import trimesh

# Blender (Z-up, -Y forward) -> Godot (Y-up, -Z forward). det(T) = +1: pure
# axis permutation, handedness is preserved, so T.T == T^-1 (see ADR-0009).
_AXIS_SWAP = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)


def _fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _parse_scale_ref(raw: str | None) -> float:
    """Return the uniform scale factor implied by ``--scale-ref`` (1.0 if unset)."""
    if not raw:
        return 1.0
    parts = raw.split(",")
    if len(parts) != 7:
        _fail("--scale-ref expects x1,y1,z1,x2,y2,z2,distance_m")
    try:
        x1, y1, z1, x2, y2, z2, distance_m = (float(p) for p in parts)
    except ValueError:
        _fail("--scale-ref values must be numbers")
    scene_len = math.dist((x1, y1, z1), (x2, y2, z2))
    if scene_len <= 0.0:
        _fail("--scale-ref points must be distinct")
    if distance_m <= 0.0:
        _fail("--scale-ref distance_m must be > 0")
    return distance_m / scene_len


def _load_mesh(path: str) -> trimesh.Trimesh | trimesh.Scene:
    if not os.path.isfile(path):
        _fail(f"mesh not found: {path}")
    try:
        loaded = trimesh.load(path)
    except Exception as exc:
        _fail(f"failed to load mesh {path}: {exc}")
    if isinstance(loaded, trimesh.Scene):
        return loaded
    if isinstance(loaded, trimesh.Trimesh):
        return loaded
    _fail(f"unsupported mesh type from {path}: {type(loaded).__name__}")
    return cast("trimesh.Trimesh | trimesh.Scene", loaded)


def _scale_mesh(mesh: trimesh.Trimesh | trimesh.Scene, factor: float) -> None:
    # apply_scale is the idiomatic, safe path: it works on both Trimesh and
    # Scene (scaling every geometry inside the scene graph).
    mesh.apply_scale(float(factor))  # type: ignore[no-untyped-call]


def _export_glb(mesh: trimesh.Trimesh | trimesh.Scene, path: str) -> None:
    try:
        data = mesh.export(file_type="glb")
    except Exception as exc:
        _fail(f"GLB export failed: {exc}")
    if not isinstance(data, bytes):
        _fail("GLB export returned no bytes")
    with open(path, "wb") as fh:
        fh.write(cast(bytes, data))


def _read_cameras(path: str) -> list[dict[str, Any]]:
    if not os.path.isfile(path):
        _fail(f"cameras file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot parse {path}: {exc}")
    if isinstance(raw, dict):
        raw = raw.get("cameras")
    if not isinstance(raw, list):
        _fail("cameras.json must be a list of camera objects")
    items = cast("list[Any]", raw)
    cameras: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            cameras.append(item)
    return cameras


def _camera_matrix(cam: dict[str, Any]) -> np.ndarray:
    """Parse the row-major 16-element Blender matrix into a 4x4 array."""
    name = str(cam.get("name", "camera"))
    matrix_flat = cam.get("matrix")
    if not isinstance(matrix_flat, list) or len(matrix_flat) != 16:
        _fail(f"camera {name!r}: 'matrix' must be a 16-element list")
    items = cast("list[Any]", matrix_flat)
    values: list[float] = []
    for element in items:
        if not isinstance(element, (int, float)):
            _fail(f"camera {name!r}: 'matrix' contains a non-numeric value")
        values.append(float(element))
    return np.array(values, dtype=np.float64).reshape(4, 4)


def _camera_fov_deg(cam: dict[str, Any]) -> float:
    name = str(cam.get("name", "camera"))
    fov_rad = cam.get("fov_rad")
    if not isinstance(fov_rad, float) and not isinstance(fov_rad, int):
        _fail(f"camera {name!r}: 'fov_rad' must be a number in (0, pi)")
    degrees = math.degrees(float(cast(float, fov_rad)))
    if not 0.0 < degrees < 180.0:
        _fail(f"camera {name!r}: 'fov_rad' must be in (0, pi)")
    return degrees


def _orthonormal_rotation(rot: np.ndarray) -> np.ndarray:
    """Re-orthonormalize a (possibly scaled) 3x3 rotation via SVD."""
    u, _, vt = np.linalg.svd(rot)
    ortho = u @ vt
    if np.linalg.det(ortho) < 0:
        u[:, -1] *= -1.0
        ortho = u @ vt
    return ortho


def _convert_camera(cam: dict[str, Any]) -> dict[str, Any]:
    name = str(cam.get("name", "camera"))
    m_blender = _camera_matrix(cam)
    # T @ M @ T.T: T is orthogonal (T.T == T^-1), det(T) = +1 -> no handedness
    # flip, only the axis labels move (Blender Z-up -> Godot Y-up).
    m_godot = _AXIS_SWAP @ m_blender @ _AXIS_SWAP.T
    position = [float(v) for v in m_godot[:3, 3]]

    rot = _orthonormal_rotation(m_godot[:3, :3])
    rot_4x4 = np.eye(4, dtype=np.float64)
    rot_4x4[:3, :3] = rot
    quat_wxyz = trimesh.transformations.quaternion_from_matrix(rot_4x4)  # type: ignore[no-untyped-call]
    quaternion = [
        float(quat_wxyz[1]),
        float(quat_wxyz[2]),
        float(quat_wxyz[3]),
        float(quat_wxyz[0]),
    ]

    return {
        "name": name,
        "position": position,
        "quaternion": quaternion,
        "fov_deg": _camera_fov_deg(cam),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Import a Blender mesh + camera rig into Godot (see ADR-0009)."
    )
    p.add_argument("--input-mesh", required=True, help="mesh file (obj/gltf/glb/ply/...)")
    p.add_argument("--input-cameras", required=True, help="cameras.json from Blender")
    p.add_argument("--output-dir", required=True, help="destination directory")
    p.add_argument(
        "--scale-ref",
        default=None,
        help="x1,y1,z1,x2,y2,z2,distance_m: two source points and their real length",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    factor = _parse_scale_ref(args.scale_ref)
    mesh = _load_mesh(args.input_mesh)
    _scale_mesh(mesh, factor)
    cameras = [_convert_camera(c) for c in _read_cameras(args.input_cameras)]

    os.makedirs(args.output_dir, exist_ok=True)
    mesh_out = os.path.join(args.output_dir, "studio_mesh.glb")
    cams_out = os.path.join(args.output_dir, "cameras.json")
    _export_glb(mesh, mesh_out)
    with open(cams_out, "w", encoding="utf-8") as fh:
        json.dump(cameras, fh, indent=2)

    print(
        f"wrote {mesh_out} (scale={factor:g}, {type(mesh).__name__}) "
        f"and {cams_out} ({len(cameras)} camera(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
