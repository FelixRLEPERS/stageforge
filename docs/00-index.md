# StageForge Documentation Index

Welcome. This is the single entry point to every document in the
repository. Read `00-index.md` first, then `02-architecture.md`.

## Quick links

| # | Document | What it answers |
|---|----------|-----------------|
| 00 | [Index](00-index.md) | Where do I start? |
| 01 | [Getting started](01-getting-started.md) | How do I run it locally? |
| 02 | [Architecture](02-architecture.md) | How do the 5 layers fit together? |
| 03 | [Capture](03-capture.md) | How do SDI/NDI frames enter the pipeline? |
| 04 | [Reconstruction & tracking](04-reconstruction-tracking.md) | How is the studio rebuilt in 3D? |
| 05 | [Segmentation & alpha](05-segmentation-alpha.md) | How is the alpha channel produced? |
| 06 | [Compositing & AR](06-compositing-ar.md) | How is AR rendered and mixed? |
| 07 | [Output & delivery](07-output-delivery.md) | How does the frame reach the air? |
| 08 | [Integrations](08-integrations.md) | Which third-party systems are supported? |
| 09 | [Configuration](09-configuration.md) | What does `configs/*.yaml` mean? |
| 10 | [Development](10-development.md) | How do I hack on the code? |
| 11 | [Roadmap](11-roadmap.md) | What is next and when? |

## Reference material

- [Architecture Decision Records](adr/README.md) — why a decision was
  taken, not just what was decided.
- [`CHANGELOG.md`](https://github.com/FelixRLEPERS/stageforge/blob/main/CHANGELOG.md) — what changed between versions.
- [`CONTRIBUTING.md`](https://github.com/FelixRLEPERS/stageforge/blob/main/CONTRIBUTING.md) — workflow and commit rules.
- [`prototypes`](https://github.com/FelixRLEPERS/stageforge/blob/main/prototypes) — throwaway MVP experiments that
  de-risk the roadmap.

## Conventions used in these docs

- Layer numbers `L1..L5` always refer to the five pipeline layers from
  `02-architecture.md`.
- Every interface lives in a `base.py` file; every placeholder
  implementation lives in `stub.py`.
- Timings are expressed in frames at the programme frame rate (default
  1080i50 / 1080p59.94).

## Audience

| If you are… | Read |
|-------------|------|
| A broadcast engineer | 03, 07, 08, `infra/hardware/mvp-bom.md` |
| A developer | 01, 02, 09, 10 |
| A product / editorial person | 06, 11 |
| A security researcher | [`SECURITY.md`](https://github.com/FelixRLEPERS/stageforge/blob/main/SECURITY.md) |
