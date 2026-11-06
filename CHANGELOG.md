# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MVP implementation in `src/stageforge/`**, replacing the stubs while
  keeping every existing interface and test intact:
  - `capture`: `UsbCameraSource` (UVC + cached pillarbox autocrop),
    `SyntheticCameraSource` (hardware-free dry runs), `MultiCameraSource`
    (frame-id alignment + desync counter), `crop.py` bar detection.
  - `reconstruction`: `MonocularDepthProvider` (Depth Anything V2 Small
    via `transformers`, relative depth in `[0, 1]`),
    `SyntheticDepthProvider` radial ramp.
  - `segmentation`: `DepthAlphaSegmenter` (percentile stretch + optional
    morphology), `metric.py` for the future depth-sensor pilot.
  - `compositing`: `Simple2DCompositor` + `assets.py` loader/placeholders
    (no Unreal bridge required).
  - `output`: `FileOutputSink`, `NDIOutputSink` (degrades to a counted
    no-op when `ndi-python` is absent), `NullOutputSink`.
  - `storylink`: `YamlStoryLink` resolving `configs/storylink.yaml`.
  - `orchestrator`: `builder.py` layer factory, `StageForgePipeline`
    with per-frame latency and run summary, `--frames` / `--dry-run`
    CLI flags. The scaffold `Pipeline` class is kept untouched so
    `tests/test_pipeline.py` still passes.
- Optional extras in `pyproject.toml`: `ml` (torch, torchvision,
  transformers, timm) and `ndi` (ndi-python).
- ADR 0002 (`monocular-depth-contract`) and ADR 0003
  (`pull-based-capture-contract`), both indexed in `docs/adr/README.md`
  and `mkdocs.yml`.
- Tests: `test_capture_autocrop`, `test_reconstruction_monocular`
  (skips without the `[ml]` extra), `test_segmentation_depth_alpha`,
  `test_pipeline_e2e_synthetic`.
- `stageforge.core.log` — prefers `loguru`, falls back to stdlib
  `logging`, so the package imports in a bare environment.
- `RelativeDepthFrame` in `core/types.py` and `SyntheticDepthProvider`
  in `reconstruction/synthetic.py`.

### Changed

- `CaptureSource` contract: added abstract `read()`; `frames()` remains
  the iterator form (ADR 0003).
- `DepthProvider.depth_for()` now returns `DepthMap | RelativeDepthFrame`
  (ADR 0002).
- `Segmenter.segment()` accepts `DepthMap | RelativeDepthFrame | None`
  so the alpha layer can consume monocular depth.
- `configs/dev.yaml` extended with the MVP keys (`mode`, `camera`,
  `reconstruction`, `segmentation`, `compositing`, `output.mode`,
  `storylink`); the original scaffold keys are retained below a
  separator for reference.
- `docs/03-capture.md`, `04-reconstruction-tracking.md`,
  `05-segmentation-alpha.md`, `07-output-delivery.md`,
  `11-roadmap.md`, `prototypes/p01-depth-mvp/README.md` updated to the
  real rig (Canon 5D IV + 5D II with Magic Lantern, two USB FHD cards,
  monocular depth); `docs/09-configuration.md` now documents the full
  MVP schema.
- `mypy` overrides added for the optional extras (`torch`,
  `transformers`, `timm`, `NDIlib`) and `loguru`, all of which may be
  absent from CI.

### Decisions taken while scaffolding (MVP)

- **MVP keys mirror the plan's schema instead of reusing the scaffold
  keys.** The plan specified top-level `segmentation:` and
  `compositing:`, while the scaffold already had `segmenter:` and
  `compositor:` for the abstract contracts. Both are kept: the MVP keys
  are read by `builder.py`, the scaffold keys document the layer
  contracts and are marked as such in the file and in
  `docs/09-configuration.md`. Folding them together would have silently
  renamed the specified schema.
- **`Pipeline` (scaffold) and `StageForgePipeline` (MVP) coexist.**
  Rewriting `Pipeline.run()` to do real work would have broken
  `tests/test_pipeline.py`, which the plan forbids; the plan itself
  allows adding a `StageForgePipeline` class instead.
- **`MultiCameraSource.read()` returns a single `Frame`.** The plan
  asked for `list[Frame]`, which would violate the `CaptureSource`
  contract mypy enforces; the aligned batch is `read_round()`.
- **`assets_for_topic(topic)` added next to `assets_for(cue)`.** Same
  reason: overriding the base signature with a different parameter type
  would break the `StoryLink` contract; the cue-based API stays intact.
- **Detector polarity** — `depth_rel` is normalised so 0 = near,
  1 = far (`near_is_high: true` records Depth Anything's native
  polarity and flips it), because `DepthAlphaSegmenter` inverts on that
  assumption.
- **`--dry-run` with no config** falls back to
  `mode=synthetic, output.mode=null` so the flag works on a bare clone.

- Initial repository scaffold (see `[0.1.0]`).

## [0.1.0] - 2026-11-06

### Added

- Initial repository scaffold: five-layer package layout
  (`capture`, `reconstruction`, `tracking`, `segmentation`,
  `compositing`, `storylink`, `output`, `orchestrator`), shared data
  contracts in `core/types.py`, abstract interfaces in `base.py` and
  raising stubs in `stub.py`.
- Documentation set under `docs/` with index, layer pages,
  configuration and development guides, roadmap and the ADR process
  (ADR 0001).
- GitHub infrastructure: CI (Python 3.11/3.12 matrix), docs build,
  issue templates and pull request checklist.
- Prototypes P01–P03, MVP bill of materials, Docker image and compose
  file, dev/prod configs, bootstrap scripts.

### Decisions taken while scaffolding

- `mkdocs.yml` added at the repository root because `make docs` and the
  docs workflow call `mkdocs build --strict`; without it the target
  would fail. `mkdocs-material` is not pinned as a dependency yet — it
  is expected from the environment.
- `tests/` added with three suites (`test_core_types`,
  `test_interfaces`, `test_pipeline`) because the CI workflow runs
  `pytest`; they assert only scaffold invariants so they stay green as
  real implementations land.
- `configs/storylink.yaml` added as the example rule table referenced
  by `docs/06-compositing-ar.md` and `prod.example.yaml`.
- `assets/sample-data/.gitkeep` added because `.gitignore` excludes
  the sample data directory.
- The CI line-ending check only fails on `crlf`/`mixed` index states so
  that intentionally binary files are not flagged.

[Unreleased]: https://github.com/stageforge/stageforge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/stageforge/stageforge/releases/tag/v0.1.0
