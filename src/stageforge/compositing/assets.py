"""Loading and placing AR assets on a flat plate.

The MVP composites in 2D — no Unreal Engine, no camera solve. Assets are
anchored to named stage positions expressed as fractions of the raster,
which is enough to park a graphic next to the presenter and to prove the
Story-Link wiring before the 3D bridge exists.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.core.types import ARAsset

_ANCHORS: dict[str, tuple[float, float]] = {
    "stage_center": (0.50, 0.50),
    "stage_left": (0.26, 0.52),
    "stage_right": (0.74, 0.52),
    "desk_right": (0.78, 0.64),
    "desk_left": (0.22, 0.64),
    "backdrop": (0.50, 0.34),
}

# The green cue box is a debug affordance, not on-air content: it only
# draws when this variable is set, so a missing asset yields a clean
# plate by default.
_PLACEHOLDER_ENV = "STAGEFORGE_AR_PLACEHOLDER"
_skipped: set[str] = set()

__all__ = ["anchor_point", "load_asset", "place_asset"]


def anchor_point(
    anchor: str,
    width: int,
    height: int,
    metadata: dict[str, object] | None = None,
) -> tuple[int, int]:
    """Pixel centre for an anchor name; ``metadata`` may override with x/y."""
    fraction = _ANCHORS.get(anchor)
    if fraction is None and metadata:
        override_x, override_y = metadata.get("x"), metadata.get("y")
        if isinstance(override_x, (int, float)) and isinstance(override_y, (int, float)):
            fraction = (float(override_x), float(override_y))
    if fraction is None:
        logger.warning(f"unknown anchor {anchor!r}, falling back to stage centre")
        fraction = _ANCHORS["stage_center"]
    return int(fraction[0] * width), int(fraction[1] * height)


def load_asset(uri: str) -> npt.NDArray[np.uint8] | None:
    """Read an image asset as BGRA/BGR, or ``None`` when it is absent.

    Video and 3D assets are not handled by the 2D compositor; returning
    ``None`` lets the caller drop them instead of crashing.
    """
    if not uri or not Path(uri).is_file():
        return None
    image = cv2.imread(uri, cv2.IMREAD_UNCHANGED)
    if image is None:
        return None
    return np.asarray(image, dtype=np.uint8)


def place_asset(
    target: npt.NDArray[np.uint8],
    asset: ARAsset,
) -> npt.NDArray[np.uint8]:
    """Blit ``asset`` onto ``target``; skip it when the file is missing.

    An asset that is absent or not a loadable image (a video loop, a 3D
    model) draws nothing, so the plate stays clean on air. Set
    ``STAGEFORGE_AR_PLACEHOLDER=1`` to get the green cue box instead —
    visible proof that a Story-Link rule fired.
    """
    height, width = target.shape[:2]
    image = load_asset(asset.uri)
    if image is None:
        if os.environ.get(_PLACEHOLDER_ENV):
            return _placeholder(target, asset, width, height)
        if asset.asset_id not in _skipped:
            _skipped.add(asset.asset_id)
            logger.warning(
                f"asset {asset.asset_id!r} ({asset.uri!r}) is not a loadable image; "
                f"no overlay drawn — set {_PLACEHOLDER_ENV}=1 for the debug box"
            )
        return target

    scale = asset.scale if asset.scale > 0 else 1.0
    new_width = max(1, round(image.shape[1] * scale))
    new_height = max(1, round(image.shape[0] * scale))
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    centre_x, centre_y = anchor_point(asset.anchor, width, height, asset.metadata)
    x0 = min(max(0, centre_x - new_width // 2), max(0, width - 1))
    y0 = min(max(0, centre_y - new_height // 2), max(0, height - 1))
    x1, y1 = min(width, x0 + new_width), min(height, y0 + new_height)
    patch = resized[0 : y1 - y0, 0 : x1 - x0]
    if patch.size == 0:
        return target

    if patch.ndim == 3 and patch.shape[2] == 4:
        alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
        rgb = patch[:, :, :3].astype(np.float32)
        region = target[y0:y1, x0:x1].astype(np.float32)
        blended = rgb * alpha + region * (1.0 - alpha)
        target[y0:y1, x0:x1] = np.asarray(np.round(blended), dtype=np.uint8)
    elif patch.ndim == 3:
        target[y0:y1, x0:x1] = patch[:, :, :3]
    else:
        target[y0:y1, x0:x1] = patch
    return target


def _placeholder(
    target: npt.NDArray[np.uint8],
    asset: ARAsset,
    width: int,
    height: int,
) -> npt.NDArray[np.uint8]:
    """Green outline plus the asset id — visible proof that a cue fired.

    Only reachable when ``STAGEFORGE_AR_PLACEHOLDER`` is set (see
    :func:`place_asset`); off by default because it is debug furniture.
    """
    box_width = max(32, width // 5)
    box_height = max(32, height // 5)
    centre_x, centre_y = anchor_point(asset.anchor, width, height, asset.metadata)
    x0 = min(max(0, centre_x - box_width // 2), max(0, width - box_width))
    y0 = min(max(0, centre_y - box_height // 2), max(0, height - box_height))
    x1, y1 = x0 + box_width, y0 + box_height

    # Fill only the box, not the whole raster: the addWeighted blend on
    # the full frame cost ~9 ms per placeholder at 1080p.
    box = target[y0:y1, x0:x1]
    overlay = box.copy()
    cv2.rectangle(overlay, (0, 0), (x1 - x0, y1 - y0), (0, 220, 0), -1)
    box[:] = cv2.addWeighted(overlay, 0.25, box, 0.75, 0)
    cv2.rectangle(target, (x0, y0), (x1, y1), (0, 255, 0), 3)
    cv2.putText(
        target,
        f"AR {asset.asset_id}"[:28],
        (x0 + 8, min(y1 - 12, y0 + 34)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return target
