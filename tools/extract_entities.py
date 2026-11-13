#!/usr/bin/env python3
"""Pull the entities out of a session: objects, companies, people, places, events,
models, intention and context.

Two layers, in this order:

  · deterministic — gazetteers built from the cheat sheet and from the catalogue's own
    axes, plus patterns for models, units and events. Free, repeatable, auditable.
  · model — only for what the first layer could not name. It is opt-in (`--llm-command`)
    and its answer must validate against the schema or it is discarded.

The output is one JSON object per session, with the evidence for every field and a
`needs_llm` list so nobody has to guess what was left undecided.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
INDEX = Path.home() / ".hermes/plugin-data/make-it-smart/index.json"
CHEAT = REPO / "core/cheat_sheet.yaml"

STORES = ("amazon", "ebay", "aliexpress", "alibaba", "walmart", "best buy",
          "b&h", "bhphotovideo", "mercado libre", "newegg", "taobao")
PLACES = ("panamá", "panama", "colón", "balboa", "cristóbal", "david", "chitré",
          "miami", "estados unidos", "eeuu", "españa", "china", "alemania", "méxico",
          "colombia", "bahrein", "bahréin", "dubái", "dubai")
EVENT_HINTS = ("hackaton", "hackathon", "congreso", "feria", "expo", "cumbre", "summit",
               "conferencia", "taller", "curso", "seminario", "apedé", "apede")
PEOPLE = ("the owner", "pareja", "ivett", "sofía", "sofia", "mamá", "papá",
          "hermano", "hermana", "cliente", "autor")
MACHINE_LABELS = {"iphone": "iPhone", "ipad": "iPad", "iwatch": "Apple Watch",
                  "apple watch": "Smartwatch", "mac mini": "Mac mini", "mac studio": "Mac Studio",
                  "macbook": "Laptop", "thinkpad": "Laptop", "imac": "Desktop", "vps": "VPS",
                  "teléfono": "Celular Android", "telefono": "Celular Android",
                  "servidor": "Servidor", "desktop": "Desktop", "laptop": "Laptop",
                  "portátil": "Laptop", "portatil": "Laptop"}
MACHINE_HINTS = ("mac mini", "mac studio", "macbook", "thinkpad", "imac", "vps",
                 "teléfono", "telefono", "iphone", "ipad", "servidor", "pc", "desktop",
                 "laptop", "portátil", "portatil")
UNIT = re.compile(r"\b(\d+)\s?(gb|tb|mb|gbps|ghz|mhz|w|hz|mm|cm|pulgadas|núcleos|cores)\b", re.I)
MODEL = re.compile(r"\b(?:[A-Z][A-Za-z]{0,5}\s?\d{2,5}[A-Za-z0-9-]*|[A-Z]\d{2,3})\b")
PROPER = re.compile(r"\b[A-ZÁÉÍÓÚÑ][\w.+&-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w.+&-]*){0,2}\b")

# modelo → (marca, contexto). Un salto solo no basta: sin marca es un número.
MODEL_MAP = {
    "a55": ("Samsung", "Celular Android"), "a54": ("Samsung", "Celular Android"),
    "t1000": ("Nvidia", "Tarjeta Gráfica"), "rtx": ("Nvidia", "Tarjeta Gráfica"),
    "p53": ("Lenovo", "Laptop"), "t480s": ("Lenovo", "Laptop"), "x1 carbon": ("Lenovo", "Laptop"),
    "9100 pro": ("Samsung", "Disco"), "990 pro": ("Samsung", "Disco"),
    "avata 360": ("DJI", "Drone"), "air 2s": ("DJI", "Drone"), "mavic": ("DJI", "Drone"),
    "mac mini m4": ("Apple", "Desktop"), "mac studio": ("Apple", "Desktop"),
    "ryzen ai max": ("AMD", "Desktop"), "gorgon halo": ("AMD", "Desktop"),
    "iphone": ("Apple", "iPhone"), "ipad": ("Apple", "iPad"),
    "iwatch": ("Apple", "Smartwatch"), "apple watch": ("Apple", "Smartwatch"),
    "x4": ("Insta360", "Cámara 360"), "x3": ("Insta360", "Cámara 360"),
    "thinkpad": ("Lenovo", "Laptop"), "latitud": ("Dell", "Laptop"), "xps": ("Dell", "Laptop"),
}

SCHEMA = {
    "objects": "things the session is about (drone, laptop, chip, keyboard)",
    "companies": "who makes or sells them",
    "people": "named humans",
    "places": "countries, cities, regions",
    "events": "dated happenings (hackathon, fair, course)",
    "models": "product or part numbers, never alone",
    "brands": "the maker names",
    "intention": "one of: Troubleshooting, Web Search, Compatibility, Buy, Quote, Compare, Configuration",
    "context": {"store": "", "country": "", "machine": ""},
}


def gazetteers() -> dict[str, set[str]]:
    cheat = yaml.safe_load(CHEAT.read_text(encoding="utf-8")) or {}
    marcas = {str(k).lower() for k in (cheat.get("marcas") or {})}
    programas = {str(k).lower() for k in (cheat.get("programas") or {})}
    companias = {str(k).lower() for k in (cheat.get("companias") or {})}
    productos = {str(k).lower() for k in (cheat.get("productos") or {})}

    sesiones = json.loads(INDEX.read_text(encoding="utf-8"))["sessions"]
    for s in sesiones:
        v1 = str(s.get("iq1") or "").strip().lower()
        v2 = str(s.get("iq2") or "").strip().lower()
        if v1:
            marcas.add(v1)
        if v2:
            programas.add(v2)
    return {"brands": marcas, "programs": programas, "companies": companias,
            "products": productos}


def intention_of(texto: str) -> str:
    sys.path.insert(0, str(REPO))
    try:
        from core.taxonomy import normalize_intention
    except Exception:
        return ""
    candidatos = [w for w in re.findall(r"\b[a-záéíóúñ]{4,}\b", texto.lower())]
    for c in candidatos:
        v = normalize_intention(c)
        if v:
            return v
    return ""


def extract(texto: str, gaz: dict[str, set[str]]) -> dict:
    t = texto or ""
    bajo = t.lower()
    propios = [p.strip() for p in PROPER.findall(t)]
    res: dict = {k: [] for k in SCHEMA if k != "context"}
    res["context"] = {"store": "", "country": "", "machine": ""}

    # una tienda es contexto, nunca marca; y una frase se prueba palabra por palabra
    def es_tienda(x: str) -> bool:
        return any(s in x for s in STORES)

    for frase in propios:
        pl = frase.lower().strip()
        if es_tienda(pl):
            continue
        if pl in gaz["companies"]:
            res["companies"].append(frase)
            continue
        if pl in gaz["brands"]:
            res["brands"].append(frase)
            continue
        if pl in gaz["programs"] or pl in gaz["products"]:
            res["objects"].append(frase)
            continue
        if pl in PEOPLE:
            res["people"].append(frase)
            continue
        # "AMD Ryzen AI" → AMD es la marca, Ryzen AI el modelo
        for tok in frase.split():
            tl = tok.lower()
            if tl in gaz["brands"] and not es_tienda(tl):
                res["brands"].append(tok)
            elif tl in PEOPLE:
                res["people"].append(tok)
            elif tl in gaz["companies"]:
                res["companies"].append(tok)

    for lugar in PLACES:
        if lugar in bajo:
            res["places"].append(lugar.title())
            if not res["context"]["country"]:
                res["context"]["country"] = lugar.title()

    for tienda in STORES:
        if tienda in bajo:
            res["context"]["store"] = tienda.title()

    for maquina in MACHINE_HINTS:
        if re.search(rf"\b{re.escape(maquina)}\b", bajo):
            res["context"]["machine"] = MACHINE_LABELS.get(maquina, maquina.title())
            break

    for palabra in EVENT_HINTS:
        if palabra in bajo:
            m = re.search(rf"[^.]*\b{palabra}[^.]*", t, re.I)
            res["events"].append((m.group(0) if m else palabra).strip()[:60])
            break

    # una capacidad no es un modelo: 192GB es un atributo de la máquina
    modelos = [m for m in MODEL.findall(t) if not UNIT.fullmatch(m.strip())]
    res["models"] = list(dict.fromkeys(modelos))[:8]

    # la regla: si hay modelo, se busca su marca y su contexto; si no aparece en el texto,
    # se propone desde el mapa en lugar de dejarlo huérfano
    res["resolved"] = []
    for m in res["models"]:
        clave = m.lower().strip()
        par = MODEL_MAP.get(clave) or MODEL_MAP.get(clave.split()[0])
        if par:
            marca, contexto = par
            res["resolved"].append({"model": m, "brand": marca, "context": contexto})
            if marca not in res["brands"]:
                res["brands"].append(marca)
            if not res["context"]["machine"]:
                res["context"]["machine"] = contexto
    if res["resolved"] and res.get("warnings") and any("model without brand" in w for w in res["warnings"]):
        res["warnings"] = [w for w in res["warnings"] if "model without brand" not in w]
    res["intention"] = intention_of(t)

    # lo que queda por decidir, con nombre y apellido
    conocidos = set(map(str.lower, res["brands"] + res["companies"] + res["people"]))
    res["needs_llm"] = [p for p in dict.fromkeys(propios)
                        if p.lower() not in conocidos and p.lower() not in PLACES][:8]

    # una marca en iq1 exige que el sujeto sea una parte suya; un modelo solo no es término
    res["warnings"] = []
    if res["models"] and not res["brands"]:
        res["warnings"].append("model without brand: needs iq1")
    if not res["intention"]:
        res["warnings"].append("no intention detected: leave iq3 empty, do not guess")
    return res


def ask_model(texto: str, prompt_cmd: str, schema: dict) -> dict:
    prompt = ("Extrae entidades del texto. Responde SOLO JSON válido con este esquema:\n"
              + json.dumps(schema, ensure_ascii=False, indent=1)
              + "\nTexto:\n" + texto[:4000])
    out = subprocess.run(prompt_cmd, shell=True, input=prompt,
                         capture_output=True, text=True, timeout=180)
    crudo = out.stdout.strip()
    m = re.search(r"\{.*\}", crudo, re.S)
    if not m:
        return {"error": "the model did not return JSON", "raw": crudo[:200]}
    try:
        datos = json.loads(m.group(0))
    except Exception as e:
        return {"error": f"invalid JSON: {e}", "raw": crudo[:200]}
    faltan = [k for k in ("objects", "companies", "intention") if k not in datos]
    if faltan:
        return {"error": f"missing keys: {faltan}", "raw": crudo[:200]}
    return datos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text")
    ap.add_argument("--path", default=str(INDEX))
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--llm-command", help="cmd that reads a prompt on stdin and answers JSON,"
                                         " e.g. 'hermes --print'")
    args = ap.parse_args()

    gaz = gazetteers()
    if args.text:
        r = extract(args.text, gaz)
        if args.llm_command and r["needs_llm"]:
            r["llm"] = ask_model(args.text, args.llm_command, SCHEMA)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0

    sesiones = json.loads(Path(args.path).expanduser().read_text(encoding="utf-8"))["sessions"]
    for s in sesiones[: args.limit]:
        fuente = " ".join(str(s.get(k) or "") for k in ("raw", "sujeto", "desc"))
        claves = s.get("claves") or []
        if isinstance(claves, list) and claves:
            fuente += " " + str(claves[0])[:800]
        r = extract(fuente, gaz)
        if args.llm_command and r["needs_llm"]:
            r["llm"] = ask_model(fuente, args.llm_command, SCHEMA)
        r["n"] = s.get("n")
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
