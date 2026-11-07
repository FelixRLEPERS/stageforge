# L1 — Capture

Capture is the only layer that touches physical video. Everything
downstream works on `core.types.Frame` and never on a device handle.

## Sources

| Transport | Typical gear | Notes |
|-----------|--------------|-------|
| SDI | Blackmagic DeckLink, SDI-to-NDI bridge | Pilot phase; needs a frame grabber SDK, genlock preferred |
| NDI | Any NDI encoder, software mixer | Pilot phase; plain 1 GbE, discovery via mDNS |
| USB (UVC) | 2 × FHD USB capture cards (**MVP**) | Read with `cv2.VideoCapture(index)`, no driver, no genlock |

### MVP rig: Canon 5D Mark IV + 5D Mark II (Magic Lantern)

The customer rig has no SDI and no frame grabber, so both cameras are
ingested over USB:

- **Canon 5D Mark IV** — clean HDMI 1080p, full 1920×1080 raster.
- **Canon 5D Mark II + Magic Lantern** — *Clear Overlays* is switched on,
  which removes the on-screen UI but does **not** change the geometry:
  the body emits **1620×1080 (3:2) inside 1920×1080**, with ~150 px of
  pure-black pillarbox on each side. That is a property of the sensor's
  3:2 aspect being fitted to a 16:9 output, not an overlay.
- Both cameras appear as `cv2.VideoCapture(0)` and `cv2.VideoCapture(1)`.

### Autocrop

`capture/crop.py` finds and removes those bars:

- `detect_pillarbox()` / `detect_letterbox()` average brightness per
  column/row, take the lit region as content, and return `(x1, y1, x2, y2)`
  — or `None`.
- `detect_bars()` intersects the two; `apply_crop()` cuts the rectangle;
  `crop_to_aspect()` centre-crops the result to the target ratio.

The detector is deliberately conservative: it needs at least
`min_content_ratio` (default 0.5) of the raster to be lit, otherwise it
returns `None` and the frame passes through untouched. On the Mark IV
there are no bars, so the detector finds a fully lit frame and returns
`None` — **autocrop is a no-op there by construction**, never a risk.

The rectangle is detected on the raw frame and then **cached** for
`autocrop.refresh_interval` frames (default 300 ≈ 10 s), because a
locked-off studio camera does not change geometry mid-show and searching
every frame costs more than the crop itself. Changes are logged as
`autocrop updated: old -> new`.

### USB synchronisation

Two capture cards on two different host controllers never deliver frames
in lock-step. `MultiCameraSource` reads every camera once per round and
compares frame ids; a spread above `camera.max_skew` (default 2) is
logged as a warning and counted in `desyncs`, which appears in the run
summary. Stale frames are dropped, never delayed — broadcast prefers a
dropped frame to a late one. Plugging the two cards into **different USB
controllers** (not a shared hub) keeps the drift small enough to stay
under the threshold.

## Color calibration

Camera colour is calibrated once per camera + lens pair with a
ColorChecker chart instead of a manual 125-point grid (ADR-0005):

| Artefact | Producer | Consumer |
|---|---|---|
| `.ccm` — 3x3 matrix | `scripts/calibrate.py --build` (24 patches, `numpy.linalg.lstsq`) | `calibration/apply.py` via `calibration.enabled` |
| profile JSON | `save_profile()` (camera, lens, `aperture_used`, EV) | `calibration/step.py` |
| `.cube` 17³ (optional) | `--cube` flag, same matrix sampled | external tools / 10-bit pilot |
| EV offset | `--grey` (18% card) | applied as `frame * 2**EV` before the matrix |

`calibration.enabled: false` (the default) compiles to an identity
function: the pipeline behaves exactly as before. When enabled, the
builder loads the profile once at start-up and the run loop applies
EV + CCM to every frame *before* depth estimation, so Depth Anything
V2 and the segmenter always see corrected colour.

The one-time studio procedure (~30 minutes) lives in
[`calibration/README.md`](../calibration/README.md) — frame a chart,
`--capture`, `--build`, `--test-frame`, then flip `enabled: true`.

MVP limits: the 5D Mark II is 8-bit sRGB (no log), so a linear matrix
is enough for stable depth inference (≈ ΔE 2–3 on mid-tones); the full
17³ `.cube` path and `apply_before: segmentation` are deferred to the
pilot. Generated captures and LUTs stay gitignored.

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

| Class | File | Status |
|-------|------|--------|
| `StubCaptureSource` | `capture/stub.py` | scaffold placeholder |
| `UsbCameraSource` | `capture/source.py` | **MVP** — UVC + cached autocrop |
| `SyntheticCameraSource` | `capture/synthetic.py` | dry runs, tests and CI |
| `MultiCameraSource` | `capture/multi.py` | frame-id alignment + desync counter |

NDI and SDI remain stubs and are planned for the pilot phase
(see [11-roadmap.md](11-roadmap.md)); NDI needs no kernel driver and is
therefore the natural first target for a dev laptop.
