"""One-shot colour calibration: a chart (or grey card) in, a profile out.

The deliberate workflow in ``scripts/calibrate.py`` is capture ->
build -> test-frame, three invocations per camera+lens pair. This
module is the test-day shortcut: one call detects the chart, solves
the 3x3 CCM, writes it next to the profile and reports the fit
quality as a percentage of the full sRGB scale.

When no chart is found it falls back to the centre of the frame as an
18% grey card — an EV trim only, with a warning, because exposure
cannot replace a matrix. Any residual above ``RESIDUAL_WARN_PCT`` is
flagged too: a chart that will not fit usually means it was not flat
in frame or the shot clipped, so nothing downstream can be trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from stageforge.calibration.apply import compute_ev_offset_from_grey_card
from stageforge.calibration.build_lut import FloatArray, compute_ccm, write_ccm
from stageforge.calibration.detect import find_colorchecker_patches, sample_grid_in_rect
from stageforge.calibration.profiles import load_profile, save_profile
from stageforge.calibration.reference import COLORCHECKER_CLASSIC_SRGB

RESIDUAL_WARN_PCT = 5.0

__all__ = ["RESIDUAL_WARN_PCT", "QuickResult", "quick_calibrate", "residual_pct"]


@dataclass(frozen=True)
class QuickResult:
    """What one calibration shot achieved, for the CLI to report."""

    mode: str  # "ccm" (chart) or "grey" (EV trim only)
    profile: str
    lut_path: str | None
    residual_pct: float | None
    ev: float | None
    warning: str  # "" when nothing needs saying


def residual_pct(measured: FloatArray, ccm: FloatArray) -> float:
    """Mean fit error as a percentage of the full sRGB scale (255 = 100%)."""
    predicted = np.asarray(measured, dtype=np.float64) @ np.asarray(ccm, dtype=np.float64)
    error = np.abs(predicted - COLORCHECKER_CLASSIC_SRGB)
    return float(error.mean() / 255.0 * 100.0)


def quick_calibrate(
    image: npt.NDArray[np.uint8],
    output: str | Path,
    *,
    rect: tuple[int, int, int, int] | None = None,
    camera_name: str | None = None,
) -> QuickResult:
    """Fit a correction from *image* and store it in the *output* profile.

    *output* must already be a profile JSON (a template from
    ``calibration/profiles/``); its ``lut_path`` is pointed at the new
    ``.ccm`` written beside it. Raises ``ValueError`` when the frame
    carries neither a chart nor a readable centre (pure black).
    """
    profile = load_profile(output)
    if camera_name:
        profile.camera = camera_name
    patches: npt.NDArray[np.float32] | None
    if rect is not None:
        patches = sample_grid_in_rect(image, rect)
    else:
        patches = find_colorchecker_patches(image)
    if patches is None:  # no chart: assume the centre half is an 18% card
        ev = compute_ev_offset_from_grey_card(image)
        profile.gray_card_offset_ev = ev
        save_profile(profile, output)
        return QuickResult(
            mode="grey",
            profile=str(output),
            lut_path=profile.lut_path,
            residual_pct=None,
            ev=ev,
            warning="no ColorChecker found - grey-card EV only, colour matrix unchanged",
        )
    ccm = compute_ccm(patches, COLORCHECKER_CLASSIC_SRGB)
    residual = residual_pct(patches, ccm)
    lut_path = Path(output).with_suffix(".ccm")
    write_ccm(ccm, lut_path)
    profile.lut_path = str(lut_path)
    save_profile(profile, output)
    warning = ""
    if residual > RESIDUAL_WARN_PCT:
        warning = (
            f"residual {residual:.1f}% exceeds {RESIDUAL_WARN_PCT:.0f}% - "
            "chart not flat in frame or clipped?"
        )
    return QuickResult(
        mode="ccm",
        profile=str(output),
        lut_path=str(lut_path),
        residual_pct=residual,
        ev=None,
        warning=warning,
    )
