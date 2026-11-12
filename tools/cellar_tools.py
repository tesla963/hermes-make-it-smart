"""Agent-facing `cellar_*` tools for Hermes, Make All my Work Smart!.

Implements the 10-tool surface specified in ``docs/AGENT-TOOLS.md``:
  Read (4):   cellar_search, cellar_session, cellar_stats, cellar_series
  Write (5):  cellar_rename, cellar_tag, cellar_bateria, cellar_index, cellar_verify
  Export (1): cellar_export

All persistent state lives in ``plugin_data_dir("make-it-smart")``.
``core/`` stays pure and untouched.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from ..adapters.hermes import (
        HermesTitleWriter,
        TitleWriteError,
        attach_messages,
        discover_databases,
        read_sessions,
        sha256_of,
    )
    from ..core.bateria import BATERIA_PATH, load_bateria
    from ..core.classify import ClassifyConfig, classify_one, fallback_facets
    from ..core.normalize import (
        MAX_TITLE_LENGTH,
        Facets,
        core_subject,
        render,
        slug_key,
        validate,
    )
    from ..core.taxonomy import (
        INTENTIONS,
        IT_SUBCATEGORIES,
        OTHER_THEMES,
        PILLARS,
        PLATFORMS,
        THEMES,
        VERBS,
        normalize_context,
        normalize_intention,
        normalize_pillar,
        normalize_platform,
        normalize_theme,
        normalize_verb,
    )
    from .build_index import build, is_human, parse_title
except ImportError:
    from adapters.hermes import (
        HermesTitleWriter,
        TitleWriteError,
        attach_messages,
        discover_databases,
        read_sessions,
        sha256_of,
    )
    from core.bateria import BATERIA_PATH, load_bateria
    from core.classify import ClassifyConfig, classify_one, fallback_facets
    from core.normalize import (
        MAX_TITLE_LENGTH,
        Facets,
        core_subject,
        render,
        slug_key,
        validate,
    )
    from core.taxonomy import (
        INTENTIONS,
        IT_SUBCATEGORIES,
        OTHER_THEMES,
        PILLARS,
        PLATFORMS,
        THEMES,
        VERBS,
        normalize_context,
        normalize_intention,
        normalize_pillar,
        normalize_platform,
        normalize_theme,
        normalize_verb,
    )
    from tools.build_index import build, is_human, parse_title

PLUGIN_NAME = "make-it-smart"
TOOLSET_NAME = "make-it-smart"

DEFAULT_LIMIT = 50
MAX_LIMIT = 500
MAX_BATCH_WRITE = 50


# --------------------------------------------------------------------------- #
# Storage paths (always via plugin_data_dir('make-it-smart'))
# --------------------------------------------------------------------------- #


def _plugin_dir() -> Path:
    """Resolve canonical plugin data directory."""
    try:
        from core.paths import data_dir
        return data_dir(PLUGIN_NAME)
    except ImportError:
        try:
            from ..core.paths import data_dir
            return data_dir(PLUGIN_NAME)
        except Exception:
            from plugins.plugin_storage import plugin_data_dir
            return plugin_data_dir(PLUGIN_NAME)


def _ui_dir() -> Path:
    """Resolve desktop UI mirror directory."""
    try:
        from core.paths import ui_data_dir
        return ui_data_dir(PLUGIN_NAME)
    except ImportError:
        try:
            from ..core.paths import ui_data_dir
            return ui_data_dir(PLUGIN_NAME)
        except Exception:
            return _plugin_dir()


def _index_path() -> Path:
    return _plugin_dir() / "index.json"


def _facets_path() -> Path:
    return _plugin_dir() / "facets.json"


def _corrections_path() -> Path:
    return _plugin_dir() / "corrections.yaml"


def _personal_bateria_path() -> Path:
    return _plugin_dir() / "bateria.personal.yaml"


def _backups_dir() -> Path:
    d = _plugin_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _exports_dir() -> Path:
    d = _plugin_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _next_export_number() -> int:
    ledger = _exports_dir() / "index.json"
    data: dict[str, Any] = {}
    if ledger.exists():
        try:
            data = json.loads(ledger.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
    n = int(data.get("last_export", 0)) + 1
    data["last_export"] = n
    data.setdefault("exports", []).append(n)
    ledger.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return n


# --------------------------------------------------------------------------- #
# Normalization & row helpers
# --------------------------------------------------------------------------- #


def _norm(s: Any) -> str:
    txt = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in txt if not unicodedata.combining(c))


def _is_deleted(r: dict[str, Any]) -> bool:
    sujeto = str(r.get("sujeto") or "")
    title = str(r.get("title") or r.get("raw") or "")
    return bool(
        re.search(r"borrad", sujeto, re.I)
        or re.search(r"\[sesi[oó]n borrada", title, re.I)
    )


def _is_cron(r: dict[str, Any]) -> bool:
    if r.get("esCron") is True:
        return True
    sid = str(r.get("id") or "")
    prof = str(r.get("prof") or "")
    return bool(re.match(r"^cron[_-]", sid, re.I) or re.match(r"^cron[_-]", prof, re.I))


def _is_empty(r: dict[str, Any]) -> bool:
    if "vacia" in r and r["vacia"] is not None:
        return bool(r["vacia"])
    mc = int(r.get("mc") or r.get("posts") or 0)
    claves = r.get("claves") or []
    return mc <= 0 and len(claves) == 0


def _compact_row(r: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical compact row shape defined in docs/AGENT-TOOLS.md."""
    title = str(r.get("title") or r.get("raw") or "").strip()
    iq4 = str(r.get("iq4") or r.get("pilar") or "").strip()
    fecha = str(r.get("fecha") or "")[:10]
    iq5 = str(r.get("iq5") or r.get("anio") or (fecha[:4] if fecha else "")).strip()
    return {
        "n": int(r.get("n") or 0),
        "mmm": int(r.get("mmm") or 1),
        "id": str(r.get("id") or ""),
        "title": title,
        "sujeto": str(r.get("sujeto") or "").strip(),
        "iq1": str(r.get("iq1") or "").strip(),
        "iq2": str(r.get("iq2") or "").strip(),
        "iq3": str(r.get("iq3") or "").strip(),
        "iq4": iq4,
        "iq5": iq5,
        "iq6": str(r.get("iq6") or "").strip(),
        "iq7": str(r.get("iq7") or "").strip(),
        "iq8": str(r.get("iq8") or "").strip(),
        "iq9": str(r.get("iq9") or "").strip(),
        "desc": str(r.get("desc") or "").strip(),
        "verb": str(r.get("verb") or "").strip(),
        "fecha": fecha,
        "costo": round(float(r.get("costo") or 0.0), 4),
        "horas": round(float(r.get("horas") or 0.0), 1),
        "tok": int(r.get("tok") or r.get("tok_tot") or 0),
        "posts": int(r.get("posts") or 0),
        "prof": str(r.get("prof") or "default"),
        "motor": str(r.get("motor") or "").strip(),
        "esCron": _is_cron(r),
        "vacia": _is_empty(r),
    }


def _load_facets_map() -> dict[str, dict[str, Any]]:
    p = _facets_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (ValueError, OSError):
            pass
    # Fallback to global data_dir if active profile dir has no facets.json yet
    from core.paths import data_dir as global_data_dir

    gp = global_data_dir() / "facets.json"
    if gp.exists():
        try:
            data = json.loads(gp.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (ValueError, OSError):
            pass
    return {}


def _save_facets_map(facets: dict[str, dict[str, Any]]) -> None:
    p = _facets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(facets, ensure_ascii=False, indent=1), encoding="utf-8")


def _load_index_data() -> dict[str, Any]:
    p = _index_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                return data
        except (ValueError, OSError):
            pass
    from core.paths import data_dir as global_data_dir

    gp = global_data_dir() / "index.json"
    if gp.exists():
        try:
            data = json.loads(gp.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                return data
        except (ValueError, OSError):
            pass
    # Build fresh index if none exists on disk
    data = build(with_messages=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def _load_merged_rows() -> tuple[list[dict[str, Any]], str]:
    """Return ``(rows, generation)`` enriched with ``facets.json``."""
    idx_data = _load_index_data()
    facets_map = _load_facets_map()
    generation = str(idx_data.get("generated") or "")
    raw_rows = idx_data.get("sessions") or []
    out: list[dict[str, Any]] = []
    for r in raw_rows:
        sid = str(r.get("id") or "")
        ex = facets_map.get(sid) or {}
        merged = dict(r)
        for k in ("sujeto", "iq1", "iq2", "iq3", "iq4", "iq5", "iq6", "iq7", "iq8", "iq9", "pilar", "motor"):
            if not merged.get(k) and ex.get(k):
                merged[k] = ex[k]
        if "mc" not in merged and "mc" in ex:
            merged["mc"] = ex["mc"]
        out.append(merged)
    return out, generation


def _paginate(items: list[Any], limit: Any = DEFAULT_LIMIT, offset: Any = 0) -> tuple[list[Any], int, bool, int, int]:
    try:
        lim = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        lim = DEFAULT_LIMIT
    lim = max(1, min(lim, MAX_LIMIT))
    try:
        off = max(0, int(offset) if offset is not None else 0)
    except (TypeError, ValueError):
        off = 0
    total = len(items)
    sliced = items[off : off + lim]
    truncated = (off + len(sliced)) < total
    return sliced, total, truncated, lim, off


def _parse_num_query(q: str) -> set[int] | None:
    s = (q or "").strip()
    if not s or not re.match(r"^\d+(?:\s*[-,]\s*\d+)*$", s):
        return None
    out: set[int] = set()
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a_str, b_str = [x.strip() for x in part.split("-", 1)]
            a, b = int(a_str), int(b_str)
            lo, hi = min(a, b), max(a, b)
            if hi - lo <= 2000:
                out.update(range(lo, hi + 1))
        else:
            out.add(int(part))
    return out if out else None


def _filter_rows(rows: list[dict[str, Any]], args: dict[str, Any]) -> list[dict[str, Any]]:
    q = str(args.get("q") or "").strip()
    num_set = _parse_num_query(q)
    q_norm = "" if num_set else _norm(q)
    tags = args.get("tags") if isinstance(args.get("tags"), dict) else {}
    date_from = str(args.get("date_from") or "").strip()[:10]
    date_to = str(args.get("date_to") or "").strip()[:10]
    prof = str(args.get("prof") or "").strip().lower()
    motor = str(args.get("motor") or "").strip().lower()
    state = str(args.get("state") or "active").strip().lower()
    if state not in {"active", "cron", "deleted", "empty", "all"}:
        state = "active"

    matched: list[dict[str, Any]] = []
    for raw_r in rows:
        c = _compact_row(raw_r)
        is_del = _is_deleted(raw_r)
        is_cr = c["esCron"]
        is_emp = c["vacia"]

        if state == "active":
            if is_del or is_cr or is_emp:
                continue
        elif state == "cron":
            if not is_cr:
                continue
        elif state == "deleted":
            if not is_del:
                continue
        elif state == "empty":
            if not is_emp:
                continue

        if prof and c["prof"].lower() != prof:
            continue
        if motor and c["motor"].lower() != motor:
            continue
        if date_from and (not c["fecha"] or c["fecha"] < date_from):
            continue
        if date_to and (not c["fecha"] or c["fecha"] > date_to):
            continue

        # Partial tag map filter
        tag_ok = True
        for tk, tv in tags.items():
            if not re.match(r"^tag[1-9]$", str(tk)):
                continue
            if tv is None or tv == "":
                if c.get(tk):
                    tag_ok = False
                    break
            else:
                if _norm(c.get(tk, "")) != _norm(tv):
                    tag_ok = False
                    break
        if not tag_ok:
            continue

        if num_set is not None:
            if c["n"] not in num_set:
                continue
        elif q_norm:
            haystack = _norm(
                " ".join(
                    [
                        c["title"],
                        c["sujeto"],
                        c["desc"],
                        str(raw_r.get("raw") or ""),
                        str(raw_r.get("resumen") or ""),
                        c["iq1"],
                        c["iq2"],
                        c["iq3"],
                        c["iq4"],
                        str(c["n"]),
                        c["id"],
                    ]
                )
            )
            if not all(tok in haystack for tok in q_norm.split()):
                continue

        matched.append(raw_r)

    sort_key = str(args.get("sort") or "fecha_desc").strip().lower()
    if sort_key == "n_asc":
        matched.sort(key=lambda r: int(r.get("n") or 0))
    elif sort_key == "costo_desc":
        matched.sort(key=lambda r: (float(r.get("costo") or 0.0), int(r.get("n") or 0)), reverse=True)
    elif sort_key == "horas_desc":
        matched.sort(key=lambda r: (float(r.get("horas") or 0.0), int(r.get("n") or 0)), reverse=True)
    else:  # fecha_desc (default)
        matched.sort(key=lambda r: (str(r.get("fecha") or ""), int(r.get("n") or 0)), reverse=True)

    return matched


# --------------------------------------------------------------------------- #
# Audit / Backup / Corrections helpers for writes
# --------------------------------------------------------------------------- #


def _caller_session_id(kwargs: dict[str, Any]) -> str:
    if kwargs.get("session_id"):
        return str(kwargs["session_id"])
    parent = kwargs.get("parent_agent")
    if parent is not None and getattr(parent, "session_id", None):
        return str(parent.session_id)
    return "unknown"


def _append_correction(
    *,
    session_id: str,
    tool: str,
    before: Any,
    after: Any,
    rule: str | None = None,
) -> Path:
    path = _corrections_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:
            existing = []
    entry: dict[str, Any] = {
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": session_id,
        "tool": tool,
        "before": before,
        "after": after,
    }
    if rule:
        entry["rule"] = str(rule)
    existing.append(entry)
    path.write_text(
        yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _create_write_backup(reason: str, profiles_touched: set[str] | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    dest = _backups_dir() / f"{stamp}_{reason}"
    dest.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"created_at": stamp, "reason": reason, "files": []}

    # Always back up plugin state files (index.json, facets.json, bateria.personal.yaml, corrections.yaml)
    for state_file in (_index_path(), _facets_path(), _personal_bateria_path(), _corrections_path()):
        if state_file.exists():
            target = dest / state_file.name
            shutil.copy2(state_file, target)
            manifest["files"].append(
                {
                    "kind": "plugin_data",
                    "source": str(state_file),
                    "archive": target.name,
                    "source_sha256": sha256_of(state_file),
                    "source_bytes": state_file.stat().st_size,
                }
            )

    # Back up affected state.db files (gzipped) when profiles_touched is provided
    if profiles_touched:
        for prof, db_path in discover_databases():
            if "*" not in profiles_touched and prof not in profiles_touched:
                continue
            if not db_path.exists():
                continue
            gz_name = f"{prof}.db.gz" if prof != "default" else "state.db.gz"
            target = dest / gz_name
            with open(db_path, "rb") as src, gzip.open(target, "wb", compresslevel=1) as dst:
                shutil.copyfileobj(src, dst)
            manifest["files"].append(
                {
                    "kind": "state_db",
                    "profile": prof,
                    "source": str(db_path),
                    "archive": target.name,
                    "source_sha256": sha256_of(db_path),
                    "source_bytes": db_path.stat().st_size,
                }
            )

    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dest


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# 1. cellar_search
# --------------------------------------------------------------------------- #


def handle_cellar_search(args: dict[str, Any], **_kwargs: Any) -> str:
    rows, _gen = _load_merged_rows()
    matched = _filter_rows(rows, args)
    compact = [_compact_row(r) for r in matched]
    page, total, truncated, lim, off = _paginate(compact, args.get("limit"), args.get("offset"))
    return _json(
        {
            "rows": page,
            "total": total,
            "truncated": truncated,
            "limit": lim,
            "offset": off,
            "query_echo": {
                "q": args.get("q") or "",
                "tags": args.get("tags") or {},
                "date_from": args.get("date_from") or "",
                "date_to": args.get("date_to") or "",
                "prof": args.get("prof") or "",
                "motor": args.get("motor") or "",
                "state": args.get("state") or "active",
                "sort": args.get("sort") or "fecha_desc",
            },
        }
    )


# --------------------------------------------------------------------------- #
# 2. cellar_session
# --------------------------------------------------------------------------- #


def _build_why(c: dict[str, Any]) -> str:
    return (
        f"ADN de la sesión: sujeto {c['sujeto'] or '—'} · "
        f"iq1 {c['iq1'] or '—'} (protagonista) · "
        f"iq2 {c['iq2'] or '—'} (contexto) · "
        f"iq3 {c['iq3'] or '—'} (intención) · "
        f"iq4 {c['iq4'] or '—'} (tema) · "
        f"iq5 {c['iq5'] or '—'} (fecha) · "
        f"iq6 {c['iq6'] or '—'} (máquina)."
    )


def _fetch_live_user_messages(session_id: str, profile: str, limit: int) -> list[str]:
    for prof, db_path in discover_databases():
        if prof != profile:
            continue
        dummy = read_sessions(prof, db_path)
        rec = next((x for x in dummy if x.id == session_id), None)
        if rec is None:
            continue
        import sqlite3

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        try:
            raw_msgs = [
                row[0]
                for row in conn.execute(
                    "SELECT content FROM messages WHERE session_id = ? AND role = 'user' ORDER BY rowid LIMIT 80",
                    (session_id,),
                )
            ]
        finally:
            conn.close()
        cleaned = [re.sub(r"\s+", " ", m).strip()[:400] for m in raw_msgs if is_human(m)]
        return cleaned[:limit]
    return []


def handle_cellar_session(args: dict[str, Any], **_kwargs: Any) -> str:
    n_val = args.get("n")
    id_val = str(args.get("id") or "").strip()
    if n_val is None and not id_val:
        return _json({"ok": False, "error": "Provide either 'n' or 'id'."})

    rows, generation = _load_merged_rows()
    target: dict[str, Any] | None = None
    if n_val is not None:
        try:
            n_int = int(n_val)
            target = next((r for r in rows if int(r.get("n") or 0) == n_int), None)
        except (TypeError, ValueError):
            pass
    if target is None and id_val:
        target = next((r for r in rows if str(r.get("id") or "") == id_val), None)

    if target is None:
        return _json({"ok": False, "error": f"Session not found (n={n_val!r}, id={id_val!r})."})

    c = _compact_row(target)
    include_messages = bool(args.get("include_messages", False))
    include_why = bool(args.get("include_why", True))
    try:
        msg_limit = max(1, min(50, int(args.get("messages_limit", 12))))
    except (TypeError, ValueError):
        msg_limit = 12

    out: dict[str, Any] = {"ok": True, **c, "row": c, "index_generation": generation}
    if include_why:
        out["why"] = _build_why(c)
    if include_messages:
        cached = [str(x) for x in (target.get("claves") or []) if is_human(str(x))]
        live = _fetch_live_user_messages(c["id"], c["prof"], msg_limit)
        out["messages"] = (live or cached)[:msg_limit]
    return _json(out)


# --------------------------------------------------------------------------- #
# 3. cellar_stats
# --------------------------------------------------------------------------- #


def handle_cellar_stats(args: dict[str, Any], **_kwargs: Any) -> str:
    rows, _gen = _load_merged_rows()
    matched = [_compact_row(r) for r in _filter_rows(rows, args)]

    sum_costo = round(sum(r["costo"] for r in matched), 4)
    sum_horas = round(sum(r["horas"] for r in matched), 1)
    sum_tok = sum(r["tok"] for r in matched)
    sum_posts = sum(r["posts"] for r in matched)

    all_axes = ("iq1", "iq2", "iq3", "iq4", "fecha_year", "prof")
    requested_facets = args.get("facets")
    if isinstance(requested_facets, list) and requested_facets:
        axes = [str(a) for a in requested_facets if str(a) in all_axes or re.match(r"^tag[1-9]$", str(a))]
    else:
        axes = list(all_axes)

    by_facet: dict[str, dict[str, int]] = {}
    for ax in axes:
        cnt: Counter[str] = Counter()
        for r in matched:
            if ax == "fecha_year":
                val = (r["fecha"] or "")[:4]
            else:
                val = str(r.get(ax) or "")
            if val:
                cnt[val] += 1
        by_facet[ax] = dict(cnt.most_common())

    empty_counts = {
        f"tag{i}": sum(1 for r in matched if not r.get(f"tag{i}"))
        for i in range(1, 10)
    }

    return _json(
        {
            "count": len(matched),
            "sum": {
                "costo": sum_costo,
                "horas": sum_horas,
                "tok": sum_tok,
                "posts": sum_posts,
            },
            "by_facet": by_facet,
            "empty_counts": empty_counts,
        }
    )


# --------------------------------------------------------------------------- #
# 4. cellar_series
# --------------------------------------------------------------------------- #


def handle_cellar_series(args: dict[str, Any], **_kwargs: Any) -> str:
    subj_arg = str(args.get("subject") or "").strip()
    n_arg = args.get("n")
    if not subj_arg and n_arg is None:
        return _json({"ok": False, "error": "Provide either 'subject' or 'n'."})

    rows, _gen = _load_merged_rows()
    if not subj_arg and n_arg is not None:
        try:
            n_int = int(n_arg)
            seed = next((r for r in rows if int(r.get("n") or 0) == n_int), None)
            if seed is not None:
                subj_arg = str(seed.get("sujeto") or "").strip()
        except (TypeError, ValueError):
            pass

    if not subj_arg:
        return _json({"ok": False, "error": f"Could not resolve subject from n={n_arg!r}."})

    target_slug = slug_key(core_subject(subj_arg) or subj_arg)
    series_raw = [
        r
        for r in rows
        if slug_key(core_subject(str(r.get("sujeto") or "")) or str(r.get("sujeto") or "")) == target_slug
    ]
    series_compact = [_compact_row(r) for r in series_raw]
    series_compact.sort(key=lambda r: (r["mmm"], r["n"]))

    mmms = sorted({r["mmm"] for r in series_compact if r["mmm"] > 0})
    if mmms:
        mmm_range = [mmms[0], mmms[-1]]
        gaps = [m for m in range(1, mmms[-1] + 1) if m not in mmms]
    else:
        mmm_range = [0, 0]
        gaps = []

    canonical_subject = series_compact[0]["sujeto"] if series_compact else subj_arg
    totals = {
        "count": len(series_compact),
        "costo": round(sum(r["costo"] for r in series_compact), 4),
        "horas": round(sum(r["horas"] for r in series_compact), 1),
        "tok": sum(r["tok"] for r in series_compact),
        "posts": sum(r["posts"] for r in series_compact),
    }

    page, total, truncated, lim, off = _paginate(
        series_compact, args.get("limit"), args.get("offset")
    )
    return _json(
        {
            "ok": True,
            "subject": canonical_subject,
            "mmm_range": mmm_range,
            "rows": page,
            "total": total,
            "truncated": truncated,
            "limit": lim,
            "offset": off,
            "totals": totals,
            "gaps": gaps,
        }
    )


# --------------------------------------------------------------------------- #
# 8. cellar_index
# --------------------------------------------------------------------------- #


def _resolve_deepseek_key() -> str:
    auth_path = Path.home() / ".hermes" / "auth.json"
    if auth_path.exists():
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
            pool = data.get("credential_pool", {}).get("deepseek") or []
            for entry in pool:
                tok = entry.get("access_token") or entry.get("api_key")
                if tok:
                    return str(tok)
        except Exception:
            pass
    return ""


def _scan_live_sessions() -> list[dict[str, Any]]:
    live: list[dict[str, Any]] = []
    seen: set[str] = set()
    for prof, db_path in discover_databases():
        for rec in read_sessions(prof, db_path):
            if rec.id in seen:
                continue
            seen.add(rec.id)
            title = (rec.title or "").strip()
            m = parse_title(title)
            live.append(
                {
                    "id": rec.id,
                    "prof": prof,
                    "db_path": str(db_path),
                    "title": title,
                    "fecha": str(rec.created_at or "")[:10],
                    "posts": int(rec.posts or 0),
                    "untitled": m is None,
                    "record": rec,
                }
            )
    return live


def handle_cellar_index(args: dict[str, Any], **_kwargs: Any) -> str:
    op = str(args.get("op") or "status").strip().lower()
    if op not in {"status", "detect", "rebuild", "classify"}:
        return _json({"ok": False, "error": f"Invalid op {op!r}; expected status|detect|rebuild|classify."})

    idx_data = _load_index_data()
    indexed_rows = idx_data.get("sessions") or []
    idx_by_id = {str(r.get("id") or ""): r for r in indexed_rows}
    generation = str(idx_data.get("generated") or "")

    live = _scan_live_sessions()
    new_list: list[dict[str, Any]] = []
    changed_list: list[dict[str, Any]] = []
    untitled_list: list[dict[str, Any]] = []

    for item in live:
        sid = item["id"]
        prev = idx_by_id.get(sid)
        if prev is None:
            new_list.append(item)
        elif str(prev.get("raw") or "").strip() != item["title"]:
            changed_list.append(item)
        if item["untitled"]:
            untitled_list.append(item)

    counts = {
        "total": len(live),
        "indexed": len(indexed_rows),
        "new": len(new_list),
        "changed": len(changed_list),
        "untitled": len(untitled_list),
        "classified": len(live) - len(untitled_list),
    }

    if op == "status":
        age_seconds = None
        if generation:
            try:
                gen_dt = datetime.fromisoformat(generation)
                age_seconds = max(0, int((datetime.now() - gen_dt).total_seconds()))
            except ValueError:
                age_seconds = None
        return _json(
            {
                "ok": True,
                "op": "status",
                "generation": generation,
                "age_seconds": age_seconds,
                "counts": counts,
                "proposals": [],
            }
        )

    if op == "detect":
        proposals = [
            {
                "id": x["id"],
                "prof": x["prof"],
                "fecha": x["fecha"],
                "title": x["title"],
                "change": "new" if x["id"] not in idx_by_id else "title_changed",
                "untitled": x["untitled"],
            }
            for x in (new_list + changed_list)[:MAX_LIMIT]
        ]
        return _json(
            {
                "ok": True,
                "op": "detect",
                "generation": generation,
                "counts": counts,
                "proposals": proposals,
            }
        )

    if op == "rebuild":
        backup_dir = _create_write_backup("cellar_index_rebuild")
        prev_claves = {
            str(r.get("id") or ""): r.get("claves")
            for r in indexed_rows
            if r.get("claves")
        }
        rebuilt = build(with_messages=False)
        facets_map = _load_facets_map()
        for r in rebuilt.get("sessions") or []:
            sid = str(r.get("id") or "")
            if not r.get("claves") and sid in prev_claves:
                r["claves"] = prev_claves[sid]
            ex = facets_map.get(sid) or {}
            for k in ("sujeto", "iq1", "iq2", "iq3", "iq4", "iq5", "iq6", "iq7", "iq8", "iq9", "pilar", "motor"):
                if not r.get(k) and ex.get(k):
                    r[k] = ex[k]
        out_path = _index_path()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(rebuilt, ensure_ascii=False, separators=(",", ":"))
        out_path.write_text(content, encoding="utf-8")
        try:
            ui_path = _ui_dir() / "index.json"
            ui_path.parent.mkdir(parents=True, exist_ok=True)
            ui_path.write_text(content, encoding="utf-8")
        except Exception:
            pass
        try:
            can_facets = _facets_path()
            if can_facets.exists():
                ui_facets = _ui_dir() / "facets.json"
                ui_facets.parent.mkdir(parents=True, exist_ok=True)
                ui_facets.write_text(can_facets.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
        rebuilt_rows = rebuilt.get("sessions") or []
        untitled_after = sum(1 for r in rebuilt_rows if not parse_title(str(r.get("raw") or "")))
        return _json(
            {
                "ok": True,
                "op": "rebuild",
                "generation": rebuilt.get("generated"),
                "counts": {
                    "total": len(rebuilt_rows),
                    "new": len(new_list),
                    "changed": len(changed_list),
                    "untitled": untitled_after,
                    "classified": len(rebuilt_rows) - untitled_after,
                },
                "proposals": [],
                "backup_path": str(backup_dir),
            }
        )

    # op == "classify"
    try:
        lim = max(1, min(100, int(args.get("limit", 25))))
    except (TypeError, ValueError):
        lim = 25

    key = _resolve_deepseek_key()
    cfg = ClassifyConfig(api_key=key or "offline", model="deepseek-chat", temperature=0.0, language="es")
    max_n = max((int(r.get("n") or 0) for r in indexed_rows), default=0)
    subj_counts: Counter[str] = Counter(
        slug_key(str(r.get("sujeto") or ""))
        for r in indexed_rows
        if r.get("sujeto")
    )

    proposals: list[dict[str, Any]] = []
    for idx_u, item in enumerate(untitled_list[:lim], 1):
        rec = attach_messages(item["record"], Path(item["db_path"]))
        turns = [re.sub(r"\s+", " ", m).strip()[:600] for m in (rec.messages or []) if is_human(m)]
        prev_row = idx_by_id.get(item["id"])
        n_assigned = int(prev_row["n"]) if prev_row and prev_row.get("n") else (max_n + idx_u)

        if key and turns:
            res = classify_one(
                messages=turns,
                config=cfg,
                date=item["fecha"],
                current_title=item["title"],
                ordinal=1,
            )
            f = res.facets or fallback_facets(turns, ordinal=1)
            used_fallback = bool(res.used_fallback or not res.ok)
        else:
            f = fallback_facets(turns or [item["title"] or "Sesión"], ordinal=1)
            used_fallback = True

        s_slug = slug_key(f.subject)
        mmm = subj_counts[s_slug] + 1 if s_slug else 1
        f_with_mmm = Facets(
            subject=f.subject or "Sesión",
            subject_ordinal=mmm,
            iq1=f.iq1,
            iq2=f.iq2,
            iq3=f.iq3,
            iq4=f.iq4,
            iq5=f.iq5 or (item["fecha"][:4] if item["fecha"] else ""),
            iq6=f.iq6,
            description=f.description,
            verb=f.verb,
        )
        proposed_title = render(n_assigned, f_with_mmm)
        proposals.append(
            {
                "n": n_assigned,
                "id": item["id"],
                "prof": item["prof"],
                "old_title": item["title"],
                "proposed_title": proposed_title,
                "used_fallback": used_fallback,
                "fields": {
                    "sujeto": f_with_mmm.subject,
                    "mmm": mmm,
                    "iq1": f_with_mmm.iq1,
                    "iq2": f_with_mmm.iq2,
                    "iq3": f_with_mmm.iq3,
                    "iq4": f_with_mmm.iq4,
                    "iq5": f_with_mmm.iq5,
                    "desc": f_with_mmm.description,
                    "verb": f_with_mmm.verb,
                },
            }
        )

    return _json(
        {
            "ok": True,
            "op": "classify",
            "counts": {
                "new": len(new_list),
                "changed": len(changed_list),
                "untitled": len(untitled_list),
                "classified": len(proposals),
            },
            "proposals": proposals,
        }
    )


# --------------------------------------------------------------------------- #
# 9. cellar_verify
# --------------------------------------------------------------------------- #


def _known_tag1_set() -> set[str]:
    known = {p.lower() for p in PLATFORMS if p}
    known.update({"bot", "cron"})
    for b in (load_bateria(), _load_personal_bateria()):
        for key, spec in (b.get("marcas") or {}).items():
            known.add(str(key).lower())
            if isinstance(spec, dict) and spec.get("iq1"):
                known.add(str(spec["iq1"]).lower())
        for key, spec in (b.get("programas") or {}).items():
            known.add(str(key).lower())
            if isinstance(spec, dict) and spec.get("marca"):
                known.add(str(spec["marca"]).lower())
        for key, spec in (b.get("companias") or {}).items():
            known.add(str(key).lower())
            if isinstance(spec, dict) and spec.get("nombre"):
                known.add(str(spec["nombre"]).lower())
    return known


def handle_cellar_verify(args: dict[str, Any], **_kwargs: Any) -> str:
    rows, _gen = _load_merged_rows()
    if any(k in args for k in ("q", "tags", "date_from", "date_to", "prof", "motor", "state")):
        rows = _filter_rows(rows, {**args, "state": args.get("state") or "all"})

    offenders: list[dict[str, Any]] = []
    by_rule: Counter[str] = Counter()

    def flag(c: dict[str, Any], rule: str, detail: str) -> None:
        by_rule[rule] += 1
        offenders.append({"n": c["n"], "id": c["id"], "rule": rule, "detail": detail})

    known_iq1 = _known_tag1_set()
    valid_iq3 = {x.lower() for x in INTENTIONS}
    valid_iq4 = {x.lower() for x in (*THEMES, *IT_SUBCATEGORIES, *PILLARS)}

    nnn_seen: dict[int, list[dict[str, Any]]] = defaultdict(list)
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw_r in rows:
        if _is_deleted(raw_r) or _is_cron(raw_r):
            continue
        c = _compact_row(raw_r)
        title = c["title"]

        # 1. Title length <= 100
        if len(title) > MAX_TITLE_LENGTH:
            flag(c, "title_length", f"{len(title)} chars > {MAX_TITLE_LENGTH}")

        # Track NNN uniqueness and MMM series
        if c["n"] > 0:
            nnn_seen[c["n"]].append(c)
        if c["sujeto"]:
            by_subject[slug_key(core_subject(c["sujeto"]) or c["sujeto"])].append(c)

        # 4. iq3 inside the 7 intentions
        if c["iq3"] and c["iq3"].lower() not in valid_iq3:
            flag(c, "tag3_vocabulary", f"iq3={c['iq3']!r} not in 7 intentions")

        # 5. iq4 inside themes
        if c["iq4"] and c["iq4"].lower() not in valid_iq4:
            flag(c, "tag4_vocabulary", f"iq4={c['iq4']!r} not in closed themes")

        # 6. iq1 present in bateria or empty
        if c["iq1"] and c["iq1"].lower() not in known_iq1:
            flag(c, "tag1_bateria", f"iq1={c['iq1']!r} not in bateria")

        # 7. Subject not equal to iq1 (unless subject has a version suffix)
        if c["sujeto"] and c["iq1"]:
            s_clean = slug_key(core_subject(c["sujeto"]) or c["sujeto"])
            t1_clean = slug_key(c["iq1"])
            if s_clean == t1_clean:
                flag(c, "subject_repeats_iq1", f"sujeto={c['sujeto']!r} repeats iq1={c['iq1']!r}")

        # 8. Description present when fields cannot say it
        if not c["vacia"] and not c["desc"] and not c["verb"]:
            flag(c, "missing_description", "empty desc and verb on non-empty session")

    # 2. NNN unique
    for n_val, group in nnn_seen.items():
        if len(group) > 1:
            ids = ", ".join(x["id"] for x in group)
            for x in group:
                flag(x, "nnn_unique", f"duplicate NNN={n_val} shared by [{ids}]")

    # 3. MMM without gaps per subject
    for _slug, group in by_subject.items():
        mmms = sorted(x["mmm"] for x in group if x["mmm"] > 0)
        if not mmms:
            continue
        expected = list(range(1, len(mmms) + 1))
        if mmms != expected:
            sample = group[0]
            flag(
                sample,
                "mmm_gaps",
                f"subject {sample['sujeto']!r} has MMM sequence {mmms[:12]} (expected 1..{len(mmms)})",
            )

    page, total, truncated, lim, off = _paginate(
        offenders, args.get("limit", 100), args.get("offset", 0)
    )
    return _json(
        {
            "ok": total == 0,
            "offenders": page,
            "total": total,
            "truncated": truncated,
            "limit": lim,
            "offset": off,
            "summary": {"by_rule": dict(by_rule.most_common())},
        }
    )


# --------------------------------------------------------------------------- #
# Selector resolution for cellar_rename & cellar_tag
# --------------------------------------------------------------------------- #


def _resolve_target_rows(
    rows: list[dict[str, Any]], args: dict[str, Any]
) -> tuple[list[dict[str, Any]], str | None]:
    selector = args.get("selector") if isinstance(args.get("selector"), dict) else args
    n_sel = selector.get("n", args.get("n"))
    id_sel = selector.get("id", args.get("id"))
    filt = selector.get("filter", args.get("filter"))

    if n_sel is not None:
        if isinstance(n_sel, list):
            n_set = {int(x) for x in n_sel}
        else:
            n_set = {int(n_sel)}
        matched = [r for r in rows if int(r.get("n") or 0) in n_set]
        return matched[:MAX_BATCH_WRITE], None

    if id_sel is not None:
        if isinstance(id_sel, list):
            id_set = {str(x) for x in id_sel}
        else:
            id_set = {str(id_sel)}
        matched = [r for r in rows if str(r.get("id") or "") in id_set]
        return matched[:MAX_BATCH_WRITE], None

    if isinstance(filt, dict):
        matched = _filter_rows(rows, filt)
        if len(matched) > MAX_BATCH_WRITE:
            return matched[:MAX_BATCH_WRITE], None
        return matched, None

    return [], "Provide a selector: 'n', 'id', or 'filter'."


def _db_map_by_profile() -> dict[str, Path]:
    return {prof: path for prof, path in discover_databases()}


# --------------------------------------------------------------------------- #
# 5. cellar_rename
# --------------------------------------------------------------------------- #


def handle_cellar_rename(args: dict[str, Any], **kwargs: Any) -> str:
    dry_run = bool(args.get("dry_run", True))
    confirm = bool(args.get("confirm", False))
    fields_arg = args.get("fields") if isinstance(args.get("fields"), dict) else None
    literal_title = str(args.get("title") or "").strip() if args.get("title") is not None else None

    if not fields_arg and not literal_title:
        return _json({"ok": False, "error": "Provide either 'fields' or 'title'."})

    rows, gen_before = _load_merged_rows()
    targets, sel_err = _resolve_target_rows(rows, args)
    if sel_err:
        return _json({"ok": False, "error": sel_err})

    preview: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    candidates: list[tuple[dict[str, Any], str, dict[str, Any]]] = []

    for r in targets:
        c = _compact_row(r)
        if fields_arg is not None:
            sujeto = str(fields_arg.get("sujeto") if "sujeto" in fields_arg else c["sujeto"]).strip()
            mmm = int(fields_arg.get("mmm") if "mmm" in fields_arg and fields_arg.get("mmm") else c["mmm"] or 1)
            iq1 = str(fields_arg.get("iq1") if "iq1" in fields_arg else c["iq1"]).strip()
            iq2 = str(fields_arg.get("iq2") if "iq2" in fields_arg else c["iq2"]).strip()
            desc = str(fields_arg.get("desc") if "desc" in fields_arg else c["desc"]).strip()
            verb = str(fields_arg.get("verb") if "verb" in fields_arg else c["verb"]).strip()
            f_obj = Facets(
                subject=sujeto,
                subject_ordinal=mmm,
                iq1=iq1,
                iq2=iq2,
                description=desc,
                verb=verb,
            )
            new_title = render(c["n"], f_obj)
            new_tags = {
                "sujeto": core_subject(sujeto) or sujeto,
                "mmm": mmm,
                "iq1": iq1,
                "iq2": iq2,
                "desc": desc,
                "verb": verb,
            }
            for tk in ("iq3", "iq4", "iq5", "iq6", "iq7", "iq8", "iq9"):
                if tk in fields_arg:
                    new_tags[tk] = "" if fields_arg[tk] is None else str(fields_arg[tk]).strip()
        else:
            new_title = literal_title or ""
            probs = validate(new_title)
            if len(new_title) > MAX_TITLE_LENGTH:
                rejected.append({"n": c["n"], "id": c["id"], "reason": f"title is {len(new_title)} chars (> 100)"})
                continue
            m = parse_title(new_title)
            if not m:
                rejected.append({"n": c["n"], "id": c["id"], "reason": "title does not match canonical NNN [Sujeto] MMM format"})
                continue
            if probs:
                rejected.append({"n": c["n"], "id": c["id"], "reason": "; ".join(probs)})
                continue
            gd = m.groupdict()
            new_tags = {
                "sujeto": (gd.get("subject") or "").strip(),
                "mmm": int(gd.get("mmm") or 1),
                "iq1": (gd.get("iq1") or "").strip(),
                "iq2": (gd.get("iq2") or "").strip(),
                "desc": (gd.get("desc") or "").strip(),
                "verb": (gd.get("verb") or "").strip(),
            }

        if len(new_title) > MAX_TITLE_LENGTH:
            rejected.append({"n": c["n"], "id": c["id"], "reason": f"title is {len(new_title)} chars (> 100)"})
            continue

        preview.append(
            {
                "n": c["n"],
                "id": c["id"],
                "prof": c["prof"],
                "before": c["title"],
                "after": new_title,
                "fields_after": new_tags,
            }
        )
        candidates.append((c, new_title, new_tags))

    if not confirm:
        return _json(
            {
                "ok": False,
                "reason": "confirm required",
                "dry_run": dry_run,
                "changed": 0,
                "preview": preview,
                "backup_path": None,
                "receipt": None,
                "rejected": rejected,
            }
        )

    if dry_run:
        return _json(
            {
                "ok": True,
                "dry_run": True,
                "changed": 0,
                "preview": preview,
                "backup_path": None,
                "receipt": None,
                "rejected": rejected,
            }
        )

    profiles_touched = {c["prof"] for c, _, _ in candidates}
    backup_dir = _create_write_backup("cellar_rename", profiles_touched)
    db_map = _db_map_by_profile()
    facets_map = _load_facets_map()
    idx_data = _load_index_data()
    idx_by_id = {str(r.get("id") or ""): r for r in (idx_data.get("sessions") or [])}

    writer: HermesTitleWriter | None = None
    try:
        writer = HermesTitleWriter()
    except TitleWriteError as exc:
        return _json({"ok": False, "error": str(exc), "backup_path": str(backup_dir)})

    applied_before: list[dict[str, Any]] = []
    applied_after: list[dict[str, Any]] = []

    for c, new_title, new_tags in candidates:
        db_path = db_map.get(c["prof"])
        try:
            wrote = writer.rename(c["id"], new_title, db_path)
        except Exception as exc:
            rejected.append({"n": c["n"], "id": c["id"], "reason": str(exc)})
            continue
        if not wrote:
            rejected.append({"n": c["n"], "id": c["id"], "reason": "host refused or session not found in profile db"})
            continue

        applied_before.append({"n": c["n"], "id": c["id"], "title": c["title"]})
        applied_after.append({"n": c["n"], "id": c["id"], "title": new_title, "fields": new_tags})

        ex = facets_map.setdefault(c["id"], {})
        ex.update(new_tags)
        if "iq4" in new_tags:
            ex["pilar"] = new_tags["iq4"]

        if c["id"] in idx_by_id:
            ir = idx_by_id[c["id"]]
            ir["raw"] = new_title
            ir.update(new_tags)

    gen_after = datetime.now().isoformat(timespec="seconds")
    idx_data["generated"] = gen_after
    _save_facets_map(facets_map)
    _index_path().write_text(
        json.dumps(idx_data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    _append_correction(
        session_id=_caller_session_id(kwargs),
        tool="cellar_rename",
        before=applied_before,
        after=applied_after,
        rule=args.get("rule"),
    )

    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_touched": len(applied_after),
        "generation_before": gen_before,
        "generation_after": gen_after,
    }
    return _json(
        {
            "ok": True,
            "dry_run": False,
            "changed": len(applied_after),
            "preview": preview,
            "backup_path": str(backup_dir),
            "receipt": receipt,
            "rejected": rejected,
        }
    )


# --------------------------------------------------------------------------- #
# 6. cellar_tag
# --------------------------------------------------------------------------- #


def handle_cellar_tag(args: dict[str, Any], **kwargs: Any) -> str:
    dry_run = bool(args.get("dry_run", True))
    confirm = bool(args.get("confirm", False))
    tag_set = args.get("set")
    if not isinstance(tag_set, dict) or not tag_set:
        return _json({"ok": False, "error": "Provide a non-empty 'set' mapping of tags (iq1..iq9)."})

    valid_changes: dict[str, str] = {}
    for k, v in tag_set.items():
        if re.match(r"^tag[1-9]$", str(k)):
            valid_changes[str(k)] = "" if v is None else str(v).strip()

    if not valid_changes:
        return _json({"ok": False, "error": "No valid tag keys (iq1..iq9) found in 'set'."})

    rows, gen_before = _load_merged_rows()
    targets, sel_err = _resolve_target_rows(rows, args)
    if sel_err:
        return _json({"ok": False, "error": sel_err})

    preview: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    candidates: list[tuple[dict[str, Any], dict[str, str], dict[str, str], str | None]] = []

    for r in targets:
        c = _compact_row(r)
        before_tags = {k: c.get(k, "") for k in valid_changes}
        after_tags = dict(valid_changes)

        # If iq1 or iq2 changed and session has a canonical title, re-render the title
        new_title: str | None = None
        if ("iq1" in valid_changes or "iq2" in valid_changes) and parse_title(c["title"]):
            f_obj = Facets(
                subject=c["sujeto"],
                subject_ordinal=c["mmm"],
                iq1=after_tags.get("iq1", c["iq1"]),
                iq2=after_tags.get("iq2", c["iq2"]),
                description=c["desc"],
                verb=c["verb"],
            )
            rendered = render(c["n"], f_obj)
            if len(rendered) > MAX_TITLE_LENGTH:
                rejected.append({"n": c["n"], "id": c["id"], "reason": f"re-rendered title is {len(rendered)} chars (> 100)"})
                continue
            if rendered != c["title"]:
                new_title = rendered

        preview.append(
            {
                "n": c["n"],
                "id": c["id"],
                "prof": c["prof"],
                "before": before_tags,
                "after": after_tags,
                "title_before": c["title"],
                "title_after": new_title or c["title"],
            }
        )
        candidates.append((c, before_tags, after_tags, new_title))

    if not confirm:
        return _json(
            {
                "ok": False,
                "reason": "confirm required",
                "dry_run": dry_run,
                "changed": 0,
                "preview": preview,
                "backup_path": None,
                "receipt": None,
                "rejected": rejected,
            }
        )

    if dry_run:
        return _json(
            {
                "ok": True,
                "dry_run": True,
                "changed": 0,
                "preview": preview,
                "backup_path": None,
                "receipt": None,
                "rejected": rejected,
            }
        )

    profiles_touched = {c["prof"] for c, _, _, nt in candidates if nt is not None}
    backup_dir = _create_write_backup("cellar_tag", profiles_touched or None)
    db_map = _db_map_by_profile()
    facets_map = _load_facets_map()
    idx_data = _load_index_data()
    idx_by_id = {str(r.get("id") or ""): r for r in (idx_data.get("sessions") or [])}

    writer: HermesTitleWriter | None = None
    if profiles_touched:
        try:
            writer = HermesTitleWriter()
        except TitleWriteError:
            writer = None

    applied_before: list[dict[str, Any]] = []
    applied_after: list[dict[str, Any]] = []

    for c, before_tags, after_tags, new_title in candidates:
        if new_title is not None and writer is not None:
            try:
                writer.rename(c["id"], new_title, db_map.get(c["prof"]))
            except Exception as exc:
                rejected.append({"n": c["n"], "id": c["id"], "reason": str(exc)})
                continue

        ex = facets_map.setdefault(c["id"], {})
        ex.update(after_tags)
        if "iq4" in after_tags:
            ex["pilar"] = after_tags["iq4"]

        if c["id"] in idx_by_id:
            ir = idx_by_id[c["id"]]
            ir.update(after_tags)
            if "iq4" in after_tags:
                ir["pilar"] = after_tags["iq4"]
            if new_title is not None:
                ir["raw"] = new_title

        applied_before.append({"n": c["n"], "id": c["id"], "tags": before_tags})
        applied_after.append({"n": c["n"], "id": c["id"], "tags": after_tags})

    gen_after = datetime.now().isoformat(timespec="seconds")
    idx_data["generated"] = gen_after
    _save_facets_map(facets_map)
    _index_path().write_text(
        json.dumps(idx_data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    _append_correction(
        session_id=_caller_session_id(kwargs),
        tool="cellar_tag",
        before=applied_before,
        after=applied_after,
        rule=args.get("rule"),
    )

    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_touched": len(applied_after),
        "generation_before": gen_before,
        "generation_after": gen_after,
    }
    return _json(
        {
            "ok": True,
            "dry_run": False,
            "changed": len(applied_after),
            "preview": preview,
            "backup_path": str(backup_dir),
            "receipt": receipt,
            "rejected": rejected,
        }
    )


# --------------------------------------------------------------------------- #
# 7. cellar_bateria
# --------------------------------------------------------------------------- #

_BATERIA_SECTIONS = (
    "marcas",
    "programas",
    "productos",
    "companias",
    "servicios",
    "conceptos",
    "logistica",
    "sin_marca",
    "preferencias_envio",
    "vocabulario",
    "reglas",
)


def _load_personal_bateria() -> dict[str, Any]:
    p = _personal_bateria_path()
    if not p.exists():
        # First install: copy template from core/bateria.personal.yaml preserving header comment
        repo_seed = BATERIA_PATH.with_name("bateria.personal.yaml")
        if repo_seed.exists():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(repo_seed.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
        else:
            return {"version": 1, "owner": "jorge", "vocabulario": {}, "reglas": {}, "servicios": {}}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merged_bateria(include_removed: bool = False) -> dict[str, Any]:
    base = load_bateria()
    personal = _load_personal_bateria()
    merged: dict[str, Any] = {}
    for sec in _BATERIA_SECTIONS:
        b_sec = base.get(sec)
        p_sec = personal.get(sec)
        if isinstance(b_sec, dict) or isinstance(p_sec, dict):
            combined: dict[str, Any] = {}
            if isinstance(b_sec, dict):
                combined.update(b_sec)
            if isinstance(p_sec, dict):
                for k, v in p_sec.items():
                    if not include_removed and isinstance(v, dict) and v.get("removed") is True:
                        combined.pop(k, None)
                        continue
                    combined[k] = v
            merged[sec] = combined
        elif isinstance(p_sec, list) or isinstance(b_sec, list):
            merged[sec] = list(b_sec or []) + list(p_sec or [])
        else:
            merged[sec] = {}
    return merged


def handle_cellar_bateria(args: dict[str, Any], **kwargs: Any) -> str:
    op = str(args.get("op") or "spec").strip().lower()
    if op not in {"spec", "sections", "get", "upsert", "remove"}:
        return _json({"ok": False, "error": f"Invalid op {op!r}; expected spec|sections|get|upsert|remove."})

    merged = _merged_bateria(include_removed=bool(args.get("include_removed", False)))
    sec_counts = {sec: len(merged.get(sec) or {}) for sec in _BATERIA_SECTIONS}

    if op == "spec":
        can_p = _personal_bateria_path()
        ui_p = _ui_dir() / "bateria.personal.yaml"
        can_exists = can_p.exists()
        ui_exists = ui_p.exists() and ui_p.resolve() != can_p.resolve()
        return _json(
            {
                "ok": True,
                "nomenclature": "NNN [Sujeto] MMM [Iq1] [Iq2] Descripción · Verbo",
                "max_title_length": MAX_TITLE_LENGTH,
                "axes": {
                    "iq0": {"name": "Subject (session patient)", "in_title": True},
                    "iq1": {"name": "Protagonist (brand or program/platform/service)", "in_title": True},
                    "iq2": {"name": "Context (place, machine, country, store)", "in_title": True},
                    "iq3": {"name": "Intention (closed 7-verb vocabulary)", "in_title": False},
                    "iq4": {"name": "Theme (work front or IT Manager subcategory)", "in_title": False},
                    "iq5": {"name": "Date (year / when it happened)", "in_title": False},
                    "iq6": {"name": "Machine (which computer)", "in_title": False},
                    "iq7": {"name": "Reserved", "in_title": False},
                    "iq8": {"name": "Project", "in_title": False},
                    "iq9": {"name": "Pending (authorization requests)", "in_title": False},
                },
                "vocabularies": {
                    "tag3_intentions": list(INTENTIONS),
                    "tag4_themes": list(THEMES),
                    "tag4_it_subcategories": list(IT_SUBCATEGORIES),
                    "verbs": list(VERBS),
                },
                "bateria_sections": sec_counts,
                "personal_bateria_path": str(can_p),
                "canonical_dir": str(_plugin_dir()),
                "ui_dir": str(_ui_dir()),
                "bateria_objetiva_exists": BATERIA_PATH.exists(),
                "bateria_personal_exists": can_exists,
                "ui_bateria_obsolete": ui_exists and can_exists,
            }
        )

    if op == "sections":
        return _json({"ok": True, "sections": sec_counts})

    if op == "get":
        section = str(args.get("section") or "").strip()
        key = str(args.get("key") or "").strip()
        if not section:
            return _json({"ok": False, "error": "Provide 'section' for op='get'."})
        sec_data = merged.get(section)
        if sec_data is None:
            return _json({"ok": False, "error": f"Unknown section {section!r}."})
        if not key:
            return _json({"ok": True, "section": section, "entries": sec_data, "count": len(sec_data)})
        entry = sec_data.get(key) if isinstance(sec_data, dict) else None
        if entry is None and isinstance(sec_data, dict):
            # Case-insensitive lookup fallback
            entry = next((v for k, v in sec_data.items() if str(k).lower() == key.lower()), None)
        return _json({"ok": entry is not None, "section": section, "key": key, "value": entry})

    # Write ops: upsert | remove -> plugin_data_dir()/bateria.personal.yaml ONLY
    dry_run = bool(args.get("dry_run", True))
    confirm = bool(args.get("confirm", False))
    section = str(args.get("section") or "").strip()
    key = str(args.get("key") or "").strip()
    if not section or not key:
        return _json({"ok": False, "error": f"Both 'section' and 'key' are required for op={op!r}."})

    personal = _load_personal_bateria()
    sec_dict = personal.get(section)
    if not isinstance(sec_dict, dict):
        sec_dict = {}
    before_val = sec_dict.get(key)

    if op == "upsert":
        if "value" not in args:
            return _json({"ok": False, "error": "'value' is required for op='upsert'."})
        after_val = args["value"]
    else:  # remove (soft removal: kept with removed: true)
        base_entry = (merged.get(section) or {}).get(key) if isinstance(merged.get(section), dict) else None
        seed = before_val if isinstance(before_val, dict) else (base_entry if isinstance(base_entry, dict) else {"value": before_val})
        after_val = {
            **(seed or {}),
            "removed": True,
            "removed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    preview = [{"section": section, "key": key, "before": before_val, "after": after_val}]

    if not confirm:
        return _json(
            {
                "ok": False,
                "reason": "confirm required",
                "dry_run": dry_run,
                "changed": 0,
                "preview": preview,
                "backup_path": None,
                "receipt": None,
            }
        )

    if dry_run:
        return _json(
            {
                "ok": True,
                "dry_run": True,
                "changed": 0,
                "preview": preview,
                "backup_path": None,
                "receipt": None,
            }
        )

    _, gen_before = _load_merged_rows()
    backup_dir = _create_write_backup(f"cellar_bateria_{op}")
    sec_dict[key] = after_val
    personal[section] = sec_dict
    personal["updated"] = datetime.now().strftime("%Y-%m-%d")

    p_path = _personal_bateria_path()
    p_path.parent.mkdir(parents=True, exist_ok=True)
    p_path.write_text(
        yaml.safe_dump(personal, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    _append_correction(
        session_id=_caller_session_id(kwargs),
        tool="cellar_bateria",
        before={"section": section, "key": key, "value": before_val},
        after={"section": section, "key": key, "value": after_val},
        rule=args.get("rule"),
    )

    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_touched": 1,
        "generation_before": gen_before,
        "generation_after": gen_before,
    }
    return _json(
        {
            "ok": True,
            "dry_run": False,
            "changed": 1,
            "preview": preview,
            "backup_path": str(backup_dir),
            "receipt": receipt,
        }
    )


# --------------------------------------------------------------------------- #
# 10. cellar_export
# --------------------------------------------------------------------------- #

_TITLE_EXPORT_COLS = [
    "n",
    "id",
    "fecha",
    "titulo_actual",
    "sujeto",
    "iq1",
    "iq2",
    "descripcion",
    "verbo",
    "sujeto_nuevo",
    "tag1_nuevo",
    "tag2_nuevo",
    "descripcion_nueva",
    "verbo_nuevo",
    "observaciones",
]


def handle_cellar_export(args: dict[str, Any], **_kwargs: Any) -> str:
    what = str(args.get("what") or "titles").strip().lower()
    fmt = str(args.get("format") or "csv").strip().lower()
    if what not in {"titles", "corrections", "bateria", "facets"}:
        return _json({"ok": False, "error": f"Invalid what={what!r}; expected titles|corrections|bateria|facets."})
    if fmt not in {"csv", "yaml", "json"}:
        return _json({"ok": False, "error": f"Invalid format={fmt!r}; expected csv|yaml|json."})

    rows, _gen = _load_merged_rows()
    filt = args.get("filter") if isinstance(args.get("filter"), dict) else {}
    filtered = [_compact_row(r) for r in _filter_rows(rows, {**filt, "sort": filt.get("sort") or "n_asc"})]

    if what == "titles":
        payload_rows = [
            {
                "n": c["n"],
                "id": c["id"],
                "fecha": c["fecha"],
                "titulo_actual": c["title"],
                "sujeto": c["sujeto"],
                "iq1": c["iq1"],
                "iq2": c["iq2"],
                "descripcion": c["desc"],
                "verbo": c["verb"],
                "sujeto_nuevo": "",
                "tag1_nuevo": "",
                "tag2_nuevo": "",
                "descripcion_nueva": "",
                "verbo_nuevo": "",
                "observaciones": "",
            }
            for c in filtered
        ]
    elif what == "facets":
        payload_rows = filtered
    elif what == "corrections":
        c_path = _corrections_path()
        loaded = []
        if c_path.exists():
            try:
                loaded = yaml.safe_load(c_path.read_text(encoding="utf-8")) or []
            except Exception:
                loaded = []
        if not loaded and BATERIA_PATH.with_name("corrections.yaml").exists():
            try:
                loaded = yaml.safe_load(BATERIA_PATH.with_name("corrections.yaml").read_text(encoding="utf-8")) or []
            except Exception:
                loaded = []
        payload_rows = loaded if isinstance(loaded, list) else []
    else:  # bateria
        merged_bat = _merged_bateria()
        payload_rows = [
            {"section": sec, "key": k, "value": json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)}
            for sec, entries in merged_bat.items()
            if isinstance(entries, dict)
            for k, v in entries.items()
        ]

    count = _next_export_number()
    fname = f"{what}_[{count:04d}].{fmt}"
    out_path = _exports_dir() / fname

    if fmt == "json":
        text = json.dumps(payload_rows, ensure_ascii=False, indent=2)
        out_path.write_text(text, encoding="utf-8")
    elif fmt == "yaml":
        text = yaml.safe_dump(payload_rows, allow_unicode=True, sort_keys=False)
        out_path.write_text(text, encoding="utf-8")
    else:  # csv
        buf = io.StringIO()
        if what == "titles":
            fieldnames = _TITLE_EXPORT_COLS
        elif payload_rows and isinstance(payload_rows[0], dict):
            fieldnames = list(payload_rows[0].keys())
        else:
            fieldnames = ["value"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in payload_rows:
            if isinstance(item, dict):
                writer.writerow(
                    {
                        k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                        for k, v in item.items()
                    }
                )
            else:
                writer.writerow({"value": str(item)})
        out_path.write_text("\ufeff" + buf.getvalue(), encoding="utf-8")

    return _json(
        {
            "ok": True,
            "what": what,
            "format": fmt,
            "number": f"[{count:04d}]",
            "path": str(out_path),
            "rows": len(payload_rows),
            "bytes": out_path.stat().st_size,
        }
    )


# --------------------------------------------------------------------------- #
# Tool Schemas & Registration
# --------------------------------------------------------------------------- #


def _schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        params["required"] = required
    return {"name": name, "description": description, "parameters": params}


_FILTER_PROPS: dict[str, Any] = {
    "q": {"type": "string", "description": "Free-text search (title, sujeto, desc, raw, resumen) or numeric NNN list/range."},
    "tags": {
        "type": "object",
        "description": "Partial tag map, e.g. {'iq1': 'CyberPanel', 'iq3': 'Troubleshooting'}.",
    },
    "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (inclusive)."},
    "date_to": {"type": "string", "description": "End date YYYY-MM-DD (inclusive)."},
    "prof": {"type": "string", "description": "Hermes profile name (e.g. 'default')."},
    "motor": {"type": "string", "description": "Model engine label."},
    "state": {
        "type": "string",
        "enum": ["active", "cron", "deleted", "empty", "all"],
        "description": "Session state filter (default: 'active').",
    },
    "sort": {
        "type": "string",
        "enum": ["fecha_desc", "n_asc", "costo_desc", "horas_desc"],
        "description": "Sort order (default: 'fecha_desc').",
    },
    "limit": {"type": "integer", "description": "Max rows to return (default 50, max 500)."},
    "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
}

CELLAR_SEARCH_SCHEMA = _schema(
    "cellar_search",
    "Search the session catalogue by text, nine-slot tags, date range, profile, engine, or state.",
    _FILTER_PROPS,
)

CELLAR_SESSION_SCHEMA = _schema(
    "cellar_session",
    "Fetch one session in full by NNN ('n') or session 'id', optionally including cleaned user messages and the ADN 'why' block.",
    {
        "n": {"type": "integer", "description": "Canonical session number (NNN)."},
        "id": {"type": "string", "description": "Hermes session ID."},
        "include_messages": {"type": "boolean", "description": "Include cleaned key user turns (default false)."},
        "messages_limit": {"type": "integer", "description": "Max user messages to return (default 12)."},
        "include_why": {"type": "boolean", "description": "Include the ADN explanation block (default true)."},
    },
)

CELLAR_STATS_SCHEMA = _schema(
    "cellar_stats",
    "Compute aggregate counts, cost/hours/tokens/posts sums, facet breakdowns, and empty-tag counts for any cellar_search filter.",
    {
        **_FILTER_PROPS,
        "facets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional subset of facet axes to return (iq1, iq2, iq3, iq4, fecha_year, prof).",
        },
    },
)

CELLAR_SERIES_SCHEMA = _schema(
    "cellar_series",
    "Retrieve all sessions belonging to the same subject series, including MMM range, totals, and any missing MMM gaps.",
    {
        "subject": {"type": "string", "description": "Subject name (raw or normalised)."},
        "n": {"type": "integer", "description": "Or session NNN from which to take the subject."},
        "limit": {"type": "integer", "description": "Max rows to return (default 50, max 500)."},
        "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
    },
)

CELLAR_RENAME_SCHEMA = _schema(
    "cellar_rename",
    "Rename one session or a batch (max 50). Supports structured 'fields' (preferred) or literal 'title'. Gated by dry_run (default true) and confirm=true; backs up first and logs to corrections.yaml.",
    {
        "n": {"type": ["integer", "array"], "description": "Session NNN or list of NNNs."},
        "id": {"type": ["string", "array"], "description": "Session ID or list of IDs."},
        "filter": {"type": "object", "description": "Filter object (same shape as cellar_search, max 50 rows)."},
        "selector": {"type": "object", "description": "Optional selector wrapper {'n', 'id', or 'filter'}."},
        "fields": {
            "type": "object",
            "description": "Structured fields {'sujeto', 'mmm', 'iq1'..'iq9', 'desc', 'verb'} rendered into the canonical nomenclature.",
        },
        "title": {"type": "string", "description": "Literal canonical title (validated for <=100 chars and structure)."},
        "dry_run": {"type": "boolean", "description": "Preview only without writing (default true)."},
        "confirm": {"type": "boolean", "description": "Must be true to execute a write."},
        "rule": {"type": "string", "description": "Optional rule note recorded in corrections.yaml."},
    },
)

CELLAR_TAG_SCHEMA = _schema(
    "cellar_tag",
    "Set or clear (null) individual tags (iq1..iq9) on one session or a batch without losing the rest of the title. Gated by dry_run (default true) and confirm=true.",
    {
        "n": {"type": ["integer", "array"], "description": "Session NNN or list of NNNs."},
        "id": {"type": ["string", "array"], "description": "Session ID or list of IDs."},
        "filter": {"type": "object", "description": "Filter object (same shape as cellar_search, max 50 rows)."},
        "selector": {"type": "object", "description": "Optional selector wrapper {'n', 'id', or 'filter'}."},
        "set": {
            "type": "object",
            "description": "Tag map to set or clear, e.g. {'iq1': 'CyberPanel', 'iq5': null}.",
        },
        "dry_run": {"type": "boolean", "description": "Preview only without writing (default true)."},
        "confirm": {"type": "boolean", "description": "Must be true to execute a write."},
        "rule": {"type": "string", "description": "Optional rule note recorded in corrections.yaml."},
    },
    required=["set"],
)

CELLAR_BATERIA_SCHEMA = _schema(
    "cellar_bateria",
    "Inspect or update the classifier cheatsheet (batería). Call op='spec' first in any session to read the nomenclature and closed vocabularies. Writes go to plugin_data_dir()/bateria.personal.yaml.",
    {
        "op": {
            "type": "string",
            "enum": ["spec", "sections", "get", "upsert", "remove"],
            "description": "Operation to perform (default: 'spec').",
        },
        "section": {"type": "string", "description": "Batería section name (e.g. 'marcas', 'programas', 'vocabulario', 'reglas')."},
        "key": {"type": "string", "description": "Entry key inside the section."},
        "value": {"type": ["object", "string", "array"], "description": "Value to store for op='upsert'."},
        "include_removed": {"type": "boolean", "description": "Include soft-removed entries in op='get'."},
        "dry_run": {"type": "boolean", "description": "Preview only without writing (default true)."},
        "confirm": {"type": "boolean", "description": "Must be true to execute upsert/remove."},
        "rule": {"type": "string", "description": "Optional rule note recorded in corrections.yaml."},
    },
)

CELLAR_INDEX_SCHEMA = _schema(
    "cellar_index",
    "Maintain the derived session index in-process: check status, detect new/changed sessions, rebuild index.json from state.db, or run the Python classifier over untitled sessions to get proposals.",
    {
        "op": {
            "type": "string",
            "enum": ["status", "detect", "rebuild", "classify"],
            "description": "Index operation (default: 'status').",
        },
        "limit": {"type": "integer", "description": "Max untitled sessions to classify per call (default 25)."},
    },
)

CELLAR_VERIFY_SCHEMA = _schema(
    "cellar_verify",
    "Lint the archive against all nomenclature invariants (<=100 chars, unique NNN, gapless MMM per subject, closed iq3/iq4 vocabularies, iq1 in batería, subject != iq1, non-empty description).",
    {
        **_FILTER_PROPS,
    },
)

CELLAR_EXPORT_SCHEMA = _schema(
    "cellar_export",
    "Export titles, corrections, bateria, or facets to plugin_data_dir()/exports/<what>_[CCCC].<format> with the monotonic export counter.",
    {
        "what": {
            "type": "string",
            "enum": ["titles", "corrections", "bateria", "facets"],
            "description": "Dataset to export (default: 'titles').",
        },
        "format": {
            "type": "string",
            "enum": ["csv", "yaml", "json"],
            "description": "Output file format (default: 'csv').",
        },
        "filter": {"type": "object", "description": "Optional cellar_search filter for 'titles' or 'facets'."},
    },
)

CELLAR_TOOLS: tuple[tuple[str, dict[str, Any], Any, str], ...] = (
    ("cellar_search", CELLAR_SEARCH_SCHEMA, handle_cellar_search, "🔎"),
    ("cellar_session", CELLAR_SESSION_SCHEMA, handle_cellar_session, "📄"),
    ("cellar_stats", CELLAR_STATS_SCHEMA, handle_cellar_stats, "📊"),
    ("cellar_series", CELLAR_SERIES_SCHEMA, handle_cellar_series, "🧵"),
    ("cellar_rename", CELLAR_RENAME_SCHEMA, handle_cellar_rename, "✏️"),
    ("cellar_tag", CELLAR_TAG_SCHEMA, handle_cellar_tag, "🏷️"),
    ("cellar_bateria", CELLAR_BATERIA_SCHEMA, handle_cellar_bateria, "📚"),
    ("cellar_index", CELLAR_INDEX_SCHEMA, handle_cellar_index, "🔄"),
    ("cellar_verify", CELLAR_VERIFY_SCHEMA, handle_cellar_verify, "✅"),
    ("cellar_export", CELLAR_EXPORT_SCHEMA, handle_cellar_export, "📤"),
)


def register_tools(ctx: Any) -> None:
    """Register all 10 cellar_* tools on the Hermes PluginContext."""
    for name, schema, handler, emoji in CELLAR_TOOLS:
        ctx.register_tool(
            name=name,
            toolset=TOOLSET_NAME,
            schema=schema,
            handler=handler,
            description=schema["description"],
            emoji=emoji,
        )
