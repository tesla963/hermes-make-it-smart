"""Hermes, Make All my Work Smart!.

A Hermes Desktop plugin that indexes every session across profiles and turns
the archive into a browsable, faceted catalog with canonical titles.
"""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    from .core.paths import data_dir, sync_ui_mirror
    from .tools.build_index import build
    from .tools.cellar_tools import register_tools
except ImportError:
    from core.paths import data_dir, sync_ui_mirror
    from tools.build_index import build
    from tools.cellar_tools import register_tools

__version__ = "0.29.0"

logger = logging.getLogger(__name__)


def _on_session_end(**_kwargs: Any) -> None:
    """Refresh the global session index when a session turn ends."""
    try:
        out = data_dir() / "index.json"
        prev_claves: dict[str, Any] = {}
        if out.exists():
            try:
                prev_data = json.loads(out.read_text(encoding="utf-8"))
                for r in prev_data.get("sessions") or []:
                    if r.get("id") and r.get("claves"):
                        prev_claves[str(r["id"])] = r["claves"]
            except Exception:
                prev_claves = {}
        data = build(with_messages=False)
        for r in data.get("sessions") or []:
            sid = str(r.get("id") or "")
            if not r.get("claves") and sid in prev_claves:
                r["claves"] = prev_claves[sid]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        sync_ui_mirror()
    except Exception as exc:  # pragma: no cover — observer hook must never raise
        logger.debug("hermes-make-it-smart index refresh failed: %s", exc)


def register(ctx: Any) -> None:
    """Register plugin lifecycle hooks and agent tools with the Hermes host."""
    ctx.register_hook("on_session_end", _on_session_end)
    register_tools(ctx)

