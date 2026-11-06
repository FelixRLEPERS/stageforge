# Architecture

StageForge is an **orchestrator** that chains five layers. Each layer
is an abstract interface (`base.py`) with a stub (`stub.py`), so any
layer can be swapped for a vendor component without touching the rest.

## The five layers

```
 cameras (SDI/NDI)                                   air / graphics
 ─────────────────┬───────────────────────────────────────┬────────
                  ▼                                      │
   L1 Capture ───► raw frames + genlock timestamp        │
                  ▼                                      │
   L2 Reconstruction & Tracking ─► CameraPose, DepthMap  │
                  ▼                                      │
   L3 Segmentation & Alpha ──────► AlphaMask             │
                  ▼                                      │
   L4 Compositing & AR ─────────► composited Fill        │
                  ▼                                      │
   L5 Output ───────────────────► SDI Key/Fill, NDI ─────┘
```

### L1 — Capture

Pulls multi-camera video (SDI via DeckLink, or NDI), stamps every frame
with a genlock/PTP timestamp and forwards it. Interface:
`capture.CaptureSource`.

### L2 — Reconstruction & tracking

Recovers where each camera is (`CameraPose`) and what depth the scene
is at (`DepthMap`), using SfM/ToF point clouds and the Free-D tracking
protocol. Interfaces: `reconstruction.DepthProvider`, `tracking.Tracker`.

### L3 — Segmentation & alpha

Produces `AlphaMask` for the foreground — either an AI keyer
(Vizrt / Pixotope) or a depth-threshold segmenter. Interface:
`segmentation.Segmenter`.

### L4 — Compositing & AR

Renders AR assets in Unreal Engine 5 and mixes them with the masked
plate. Interfaces: `compositing.Compositor`, `storylink.StoryLink`.

### L5 — Output

Delivers Key/Fill over SDI (DeckLink + Ultimatte) or NDI with alpha.
Interface: `output.OutputSink`.

## Cross-cutting concerns

| Concern | Where |
|---------|-------|
| Configuration | `configs/*.yaml`, validated by pydantic |
| Structured logging | `loguru`, one logger per layer |
| Timing / frame identity | `core.types.Frame` carries a monotonic timestamp |
| Lifecycle | `orchestrator.Pipeline` starts, runs and stops layers in order |

## Design rules

1. **Layers never import each other's internals** — only `core.types`.
2. **Everything is a stub until proven otherwise** — no premature
   optimisation in the scaffold.
3. **Latency budget is explicit** — the end-to-end target is ≤ 4 frames
   (see [`prototypes/p02-keyfill-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p02-keyfill-mvp/README.md)).
4. **Decisions are recorded as ADRs** — see
   [adr/README.md](adr/README.md).

## Data contracts

Defined once in `src/stageforge/core/types.py`:

`Frame`, `CameraPose`, `DepthMap`, `AlphaMask`, `ARAsset`,
`RundownCue`.

These are plain dataclasses so that the layer boundaries stay cheap to
serialise and easy to test.
