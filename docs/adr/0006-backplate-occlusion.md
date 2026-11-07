# ADR-0006. Backplate + depth-quad occlusion for the MVP

**Status: Superseded by ADR-0009.**

- **Status:** accepted
- **Date:** 2026-11-07
- **Area:** `reconstruction` (Python), `godot` (render layer)

## Context

The MVP has no metric 3D reconstruction of the studio (ADR-0002: depth
is relative, no depth sensor, no Free-D head). AR assets are therefore
composited as flat quads in front of a video plate, and nothing can
occlude a virtual prop when it should slide *behind* a set piece -
the "Auto-Geometry" promise of the pitch is not delivered.

Shooting a real studio panorama and running full SfM (Meshroom) would
give a metric point cloud, but it is blocked on the customer physically
shooting a panorama set, costs a Meshroom install plus hours of
per-show processing, and is heavier than an MVP occlusion test needs.
The offline depth tool has to ship **before** that decision so the
backplate pipeline is proven end to end.

## Decision

We will:

1. add an **offline panorama path** in `reconstruction/backplate.py`:
   `compute_panorama_depth()` runs the monocular network on an
   equirectangular panorama in `tile_size` tiles (default 1024x1024)
   and stitches a full-resolution **uint8** depth map (0 = nearest,
   255 = farthest); `project_depth_to_sphere()` returns a fibonacci
   lattice of `n_points` (default 100 000) on a unit sphere with its
   equirectangular `(u, v)` lookup;
2. expose it through `scripts/stage_reconstruct.py`, reading
   `calibration/captures/panoramas/` (gitignored, ADR-0005) and writing
   `assets/generated/backplates/<name>_depth.png` + a metadata sidecar
   (also gitignored);
3. consume it in Godot with `godot/backplate_loader.gd` +
   `godot/occlusion.gdshader` + `godot/occlusion_quad.tscn`: a
   billboarded point-cloud sphere samples the depth texture per vertex,
   giving a depth shell that can order virtual props against the set;
4. keep it **deferred, not wired**: the loader is idle unless a
   `*_backplate.json` sidecar is copied into `godot/assets/backplates/`,
   so the studio demo is unchanged until a panorama exists.

## Consequences

### Positive

- Occlusion becomes testable **without** Meshroom or a real shoot: a
  synthetic panorama exercises the whole depth-tile -> sphere -> shader
  path in CI and locally.
- The uint8 depth PNG is a plain `cv2.imwrite` artefact - no new
  dependency, no proprietary format, readable by any tool.
- Python stays the single source of truth (ADR-0004): Godot only reads
  files, it never estimates depth itself.
- The 100k fibonacci lattice needs no sidecar blob for geometry - the
  same closed-form formula runs in Python and GDScript, so the shader
  can recover `(u, v)` from the vertex direction.

### Negative / risks

- **Tile seams are unblended.** Each tile is normalised independently,
  so adjacent tiles can differ by a depth offset at their border. Fine
  for ordering (ADR-0006 goal), wrong for anything metric.
- **Relative depth, not metres.** The uint8 map inherits ADR-0002's
  limitation: it orders surfaces, it cannot tell a prop it is 3 m from
  the lens. Metric backplates wait for a real depth sensor.
- **Offline only.** The panorama must be shot and exported by hand;
  there is no runtime backplate update, and the panorama itself never
  enters the repo (licence + privacy: a panorama shows the real set).
- **Blocked on a physical shoot.** Full value (a panorama of *this*
  studio) needs the customer to shoot one; until then the path is only
  proven on synthetic images.

### Neutral

- Meshroom / SfM import stays a separate, later decision - this ADR
  does not supersede it, it only removes the MVP dependency on it.
- `docs/03-capture.md` stays the capture reference (the panorama is a
  capture artefact); the occlusion quad itself is documented in
  `docs/06-compositing-ar.md`.