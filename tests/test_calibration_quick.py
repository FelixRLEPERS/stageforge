"""One-shot calibration (`calibrate.py --quick`): fit, fallback, CLI.

The chart path is exercised with the synthetic ColorChecker, the
grey-card fallback with a flat 18% frame, and the CLI end to end via
subprocess so the real argument wiring is covered.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from stageforge.calibration.profiles import CameraProfile, load_profile, save_profile
from stageforge.calibration.quick import RESIDUAL_WARN_PCT, quick_calibrate, residual_pct
from stageforge.calibration.reference import (
    COLORCHECKER_CLASSIC_SRGB,
    generate_colorchecker_image,
)

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "calibrate.py"


def _profile(target: Path) -> Path:
    """A minimal profile for quick_calibrate to update."""
    save_profile(
        CameraProfile(
            camera="Canon EOS 5D Mark II",
            lens="EF 50mm f/1.8 STM",
            sensor="full-frame CMOS",
            crop_factor=1.0,
            aperture_used="f/4.0",
            native_iso=[100, 200, 400],
            color_space="sRGB",
        ),
        target,
    )
    return target


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_quick_fits_a_perfect_chart(tmp_path: Path) -> None:
    """Synthetic chart -> tiny residual, .ccm written, profile pointed at it."""
    profile_path = _profile(tmp_path / "profile.json")
    chart = generate_colorchecker_image(600, 400)

    result = quick_calibrate(chart, profile_path)

    assert result.mode == "ccm"
    assert result.residual_pct is not None
    assert result.residual_pct < RESIDUAL_WARN_PCT
    assert result.warning == ""
    assert result.lut_path is not None and Path(result.lut_path).is_file()
    assert load_profile(profile_path).lut_path == result.lut_path


def test_residual_pct_separates_good_fit_from_bad() -> None:
    """Identity fits perfectly; swapping red and blue misses by far more than 5%."""
    reference = COLORCHECKER_CLASSIC_SRGB
    assert residual_pct(reference, np.eye(3, dtype=np.float32)) < 0.01
    swapped = np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]], dtype=np.float32)
    assert residual_pct(reference, swapped) > RESIDUAL_WARN_PCT


def test_quick_falls_back_to_a_grey_card_with_a_warning(tmp_path: Path) -> None:
    """No chart: EV trim from the centre, and explicitly no matrix fitted."""
    profile_path = _profile(tmp_path / "profile.json")
    flat = np.full((200, 300, 3), 118, dtype=np.uint8)  # exactly 18% grey

    result = quick_calibrate(flat, profile_path)

    assert result.mode == "grey"
    assert result.ev is not None and abs(result.ev) < 0.01
    assert "no ColorChecker" in result.warning
    assert result.residual_pct is None
    assert not (tmp_path / "profile.ccm").exists()
    assert load_profile(profile_path).lut_path is None


def test_quick_cli_reports_residual_and_renames_the_body(tmp_path: Path) -> None:
    """End to end: --quick --input exits 0, prints residual, updates profile."""
    chart = tmp_path / "chart.png"
    assert cv2.imwrite(str(chart), generate_colorchecker_image(600, 400))
    profile_path = _profile(tmp_path / "profile.json")

    proc = _run(
        "--quick",
        "--input",
        str(chart),
        "--profile",
        str(profile_path),
        "--camera-name",
        "Canon EOS 5D Mark IV",
    )

    assert proc.returncode == 0, proc.stderr
    assert "fit residual" in proc.stdout
    assert (tmp_path / "profile.ccm").is_file()
    assert load_profile(profile_path).camera == "Canon EOS 5D Mark IV"


def test_quick_cli_accepts_the_output_alias(tmp_path: Path) -> None:
    """--output is a plain alias of --profile: same one-shot run, same artefacts."""
    chart = tmp_path / "chart.png"
    assert cv2.imwrite(str(chart), generate_colorchecker_image(600, 400))
    profile_path = _profile(tmp_path / "profile.json")

    proc = _run("--quick", "--input", str(chart), "--output", str(profile_path))

    assert proc.returncode == 0, proc.stderr
    assert load_profile(profile_path).lut_path is not None


def test_quick_cli_requires_a_profile_target() -> None:
    """Without --profile/--output the run stops before touching a camera."""
    proc = _run("--quick")

    assert proc.returncode != 0
    assert "--profile" in proc.stderr + proc.stdout
