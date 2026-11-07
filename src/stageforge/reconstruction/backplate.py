"""Offline panorama depth + equirectangular backplate export.

Two pure functions feed the Godot backplate (ADR-0006):

``compute_panorama_depth``
    A monocular depth network eats an equirectangular panorama like any
    other image, but 2:1 rasters are awkward: a 4096x2048 prediction is
    slow and the poles get swamped by sky. So the panorama is processed
    in **tiles** of ``tile_size`` x ``tile_size`` (default 1024) and the
    tiles are stitched back into a full-resolution **uint8** depth map
    (0 = nearest, 255 = farthest) ready for ``cv2.imwrite``.

``project_depth_to_sphere``
    Places ``n_points`` points on a sphere of ``radius`` (default 1.0,
    within ``radius_tol``) and returns their cartesian coordinates plus
    the equirectangular **(u, v)** pixel lookup for each point, so the
    shader can sample the depth/colour texture at the right texel.

This module is deliberately **offline**: no camera, no live frame, just
files on disk. Runtime depth inside the show stays with
``MonocularDepthProvider`` (see ``monocular.py``).

The panorama lives in ``calibration/captures/panoramas/`` (gitignored,
ADR-0005 ``calibration/captures/``); the exported backplate lands in
``assets/generated/backplates/`` (gitignored).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger
from stageforge.reconstruction.monocular import ML_HINT

__all__ = [
    "DEFAULT_TILE_SIZE",
    "compute_panorama_depth",
    "project_depth_to_sphere",
]

DEFAULT_TILE_SIZE = 1024


def _predict(image_rgb: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
    """Run Depth Anything V2 once on a tile and normalise to [0, 1].

    Imports ``transformers`` lazily so the module stays importable in a
    bare environment (same pattern as ``monocular.py``).
    """
    try:
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except ImportError as exc:  # pragma: no cover - only without [ml]
        raise RuntimeError(ML_HINT) from exc

    from stageforge.reconstruction.monocular import DEFAULT_MODEL_ID

    processor = AutoImageProcessor.from_pretrained(DEFAULT_MODEL_ID)  # type: ignore[no-untyped-call]
    model = AutoModelForDepthEstimation.from_pretrained(DEFAULT_MODEL_ID).eval()
    batch = processor(images=image_rgb, return_tensors="pt")
    import torch

    with torch.no_grad():
        outputs = model(**batch)
    predicted = outputs.predicted_depth
    import torch.nn.functional as functional

    height, width = image_rgb.shape[:2]
    depth = functional.interpolate(
        predicted[:, None],
        size=(height, width),
        mode="bicubic",
        align_corners=False,
    )
    raw = np.asarray(depth[0, 0].detach().cpu().numpy(), dtype=np.float32)
    low, high = float(raw.min()), float(raw.max())
    span = high - low
    if span <= 1e-6:
        return np.zeros_like(raw)
    # near_is_high=True: the model emits large = near, flip to 0 = near.
    return np.asarray(np.clip(1.0 - (raw - low) / span, 0.0, 1.0), dtype=np.float32)


def compute_panorama_depth(
    panorama_bgr: npt.NDArray[np.uint8],
    tile_size: int = DEFAULT_TILE_SIZE,
) -> npt.NDArray[np.uint8]:
    """Monocular depth of an equirectangular panorama, as a uint8 tile grid.

    The panorama is split into non-overlapping ``tile_size`` square tiles,
    each predicted independently, then merged. Neighbour seams are not
    blended: for an MVP backplate the occlusion quad only needs ordering,
    not photometric continuity (ADR-0006).

    Args:
        panorama_bgr: ``(H, W, 3)`` uint8 image in **BGR** (cv2.imread order).
        tile_size: edge length of each square tile in pixels; must be > 0.

    Returns:
        ``(H, W)`` uint8 depth map, 0 = nearest, 255 = farthest.

    Raises:
        ValueError: if the image is empty or ``tile_size`` is not positive.
        RuntimeError: if the ``[ml]`` extras are not installed.
    """
    if panorama_bgr.ndim != 3 or panorama_bgr.shape[2] != 3:
        raise ValueError(f"expected (H, W, 3) uint8 panorama, got {panorama_bgr.shape}")
    if tile_size <= 0:
        raise ValueError(f"tile_size must be positive, got {tile_size}")

    height, width = panorama_bgr.shape[:2]
    depth_u8 = np.zeros((height, width), dtype=np.uint8)
    rgb = np.ascontiguousarray(panorama_bgr[..., ::-1])  # OpenCV is BGR

    rows = list(range(0, height, tile_size))
    cols = list(range(0, width, tile_size))
    logger.info(f"panorama depth {width}x{height} in {len(rows)}x{len(cols)} tiles of {tile_size}")

    for top in rows:
        for left in cols:
            tile_rgb = rgb[top : top + tile_size, left : left + tile_size]
            normalised = _predict(tile_rgb)
            depth_u8[top : top + tile_size, left : left + tile_size] = (normalised * 255.0).astype(
                np.uint8
            )

    return depth_u8


def project_depth_to_sphere(
    n_points: int = 100_000,
    radius: float = 1.0,
    radius_tol: float = 1e-3,
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float32]]:
    """Sample ``n_points`` directions on a sphere and return xyz + (u, v).

    Points are distributed with a **fibonacci lattice** (golden-angle
    spiral), which is uniform enough for an occlusion shell and needs no
    random seed - the same ``n_points`` always yields the same cloud.

    ``(u, v)`` are equirectangular texture coordinates in ``[0, 1]``:
    ``u`` sweeps longitude, ``v`` sweeps latitude (0 = +Y pole, 1 = -Y
    pole), so the Godot shader can ``texture(depth_tex, uv)`` directly.

    Args:
        n_points: how many lattice samples to generate (default 100 000).
        radius: sphere radius in metres (default 1.0 - Godot scales it).
        radius_tol: every returned point must satisfy
            ``abs(||xyz|| - radius) <= radius_tol``.

    Returns:
        ``(xyz, uv)`` where ``xyz`` is ``(n, 3)`` float32 cartesian
        coordinates and ``uv`` is ``(n, 2)`` float32 texture coords.

    Raises:
        ValueError: if ``n_points < 2`` or ``radius <= 0``.
    """
    if n_points < 2:
        raise ValueError(f"n_points must be >= 2, got {n_points}")
    if radius <= 0.0:
        raise ValueError(f"radius must be positive, got {radius}")

    indices = np.arange(n_points, dtype=np.float64) + 0.5
    phi = np.arccos(1.0 - 2.0 * indices / n_points)  # polar angle 0..pi
    theta = np.pi * (1.0 + 5.0**0.5) * indices  # golden angle

    sin_phi = np.sin(phi)
    x = sin_phi * np.cos(theta)
    y = np.cos(phi)
    z = sin_phi * np.sin(theta)
    xyz = np.stack((x, y, z), axis=1) * radius

    u = (np.arctan2(z, x) / (2.0 * np.pi) + 1.0) % 1.0
    v = phi / np.pi
    uv = np.stack((u, v), axis=1)

    norms = np.linalg.norm(xyz, axis=1)
    if not np.all(np.abs(norms - radius) <= radius_tol):
        worst = float(np.max(np.abs(norms - radius)))
        raise AssertionError(f"sphere radius drifted by {worst:.6f} > {radius_tol}")

    return (
        np.asarray(xyz, dtype=np.float32),
        np.asarray(uv, dtype=np.float32),
    )
