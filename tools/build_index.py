#!/usr/bin/env python3
"""Build the index the desktop plugin reads.

The plugin window is JavaScript; the classification, the counters and the costs
are Python. This is the bridge: one JSON file with everything the window needs,
so the UI never has to re-derive a facet or ask the host for 884 records.

    python3 tools/build_index.py                 # -> plugin-data/.../index.json
    python3 tools/build_index.py --out /tmp/x.json

The index is a CACHE: it can be rebuilt from the twelve state.db files at any
time. Nothing here writes to the host.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import attach_messages, discover_databases, read_sessions  # noqa: E402
from core.paths import data_dir, ui_data_dir  # noqa: E402

# The ordinal sits OUTSIDE the subject bracket: 001 [Chat en Telegram] 001 [Tag] …
TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\]\s+(?P<mmm>\d{3,4})\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

# Titles written before that move still read 001 [Chat en Telegram 001] [Tag] …,
# and a subject may legitimately end in a number ("Inspiron 5570"), so the legacy
# shape is tried only when the new one fails.
TITLE_RE_LEGACY = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)


def parse_title(title: str):
    """Match either shape; the new one wins when both could apply."""
    return TITLE_RE.match(title) or TITLE_RE_LEGACY.match(title)

# Machine preamble, skill dumps and cron boilerplate are not something the owner said.
NOISE = ("[important", "## script output", "you are running as a scheduled cron job",
         "<system", "## run context", "[the user attached")


def is_human(message: str) -> bool:
    t = (message or "").strip()
    if not t:
        return False
    low = t[:160].lower()
    if any(n in low for n in NOISE):
        return False
    # a skill dumped into the turn looks like YAML frontmatter
    if re.match(r"^\s*-{3}\s*$", t[:5]) or re.match(r"^-{3}\s*name:", t[:20]):
        return False
    return not re.search(r'description:\s*"use when', t[:200], re.I)


def load_facets() -> dict:
    """Pillar, machine, engine and message count come from the curated index.

    state.db holds none of them: the pillar is a judgement, the engine lives in
    session_model_usage and the machine in a side table. facets.json carries the
    result so this indexer stays a thin reader.
    """
    path = data_dir() / "facets.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    # v0.26.x wrote tagN, v0.27.0 writes iqN: read either, so an old facets file still
    # builds a complete index while the migration catches up.
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, dict):
                for n in range(10):
                    if value.get(f"iq{n}") in (None, "") and value.get(f"tag{n}") is not None:
                        value[f"iq{n}"] = value[f"tag{n}"]
    return data


def _schema_of(path: Path) -> int:
    """Esquema que declara un artefacto: el sello `schema`, o 1 si no lleva ninguno."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return 0
    if isinstance(data, dict) and isinstance(data.get("schema"), int):
        return int(data["schema"])
    return 1


def _pisa_espejo(canonico: Path, espejo: Path) -> bool:
    """¿Se puede copiar el canónico sobre el espejo?

    No si el espejo ya está en un esquema MÁS NUEVO: el panel migró sus datos y el
    canónico se quedó atrás (o su migración falló). Copiar encima devolvería el
    espejo al esquema viejo y el panel volvería a pedir la migración.
    """
    if not Path(espejo).exists():
        return True
    return _schema_of(canonico) >= _schema_of(espejo)


def build(with_messages: bool = True) -> dict:
    # Bring any older artefact to the iqN schema before reading it. A failure here is
    # not fatal: load_facets() accepts both key sets.
    try:
        import sys as _sys  # noqa: PLC0415
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from migrate_axes import ensure_current  # noqa: PLC0415

        ensure_current()
    except Exception as exc:  # noqa: BLE001
        # No es fatal (el lector acepta ambos esquemas), pero callarlo dejaba que el
        # canónico viejo se copiara sobre el espejo sin que nadie se enterara.
        print(f"aviso: no se pudo migrar el canónico antes de reconstruir: {exc}", file=sys.stderr)
    extra = load_facets()
    rows: list[dict] = []
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            m = parse_title(title)
            # A session without the canonical shape is still a session: it enters
            # with n=0 and gets a number after the highest one in use, below.
            g = m.groupdict() if m else {"nnn": "0", "mmm": "1", "subject": "",
                                         "iq1": "", "iq2": "", "desc": "", "verb": ""}
            if with_messages:
                rec = attach_messages(rec, path)
            msgs = [re.sub(r"\s+", " ", x)[:400] for x in (rec.messages or []) if is_human(x)]
            # El titulo manda, pero no es la unica fuente: una sesion que el host no
            # deja renombrar (las del modo Bot, por ejemplo) ya viene clasificada en
            # facets.json. Descartar ese dato dejaba la sesion sin sujeto ni marca.
            ex = extra.get(rec.id, {})
            rows.append(
                {
                    "n": int(g["nnn"]),
                    "mmm": int(g["mmm"]),
                    "sujeto": g["subject"].strip() or (ex.get("sujeto") or "").strip(),
                    "iq1": (g["iq1"] or "").strip() or (ex.get("iq1") or "").strip(),
                    "iq2": (g["iq2"] or "").strip() or (ex.get("iq2") or "").strip(),
                    # Nine slots always, empty when unused: gaining an axis later
                    # must not cost a migration of every record.
                    "iq3": extra.get(rec.id, {}).get("iq3", ""),
                    "iq4": extra.get(rec.id, {}).get("iq4", ""),
                    "iq5": extra.get(rec.id, {}).get("iq5", ""),
                    "iq6": "",
                    "iq7": extra.get(rec.id, {}).get("iq7", ""),
                    "iq8": extra.get(rec.id, {}).get("iq8", ""),
                    "iq9": extra.get(rec.id, {}).get("iq9", ""),
                    "desc": (g["desc"] or "").strip(),
                    "verb": (g["verb"] or "").strip(),
                    "raw": title,
                    "id": rec.id,
                    "prof": profile,
                    "fecha": str(rec.created_at or "")[:10],
                    "costo": round(float(rec.cost_usd or 0), 4),
                    "horas": round(float(rec.hours or 0), 1),
                    "tok": int(rec.tokens or 0),
                    "posts": int(rec.posts or 0),
                    "esCron": bool(re.match(r"^cron[_-]", rec.id or "")),
                    # Machinery, not work: the canonical Bot Chat and the transcripts
                    # delegate_task spawns. The panel hides them behind the Bots chip.
                    "esBot": (rec.source or "").lower() in {"subagent", "bot"},
                    "source": rec.source or "",
                    # Mother session of a subagent transcript, "" for a root session. The
                    # panel indents the row under it; it is still one row, counted once.
                    # Only subagents: the host also sets parent_session_id on a desktop
                    # session that continues one reaped at startup (end_reason
                    # *_orphan_reap). That is a continuation, not delegated work.
                    "parent": (rec.parent_session_id or "")
                    if (rec.source or "").lower() == "subagent"
                    else "",
                    "pilar": extra.get(rec.id, {}).get("pilar", ""),
                    "motor": extra.get(rec.id, {}).get("motor", ""),
                    "mc": extra.get(rec.id, {}).get("mc", rec.posts or 0),
                    "claves": msgs[:6],
                }
            )

    rows.sort(key=lambda r: r["n"])
    subjects = Counter(r["sujeto"] for r in rows)
    facets = {
        "iq1": dict(Counter(r["iq1"] for r in rows if r["iq1"]).most_common()),
        "iq2": dict(Counter(r["iq2"] for r in rows if r["iq2"]).most_common()),
        "prof": dict(Counter(r["prof"] for r in rows).most_common()),
    }
    # Number the untitled ones after the last number in use, oldest first.
    siguientes = max((r["n"] for r in rows if r["n"]), default=0) + 1
    for r in sorted((x for x in rows if not x["n"]), key=lambda x: x.get("fecha") or ""):
        r["n"] = siguientes
        siguientes += 1

    return {
        "schema": 2,  # iq0…iq9. v1 (tag0…tag9) is migrated on read by tools/migrate_axes.py.
        "generated": datetime.now().isoformat(timespec="seconds"),
        "count": len(rows),
        "subjects": len(subjects),
        "facets": facets,
        "sessions": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--no-messages", action="store_true")
    args = ap.parse_args()

    data = build(with_messages=not args.no_messages)
    out = Path(args.out).expanduser() if args.out else data_dir() / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out.write_text(content, encoding="utf-8")
    if not args.out:
        try:
            ui_out = ui_data_dir() / "index.json"
            ui_out.parent.mkdir(parents=True, exist_ok=True)
            if _pisa_espejo(data_dir() / "index.json", ui_out):
                ui_out.write_text(content, encoding="utf-8")
        except Exception:
            pass
        try:
            can_facets = data_dir() / "facets.json"
            if can_facets.exists():
                ui_facets = ui_data_dir() / "facets.json"
                ui_facets.parent.mkdir(parents=True, exist_ok=True)
                if _pisa_espejo(can_facets, ui_facets):
                    ui_facets.write_text(can_facets.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
        try:
            can_pending = data_dir() / "pending_index.json"
            ui_pending = ui_data_dir() / "pending_index.json"
            if can_pending.exists() and not ui_pending.exists():
                ui_pending.write_text(can_pending.read_text(encoding="utf-8"), encoding="utf-8")
            elif ui_pending.exists() and not can_pending.exists():
                can_pending.write_text(ui_pending.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass

    print(f"{data['count']} sesiones · {data['subjects']} sujetos")
    print(f"{out} · {out.stat().st_size/1024:.0f} KB · generado {data['generated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
