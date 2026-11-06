"""Base contracts shared by every StageForge layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Layer(ABC):
    """Common lifecycle for every pipeline layer (L1..L5).

    Contract: ``configure`` receives the validated YAML section for the
    layer and must be called once before ``start``; ``start`` acquires
    devices or connections; ``stop`` releases them and must be
    idempotent. Implementations must raise ``NotImplementedError`` only
    while the scaffold is in place, and any operational failure after
    ``start`` must surface as ``RuntimeError`` with a message that says
    which layer failed.
    """

    @abstractmethod
    def configure(self, config: dict[str, Any]) -> None:
        """Validate and store the layer configuration section."""

    @abstractmethod
    def start(self) -> None:
        """Acquire resources. Idempotent."""

    @abstractmethod
    def stop(self) -> None:
        """Release resources. Idempotent and safe during shutdown."""
