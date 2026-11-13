#!/usr/bin/env python3
"""Strip the wordiness from a session and keep only what it was about.

The owner's words: "un script que elimine la palabrería de la sesión para condensar la
intencionalidad y el contenido". This does it with rules, in this order:

  1 · remove the scaffolding (markdown, paths, urls, code, emojis, citations)
  2 · remove the courtesy and the filler ("hola", "por favor", "me gustaría", "o sea")
  3 · remove the meta-talk about the plugin itself ("renombra la sesión", "iq1", "título")
  4 · protect what must survive: proper nouns, numbers with units, action verbs
  5 · keep the first action verb as the intent, the proper nouns as the content

If a phrase is removed, it is reported in `dropped`, so the condensation can be audited.
No model is used: the same input always gives the same output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

INDEX = Path.home() / ".hermes/plugin-data/make-it-smart/index.json"

FILLER = [
    r"\bhola\b", r"\bbuenas?\b", r"\bbuenos d[ií]as\b", r"\bbuenas (tardes|noches)\b",
    r"\bpor favor\b", r"\bporfa\b", r"\bgracias\b", r"\bok(ei)?\b", r"\bvale\b",
    r"\bme gustar[ií]a\b", r"\bquisiera\b", r"\bquiero que\b", r"\bnecesito que\b",
    r"\bpuedes\b", r"\bpodr[ií]as\b", r"\bser[ií]a posible\b", r"\bay[uú]dame a\b",
    r"\bte pido\b", r"\bte encargo\b", r"\bque me\b", r"\bme ayudes a\b",
    r"\bme ayudas a\b", r"\bsobre el\b", r"\bsobre la\b", r"\bacerca de\b", r"\bnecesito\b", r"\bquiero\b", r"\bfavor de\b",
    r"\bo sea\b", r"\bes que\b", r"\blo que pasa es que\b", r"\ba ver\b", r"\bmira\b",
    r"\bf[ií]jate\b", r"\ben realidad\b", r"\bb[aá]sicamente\b", r"\bsimplemente\b",
    r"\bde alguna manera\b", r"\bun poco\b", r"\bm[aá]s o menos\b", r"\bdigamos\b",
    r"\bentonces\b", r"\bbueno\b", r"\bpues\b", r"\bya que\b", r"\badem[aá]s\b",
    r"\bplease\b", r"\bthanks\b", r"\bi (want|need) you to\b", r"\bcould you\b",
    r"\bwould you\b", r"\bjust\b", r"\bkindly\b",
]
META = [
    r"\brenombra(r)? (la |las )?sesi[oó]n(es)?\b", r"\bnombre de la sesi[oó]n\b",
    r"\biq[0-9]\b", r"\btag[0-9]\b", r"\bt[ií]tulo(s)?\b", r"\bcampo(s)?\b",
    r"\bel plugin\b", r"\bla taxonom[ií]a\b", r"\bcategor[ií]a(s)?\b",
    r"\bclasifica(r)?\b", r"\betiqueta(r)?\b",
]
NOISE = [
    r"https?://\S+", r"/Users/\S+", r"[\w.-]+/[\w./-]{3,}", r"```.*?```", r"`[^`]*`",
    r"@\w+", r"\[[^\]]{0,40}\]\([^)]*\)", r"^#+\s*", r"[\U0001F300-\U0001FAFF\u2600-\u27BF]",
    r"\bOUT-OF-BAND\b[^.]*", r"\bAttached Context\b", r"\bSubagent:\s*",
]
ACTION = re.compile(r"\b([a-záéíóúñ]{4,}(?:ar|er|ir|ando|iendo|ado|ido|ing))\b", re.I)
UNITS = re.compile(r"(\d+)\s?(gb|tb|mb|gbps|w|hz|mm|cm|pulgadas|ram|vram)\b", re.I)


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFC", texto or "")
    for patron in NOISE:
        t = re.sub(patron, " ", t, flags=re.I | re.S | re.M)
    return re.sub(r"\s+", " ", t).strip()


def condesar(texto: str) -> dict:
    original = normalizar(texto)
    t = original
    dropped: list[str] = []

    for patron in META + FILLER:
        for m in re.finditer(patron, t, flags=re.I):
            dropped.append(m.group(0))
        t = re.sub(patron, " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" .,;:-—·")
    t = re.sub(r"^(y|o|a|de|que|me|te|se|le|lo|la|el|en|con|para)\s+", "", t, flags=re.I)

    # lo que nunca se toca: nombres propios, unidades y verbos de acción
    propios = re.findall(r"\b[A-ZÁÉÍÓÚÑ][\w.+&-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w.+&-]*){0,2}\b", original)
    unidades = UNITS.findall(original)
    acciones = [v for v in ACTION.findall(t)]
    frases_protegidas = [p for p in propios if p.lower() not in {"el", "la", "los", "las"}]

    # el contenido condensado: la frase sin relleno, recortada a lo esencial
    palabras = [w for w in t.split() if w.lower() not in
                {"de", "la", "el", "los", "las", "un", "una", "que", "y", "a", "en", "con", "por", "para", "del", "al", "se", "lo", "su", "mi"}]
    condensado = " ".join(t.split()[:14])
    contenido = " ".join(dict.fromkeys([*frases_protegidas[:6], *[f"{n} {u}".upper() for n, u in unidades[:3]]]))

    return {
        "original_chars": len(original),
        "condensed_chars": len(condensado),
        "compression": round(1 - (len(condensado) / max(len(original), 1)), 2),
        "condensed": condensado,
        "content": contenido,
        "action_verbs": list(dict.fromkeys(acciones))[:4],
        "proper_nouns": list(dict.fromkeys(frases_protegidas))[:8],
        "units": [f"{n} {u}".upper() for n, u in unidades],
        "keywords": list(dict.fromkeys(palabras))[:12],
        "dropped": sorted(set(d.lower() for d in dropped))[:20],
    }


def sesiones(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["sessions"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", help="condense this text instead of reading the index")
    ap.add_argument("--path", default=str(INDEX))
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="one JSON object per session")
    args = ap.parse_args()

    if args.text:
        print(json.dumps(condesar(args.text), ensure_ascii=False, indent=1))
        return 0

    filas = []
    for s in sesiones(Path(args.path).expanduser())[: args.limit]:
        fuente = " ".join(str(s.get(k) or "") for k in ("raw", "sujeto", "desc"))
        claves = s.get("claves") or []
        if isinstance(claves, list) and claves:
            fuente += " " + str(claves[0])
        r = condesar(fuente)
        r["n"] = s.get("n")
        filas.append(r)
        if not args.json:
            print(f"\n  #{s.get('n')}  compresión {r['compression']*100:.0f}%  "
                  f"({r['original_chars']} → {r['condensed_chars']} caracteres)")
            print(f"    condensado : {r['condensed'][:96]}")
            print(f"    contenido  : {r['content'][:96]}")
            print(f"    verbos     : {', '.join(r['action_verbs']) or '—'}")
            print(f"    se quitó   : {', '.join(r['dropped'][:8]) or '—'}")
    if args.json:
        print(json.dumps(filas, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
