# L3 — Segmentation & Alpha

The point of StageForge is to build an **alpha channel without a green
screen**. This layer is where that promise is kept.

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

`Segmenter` is a stub; the depth-threshold implementation is the first
MVP item after
[`prototypes/p01-depth-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p01-depth-mvp/README.md).
