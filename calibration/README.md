# Calibration — one-time, ~30 minutes

Colour and exposure matching for the Python pipeline (ADR-0005).
Replaces the manual 125-point grid (10 hours) with one chart shot:
**ColorChecker 24 patches → CCM 3×3**, **18% grey card → EV offset**.
The correction runs *before* reconstruction and segmentation, so the
networks always see stable colour.

Everything below runs from the repository root. Generated artefacts
(`calibration/captures/`, `*.ccm`, `*.cube`) are gitignored — only code
and empty profile JSONs are committed.

## What you need

| Item | Notes |
|---|---|
| ColorChecker Classic 24 | Real chart (X-Rite / Calibrite) for production numbers. A print-out validates the workflow but paper gamut limits accuracy — fine for bring-up, not for delivery. |
| 18% grey card | Or a neutral paint sample. Used for the EV trim. |
| Fixed camera setup | 5D Mark II on the tripod, lens seated, **aperture dial physically locked** (studio default `f/4.0`), AWB **off** (manual Kelvin, e.g. 5600), native ISO 100, manual shutter. |
| Show lighting | Calibrate under the lights you will broadcast with — colour temperature is part of the measurement. |

## Why one profile per lens

The colour signature belongs to the *lens* too (coatings, transmission),
so MVP ships two profiles and never mixes them:

- `calibration/profiles/canon_5d_mk2_50mm_1.8.json` — primary studio lens
- `calibration/profiles/canon_5d_mk2_40mm_2.8.json` — wide alternate

The CCM is built at a specific aperture (`aperture_used` records the
dial position). Change the aperture → rebuild. A 5D Mark IV would get a
third profile later; nothing else changes.

## Procedure

1. **Frame the chart** — perpendicular to the lens, filling at least a
   third of the frame, no glare or shadows across it.
2. **Shoot it:**

   ```powershell
   python scripts/calibrate.py --capture --camera 0
   ```

   (or save the frame any other way and pass it as `--input`).
3. **Build the matrix:**

   ```powershell
   python scripts/calibrate.py --build --input calibration/captures/raw_TS.png `
       --profile calibration/profiles/canon_5d_mk2_50mm_1.8.json --aperture f/4.0
   ```

   Prints the fit residual — `mean` below ~4 sRGB units is healthy.
   Auto-detect failing? Add `--rect X,Y,W,H` around the chart.
4. **Grey card** (optional EV trim): shoot the card, then

   ```powershell
   python scripts/calibrate.py --grey --input calibration/captures/grey_TS.png `
       --profile calibration/profiles/canon_5d_mk2_50mm_1.8.json
   ```

5. **Check the preview:**

   ```powershell
   python scripts/calibrate.py --test-frame --input calibration/captures/raw_TS.png `
       --profile calibration/profiles/canon_5d_mk2_50mm_1.8.json
   ```

   Neutrals must look neutral; the same chart shot back through the
   correction should land near the reference values.
6. **Switch it on** in `configs/dev.yaml`:

   ```yaml
   calibration:
     enabled: true
   ```

   The pipeline now compiles the profile at build time and applies
   EV + CCM to every frame before depth estimation.

## Limits (MVP, ADR-0005)

- 5D Mark II: 8-bit sRGB, no log curve — a linear 3×3 matrix is enough
  (target ≈ ΔE 2–3 on mid-tones: stable input for Depth Anything V2).
- A full 17³ `.cube` can be exported with `--cube` (same matrix,
  sampled) for external tools; shipping it as the pipeline format is
  deferred to the 10-bit pilot.
- `calibration.apply_before: "segmentation"` is deferred; MVP applies
  the correction before reconstruction.

## Scope

Calibration is Python-only. Godot, NDI and the RGBA stream
(`docs/06`) are untouched — the corrected frames reach the existing
sinks unchanged.
