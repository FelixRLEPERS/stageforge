# L4 — Compositing & AR

L4 renders the virtual content and mixes it with the keyed plate.

## Division of labour

| Job | Done by |
|-----|---------|
| Rendering 3D assets, lighting, shadows | Unreal Engine 5 (via Zero Density / Aximmetry / Mo-Sys bridge) |
| Matching the plate camera | `CameraPose` from L2, pushed into UE as a frustum + transform |
| Deciding *what* to show | `storylink.StoryLink` |
| Final mix (Fill + Key) | `compositing.Compositor` |

## Story-Link

Story-Link maps editorial intent to geometry. It is deliberately
simple in the scaffold: a YAML table of
`cue pattern → asset id → transform`, evaluated against the current
`RundownCue` (topic/title/slug from the newsroom computer system).

Example (`configs/storylink.yaml`):

```yaml
rules:
  - match: { topic: oil }
    asset: barrel_stack_v3
    anchor: stage_left
    animation: rise
  - match: { keyword: "interest rate" }
    asset: rate_chart_live
    anchor: desk_right
```

Matching is first-hit-wins, ordered as written, so a producer can
reason about it without a rule engine.

## Contract

`compositing.Compositor`:

- **Input** — `Frame` (plate), `AlphaMask`, the current AR scene
  description from Story-Link, `CameraPose`.
- **Output** — a composited `Frame` for L5.
- **Exceptions** — `RendererUnavailableError` if the UE bridge is
  down; policy is configurable (`fail_air` | `pass_through`).

## Latency

UE render + mix must fit inside the overall 4-frame budget together
with L3 and L5. Practical rule: render *ahead* — the camera pose for
frame N can be predicted from N-1, so the renderer starts before the
plate arrives.

## Status

`Compositor` and `StoryLink` are stubs. Prototype
[`prototypes/p03-story-link-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p03-story-link-mvp/README.md)
proves the cue→asset mapping independently of Unreal.
