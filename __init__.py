"""Hermes, Make All my Work Smart!.

A Hermes Desktop plugin that indexes every session across profiles and turns
the archive into a browsable, faceted catalog with canonical titles.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .core.paths import data_dir
from .tools.build_index import build

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


def _on_session_end(**_kwargs: Any) -> None:
    """Refresh the global session index when a session turn ends."""
    try:
        data = build()
        out = data_dir() / "index.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception as exc:  # pragma: no cover — observer hook must never raise
        logger.debug("hermes-make-all-my-work-smart index refresh failed: %s", exc)


def register(ctx: Any) -> None:
    """Register plugin lifecycle hooks with the Hermes host."""
    ctx.register_hook("on_session_end", _on_session_end)

