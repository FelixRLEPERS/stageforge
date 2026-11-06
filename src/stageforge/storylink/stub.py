"""Scaffold implementation of :class:`StoryLink`."""

from __future__ import annotations

from stageforge.core.types import ARAsset, RundownCue
from stageforge.storylink.base import StoryLink

_MESSAGE = "StageForge scaffold — replace in MVP phase"


class StubStoryLink(StoryLink):
    """Placeholder matcher that raises instead of resolving cues."""

    def load_rules(self, rules: list[dict[str, object]]) -> None:
        """Raise until the YAML rule matcher exists."""
        raise NotImplementedError(_MESSAGE)

    def assets_for(self, cue: RundownCue) -> tuple[ARAsset, ...]:
        """Raise until the YAML rule matcher exists."""
        raise NotImplementedError(_MESSAGE)
