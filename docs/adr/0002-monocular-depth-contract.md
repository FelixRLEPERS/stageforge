# 0002. Monocular depth is relative, not metric

Date: 2026-11-06

## Status

Accepted — supersedes the metric-only wording of the `DepthProvider`
contract in `src/stageforge/reconstruction/base.py`.

## Context

The scaffold contract states that a `DepthProvider` returns a
`DepthMap` whose values are **in metres**, because the intended design
was a calibrated depth sensor (ToF/stereo) plus Free-D camera tracking.

The MVP hardware does not have that. The customer rig is two Canon
bodies into two USB capture cards:

- Canon 5D Mark IV over clean HDMI;
- Canon 5D Mark II with Magic Lantern, pillarboxed 1620x1080 inside
  1920x1080.

There is no depth sensor, no genlock and no SDI. The only depth
available on this rig is **monocular depth estimated from the RGB
frame** (Depth Anything V2 Small via `transformers`). A monocular
network recovers *relative* depth: it orders surfaces near-to-far, but
its output has no metric scale without knowing the focal length and a
real-world reference distance, neither of which is available.

Forcing that output into `DepthMap.unit = "m"` would be a lie that
propagates into the alpha threshold (`threshold_m`) and silently
produces wrong keys.

Alternatives considered:

- **Fake metric scale** (assume the presenter stands at 2 m) — brittle,
  breaks whenever the set changes, and hides the real limitation.
- **Retrofit Free-D** — not possible, there is no robotic head.
- **Reject monocular depth for the MVP** — blocks the whole MVP for a
  constraint the alpha layer does not actually have.

## Decision

1. Add `RelativeDepthFrame` to `core/types.py`: float32 buffer in
   `[0, 1]`, normalised so **0 = nearest, 1 = farthest**, carrying the
   `camera_id` and `timestamp_us` of the frame it came from.
2. Widen `DepthProvider.depth_for()` to return
   `DepthMap | RelativeDepthFrame`. Metric `DepthMap` stays valid and
   untouched for the future depth-sensor pilot.
3. Convert to alpha in **layer L3, not L2**: `DepthAlphaSegmenter`
   turns relative depth into an `AlphaMask` with a percentile stretch
   (`low_pct`/`high_pct`) and an optional inversion, so no layer ever
   pretends the values are metres.
4. Keep the polarity explicit. `MonocularDepthProvider(near_is_high=...)`
   records the model's native polarity and normalises to the
   "0 = near" convention, so a model whose output is inverted can be
   corrected in one config line instead of by editing code.
5. Widen `Segmenter.segment()` to accept
   `DepthMap | RelativeDepthFrame | None` — L3 is the layer that must
   understand both, and narrowing it back to `DepthMap` would have made
   the MVP keyer impossible to express against its own contract.

## Consequences

### Positive

- The MVP runs on hardware the customer already owns — no ToF camera,
  no DeckLink, no genlock.
- Layer boundaries stay honest: L2 estimates, L3 interprets.
- The metric path remains a drop-in later; `DepthMap` is unchanged.

### Negative / risks

- **No absolute studio geometry.** Nothing in the MVP reconstructs a
  metric 3D room; the AR placement is 2D and the "Auto-Geometry"
  promise of the pitch is not delivered yet.
- **Thresholds are per-show.** Percentile-based alpha adapts to the
  frame, so a wide shot and a close-up can key differently within the
  same programme.
- **Monocular scale is ill-posed** near the far plane; distant set
  pieces may drift into the foreground matte.

### Neutral

- `docs/04-reconstruction-tracking.md` documents monocular depth as the
  MVP path and the depth sensor + stereo as the pilot phase.