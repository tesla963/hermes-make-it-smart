#!/usr/bin/env python3
"""Run the two-layer protocol over every session and show what it would change.

    python3 tools/apply_protocol.py --dry      # propose only, write nothing
    python3 tools/apply_protocol.py --apply    # backup, write, read back

The protocol is conservative on purpose. It only proposes a change when the
script can prove one:

  subject   the current subject contains a name the cheat_sheet knows, and a more
            specific actor sits inside it ("DJI Avata 360" → "Avata 360")
  iq1      the subject had a brand inside, or the actor list names the maker
  iq2      the intent keywords fire clearly and the current iq2 is generic

Everything else is left alone. A iq2 of "Electronia" that the keywords cannot
resolve is not replaced with a guess — it waits for the model, which this script
does not call yet: the cheap layer must be measured before the costly one runs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import (  # noqa: E402
    attach_messages,
    backup_databases,
    discover_databases,
    read_sessions,
)
from core.actors import brand_of_subject, describe, find_actors  # noqa: E402
from core.cheat_sheet import load_cheat_sheet  # noqa: E402
from core.intent import classify_intent  # noqa: E402
from core.normalize import MAX_TITLE_LENGTH, Facets, render  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\]\s+(?P<mmm>\d{3,4})\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

# A iq2 that says where the object would sit in a shop, not what was done.
GENERIC_TAG2 = {
    "electronica", "ia", "productivity", "it manager", "multimedia",
    "software", "hardware", "otros", "general", "varios", "",
}

# The intent only replaces a generic iq2. Replacing a specific one
# ("Troubleshooting", "WebHosting") with a verb would lose information.
PROTECTED_TAG2 = {
    "troubleshooting", "webhosting", "data backup", "data mining",
    "data security", "mcp/cli", "networking", "file system", "repository",
    "automation", "programming", "programación", "testing", "cotizar",
}


def parse(title: str):
    return TITLE_RE.match(title or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write; default is dry")
    ap.add_argument("--limit", type=int, default=0, help="stop after N proposals")
    ap.add_argument("--iq2-only", action="store_true",
                    help="touch only Iq2; leave subject and Iq1 for review")
    args = ap.parse_args()

    bat = load_cheat_sheet()
    proposals: list[dict] = []
    seen_ids: set[str] = set()
    skipped = 0

    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            m = parse(title)
            if not m or rec.id in seen_ids:
                continue
            seen_ids.add(rec.id)
            g = m.groupdict()
            subject = g["subject"].strip()
            iq1 = (g["iq1"] or "").strip()
            iq2 = (g["iq2"] or "").strip()

            rec = attach_messages(rec, path)
            turns = [t for t in (rec.messages or []) if t and len(t.strip()) > 12]
            text = " ".join(turns[:6]) + " " + subject + " " + (g["desc"] or "")

            d = describe(text, bat)
            new_subject, new_iq1, new_iq2 = subject, iq1, iq2
            why: list[str] = []

            # --- subject: only when a known actor sits inside the current name
            cand = d["subject"]
            if cand and cand != subject and subject.lower().startswith(cand.lower() + " "):
                # "DJI Avata 360" → the actor "Avata 360" is the tail of the name
                new_subject = cand
                why.append(f"sujeto: marca fuera ({subject} → {cand})")
            elif cand and cand != subject and subject.lower() in {
                a["name"].lower() for a in d["actors"]
            }:
                pass  # already a clean actor
            elif d["subject_kind"] == "product" and subject.lower() == iq1.lower():
                # Subject is literally the brand: promote the product
                new_subject = cand
                why.append(f"sujeto: la marca era el sujeto ({subject} → {cand})")

            # --- iq1: the maker of the subject, when we can prove it
            if d["brand"] and d["brand"] != iq1 and new_subject != subject:
                new_iq1 = d["brand"]
                why.append(f"iq1: {iq1 or '(vacío)'} → {d['brand']}")

            # --- iq2: the intent, only over a generic label
            if iq2.strip().lower() in GENERIC_TAG2:
                intent = classify_intent(text, focus=(g["desc"] or ""))
                if intent.name and intent.source == "rules":
                    new_iq2 = intent.name
                    why.append(f"iq2: {iq2 or '(vacío)'} → {intent.name}")

            if args.iq2_only and (new_subject != subject or new_iq1 != iq1):
                # The subject and Iq1 recuts still need a human eye: "Grok Bot"
                # is a product, "Windows" is not Apple. Iq2 is the safe half.
                skipped += 1
                continue

            if new_subject == subject and new_iq1 == iq1 and new_iq2 == iq2:
                skipped += 1
                continue

            facets = Facets(
                subject=new_subject,
                subject_ordinal=int(g["mmm"]),
                iq1=new_iq1,
                iq2=new_iq2,
                description=(g["desc"] or "").strip(),
                verb=(g["verb"] or "").strip(),
            )
            new_title = render(int(g["nnn"]), facets)
            if len(new_title) > MAX_TITLE_LENGTH or new_title == title:
                skipped += 1
                continue

            proposals.append({
                "id": rec.id, "db": str(path), "nnn": int(g["nnn"]), "old": title,
                "new": new_title, "why": "; ".join(why), "actors": d["actors"][:3],
            })
            if args.limit and len(proposals) >= args.limit:
                break

    print(f"propuestas: {len(proposals)} · sin cambio: {skipped}")
    for p in proposals:
        print(f"\n  {p['nnn']:>3}  {p['why']}")
        print(f"       - {p['old'][:96]}")
        print(f"       + {p['new'][:96]}")

    if not args.apply:
        print("\n(dry run — nada escrito)")
        return 0

    if not proposals:
        print("nada que aplicar")
        return 0

    dest = backup_databases(Path("/Volumes/1TB_HD/Backups-the assistant"), "pre-protocolo-masivo")
    print(f"\nbackup -> {dest}")

    from adapters.hermes import HermesTitleWriter

    w = HermesTitleWriter()
    ok = 0
    for p in proposals:
        if w.rename(p["id"], p["new"], p["db"]):
            ok += 1
        else:
            print(f"  FALLO {p['nnn']}")
    print(f"escritas: {ok} de {len(proposals)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
