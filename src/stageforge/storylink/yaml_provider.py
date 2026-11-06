"""Story-Link driven by a plain YAML rule table.

A producer writes ``match → asset → anchor`` and the pipeline resolves
it at frame time. First matching rule wins and the order in the file is
the precedence order, so the behaviour is readable without a rule
engine. The format is exactly the one already shipped in
``configs/storylink.yaml``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

import yaml

from stageforge.core.log import logger
from stageforge.core.types import ARAsset, RundownCue
from stageforge.storylink.base import CueMatchError, StoryLink

Kind = Literal["model", "video", "graphic", "chart"]

_KIND_BY_SUFFIX: dict[str, Kind] = {
    ".glb": "model",
    ".gltf": "model",
    ".fbx": "model",
    ".obj": "model",
    ".mp4": "video",
    ".mov": "video",
    ".png": "graphic",
    ".jpg": "graphic",
    ".jpeg": "graphic",
    ".svg": "graphic",
    ".csv": "chart",
    ".json": "chart",
}

__all__ = ["YamlStoryLink"]


class YamlStoryLink(StoryLink):
    """Compiles a YAML rule table and resolves cues against it."""

    def __init__(self, config_path: str | None = None, strict: bool = False) -> None:
        self._strict = strict
        self._rules: list[dict[str, object]] = []
        self._source: str = "<empty>"
        if config_path:
            self.load(config_path)

    @property
    def rule_count(self) -> int:
        """How many rules are compiled and ready to fire."""
        return len(self._rules)

    @property
    def source(self) -> str:
        """Where the rules came from, for run reports."""
        return self._source

    def load(self, config_path: str) -> None:
        """Read and compile a ``storylink`` YAML file."""
        path = Path(config_path)
        if not path.is_file():
            raise CueMatchError(f"story-link config not found: {path}")
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(document, dict):
            raise CueMatchError(f"story-link config root must be a mapping: {path}")
        rules = document.get("rules", [])
        if not isinstance(rules, list):
            raise CueMatchError(f"'rules' must be a list in {path}")
        self.load_rules(cast("list[dict[str, object]]", rules))
        self._source = str(path)
        logger.info(f"story-link loaded: {len(self._rules)} rules from {path}")

    def load_rules(self, rules: list[dict[str, object]]) -> None:
        """Compile the ordered rule table."""
        self._rules = [rule for rule in rules if isinstance(rule, dict)]

    def assets_for(self, cue: RundownCue) -> tuple[ARAsset, ...]:
        """Resolve a rundown cue to the assets that should be on air."""
        return self._resolve(cue.topic, (cue.title, *cue.keywords))

    def assets_for_topic(self, topic: str, keywords: Sequence[str] = ()) -> tuple[ARAsset, ...]:
        """Resolve a bare topic string — the form the pipeline uses."""
        return self._resolve(topic, keywords)

    def _resolve(self, topic: str, context: Sequence[str]) -> tuple[ARAsset, ...]:
        """First matching rule wins; ``strict`` turns a miss into an error."""
        for rule in self._rules:
            match = rule.get("match")
            if isinstance(match, dict) and _rule_matches(match, topic, context):
                asset = _build_asset(rule, topic)
                if asset is not None:
                    return (asset,)
        if self._strict:
            raise CueMatchError(f"no story-link rule matched topic {topic!r}")
        logger.debug(f"story-link: no rule matched topic {topic!r}")
        return ()


def _rule_matches(match: dict[object, object], topic: str, context: Sequence[str]) -> bool:
    """Topic slug equality or keyword substring, whichever the rule uses."""
    topic_rule = match.get("topic")
    keyword_rule = match.get("keyword")
    if topic_rule is None and keyword_rule is None:
        return False
    if isinstance(topic_rule, str) and _equals(topic_rule, topic):
        return True
    return isinstance(keyword_rule, str) and _contains(keyword_rule, topic, context)


def _equals(pattern: str, value: str) -> bool:
    """Wildcard-aware exact comparison, case-insensitive."""
    normalised = pattern.strip().casefold()
    if normalised in {"", "*"}:
        return True
    return normalised == value.strip().casefold()


def _contains(pattern: str, topic: str, context: Sequence[str]) -> bool:
    """Wildcard-aware substring search over topic + free text."""
    normalised = pattern.strip().casefold()
    if normalised in {"", "*"}:
        return True
    haystack = " ".join((topic, *context)).casefold()
    return normalised in haystack


def _build_asset(rule: dict[str, object], topic: str) -> ARAsset | None:
    """Turn one YAML rule into an :class:`ARAsset`, or skip a malformed one."""
    asset_id = rule.get("asset")
    if not isinstance(asset_id, str) or not asset_id.strip():
        logger.warning(f"story-link rule for topic {topic!r} has no 'asset', skipped")
        return None

    uri = rule.get("path") or rule.get("uri") or f"assets/ar/{asset_id}.png"
    if not isinstance(uri, str):
        return None
    anchor = rule.get("anchor")
    metadata = {
        "topic": topic,
        "animation": rule.get("animation"),
        "raw": {key: value for key, value in rule.items() if key != "match"},
    }
    return ARAsset(
        asset_id=asset_id,
        kind=_kind_for(uri),
        uri=uri,
        anchor=anchor if isinstance(anchor, str) else "stage_center",
        scale=_positive_float(rule.get("scale"), default=1.0),
        metadata=metadata,
    )


def _kind_for(uri: str) -> Kind:
    """Classify an asset from its file suffix; unknown means 'graphic'."""
    return _KIND_BY_SUFFIX.get(Path(uri).suffix.lower(), "graphic")


def _positive_float(value: object, default: float) -> float:
    """Coerce a YAML value to a usable scale factor."""
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return default
