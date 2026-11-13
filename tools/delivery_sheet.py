#!/usr/bin/env python3
"""Hoja de entrega: qué archivos cambiaron desde la última foto, y quién pudo tocarlos.

La regla de trabajo entre dos agentes necesita evidencia, no confianza. Esto hace la evidencia:

    python3 tools/delivery_sheet.py --snapshot     # saca una foto (la línea base)
    python3 tools/delivery_sheet.py --check        # compara contra la última foto
    python3 tools/delivery_sheet.py --check --json

`--check` sale con código 1 si algo cambió, y lista archivo por archivo con su hash antes y
después. Nadie puede modificar un archivo sin que la hoja lo muestre.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FOTO = REPO / ".delivery-baseline.json"
VIGILADOS = ("desktop/plugin.js", "core/", "tools/", "docs/", "tests/", "plugin.yaml",
             "README.md", "CHANGELOG.md")


def archivos() -> list[Path]:
    """Rastreados Y no rastreados. Un archivo nuevo sin `git add` también es un cambio que hay que ver:
    si la hoja solo mirara `git ls-files`, el trabajo de otro agente quedaría invisible."""
    listado = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout
    sueltos = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                             cwd=REPO, capture_output=True, text=True).stdout
    nombres = {f for f in (listado + "\n" + sueltos).split() if f}
    return [REPO / f for f in sorted(nombres)
            if (REPO / f).exists() and f.startswith(VIGILADOS) and not f.startswith(".")]


def hash_de(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:12]


def foto() -> dict:
    return {str(p.relative_to(REPO)): hash_de(p) for p in archivos()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", action="store_true", help="guarda la línea base")
    ap.add_argument("--check", action="store_true", help="compara contra la línea base")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--who", default="", help="quién firma la entrega")
    args = ap.parse_args()

    actual = foto()

    if args.snapshot or not FOTO.exists():
        FOTO.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "who": args.who or "baseline",
                                    "files": actual}, indent=1), encoding="utf-8")
        print(f"  línea base guardada: {len(actual)} archivos · {FOTO.name}")
        return 0

    base = json.loads(FOTO.read_text(encoding="utf-8"))
    antes = base.get("files", {})
    cambiaron = [f for f in actual if f in antes and actual[f] != antes[f]]
    nuevos = [f for f in actual if f not in antes]
    borrados = [f for f in antes if f not in actual]

    if args.json:
        print(json.dumps({"baseline": base.get("ts"), "baseline_who": base.get("who"),
                          "changed": cambiaron, "added": nuevos, "deleted": borrados},
                         indent=1))
    else:
        print(f"  línea base: {base.get('ts')} ({base.get('who')}) · {len(antes)} archivos")
        print(f"  modificados: {len(cambiaron)} · nuevos: {len(nuevos)} · borrados: {len(borrados)}")
        for f in cambiaron:
            print(f"    M {f}  {antes[f]} → {actual[f]}")
        for f in nuevos:
            print(f"    + {f}  {actual[f]}")
        for f in borrados:
            print(f"    - {f}")
        if not (cambiaron or nuevos or borrados):
            print("  nada cambió desde la línea base")

    return 1 if (cambiaron or nuevos or borrados) else 0


if __name__ == "__main__":
    sys.exit(main())
