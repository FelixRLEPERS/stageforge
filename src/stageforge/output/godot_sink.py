"""Godot sink: fill+alpha published into a file-backed shared buffer.

Transport for the Python → Godot leg of ADR-0004, decided in
``docs/06-compositing-ar.md`` (§ "Python → Godot: RGBA stream"):
one slot, one file, seqlock protocol.

Why this and not the obvious alternatives:

* ``multiprocessing.shared_memory`` — anonymous named mappings have no
  API in GDScript; Godot cannot open them at all, so the two sides
  could never meet on one object.
* NDI — the NDI Runtime is not installed on the dev machine
  (``HKLM\\SOFTWARE\\NDI`` absent), so that path cannot be verified
  here. It stays one config switch away: ``output.mode: "ndi"``.

The file needs no daemon, no DLL and no sockets. Python memory-maps it
for writing, Godot reads it with plain ``FileAccess``; on a single
machine the system cache makes writer and reader coherent without an
explicit flush.

File layout (little-endian, 40-byte header)::

    offset  size  field
    0       8     magic  b"SGFRM01\\n"
    8       4     width        (uint32)
    12      4     height       (uint32)
    16      8     seq          (uint64, seqlock: odd = write in progress)
    24      8     timestamp_us (int64, frame stamp from L1)
    32      4     format       (uint32, 0 = RGBA8)
    36      4     padding
    40      ...   width*height*4 RGBA8 pixels (row-major)
"""

from __future__ import annotations

import mmap
import struct
from pathlib import Path
from typing import IO

import numpy as np

from stageforge.core.log import logger
from stageforge.core.types import AlphaMask, Frame
from stageforge.output.base import DeliveryStats, OutputSink, SinkWriteError

__all__ = ["FORMAT_RGBA8", "HEADER_SIZE", "SHM_MAGIC", "GodotOutputSink"]

HEADER = struct.Struct("<8sIIQQI4x")
SHM_MAGIC = b"SGFRM01\n"
FORMAT_RGBA8 = 0
HEADER_SIZE = HEADER.size  # 40
_SEQ_OFFSET = struct.calcsize("<8sII")  # 16 — 8-byte aligned, atomic on x86


class GodotOutputSink(OutputSink):
    """Publishes each composited frame as RGBA into ``shm_path``."""

    def __init__(self, shm_path: str = "out/godot_frame.rgba") -> None:
        self._path = Path(shm_path)
        self._sent = 0
        self._opened = False
        self._file: IO[bytes] | None = None
        self._buffer: mmap.mmap | None = None
        self._size: tuple[int, int] | None = None
        self._seq = 0

    @property
    def path(self) -> Path:
        """Where the shared buffer lives — the file ``receiver.gd`` watches."""
        return self._path

    def open(self) -> None:
        """Create the parent folder. Safe to call twice."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._opened:
            logger.info(f"godot sink open: {self._path}")
        self._opened = True

    def send(self, frame: Frame, key: AlphaMask) -> DeliveryStats:
        """Convert BGR fill + key to RGBA and publish it through the seqlock."""
        if not self._opened:
            raise SinkWriteError("GodotOutputSink.send() before open()")
        data = frame.data
        if data is None:
            raise SinkWriteError(f"frame {frame.camera_id} has no pixels to send")
        expected_fill = (frame.height, frame.width, 3)
        if data.shape != expected_fill:
            raise SinkWriteError(f"fill shape {data.shape} != {expected_fill}")
        expected_key = (frame.height, frame.width)
        if key.data.shape != expected_key:
            raise SinkWriteError(f"key shape {key.data.shape} != {expected_key}")

        try:
            self._map(frame.width, frame.height)
            if self._buffer is None:  # pragma: no cover - _map guarantees it
                raise SinkWriteError(f"godot shm {self._path} not mapped")
            rgba = np.empty((frame.height, frame.width, 4), dtype=np.uint8)
            rgba[:, :, :3] = data[:, :, ::-1]  # BGR → RGB
            rgba[:, :, 3] = key.data  # key = alpha (255 = foreground)
            # seqlock: odd seq = payload in flight, even = coherent slot
            self._seq += 1
            HEADER.pack_into(
                self._buffer,
                0,
                SHM_MAGIC,
                frame.width,
                frame.height,
                self._seq,
                frame.timestamp_us,
                FORMAT_RGBA8,
            )
            self._buffer[HEADER_SIZE : HEADER_SIZE + rgba.nbytes] = rgba.tobytes()
            self._seq += 1
            struct.pack_into("<Q", self._buffer, _SEQ_OFFSET, self._seq)
        except OSError as exc:
            raise SinkWriteError(f"godot shm {self._path}: {exc}") from exc

        self._sent += 1
        return DeliveryStats(sent_frames=self._sent, last_latency_us=0)

    def _map(self, width: int, height: int) -> None:
        """(Re)allocate the slot; a resolution change rebuilds the file."""
        if self._buffer is not None and self._size == (width, height):
            return
        self._unmap()
        total = HEADER_SIZE + width * height * 4
        self._file = self._path.open("w+b")
        self._file.truncate(total)
        self._buffer = mmap.mmap(self._file.fileno(), total, access=mmap.ACCESS_WRITE)
        self._size = (width, height)
        self._seq = 0

    def _unmap(self) -> None:
        """Release the mapping and the handle. Safe when already clean."""
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
        if self._file is not None:
            self._file.close()
            self._file = None
        self._size = None

    def close(self) -> None:
        """Release the mapping. Safe to call twice."""
        self._unmap()
        if self._opened:
            logger.info(f"godot sink closed: sent {self._sent} frames -> {self._path}")
        self._opened = False
