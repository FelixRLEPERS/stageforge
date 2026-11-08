# Getting Started

This guide takes you from a clean machine to a running (scaffold)
StageForge installation.

## Prerequisites

- Python 3.11 or 3.12
- `git`
- `make` (optional, Windows users can call the tools directly)
- For real hardware work: an NDI-enabled network and/or a Blackmagic
  DeckLink card — see [`infra/hardware/mvp-bom.md`](https://github.com/FelixRLEPERS/stageforge/blob/main/infra/hardware/mvp-bom.md)

## 1. Clone and bootstrap

```bash
git clone https://github.com/FelixRLEPERS/stageforge.git
cd stageforge
```

Linux / macOS:

```bash
./scripts/bootstrap.sh
```

Windows (PowerShell):

```powershell
.\scripts\bootstrap.ps1
```

The script creates `.venv/`, installs `pip install -e ".[dev]"` and
registers the pre-commit hooks.

## 2. Verify the install

```bash
make lint
make test
```

Both should pass on a fresh clone. The test suite is intentionally
small at this stage — it asserts that the package imports and that the
public interfaces are abstract.

## 3. Pick a configuration

```bash
cp configs/prod.example.yaml configs/prod.local.yaml
```

`configs/dev.yaml` is the default and points at stub providers, so no
hardware is required. See [Configuration](09-configuration.md).

## 4. Run the orchestrator

```bash
python -m stageforge.orchestrator --config configs/dev.yaml
```

Expected output on a scaffold build:

```
StageForge scaffold — replace in MVP phase
```

Every layer raises `NotImplementedError` on purpose; wiring real
implementations is exactly what the roadmap in
[11-roadmap](11-roadmap.md) tracks.

## 5. Build the documentation

```bash
make docs
```

Output lands in `site/`.

## Next steps

- Understand the data flow: [02-architecture.md](02-architecture.md)
- Try a prototype: [`prototypes`](https://github.com/FelixRLEPERS/stageforge/blob/main/prototypes)
- Read the roadmap: [11-roadmap.md](11-roadmap.md)
