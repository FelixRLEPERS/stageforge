"""Offline panorama -> depth map -> backplate export for the Godot studio.

Workflow (details in docs/adr/0006-backplate-occlusion.md):

    python scripts/stage_reconstruct.py calibration/captures/panoramas/studio_a.png
    python scripts/stage_reconstruct.py <panorama> --out-dir assets/generated/backplates

Reads an equirectangular panorama from ``calibration/captures/panoramas/``
(gitignored, ADR-0005), computes its monocular depth in tiles, writes a
uint8 depth PNG plus a sidecar JSON (sphere projection metadata) into
``assets/generated/backplates/`` (gitignored). The panorama itself and
the outputs never enter the public repo - only this script ships.

Requires the ``[ml]`` extras (torch + transformers) for the depth model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from stageforge.reconstruction.backplate import (
    DEFAULT_TILE_SIZE,
    compute_panorama_depth,
    project_depth_to_sphere,
)

PANORAMA_DIR = Path("calibration/captures/panoramas")
DEFAULT_OUT_DIR = Path("assets/generated/backplates")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute panorama depth + backplate export")
    parser.add_argument("panorama", type=Path, help="equirectangular panorama image")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"output directory (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=DEFAULT_TILE_SIZE,
        help=f"depth tile edge in pixels (default: {DEFAULT_TILE_SIZE})",
    )
    parser.add_argument(
        "--n-points",
        type=int,
        default=100_000,
        help="sphere lattice samples for the metadata (default: 100000)",
    )
    args = parser.parse_args()

    panorama = cv2.imread(str(args.panorama), cv2.IMREAD_COLOR)
    if panorama is None:
        raise SystemExit(f"cannot read panorama: {args.panorama}")

    depth = compute_panorama_depth(panorama, tile_size=args.tile_size)
    xyz, uv = project_depth_to_sphere(n_points=args.n_points)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.panorama.stem
    depth_path = args.out_dir / f"{stem}_depth.png"
    meta_path = args.out_dir / f"{stem}_backplate.json"

    if not cv2.imwrite(str(depth_path), depth):
        raise SystemExit(f"cannot write depth map: {depth_path}")

    meta = {
        "panorama": str(args.panorama),
        "depth_png": str(depth_path),
        "depth_shape": list(depth.shape),
        "depth_range": [int(depth.min()), int(depth.max())],
        "tile_size": args.tile_size,
        "sphere": {
            "n_points": int(xyz.shape[0]),
            "radius": 1.0,
            "xyz_dtype": str(xyz.dtype),
            "uv_dtype": str(uv.dtype),
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"backplate: depth {depth.shape[1]}x{depth.shape[0]} -> {depth_path}")
    print(f"backplate: metadata {args.n_points} sphere points -> {meta_path}")


if __name__ == "__main__":
    main()
