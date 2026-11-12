#!/usr/bin/env python3
"""Remove dates that leaked into session descriptions.

The title already carries no date — by decision — but older descriptions still
open with one ("06ago Revisar el turno", "2026-08-28 Analizar"). A description
is what the session did, not when: the date lives in the `created_at` column.

Careful: not every date is noise. "Sesión eliminada el 27 de octubre" and
"ENSPA 2019" use a date as meaning. Only a LEADING date is a leftover from an
older title format, and only that is removed here.

    python3 tools/drop_description_dates.py            # report
    python3 tools/drop_description_dates.py --apply    # rewrite titles
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import discover_databases, read_sessions  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

# A description that is ONLY a date ("01sep") is the same leftover with nothing
# left behind: strip it and leave the description empty.
ONLY_DATE = re.compile(
    r"^\s*\d{1,2}\s*\.?\s*(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*\.?\s*$",
    re.I,
)

# "06ago ", "6 de agosto ", "2026-08-28 ", "28/08 "
LEADING_DATE = re.compile(
    r"^\s*(?:"
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}/\d{1,2}(?:/\d{2,4})?"
    r"|\d{1,2}\s*\.?\s*(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*\.?"
    r"|\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
    r")\s+",
    re.I,
)

# A date that carries meaning, never touched — listed so the owner can look.
MEANINGFUL = re.compile(
    r"(eliminada|borrada|descartada|ENSPA|MacBook|ThinkPad|informe|ley|c[aá]mara|modelo)\s.*\b(19|20)\d{2}\b"
    r"|el\s+\d{1,2}\s+de\s+\w+",
    re.I,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    leftovers: list[dict] = []
    meaningful: list[dict] = []
    total = 0

    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            m = TITLE_RE.match(title)
            if not m:
                continue
            total += 1
            g = m.groupdict()
            desc = (g["desc"] or "").strip()
            if not desc:
                continue
            hit = LEADING_DATE.match(desc)
            bare = ONLY_DATE.match(desc)
            if bare:
                leftovers.append(
                    {
                        "session_id": rec.id, "profile": profile, "db_path": str(path),
                        "nnn": g["nnn"], "mmm": g["mmm"], "subject": g["subject"],
                        "iq1": g["iq1"] or "", "iq2": g["iq2"] or "",
                        "verb": (g["verb"] or "").strip(),
                        "before": desc, "after": "", "stamp": bare.group(0).strip(),
                    }
                )
            elif hit:
                cleaned = LEADING_DATE.sub("", desc, count=1).strip()
                cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
                leftovers.append(
                    {
                        "session_id": rec.id,
                        "profile": profile,
                        "db_path": str(path),
                        "nnn": g["nnn"],
                        "mmm": g["mmm"],
                        "subject": g["subject"],
                        "iq1": g["iq1"] or "",
                        "iq2": g["iq2"] or "",
                        "verb": (g["verb"] or "").strip(),
                        "before": desc,
                        "after": cleaned,
                        "stamp": hit.group(0).strip(),
                    }
                )
            elif MEANINGFUL.search(desc):
                meaningful.append({"nnn": g["nnn"], "desc": desc})

    stamps = Counter(r["stamp"] for r in leftovers)
    print(f"sesiones canónicas: {total}")
    print(f"descripciones con fecha al inicio: {len(leftovers)}")
    if stamps:
        print("fechas más repetidas: " + ", ".join(f"{k}×{v}" for k, v in stamps.most_common(6)))
    print(f"descripciones con fecha CON significado (no se tocan): {len(meaningful)}")

    for r in leftovers[:12]:
        print(f"  {r['nnn']}  {r['before'][:60]!r}\n        → {r['after'][:60]!r}")
    if len(leftovers) > 12:
        print(f"  … y {len(leftovers)-12} más")

    if meaningful:
        print("\nfechas con significado, intactas:")
        for r in meaningful[:10]:
            print(f"  {r['nnn']}: {r['desc'][:70]}")

    if not args.apply:
        print("\n(--apply para escribir)")
        return 0

    from adapters.hermes import HermesTitleWriter, backup_databases
    from core.normalize import Facets, render

    dest = Path("/Volumes/1TB_HD/Backups-Lisa")
    if dest.exists():
        print(f"\nbackup → {backup_databases(dest, 'pre-drop-desc-dates')}")

    w = HermesTitleWriter()
    written = 0
    for r in leftovers:
        f = Facets(
            subject=r["subject"],
            subject_ordinal=int(r["mmm"]),
            iq1=r["iq1"],
            iq2=r["iq2"],
            description=r["after"],
            verb=r["verb"],
        )
        new = render(int(r["nnn"]), f)
        if w.rename(r["session_id"], new, r["db_path"]):
            written += 1
    print(f"escritas: {written} de {len(leftovers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
