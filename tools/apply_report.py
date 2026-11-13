#!/usr/bin/env python3
"""What did the last apply actually do? Which titles came out the same, which got fixed?

Compares the last commit backup against the live index and the audit, and answers:

  · unchanged — the applied title was identical to the one already there: the rules agreed
  · changed   — the title moved, with the rule that moved it
  · fixed     — the audit had flagged it and the new title no longer trips that rule

    python3 tools/apply_report.py
    python3 tools/apply_report.py --json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATA = Path.home() / ".hermes/plugin-data/make-it-smart"
CANON = re.compile(r"^\d{3,4} \[")


def ultimo_respaldo() -> dict | None:
    libro = DATA / "commit-last.json"
    if libro.exists():
        try:
            return json.loads(libro.read_text(encoding="utf-8"))
        except Exception:
            pass
    candidatos = sorted((DATA / "backups").glob("commit-backup-*.json"))
    if not candidatos:
        return None
    try:
        return json.loads(candidatos[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    respaldo = ultimo_respaldo()
    if not respaldo:
        print("  no hay respaldo de un commit: nada que comparar todavía")
        return 1

    entradas = respaldo.get("entries") or []
    indice = {}
    idx_path = DATA / "index.json"
    if idx_path.exists():
        for s in json.loads(idx_path.read_text(encoding="utf-8")).get("sessions", []):
            indice[str(s.get("id"))] = s

    iguales, cambiadas, sin_verificar = [], [], []
    for e in entradas:
        antes = str(e.get("title_before") or "")
        despues = str(e.get("title_after") or "")
        actual = str((indice.get(str(e.get("id"))) or {}).get("raw") or "")
        if antes == despues:
            iguales.append((e.get("id"), antes))
        elif actual == despues:
            cambiadas.append((e.get("id"), antes, despues))
        else:
            sin_verificar.append((e.get("id"), antes, despues, actual))

    auditoria = {}
    aud = DATA / "iq-audit.json"
    if aud.exists():
        try:
            for fila in json.loads(aud.read_text(encoding="utf-8")).get("rows", []):
                auditoria[str(fila.get("id"))] = fila
        except Exception:
            pass

    arregladas = []
    for _id, antes, despues in cambiadas:
        fila = auditoria.get(str(_id))
        if not fila:
            continue
        tenia = [p for p in fila.get("problems", []) if p != "iq3-old-vocabulary"]
        if tenia and CANON.match(despues):
            arregladas.append((_id, tenia, antes, despues))

    salida = {
        "commit": respaldo.get("filename"),
        "origin": respaldo.get("origin", "panel"),
        "total": len(entradas),
        "unchanged": len(iguales),
        "changed": len(cambiadas),
        "fixed_by_audit": len(arregladas),
        "unverified": len(sin_verificar),
    }

    if args.json:
        print(json.dumps({**salida,
                          "unchanged_rows": iguales,
                          "changed_rows": cambiadas,
                          "fixed_rows": [{"id": i, "problems": p, "before": b, "after": a}
                                         for i, p, b, a in arregladas]},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"  respaldo comparado: {salida['commit']} (origen: {salida['origin']})")
    print(f"  entradas: {salida['total']}")
    print(f"    iguales (la regla coincidió con lo que ya había): {salida['unchanged']}")
    print(f"    cambiadas:                                        {salida['changed']}")
    print(f"    arregladas que el auditor había marcado:           {salida['fixed_by_audit']}")
    print(f"    sin verificar (el índice no refleja el cambio):    {salida['unverified']}")
    if cambiadas[:10]:
        print("\n  las primeras que cambiaron:")
        for _id, antes, despues in cambiadas[:10]:
            print(f"    {antes[:46]:46s} → {despues[:46]}")
    if arregladas[:10]:
        print("\n  las que el auditor había encontrado mal:")
        for _id, problemas, antes, despues in arregladas[:10]:
            print(f"    {', '.join(problemas)[:40]:40s} {antes[:34]} → {despues[:34]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
