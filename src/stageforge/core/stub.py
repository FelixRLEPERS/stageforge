"""Placeholder implementations of the shared layer lifecycle."""

from __future__ import annotations

from typing import Any

from stageforge.core.base import Layer

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubLayer(Layer):
    """A :class:`Layer` that does nothing and refuses to pretend otherwise."""

    def configure(self, config: dict[str, Any]) -> None:
        """Raise until a real implementation exists."""
        raise NotImplementedError(_MESSAGE)

    def start(self) -> None:
        """Raise until a real implementation exists."""
        raise NotImplementedError(_MESSAGE)

    def stop(self) -> None:
        """Raise until a real implementation exists."""
        raise NotImplementedError(_MESSAGE)
