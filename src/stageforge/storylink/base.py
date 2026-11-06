"""Contract for Story-Link: editorial intent becomes scene content."""

from __future__ import annotations

from abc import ABC, abstractmethod

from stageforge.core.types import ARAsset, RundownCue


class CueMatchError(RuntimeError):
    """Raised when a cue arrives but no rule resolves it and none is allowed."""


class StoryLink(ABC):
    """Maps the current :class:`RundownCue` to the assets to render.

    Input: the live cue from the newsroom system plus the rule table in
    ``configs/storylink.yaml`` (first matching rule wins).
    Output: an ordered tuple of ``ARAsset`` with anchors resolved to
    named stage positions.
    Raises: ``CueMatchError`` when a cue has no matching rule while
    ``strict`` is enabled; otherwise an empty tuple is returned and the
    plate is shown without AR.
    """

    @abstractmethod
    def load_rules(self, rules: list[dict[str, object]]) -> None:
        """Compile the ordered rule table."""

    @abstractmethod
    def assets_for(self, cue: RundownCue) -> tuple[ARAsset, ...]:
        """Resolve a cue to the assets that should be on air."""
