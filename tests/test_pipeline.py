"""The orchestrator wires five layers in order and is still a scaffold."""

from __future__ import annotations

import pytest

from stageforge.orchestrator.pipeline import Pipeline

EXPECTED_LAYERS = (
    "capture",
    "reconstruction",
    "tracking",
    "segmentation",
    "compositing",
    "output",
)


def test_layers_are_listed_in_start_order() -> None:
    assert Pipeline().layers == EXPECTED_LAYERS


def test_config_defaults_to_empty_mapping() -> None:
    assert Pipeline().layers == Pipeline(config={}).layers
    assert Pipeline(config={"cameras": []}).layers == EXPECTED_LAYERS


def test_run_is_still_a_scaffold() -> None:
    with pytest.raises(NotImplementedError, match="StageForge scaffold"):
        Pipeline().run()


def test_stop_is_still_a_scaffold() -> None:
    with pytest.raises(NotImplementedError, match="StageForge scaffold"):
        Pipeline().stop()
