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

__version__ = "0.32.2"

logger = logging.getLogger(__name__)


def _on_session_end(**_kwargs: Any) -> None:
    """Refresh the global session index when a session turn ends."""
    try:
        import importlib
        import sys
        for mod_sfx in ("adapters.hermes", "tools.build_index"):
            for full_name, mod in list(sys.modules.items()):
                if (full_name == mod_sfx or full_name.endswith("." + mod_sfx)) and mod is not None:
                    try:
                        importlib.reload(mod)
                    except Exception:
                        pass
        try:
            from .tools.build_index import build as _fresh_build
        except ImportError:
            from tools.build_index import build as _fresh_build
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
        data = _fresh_build(with_messages=False)
        # Restore claves and last_used_at from previous artefacts if missing
        lu_cache_file = data_dir() / "last_used_cache.json"
        prev_lu: dict[str, Any] = {}
        if lu_cache_file.exists():
            try:
                parsed_lu = json.loads(lu_cache_file.read_text(encoding="utf-8"))
                if isinstance(parsed_lu, dict) and isinstance(parsed_lu.get("by_id"), dict):
                    prev_lu = parsed_lu["by_id"]
            except Exception:
                prev_lu = {}

        for r in data.get("sessions") or []:
            sid = str(r.get("id") or "")
            if not r.get("claves") and sid in prev_claves:
                r["claves"] = prev_claves[sid]
            if r.get("last_used_at") is None and sid in prev_lu:
                r["last_used_at"] = prev_lu[sid]

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        # Atomically update the sidecar last_used_cache.json
        by_id = {
            str(r["id"]): r["last_used_at"]
            for r in (data.get("sessions") or [])
            if r.get("id") and r.get("last_used_at") is not None
        }
        if by_id:
            try:
                (data_dir() / "last_used_cache.json").write_text(
                    json.dumps(
                        {"generated": data.get("generated"), "by_id": by_id},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

        sync_ui_mirror()
    except Exception as exc:  # pragma: no cover — observer hook must never raise
        logger.debug("hermes-make-it-smart index refresh failed: %s", exc)


def register(ctx: Any) -> None:
    """Register plugin lifecycle hooks and agent tools with the Hermes host."""
    ctx.register_hook("on_session_end", _on_session_end)
    register_tools(ctx)

