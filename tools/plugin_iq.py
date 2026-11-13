#!/usr/bin/env python3
"""Collect what the plugin is made of, so the panel can show it without reading the repo.

The HTML panel can only read its own data directory, so the inventory is built here and written
as `plugin-iq.json`: the rules, the Python scripts with what each one does, and every markdown
document with its text.

    python3 tools/plugin_iq.py
"""
from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DATA = Path.home() / ".hermes/plugin-data/make-it-smart"
OUT = DATA / "plugin-iq.json"


def espejo() -> Path | None:
    import os
    casa = Path.home()
    cands = []
    if os.environ.get("APPDATA"):
        cands.append(Path(os.environ["APPDATA"]) / "Hermes/plugin-files/data/make-it-smart")
    cands += [casa / "Library/Application Support/Hermes/plugin-files/data/make-it-smart",
              casa / ".config/Hermes/plugin-files/data/make-it-smart"]
    return next((c for c in cands if c.is_dir()), None)


def reglas() -> list[dict]:
    ruta = REPO / "core/corrections.yaml"
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    salida = []
    for r in datos:
        if not isinstance(r, dict):
            continue
        salida.append({
            "id": r.get("id", ""),
            "taught": str(r.get("taught", "")),
            "rule": " ".join(str(r.get("rule", "")).split()),
            "control": " ".join(str(r.get("control_question", "")).split()),
        })
    return salida


def scripts() -> list[dict]:
    salida = []
    for p in sorted((REPO / "tools").glob("*.py")):
        try:
            arbol = ast.parse(p.read_text(encoding="utf-8"))
            doc = ast.get_docstring(arbol) or ""
        except Exception:
            doc = ""
        primera = " ".join(doc.split("\n")[0].split()) if doc else "(sin descripción)"
        salida.append({"name": p.name, "what": primera, "lines": len(p.read_text().splitlines())})
    return salida


def docs() -> list[dict]:
    salida = []
    for p in sorted((REPO / "docs").glob("*.md")) + [REPO / "README.md"]:
        if not p.exists():
            continue
        texto = p.read_text(encoding="utf-8")
        titulo = next((l.lstrip("# ").strip() for l in texto.splitlines() if l.startswith("#")), p.stem)
        salida.append({"name": p.name, "title": titulo, "body": texto[:24000],
                       "lines": len(texto.splitlines())})
    return salida


def main() -> int:
    inventario = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rules": reglas(),
        "scripts": scripts(),
        "docs": docs(),
    }
    texto = json.dumps(inventario, ensure_ascii=False)
    OUT.write_text(texto, encoding="utf-8")
    print(f"  reglas: {len(inventario['rules'])} · scripts: {len(inventario['scripts'])} · "
          f"documentos: {len(inventario['docs'])}")
    e = espejo()
    if e:
        (e / OUT.name).write_text(texto, encoding="utf-8")
        print(f"  copiado al espejo: {e / OUT.name}")
    print(f"  escrito: {OUT.name} ({OUT.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
