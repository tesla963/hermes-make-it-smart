#!/usr/bin/env python3
"""Construir pending_index.json desde la fuente real, no desde una foto vieja.

El plugin leía `pending_index.json` como si fuera un dato eterno, pero ese archivo lo generaba un
indexador externo que nadie corría: en la máquina del dueño tenía dos días. Las autorizaciones
pendientes viven en el disco, en `~/.hermes/pending/{memory,skills}/*.json`, y cada una trae su
`created_at`. Eso es lo que este script lee.

La atribución a una sesión es la parte difícil y no se inventa: una autorización pertenece a la
sesión que estaba viva cuando se creó. Se busca el mensaje más cercano en el tiempo y sólo se
acepta si cae dentro de la ventana (`--ventana`, por defecto 120 s). Si no cae, queda huérfana y
se informa como huérfana — no se le asigna la sesión más cercana "porque sí".

    python3 tools/build_pending.py            # escribe pending_index.json en los dos índices
    python3 tools/build_pending.py --seco     # muestra los números sin escribir
"""
from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
import sys
import time
from pathlib import Path

HOME = Path.home()
DATA = HOME / ".hermes/plugin-data/make-it-smart"
ESPEJO = HOME / "Library/Application Support/Hermes/plugin-files/data/make-it-smart"
PENDING = HOME / ".hermes/pending"
STATE = HOME / ".hermes/state.db"
VENTANA = 120


def autorizaciones() -> list[dict]:
    """Cada archivo pendiente es una autorización: id, subsistema y cuándo se creó."""
    fuera = []
    for sub in ("memory", "skills"):
        d = PENDING / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            creado = j.get("created_at")
            if creado is None:
                creado = f.stat().st_mtime
            fuera.append({
                "id": str(j.get("id") or f.stem),
                "subsistema": "memoria" if sub == "memory" else "skills",
                "created_at": float(creado),
                "resumen": str(j.get("summary") or "")[:120],
            })
    return fuera


def actividad() -> tuple[list[float], list[str]]:
    """Timestamps de mensajes ordenados, con el id de sesión de cada uno."""
    con = sqlite3.connect(f"file:{STATE}?mode=ro", uri=True)
    try:
        filas = con.execute(
            "select timestamp, session_id from messages order by timestamp"
        ).fetchall()
    finally:
        con.close()
    return [f[0] for f in filas], [f[1] for f in filas]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seco", action="store_true")
    ap.add_argument("--ventana", type=float, default=VENTANA)
    args = ap.parse_args()

    if not STATE.exists():
        print("  no hay state.db: no se puede atribuir nada")
        return 2
    auts = autorizaciones()
    if not auts:
        print("  no hay autorizaciones pendientes en ~/.hermes/pending")
        return 0

    tiempos, sesiones = actividad()
    if not tiempos:
        print("  state.db no tiene mensajes: todo quedaría huérfano")
        return 2

    titulos = {}
    con = sqlite3.connect(f"file:{STATE}?mode=ro", uri=True)
    try:
        for sid, titulo in con.execute("select id, title from sessions"):
            titulos[str(sid)] = titulo or ""
    finally:
        con.close()

    por_sesion: dict[str, dict] = {}
    exactas = ventana = huerfanas = 0
    for a in auts:
        i = bisect.bisect_left(tiempos, a["created_at"])
        candidatos = [k for k in (i - 1, i) if 0 <= k < len(tiempos)]
        mejor, delta = None, None
        for k in candidatos:
            d = abs(tiempos[k] - a["created_at"])
            if delta is None or d < delta:
                mejor, delta = k, d
        if mejor is None or delta is None or delta > args.ventana:
            huerfanas += 1
            continue
        sid = sesiones[mejor]
        clave = "memoria" if a["subsistema"] == "memoria" else "skills"
        entrada = por_sesion.setdefault(sid, {"title": titulos.get(sid, ""),
                                              "memoria": [], "skills": []})
        entrada[clave].append(a["id"])
        if delta < 1:
            exactas += 1
        else:
            ventana += 1

    total = sum(len(v["memoria"]) + len(v["skills"]) for v in por_sesion.values())
    salida = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "window_s": args.ventana,
        "counts": {
            "memoria": sum(len(v["memoria"]) for v in por_sesion.values()),
            "skills": sum(len(v["skills"]) for v in por_sesion.values()),
            "total": total,
            "sesiones_con_pendientes": len(por_sesion),
            "exactas": exactas,
            "por_ventana": ventana,
            "huerfanas": huerfanas,
        },
        "by_session": por_sesion,
    }

    c = salida["counts"]
    print(f"  autorizaciones en disco: {len(auts)}")
    print(f"  atribuidas: {total} en {c['sesiones_con_pendientes']} sesiones "
          f"(exactas {exactas} · por ventana {ventana}) · huérfanas {huerfanas}")
    print(f"  memoria {c['memoria']} · skills {c['skills']}")
    if args.seco:
        print("  seco — nada escrito")
        return 0
    for base in (DATA, ESPEJO):
        if base.exists():
            (base / "pending_index.json").write_text(
                json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  escrito pending_index.json en el canónico y en el espejo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
