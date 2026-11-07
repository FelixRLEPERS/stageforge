# Configuration

Configuration is YAML, read once at startup. `builder.py` validates
every value it consumes and raises before any device is opened, so a
typo in a config can never reach a camera.

## Files

| File | Purpose |
|------|---------|
| `configs/dev.yaml` | Real rig defaults (Canon 5D IV + 5D II) plus the scaffold contract keys; `--dry-run` runs it with no hardware |
| `configs/prod.example.yaml` | Template for a real studio — copy to `configs/prod.local.yaml` |
| `configs/*.local.yaml` | Machine-specific, gitignored |

Precedence: CLI flags > environment (`STAGEFORGE_*`) > YAML > defaults.

## Schema

### MVP keys (read by `src/stageforge/orchestrator/builder.py`)

```yaml
calibration:
  enabled: false               # off until a profile exists (ADR-0005)
  profile: "calibration/profiles/canon_5d_mk2_50mm_1.8.json"
  mode: "ccm"                  # ccm | cube (cube deferred to the pilot)
  apply_before: "reconstruction"   # "segmentation" accepted but deferred
```

`enabled: false` compiles to an identity function, so an absent or
disabled block is a no-op. When enabled, `profile` must be a
`CameraProfile` JSON with a `lut_path`; the build fails fast (before
any device opens) if it is missing or invalid.

```yaml
mode: monocular                # monocular | synthetic (--dry-run forces synthetic)

camera:
  num_cameras: 2               # how many entries below to activate
  max_skew: 2                  # frame-id spread tolerated before counting a desync
  cameras:
    - name: "5D Mark IV"       # camera_id used in logs and Frame
      source: 0                # cv2.VideoCapture index
      autocrop:
        enabled: true          # false disables detection entirely
        threshold: 10          # mean brightness above which a column/row counts as content
        refresh_interval: 300  # frames between bar re-detections
        target_aspect: "16:9"  # "W:H", a float ratio, or null for "keep as is"
    - name: "5D Mark II (ML)"
      source: 1
      autocrop: { enabled: true, threshold: 10, refresh_interval: 300, target_aspect: "16:9" }
  width: 1920                  # requested capture raster
  height: 1080
  fps: 30
  synthetic:
    pattern: "pillarbox"       # plain | bars | pillarbox (synthetic mode only)

reconstruction:
  monocular:
    device: "auto"             # auto | cuda | cpu
    model_id: "depth-anything/Depth-Anything-V2-Small-hf"
    near_is_high: true         # native model polarity; output is always 0 = near

segmentation:
  depth_alpha:
    low_pct: 5.0               # nearest percentiles → fully keyed (255)
    high_pct: 95.0             # farthest percentiles → fully clear (0)
    morphology_kernel: 3       # odd, or 0/1 to disable
    invert: true               # low depth = foreground

compositing:
  mode: "2d"                   # only 2d exists in the MVP
  topic: "military_tech"       # key into configs/storylink.yaml
  background_shade: 0.55       # brightness the keyed-out background keeps (0..1)

output:
  mode: "file"                 # file | ndi | godot | null
  out_dir: "out"               # file sink: fill_NNNN.png / key_NNNN.png
  ndi_name: "StageForge Preview"

storylink:
  rules: "configs/storylink.yaml"
  strict: false                # true: unmatched cues raise CueMatchError
```

### Scaffold keys (layer contracts, not read by the MVP pipeline)

Every config also carries the six keys describing the abstract
contracts, one per concern:

```yaml
# Scaffold schema: one key per abstract layer contract.
cameras:
  - id: cam_a
    transport: ndi          # sdi | ndi
    source: "STUDIO-A/CAM1"
    frame_rate: 50
    resolution: [1920, 1080]

depth:
  provider: tof             # tof | stereo | sfm | none
  device: "TOF-01"
  max_range_m: 6.0

tracker:
  protocol: freed           # freed | none
  endpoint: "udp://10.0.0.12:5600"
  calibration: configs/cam_a_calib.json

segmenter:
  engine: depth             # depth | ai
  threshold_m: 2.4
  feather_px: 2

compositor:
  engine: godot             # godot | none (ADR-0004: Godot + Blender, no UE5)
  bridge: "direct"          # direct (local render) | ndi | spout
  fallback: pass_through    # fail_air | pass_through

output:
  sink: sdi                 # sdi | ndi | null
  device: 0
  scan_mode: 1080i50
  key_level: 1.0
```

In `configs/dev.yaml` both groups share one `output:` mapping (YAML has
no namespacing) — the field names are disjoint, so
`output.mode` and `output.sink` coexist without ambiguity.

## Validation rules

MVP keys (raised by `builder.py`, before any device is opened):

- `mode` must be `monocular` or `synthetic`.
- `output.mode` must be `file`, `ndi`, `godot` or `null`.
- `camera.num_cameras` is clamped to the number of `camera.cameras`
  entries; with no entries a single default source is created.
- `segmentation.depth_alpha` requires `0 <= low_pct < high_pct <= 100`.
- `camera.synthetic.pattern` must be `plain`, `bars` or `pillarbox`.
- `camera.autocrop.target_aspect` accepts `"W:H"`, a float or `null`;
  an unparsable value logs a warning and falls back to the default.

Scaffold keys:

- `cameras` must be non-empty unless `segmenter.engine` is `none`.
- `output.scan_mode` must match every camera's `frame_rate`.
- `compositor.fallback: fail_air` requires `output.sink != null`.

Violations raise `ValueError` (MVP keys) or `SegmentationError`, with
the offending value in the message, e.g.
`unknown mode 'monolith', expected one of ('monocular', 'synthetic')`.
The scaffold's pydantic validation is planned for the pilot phase and
applies to the scaffold keys above.

## Environment variables

| Variable | Meaning |
|----------|---------|
| `STAGEFORGE_CONFIG` | Path to the YAML file |
| `STAGEFORGE_LOG_LEVEL` | `trace|debug|info|warn|error` |
| `STAGEFORGE_FAKE_INPUT` | Use a synthetic source (tests/CI) |

## Running it

```bash
# Real rig: two USB cameras + Depth Anything V2 (needs the [ml] extra)
python -m stageforge.orchestrator --config configs/dev.yaml --frames 300

# No hardware, no torch, safe anywhere — forces mode=synthetic
python -m stageforge.orchestrator --config configs/dev.yaml --dry-run --frames 3

# Bare invocation reports the scaffold status and exits 1
python -m stageforge.orchestrator
```

Every run ends with a summary line:

```
mode=synthetic total_frames=3 avg_latency_ms=41.2 fps=24.3 desyncs=0
```
