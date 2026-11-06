# L5 — Output & Delivery

The last layer turns the composited frame into something a vision
mixer can use on air.

## Two delivery paths

### SDI Key/Fill

Two synchronous SDI streams out of a Blackmagic DeckLink card:

- **Fill** — the composited RGB picture.
- **Key** — the alpha as a luma key, aligned sample-for-sample with
  Fill.

The downstream switcher (or Ultimatte) combines them. Both streams
must share the same genlock and the same scan mode (1080i50,
1080p59.94, …). A mismatch is a hard error, not a warning.

### NDI with alpha

One stream carrying RGBA. Easier to set up, higher bandwidth, no
second cable. Good for control rooms, less common for on-air paths.

## Contract

`output.OutputSink`:

- **Input** — composited `Frame` + `AlphaMask`.
- **Output** — nothing (side effect: frames go on the wire); returns
  per-frame delivery stats.
- **Exceptions** — `SinkWriteError` when the device buffer overruns.

## Latency budget (≤ 4 frames total)

| Stage | Budget |
|-------|--------|
| L1 capture → L2 tracking | 1 frame |
| L3 segmentation | 1 frame |
| L4 render + mix | 1 frame |
| L5 output + device buffer | 1 frame |

Prototype [`prototypes/p02-keyfill-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p02-keyfill-mvp/README.md)
measures this end to end.

## Redundancy

Broadcast expects a fallback. Recommended setup: two DeckLink cards,
one "primary" and one "hot spare", both fed from the same pipeline
instance; the output layer keeps the spare's queue primed with the
last good frame.

## Status

`OutputSink` is a stub.
