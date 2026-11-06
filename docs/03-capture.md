# L1 — Capture

Capture is the only layer that touches physical video. Everything
downstream works on `core.types.Frame` and never on a device handle.

## Sources

| Transport | Typical gear | Notes |
|-----------|--------------|-------|
| SDI | Blackmagic DeckLink, SDI-to-NDI bridge | Needs a frame grabber SDK; genlock preferred |
| NDI | Any NDI encoder, software mixer | Runs on plain 1 GbE; discovery via mDNS |

## Contract

`capture.CaptureSource` (see `src/stageforge/capture/base.py`):

- **Input** — a source descriptor from the YAML config (device id,
  codec, expected frame rate).
- **Output** — an iterator of `Frame`, each with a monotonic capture
  timestamp in microseconds.
- **Exceptions** — `SourceUnavailableError` when the device disappears
  mid-show; the orchestrator decides whether to fail over or to keep
  the last good frame.

## Timestamps matter

Layers L2–L4 must agree on *which* frame they are looking at. All
timestamps come from the genlock/PTP clock where available, otherwise
from `time.monotonic_ns()`. Frames that miss the deadline are dropped,
never buffered — broadcast prefers a dropped frame over a late one.

## Failure policy

| Situation | Behaviour |
|-----------|-----------|
| Device lost | Emit an error log, keep last frame for N frames, then raise |
| Frame arriving late | Drop and count in metrics |
| Resolution change | Restart the source, propagate a `Reconfigure` event |

## Reference implementation status

`stub.py` raises
`NotImplementedError("StageForge scaffold — replace in MVP phase")`.
The first real implementation should target NDI, because it needs no
kernel driver and therefore runs on any dev laptop.
