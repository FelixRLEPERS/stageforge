# ADR-0005: ColorChecker → CCM 3×3, manual 125-point grid dropped

- **Status:** accepted
- **Date:** 2026-11-07
- **Area:** `calibration` (Python pipeline)

## Context

Colour and exposure matching was planned as a manual 125-point grid:
about ten hours of expert work per camera + lens + aperture, and it
would have to be repeated every time a lens or lighting package
changes. That cost pushes calibration out of the MVP, which leaves
Depth Anything V2 and the segmenter absorbing whatever colour cast the
sensor delivers — the segmentation milestone already showed how
sensitive they are to input statistics. The studio also has no
physical ColorChecker or grey card yet, and the 5D Mark II shares its
body between two lenses (50 mm f/1.8, 40 mm f/2.8).

## Decision

1. **One ColorChecker Classic shot → one 3×3 colour correction matrix
   (CCM) per profile.** The matrix is a least-squares fit over the 24
   patch pairs (`numpy.linalg.lstsq`, nine coefficients, no bias
   term), written as a `.ccm` text file and applied with
   `frame_rgb @ ccm`.
2. **Profiles are per camera + lens**, stored as plain JSON
   (`calibration/profiles/*.json`) with `aperture_used`, `lut_path`
   and `gray_card_offset_ev`. The aperture is fixed physically on the
   lens and recorded in the profile; MVP ships two profiles for the
   two 50 mm/40 mm optics.
3. **EV offset from an 18% grey card** stays a separate linear step
   (`frame * 2**ev`), applied before the matrix — exposure and colour
   are corrected independently.
4. **The correction runs before reconstruction**, i.e. before depth
   estimation and segmentation, so the networks see corrected colour
   (`calibration.apply_before: "reconstruction"`). Applying before
   segmentation is accepted as a config value but deferred.
5. **The .cube LUT is generated but not the default path.** A 17³
   cube can be sampled from the same CCM for tools that expect
   Adobe .cube, but the pipeline default is `mode: "ccm"` — nine
   numbers are as far as a single chart shot can be validated.
6. **Tests are synthetic.** `generate_colorchecker_image()` renders
   the reference chart, so CI needs no physical chart; a real one is
   only required for a real one-time studio calibration.

## Consequences

- A calibration session drops from ~10 hours of manual grid work to a
  ~30-minute procedure (`scripts/calibrate.py --capture` → `--build`
  → `--test-frame`), and is redone per lens or aperture change.
- A 3×3 matrix has no bias term: black is pinned to black. If a
  camera needs a black-level lift, it must come from the camera
  settings or from a future biased model — not from this CCM.
- Expected accuracy is ΔE ≈ 2–3 in the mid-tones: enough for stable
  Depth Anything V2 input, not enough for a broadcast colourist's
  final grade. The 10-bit pilot can add a measured .cube later.
- Artefacts are machine-local: `calibration/captures/`, `*.cube` and
  `*.ccm` are gitignored; only code and empty profile JSONs ship.
- Godot/NDI are untouched — calibration is Python-only and sits
  upstream of the RGBA stream.