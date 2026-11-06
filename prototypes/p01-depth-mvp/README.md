# P01 — Depth MVP

**Goal.** Prove that we can produce a depth map and a usable alpha
mask of a presenter, live, without a green screen.

## Hypothesis

A single ToF depth sensor, calibrated against one studio camera, is
enough to separate a standing presenter from the set at broadcast
frame rates — no machine-learning model, no chromakey.

## Success criteria

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Depth map + alpha delivered together | **≥ 25 fps sustained for 10 min** |
| 2 | Matte quality on a standing presenter | silhouette usable, no holes in the torso |
| 3 | End-to-end latency (sensor → mask) | ≤ 2 frames |
| 4 | CPU/GPU load | ≤ 40 % of one modern core per camera |

If criterion 1 or 2 fails, the depth-based path is declared unsuitable
for the default segmenter and the AI path (Vizrt / Pixotope) becomes
the MVP baseline.

## Hardware needed

- 1 × ToF / depth camera (global shutter, ≥ 640×480 depth,
  USB3 or GigE), mounted above or beside the studio camera
- 1 × studio camera with a known lens (calibration target: checkerboard
  or ChArUco board)
- Tripod, calibration board, 2–3 m of clear floor
- Dev machine: any machine with USB3 (GPU optional for this prototype)

## Method

1. Calibrate depth ↔ RGB extrinsics once, store as JSON.
2. Record 10 min of a presenter walking, turning and crouching.
3. Threshold depth at a configurable distance; morphological clean-up.
4. Log fps, latency percentiles, and dump 20 sample mask frames.

## Deliverables

- A notebook or small script that replays the recording and prints the
  metrics table.
- A short written verdict: **go / no-go** for depth-based keying.

## Risks

- ToF multipath error near the floor → raise the sensor, tilt it.
- Dark or reflective clothing → check confidence channel.
- Sunlight through studio windows → IR interference; test at show
  time of day.
