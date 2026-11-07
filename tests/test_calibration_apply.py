"""Frame corrections: CCM, EV offset, and the compiled calibrator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from stageforge.calibration.apply import (
    apply_ccm_to_frame,
    apply_cube_lut_to_frame,
    apply_ev_offset,
    compute_ev_offset_from_grey_card,
    load_cube,
)
from stageforge.calibration.build_lut import write_ccm, write_cube
from stageforge.calibration.profiles import CameraProfile, save_profile
from stageforge.calibration.step import build_calibrator
from stageforge.core.types import Frame


def _frame(data: npt.NDArray[np.uint8]) -> Frame:
    return Frame(
        timestamp_us=0,
        camera_id="calib",
        width=int(data.shape[1]),
        height=int(data.shape[0]),
        data=data,
    )


def test_identity_ccm_leaves_frame_unchanged() -> None:
    frame = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    out = apply_ccm_to_frame(frame, np.eye(3, dtype=np.float32))
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(out, frame)


def test_known_shift_moves_pixels_as_expected() -> None:
    frame = np.full((2, 2, 3), 100, dtype=np.uint8)
    ccm = np.diag([1.0, 0.5, 1.0]).astype(np.float32)  # green channel halved
    out = apply_ccm_to_frame(frame, ccm)
    assert int(out[0, 0, 1]) == 50  # G
    assert int(out[0, 0, 0]) == 100  # B untouched
    assert int(out[0, 0, 2]) == 100  # R untouched


def test_frame_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError):
        apply_ccm_to_frame(np.zeros((4, 4), dtype=np.uint8), np.eye(3, dtype=np.float32))


def test_ev_plus_one_doubles_brightness() -> None:
    frame = np.full((2, 2, 3), 100, dtype=np.uint8)
    assert int(apply_ev_offset(frame, 1.0)[0, 0, 0]) == 200


def test_ev_minus_one_halves_brightness() -> None:
    frame = np.full((2, 2, 3), 200, dtype=np.uint8)
    assert int(apply_ev_offset(frame, -1.0)[0, 0, 0]) == 100


def test_ev_zero_returns_input_unchanged() -> None:
    frame = np.full((2, 2, 3), 77, dtype=np.uint8)
    assert apply_ev_offset(frame, 0.0) is frame


def test_compute_ev_offset_from_grey_card() -> None:
    # card already at target -> no correction
    card = np.full((64, 64, 3), 118, dtype=np.uint8)
    assert compute_ev_offset_from_grey_card(card) == 0.0
    # card one stop under -> +1 EV
    dark = np.full((64, 64, 3), 59, dtype=np.uint8)
    assert compute_ev_offset_from_grey_card(dark) == pytest.approx(1.0, abs=0.05)
    # card one stop over -> -1 EV
    bright = np.full((64, 64, 3), 236, dtype=np.uint8)
    assert compute_ev_offset_from_grey_card(bright) == pytest.approx(-1.0, abs=0.05)


def test_compute_ev_offset_rejects_black_card() -> None:
    with pytest.raises(ValueError, match="pure black"):
        compute_ev_offset_from_grey_card(np.zeros((64, 64, 3), dtype=np.uint8))


def test_identity_cube_roundtrip_is_noop(tmp_path: Path) -> None:
    # write an identity 17^3 cube, load it, apply it -> frame byte-identical
    grid = 17
    axes = np.linspace(0.0, 1.0, grid, dtype=np.float32)
    blue, green, red = np.meshgrid(axes, axes, axes, indexing="ij")
    cube = np.stack((red, green, blue), axis=-1)
    cube_path = tmp_path / "identity.cube"
    write_cube(cube, cube_path, title="identity")
    loaded = load_cube(cube_path)
    frame = np.arange(192, dtype=np.uint8).reshape(8, 8, 3)
    out = apply_cube_lut_to_frame(frame, loaded)
    np.testing.assert_array_equal(out, frame)


def test_disabled_config_builds_identity(tmp_path: Path) -> None:
    calibrate = build_calibrator({})
    frame = _frame(np.zeros((4, 4, 3), dtype=np.uint8))
    assert calibrate(frame) is frame
    assert calibrate(build_calibrator({"enabled": False})(frame)) is frame


def test_segmentation_position_is_rejected() -> None:
    with pytest.raises(ValueError, match="deferred"):
        build_calibrator({"enabled": True, "apply_before": "segmentation"})


def test_enabled_calibrator_applies_profile_ccm(tmp_path: Path) -> None:
    # red doubled, green and blue untouched
    lut_path = tmp_path / "known.ccm"
    write_ccm(np.diag([2.0, 1.0, 1.0]).astype(np.float32), lut_path)
    profile_path = tmp_path / "profile.json"
    save_profile(
        CameraProfile(
            camera="Canon EOS 5D Mark II",
            lens="EF 50mm f/1.8 STM",
            sensor="full-frame CMOS",
            crop_factor=1.0,
            aperture_used="f/4.0",
            native_iso=[100],
            color_space="sRGB",
            lut_path=str(lut_path),
        ),
        profile_path,
    )
    calibrate = build_calibrator({"enabled": True, "profile": str(profile_path), "mode": "ccm"})
    frame = _frame(np.full((2, 2, 3), 100, dtype=np.uint8))
    out = calibrate(frame)
    assert out is not frame
    assert int(out.data[0, 0, 2]) == 200  # R doubled, BGR channel 2
    assert int(out.data[0, 0, 0]) == 100  # B untouched


def test_enabled_without_lut_path_fails_fast(tmp_path: Path) -> None:
    profile_path = tmp_path / "empty.json"
    save_profile(
        CameraProfile(
            camera="c",
            lens="l",
            sensor="s",
            crop_factor=1.0,
            aperture_used="f/4.0",
            native_iso=[100],
            color_space="sRGB",
        ),
        profile_path,
    )
    with pytest.raises(ValueError, match="no lut_path"):
        build_calibrator({"enabled": True, "profile": str(profile_path)})
