#!/usr/bin/env python3
"""Re-classify every session under the 2026-11-10 schema.

    python3 tools/reclassify.py --sample 10      # ten sessions, to judge quality
    python3 tools/reclassify.py --all            # every session, propose only
    python3 tools/reclassify.py --all --apply    # back up and write

This is NOT a migration. The old Iq2 (families, topics, intentions mixed in one
field) is thrown away; the model reads what the user said and decides again.
That is why some sessions will come out with an empty iq3: an empty field says
nobody read an intention there, which is true. It is not filled with whatever
the old tag happened to hold.

The schema:
    iq1 = maker of the subject (adjective)   "DJI"
    iq2 = context: store, country or machine "Ebay"
    iq3 = intention (seven verbs, closed)    "Comparar"
    iq4 = theme / subcategory                "Hardware"
    iq5 = year                               "2026"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import (  # noqa: E402
    attach_messages,
    backup_databases,
    discover_databases,
    read_sessions,
)
from core.classify import ClassifyConfig, classify_one  # noqa: E402
from core.normalize import Facets, render  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\]\s+(?P<mmm>\d{3,4})\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

# Machine preamble and skill dumps are not something the owner said.
NOISE = (
    "[important", "## script output", "you are running as a scheduled cron job",
    "<system", "## run context", "[the user attached",
)


def human_turns(messages, limit=8) -> list[str]:
    out = []
    for m in messages or []:
        t = re.sub(r"\s+", " ", (m or "").strip())
        if len(t) < 15:
            continue
        low = t[:160].lower()
        if any(n in low for n in NOISE):
            continue
        if re.match(r"^-{3}\s*name:", t[:20]) or 'description: "use when' in t[:200].lower():
            continue
        out.append(t[:600])
        if len(out) >= limit:
            break
    return out


def api_key() -> str:
    """Read the DeepSeek token the app already stores. Never printed."""
    path = Path.home() / ".hermes" / "auth.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    pool = data.get("credential_pool", {}).get("deepseek") or []
    for entry in pool:
        tok = entry.get("access_token") or entry.get("api_key")
        if tok:
            return tok
    raise SystemExit("no DeepSeek token in ~/.hermes/auth.json")


def collect() -> list[dict]:
    """Every session in every database — titled or not.

    A session without the catalogue's NNN [Subject] MMM shape used to be skipped,
    and 25 of them never reached the catalogue. 'None left outside' means the
    collector cannot filter by shape any more: it reads them all and hands the
    untitled ones a number after the last one in use.
    """
    rows = []
    seen = set()
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            if rec.id in seen:
                continue
            seen.add(rec.id)
            m = TITLE_RE.match(title)
            rec = attach_messages(rec, path)
            rows.append({
                "id": rec.id, "db": str(path), "prof": profile,
                "nnn": int(m.group("nnn")) if m else 0,
                "mmm": int(m.group("mmm")) if m else 1,
                "old": title, "date": str(rec.created_at or "")[:10],
                "turns": human_turns(rec.messages),
                "untitled": m is None,
                "messages": len(rec.messages or []),
            })
    # Untitled sessions are numbered after the last number in use, oldest first.
    siguientes = max((r["nnn"] for r in rows if r["nnn"]), default=0) + 1
    for r in sorted((x for x in rows if not x["nnn"]), key=lambda x: x["date"]):
        r["nnn"] = siguientes
        siguientes += 1
    rows.sort(key=lambda r: r["nnn"])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default="/tmp/reclassify.json")
    ap.add_argument("--workers", type=int, default=8,
                    help="parallel requests; the API allows more than one")
    args = ap.parse_args()

    rows = collect()
    if args.sample:
        # Spread across the catalogue instead of taking the first N: the first
        # fifty are all from July and teach nothing about the rest.
        step = max(1, len(rows) // args.sample)
        rows = rows[::step][: args.sample]
    elif not args.all:
        print(f"{len(rows)} sesiones disponibles. Usa --sample N o --all.")
        return 0

    cfg = ClassifyConfig(api_key=api_key(), model="deepseek-chat",
                         temperature=0.0, max_tokens=1200, language="es")
    print(f"clasificando {len(rows)} sesiones…")

    out = []
    empty_intent = 0
    t0 = time.time()

    def one(r):
        res = classify_one(
            messages=r["turns"], config=cfg, date=r["date"],
            current_title=r["old"], ordinal=r["mmm"],
        )
        return r, res

    # Sequential was 20 s a session: five hours for the catalogue. The work is
    # waiting on the network, not on the CPU, so eight in flight costs nothing
    # but patience.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(one, r) for r in rows]
        for i, fut in enumerate(as_completed(futures), 1):
            r, res = fut.result()
            f = res.facets
            if f is None:
                continue
            if not f.iq3:
                empty_intent += 1
            new = render(r["nnn"], f)
            out.append({
                "id": r["id"], "db": r["db"], "nnn": r["nnn"], "old": r["old"],
                "new": new, "subject": f.subject, "iq1": f.iq1, "iq2": f.iq2,
                "iq3": f.iq3, "iq4": f.iq4, "iq5": f.iq5,
                "desc": f.description, "attempts": getattr(res, "attempts", 1),
            })
            if i % 50 == 0 or i == len(rows):
                rate = i / max(1e-9, time.time() - t0)
                left = (len(rows) - i) / max(1e-9, rate)
                print(f"  {i}/{len(rows)} · {time.time()-t0:.0f}s · faltan {left/60:.0f} min · sin iq3: {empty_intent}", flush=True)

    out.sort(key=lambda r: r["nnn"])

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(out)} clasificadas · {empty_intent} sin iq3 ({empty_intent/len(out)*100:.0f}%)")
    print(f"-> {args.out}")

    for r in out[:8]:
        print(f"\n  {r['nnn']:>3} [{r['iq1'] or '—'}] [{r['iq2'] or '—'}] [{r['iq3'] or '—'}] [{r['iq4'] or '—'}]")
        print(f"       - {r['old'][:92]}")
        print(f"       + {r['new'][:92]}")

    if not args.apply:
        print("\n(propuesta — nada escrito)")
        return 0

    from adapters.hermes import HermesTitleWriter

    dest = backup_databases(Path("/Volumes/1TB_HD/Backups-Lisa"), "pre-esquema-2026-11-10")
    print(f"\nbackup -> {dest}")
    w = HermesTitleWriter()
    ok = 0
    for r in out:
        if r["new"] == r["old"]:
            ok += 1
            continue
        if w.rename(r["id"], r["new"], r["db"]):
            ok += 1
        else:
            print(f"  FALLO {r['nnn']}")
    print(f"escritas: {ok} de {len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
