"""Export a Blender scene to glTF 2.0 (``.glb``) for the StageForge Godot layer.

Asset preparation only — this script never runs in the real-time path
(ADR-0004: Godot renders, Blender prepares).

Usage (headless, no GUI, no MCP needed):

    blender --background scene.blend --python blender/export_for_godot.py -- \\
        --output godot/assets/scene.glb

    blender --background --python blender/export_for_godot.py -- \\
        --input props/rock.blend --output godot/assets/rock.glb

Arguments (everything after ``--``):

    --output  destination .glb path (required)
    --input   .blend to open first (optional — skip when Blender was
              already started with the .blend on the command line)

Export properties:

* ``GLB`` — single binary file, textures embedded, what Godot's glTF
  importer expects under ``godot/assets/``.
* ``export_materials="EXPORT"`` + ``export_image_format="AUTO"`` —
  Principled BSDF materials survive; images keep their **alpha channel**
  (PNG is chosen automatically when the material is translucent).
* Modifiers are applied so Godot sees final geometry; cameras and
  lights are dropped — the Godot scene owns framing and lighting.

Exit code 0 on success; 1 on exporter/verification failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

__all__ = ["main"]

_EXPORT_FAIL = 1


def _parse_args() -> argparse.Namespace:
    """Everything Blender does not consume lives after the ``--`` separator."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(
        description="Export a .blend to .glb for the StageForge Godot layer."
    )
    parser.add_argument(
        "--input", type=Path, default=None, help=".blend to open before exporting"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="destination .glb path"
    )
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args()

    try:
        import bpy
    except ModuleNotFoundError:  # plain `python` instead of `blender`
        print("EXPORT FAIL: run this with `blender --background --python … --`")
        return 2

    if args.input is not None:
        bpy.ops.wm.open_mainfile(filepath=str(args.input.resolve()))

    out: Path = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    result = bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",           # glTF 2.0 binary, textures embedded
        export_apply=True,             # apply modifiers — Godot sees final mesh
        export_materials="EXPORT",     # keep Principled BSDF materials
        export_image_format="AUTO",    # PNG when alpha is present, else JPEG
        export_yup=True,               # glTF convention; Godot importer undoes it
        export_cameras=False,          # the Godot scene owns the camera
        export_lights=False,           # …and the lighting
        export_animations=True,
    )
    if "FINISHED" not in result:
        print(f"EXPORT FAIL: export_scene.gltf returned {tuple(result)}")
        return _EXPORT_FAIL

    if not out.is_file() or out.stat().st_size == 0:
        print(f"EXPORT FAIL: {out} missing or empty after export")
        return _EXPORT_FAIL

    print(f"EXPORT OK: {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
