# P03 — Story-Link MVP

**Goal.** Prove the mapping *"rundown topic → 3D object"* without
touching Unreal Engine, tracking or keying.

## Hypothesis

A producer can describe the whole AR plan for a show as an ordered
YAML rule table, and a plain matcher can turn a `RundownCue` into a
stable asset selection — no rule engine, no ML.

## Success criteria

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Cue → asset resolution | ≥ 95 % of cues in a real rundown match a rule |
| 2 | Determinism | same cue always yields the same assets |
| 3 | Authoring effort | a producer edits YAML without help after a 10 min briefing |
| 4 | Evaluation speed | < 1 ms per cue (it runs on the show clock) |

## Hardware needed

None. This prototype is pure software and runs on a laptop.

- A sample rundown export (CSV or JSON) from the newsroom system —
  or a hand-written one with ~40 cues.
- `configs/storylink.yaml` as the rule file.

## Method

1. Define the rule schema:
   `match: {topic, keyword, asset, anchor, animation}`.
2. Load the sample rundown, evaluate every cue, dump a table
   `cue → matched rule → assets`.
3. Manually review misses and refine rules until ≥ 95 %.
4. Measure evaluation time and check determinism (run 1000×).

## Deliverables

- `configs/storylink.yaml` with the rules that reached 95 %.
- A report of the unmatched cues and *why* they missed — this is the
  real output of the prototype, because it tells us what the schema is
  missing (e.g. guest segments, breaking news).

## Risks

- Free-text topics are unstable → prefer stable slugs from the NRCS,
  use keywords only as a fallback.
- Overfitting to one show's vocabulary → validate against a second
  rundown from a different programme.
