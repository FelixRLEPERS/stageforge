"""Building the capture layer from the ``camera`` config section.

Split out of :mod:`stageforge.orchestrator.builder` so the layer factory
stays readable: this module only knows about sources, autocrop policy
and how many cameras are active.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stageforge.capture.base import CaptureSource
from stageforge.capture.multi import MultiCameraSource
from stageforge.capture.source import UsbCameraSource
from stageforge.capture.synthetic import SyntheticCameraSource
from stageforge.core.log import logger

__all__ = ["aspect", "build_capture", "mapping"]


def build_capture(
    mode: str,
    camera_cfg: Mapping[str, Any],
) -> tuple[CaptureSource, MultiCameraSource | None]:
    """Build one source per configured camera, wrapped when there are two."""
    width = int(camera_cfg.get("width", 1920))
    height = int(camera_cfg.get("height", 1080))
    fps = int(camera_cfg.get("fps", 30))
    entries = [item for item in camera_cfg.get("cameras", []) if isinstance(item, dict)]
    count = max(1, int(camera_cfg.get("num_cameras", len(entries) or 1)))
    count = min(count, max(1, len(entries))) if entries else count

    sources: list[CaptureSource] = []
    for index in range(count):
        entry: Mapping[str, Any] = entries[index] if index < len(entries) else {}
        if mode == "synthetic":
            sources.append(_synthetic_source(index, entry, width, height, camera_cfg))
        else:
            sources.append(_usb_source(index, entry, width, height, fps))

    if len(sources) == 1:
        return sources[0], None
    multi = MultiCameraSource(sources, max_skew=int(camera_cfg.get("max_skew", 2)))
    return multi, multi


def mapping(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Read a nested mapping, tolerating absent or wrongly typed sections."""
    value = config.get(key)
    return value if isinstance(value, Mapping) else {}


def aspect(value: Any, default: float | None) -> float | None:
    """Accept ``"16:9"``, ``1.777`` or nothing at all."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and ":" in value:
        numerator, _, denominator = value.partition(":")
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            logger.warning(f"unparsable target_aspect {value!r}, using {default}")
    return default


def _usb_source(
    index: int,
    entry: Mapping[str, Any],
    width: int,
    height: int,
    fps: int,
) -> UsbCameraSource:
    """One UVC device with its autocrop policy."""
    autocrop = mapping(entry, "autocrop")
    return UsbCameraSource(
        index=int(entry.get("source", index)),
        width=width,
        height=height,
        fps=fps,
        autocrop=bool(autocrop.get("enabled", True)),
        autocrop_threshold=int(autocrop.get("threshold", 10)),
        autocrop_refresh=int(autocrop.get("refresh_interval", 300)),
        target_aspect=aspect(autocrop.get("target_aspect"), 16 / 9),
        name=str(entry.get("name", f"cam{index}")),
    )


def _synthetic_source(
    index: int,
    entry: Mapping[str, Any],
    width: int,
    height: int,
    camera_cfg: Mapping[str, Any],
) -> SyntheticCameraSource:
    """Generated stand-in that still exercises the autocrop path."""
    autocrop = mapping(entry, "autocrop")
    pattern = str(mapping(camera_cfg, "synthetic").get("pattern", "pillarbox"))
    return SyntheticCameraSource(
        index=index,
        width=width,
        height=height,
        pattern=pattern,
        autocrop=bool(autocrop.get("enabled", True)),
        autocrop_threshold=int(autocrop.get("threshold", 10)),
        autocrop_refresh=int(autocrop.get("refresh_interval", 300)),
        target_aspect=aspect(autocrop.get("target_aspect"), 16 / 9),
        name=str(entry.get("name", f"synthetic{index}")),
    )
