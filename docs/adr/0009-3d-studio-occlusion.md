# ADR-0009: 3D Studio Occlusion (Mesh + Cameras from Blender)

**Date:** 2026-11-07
**Status:** Accepted

## Context

ADR-0006 introduced an offline backplate pipeline: an equirectangular panorama
plus a depth map drives a `depth-quad` shader that hides AR elements behind
scene geometry. That solves *depth-of-scene* for a single 2.5D plate, but the
quad is still a flat surface: real studio furniture with volume (desks, columns,
set pieces) cannot occlude AR objects correctly, and the plate cannot be
parallax-shifted when a virtual camera moves.

Level A of the AR roadmap therefore moves occlusion to a true 3D mesh of the
studio: import an offline reconstruction (mesh + camera rig) from Blender into
Godot as an occluder.

## Decision

1. **Offline export, online import.** The user reconstructs the studio offline
   (photogrammetry / Blender modelling), exports a mesh (`glTF`/`GLB`) plus a
   `cameras.json` describing the camera rig, and a Python import script converts
   it into Godot-ready assets under `godot/assets/studio/`.
2. **Dependency surface: `trimesh` + `numpy` only.** Mesh loading, scale
   application and GLB export go through `trimesh`; matrix/quaternion math goes
   through `numpy`. `scipy` and `pygltflib` are explicitly rejected — they are
   not needed for this MVP and would widen the dependency surface without
   benefit. Exposed as the `reconstruction` optional extra in `pyproject.toml`.
3. **Coordinate conversion is a pure axis swap (no handedness flip).**
   Both Blender and Godot are right-handed; only the axis *labels* differ
   (Blender `Z-up` → Godot `Y-up`). World points map as
   `p_godot = T · p_blender` with the orthogonal permutation

   ```text
   T = | 1  0  0  0 |
       | 0  0  1  0 |
       | 0 -1  0  0 |
       | 0  0  0  1 |
   ```

   `T` has determinant `+1` → the transform stays right-handed; `Tᵀ = T⁻¹`.

   A **camera node transform** therefore converts as `M_godot = T · M_blender`
   (left-multiply only). A camera's *local* convention (−Z forward, +Y up) is
   identical in both engines, so its basis maps with `T` applied on the world
   side only. Conjugation `T · M · Tᵀ` is correct only when the node's *local*
   coordinates are re-expressed by `T` as well — true for mesh geometry (the
   glTF exporter bakes `T` into the vertices, and glTF is Y-up by spec), but
   not for cameras. Conjugating a camera rotates its look direction by `T⁻¹`:
   a Blender camera looking straight down would look horizontally in Godot.
   This was caught in pre-flight and verified against Blender's own glTF
   exporter (`export_cameras=True`) as ground truth; the importer's output
   quaternions now match Blender's camera nodes to floating-point precision
   (4/4 test cameras, including a non-unit-scale one through the SVD
   orthonormalization).
4. **Scale is data-driven.** Photogrammetric reconstructions live in an
   arbitrary scene scale. The importer takes `--scale-ref` (two source points
   and their real-world distance in metres) and applies a single uniform
   `apply_scale` to the `trimesh` object, which correctly handles both
   `Trimesh` and `Scene` returns from `trimesh.load()`.
5. **Rotation is extracted orthonormally.** The upper-left 3×3 of the converted
   camera matrix may carry residual scale/shear; the importer re-orthonormalizes
   it before `trimesh.transformations.quaternion_from_matrix`, and reorders
   `[w, x, y, z]` → `[x, y, z, w]` for Godot's `Quaternion(x, y, z, w)`.
6. **Godot side is a loader node.** `godot/studio_3d_loader.gd` (a `Node3D`)
   instantiates the `GLB`, reads `cameras.json`, spawns `Marker3D` per camera
   and ensures a `WorldEnvironment` exists. The imported mesh is marked as an
   occluder candidate; the actual AR-occlusion wiring (CSG/surface-occlusion
   shader) is a follow-up ADR.

## Consequences

- Occlusion in Level A is driven by a *static* 3D mesh of the studio, which
  supports parallax and volume correctly — a strict upgrade over the 2D
  depth-quad of ADR-0006.
- **ADR-0006 is superseded** by this decision for the occlusion path; the
  backplate loader remains in the codebase as a fallback for setups without a
  3D reconstruction.
- AR elements remain 2D sprites (`Sprite3D`) placed in 3D space; their
  occlusion derives from the depth-buffer position of the *sprite plane*, not
  from any intrinsic depth of their own.
- The pipeline requires the operator to have a Blender (or equivalent) scene;
  there is no in-engine reconstruction. Meshroom/SfM ingestion is deferred
  (planned ADR-0010).
- Requires the `reconstruction` extra (`pip install -e ".[reconstruction]"`);
  the core install stays lean.