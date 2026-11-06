"""Scaffold implementation of :class:`Compositor`."""

from __future__ import annotations

from stageforge.compositing.base import Compositor
from stageforge.core.types import AlphaMask, ARAsset, CameraPose, Frame

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubCompositor(Compositor):
    """Placeholder compositor that raises instead of rendering."""

    def connect(self) -> None:
        """Raise until the Unreal Engine bridge exists."""
        raise NotImplementedError(_MESSAGE)

    def render(
        self,
        frame: Frame,
        mask: AlphaMask,
        pose: CameraPose,
        assets: tuple[ARAsset, ...],
    ) -> Frame:
        """Raise until the Unreal Engine bridge exists."""
        raise NotImplementedError(_MESSAGE)

    def disconnect(self) -> None:
        """Raise until the Unreal Engine bridge exists."""
        raise NotImplementedError(_MESSAGE)
