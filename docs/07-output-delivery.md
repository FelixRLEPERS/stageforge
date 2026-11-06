# L5 — Output & Delivery

The last layer turns the composited frame into something a vision
mixer can use on air.

## MVP: file + NDI

The MVP ships two sinks and deliberately no SDI:

| Sink | File | Behaviour |
|------|------|-----------|
| File | `output/file_sink.py` | Writes `fill_NNNN.png` + `key_NNNN.png` — the cheapest way to *look* at what the pipeline produced, and what CI uses to prove the chain end to end |
| NDI | `output/ndi_sink.py` | Streams RGBA via `ndi-python` (`[ndi]` extra) straight into OBS or a control room |
| Null | `output/null_sink.py` | Counts frames, writes nothing — dry runs and benchmarks |

If `ndi-python` or the NDI runtime is missing, `NDIOutputSink` **degrades
to a counted no-op** instead of raising: it records `reason`, logs it
once, and counts every subsequent frame as dropped. A show must not go
down because a library is absent; inspect `sink.reason` to know whether
you are actually on air.

### SDI Key/Fill — pilot phase

Two synchronous SDI streams out of a Blackmagic DeckLink card:

- **Fill** — the composited RGB picture.
- **Key** — the alpha as a luma key, aligned sample-for-sample with
  Fill.

The downstream switcher (or Ultimatte) combines them. Both streams
must share the same genlock and the same scan mode (1080i50,
1080p59.94, …). A mismatch is a hard error, not a warning.

This requires broadcast cameras with SDI outputs and a capture card the
current rig does not have, so it stays a **pilot-phase** target — the
MVP camera bodies only output HDMI.

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

| Class | File | Status |
|-------|------|--------|
| `FileOutputSink` | `output/file_sink.py` | **MVP** |
| `NDIOutputSink` | `output/ndi_sink.py` | **MVP**, degrades to null if unavailable |
| `NullOutputSink` | `output/null_sink.py` | **MVP** — tests and dry runs |
| `StubOutputSink` | `output/stub.py` | scaffold placeholder; SDI stays here until the pilot |
