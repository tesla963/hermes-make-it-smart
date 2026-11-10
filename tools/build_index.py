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
from core.paths import data_dir  # noqa: E402

# The ordinal sits OUTSIDE the subject bracket: 001 [Chat en Telegram] 001 [Tag] …
TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\]\s+(?P<mmm>\d{3,4})\s*"
    r"(?:\[(?P<tag1>[^\]]*)\])?\s*(?:\[(?P<tag2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

# Titles written before that move still read 001 [Chat en Telegram 001] [Tag] …,
# and a subject may legitimately end in a number ("Inspiron 5570"), so the legacy
# shape is tried only when the new one fails.
TITLE_RE_LEGACY = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<tag1>[^\]]*)\])?\s*(?:\[(?P<tag2>[^\]]*)\])?\s*"
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
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def build(with_messages: bool = True) -> dict:
    extra = load_facets()
    rows: list[dict] = []
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            m = parse_title(title)
            if not m:
                continue
            g = m.groupdict()
            if with_messages:
                rec = attach_messages(rec, path)
            msgs = [re.sub(r"\s+", " ", x)[:400] for x in (rec.messages or []) if is_human(x)]
            rows.append(
                {
                    "n": int(g["nnn"]),
                    "mmm": int(g["mmm"]),
                    "sujeto": g["subject"].strip(),
                    "tag1": (g["tag1"] or "").strip(),
                    "tag2": (g["tag2"] or "").strip(),
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
                    "pilar": extra.get(rec.id, {}).get("pilar", ""),
                    "motor": extra.get(rec.id, {}).get("motor", ""),
                    "tag6": extra.get(rec.id, {}).get("tag6", ""),
                    "mc": extra.get(rec.id, {}).get("mc", rec.posts or 0),
                    "claves": msgs[:6],
                }
            )

    rows.sort(key=lambda r: r["n"])
    subjects = Counter(r["sujeto"] for r in rows)
    facets = {
        "tag1": dict(Counter(r["tag1"] for r in rows if r["tag1"]).most_common()),
        "tag2": dict(Counter(r["tag2"] for r in rows if r["tag2"]).most_common()),
        "prof": dict(Counter(r["prof"] for r in rows).most_common()),
    }
    return {
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
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"{data['count']} sesiones · {data['subjects']} sujetos")
    print(f"{out} · {out.stat().st_size/1024:.0f} KB · generado {data['generated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
