#!/usr/bin/env python3
"""Audit session subjects: they must be a point, not a sentence.

A subject competes with the description when it reads like a phrase. The rules:

  S1  No verb. "Comparación con Ollama", "Aprender a programar", "Buscar virus"
      — the verb belongs in the `verb` field, not in the noun.
  S2  No linking prepositions that turn a noun into a clause:
      " con ", " para ", " que ", " sobre ", " entre ", " desde ", " hasta ",
      " a ", " vs ", " versus ". ("Cierre de sesión" is fine: "de" names a thing.)
  S3  Length. Median is 17 characters. Anything past 26 is suspect; past 30 is a
      sentence in disguise.
  S4  It must not repeat Iq1.
  S5  ALL CAPS or Title Case noise is normalised.

Usage
-----
    python3 tools/audit_subjects.py                  # report
    python3 tools/audit_subjects.py --csv out.csv    # export for review
    python3 tools/audit_subjects.py --apply          # apply the dictated fixes
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import discover_databases, read_sessions  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*(?:\[(?P<iq2>[^\]]*)\])?\s*(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

VERB_START = re.compile(
    r"^(comparaci[oó]n|comparar|analizar|an[aá]lisis|buscar|b[uú]squeda|instalar|"
    r"instalaci[oó]n|configurar|configuraci[oó]n|revisar|revisi[oó]n|verificar|"
    r"investigar|corregir|crear|hacer|elegir|comprar|mirar|leer|probar|"
    r"solucionar|monitorear|respaldar|migrar|organizar|documentar|evaluar|"
    r"determinar|aprender|mejorar|explicar)\s+",
    re.I,
)

LINKING = re.compile(r"\s(con|para|que|sobre|entre|desde|hasta|a|vs\.?|versus)\s", re.I)

# A preposition that belongs to the concept's own name is legal:
# "Descuentos a Jubilados" is a benefit, not a sentence.
NAMED_CONCEPTS = ("descuentos a jubilados", "beneficios a jubilados")

COMPARISON = re.compile(r"\s(vs\.?|versus|frente a)\s", re.I)

MAX_OK = 26
SENTENCE_OK = 30

# The owner's dictated fixes: nnn -> (sujeto, iq1, iq2, country)
DICTATED: dict[int, dict[str, str]] = {
    98: {"subject": "Samurái Ciego", "iq1": "Película", "iq2": "Serie", "country": "Japón"},
    97: {"subject": "Buscador OS"},
    96: {"subject": "Tarea Cron"},
    95: {"subject": "Programming Language"},
    93: {"subject": "Ollama"},
}


def flags(subject: str, iq1: str) -> list[str]:
    s = (subject or "").strip()
    out: list[str] = []
    if not s:
        return ["S0 vacío"]
    if VERB_START.match(s):
        out.append("S1 verbo")
    elif re.search(r"\b(comparar|comparaci[oó]n|instalar|verificar|analizar|organizar|buscar)\b", s, re.I):
        out.append("S1 verbo")
    if LINKING.search(s) and s.lower() not in NAMED_CONCEPTS:
        out.append("S2 preposición")
    if COMPARISON.search(s):
        # The comparison belongs in the description; Iq2 becomes "Comparación".
        out.append("S5 comparación")
    if len(s) > SENTENCE_OK:
        out.append("S3 oración")
    elif len(s) > MAX_OK:
        out.append("S3 largo")
    if iq1 and s.lower() == iq1.lower():
        out.append("S4 = iq1")
    if re.search(r"\bde\s+\w+", s) and len(s) > 22:
        out.append("S2 de+algo")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    rows: list[dict] = []
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            m = TITLE_RE.match((rec.title or "").strip())
            if not m:
                continue
            g = m.groupdict()
            f = flags(g["subject"], g["iq1"] or "")
            rows.append(
                {
                    "session_id": rec.id,
                    "profile": profile,
                    "nnn": g["nnn"],
                    "subject": g["subject"],
                    "len": len(g["subject"]),
                    "iq1": g["iq1"] or "",
                    "iq2": g["iq2"] or "",
                    "flags": f,  # list, so "S2 preposición" counts as one flag
                    "title": (rec.title or ""),
                }
            )

    lens = sorted(r["len"] for r in rows)
    print(f"sesiones con titulo canónico: {len(rows)}")
    print(
        f"largo del sujeto → mediana {statistics.median(lens):.0f} · "
        f"media {statistics.mean(lens):.1f} · p90 {lens[int(len(lens)*.9)]} · máx {max(lens)}"
    )

    sus = [r for r in rows if r["flags"]]
    print(f"\nsospechosos: {len(sus)}  ({len(sus)/len(rows)*100:.1f}%)")
    counts: dict[str, int] = {}
    for r in sus:
        for f in r["flags"]:
            counts[f] = counts.get(f, 0) + 1
    for f, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {f:<22} {n}")

    print(f"\npeores {args.top}:")
    for r in sorted(sus, key=lambda x: -x["len"])[: args.top]:
        print(f"  {r['nnn']} [{r['len']:>2}] {r['subject']!r}   ({', '.join(r['flags'])})")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            fields = [k for k in rows[0] if k != "flags"] + ["flags"]
            w = csv.DictWriter(fh, fieldnames=fields)
            rows_csv = [{**r, "flags": ", ".join(r["flags"])} for r in rows]
            w.writeheader()
            w.writerows(sorted(rows_csv, key=lambda x: -x["len"]))
        print(f"\ncsv -> {args.csv}")

    if args.apply:
        from adapters.hermes import HermesTitleWriter, backup_databases
        from core.normalize import Facets, render

        dest = Path("/Volumes/1TB_HD/Backups-Lisa")
        if dest.exists():
            print(f"\nbackup -> {backup_databases(dest, 'pre-subject-audit')}")
        w = HermesTitleWriter()
        pairs = []
        for r in rows:
            n = int(r["nnn"])
            if n not in DICTATED:
                continue
            d = DICTATED[n]
            m = TITLE_RE.match(r["title"])
            if not m:
                continue
            g = m.groupdict()
            f = Facets(
                subject=d.get("subject", g["subject"]),
                subject_ordinal=int(g["mmm"]),
                iq1=d.get("iq1", g["iq1"] or ""),
                iq2=d.get("iq2", g["iq2"] or ""),
                country=d.get("country", ""),
                description=(g["desc"] or "").strip(),
                verb=(g["verb"] or "").strip(),
            )
            pairs.append((r["session_id"], render(n, f)))
        for sid, t in pairs:
            print(f"  -> {t[:100]}")
        print(f"\n{len(pairs)} correcciones dictadas")
        rep = w.rename_batch(pairs)
        print(rep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
