#!/usr/bin/env python3
"""Audit the ten fields: do they follow the new rules, and do they tell a story?

Reads every session in the catalogue and, for each one, asks four questions:

  1. Do the fields break a structural rule? (iq0 = iq1, iq0 with a verb, an intention that
     does not exist, a context that is not a store/country/machine)
  2. Does the first user prompt — where the subject and the description usually live — contain
     the words the fields claim? A field nobody can find in the prompt is a guess.
  3. Do the fields tell a story? Subject + program + intent read as one sentence or they do not.
  4. Did this session slip through the old rules? A title that predates the new vocabulary is
     a candidate for reconstruction, not a session that is fine.

Writes `iq-audit.json` and prints a summary. No model: every verdict is a rule with a reason.

    python3 tools/audit_iq.py
    python3 tools/audit_iq.py --limit 20 --show
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = Path.home() / ".hermes/plugin-data/make-it-smart"

INTENCIONES = {"Troubleshooting", "Web Search", "Compatibility", "Buy", "Quote", "Compare",
               "Configuration"}
VIEJAS = {"Investigar", "Comparar", "Testear", "Compatibilidad", "Instalar", "Cotizar"}
TIENDAS = {"amazon", "ebay", "aliexpress", "alibaba", "walmart", "best buy", "newegg",
           "mercado libre", "taobao", "b&h"}
PAISES = {"panamá", "panama", "colón", "balboa", "cristóbal", "miami", "españa", "china",
          "alemania", "méxico", "colombia", "estados unidos", "eeuu", "bahréin", "dubái"}
MAQUINAS = {"mac mini", "mac studio", "macbook", "thinkpad", "imac", "vps", "teléfono",
            "telefono", "iphone", "ipad", "servidor", "desktop", "laptop", "portátil", "drone"}
VERBO = re.compile(r"\b\w+(?:ar|er|ir|ando|iendo|ado|ido)\b", re.I)
STOP = set("de la el los las un una que y a en con por para del al se lo su mi es son "
           "the of and to in for with on is are this that".split())


def sin_acentos(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def contenido(texto: str) -> set[str]:
    palabras = re.findall(r"[a-záéíóúñ0-9]{3,}", (texto or "").lower())
    return {sin_acentos(w) for w in palabras if w not in STOP}


def primer_prompt(s: dict) -> str:
    claves = s.get("claves")
    if isinstance(claves, list) and claves:
        return str(claves[0])[:1500]
    return ""


def auditar(s: dict) -> dict:
    sujeto = str(s.get("sujeto") or "").strip()
    iq1 = str(s.get("iq1") or "").strip()
    iq2 = str(s.get("iq2") or "").strip()
    iq3 = str(s.get("iq3") or "").strip()
    iq4 = str(s.get("iq4") or "").strip()
    raw = str(s.get("raw") or "").strip()
    prompt = primer_prompt(s)

    problemas: list[str] = []
    avisos: list[str] = []

    # 1 · estructura
    if not sujeto:
        problemas.append("no-subject")
    if sujeto and iq1 and sujeto.lower() == iq1.lower():
        problemas.append("subject-repeats-iq1")
    if sujeto and len(sujeto.split()) >= 4:
        problemas.append("subject-too-long")
    if sujeto and VERBO.search(sujeto) and len(sujeto.split()) > 1:
        avisos.append("subject-has-a-verb")
    if iq2:
        bajo = iq2.lower()
        if not any(t in bajo for t in TIENDAS | PAISES | MAQUINAS):
            problemas.append("iq2-is-not-store-country-or-machine")
    if iq3 and iq3 not in INTENCIONES:
        problemas.append(f"iq3-not-canonical:{iq3}")
    if iq3 in VIEJAS:
        problemas.append("iq3-old-vocabulary")

    # 2 · ¿el prompt contiene lo que los campos afirman?
    palabras_prompt = contenido(prompt)
    palabras_campos = contenido(" ".join([sujeto, iq1, iq2, iq4]))
    comunes = palabras_campos & palabras_prompt
    cobertura = len(comunes) / max(len(palabras_campos), 1) if palabras_campos else 0.0
    if prompt and palabras_campos and cobertura == 0:
        avisos.append("the-prompt-shares-nothing-with-the-fields")
    elif prompt and palabras_campos and cobertura < 0.34:
        avisos.append("the-fields-barely-appear-in-the-prompt")

    # 3 · ¿cuentan una historia?
    piezas = [p for p in (sujeto, iq1, iq3) if p]
    historia = len(piezas)
    if historia >= 3 and not problemas:
        relato = "completa"
    elif historia == 2:
        relato = "parcial"
    elif historia == 1:
        relato = "floja"
    else:
        relato = "no hay relato"

    # 4 · ¿pasó agachada por las reglas viejas?
    agachada = bool(re.search(r"^\d{3,4} \[", raw)) and not iq3 and bool(sujeto)
    if agachada:
        avisos.append("no-intent-since-the-old-rules")

    return {
        "id": s.get("id"), "n": s.get("n"), "raw": raw[:90],
        "fields": {"iq0": sujeto, "iq1": iq1, "iq2": iq2, "iq3": iq3, "iq4": iq4},
        "story": relato, "pieces": historia,
        "prompt_overlap": round(cobertura, 2),
        "problems": problemas, "warnings": avisos,
        "verdict": "reconstruir" if problemas or relato in ("floja", "no hay relato") else
                   ("revisar" if avisos else "ok"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=str(DATA / "index.json"))
    ap.add_argument("--out", default=str(DATA / "iq-audit.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--show", action="store_true", help="print the worst rows")
    args = ap.parse_args()

    datos = json.loads(Path(args.path).expanduser().read_text(encoding="utf-8"))
    sesiones = datos.get("sessions", [])
    if args.limit:
        sesiones = sesiones[: args.limit]

    filas = [auditar(s) for s in sesiones]
    veredicto = Counter(f["verdict"] for f in filas)
    relato = Counter(f["story"] for f in filas)
    problemas = Counter(p for f in filas for p in f["problems"])
    avisos = Counter(a for f in filas for a in f["warnings"])

    print(f"  sesiones auditadas: {len(filas)}")
    print(f"  veredicto: {dict(veredicto)}")
    print(f"  relato:    {dict(relato)}")
    print("  problemas más frecuentes:")
    for k, n in problemas.most_common(8):
        print(f"    {n:4d}  {k}")
    print("  avisos más frecuentes:")
    for k, n in avisos.most_common(6):
        print(f"    {n:4d}  {k}")

    if args.show:
        print("\n  primeras filas a reconstruir:")
        for f in [x for x in filas if x["verdict"] == "reconstruir"][:10]:
            print(f"    #{f['n']} {f['story']:10s} {f['raw'][:44]:44s} "
                  f"iq0={f['fields']['iq0'][:16]:16s} iq1={f['fields']['iq1'][:12]:12s} "
                  f"iq3={f['fields']['iq3'][:14]}")

    salida = {
        "generated": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "sessions": len(filas),
        "verdicts": dict(veredicto),
        "story": dict(relato),
        "problems": dict(problemas),
        "warnings": dict(avisos),
        "rows": filas,
    }
    if not args.limit:
        out = Path(args.out).expanduser()
        out.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  escrito: {out.name} ({out.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
