# L2 — Reconstruction & Tracking

This layer answers two questions every frame: **where is the camera**
and **how far away is everything in front of it**.

## Two inputs, one geometry

### Point tracking (Free-D)

[Free-D](https://freed-documentation.readthedocs.io/) is a JSON
tracking protocol used by robotic heads and jib encoders. It carries
pan/tilt/zoom/focus plus the head position, which is enough to build a
pinhole model with a zoom-dependent intrinsic matrix.

StageForge consumes Free-D as a `Tracker`:

- **Input** — a UDP/TCP stream of Free-D JSON packets, plus the
  camera's calibration file (intrinsics, lens distortion).
- **Output** — `CameraPose` per frame (4×4 world-from-camera matrix).
- **Exceptions** — `TrackingLostError` when no packet arrives within
  the deadline; the compositor must hold the last pose.

### Monocular depth (MVP)

The MVP has no depth sensor, no genlock and no robotic head, so depth
comes from the RGB frame itself:

- **Model** — `depth-anything/Depth-Anything-V2-Small-hf` through
  `transformers`, loaded lazily on first use
  (`reconstruction/monocular.py`).
- **Output** — a `RelativeDepthFrame`: float32 in `[0, 1]`, **relative,
  not metric** — 0 = nearest, 1 = farthest. The conversion to an alpha
  mask happens one layer down (see
  [05-segmentation-alpha.md](05-segmentation-alpha.md)).
- **Why not metres** — a monocular network recovers ordering but not
  scale without a known focal length and a real-world reference distance.
  Neither exists on this rig, so the contract was widened instead of
  faking a scale. Full reasoning in
  [ADR 0002](adr/0002-monocular-depth-contract.md).
- **Dependencies** — `torch`/`transformers` live in the `[ml]` extra;
  without it the provider raises
  `monocular depth requires [ml] extras: pip install -e .[ml]`.

Set `reconstruction.monocular.near_is_high` if a future checkpoint
emits the opposite polarity; the output is always normalised to
0 = near.

### Depth sensors (ToF / stereo) — pilot phase

A `DepthProvider` can also emit `DepthMap`:

- **Input** — a calibrated depth device (ToF camera, stereo pair) or a
  structure-from-motion pass over the studio point cloud.
- **Output** — a float32 depth buffer in metres, aligned to the
  matching `Frame`.
- **Exceptions** — `CalibrationError` if the depth/camera extrinsics
  are missing or stale.

This path is not wired into the MVP; it is the pilot-phase replacement
for monocular depth once broadcast cameras and a real depth sensor
exist.

### Panorama backplate + depth-quad occlusion (offline, MVP-adjacent)

The studio has no metric 3D reconstruction yet, so virtual props
cannot slide behind set pieces (ADR-0002: no depth sensor, no Free-D).
An **offline** backplate path removes that dependency without Meshroom:

- **Input** — an equirectangular studio panorama from
  `calibration/captures/panoramas/` (gitignored, ADR-0005 captures).
- **`compute_panorama_depth()`** (`reconstruction/backplate.py`) runs
  the monocular network on **1024x1024 tiles** and stitches a
  full-resolution **uint8** depth map (0 = nearest, 255 = farthest).
- **`project_depth_to_sphere()`** returns a fibonacci lattice of
  100 000 points on a unit sphere plus their equirectangular `(u, v)`.
- **Export** — `scripts/stage_reconstruct.py` writes
  `assets/generated/backplates/<name>_depth.png` + metadata sidecar
  (both gitignored). Requires the `[ml]` extras.
- **Consume** — `godot/backplate_loader.gd` +
  `godot/occlusion.gdshader` sample the depth texture per vertex to
  build an occlusion shell. Idle until a sidecar is copied into
  `godot/assets/backplates/`, so the studio demo is unchanged.

Full reasoning (tile seams, relative-not-metric, blocked on a physical
panorama shoot) in [ADR 0006](adr/0006-backplate-occlusion.md).

## Fusion

`Pipeline` pairs `Frame` + `CameraPose` + `DepthMap` by timestamp. A
pairing tolerance of one frame period is configurable; anything
outside it is logged as a sync warning.

## Known hard problems (pre-MVP)

1. **Lens zoom** — zoom is continuous, so intrinsics must be
   interpolated from a calibration curve, not a single matrix.
2. **Occlusion** — the depth sensor sees the presenter's back when they
   turn; the alpha layer needs a fallback (see
   [05-segmentation-alpha.md](05-segmentation-alpha.md)).
3. **Drift** — SfM-only reconstruction drifts over long shows; an
   anchor marker on the studio floor bounds it.

## Status

| Contract | Implementation | Status |
|----------|----------------|--------|
| `DepthProvider` | `MonocularDepthProvider` | **MVP** — Depth Anything V2, relative depth |
| `DepthProvider` | `SyntheticDepthProvider` | dry runs and tests |
| `DepthProvider` | `StubDepthProvider` | scaffold placeholder |
| `Tracker` | `StubTracker` | stub — Free-D is pilot phase |
| (offline) `compute_panorama_depth` | `reconstruction/backplate.py` | **MVP-adjacent** — tiled depth for the occlusion backplate (ADR-0006) |
| (offline) `project_depth_to_sphere` | `reconstruction/backplate.py` | unit-sphere lattice + equirect `(u, v)` |

MVP implementation lives in `src/stageforge/`; the original hypothesis
is kept as documentation in
[`prototypes/p01-depth-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p01-depth-mvp/README.md).
