"""Contract for L4: rendering AR and mixing it with the plate."""

from __future__ import annotations

from abc import ABC, abstractmethod

from stageforge.core.types import AlphaMask, ARAsset, CameraPose, Frame


class RendererUnavailableError(RuntimeError):
    """Raised when the UE bridge is down or the render node is unreachable."""


class Compositor(ABC):
    """Renders AR assets and mixes them into the keyed plate.

    Input: the plate ``Frame``, its ``AlphaMask``, the current
    ``CameraPose`` and the ``ARAsset`` list selected by Story-Link.
    Output: one composited ``Frame`` ready for the output layer.
    Raises: ``RendererUnavailableError`` when the Unreal Engine bridge
    cannot be reached; ``compositor.fallback`` decides whether the
    pipeline fails on air or passes the plate through untouched.
    """

    @abstractmethod
    def connect(self) -> None:
        """Attach to the render bridge and sync the frame rate."""

    @abstractmethod
    def render(
        self,
        frame: Frame,
        mask: AlphaMask,
        pose: CameraPose,
        assets: tuple[ARAsset, ...],
    ) -> Frame:
        """Composite the assets for this frame and return the result."""

    @abstractmethod
    def disconnect(self) -> None:
        """Detach from the render bridge. Safe to call twice."""
