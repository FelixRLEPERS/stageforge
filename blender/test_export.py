"""Phase 5 Blender check: cube + alpha → `.glb`, verified for content.

Run (headless, no MCP needed — MCP path documented in `blender/README.md`):

    blender --background --python blender/test_export.py

Builds a cube with a translucent Principled material in memory, reuses
the *real* export path (`export_for_godot.main`) and then reads the
GLB back: header, non-empty file, and the material's alpha survived
into glTF. Exit code 0 on success, 1 on failure (Blender propagates
`sys.exit` codes from background scripts).
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

try:
    import bpy
except ModuleNotFoundError:
    sys.exit("run with: blender --background --python blender/test_export.py")

import bmesh

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "godot" / "assets" / "test_cube.glb"
sys.path.insert(0, str(HERE))


def _build_cube() -> None:
    """One cube, one translucent material; the startup scene is dropped."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    mesh = bpy.data.meshes.new("TestCubeMesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("TestCube", mesh)
    bpy.context.scene.collection.objects.link(obj)

    mat = bpy.data.materials.new("TestCubeMat")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.8, 0.2, 0.2, 1.0)
    bsdf.inputs["Alpha"].default_value = 0.5
    mesh.materials.append(mat)


def _glb_json(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    magic, version, _length = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"bad GLB header: {magic!r} v{version}")
    chunk_len, chunk_type = struct.unpack_from("<II", raw, 12)
    if chunk_type != 0x4E4F534A:  # 'JSON'
        raise ValueError(f"first chunk is not JSON: {chunk_type:#x}")
    return json.loads(raw[20 : 20 + chunk_len].decode("utf-8"))


def main() -> int:
    _build_cube()

    from export_for_godot import main as export_main

    sys.argv = ["blender", "--", "--output", str(OUT)]
    if export_main() != 0:
        print("BLENDER TEST FAIL: export_for_godot returned non-zero")
        return 1
    if not OUT.is_file() or OUT.stat().st_size == 0:
        print(f"BLENDER TEST FAIL: {OUT} missing or empty")
        return 1

    doc = _glb_json(OUT)
    materials = doc.get("materials", [])
    if not materials:
        print("BLENDER TEST FAIL: no materials in GLB")
        return 1

    first = materials[0]
    pbr = first.get("pbrMetallicRoughness", {})
    factor = pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])
    if first.get("alphaMode") != "BLEND" and factor[3] >= 1.0:
        print(f"BLENDER TEST FAIL: alpha lost in export: {first}")
        return 1

    print(
        f"BLENDER TEST PASS: {OUT} ({OUT.stat().st_size} bytes, "
        f"alphaMode={first.get('alphaMode', 'OPAQUE')} factor[3]={factor[3]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
