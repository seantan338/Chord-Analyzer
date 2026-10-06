"""Logging setup."""

from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # numba is extremely chatty at DEBUG level
    logging.getLogger("numba").setLevel(logging.WARNING)
