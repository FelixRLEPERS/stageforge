"""Recording raw camera frames for offline debugging (``debug.record_raw``).

When the config asks for it, every Nth *pre-crop* frame is written to
``out/raw_frames/`` as ``cam{index}_frame{ID:06d}.png`` next to a
``manifest.json`` describing what was recorded: per-frame timestamp,
frame id and resolution, plus the reported (config) and measured
(first-to-last observed frame) rate of the source. The point is
test-day triage — what exactly did the capture card deliver (pillarbox
bars, Magic Lantern overlay, compression artefacts) is answerable by
looking at files after the show, without re-running anything.

Recording is strictly opt-in (``debug.record_raw``), best effort (a
failed write is logged, never raised) and never touches the frames the
pipeline consumes: the recorder gets the raw array *before* autocrop,
the source returns its frame untouched. The manifest is merged
read-write, so both cameras of a rig can share one file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from stageforge.core.log import logger

__all__ = ["RawFrameRecorder"]


class RawFrameRecorder:
    """Saves every Nth raw frame plus a merged ``manifest.json``."""

    def __init__(
        self,
        index: int,
        name: str = "",
        out_dir: str = "out/raw_frames",
        fmt: str = "png",
        every_n: int = 30,
        fps_reported: float = 30.0,
    ) -> None:
        if fmt not in ("png", "jpg", "jpeg"):
            raise ValueError(f"unknown raw_format {fmt!r}, expected png or jpeg")
        self._index = index
        self._name = name or f"cam{index}"
        self._dir = Path(out_dir)
        self._ext = "jpg" if fmt in ("jpg", "jpeg") else "png"
        self._every_n = max(1, every_n)
        self._fps_reported = fps_reported
        self._seen = 0
        self._first_us: int | None = None
        self._last_us: int | None = None
        self._entries: list[dict[str, Any]] = []

    @property
    def saved(self) -> int:
        """Number of frames written to disk."""
        return len(self._entries)

    @property
    def manifest_path(self) -> Path:
        """Where the shared manifest of this recording lands."""
        return self._dir / "manifest.json"

    def record(self, frame_id: int, timestamp_us: int, image: npt.NDArray[np.uint8]) -> None:
        """Observe every frame; write the ones on the every-Nth grid."""
        self._seen += 1
        if self._first_us is None:
            self._first_us = timestamp_us
        self._last_us = timestamp_us
        if frame_id % self._every_n != 0:
            return
        name = f"cam{self._index}_frame{frame_id:06d}.{self._ext}"
        if not self._write_image(name, image):
            return
        self._entries.append(
            {
                "file": name,
                "frame_id": frame_id,
                "timestamp_us": timestamp_us,
                "resolution": [int(image.shape[1]), int(image.shape[0])],
            }
        )
        self._flush()

    def close(self) -> None:
        """Write the manifest once more (idempotent; safe to call twice)."""
        if self._seen:
            self._flush()

    def _write_image(self, name: str, image: npt.NDArray[np.uint8]) -> bool:
        """Best-effort frame write: diagnostics never break the pipeline."""
        path = self._dir / name
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            ok = cv2.imwrite(str(path), image)
        except (OSError, cv2.error) as error:
            logger.warning(f"record_raw: cannot write {path}: {error}")
            return False
        if not ok:
            logger.warning(f"record_raw: cv2.imwrite failed for {path}")
            return False
        return True

    def _flush(self) -> None:
        """Merge this camera's block into the shared manifest.json."""
        data: dict[str, Any] = {}
        if self.manifest_path.is_file():
            try:
                loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError) as error:
                logger.warning(f"record_raw: manifest unreadable, starting over: {error}")
        data[f"cam{self._index}"] = {
            "name": self._name,
            "fps_reported": self._fps_reported,
            "fps_actual": self._fps_actual(),
            "frames": self._entries,
        }
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as error:
            logger.warning(f"record_raw: cannot write {self.manifest_path}: {error}")

    def _fps_actual(self) -> float:
        """Measured rate over the observed window (0.0 if under two frames)."""
        if self._seen < 2 or self._first_us is None or self._last_us is None:
            return 0.0
        span_us = self._last_us - self._first_us
        return round((self._seen - 1) / (span_us / 1_000_000), 3) if span_us > 0 else 0.0
