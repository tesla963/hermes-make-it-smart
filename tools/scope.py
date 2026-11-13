#!/usr/bin/env python3
"""Qué sesiones se pueden auditar: solo las que ya fueron renombradas.

El dueño lo fijó como regla: un auditor no puede tocar una sesión que no ha sido renombrada.
Primero se renombra, después se audita. Nunca al revés, y nunca las dos cosas sobre la misma
sesión en la misma pasada.

"Creada" no quiere decir "renombrada". Una sesión está renombrada si cumple alguna de estas:

  1. Su id está en el journal de renombrados (`rename-journal.json`) — la prueba más fuerte:
     un script o el panel le escribió un título y lo anotó.
  2. Su id aparece en algún `commit-backup-*.json` — el panel renombró y respaldó.
  3. Su título ya sigue la forma canónica `NNN [Sujeto] MMM …` — fue estructurado por el plugin
     en algún momento, aunque no quede el rastro del journal.

Una sesión con título virgen ("Firefox tarda mucho en arrancar") NO es auditable: no tiene
sujeto, ni iq1, ni iq2 que auditar. Su primer paso es el renombrado.

Uso desde otro script:

    from scope import ya_renombradas, es_auditable
    listas = ya_renombradas(index_sessions)
    if not es_auditable(s, listas): skip
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HOME = Path.home()
DATA = HOME / ".hermes/plugin-data/make-it-smart"
JOURNAL = DATA / "rename-journal.json"
BACKUPS = DATA / "backups"
CANON = re.compile(r"^\d{3,4} \[[^\]]+\] \d{3}")
MAQUINARIA = re.compile(r"^(Subagent|Bot Chat|Cron|Cronjob|Hermes Agent Cron)\b", re.I)


def _journal_ids() -> set[str]:
    if not JOURNAL.exists():
        return set()
    try:
        return set(json.loads(JOURNAL.read_text(encoding="utf-8")).keys())
    except Exception:
        return set()


def _backup_ids() -> set[str]:
    ids: set[str] = set()
    if not BACKUPS.exists():
        return ids
    for f in sorted(BACKUPS.glob("commit-backup-*.json"))[-40:]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in d.get("entries") or []:
            if e.get("id"):
                ids.add(str(e["id"]))
    return ids


def ya_renombradas(sesiones: list[dict]) -> set[str]:
    """Los ids que ya pasaron por un renombrado, por la vía que sea."""
    listas = _journal_ids() | _backup_ids()
    for s in sesiones:
        raw = str(s.get("raw") or "").strip()
        if raw and CANON.match(raw):
            listas.add(str(s.get("id")))
    return listas


def es_maquinaria(s: dict) -> bool:
    return bool(MAQUINARIA.match(str(s.get("raw") or "").strip()))


def es_auditable(s: dict, renombradas: set[str]) -> tuple[bool, str]:
    """(sí/no, motivo). El motivo se informa; no se descarta en silencio."""
    if es_maquinaria(s):
        return False, "machinery: never renamed, never audited"
    if str(s.get("id")) not in renombradas:
        return False, "not renamed yet: rename comes first, the audit comes after"
    return True, ""


def resumen(sesiones: list[dict]) -> dict:
    ren = ya_renombradas(sesiones)
    auditables = [s for s in sesiones if es_auditable(s, ren)[0]]
    return {
        "total": len(sesiones),
        "renombradas": len([s for s in sesiones if str(s.get('id')) in ren]),
        "auditables": len(auditables),
        "pendientes_de_renombrar": len([s for s in sesiones
                                        if es_auditable(s, ren)[1].startswith("not renamed")]),
        "maquinaria": len([s for s in sesiones if es_maquinaria(s)]),
    }


if __name__ == "__main__":
    idx = json.loads((DATA / "index.json").read_text(encoding="utf-8"))["sessions"]
    r = resumen(idx)
    print(f"  total: {r['total']} · renombradas: {r['renombradas']} · auditables: {r['auditables']}")
    print(f"  pendientes de renombrar (no auditables): {r['pendientes_de_renombrar']} · maquinaria: {r['maquinaria']}")
