"""CameraProfile: one JSON file per camera + lens combination.

Profiles are plain JSON (no pydantic — calibration must not grow the
dependency set). Two profiles exist for the 5D Mark II because the
colour signature belongs to the *lens* too: one per optic, each built
at a physically fixed aperture (ADR-0005).
"""

from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, fields
from pathlib import Path
from typing import Any

__all__ = ["CameraProfile", "load_profile", "save_profile"]


@dataclass(slots=True)
class CameraProfile:
    """Everything fixed for one camera + lens + aperture combination."""

    camera: str
    lens: str
    sensor: str
    crop_factor: float
    aperture_used: str  # dial position the chart was shot at, e.g. "f/4.0"
    native_iso: list[int]
    color_space: str  # 5D II: sRGB, no log curve (ADR-0005)
    lut_path: str | None = None  # .ccm (default) or .cube correction file
    gray_card_offset_ev: float = 0.0  # grey-card trim, applied before the matrix


def load_profile(path: str | Path) -> CameraProfile:
    """Read a profile JSON; unknown or missing keys raise ``ValueError``."""
    source = Path(path)
    data: Any = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"profile root must be a JSON object: {source}")
    known = {field.name for field in fields(CameraProfile)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown profile keys {sorted(unknown)} in {source}")
    required = {
        field.name
        for field in fields(CameraProfile)
        if field.default is MISSING and field.default_factory is MISSING
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"profile missing keys {sorted(missing)} in {source}")
    return CameraProfile(**data)


def save_profile(profile: CameraProfile, path: str | Path) -> None:
    """Write the profile as pretty JSON, creating parent folders."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(profile), indent=2, ensure_ascii=False)
    target.write_text(payload + "\n", encoding="utf-8")
