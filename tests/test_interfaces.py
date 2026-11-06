"""Every layer exposes an abstract contract and a raising stub."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from stageforge.capture.base import CaptureSource
from stageforge.capture.stub import StubCaptureSource
from stageforge.compositing.base import Compositor
from stageforge.compositing.stub import StubCompositor
from stageforge.core.base import Layer
from stageforge.core.stub import StubLayer
from stageforge.output.base import OutputSink
from stageforge.output.stub import StubOutputSink
from stageforge.reconstruction.base import DepthProvider
from stageforge.reconstruction.stub import StubDepthProvider
from stageforge.segmentation.base import Segmenter
from stageforge.segmentation.stub import StubSegmenter
from stageforge.storylink.base import StoryLink
from stageforge.storylink.stub import StubStoryLink
from stageforge.tracking.base import Tracker
from stageforge.tracking.stub import StubTracker

INTERFACES: list[type] = [
    Layer,
    CaptureSource,
    DepthProvider,
    Tracker,
    Segmenter,
    Compositor,
    StoryLink,
    OutputSink,
]

LAYER_PACKAGES = (
    "stageforge.capture",
    "stageforge.compositing",
    "stageforge.output",
    "stageforge.reconstruction",
    "stageforge.segmentation",
    "stageforge.storylink",
    "stageforge.tracking",
)

# Each stub paired with a zero-argument way to reach one of its methods.
STUBS: list[tuple[str, Callable[[], Any]]] = [
    ("StubLayer", lambda: StubLayer().configure({})),
    ("StubCaptureSource", lambda: StubCaptureSource().open()),
    ("StubDepthProvider", lambda: StubDepthProvider().calibrate()),
    ("StubTracker", lambda: StubTracker().connect()),
    ("StubSegmenter", lambda: StubSegmenter().warmup()),
    ("StubCompositor", lambda: StubCompositor().connect()),
    ("StubStoryLink", lambda: StubStoryLink().load_rules([])),
    ("StubOutputSink", lambda: StubOutputSink().open()),
]


@pytest.mark.parametrize("interface", INTERFACES)
def test_interface_is_abstract(interface: type) -> None:
    """Contracts cannot be instantiated directly."""
    with pytest.raises(TypeError):
        interface()  # type: ignore[abstract]


@pytest.mark.parametrize(("name", "call"), STUBS)
def test_stub_refuses_to_pretend(name: str, call: Callable[[], Any]) -> None:
    """Stubs are instantiable but raise the scaffold message when used."""
    assert name.startswith("Stub")
    with pytest.raises(NotImplementedError, match="StageForge scaffold"):
        call()


@pytest.mark.parametrize("package", LAYER_PACKAGES)
def test_layer_package_ships_contract_and_stub(package: str) -> None:
    """Each layer ships ``base`` (contract) and ``stub`` (placeholder)."""
    contract = __import__(f"{package}.base", fromlist=["base"])
    placeholder = __import__(f"{package}.stub", fromlist=["stub"])
    assert hasattr(contract, "__name__")
    assert hasattr(placeholder, "__name__")
    assert contract.__name__ == f"{package}.base"
    assert placeholder.__name__ == f"{package}.stub"
