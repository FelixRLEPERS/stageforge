"""Turn the ``calibration`` config block into a ``Frame -> Frame`` call.

The compiled calibrator is built once by the orchestrator builder —
fail-fast there, before any device opens (docs/09). With the default
config (``enabled: false``) this returns a pass-through, so the
pipeline behaves exactly as before the calibration package existed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import partial
from typing import Any

import numpy as np
import numpy.typing as npt

from stageforge.calibration.apply import (
    apply_ccm_to_frame,
    apply_cube_lut_to_frame,
    apply_ev_offset,
    load_ccm,
    load_cube,
)
from stageforge.calibration.profiles import load_profile
from stageforge.core.log import logger
from stageforge.core.types import Frame

__all__ = ["build_calibrator"]

Correct = Callable[[npt.NDArray[np.uint8]], npt.NDArray[np.uint8]]


def build_calibrator(config: Mapping[str, Any]) -> Callable[[Frame], Frame]:
    """Compile ``calibration`` into a per-frame transform (identity if off).

    Raises ``ValueError`` for a broken or unsupported block at build
    time: a wrong profile must stop the run, not corrupt frames.
    """
    if not config.get("enabled"):
        return _identity
    apply_before = str(config.get("apply_before", "reconstruction"))
    if apply_before != "reconstruction":
        raise ValueError(
            f"calibration.apply_before={apply_before!r} is deferred: MVP applies "
            "calibration before reconstruction (ADR-0005)"
        )
    profile_path = str(config.get("profile", ""))
    if not profile_path:
        raise ValueError("calibration.enabled=true needs calibration.profile")
    profile = load_profile(profile_path)
    if not profile.lut_path:
        raise ValueError(
            f"profile {profile_path} has no lut_path - run scripts/calibrate.py --build"
        )
    mode = str(config.get("mode", "ccm"))
    if mode not in ("ccm", "cube"):
        raise ValueError(f"calibration.mode={mode!r}, expected 'ccm' or 'cube'")

    lut_path = str(profile.lut_path)
    correct: Correct
    if mode == "cube":
        correct = partial(apply_cube_lut_to_frame, cube_lut=load_cube(lut_path))
    else:
        correct = partial(apply_ccm_to_frame, ccm=load_ccm(lut_path))

    ev = float(profile.gray_card_offset_ev)

    def calibrate(frame: Frame) -> Frame:
        """Grey-card EV first, then the colour matrix (ADR-0005 order)."""
        data = frame.data
        if data is None:
            return frame
        if ev != 0.0:
            data = apply_ev_offset(data, ev)
        return replace(frame, data=correct(data))

    logger.info(
        f"calibration on: profile={profile_path} lens={profile.lens!r} "
        f"aperture={profile.aperture_used} mode={mode} ev={ev:+.2f}"
    )
    return calibrate


def _identity(frame: Frame) -> Frame:
    """Calibration disabled: the frame passes through untouched."""
    return frame
