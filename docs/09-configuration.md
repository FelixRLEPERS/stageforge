# Configuration

Configuration is YAML, validated into pydantic models at startup. An
invalid config aborts the process before any device is opened.

## Files

| File | Purpose |
|------|---------|
| `configs/dev.yaml` | Defaults, all layers stubbed, no hardware |
| `configs/prod.example.yaml` | Template for a real studio — copy to `configs/prod.local.yaml` |
| `configs/*.local.yaml` | Machine-specific, gitignored |

Precedence: CLI flags > environment (`STAGEFORGE_*`) > YAML > defaults.

## Schema

Every config has exactly six top-level keys, one per concern:

```yaml
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
  engine: unreal            # unreal | none
  bridge: "aximmetry"       # aximmetry | zerodensity | mosys | direct
  fallback: pass_through    # fail_air | pass_through

output:
  sink: sdi                 # sdi | ndi | null
  device: 0
  scan_mode: 1080i50
  key_level: 1.0
```

## Validation rules

- `cameras` must be non-empty unless `segmenter.engine` is `none`.
- `output.scan_mode` must match every camera's `frame_rate`.
- `compositor.fallback: fail_air` requires `output.sink != null`.

Violations raise a pydantic `ValidationError` with a path, e.g.
`output.scan_mode: expected one of 1080i50, 1080p59.94…`.

## Environment variables

| Variable | Meaning |
|----------|---------|
| `STAGEFORGE_CONFIG` | Path to the YAML file |
| `STAGEFORGE_LOG_LEVEL` | `trace|debug|info|warn|error` |
| `STAGEFORGE_FAKE_INPUT` | Use a synthetic source (tests/CI) |
