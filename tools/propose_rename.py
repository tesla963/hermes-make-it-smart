#!/usr/bin/env python3
"""Write a rename proposal — never apply it.

Reads the live index, rebuilds the canonical title from the fields, and writes
`proposed-index.json` next to it with every change, its rule and its before/after.

The panel's **New Rules** tab reads that file, shows the count and lets the owner apply it with
a backup and a revert. This script only proposes: it never writes a title.

    python3 tools/propose_rename.py            # writes proposed-index.json
    python3 tools/propose_rename.py --dry-run  # prints a summary, writes nothing
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.normalize import shrink_subject

DATA = Path.home() / ".hermes/plugin-data/make-it-smart"


def espejo_del_panel() -> Path | None:
    """The panel reads its own data directory (Electron userData), not the canonical one.
    A proposal written only to the canonical folder is invisible to the panel."""
    casa = Path.home()
    candidatos = [
        casa / "Library/Application Support/Hermes/plugin-files/data/make-it-smart",  # macOS
        Path(str(casa).replace("/root", "/root")) / ".config/Hermes/plugin-files/data/make-it-smart",  # Linux
    ]
    import os
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidatos.insert(0, Path(appdata) / "Hermes/plugin-files/data/make-it-smart")  # Windows
    for c in candidatos:
        if c.is_dir():
            return c
    return None
CANON = re.compile(r"^\d{3,4} \[")
LIMIT = 100


RELLENO = re.compile(
    r"\b(hola|por favor|necesito|quiero|quisiera|puedes|podrias|ayudame|dime|dame|"
    r"me gustaria|o sea|basicamente|simplemente|entonces|bueno|mira|fijate|a ver|"
    r"renombrar|renombra|titulo|sesion|sesiones|plugin|agregar|agrega|poner|pon|"
    r"actualizar|actualiza|revisar|revisa|crear|crea|hacer|haz|verificar|verifica)\b", re.I)


def derivar_sujeto(raw: str) -> str:
    """A subject out of a free-form title: no model, no invention — the words that are left."""
    t = re.sub(r"^\d{3,4}\s*\[[^\]]*\]\s*\d{0,3}\s*", "", raw or "")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = RELLENO.sub(" ", t)
    corto, _cola = shrink_subject(t)
    if corto:
        return corto
    palabras = [w.strip(".,;:¡!¿?()") for w in t.split()]
    palabras = [w for w in palabras if len(w) > 2 and not w.isdigit()]
    return " ".join(palabras[:3]).strip() if palabras else ""


def canon_title(s: dict) -> str:
    """The same shape the panel builds, so a proposal is never prettier than reality."""
    nnn = f"{int(s.get('n') or 0):03d}"
    subj = str(s.get("sujeto") or s.get("iq0") or "").strip() or "Sin sujeto"
    mmm = f"{int(s.get('mmm') or 1):03d}"
    head = f"{nnn} [{subj}] {mmm}"
    for campo in ("iq1", "iq2"):
        v = str(s.get(campo) or "").strip()
        if v:
            head += f" [{v}]"
    if len(head) >= LIMIT:
        return head[:LIMIT].rstrip()
    fecha = str(s.get("fecha") or "").strip()[:10]
    desc = str(s.get("desc") or "").strip()
    verb = str(s.get("verb") or "").strip()
    out = head
    if fecha:
        out += f" {fecha}"
    if desc:
        out += f" {desc}"
    if verb:
        out += f" · {verb}"
    return out[:LIMIT].rstrip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=str(DATA / "index.json"))
    ap.add_argument("--out", default=str(DATA / "proposed-index.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ruta = Path(args.path).expanduser()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    sesiones = datos.get("sessions", [])

    cambios, saltadas = [], []
    for s in sesiones:
        raw = str(s.get("raw") or "").strip()
        sujeto = str(s.get("sujeto") or "").strip()
        iq1 = str(s.get("iq1") or "").strip()
        fuente = str(s.get("source") or "")

        # Maquinaria: bots, subagentes y cron no se renombran nunca.
        if (s.get("esBot") or s.get("esCron") or fuente == "subagent"
                or raw.startswith("Bot Chat") or raw.startswith("Subagent:")):
            saltadas.append({"id": s.get("id"), "title": raw[:60], "why": "machinery"})
            continue

        reglas, campos = [], {}
        # Sin sujeto se deriva de las palabras que quedan del título; si no queda nada,
        # se deja como está en lugar de inventar.
        if not sujeto or sujeto == "Sin sujeto":
            derivado = derivar_sujeto(raw)
            if not derivado:
                saltadas.append({"id": s.get("id"), "title": raw[:60],
                                 "why": "nothing to derive a subject from"})
                continue
            campos["sujeto"] = derivado
            reglas.append("subject-derived-from-title")
        # 1 · un título que no sigue la forma canónica
        if not CANON.match(raw):
            reglas.append("not-canonical-title")
        # 2 · el sujeto repite el programa: una respuesta en dos campos
        if iq1 and sujeto.lower() == iq1.lower():
            reglas.append("subject-repeats-iq1")
            campos["iq1"] = ""
        # 3 · el sujeto es una frase, no un bloque: no se recorta, se pide un nombre.
        # Recortar "Educación Estatal o Particular" a "Educación Estatal o" no es un sujeto.
        if len(sujeto.split()) >= 4 and "sujeto" not in campos:
            corto, cola = shrink_subject(sujeto)
            if corto and corto != sujeto and len(corto.split()) <= 3:
                campos["sujeto"] = corto
                if cola:
                    campos["desc"] = (cola + " " + str(s.get("desc") or "")).strip()[:90]
                reglas.append("subject-shrunk-to-its-head")
            else:
                saltadas.append({"id": s.get("id"), "title": raw[:60],
                                 "why": "subject-too-long and no safe head to cut"})
                continue

        if not reglas:
            continue

        propuesta_campos = dict(s)
        propuesta_campos.update(campos)
        after = canon_title(propuesta_campos)
        if not after or after == raw:
            continue
        cambios.append({
            "id": s.get("id"),
            "prof": s.get("prof") or "default",
            "n": s.get("n"),
            "before": raw,
            "after": after,
            "rules": reglas,
            "fields": campos,
        })

    propuesta = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rules_version": "v0.28",
        "sessions": len(sesiones),
        "changes": cambios,
        "skipped": saltadas,
    }

    print(f"  sesiones: {len(sesiones)} · cambios propuestos: {len(cambios)} · "
          f"omitidas por maquinaria: {len(saltadas)}")
    for c in cambios[:8]:
        print(f"    {c['before'][:46]:46s} → {c['after'][:46]}")
    if args.dry_run:
        print("  dry run — nada escrito")
        return 0

    out = Path(args.out).expanduser()
    texto = json.dumps(propuesta, ensure_ascii=False, indent=1)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(texto, encoding="utf-8")
    tmp.replace(out)
    print(f"  escrito: {out.name} ({out.stat().st_size / 1024:.1f} KB)")

    espejo = espejo_del_panel()
    if espejo:
        dest = espejo / out.name
        tmp2 = dest.with_suffix(".tmp")
        tmp2.write_text(texto, encoding="utf-8")
        tmp2.replace(dest)
        print(f"  copiado al espejo del panel: {dest}")
    else:
        print("  aviso: no encontré el espejo del panel; la pestaña New Rules no verá la propuesta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
