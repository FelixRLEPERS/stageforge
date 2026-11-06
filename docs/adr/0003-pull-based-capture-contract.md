# 0003. Capture is pull-based: `read()` plus `frames()`

Date: 2026-11-06

## Status

Accepted — refines the `CaptureSource` contract in
`src/stageforge/capture/base.py`.

## Context

The scaffold contract exposed only `open()` / `frames()` / `close()`,
where `frames()` returned a lazy `Iterator[Frame]`. That fits a
producer-style loop but not the MVP orchestrator, which needs to:

- grab **exactly one** frame, run it through L2–L5, then decide whether
  to grab the next one (`max_frames`, latency measurement between
  `read()` and `write()`);
- read **several cameras in lock-step** so the frame ids can be compared
  for drift;
- report *why* a read failed (`SourceUnavailableError` per frame rather
  than a generator that dies somewhere in the middle of a `for` loop).

An iterator hides all three. The implementations therefore grew a
`read()` method, which at first made them violate the contract mypy
enforced — every concrete source had `read()`, the base class did not.

## Decision

1. `CaptureSource` gains an abstract `read() -> Frame`: pull exactly one
   frame or raise `SourceUnavailableError`. `frames()` stays as the
   iterator form (`while open: yield read()`), so existing callers and
   the scaffold stub are unaffected.
2. `MultiCameraSource` keeps `read()` contract-compatible (returns the
   primary camera's frame) and exposes the aligned batch through
   `read_round() -> list[Frame]`. Returning `list[Frame]` from `read()`
   would have broken the Liskov substitution principle, which mypy
   flagged immediately.
3. `StubCaptureSource` implements `read()` by raising the scaffold
   message, so `tests/test_interfaces.py` keeps passing unchanged.

## Consequences

### Positive

- The orchestrator can measure per-frame latency and stop after N
  frames without cancelling a generator mid-iteration.
- Multi-camera drift is observable: `read_round()` returns every
  camera's frame id, and spread above `max_skew` increments `desyncs`.
- mypy `--strict` now type-checks the real code path end to end.

### Negative / risks

- `frames()` and `read()` must be kept in sync by each implementation;
  forgetting one is only caught at runtime.
- A caller that holds a `CaptureSource` and expects the iterator style
  still works, but pull-style callers must use `read()` directly.

### Neutral

- Documented in `docs/03-capture.md` under *Reference implementation
  status*.