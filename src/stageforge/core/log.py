"""Project logger.

``loguru`` is a declared dependency and is used when it is installed,
but the package must also import cleanly in a bare environment (CI
matrix, fresh clone) where only the standard library is guaranteed.
Messages are therefore always pre-formatted f-strings — neither backend
is asked to do lazy ``{}`` / ``%s`` interpolation, so the same call is
valid for both APIs.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised by whichever backend is present
    from loguru import logger as _logger

    logger: Any = _logger
except ImportError:  # pragma: no cover - fallback for bare environments
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    logger = logging.getLogger("stageforge")

__all__ = ["logger"]
