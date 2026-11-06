#!/usr/bin/env bash
# StageForge bootstrap for Linux / macOS.
# Creates .venv, installs the package with dev extras, registers hooks.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

echo "[1/4] Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11 or newer is required." >&2; exit 1; }
echo "      $(python3 --version)"

echo "[2/4] Creating virtual environment..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip

echo "[3/4] Installing stageforge[dev]..."
python -m pip install -e ".[dev]"

echo "[4/4] Installing pre-commit hooks..."
pre-commit install

echo ""
echo "Done. Activate with:  source .venv/bin/activate"
echo "Then run:             make test"
