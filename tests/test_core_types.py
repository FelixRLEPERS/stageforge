"""Sanity checks for the shared data contracts."""

from __future__ import annotations

import numpy as np

from stageforge.core.types import AlphaMask, CameraPose, Frame, RundownCue


def test_frame_shape_reports_spatial_size() -> None:
    frame = Frame(timestamp_us=1, camera_id="cam_a", width=1920, height=1080, data=None)
    assert frame.shape == (1080, 1920)


def test_camera_pose_identity_is_4x4() -> None:
    pose = CameraPose.identity("cam_a", 42)
    assert pose.matrix.shape == (4, 4)
    assert pose.is_valid


def test_alpha_mask_accepts_uint8_buffer() -> None:
    buffer = np.full((4, 4), 255, dtype=np.uint8)
    mask = AlphaMask(camera_id="cam_a", timestamp_us=7, data=buffer, source="depth")
    assert mask.data.dtype == np.uint8
    assert mask.source == "depth"


def test_rundown_cue_matches_topic_and_keywords() -> None:
    cue = RundownCue(
        cue_id="c1",
        topic="markets",
        title="Rates steady as oil slips",
        starts_at_us=0,
        keywords=("rates", "oil"),
    )
    assert cue.matches("MARKET")
    assert cue.matches("oil")
    assert not cue.matches("weather")


def test_package_exports_pipeline() -> None:
    import stageforge

    assert stageforge.__version__ == "0.1.0"
