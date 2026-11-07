"""CameraProfile JSON: round-trip, validation, committed templates."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from stageforge.calibration.profiles import CameraProfile, load_profile, save_profile

TEMPLATE = Path("calibration/profiles/canon_5d_mk2_50mm_1.8.json")


def _profile() -> CameraProfile:
    return CameraProfile(
        camera="Canon EOS 5D Mark II",
        lens="EF 50mm f/1.8 STM",
        sensor="full-frame CMOS",
        crop_factor=1.0,
        aperture_used="f/4.0",
        native_iso=[100, 200, 400],
        color_space="sRGB",
        gray_card_offset_ev=0.5,
    )


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "profile.json"
    save_profile(_profile(), target)
    assert load_profile(target) == _profile()


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "profile.json"
    data = asdict(_profile())
    data["iso"] = 100  # wrong name for native_iso
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_profile(target)


def test_missing_required_key_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "profile.json"
    data = asdict(_profile())
    del data["camera"]
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        load_profile(target)


def test_committed_template_profiles_load() -> None:
    for name in ("canon_5d_mk2_50mm_1.8.json", "canon_5d_mk2_40mm_2.8.json"):
        profile = load_profile(Path("calibration/profiles") / name)
        assert profile.camera == "Canon EOS 5D Mark II"
        assert profile.lut_path is None  # templates ship without a LUT
        assert profile.aperture_used == "f/4.0"
