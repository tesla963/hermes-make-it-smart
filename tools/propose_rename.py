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


def merge_description(cola: str, desc: str) -> str:
    """Merge words removed from the subject into the description without duplicating."""
    d = (desc or "").strip()
    # Strip any accidental title prefix like "024 [Hola DeepSeek...] 001" or "[Brave] ["
    d = re.sub(r"^\d{3,4}\s*\[[^\]]*\]\s*(\d{3,4})?\s*(?:\[[^\]]*\]\s*)*", "", d).strip()
    d = re.sub(r"\[[^\]]*$", "", d).strip()
    d = re.sub(r"^\[[^\]]*\]\s*", "", d).strip()
    d = d.strip(" [].;:-")

    c = (cola or "").strip()
    if not c:
        return d
    if not d or len(d) < 3:
        return c

    # Normalize for comparison
    c_clean = re.sub(r"[^\w\s]", " ", c.lower())
    d_clean = re.sub(r"[^\w\s]", " ", d.lower())
    c_words = set(c_clean.split()) - {"de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "a", "en", "con", "por", "para", "al", "que"}
    d_words = set(d_clean.split())

    # If cola words are already in description, don't duplicate
    if not c_words or c_words.issubset(d_words) or (len(c_words - d_words) <= 1 and len(c_words) >= 2):
        return d
    if d.lower().startswith(c.lower()):
        return d
    if c.lower().startswith(d.lower()):
        return c

    # Filter out individual words already in description
    new_words = [w for w in c.split() if w.lower().strip(".,;:¡!¿?\"'") not in d_words]
    if not new_words:
        return d
    clean_tail = " ".join(new_words).strip(" ,.;:-")
    if not clean_tail:
        return d
    return f"{d} · {clean_tail}"


def derivar_sujeto(raw: str) -> str:
    """A subject out of a free-form title: no model, no invention — the words that are left."""
    t = re.sub(r"^\d{3,4}\s*\[[^\]]*\]\s*\d{0,3}\s*", "", raw or "")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = RELLENO.sub(" ", t)
    corto, _cola = shrink_subject(t)
    if corto:
        return corto
    return ""


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
                    merged = merge_description(cola, str(s.get("desc") or ""))
                    if merged:
                        campos["desc"] = merged[:90]
                reglas.append("subject-shrunk-to-its-head")
            else:
                saltadas.append({"id": s.get("id"), "title": raw[:60],
                                 "why": "subject-too-long and no safe head to cut"})
                continue

        # Re-verificar si el sujeto resultante repite iq1 tras el recorte
        suj_final = campos.get("sujeto") or sujeto
        iq1_final = campos.get("iq1", iq1)
        if iq1_final and suj_final.lower() == iq1_final.lower():
            if "subject-repeats-iq1" not in reglas:
                reglas.append("subject-repeats-iq1")
            campos["iq1"] = ""

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

    total = len(sesiones)
    saltadas_count = len(saltadas)
    cambios_count = len(cambios)
    iguales_count = total - saltadas_count - cambios_count

    propuesta = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rules_version": "v0.28",
        "sessions": total,
        "total": total,
        "unchanged": iguales_count,
        "changes": cambios,
        "skipped": saltadas,
    }

    print(f"  sesiones: {total} · cambios propuestos: {cambios_count} · "
          f"idénticas: {iguales_count} · omitidas: {saltadas_count}")
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
