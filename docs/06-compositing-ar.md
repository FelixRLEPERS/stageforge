# L4 — Compositing & AR

L4 renders the virtual content and mixes it with the keyed plate.

## Division of labour

| Job | Done by |
|-----|---------|
| Rendering 3D assets, lighting, shadows | Godot 4 (real-time layer in `godot/` — ADR-0004; assets prepped in Blender) |
| Matching the plate camera | `CameraPose` from L2, pushed into Godot as a frustum + transform |
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
- **Exceptions** — `RendererUnavailableError` if the Godot render
  layer is down; policy is configurable (`fail_air` | `pass_through`).

## Latency

Godot render + mix must fit inside the overall 4-frame budget together
with L3 and L5. Practical rule: render *ahead* — the camera pose for
frame N can be predicted from N-1, so the renderer starts before the
plate arrives.

## Status

`Compositor` and `StoryLink` are stubs. Prototype
[`prototypes/p03-story-link-mvp`](https://github.com/stageforge/stageforge/blob/main/prototypes/p03-story-link-mvp/README.md)
proves the cue→asset mapping independently of the render layer.

## Python → Godot: RGBA stream

The bridge between this pipeline and the Godot renderer (ADR-0004) is
one frame slot on disk, written by
[`GodotOutputSink`](../src/stageforge/output/godot_sink.py) and
consumed by [`godot/receiver.gd`](../godot/receiver.gd):

```
L4 Compositor ── Fill (BGR) + AlphaMask ──► GodotOutputSink
                                               │ file-backed mmap,
                                               │ seqlock header
                                               ▼
                          out/godot_frame.rgba   (40 B header + RGBA8)
                                               │ FileAccess
                                               ▼
             receiver.gd → plate texture → Scene3D (keyed plate + AR cube,
             cube over plate) → SubViewport (transparent, 1920x1080)
                                               │
                                               ▼
                                   NDIOutput / Spout → air
```

**File layout** (little-endian): `magic "SGFRM01\n" | width u32 |
height u32 | seq u64 | timestamp_us u64 | format u32 (0 = RGBA8) |
pad 4 B | RGBA8 pixels`. `seq` is a seqlock counter — odd while the
writer is mid-frame, even when the slot is coherent; the receiver
drops odd/torn frames instead of ever showing them.

**Transport choice** (config `output.mode: "godot"`, optional key
`shm_path`, default `out/godot_frame.rgba`; the receiver honours
`STAGEFORGE_GODOT_SHM` to point elsewhere):

| Option | Verdict on this machine |
|---|---|
| `multiprocessing.shared_memory` (anonymous named mapping) | **rejected** — GDScript has no API to open anonymous mappings; the two sides could never meet on one object |
| NDI (`output.mode: "ndi"` → `NDIOutputSink` → NDI in Godot) | **not testable here** — NDI Runtime absent (`HKLM\SOFTWARE\NDI` missing); remains one config switch away once the runtime is installed |
| **file-backed mmap + seqlock** | **chosen** — no daemon, no DLL, no sockets; the system cache makes writer and reader coherent on one machine; Godot reads it with plain `FileAccess` |

To move to NDI later: keep `GodotOutputSink`'s contract and swap the
transport inside it (or select `output.mode: "ndi"`), and on the Godot
side replace `receiver.gd` with the vendored `NDIOutput` node
(`godot/addons/godot-ndi`, wired by `godot/main.gd` — see
`godot/README.md`).

**Measured (2026-11-07, headless):** the 30.6 fps figure is a smoke
run on an *empty* scene (1920x1080, `transparent_bg`). Real scenes
with AR models, textures and lighting need their own measurement at
pilot stage — 30 fps is the design target here, not a benchmark of a
finished studio scene.

## Backplate + occlusion shell (offline, MVP-adjacent)

Flat quads cannot hide a prop behind a set piece, so the render layer
can optionally load a **backplate**: an equirectangular panorama of the
studio plus its monocular depth map, projected onto a point-cloud
sphere (ADR-0006).

```
calibration/captures/panoramas/*.png      (gitignored, shot by hand)
        |
        v  python scripts/stage_reconstruct.py <panorama>
assets/generated/backplates/*_depth.png   uint8, 0 = near .. 255 = far
        |  + *_backplate.json metadata
        v  copy into godot/assets/backplates/  (gitignored)
godot/backplate_loader.gd  ->  occlusion.gdshader  ->  depth shell
```

- `godot/occlusion_quad.tscn` — the standalone scene wiring loader +
  shader, so the shell can be previewed without touching `main.tscn`.
- The shader samples `depth_tex` per vertex using the fibonacci
  `(u, v)` recovered from the sphere direction — no sidecar blob for
  geometry, the same formula runs in Python and GDScript.
- **Idle by design:** `backplate_loader.gd` prints
  `godot backplate: no *_backplate.json ... (loader idle)` and builds
  nothing when no sidecar is present, so the studio demo above is
  byte-for-byte unchanged until a panorama is shot.
