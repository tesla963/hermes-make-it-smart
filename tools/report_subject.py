#!/usr/bin/env python3
"""Consolidate every session that shares a subject into one dated report.

This is the plugin using itself. The agent runs this and hands the owner a
single file that reconstructs a topic's whole history, so a new session can
start with the context already on the table instead of re-deriving it.

    # what subjects exist, and how many sessions each has
    python3 tools/report_subject.py --list

    # one report, oldest session first
    python3 tools/report_subject.py "Read Aloud" --out ~/Desktop/read_aloud.md

    # every subject with 3+ sessions, one file each
    python3 tools/report_subject.py --all --min-sessions 3 --out-dir ~/Desktop/reportes

Reads every state.db in read-only mode. Never writes to the host.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import attach_messages, discover_databases, read_sessions  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)


def norm(text: str) -> str:
    """Fold case and accents so "samurai" finds "Samurái"."""
    nfd = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower().strip()


def collect(with_bodies: bool = False) -> list[dict]:
    """Every canonical session, from every profile, in one list.

    Bodies are only fetched for sessions that survive the filter: reading 40
    messages for 884 sessions to print a subject list would be pure waste.
    """
    out: list[dict] = []
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            m = TITLE_RE.match(title)
            if not m:
                continue
            if with_bodies:
                rec = attach_messages(rec, path)
            g = m.groupdict()
            out.append(
                {
                    "nnn": int(g["nnn"]),
                    "mmm": int(g["mmm"]),
                    "subject": g["subject"].strip(),
                    "iq1": (g["iq1"] or "").strip(),
                    "iq2": (g["iq2"] or "").strip(),
                    "description": (g["desc"] or "").strip(),
                    "verb": (g["verb"] or "").strip(),
                    "title": title,
                    "session_id": rec.id,
                    "profile": profile,
                    "date": str(rec.created_at or "")[:19],
                    "messages": list(rec.messages or []),
                    "posts": rec.posts or 0,
                    "cost": rec.cost_usd or 0.0,
                    "tokens": rec.tokens or 0,
                }
            )
    return out


def by_subject(rows: list[dict]) -> dict[str, list[dict]]:
    """Group by normalised subject, then order by date and by ordinal."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[norm(r["subject"])].append(r)
    for key, items in groups.items():
        items.sort(key=lambda x: (x["date"] or "", x["mmm"]))
    return dict(groups)


# Cron sessions open with a machine preamble, not with the owner speaking.
_NOISE = ("[important", "## script output", "you are running as a scheduled cron job",
          "<system", "## run context")


def _is_human(message: str) -> bool:
    m = (message or "").strip()
    if not m:
        return False
    return not any(m.lower().startswith(n) or n in m[:120].lower() for n in _NOISE)


def render_report(subject: str, sessions: list[dict]) -> str:
    first, last = sessions[0], sessions[-1]
    tags = sorted({s["iq1"] for s in sessions if s["iq1"]})
    families = sorted({s["iq2"] for s in sessions if s["iq2"]})
    posts = sum(s["posts"] or 0 for s in sessions)
    cost = sum(s["cost"] or 0 for s in sessions)
    tokens = sum(s["tokens"] or 0 for s in sessions)

    lines = [
        f"# {first['subject']}",
        "",
        f"**{len(sessions)} sesiones** · {first['date'][:10]} → {last['date'][:10]}"
        f" · {posts} posts · ${cost:.2f} · {tokens/1e6:.1f}M tokens",
        "",
        f"**Plataformas:** {', '.join(tags) if tags else '—'}  ",
        f"**Familias:** {', '.join(families) if families else '—'}",
        "",
        "---",
        "",
    ]

    for i, s in enumerate(sessions, 1):
        head = f"## {i}. {s['date'][:10]} · {s['nnn']:03d}"
        lines.append(head)
        lines.append("")
        meta = f"`{s['title']}`"
        lines.append(meta)
        lines.append("")
        # What was actually asked, in the owner's own words, is the only body
        # that survives a new session reading this file.
        said = [m for m in s["messages"] if _is_human(m)]
        if said:
            for msg in said[:4]:
                text = " ".join(msg.split())[:400]
                lines.append(f"> {text}")
                lines.append(">")
            if lines[-1] == ">":
                lines.pop()
            lines.append("")
        elif s["description"]:
            lines.append(s["description"])
            lines.append("")
        lines.append(f"<sub>perfil `{s['profile']}` · `{s['session_id']}`</sub>")
        lines.append("")

    lines += [
        "---",
        "",
        f"*Generado por make-it-smart, Hermes — {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("subject", nargs="?", help="subject to consolidate")
    ap.add_argument("--list", action="store_true", help="list subjects and counts")
    ap.add_argument("--all", action="store_true", help="one report per subject")
    ap.add_argument("--min-sessions", type=int, default=2)
    ap.add_argument("--out")
    ap.add_argument("--out-dir")
    ap.add_argument("--md", action="store_true", help="print the report to stdout")
    ap.add_argument("--like", action="store_true",
                    help="match the term anywhere in the title, not just as subject")
    args = ap.parse_args()

    rows = collect(with_bodies=bool(args.subject or args.all))
    groups = by_subject(rows)

    if args.list or not (args.subject or args.all):
        ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        print(f"{len(rows)} sesiones canónicas · {len(groups)} sujetos\n")
        for key, items in ranked:
            if len(items) < args.min_sessions:
                continue
            print(f"{len(items):>3}  {items[0]['subject']:<34} {items[0]['date'][:10]} → {items[-1]['date'][:10]}")
        return 0

    if args.all:
        dest = Path(args.out_dir or ".").expanduser()
        dest.mkdir(parents=True, exist_ok=True)
        written = 0
        for key, items in groups.items():
            if len(items) < args.min_sessions:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", norm(items[0]["subject"])).strip("-")[:48]
            path = dest / f"{slug}.md"
            path.write_text(render_report(items[0]["subject"], items), encoding="utf-8")
            written += 1
            print(f"  {len(items):>3} sesiones → {path}")
        print(f"\n{written} reportes en {dest}")
        return 0

    key = norm(args.subject)
    if args.like:
        # "read aloud" may live under another subject: search the whole title.
        loose = [r for r in rows if key in norm(r["title"])]
        if loose:
            buckets = by_subject(loose)
            label = loose[0]["subject"] if len(buckets) == 1 else args.subject
            report = render_report(label, sorted(loose, key=lambda x: (x["date"] or "", x["nnn"])))
            print(f"«{args.subject}» aparece en {len(loose)} títulos "
                  f"({len(buckets)} sujetos distintos)", file=sys.stderr)
            if args.out:
                out = Path(args.out).expanduser()
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(report, encoding="utf-8")
                print(f"{len(loose)} sesiones → {out}")
            else:
                print(report)
            return 0
    items = groups.get(key)
    if not items:
        near = [k for k in groups if key in k or k in key][:8]
        print(f"sin sesiones para «{args.subject}».", file=sys.stderr)
        if near:
            print("quizá: " + ", ".join(groups[k][0]["subject"] for k in near), file=sys.stderr)
        return 1

    report = render_report(items[0]["subject"], items)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"{len(items)} sesiones → {out}")
        print(f"{len(report.splitlines())} líneas · {len(report):,} caracteres")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
