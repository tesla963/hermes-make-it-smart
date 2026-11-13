#!/usr/bin/env python3
"""Sincronizar index.json con la verdad: los títulos que hay hoy en state.db.

Por qué existe: el panel escribe en el espejo, los scripts de Python leen el canónico. Cuando el
panel renombra, el espejo queda al día y el canónico se queda con los títulos viejos. Con esa
divergencia pasan dos cosas, las dos malas:

  · la pestaña Process no muestra lo que falta (lee el espejo: al día)
  · un script de Python ve títulos viejos y propone renombrar sesiones YA renombradas

Esta herramienta toma state.db como única fuente de verdad de los títulos y alinea los dos
índices. No decide nada, no clasifica nada: copia lo que la base dice.

    python3 tools/sync_index.py            # muestra qué cambiaría
    python3 tools/sync_index.py --apply    # escribe (con respaldo antes)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

HOME = Path.home()
DATA = HOME / ".hermes/plugin-data/make-it-smart"
ESPEJO = HOME / "Library/Application Support/Hermes/plugin-files/data/make-it-smart"
STATE = HOME / ".hermes/state.db"


def titulos_vivos() -> dict[str, str]:
    con = sqlite3.connect(f"file:{STATE}?mode=ro", uri=True)
    try:
        return {str(i): (t or "") for i, t in
                con.execute("select id, title from sessions")}
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not STATE.exists():
        print("  no hay state.db: nada que sincronizar")
        return 2
    vivos = titulos_vivos()
    cambiados = 0
    informe = []

    for base in (DATA, ESPEJO):
        f = base / "index.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        sesiones = d.get("sessions") or []
        locales = 0
        for s in sesiones:
            sid = str(s.get("id"))
            vivo = vivos.get(sid)
            if not vivo:
                continue
            if str(s.get("raw") or "") != vivo:
                if len(informe) < 8 and base is DATA:
                    informe.append((s.get("n"), str(s.get("raw"))[:44], vivo[:52]))
                s["raw"] = vivo
                locales += 1
            # el sujeto y los ejes salen del propio título canónico cuando existe
            if vivo.startswith(tuple("0123456789")):
                if s.get("sujeto") and str(s.get("sujeto")) not in vivo:
                    pass  # no se toca: el campo puede ser correcto aunque el título cambie
        cambiados += locales
        print(f"  {str(f)[-42:]}: {locales} título(s) desalineado(s) de {len(sesiones)}")
        if args.apply and locales:
            resp = base / f"index-backup-{time.strftime('%Y%m%d_%H%M')}.json"
            shutil.copy2(f, resp)
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"     respaldo: {resp.name} · escrito")

    # Lo contrario también cuenta: sesiones que la base tiene y el índice no conoce.
    # Sin esto, una sesión nueva no aparece en Process y el dueño no puede renombrarla nunca.
    anadidas = 0
    for base in (DATA, ESPEJO):
        f = base / "index.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        sesiones = d.get("sessions") or []
        conocidas = {str(s.get("id")) for s in sesiones}
        siguiente = max([int(s.get("n") or 0) for s in sesiones] or [0]) + 1
        nuevas = []
        for sid, titulo in vivos.items():
            if sid in conocidas or not titulo:
                continue
            nuevas.append({
                "id": sid, "n": siguiente, "mmm": 1, "prof": "default",
                "raw": titulo, "date": "", "sujeto": "", "iq0": "", "iq1": "",
                "iq2": "", "iq3": "", "desc": "", "verb": "", "nueva": True,
            })
            siguiente += 1
        if nuevas:
            sesiones.extend(nuevas)
            d["sessions"] = sesiones
            d["total"] = len(sesiones)
            anadidas += len(nuevas)
            print(f"  {str(f)[-42:]}: +{len(nuevas)} sesión(es) nueva(s) que la base tenía")
            for s in nuevas[:5]:
                print(f"     #{s['n']} «{s['raw'][:52]}»")
            if args.apply:
                (base / f"index-backup-{time.strftime('%Y%m%d_%H%M')}.json").write_bytes(f.read_bytes())
                f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                print("     escrito")

    if informe:
        print("\n  ejemplos (índice → base):")
        for n, antes, ahora in informe:
            print(f"    #{n} «{antes}» → «{ahora}»")
    if not args.apply:
        print("\n  seco — nada escrito. Con --apply alinea los dos índices.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
