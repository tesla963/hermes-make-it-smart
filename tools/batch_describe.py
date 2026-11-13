#!/usr/bin/env python3
"""Generar descripciones en lotes, con caché y reanudable.

La descripción la escribe el modelo leyendo el post inicial — eso vive en
tools/rename_sessions.py (descripcion_llm). Este script sólo organiza el trabajo en lotes para no
hacer 860 llamadas de golpe: toma N sesiones, pide la descripción de cada una, y deja un registro
en disco. Lo que ya está en la caché no se vuelve a pedir, así que se puede cortar y retomar sin
perder nada.

    python3 tools/batch_describe.py --limit 50            # un lote
    python3 tools/batch_describe.py --limit 50 --solo-faltan
    python3 tools/batch_describe.py --estado               # cuántas faltan

El resultado de cada lote queda en ~/.hermes/plugin-data/make-it-smart/descriptions-log.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DATA = Path.home() / ".hermes/plugin-data/make-it-smart"
CACHE = DATA / "descriptions.json"
LOG = DATA / "descriptions-log.jsonl"
CANON = r"^\d{3,4}\s+\[([^\]]+)\]"


def sujeto_de(raw: str) -> str:
    import re
    m = re.match(CANON, str(raw or "").strip())
    return m.group(1).strip() if m else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--estado", action="store_true")
    ap.add_argument("--pausa", type=float, default=1.0, help="segundos entre llamadas")
    args = ap.parse_args()

    from tools.rename_sessions import descripcion_llm  # noqa: PLC0415

    from tools.scope import es_maquinaria, tiene_numero  # noqa: PLC0415
    idx = json.loads((DATA / "index.json").read_text(encoding="utf-8"))["sessions"]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    # Sólo tiene sentido describir sesiones renombradas y de usuario: la maquinaria (bots,
    # subagentes, cron) no se renombra y suele no tener post inicial, así que pedirle una
    # descripción al modelo es gastar una llamada para recibir nada.
    faltan = [s for s in idx if str(s.get("id")) not in cache]
    pendientes = [s for s in faltan if tiene_numero(str(s.get("raw"))) and not es_maquinaria(s)]
    fuera = len(faltan) - len(pendientes)

    if args.estado:
        print(f"  sesiones: {len(idx)} · con descripción: {len(cache)} · describibles: {len(pendientes)}")
        return 0

    lote = pendientes[: args.limit]
    print(f"  lote de {len(lote)} (faltan {len(pendientes)})")
    t0 = time.time()
    ok = fallo = 0
    for i, s in enumerate(lote, 1):
        ident = str(s.get("id"))
        sujeto = sujeto_de(str(s.get("raw")))
        frase, fuente = descripcion_llm(ident, sujeto)
        if frase:
            ok += 1
        else:
            fallo += 1
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": ident,
                                "n": s.get("n"), "sujeto": sujeto, "desc": frase,
                                "fuente": fuente}, ensure_ascii=False) + "\n")
        if i % 10 == 0:
            print(f"    {i}/{len(lote)} · ok {ok} · fallo {fallo} · {time.time()-t0:.0f}s")
        time.sleep(args.pausa)

    print(f"  lote terminado: {ok} con descripción · {fallo} sin · {time.time()-t0:.0f}s")
    restantes = len(pendientes) - len(lote)
    print(f"  quedan {restantes} para el próximo lote" + ("  → corré otra vez" if restantes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
