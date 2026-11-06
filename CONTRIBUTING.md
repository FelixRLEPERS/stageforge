# Contributing to StageForge

Thanks for your interest in contributing. This document explains the
workflow and the rules we follow.

## Workflow

1. Fork the repository and create a feature branch from `main`.
2. Install the development environment:

   ```bash
   ./scripts/bootstrap.sh        # or .\scripts\bootstrap.ps1 on Windows
   ```

3. Make your changes. Keep files under 200 lines where it is reasonable;
   split long modules instead.
4. Run the local checks before pushing:

   ```bash
   make lint
   make test
   ```

5. Update `CHANGELOG.md` under `[Unreleased]`.
6. Open a pull request using the template.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — a new user-facing capability
- `fix:` — a bug fix
- `chore:` — tooling, scaffolding, housekeeping
- `docs:` — documentation only
- `refactor:`, `test:`, `ci:` — as usual

Example: `feat(capture): add NDI source discovery`.

## Code style

- Python 3.11+, 4-space indent, `ruff` + `ruff-format` enforce the rest.
- Type annotations are mandatory; `mypy` runs in CI.
- Public interfaces (`base.py`) are abstract and documented: state the
  input, the output and the exceptions of the contract.

## Architecture Decision Records

Significant decisions (protocol choice, dependency, data layout) require
an ADR. See [docs/adr/README.md](docs/adr/README.md). Small fixes and
pure refactors do not.

## Reporting bugs

Use the issue templates. Include the OS, Python version, GPU/driver and
a minimal reproduction.

## Code of Conduct

This project follows the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md).
