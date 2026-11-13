#!/usr/bin/env python3
"""Mine the vocabulary of every session and sort it into the fields the plugin uses.

Reads the live index (titles, subjects, descriptions and the stored prompts), extracts
candidate terms, classifies them against the cheat sheet and the taxonomy, and writes:

  · vocabulario-sesiones.json   machine-readable, one row per term
  · 10-vocabulary.html          dark report, one table per category
  · prompt-clasificar-vocabulario.md   the unclassified remainder, ready to paste into a model

No model calls: every count comes from the data.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re

import yaml

HOME = pathlib.Path.home()
REPO = HOME / "Documents/hermes-make-it-smart"
INDEX = HOME / ".hermes/plugin-data/make-it-smart/index.json"
CHEAT = REPO / "core/cheat_sheet.yaml"
OUTDIR = HOME / "Desktop/hermes-make-it-smart-work/reportes"

STOP_ES = set("""a al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada como
con contra cual cuales cuando de del desde donde dos durante e el ella ellas ello ellos en entre
era eran es esa esas ese eso esos esta estaba estado estan estar estas este esto estos estoy
fue fueron ha habia hace hacer hasta hay la las le les lo los mas me mi mis mucho muy nada ni no
nos o os otra otro para pero poco por porque que quien se sea segun ser si sin sobre sola solo son
su sus tambien tan tanto te tengo ti tiene tienen todo todos tu tus un una unas uno unos y ya yo
esta estan quiero queria puedes puede puedo hacer dando dado siendo tiene vez veces cosa cosas
otra cada parte solo puede desde entonces ademas ahora siempre nunca luego mismo misma
""".split())
STOP_EN = set("""about after all also and any are as at be been being but by can could do does
doing done for from had has have having here how into is it its just like made make many more most
much must my new not now of off on once only or other our out over own same should so some such than
that the their them then there these they this those through to too under up us use used very was
way we were what when where which while who will with would you your via one two three
""".split())
STOP = STOP_ES | STOP_EN
CONTEXT_WORDS = set("""archivo archivos repo repositorio codigo version linea lineas tabla tablas
sesion sesiones nombre nombres dato datos campo campos regla reglas lista listas pagina paginas
texto textos parte partes forma manera tema temas cosa cosas""".split())

# Lo que nunca es vocabulario, con el motivo. Se reporta, no se borra en silencio.
REJECT = [
    (r"^\d+\s*[-–]\s*\d+$", "numeric range from a compressed list"),
    (r"^(hola|hi|hello|buenas|gracias)\b", "greeting"),
    (r"^skill\b", "interface scaffolding"),
    (r"\b\d{1,2}[- ](ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)", "date"),
    (r"\b(19|20)\d{2}\b", "year alone"),
    (r"^\d+(\.\d+)?\s*(gb|tb|mb)$", "size or capacity"),
    (r"^\d+b$", "model size (parameters)"),
    (r"^\d+$", "bare number"),
    (r"^(attached|out[- ]of[- ]band|num|url|mmm|nnn)\b", "interface scaffolding"),
    (r"^tesla369$", "personal identifier — never vocabulary"),
]
EVENT_HINTS = ("hackaton", "hackathon", "congreso", "feria", "curso", "taller",
               "conferencia", "summit", "apedé", "apede", "expo")

PLACE_HINTS = ("panamá", "panama", "balboa", "cristóbal", "cristobal", "bahréin", "bahrein",
               "colón", "colon", "españa", "espana", "eeuu", "miami", "china", "alemania")
STORE_HINTS = ("amazon", "ebay", "aliexpress", "alibaba", "mercado libre", "walmart",
               "best buy", "bhphotovideo", "b&h")


def tokens(texto: str) -> list[str]:
    limpio = re.sub(r"https?://\S+|[\w.-]+/[\w./-]+|@\w+|`[^`]*`", " ", texto)
    limpio = re.sub(r"[^\wáéíóúñüÁÉÍÓÚÑÜ .+-]", " ", limpio)
    return [w.strip(" .+-") for w in limpio.split() if len(w.strip(" .+-")) > 1]


def priv(texto: str) -> str:
    """Nothing personal leaves this script: paths and usernames become placeholders."""
    return re.sub(r"/Users/[^/\s]+", "/Users/<user>", str(texto)).replace("tesla369", "<user>")


def oraciones(texto: str) -> list[str]:
    """Cut on real boundaries: a phrase mined across two sentences is garbage."""
    return [o for o in re.split(r"[.!?\n;·|,()\[\]{}:]+", texto) if o.strip()]


def candidates(texto: str) -> list[tuple[str, str]]:
    """Proper-noun runs inside one sentence, 1 to 3 words: (term, the sentence it came from)."""
    salida: list[tuple[str, str]] = []
    for frase in oraciones(texto):
        toks = tokens(frase)
        i = 0
        while i < len(toks):
            w = toks[i]
            propio = (w[:1].isupper() or any(c.isdigit() for c in w)) and not w.isdigit()
            if not propio or w.lower() in STOP:
                i += 1
                continue
            corrida = [w]
            j = i + 1
            while j < len(toks) and len(corrida) < 3:
                sig = toks[j]
                if not (sig[:1].isupper() or any(c.isdigit() for c in sig)):
                    break
                if sig.lower() in STOP:
                    break
                corrida.append(sig)
                j += 1
            for n in range(1, len(corrida) + 1):
                term = " ".join(corrida[:n])
                if len(term) > 2:
                    salida.append((term, priv(frase.strip())[:66]))
            i = j if len(corrida) > 1 else i + 1
    return salida


def main() -> None:
    sesiones = json.loads(INDEX.read_text(encoding="utf-8"))["sessions"]
    cheat = yaml.safe_load(CHEAT.read_text(encoding="utf-8")) or {}

    marcas: dict[str, str] = {}
    for seccion, etiqueta in (("marcas", "brand"), ("programas", "program"),
                              ("productos", "product"), ("companias", "company")):
        for k, v in (cheat.get(seccion) or {}).items():
            marcas[str(k).lower()] = etiqueta
            if isinstance(v, dict):
                for alias in (v.get("alias") or []) + (v.get("aliases") or []):
                    marcas[str(alias).lower()] = etiqueta

    # the catalogue's own axes are the dictionary: iq1 = brands/programs, iq2 = machines,
    # iq4 = topics. A word the plugin already files somewhere needs no model.
    for s in sesiones:
        for campo, etiqueta in (("iq1", "brand"), ("iq2", "machine"), ("iq4", "topic")):
            v = str(s.get(campo) or "").strip().lower()
            if v and len(v) > 2:
                marcas.setdefault(v, etiqueta)

    temas = {str(v).lower() for v in (cheat.get("conceptos") or {})}
    temas |= {str(x).lower() for x in (cheat.get("servicios") or {})}
    for sec in ("programas", "productos", "companias"):
        temas |= {str(k).lower() for k in (cheat.get(sec) or {})}

    intent_signals: dict[str, str] = {}
    for nombre, datos in ({"Troubleshooting": "reparar arreglar falla error roto no abre",
                           "Search the Web": "investigar buscar averiguar consultar documentación",
                           "Compatibility": "compatible compatibilidad funciona con",
                           "Buy": "comprar compra pedir carrito",
                           "Quote": "precio cuesta cotizar cotización costo factura",
                           "Compare": "comparar diferencia mejor vs",
                           "Configuration": "instalar configurar actualizar setup versión"}.items()):
        for sig in datos.split():
            intent_signals[sig] = nombre

    conteo: collections.Counter = collections.Counter()
    en_sesiones: collections.defaultdict = collections.defaultdict(set)
    ejemplo: dict[str, str] = {}

    for s in sesiones:
        # frases: solo del texto que el plugin ya curó (título, sujeto, descripción, verbo)
        curado = " ".join(str(s.get(k) or "") for k in ("raw", "sujeto", "desc", "verb"))
        for term, frase in candidates(curado):
            conteo[term] += 1
            en_sesiones[term].add(s.get("id") or s.get("n"))
            ejemplo.setdefault(term, frase)
        # palabras sueltas: también del prompt guardado, que es donde vive la jerga
        claves = s.get("claves") or []
        if isinstance(claves, list):
            for c in claves[:3]:
                for term, frase in candidates(str(c)[:900]):
                    if len(term.split()) > 1:
                        continue
                    conteo[term] += 1
                    en_sesiones[term].add(s.get("id") or s.get("n"))
                    ejemplo.setdefault(term, frase)

    PERSONAS = {"lisa", "jorge", "ivette", "ivett", "sofía", "sofia", "antigravity"}
    RUIDO = {"ai", "ia", "max", "halo", "still", "continue", "still in", "in progress",
             "todo", "none", "tb", "gb", "vram", "ssd", "ram", "out of band", "user",
             "message", "busca", "buscar", "verificar", "investigar", "comparar",
             "instalar", "configurar", "revisar", "analizar", "subagent", "bot chat",
             "vigila", "vigilar", "esperar", "lee", "leer", "contexto", "resumen", "nota",
             "objetivo", "problema", "plan", "estado", "tarea", "paso", "respuesta",
             "pregunta", "decidió", "decidio", "haz", "hacer", "dime", "dame", "mira",
             "attached", "num", "url", "examine", "usa", "crea", "system", "mmm",
             "nnn", "context", "mensaje", "message"}

    def rechazo(term: str) -> str:
        for patron, motivo in REJECT:
            if re.search(patron, term.lower().strip()):
                return motivo
        return ""

    def clasificar(term: str) -> str:
        t = term.lower().strip()
        if any(e in t for e in EVENT_HINTS):
            return "event"
        if re.match(r"^(\d+\s*)?(gb|tb|mb)\s+(de\s+)?ram$", t):
            return "attribute · memory"
        if re.match(r"^\d+\s*(gb|tb|mb)\s+(de\s+)?ram$", t):
            return "attribute · memory"
        if t.startswith("miami express"):
            return "known company"
        if t in RUIDO:
            return "noise"
        if t in PERSONAS:
            return "person"
        if any(p in t for p in STORE_HINTS):
            return "context · store"
        if any(p in t for p in PLACE_HINTS):
            return "context · place"
        if t in marcas:
            return f"known {marcas[t]}"
        if t in intent_signals:
            return "intent signal"
        if t in temas:
            return "topic"
        # ¿contiene un término conocido? gana la coincidencia más larga
        partes = sorted({k for k in marcas if k in t and len(k) > 3}, key=len, reverse=True)
        if partes:
            return f"known {marcas[partes[0]]}"
        partes = sorted({k for k in temas if k in t and len(k) > 4}, key=len, reverse=True)
        if partes:
            return "topic"
        if re.search(r"\d", t) and len(term.split()) == 1:
            return "model · needs brand + context"
        if re.search(r"\d", t) and len(term.split()) <= 3:
            return "model or version"
        if re.search(r"(mini|studio|thinkpad|macbook|vps|teléfono|telefono|iphone|ipad|monitor|ssd|disco)", t):
            return "context · machine"
        return "unclassified"

    def es_fragmento(fila: dict, todas: list[dict]) -> bool:
        """'Gorgon' es un trozo de 'Gorgon Halo' cuando aparecen casi lo mismo."""
        for otra in todas:
            if otra is fila or fila["term"] == otra["term"]:
                continue
            if fila["term"] in otra["term"] and len(otra["term"].split()) > len(fila["term"].split()):
                if fila["count"] >= otra["count"] * 0.85:
                    return True
        return False

    filas = []
    privados = [0]
    for term, n in conteo.most_common(900):
        if n < 2 and len(term.split()) == 1:
            continue
        motivo = rechazo(term)
        cat = clasificar(term)
        if cat == "event" or cat.startswith("attribute"):
            motivo = ""
        # privacidad: un identificador personal no se imprime nunca, ni para rechazarlo
        if "personal identifier" in motivo:
            privados[0] += 1
            continue
        filas.append({"term": term, "count": n, "sessions": len(en_sesiones[term]),
                      "category": "rejected" if motivo else cat,
                      "reason": motivo, "example": ejemplo[term]})

    for f in filas:
        f["fragment"] = es_fragmento(f, filas)
    filas = [f for f in filas if not f["fragment"] and f["category"] != "noise"]

    grupos: dict[str, list[dict]] = collections.defaultdict(list)
    for f in filas:
        grupos[f["category"]].append(f)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "vocabulario-sesiones.json").write_text(
        json.dumps({"sessions": len(sesiones), "terms": len(filas), "rows": filas},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    libres = [f for f in filas if f["category"] == "unclassified"][:220]
    (OUTDIR / "prompt-clasificar-vocabulario.md").write_text(
        "# Vocabulary to classify\n\n"
        f"{len(libres)} terms found in {len(sesiones)} session names and prompts. For each one, say\n"
        "which field it belongs to: iq0 subject · iq1 program/brand · iq2 context (store, country,\n"
        "machine) · iq3 intention · iq4 topic — or 'not a field'.\n\n"
        "| term | times | example title |\n|---|---|---|\n"
        + "\n".join(f"| {f['term']} | {f['count']} | {f['example']} |" for f in libres) + "\n",
        encoding="utf-8")

    def tabla(cat: str, limite: int = 28) -> str:
        items = grupos.get(cat, [])[:limite]
        if not items:
            return "<p class='note'>— nothing in this bucket —</p>"
        con_motivo = cat == "rejected"
        filas_html = "".join(
            f"<tr><td>{i['term']}</td><td class='num'>{i['count']}</td>"
            + (f"<td class='bad'>{i.get('reason','')}</td>" if con_motivo
               else f"<td class='num'>{i['sessions']}</td><td class='ex'>{i['example']}</td>")
            + "</tr>" for i in items)
        cabecera = ("<th>Term</th><th>Times</th><th>Why it is not vocabulary</th>" if con_motivo
                    else "<th>Term</th><th>Times</th><th>Sessions</th><th>Seen in</th>")
        return ("<table><thead><tr>" + cabecera + "</tr></thead><tbody>"
                + filas_html + "</tbody></table>")

    orden = ["rejected", "model · needs brand + context", "attribute · memory", "known brand", "known program", "known product", "known company",
             "model or version", "intent signal", "context · store", "context · place",
             "context · machine", "topic", "unclassified"]
    secciones = []
    for i, cat in enumerate(orden, 1):
        n = len(grupos.get(cat, []))
        if n == 0:
            continue
        secciones.append(f"<h2>{i} · {cat} <span class='tag'>{n} terms</span></h2>")
        secciones.append(tabla(cat))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vocabulary of the sessions</title>
<style>
:root{{--bg:#0e0c11;--card:#17141b;--line:#2a2431;--tx:#e9e4ee;--tx2:#b9b0c4;--tx3:#8d8399;--gold:#c9a227;--green:#3f9e6a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",Segoe UI,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:32px 24px 70px}}
h1{{font-size:26px;margin:0 0 4px}}h2{{font-size:17px;margin:28px 0 8px;padding-bottom:6px;border-bottom:1px solid var(--line)}}
.sub{{color:var(--tx3);font-size:13px;margin:0 0 18px}}
.note{{color:var(--tx3);font-size:12.8px}}
code{{background:#241f2b;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.4px;color:#e7d9ff}}
table{{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px}}
th,td{{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#221d29;color:var(--tx2);font-size:11.4px;text-transform:uppercase;letter-spacing:.05em}}
tr:nth-child(even) td{{background:#131017}}.num{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.ex{{color:var(--tx2);font-size:12.2px}}.bad{{color:#d98a8a;font-size:12.4px}}.tag{{font-size:11px;color:var(--gold);font-weight:400;text-transform:none;letter-spacing:0}}
ul{{margin:8px 0 8px 20px}}li{{margin:3px 0}}
</style></head><body><div class="wrap">
<h1>Vocabulary of the sessions</h1>
<p class="sub">{len(sesiones)} sessions mined · {len(filas)} candidate terms · classified against the
cheat sheet, the taxonomy and the intention signals. No model calls.</p>
{''.join(secciones)}
<h2>What this exercise should be, inside the plugin</h2>
<p class="note">This is the job the plugin should run the first time it opens, and again only when
the user asks:</p>
<ul>
<li><b>1 · Mine.</b> Read every title, subject, description and stored prompt; extract proper
nouns and 2–3 word phrases; drop stopwords and code tokens.</li>
<li><b>2 · Match against what is already known.</b> The cheat sheet says which words are brands,
programs, products or companies; the taxonomy says which are topics. Anything that matches needs
no model.</li>
<li><b>3 · Ask only about the remainder.</b> The unclassified list goes to the model in one batch,
with the question "which field does this belong to?" — not a full classification pass.</li>
<li><b>4 · Propose, never write.</b> New brands, machines and topics land in a
<code>pending</code> file; the user approves, and only then they join
<code>cheat_sheet.personal.yaml</code>.</li>
<li><b>5 · Keep the evidence.</b> Each accepted term keeps the sessions that produced it, so a
wrong term can be traced back to the sentence that taught it.</li>
</ul>
<p class="note">The value is not the list: it is that after one pass the plugin stops guessing what
"Gorgon Halo" or "Avata 360" is, and the user never has to explain their own world twice.</p>
</div></body></html>"""
    (OUTDIR / "10-vocabulary.html").write_text(page, encoding="utf-8")

    print(f"  sesiones: {len(sesiones)} · términos: {len(filas)}")
    for cat in orden:
        n = len(grupos.get(cat, []))
        if n:
            print(f"    {cat:22s} {n:4d}")
    if privados[0]:
        print(f"    (privacidad) {privados[0]} entradas personales excluidas del reporte")
    print(f"  escrito: 10-vocabulary.html · vocabulario-sesiones.json · prompt-clasificar-vocabulario.md")


if __name__ == "__main__":
    main()
