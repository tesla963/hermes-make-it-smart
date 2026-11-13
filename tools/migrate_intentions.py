#!/usr/bin/env python3
"""Fold the retired intention names onto the seven that exist today.

Reads index.json and rewrites the intention field (iq3) using the canonical mapping:
Investigar → Search the Web, Comparar → Compare, Cotizar → Quote, Instalar → Configuration,
Compatibilidad → Compatibility, Testear → Troubleshooting. Unknown values are reported,
never guessed.

Backs up before writing and writes atomically. Idempotent: a second run changes nothing.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

DATA = Path.home() / ".hermes/plugin-data/make-it-smart/index.json"

MAP = {
    "investigar": "Web Search",
    "comparar": "Compare",
    "comparacion": "Compare",
    "comparación": "Compare",
    "cotizar": "Quote",
    "costo": "Quote",
    "instalar": "Configuration",
    "configurar": "Configuration",
    "compatibilidad": "Compatibility",
    "testear": "Troubleshooting",
    "diagnosticar": "Troubleshooting",
    "troubleshooting": "Troubleshooting",
    "web search": "Web Search",
    "compare": "Compare",
    "quote": "Quote",
    "buy": "Buy",
    "comprar": "Buy",
    "compatibility": "Compatibility",
    "configuration": "Configuration",
}
CANON = set(MAP.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=str(DATA))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ruta = Path(args.path).expanduser()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    sesiones = datos.get("sessions", [])

    cambios: dict[tuple[str, str], int] = {}
    desconocidos: dict[str, int] = {}
    tocadas = 0
    for s in sesiones:
        actual = str(s.get("iq3") or "").strip()
        if not actual:
            continue
        nuevo = MAP.get(actual.lower())
        if nuevo is None:
            if actual not in CANON:
                desconocidos[actual] = desconocidos.get(actual, 0) + 1
            continue
        if nuevo != actual:
            cambios[(actual, nuevo)] = cambios.get((actual, nuevo), 0) + 1
            tocadas += 1
            if not args.dry_run:
                s["iq3"] = nuevo

    print(f"  sesiones: {len(sesiones)} · a cambiar: {tocadas}")
    for (viejo, nuevo), n in sorted(cambios.items(), key=lambda x: -x[1]):
        print(f"    {viejo:16s} → {nuevo:16s} {n:4d}")
    if desconocidos:
        print("  valores fuera de la lista (no se tocan):")
        for v, n in sorted(desconocidos.items(), key=lambda x: -x[1]):
            print(f"    {v:24s} {n:4d}")

    if args.dry_run or tocadas == 0:
        print("  dry run — nada escrito" if args.dry_run else "  nada que hacer")
        return 0

    sello = time.strftime("%Y%m%d_%H%M%S")
    backups = ruta.parent / "backups"
    backups.mkdir(exist_ok=True)
    respaldo = backups / f"index.json.pre-intent_{sello}"
    shutil.copy2(ruta, respaldo)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)
    print(f"  escrito · respaldo: {respaldo.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
