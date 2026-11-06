# P02 — Key/Fill MVP

**Goal.** Get a composited Fill and Key out of a Blackmagic DeckLink
card and into a vision mixer, and measure the real latency.

## Hypothesis

A software pipeline (segment → composite → output) can deliver
SDI Key/Fill with **≤ 4 frames** of total latency on a single
workstation, leaving headroom for the Unreal Engine render.

## Success criteria

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Key/Fill visible on the switcher, correctly aligned | no visible tearing or offset |
| 2 | End-to-end latency (SDI in → SDI out) | **≤ 4 frames @ 1080i50** |
| 3 | Stability | 30 min without a dropped frame |
| 4 | Scan mode match | in/out identical, genlock locked |

Any reading above 4 frames is a fail even if the picture looks fine —
the budget is what makes the rest of the pipeline possible.

## Hardware needed

- 1 × Blackmagic DeckLink card (e.g. DeckLink Duo 2 or Mini Monitor 4K)
- 1 × SDI source (camera or test-pattern generator with loop-through)
- 1 × Ultimatte or a switcher with a linear/keyer input
- Reference monitor connected to the program output
- Genlock source (blackburst or tri-level), or DeckLink loop-out
- Host: PCIe slot, RTX A4000 or better, ≥ 32 GB RAM

## Method

1. Loop SDI in → out with a trivial pass-through; measure baseline.
2. Insert segmentation, then compositing; re-measure at each step.
3. Use a frame counter burned into the input to read latency off the
   reference monitor, then confirm with a capture card timestamp.
4. Record the per-stage numbers in the latency table of
   `docs/07-output-delivery.md`.

## Deliverables

- Latency table broken down per stage (L1..L5).
- Go / no-go on the 4-frame budget, with the biggest consumer named.

## Risks

- Driver buffering adds frames invisibly → prefer the SDK's
  timestamped API over the OS preview path.
- Ultimatte expects a specific key polarity → verify with a scope.
