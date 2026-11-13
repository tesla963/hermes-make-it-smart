#!/usr/bin/env python3
"""Puente entre el auditor y el panel: proposals.json → proposed-index.json.

El auditor (tools/audit_titles.py) escribe `proposals.json` con su propio esquema: categorías,
veredictos y evidencia por campo. El panel, en su pestaña "New Rules", lee `proposed-index.json`
con otro esquema: `changes` y `summary`. Sin este puente, el dueño no puede correr el auditor
desde el panel y el trabajo del auditor se queda en un archivo que nadie mira.

Lo que hace, y no es un simple copiar y pegar: **valida** cada propuesta antes de publicarla.
Una propuesta que no sobrevive la validación no se publica y se informa con su motivo. Un título
mal formado en la base cuesta más que un título que falta.

Validaciones, todas nacidas de errores reales de hoy:
  1. `after` tiene que parsear como título canónico. Un corchete sin cerrar rompe el panel.
  2. El sujeto no puede empezar con verbo conjugado ni ser un saludo: si al quitar el verbo no
     queda un sintagma nominal de 1–3 palabras, la propuesta no sirve.
  3. El sujeto no puede repetir iq1.
  4. La descripción no puede repetir el sujeto (no amplifica nada).
  5. Nada de datos personales: los términos de la lista de bloqueo se rechazan.
  6. Solo se publican las categorías que el dueño aprobó (por defecto: `correccion`).

Uso:

    python3 tools/publish_proposals.py                    # correccion, valida y publica
    python3 tools/publish_proposals.py --categorias correccion,formato
    python3 tools/publish_proposals.py --seco             # muestra sin escribir
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DATA = Path.home() / ".hermes/plugin-data/make-it-smart"
ESPEJO = (Path.home() / "Library/Application Support/Hermes/plugin-files/data/make-it-smart")

TITULO = re.compile(r"^(\d{3,4})\s+\[([^\]]+)\]\s+(\d{3,4})((?:\s*\[[^\]]*\])*)\s*(?:·\s*(.*))?$")
VERBO_CONJ = re.compile(
    r"^(hola|hey|buenas|esta|estan|está|están|se|no|si|ya|puede|debo|necesito|quiero|tengo|"
    r"tarda|falla|abre|cierra|funciona|dice|tiene|hace|sale|entra)\b", re.I)


def bloqueo() -> set[str]:
    """Términos que no pueden aparecer en nada publicado."""
    f = DATA / "publish-blocklist.yaml"
    if not f.exists():
        return set()
    try:
        import yaml
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        terminos = []
        for v in d.values() if isinstance(d, dict) else []:
            if isinstance(v, list):
                terminos += [str(x) for x in v]
            elif isinstance(v, str):
                terminos.append(v)
        return {t.lower() for t in terminos if len(t) > 2}
    except Exception:
        return set()


def validar(after: str, vetos: set[str]) -> tuple[bool, str]:
    m = TITULO.match(after.strip())
    if not m:
        return False, "assembly-error: el título no parsea (corchete sin cerrar o campo de más)"
    sujeto = m.group(2).strip()
    brackets = re.findall(r"\[([^\]]*)\]", m.group(4) or "")
    if len(sujeto.split()) > 3:
        return False, "subject-too-long: más de tres palabras"
    if VERBO_CONJ.match(sujeto):
        return False, "subject-starts-with-a-verb: no es un sintagma nominal"
    if any(b.strip().lower() == sujeto.lower() for b in brackets if b.strip()):
        return False, "subject-repeats-iq1: el sujeto se repite en un campo"
    cola = (m.group(5) or "").strip()
    if cola and sujeto.lower() in cola.lower():
        return False, "description-repeats-the-subject: no amplifica el nombre"
    plano = after.lower()
    for v in vetos:
        if re.search(r"(?<![\w])" + re.escape(v) + r"(?![\w])", plano):
            return False, f"personal-data: contiene un término de la lista de bloqueo"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposals", default=str(DATA / "proposals.json"))
    ap.add_argument("--categorias", default="correccion")
    ap.add_argument("--seco", action="store_true")
    args = ap.parse_args()

    f = Path(args.proposals).expanduser()
    if not f.exists():
        print(f"  no hay propuestas en {f}: corré primero tools/audit_titles.py")
        return 2
    d = json.loads(f.read_text(encoding="utf-8"))
    its = d.get("proposals") or d.get("items") or []
    quiero = {c.strip() for c in args.categorias.split(",")}
    vetos = bloqueo()

    cambios, rechazos = [], []
    for x in its:
        cat = (x.get("categoria") or x.get("category") or "ninguna")
        after = x.get("after")
        if cat not in quiero or not after:
            continue
        bien, motivo = validar(str(after), vetos)
        if not bien:
            rechazos.append({"n": x.get("n"), "motivo": motivo, "after": str(after)[:70]})
            continue
        cambios.append({
            "id": x.get("id"), "n": x.get("n"), "prof": x.get("prof") or "default",
            "before": x.get("before") or "", "after": str(after),
            "rules": x.get("rules") or [cat],
        })

    print(f"  categorías publicadas: {sorted(quiero)}")
    print(f"  propuestas en el archivo: {len(its)} · publicables: {len(cambios)} · rechazadas: {len(rechazos)}")
    for r in rechazos[:10]:
        print(f"    #{r['n']} {r['motivo']}")
        print(f"       {r['after']}")
    for c in cambios[:10]:
        print(f"    #{c['n']}  {c['before'][:40]:40s} → {c['after'][:52]}")

    if args.seco:
        print("\n  seco — nada escrito")
        return 0

    total = len(its)
    salida = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rules_version": "v0.28",
        "source": {"file": f.name, "categories": sorted(quiero),
                   "snapshot": (d.get("summary") or {}).get("snapshot", {})},
        "summary": {
        "evaluadas": total,
            "cambios": len(cambios),
            "identicas": max(total - len(cambios) - len(rechazos), 0),
            "omitidas": len(rechazos),
        },
        "changes": cambios,
        "skipped": rechazos,
    }
    for base in (DATA, ESPEJO):
        if base.exists():
            (base / "proposed-index.json").write_text(
                json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  publicado: proposed-index.json con {len(cambios)} cambios · "
          f"{salida['summary']['omitidas']} rechazadas por validación")
    print("  el panel lo ve al recargar: pestaña New Rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
