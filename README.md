# StageForge

**Automatic virtual studio with real-time AR compositing.**

[![CI](https://github.com/stageforge/stageforge/actions/workflows/ci.yml/badge.svg)](https://github.com/stageforge/stageforge/actions/workflows/ci.yml)
[![Docs](https://github.com/stageforge/stageforge/actions/workflows/docs.yml/badge.svg)](https://github.com/stageforge/stageforge/actions/workflows/docs.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

StageForge turns a regular multi-camera studio into a fully automated
virtual environment: cameras reconstruct the 3D geometry of the stage,
the pipeline generates a clean alpha channel without a green screen,
and AR content is composited in real time and delivered to broadcast
via SDI Key/Fill or NDI.

## Why

- No green screen required.
- No manual camera calibration per show.
- AR content auto-linked to the anchor's rundown.
- Works with existing broadcast gear.

## Architecture (5 layers)

1. Capture (SDI/NDI + genlock)
2. Reconstruction & tracking (SfM, ToF, Free-D)
3. Segmentation & alpha (AI keyer / depth-based)
4. Compositing & AR (Godot render layer)
5. Output (SDI Key/Fill, NDI)

See [docs/02-architecture.md](docs/02-architecture.md).

## Status

🚧 Pre-MVP scaffold. See [docs/11-roadmap.md](docs/11-roadmap.md).

## Quick start

```bash
git clone https://github.com/stageforge/stageforge.git
cd stageforge
./scripts/bootstrap.sh      # or .\scripts\bootstrap.ps1 on Windows
make test
```

### ML extras on a CUDA machine

`[ml]` declares `torch>=2.0`, and pip resolves that to the **CPU wheel**
from PyPI — silently replacing a CUDA-enabled torch. Install torch from
the PyTorch index first, then StageForge without dependency resolution:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -e ".[ml]" --no-deps
pip install transformers timm
```

(CPU-only machines can just run `pip install -e ".[ml]"`.) For the ONNX
depth backend add `pip install -e ".[onnx-gpu]"` — or `".[onnx]"` for CPU
— and export the model once with `python scripts/export_depth_onnx.py`.

## Documentation

All documentation lives in [`docs/`](docs/00-index.md). Russian
translation: [`README.ru.md`](README.ru.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By participating you agree to
the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE).
