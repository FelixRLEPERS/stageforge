PYTHON ?= python
PIP ?= pip

.PHONY: install lint fmt test docs clean

## Install the package with dev extras and pre-commit hooks.
install:
	$(PIP) install -e ".[dev]"
	pre-commit install

## Run ruff + mypy.
lint:
	ruff check src tests scripts
	ruff format --check src tests scripts
	mypy src

## Auto-format with ruff.
fmt:
	ruff format src tests scripts
	ruff check --fix src tests scripts

## Run the test suite.
test:
	pytest -q

## Build the documentation site into site/.
docs:
	mkdocs build --strict

## Remove build artifacts and caches.
clean:
	rm -rf build dist site .pytest_cache .mypy_cache .ruff_cache htmlcov
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.egg-info" -type d -prune -exec rm -rf {} +
