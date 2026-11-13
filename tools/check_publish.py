#!/usr/bin/env python3
"""Refuse to publish anything personal.

Reads the blocklist that lives with the owner's data — never in the repository — and scans the
tracked files. A hit prints the file, the line and the term **redacted**: the point is to find
the leak, not to print it again in a terminal log.

Exit code 0 = clean, 1 = leak.

    python3 tools/check_publish.py
    python3 tools/check_publish.py --staged
    python3 tools/check_publish.py --blocklist ~/otra-lista.yaml
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BLOCKLIST = Path.home() / ".hermes/plugin-data/make-it-smart/publish-blocklist.yaml"
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".mp3", ".mp4", ".mov",
               ".db", ".sqlite", ".pyc", ".woff", ".woff2"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", "reports", "dist", "build"}


def cargar(ruta: Path) -> dict:
    if not ruta.exists():
        return {"terms": [], "paths": [], "patterns": [], "allow": []}
    d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {k: d.get(k) or [] for k in ("terms", "paths", "patterns", "allow")}


def archivos(staged: bool) -> list[Path]:
    if staged:
        out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                             cwd=REPO, capture_output=True, text=True).stdout
        return [REPO / f for f in out.split() if (REPO / f).exists()]
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout
    return [REPO / f for f in out.split() if (REPO / f).exists()]


def redactar(term: str) -> str:
    return f"«{term[:1]}{'·' * max(len(term) - 2, 1)}{term[-1:]}» ({len(term)} caracteres)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blocklist", default=str(BLOCKLIST))
    ap.add_argument("--staged", action="store_true", help="only what is staged right now")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    reglas = cargar(Path(args.blocklist).expanduser())
    if not reglas["terms"] and not reglas["patterns"]:
        print("  sin lista de bloqueo: nada que comprobar")
        print(f"  crea {BLOCKLIST} para activar la guardia")
        return 0

    # un término se busca como palabra, no como pedazo: "lisa" no debe casar con "capitalisation"
    patrones = [("term", re.compile(r"(?<![\w])" + re.escape(t) + r"(?![\w])", re.I))
                for t in reglas["terms"]]
    patrones += [("path", p) for p in reglas["paths"]]
    patrones += [("pattern", p) for p in reglas["patterns"]]
    permitidos = set(reglas["allow"])

    hallazgos: list[tuple[str, int, str]] = []
    revisados = 0
    for p in archivos(args.staged):
        if p.name in permitidos or p.suffix.lower() in SKIP_SUFFIX:
            continue
        if any(parte in SKIP_DIRS for parte in p.parts):
            continue
        try:
            lineas = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        revisados += 1
        for n, linea in enumerate(lineas, 1):
            for tipo, patron in patrones:
                if tipo == "pattern":
                    m = re.search(patron, linea)
                    if m:
                        hallazgos.append((str(p.relative_to(REPO)), n, tipo))
                        break
                elif hasattr(patron, "search"):
                    if patron.search(linea):
                        hallazgos.append((str(p.relative_to(REPO)), n, tipo))
                        break

    print(f"  archivos revisados: {revisados} · términos en la lista: {len(reglas['terms'])}"
          f" · patrones: {len(reglas['patterns'])}")
    if not hallazgos:
        print("  limpio: ningún dato personal en lo que se va a publicar")
        return 0

    print(f"\n  {len(hallazgos)} hallazgo(s):")
    for f, n, tipo in hallazgos[:40]:
        print(f"    {f}:{n}  ({tipo})")
    if args.verbose:
        print("\n  detalle redactado:")
        for f, n, tipo in hallazgos[:40]:
            print(f"    {f}:{n} → {redactar(tipo)}")
    print("\n  No se publica hasta limpiarlo. El término no se imprime a propósito.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
