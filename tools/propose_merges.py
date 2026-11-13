#!/usr/bin/env python3
"""Propose the merges: which vocabulary terms are the same thing written twice.

Reads the mined vocabulary and proposes, with a reason and a confidence level:

  · merge     — two terms that are one thing (case, accent, plural, typo, synonym)
  · split     — a term that is really two fields glued together
  · promote   — a fragment that needs its brand and context to become vocabulary
  · family    — several terms that belong to one canonical entry as aliases

Writes 11-merge-proposals.html and merge-proposals.md. Proposes only: nothing is applied.
"""
from __future__ import annotations

import collections
import difflib
import html
import json
import pathlib
import re
import unicodedata

HOME = pathlib.Path.home()
OUT = HOME / "Desktop/hermes-make-it-smart-work/reportes"
VOC = OUT / "vocabulario-sesiones.json"

# Sinónimos que ya decidiste, más los que el vocabulario necesita para no partir un filtro.
SYNONYMS = {
    "portátil": ("Laptop", "forced synonym: one kind of machine, one value"),
    "portatil": ("Laptop", "forced synonym"),
    "notebook": ("Laptop", "forced synonym"),
    "laptop": ("Laptop", "canonical"),
    "drone": ("Drone", "canonical"),
    "dron": ("Drone", "forced synonym"),
    "gpu": ("Tarjeta Gráfica", "forced synonym"),
    "tarjeta grafica": ("Tarjeta Gráfica", "forced synonym"),
    "celular": ("Celular Android", "needs the OS to be a filter"),
    "teléfono": ("Celular Android", "needs the OS to be a filter"),
    "telefono": ("Celular Android", "needs the OS to be a filter"),
    "escritorio": ("Desktop", "forced synonym"),
    "desktop": ("Desktop", "canonical"),
    "mobiltransfer": ("MobileTrans", "product spelling"),
    "fitnes": ("Fitness", "product spelling"),
    "muestrame": ("Muéstrame", "accent, not a term"),
    "openxtalk": ("OpenXTalk", "casing"),
    "devonthink": ("DEVONthink", "casing"),
    "cyberpanel": ("CyberPanel", "casing"),
    "logseq": ("Logseq", "casing"),
    "ollama": ("Ollama", "casing"),
}

# Familias que ya conocemos: un nombre canónico y sus alias.
FAMILIES = [
    ("AMD Ryzen AI Max", ["ryzen", "ryzen ai", "ryzen ai max", "ai max", "ai max 400",
                          "gorgon halo", "amd ryzen ai"], "chip de AMD: nombre + codename"),
    ("Framework Desktop", ["framework", "framework desktop"], "la máquina que lo lleva"),
    ("Mac mini M4", ["mac mini", "mac mini m4", "m4"], "máquina"),
    ("ThinkPad P53", ["thinkpad", "thinkpad p53", "p53", "t480s"], "equipo portátil"),
    ("DJI Avata 360", ["avata 360", "avata360", "dji avata"], "dron"),
    ("Marginalia", ["marginalia", "marginalia ia"], "el buscador local"),
    ("Nous Hackaton 2026", ["nous hackaton", "nous hackaton 2026"], "evento"),
]

FRAGMENT_HINT = {
    "a55": ("A55", "Samsung", "Celular Android"),
    "t1000": ("Turing T1000", "Nvidia", "Tarjeta Gráfica"),
    "turing": ("Turing T1000", "Nvidia", "Tarjeta Gráfica"),
    "avata360": ("Avata 360", "DJI", "Drone"),
    "avata 360": ("Avata 360", "DJI", "Drone"),
    "p53": ("ThinkPad P53", "Lenovo", "Laptop"),
    "9100 pro": ("SSD 9100 PRO", "Samsung", "Disco"),
    "qwen3": ("Qwen3", "Alibaba", "Modelo IA"),
    "qwen 3.8 27b": ("Qwen 3.8", "Alibaba", "Modelo IA"),
    "27b": ("—", "—", "tamaño: no es término"),
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def main() -> None:
    datos = json.loads(VOC.read_text(encoding="utf-8"))
    filas = [f for f in datos["rows"] if f["category"] not in ("rejected",)]
    peso = {f["term"]: f["count"] for f in filas}
    cat = {f["term"]: f["category"] for f in filas}

    propuestas: list[dict] = []

    # 1 · la misma palabra escrita distinto (mayúsculas, acentos, plural)
    por_norm: dict[str, list[str]] = collections.defaultdict(list)
    for f in filas:
        por_norm[norm(f["term"])].append(f["term"])
    for clave, termos in por_norm.items():
        if len(termos) > 1:
            # gana el más frecuente; si empatan, el que está bien escrito (mayúscula inicial)
            # entre variantes casi igual de frecuentes, gana la que está bien escrita
            tope = max(peso[x] for x in termos)
            bien = [x for x in termos if peso[x] >= tope * 0.5]
            canon = max(bien, key=lambda x: (sum(c.isupper() for c in x), peso[x]))
            for otro in termos:
                if otro != canon:
                    propio = cat.get(canon, "").startswith("known") or "known" in cat.get(otro, "")
                    propuestas.append({
                        "tipo": "merge", "de": otro, "a": canon,
                        "motivo": "same word, different casing or accent",
                        "confianza": "alta" if propio else "baja",
                        "evidencia": f"{peso[otro]} → {peso[canon]}"})
        # plural
        if clave.endswith("s") and clave[:-1] in por_norm:
            singular = por_norm[clave[:-1]][0]
            plural = termos[0]
            canon = singular if peso.get(singular, 0) >= peso.get(plural, 0) else plural
            otro = plural if canon == singular else singular
            if canon != otro:
                propio = canon[:1].isupper() and otro[:1].isupper() and (
                    cat.get(canon, "").startswith("known") or cat.get(otro, "").startswith("known"))
                propuestas.append({
                    "tipo": "merge", "de": otro, "a": canon, "motivo": "singular / plural",
                    "confianza": "media" if propio else "baja",
                    "evidencia": f"{peso.get(otro,0)} → {peso.get(canon,0)}"})

    # 2 · errores de tipeo: parecidos y con la misma inicial
    nombres = sorted(peso, key=lambda x: -peso[x])[:400]
    for i, a in enumerate(nombres):
        if len(a) < 4 or " " in a:
            continue
        for b in nombres[i + 1:i + 60]:
            if len(b) < 4 or " " in b or a[0].lower() != b[0].lower():
                continue
            r = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
            if 0.86 <= r < 1.0:
                canon = a if peso[a] >= peso[b] else b
                otro = b if canon == a else a
                propuestas.append({
                    "tipo": "merge", "de": otro, "a": canon,
                    "motivo": f"probable typo (similarity {r:.0%})",
                    "confianza": "media", "evidencia": f"{peso[otro]} → {peso[canon]}"})

    # 3 · sinónimos conocidos
    for f in filas:
        s = SYNONYMS.get(f["term"].lower().strip())
        if s and s[0].lower() != f["term"].lower():
            propuestas.append({"tipo": "merge", "de": f["term"], "a": s[0],
                               "motivo": s[1], "confianza": "alta",
                               "evidencia": f"{f['count']} usos"})

    # 4 · fragmentos que necesitan marca y contexto
    for f in filas:
        h = FRAGMENT_HINT.get(f["term"].lower().strip())
        if h:
            propuestas.append({"tipo": "promote", "de": f["term"],
                               "a": f"{h[0]} · iq1 {h[1]} · iq2 {h[2]}",
                               "motivo": "a model alone is not vocabulary",
                               "confianza": "alta", "evidencia": f"{f['count']} usos"})

    # 5 · familias: alias que deben apuntar a un nombre canónico
    for canonico, alias, por_que in FAMILIES:
        presentes = [f["term"] for f in filas if f["term"].lower().strip() in alias]
        if len(presentes) > 1:
            propuestas.append({"tipo": "family", "de": " · ".join(presentes), "a": canonico,
                               "motivo": por_que, "confianza": "alta",
                               "evidencia": f"{sum(peso[p] for p in presentes)} usos repartidos"})

    # 6 · términos que son dos campos pegados
    marcas = {f["term"] for f in filas if f["category"].startswith("known brand")}
    for f in filas:
        t = f["term"]
        if " " not in t:
            continue
        for m in marcas:
            if m != t and t.lower().startswith(m.lower() + " "):
                propuestas.append({"tipo": "split", "de": t, "a": f"{m} (iq1) + {t[len(m):].strip()} (iq0/iq2)",
                                   "motivo": "a brand glued to a model is two fields",
                                   "confianza": "media", "evidencia": f"{f['count']} usos"})
                break

    # un solo destino por origen: gana la confianza más alta
    orden = {"alta": 0, "media": 1, "baja": 2}
    vistos: dict[str, dict] = {}
    for p in sorted(propuestas, key=lambda x: orden[x["confianza"]]):
        vistos.setdefault(p["de"], p)
    finales = sorted(vistos.values(), key=lambda x: (orden[x["confianza"]], x["tipo"], x["de"]))

    por_tipo = collections.Counter(p["tipo"] for p in finales)
    bloques = []
    for nivel, titulo in (("alta", "Apply with confidence"),
                          ("media", "Review before applying"),
                          ("baja", "Your call — could be a real difference")):
        grupo = [p for p in finales if p["confianza"] == nivel]
        if not grupo:
            continue
        cuerpo = "".join(
            f"<tr><td>{p['de']}</td><td class='arrow'>→</td><td><b>{p['a']}</b></td>"
            f"<td>{p['motivo']}</td><td class='num'>{p['evidencia']}</td></tr>" for p in grupo)
        bloques.append(f"<h2>{titulo} <span class='note'>({len(grupo)})</span></h2>"
                       "<table><thead><tr><th>From</th><th></th><th>To</th><th>Why</th>"
                       f"<th>Evidence</th></tr></thead><tbody>{cuerpo}</tbody></table>")
    # ── agrupado por TIPO DE COSA, que es como se decide, no por confianza
    def grupo_de(p: dict) -> str:
        c = cat.get(p["de"], "")
        if p["tipo"] == "promote":
            return "El modelo de algún producto necesita su Marca"
        if p["tipo"] == "split":
            return "Fields glued together"
        if p["tipo"] == "family":
            return "One name, several spellings"
        if "brand" in c:
            return "Brands"
        if "company" in c:
            return "Companies"
        if "person" in c:
            return "People"
        if "place" in c:
            return "Places"
        if "event" in c:
            return "Events"
        if "machine" in c:
            return "Machines"
        if "intent" in c:
            return "Intentions"
        return "Spelling and synonyms"

    grupos: dict[str, list[dict]] = collections.defaultdict(list)
    for pr in finales:
        grupos[grupo_de(pr)].append(pr)

    orden_grupos = ["Fields glued together", "One name, several spellings",
                    "El modelo de algún producto necesita su Marca", "Brands", "Companies", "Machines",
                    "Places", "Events", "People", "Intentions", "Spelling and synonyms"]
    bloques = []
    for nombre in orden_grupos:
        items = grupos.get(nombre, [])
        if not items:
            continue
        filas_html = "".join(
            f"<tr><td class='term'>{html.escape(p['de'])}</td>"
            f"<td class='arrow'>→</td><td class='target'>{html.escape(p['a'])}</td>"
            f"<td class='why'>{html.escape(p['motivo'])}</td>"
            f"<td class='num'>{html.escape(p['evidencia'])}</td>"
            f"<td class='pick'><span class='box'>sí</span><span class='box'>no</span></td></tr>"
            for p in items)
        que = {
            "Fields glued together": "una palabra que son dos campos: se separa, no se fusiona",
            "One name, several spellings": "un nombre canónico y sus alias",
            "El modelo de algún producto necesita su Marca": "un modelo solo no es vocabulario: exige su marca (iq1) y su tipo (iq2)",
            "Brands": "una marca, una forma de escribirla",
            "Companies": "la compañía con su giro",
            "Machines": "la máquina, con su nombre completo",
            "Places": "el lugar, sin variantes",
            "Events": "el evento con su año",
            "People": "la persona por su nombre",
            "Intentions": "la intención, de las siete que existen",
            "Spelling and synonyms": "lo que se escribe distinto y significa lo mismo",
        }[nombre]
        bloques.append(
            f"<h2>{nombre} <span class='cnt'>{len(items)}</span></h2>"
            f"<p class='que'>{que}</p>"
            "<table><thead><tr><th>Término</th><th></th><th>Quedaría como</th>"
            "<th>Por qué</th><th>Evidencia</th><th>Decisión</th></tr></thead>"
            f"<tbody>{filas_html}</tbody></table>")

    altas = sum(1 for p in finales if p["confianza"] == "alta")
    dudosas = [p for p in finales if p["confianza"] == "baja"]

    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Propuestas de fusión — archivo personal</title><style>
:root{{--bg:#0e0c11;--card:#17141b;--line:#2a2431;--tx:#e9e4ee;--tx2:#b9b0c4;--tx3:#8d8399;--gold:#c9a227;--green:#3f9e6a;--red:#d98a8a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.65 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:34px 26px 80px}}
h1{{font-size:25px;margin:0 0 3px;letter-spacing:-.01em}}
h2{{font-size:16px;margin:30px 0 2px;padding-bottom:7px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:9px}}
.cnt{{font-size:11px;color:var(--gold);border:1px solid var(--line);border-radius:20px;padding:1px 8px;font-weight:400}}
.sub{{color:var(--tx3);font-size:12.6px;margin:0 0 6px}}
.privado{{background:#2a1f24;border:1px solid #4a2f38;border-radius:8px;padding:9px 13px;font-size:12.6px;color:#e7c7cf;margin:14px 0 20px}}
.que{{color:var(--tx3);font-size:12.4px;margin:5px 0 9px}}
table{{border-collapse:collapse;width:100%;margin:0 0 6px;font-size:12.8px}}
th,td{{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:middle}}
th{{background:#221d29;color:var(--tx2);font-size:10.8px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}}
tr:nth-child(even) td{{background:#131017}}
.term{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.2px;color:#cfc7da}}
.arrow{{color:var(--gold);text-align:center;width:22px}}
.target{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.2px;color:#e7d9ff;font-weight:600}}
.why{{color:var(--tx2);font-size:12.2px}}.num{{text-align:right;white-space:nowrap;color:var(--tx3);font-size:11.8px}}
.pick{{white-space:nowrap;text-align:center}}.box{{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:0 6px;margin:0 2px;font-size:10.6px;color:var(--tx3)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0 4px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 14px}}
.card b{{display:block;font-size:10.8px;color:var(--tx3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px}}
.big{{font-size:24px;font-weight:700;color:var(--gold);line-height:1.1}}
.note{{color:var(--tx3);font-size:12.2px;margin-top:26px;border-top:1px solid var(--line);padding-top:12px}}
code{{background:#241f2b;border:1px solid var(--line);border-radius:4px;padding:1px 5px;color:#e7d9ff;font-size:11.8px}}
</style></head><body><div class="wrap">
<h1>Propuestas de fusión del vocabulario</h1>
<p class="sub">{len(finales)} propuestas sobre {len(filas)} términos · generadas el 12-nov-2026 · nada aplicado</p>
<div class="privado"><b>Archivo personal.</b> Este documento y el vocabulario que lo alimenta son datos
tuyos: no viajan al repositorio ni a la chuleta de fábrica. Vive en
<code>~/Desktop/hermes-make-it-smart-work/reportes/</code>.</div>
<div class="grid">
<div class="card"><b>Listas para aceptar</b><div class="big">{altas}</div></div>
<div class="card"><b>Necesitan tu criterio</b><div class="big">{len(dudosas)}</div></div>
<div class="card"><b>Tipos de cosa</b><div class="big">{len(grupos)}</div></div>
</div>
{''.join(bloques)}
<p class="note">Agrupadas por tipo de cosa porque así se decide: primero los campos que están
pegados, después los nombres, después las variantes. Cada fila lleva el motivo, la evidencia
(cuántas veces aparece cada forma) y una casilla para marcar sí o no a mano.</p>
</div></body></html>"""
    (OUT / "11-merge-proposals.html").write_text(page, encoding="utf-8")

    md = ["# Merge proposals", "",
          f"{len(finales)} proposals from {len(filas)} terms. Nothing applied.", "",
          "| From | To | Why | Confidence | Evidence |", "|---|---|---|---|---|"]
    md += [f"| {p['de']} | **{p['a']}** | {p['motivo']} | {p['confianza']} | {p['evidencia']} |"
           for p in finales]
    (OUT / "merge-proposals.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"  propuestas: {len(finales)} · {dict(por_tipo)}")
    for p in finales[:12]:
        print(f"    {p['tipo']:8s} {p['de'][:26]:26s} → {p['a'][:44]}")


if __name__ == "__main__":
    main()
