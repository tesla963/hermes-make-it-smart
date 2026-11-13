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
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from core.normalize import shrink_subject, split_verb_subject

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
    # NEVER use '·' inside the description; '·' is reserved exclusively for the canonical verb tail.
    if clean_tail.split()[0].lower() in {"a", "de", "en", "con", "por", "para", "sobre", "hacia"}:
        return f"{d} {clean_tail}"
    return f"{d}; {clean_tail}"


def _marcas_conocidas() -> set[str]:
    """Marcas del cheat sheet en minúsculas: sirven para no poner una marca como sujeto."""
    import yaml
    try:
        d = yaml.safe_load((REPO / "core/cheat_sheet.yaml").read_text(encoding="utf-8")) or {}
        return {str(k).lower() for k in list((d.get("marcas") or {})) + list((d.get("programas") or {}))}
    except Exception:
        return set()


MARCAS_CONOCIDAS = _marcas_conocidas()


def derivar_sujeto(raw: str) -> tuple[str, str]:
    """A subject and description out of a free-form title: no model, no invention."""
    t = re.sub(r"^\d{3,4}\s*\[[^\]]*\]\s*\d{0,3}\s*", "", raw or "")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = RELLENO.sub(" ", t)
    # El verbo abre la frase pero NO es el sujeto: es la intención. Y la marca es iq1.
    verbo, cuerpo = split_verb_subject(t)
    corto, cola = shrink_subject(cuerpo or t)
    if not corto:
        # el recorte se niega a adivinar; el cuerpo ya está limpio, se usa tal cual
        corto = " ".join((cuerpo or t).split()[:3]).strip(" ,.;:-")
        if corto and corto[:1].islower():
            corto = corto[0].upper() + corto[1:]
    if corto:
        # si el recorte eligió una marca en vez del objeto, se prefiere el objeto
        palabras = [w for w in (cuerpo or t).split()]
        sin_marca = [w for w in palabras if w.lower() not in MARCAS_CONOCIDAS]
        if corto.lower() in MARCAS_CONOCIDAS and len(sin_marca) >= 2:
            corto = " ".join(sin_marca[:3])
            corto = corto[0].upper() + corto[1:]
        return corto, cola
    return "", ""


def repair_mutilated_subject(sujeto: str, desc: str) -> tuple[str, str] | None:
    """Repair subjects that were sliced mid-word by legacy 35-char caps."""
    from core.normalize import KNOWN_ENTITIES, _is_mutilated
    if not any(_is_mutilated(w) for w in sujeto.split()):
        return None
    d = (desc or "").strip()
    d_low = d.lower()
    for k, v in KNOWN_ENTITIES.items():
        if re.search(r"\b" + re.escape(k) + r"\b", d_low):
            clean_d = re.sub(r"\b(de|del|en|para|con)\s+" + re.escape(k) + r"\b", "", d, flags=re.I).strip()
            clean_d = re.sub(r"\b" + re.escape(k) + r"\b", "", clean_d, flags=re.I).strip()
            clean_d = re.sub(r"\s+", " ", clean_d).strip(" ,.;:-")
            return v, clean_d
    if "make it smart" in d_low:
        clean_d = re.sub(r"del plugin make it smart", "", d, flags=re.I).strip()
        clean_d = re.sub(r"\s+", " ", clean_d).strip(" ,.;:-")
        return "Make It Smart", clean_d
    return None


def canon_title(s: dict) -> str:
    """The same shape desktop/plugin.js builds, so a proposal is never prettier than reality."""
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

    verb = str(s.get("verb") or "").strip()
    tail = f" · {verb}" if verb else ""
    budget = LIMIT - len(head) - 1 - len(tail)

    desc = str(s.get("desc") or "").strip()
    if desc and budget > 0:
        if len(desc) > budget:
            desc = desc[:budget].rstrip()
        return f"{head} {desc}{tail}".strip()
    if tail and len(head) + len(tail) + 1 <= LIMIT:
        return f"{head}{tail}".strip()
    return head


def run_teacher(teacher_path: Path) -> int:
    """Evaluate 100% title reproduction using teacher fields."""
    if not teacher_path.exists():
        print(f"  error: no existe el archivo maestro: {teacher_path}", file=sys.stderr)
        return 1

    datos = json.loads(teacher_path.read_text(encoding="utf-8"))
    good = datos.get("teacher_good", datos)
    bad = datos.get("teacher_bad", {})

    total = len(good)
    exactos = 0
    diferencias = []

    for sid, t in good.items():
        raw = t.get("raw") or ""
        built = canon_title(t)
        if built == raw:
            exactos += 1
        else:
            motivo = []
            if len(raw) > LIMIT:
                motivo.append("raw supera LIMIT")
            if t.get("sujeto") not in raw:
                motivo.append("sujeto no coincide con raw")
            diferencias.append({
                "id": sid,
                "n": t.get("n"),
                "raw": raw,
                "built": built,
                "why": ", ".join(motivo) or "diferencia en ensamblado",
            })

    pct = (exactos / total * 100) if total else 0.0
    print("=== Corrida con trampa (--teacher) ===")
    print(f"  sesiones en teacher_good: {total} · reproducidas exactas: {exactos} ({pct:.1f}%) · "
          f"diferencias: {len(diferencias)}")
    if bad:
        print(f"  sesiones en teacher_bad:  {len(bad)} (contraejemplos para contrastar mejoras)")

    if diferencias:
        print("\n  Diferencias encontradas:")
        for d in diferencias[:10]:
            print(f"    #{d['n']} ({d['id']}): {d['why']}")
            print(f"      RAW:   {d['raw']}")
            print(f"      BUILT: {d['built']}")
        return 1

    print("  reproducción perfecta: 100% de los títulos de teacher_good ensamblados exactamente")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=str(DATA / "index.json"))
    ap.add_argument("--out", default=str(DATA / "proposed-index.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--teacher", nargs="?", const=str(REPO / "tools/teacher.json"), default=None,
                    help="Run in teacher mode to verify title reconstruction")
    ap.add_argument("--eval", action="store_true",
                    help="Measure agreement of the proposal against tools/teacher.json")
    args = ap.parse_args()

    if args.teacher:
        return run_teacher(Path(args.teacher).expanduser())

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
            derivado, desc_derivada = derivar_sujeto(raw)
            if not derivado:
                saltadas.append({"id": s.get("id"), "title": raw[:60],
                                 "why": "nothing to derive a subject from"})
                continue
            campos["sujeto"] = derivado
            # la marca que aparece en el título es iq1, no sujeto
            if not str(s.get("iq1") or "").strip():
                for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9]+", raw):
                    if w.lower() in MARCAS_CONOCIDAS:
                        campos["iq1"] = w[:1].upper() + w[1:]
                        break
            if desc_derivada and not s.get("desc"):
                campos["desc"] = desc_derivada[:90]
            reglas.append("subject-derived-from-title")
        # 1 · un título que no sigue la forma canónica
        if not CANON.match(raw):
            reglas.append("not-canonical-title")
        # 2 · el sujeto repite el programa: una respuesta en dos campos
        if iq1 and sujeto.lower() == iq1.lower():
            reglas.append("subject-repeats-iq1")
            campos["iq1"] = ""
        # 3 · el sujeto es una frase o está mutilado: reparar o recortar a la cabeza limpia.
        # El verbo es intención, nunca sujeto; el adjetivo de estado se cae.
        verbo, cuerpo = split_verb_subject(sujeto)
        if verbo and cuerpo and cuerpo != sujeto:
            campos["sujeto"] = cuerpo
            reglas.append("verb-moved-from-subject-to-intention")
            if not str(s.get("iq3") or "").strip():
                from core.taxonomy import normalize_intention
                intencion = normalize_intention(verbo)
                if intencion:
                    campos["iq3"] = intencion
            sujeto = cuerpo

        # una marca dentro del sujeto es iq1, no sujeto
        marca = str(iq1 or "").strip()
        if marca and marca.lower() in sujeto.lower().split():
            restante = " ".join(w for w in sujeto.split() if w.lower() != marca.lower()).strip()
            if len(restante.split()) >= 2:
                campos["sujeto"] = restante
                sujeto = restante

        if len(sujeto.split()) >= 4 and "sujeto" not in campos:
            repaired = repair_mutilated_subject(sujeto, str(s.get("desc") or ""))
            if repaired:
                campos["sujeto"], campos["desc"] = repaired
                reglas.append("mutilated-subject-repaired")
            else:
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

    if args.eval:
        teacher_path = REPO / "tools/teacher.json"
        if teacher_path.exists():
            teacher_raw = json.loads(teacher_path.read_text(encoding="utf-8"))
            teacher_good = teacher_raw.get("teacher_good", teacher_raw)
            teacher_bad = teacher_raw.get("teacher_bad", {})
            cambios_by_id = {c["id"]: c for c in cambios}

            # 1. Medir acuerdo SOLO contra teacher_good
            good_exactos = 0
            good_diffs = []
            for sid, t in teacher_good.items():
                if sid in cambios_by_id:
                    c = cambios_by_id[sid]
                    good_diffs.append((t["n"], t["raw"], c["after"], c["rules"]))
                else:
                    good_exactos += 1
            pct_good = (good_exactos / len(teacher_good) * 100) if teacher_good else 0.0

            # 2. Medir corrección de teacher_bad
            bad_corregidas = 0
            bad_sin_tocar = 0
            for sid, t in teacher_bad.items():
                if sid in cambios_by_id:
                    bad_corregidas += 1
                else:
                    bad_sin_tocar += 1
            pct_bad_corr = (bad_corregidas / len(teacher_bad) * 100) if teacher_bad else 0.0

            print("\n=== Evaluación contra el Maestro (--eval) ===")
            print("  AVISO: mide 'no propuso cambio' como acuerdo, y lee los campos del índice,")
            print("  que es la misma fuente del maestro. Sirve para detectar regresiones, no como")
            print("  medida de inteligencia. Para eso hace falta la corrida con modelo.")
            print(f"  teacher_good ({len(teacher_good)} sesiones): acuerdo exacto: {good_exactos} ({pct_good:.2f}%) · diferencias: {len(good_diffs)}")
            print(f"  teacher_bad  ({len(teacher_bad)} sesiones): corregidas por reglas: {bad_corregidas} ({pct_bad_corr:.1f}%) · sin tocar: {bad_sin_tocar}")
            if good_diffs:
                print("  Diferencias en teacher_good:")
                for n, raw, after, r in good_diffs[:5]:
                    print(f"    #{n} ({', '.join(r)}):\n      RAW:   {raw}\n      AFTER: {after}")

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
