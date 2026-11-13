#!/usr/bin/env python3
"""Blind evaluation: derive the fields from the text alone and compare against the teacher.

The `--eval` mode in propose_rename.py counts "no change proposed" as agreement, but the
algorithm reads `sujeto` and `iq1` from the index — the same fields the teacher was built
from. That is circular: it measures whether the fields equal themselves.

This script blanks the fields and rebuilds them from the raw title and the first prompt, then
compares the SUBJECT and the iq1 against `teacher_good`. A low number here is the truth; a high
number here would mean the rules really learned something.

    python3 tools/eval_blind.py
    python3 tools/eval_blind.py --show 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.normalize import shrink_subject  # noqa: E402

DATA = Path.home() / ".hermes/plugin-data/make-it-smart"
TEACHER = REPO / "tools/teacher.json"
CANON = re.compile(r"^\d{3,4} \[")


def sin_acentos(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def limpio(titulo: str) -> str:
    """El título sin su andamiaje: ni número, ni corchetes, ni ordinal."""
    t = re.sub(r"^\d{3,4}\s*", "", titulo or "")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"\b\d{3,4}\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def derivar_sujeto(titulo: str, prompt: str) -> str:
    base = limpio(titulo)
    corto, _ = shrink_subject(base)
    if corto:
        return corto
    # sin cabeza clara en el título, se busca la primera entidad del prompt
    corto, _ = shrink_subject(prompt[:300])
    return corto


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--teacher", default=str(TEACHER))
    ap.add_argument("--show", type=int, default=8)
    args = ap.parse_args()

    teacher = json.loads(Path(args.teacher).read_text(encoding="utf-8"))
    good = teacher.get("teacher_good", {})
    index = {}
    for s in json.loads((DATA / "index.json").read_text(encoding="utf-8"))["sessions"]:
        index[str(s.get("id"))] = s

    iguales, distintos, sin_dato = 0, [], 0
    for sid, esperado in good.items():
        s = index.get(str(sid))
        if not s:
            sin_dato += 1
            continue
        claves = s.get("claves") or []
        prompt = str(claves[0])[:600] if isinstance(claves, list) and claves else ""
        obtenido = derivar_sujeto(str(s.get("raw") or esperado.get("raw") or ""), prompt)
        objetivo = str(esperado.get("sujeto") or "")
        if sin_acentos(obtenido) == sin_acentos(objetivo):
            iguales += 1
        else:
            distintos.append((esperado.get("n"), objetivo, obtenido))

    total = iguales + len(distintos)
    pct = iguales / total * 100 if total else 0
    print(f"  teacher_good: {len(good)} · evaluables: {total}")
    print(f"  sujeto derivado del texto == sujeto del maestro: {iguales} ({pct:.1f}%)")
    print(f"  distinto: {len(distintos)}")
    if distintos and args.show:
        print("\n  las primeras diferencias (maestro → derivado):")
        for n, esp, obt in distintos[: args.show]:
            print(f"    #{n}  «{esp[:30]:30s}» → «{obt[:30]}»")
    motivos = Counter("vacío" if not o else ("más largo" if len(o.split()) > len(e.split()) else "otro")
                      for _, e, o in distintos)
    print(f"  forma de las diferencias: {dict(motivos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
