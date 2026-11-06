# L3 — Segmentation & Alpha

The point of StageForge is to build an **alpha channel without a green
screen**. This layer is where that promise is kept.

## Depth alpha from relative depth (MVP)

`segmentation/depth_alpha.py` turns a monocular `RelativeDepthFrame`
into an `AlphaMask` statistically, because relative depth has no
threshold you could express in metres:

1. Take the `low_pct` / `high_pct` percentiles of the depth buffer
   (defaults 5 / 95) — these bound out-of-range noise instead of
   letting one bright pixel define the whole stretch.
2. Clip the buffer to that window and stretch it linearly to 0…255.
3. Invert (`invert: true` by default) so **low depth = foreground**,
   matching the package-wide convention that near is what gets keyed.
4. Optionally run a morphological close + open with an odd
   `morphology_kernel` to fill holes and drop speckle.

Because the stretch is recomputed per frame, a wide shot and a close-up
key the same way without a per-show calibration.

### Known risks

- **CPU morphology** — a 5 px+ kernel on a 1080p frame can miss the
  30 fps budget; the segmenter logs this warning once and suggests
  `cv2.cuda` or a smaller kernel.
- **Rolling shutter on the 5D** — fast motion skews the raster, so the
  matte and the plate share the distortion (harmless) but any future
  3D solve will have to compensate for it.
- **Percentile drift** — a foreground object filling most of the frame
  pushes the percentiles around; watch the matte in the file sink when
  changing shot size.

### Metric path (pilot)

`segmentation/metric.py` keeps `depth_to_alpha(depth_m, near_m, far_m)`
for the future depth-sensor pilot, where distances really are in metres.
Nothing in the MVP calls it yet — it exists so the ToF/stereo pilot has
a drop-in replacement.

## Two strategies

### Depth-based keying (default, no GPU needed)

Take `DepthMap`, pick a foreground threshold (person depth ± tolerance),
morphologically clean the edges, and emit `AlphaMask`.

- Pros: deterministic, runs on CPU, no training data.
- Cons: struggles with hair and with objects crossing the threshold
  plane; needs a per-show depth calibration.

### AI segmentation (vendor or model)

Hand the RGB frame to a person/matte model — either the vendor's
(Vizrt AI Keyer, Pixotope Reveal) or an on-prem inference runtime.

- Pros: state-of-the-art edges, handles hair and translucent objects.
- Cons: needs GPU, has a fixed inference latency that must fit inside
  the 4-frame budget.

## Contract

`segmentation.Segmenter`:

- **Input** — `Frame` plus, optionally, `DepthMap`.
- **Output** — `AlphaMask` (uint8, same spatial size as the frame).
- **Exceptions** — `SegmentationError` on inference failure; the
  compositor falls back to "no key" and the director is told on-air.

## Edge handling checklist

- [ ] Feather radius configurable per output (SDI key usually wants a
      harder edge than NDI).
- [ ] Post-process pass to remove speckle inside the matte.
- [ ] Hold last good matte for up to 3 frames if inference drops.
- [ ] Emit a confidence value so downstream can log quality.

## Status

| Class | File | Status |
|-------|------|--------|
| `DepthAlphaSegmenter` | `segmentation/depth_alpha.py` | **MVP** — percentile stretch of relative depth |
| `depth_to_alpha` | `segmentation/metric.py` | pilot path, metric depth, not wired |
| `StubSegmenter` | `segmentation/stub.py` | scaffold placeholder |

The AI segmentation strategy (Vizrt AI Keyer / Pixotope Reveal) is
still a stub and is planned for the broadcast-readiness phase.
