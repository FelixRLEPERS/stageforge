"""One-time studio calibration CLI: capture -> build -> check preview.

Workflow (details in calibration/README.md):

    python scripts/calibrate.py --capture --camera 0
    python scripts/calibrate.py --build --input calibration/captures/raw_TS.png \\
        --profile calibration/profiles/canon_5d_mk2_50mm_1.8.json
    python scripts/calibrate.py --test-frame --input calibration/captures/raw_TS.png \\
        --profile calibration/profiles/canon_5d_mk2_50mm_1.8.json

Test day is one call per camera: without ``--input`` the frame is
grabbed from ``--camera`` after an auto-exposure warm-up.

    python scripts/calibrate.py --quick --camera 0 --camera-name "Canon EOS 5D Mark IV" \\
        --profile calibration/profiles/canon_5d_mk2_50mm_1.8.json

``--quick`` fits what it sees: chart -> CCM + residual report, or the
centre 18% card -> EV trim with a warning that no matrix was fitted.

Nothing here runs in CI: a physical chart (or its print-out) is needed
once per camera + lens pair; the resulting .ccm stays gitignored and
the empty profile JSON travels with the repo.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.calibration.apply import (
    apply_ccm_to_frame,
    apply_cube_lut_to_frame,
    apply_ev_offset,
    compute_ev_offset_from_grey_card,
    load_ccm,
    load_cube,
)
from stageforge.calibration.build_lut import (
    compute_ccm,
    generate_lut_from_patches,
    write_ccm,
    write_cube,
)
from stageforge.calibration.detect import find_colorchecker_patches, sample_grid_in_rect
from stageforge.calibration.profiles import load_profile, save_profile
from stageforge.calibration.quick import RESIDUAL_WARN_PCT, quick_calibrate
from stageforge.calibration.reference import COLORCHECKER_CLASSIC_SRGB, GREY_CARD_18_SRGB

CAPTURES = Path("calibration/captures")


def _load(path: str) -> npt.NDArray[np.uint8]:
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"cannot read image: {path}")
    return np.asarray(image, dtype=np.uint8)


def _save(image: npt.NDArray[np.uint8], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), image):
        raise SystemExit(f"cannot write image: {target}")
    print(f"written: {target}")


def _patches(image: npt.NDArray[np.uint8], rect: Any) -> npt.NDArray[np.float32]:
    if rect is not None:
        return sample_grid_in_rect(image, rect)
    found = find_colorchecker_patches(image)
    if found is None:
        raise SystemExit(
            "ColorChecker not found on the frame. Options:\n"
            "  1. Check the chart is fully in frame (all 24 patches visible).\n"
            "  2. If auto-detect fails, pass --rect X,Y,W,H to set the grid box manually."
        )
    return found


def capture(args: argparse.Namespace) -> int:
    """Grab one frame with the chart in view -> captures/raw_<ts>.png."""
    _save(_grab(args.camera), CAPTURES / f"raw_{_stamp()}.png")
    return 0


def _grab(camera: int, warmup: int = 5) -> npt.NDArray[np.uint8]:
    """Open *camera*, discard *warmup* frames (auto-exposure settles), keep the last."""
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        raise SystemExit(f"cannot open camera index {camera}")
    frame: npt.NDArray[np.uint8] | None = None
    try:
        for _ in range(warmup):
            ok, image = cap.read()
            if ok and image is not None:
                frame = np.asarray(image, dtype=np.uint8)
    finally:
        cap.release()
    if frame is None:
        raise SystemExit(f"camera index {camera} returned no frame")
    return frame


def quick(args: argparse.Namespace) -> int:
    """One shot: chart (or centre grey card) -> profile + .ccm + residual%."""
    image = _load(args.input) if args.input else _grab(args.camera)
    try:
        result = quick_calibrate(image, args.profile, rect=args.rect, camera_name=args.camera_name)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(f"quick: {result.mode} -> {result.profile}")
    if result.residual_pct is not None:
        print(f"fit residual: {result.residual_pct:.1f}% (warn above {RESIDUAL_WARN_PCT:.0f}%)")
    if result.ev is not None:
        print(f"grey card: ev={result.ev:+.2f}")
    if result.warning:
        print(f"warning: {result.warning}")
    return 0


def build(args: argparse.Namespace) -> int:
    """Solve the CCM from the chart photo; save .ccm and point the profile at it."""
    profile = load_profile(args.profile)
    measured = _patches(_load(args.input), args.rect)
    ccm = compute_ccm(measured, COLORCHECKER_CLASSIC_SRGB)
    lut_path = Path(args.profile).with_suffix(".ccm")
    write_ccm(ccm, lut_path)
    profile.lut_path = str(lut_path)
    if args.cube:
        cube = generate_lut_from_patches(measured, COLORCHECKER_CLASSIC_SRGB, args.grid_size)
        cube_path = Path(args.profile).with_suffix(".cube")
        write_cube(cube, cube_path, title=f"{profile.camera} {profile.lens}")
        profile.lut_path = str(cube_path)
        print(f"cube written: {cube_path} - set calibration.mode: cube in the config")
    if args.aperture:
        profile.aperture_used = args.aperture
    save_profile(profile, args.profile)
    residual = np.abs(measured @ ccm.astype(np.float64) - COLORCHECKER_CLASSIC_SRGB)
    print(f"ccm written: {profile.lut_path}")
    print(f"fit residual: mean={residual.mean():.1f} max={residual.max():.1f} sRGB units")
    return 0


def test_frame(args: argparse.Namespace) -> int:
    """Apply EV + correction to a frame -> captures/test_<ts>.png."""
    profile = load_profile(args.profile)
    if not profile.lut_path:
        raise SystemExit(f"profile {args.profile} has no lut_path - run --build first")
    image = _load(args.input)
    ev = float(profile.gray_card_offset_ev)
    if ev:
        image = apply_ev_offset(image, ev)
    if args.mode == "cube":
        image = apply_cube_lut_to_frame(image, load_cube(profile.lut_path))
    else:
        image = apply_ccm_to_frame(image, load_ccm(profile.lut_path))
    _save(image, CAPTURES / f"test_{_stamp()}.png")
    return 0


def grey(args: argparse.Namespace) -> int:
    """18% grey card photo -> gray_card_offset_ev in the profile."""
    image = _load(args.input)
    try:
        ev = compute_ev_offset_from_grey_card(image)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    profile = load_profile(args.profile)
    profile.gray_card_offset_ev = ev
    save_profile(profile, args.profile)
    print(f"grey card: target={GREY_CARD_18_SRGB} -> ev={ev:+.2f}")
    return 0


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _rect(text: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in text.replace(",", " ").split()]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("rect needs four integers: X,Y,W,H")
    return parts[0], parts[1], parts[2], parts[3]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="StageForge one-time colour calibration")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--capture", action="store_true", help="grab a frame with the chart in view")
    modes.add_argument("--build", action="store_true", help="chart photo -> CCM (+ optional .cube)")
    modes.add_argument(
        "--test-frame", action="store_true", help="apply the profile, save a preview"
    )
    modes.add_argument("--grey", action="store_true", help="18%% grey card -> EV offset")
    modes.add_argument("--quick", action="store_true", help="one shot: chart -> CCM + residual%%")
    parser.add_argument("--input", help="source image (png/jpg)")
    parser.add_argument("--profile", help="CameraProfile JSON (templates in calibration/profiles/)")
    parser.add_argument("--output", dest="profile", help="alias of --profile")
    parser.add_argument("--camera-name", help="record the body name in the profile")
    parser.add_argument("--camera", type=int, default=0, help="cv2 camera index for --capture")
    parser.add_argument(
        "--rect", type=_rect, help="manual chart box X,Y,W,H when auto-detect fails"
    )
    parser.add_argument("--aperture", help="record the dial position, e.g. f/4.0")
    parser.add_argument(
        "--cube", action="store_true", help="also write a .cube and point lut_path at it"
    )
    parser.add_argument("--grid-size", type=int, default=17, help=".cube resolution (default 17)")
    parser.add_argument(
        "--mode", choices=("ccm", "cube"), default="ccm", help="consumer for --test-frame"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.quick:
        if not args.profile:
            raise SystemExit("--quick needs --profile (or --output)")
        return quick(args)
    if args.capture:
        return capture(args)
    if not args.input or not args.profile:
        raise SystemExit("--build / --test-frame / --grey need --input and --profile")
    if args.build:
        return build(args)
    if args.test_frame:
        return test_frame(args)
    return grey(args)


if __name__ == "__main__":
    raise SystemExit(main())
