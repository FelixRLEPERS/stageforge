# Integrations

StageForge is an orchestrator: it does not reimplement vendor
products, it wires them together.

## Standards and partners

| System | Role in StageForge | Interface |
|--------|--------------------|-----------|
| **Free-D** | Camera tracking protocol (pan/tilt/zoom/focus/position) | `tracking.Tracker` |
| **Godot Engine 4** | Real-time AR rendering layer (ADR-0004) | `compositing.Compositor` |
| **Blender** | Offline asset prep → `.glb` for Godot | `blender/export_for_godot.py` |
| **Vizrt AI Keyer** | AI person keying | `segmentation.Segmenter` |
| **Pixotope Reveal** | AI segmentation alternative | `segmentation.Segmenter` |
| **Blackmagic DeckLink** | SDI capture and Key/Fill output | `capture.CaptureSource`, `output.OutputSink` |
| **Ultimatte** | Hardware keyer downstream of Key/Fill | passive, we feed it |
| **NDI** | IP video in and out | `capture.CaptureSource`, `output.OutputSink` |
| **Newsroom computer system** | Supplies `RundownCue` | `storylink.StoryLink` |

## Integration rules

1. **One adapter per vendor.** Vendor SDK quirks stay inside the
   adapter, never leak into `core`.
2. **Every adapter is optional.** Missing hardware must degrade to a
   stub with a clear log line, not a crash at import time.
3. **Protocol details live in the adapter's docstring** — the abstract
   contract in `base.py` stays vendor-neutral.

## Interop notes

- **Genlock**: DeckLink and NDI both need a common time base; PTP
  (IEEE 1588) is the reference if SDI blackburst is unavailable.
- **Colour**: keep everything in Rec.709 for the MVP; HDR is a
  roadmap item.
- **Frame rate**: declare it once in `configs/*.yaml`; all layers read
  the same value.

## Vendor SDK licensing

Several SDKs (DeckLink, NDI) have their own redistribution terms. They
are deliberately **not** vendored into this repository — install them
in the environment via `scripts/bootstrap.*`.
