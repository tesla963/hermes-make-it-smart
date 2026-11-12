#!/usr/bin/env python3
"""Export the titles to CSV so the owner can correct them in a spreadsheet.

Same columns the desktop button produces, so a file from either side can be
filled and handed back without translation.

    python3 tools/export_titles.py                 # all canonical sessions
    python3 tools/export_titles.py --subject "Flight Path"
    python3 tools/export_titles.py --out ~/Desktop  # write somewhere else

Every export gets the next ``[CCCC]`` from the shared ledger, so the desktop UI
and this CLI never issue the same number twice.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import discover_databases, read_sessions  # noqa: E402
from core.paths import export_filename, exports_dir, next_export_number  # noqa: E402

import re  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

COLUMNS = [
    "n", "id", "fecha", "titulo_actual", "sujeto", "iq1", "iq2", "descripcion", "verbo",
    "sujeto_nuevo", "tag1_nuevo", "tag2_nuevo", "descripcion_nueva", "verbo_nuevo",
    "observaciones",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", help="only this subject")
    ap.add_argument("--out", help="directory for the file (default: plugin exports dir)")
    ap.add_argument("--dry-run", action="store_true", help="build it, do not number it")
    args = ap.parse_args()

    rows: list[dict] = []
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            m = TITLE_RE.match(title)
            if not m:
                continue
            g = m.groupdict()
            if args.subject and args.subject.lower() not in g["subject"].lower():
                continue
            rows.append(
                {
                    "n": int(g["nnn"]),
                    "id": rec.id,
                    "fecha": str(rec.created_at or "")[:10],
                    "titulo_actual": title,
                    "sujeto": g["subject"].strip(),
                    "iq1": (g["iq1"] or "").strip(),
                    "iq2": (g["iq2"] or "").strip(),
                    "descripcion": (g["desc"] or "").strip(),
                    "verbo": (g["verb"] or "").strip(),
                    "sujeto_nuevo": "",
                    "tag1_nuevo": "",
                    "tag2_nuevo": "",
                    "descripcion_nueva": "",
                    "verbo_nuevo": "",
                    "observaciones": "",
                }
            )

    rows.sort(key=lambda r: r["n"])
    if not rows:
        print("sin sesiones que exportar", file=sys.stderr)
        return 1

    when = datetime.now()
    count = 0 if args.dry_run else next_export_number()
    name = export_filename(count or 1, when, len(rows))
    dest = Path(args.out).expanduser() if args.out else exports_dir()
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / name

    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} sesiones → {out}")
    print(f"{out.stat().st_size/1024:.0f} KB · {len(COLUMNS)} columnas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
