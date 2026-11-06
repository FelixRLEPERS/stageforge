# Roadmap

StageForge moves in short, hardware-proving milestones. Every milestone
must produce something observable on a real monitor — no milestone is
"finished because the code exists".

## Status legend

`◻ planned` · `◐ in progress` · `✔ done`

## Phase 0 — Scaffold ✔

- [x] Repository, CI, docs skeleton, interfaces and stubs
- [x] ADR process, contribution and security policies

## Phase 1 — Prototypes (de-risk)

| ID | Prototype | Success criterion |
|----|-----------|-------------------|
| P01 | [Depth MVP](https://github.com/stageforge/stageforge/blob/main/prototypes/p01-depth-mvp/README.md) | depth map + alpha at ≥ 25 fps |
| P02 | [Key/Fill MVP](https://github.com/stageforge/stageforge/blob/main/prototypes/p02-keyfill-mvp/README.md) | end-to-end latency ≤ 4 frames |
| P03 | [Story-Link MVP](https://github.com/stageforge/stageforge/blob/main/prototypes/p03-story-link-mvp/README.md) | cue → 3D object mapping from YAML |

## Phase 2 — MVP pipeline

- [ ] `CaptureSource` over NDI with genlock timestamps
- [ ] `Tracker` speaking Free-D from a robotic head
- [ ] `DepthProvider` from a ToF sensor, depth-threshold `Segmenter`
- [ ] `Pipeline.run()` wiring all five layers
- [ ] `OutputSink` to NDI with alpha (SDI follows in Phase 3)

## Phase 3 — Broadcast readiness

- [ ] DeckLink SDI capture + Key/Fill output, measured ≤ 4 frames
- [ ] Redundant output card and fail-over policy
- [ ] AI `Segmenter` (Vizrt AI Keyer or Pixotope Reveal)
- [ ] UE5 bridge through Aximmetry / Zero Density

## Phase 4 — Editorial automation

- [ ] Newsroom feed → `RundownCue` (MOS/ANP or CSV fallback)
- [ ] Story-Link rule editor and dry-run preview
- [ ] Per-show asset libraries

## Phase 5 — Operations

- [ ] Metrics endpoint (dropped frames, key confidence, latency)
- [ ] Show report: what ran, when, with which assets
- [ ] Installers and hardware certification list

## Deliberately out of scope (for now)

- HDR and 4K (design does not preclude it; the budget does)
- Multi-studio federation
- Cloud rendering

## How to influence the order

Open an issue with the `feature_request` template and say which
broadcast problem it unblocks. ADRs for accepted direction land in
[adr/](adr/README.md).
