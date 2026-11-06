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

### Depth sensors (ToF / stereo)

A `DepthProvider` emits `DepthMap`:

- **Input** — a calibrated depth device (ToF camera, stereo pair) or a
  structure-from-motion pass over the studio point cloud.
- **Output** — a float32 depth buffer in metres, aligned to the
  matching `Frame`.
- **Exceptions** — `CalibrationError` if the depth/camera extrinsics
  are missing or stale.

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

Both `DepthProvider` and `Tracker` are stubs. Prototype
[`prototypes/p01-depth-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p01-depth-mvp/README.md)
de-risks the depth path first.
