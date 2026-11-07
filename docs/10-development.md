# Development Guide

## Layout

```
src/stageforge/        installable package
  core/                shared types + base contracts
  capture/             L1
  reconstruction/      L2 (depth)
  tracking/            L2 (pose)
  segmentation/        L3
  compositing/         L4
  storylink/           L4 (editorial mapping)
  orchestrator/        wiring + lifecycle
tests/                 pytest suite
docs/                  this documentation
prototypes/            throwaway MVP experiments
infra/                 hardware, docker
configs/               YAML configuration
scripts/               bootstrap and tooling
```

## Interfaces

Every layer package has the same shape:

| File | Contents |
|------|----------|
| `__init__.py` | re-exports the public names |
| `base.py` | one `abc.ABC` — the contract |
| `stub.py` | a class implementing it by raising `NotImplementedError` |

Adding a layer means adding those three files plus an entry in
`orchestrator/pipeline.py`.

## Rules we actually enforce

1. `ruff check`, `ruff format --check` and `mypy --strict` pass.
2. Files stay under ~200 lines; split before you sprawl.
3. Public behaviour changes need a test and a `CHANGELOG.md` entry.
4. Architectural changes need an ADR ([adr/README.md](adr/README.md)).
5. UTF-8 + LF everywhere (`.editorconfig`, `.gitattributes`,
   `pre-commit` `mixed-line-ending` hook all agree).

> **Known mypy baseline:** `mypy src scripts --strict` reports 13 errors in 6
> older scripts that pre-date ADR-0009 (`stage_reconstruct.py`,
> `profile_pipeline.py`, `measure_depth_backends.py`, `export_depth_onnx.py`,
> `gen_tree.py`, `diagnose_camera.py`). CI type-checks `src/` only and stays
> green. Do not try to "fix" that baseline in the middle of an unrelated task —
> it is tracked as technical debt for the pilot.

## Commands

```bash
make install   # editable install + hooks
make lint      # ruff + mypy
make fmt       # auto-fix
make test      # pytest
make docs      # mkdocs build --strict
make clean     # remove caches
```

## Adding a test

```python
# tests/test_core_types.py
from stageforge.core.types import Frame


def test_frame_is_immutable() -> None:
    f = Frame(timestamp_us=0, width=1920, height=1080, data=None)
    assert f.timestamp_us == 0
```

## Debugging tips

- Set `STAGEFORGE_LOG_LEVEL=debug` to see per-layer timing.
- `STAGEFORGE_FAKE_INPUT=1` replaces cameras with a generated pattern,
  so the pipeline runs with no hardware.
- `scripts/gen_tree.py` regenerates the tree shown in the README.
