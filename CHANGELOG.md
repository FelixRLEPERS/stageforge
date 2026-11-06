# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
