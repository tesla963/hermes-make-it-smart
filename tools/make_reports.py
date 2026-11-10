#!/usr/bin/env python3
"""Generate the two living reports from the data, not from prose.

    tools/make_reports.py            # árbol de filtros + batería

Both read the same sources the plugin does — the index and the YAML — so a
report can never drift from the thing it describes.
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml

from core.paths import data_dir

OUT = Path.home() / "Documents" / "Reportes - [Lisa]" / datetime.now().strftime("%Y-%m-%d")

# La paleta de los nueve tags: la misma que usa el simulador y el plugin.
PALETTE = {
    "tag1": ("#f0d48a", "#2a2210", "plataforma"),
    "tag2": ("#d3e3f3", "#121d28", "familia"),
    "tag3": ("#c9a8f0", "#221634", "pilar"),
    "tag4": ("#96e0b0", "#0f2618", "país"),
    "tag5": ("#f2a8c4", "#2b1220", "año"),
    "tag6": ("#f5b98f", "#2b1a0f", "máquina"),
    "tag7": ("#8fe6e0", "#0d2725", "libre"),
    "tag8": ("#b8b8f5", "#1a1a33", "libre"),
    "tag9": ("#d8ec8f", "#222b0f", "libre"),
}

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0d0b0e;color:#e8dde4;font:14px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:32px 24px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.4px}
h2{font-size:17px;margin:38px 0 12px;padding-bottom:7px;border-bottom:1px solid #2a2330;color:#f4e6ee}
h3{font-size:14px;margin:22px 0 8px;color:#c9bccf}
.lead{color:#9a8fa5;font-size:13.5px;margin:0 0 4px}
.meta{color:#6f6579;font-size:11.5px;margin-bottom:28px}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
table{width:100%;border-collapse:collapse;margin:10px 0 18px;font-size:12.5px}
th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#8b8095;padding:7px 9px;border-bottom:1px solid #2a2330}
td{padding:6px 9px;border-bottom:1px solid #1c1721;vertical-align:top}
tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums;color:#b5a9bf}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:10.5px;white-space:nowrap;border:1px solid}
.card{background:#141117;border:1px solid #2a2330;border-radius:10px;padding:16px 18px;margin:14px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.pillar{background:#141117;border:1px solid #2a2330;border-radius:10px;padding:14px 16px}
.pillar h4{margin:0 0 2px;font-size:13.5px;color:#f4e6ee}
.pillar .n{font-size:22px;font-weight:700;color:#8fd0f5;font-variant-numeric:tabular-nums}
.pillar .br{font-size:11px;color:#8b8095;margin-top:6px;line-height:1.7}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 14px;font-size:12.5px}
.kv div:nth-child(odd){color:#8b8095}
ol,ul{margin:8px 0 14px;padding-left:22px}
li{margin:4px 0}
.tag{display:inline-block;background:#241d2b;color:#b5a9bf;border-radius:5px;padding:1px 6px;font-size:10.5px;margin-right:4px}
.id{color:#f0d48a}
.rule{background:#141117;border:1px solid #2a2330;border-left:3px solid #5a2040;border-radius:0 8px 8px 0;padding:12px 16px;margin:10px 0}
.rule .rid{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:#f0d48a}
.rule .q{color:#9a8fa5;font-size:12px;margin-top:6px;font-style:italic}
.bad{color:#e8748f}
.good{color:#96e0b0}
footer{margin-top:52px;padding-top:16px;border-top:1px solid #2a2330;color:#6f6579;font-size:11px}
"""


def pill(tag: str, text: str) -> str:
    c, b, _ = PALETTE.get(tag, ("#b5a9bf", "#1c1721", ""))
    return f'<span class="pill" style="color:{c};background:{b};border-color:{c}44">{html.escape(str(text))}</span>'


def page(title: str, subtitle: str, body: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>{html.escape(title)}</h1>
<p class="lead">{subtitle}</p>
<p class="meta">Generado el {stamp} desde los datos vivos · Hermes, make all my work Smart!</p>
{body}
<footer>Hermes, make all my work Smart! · este documento se regenera con <code>tools/make_reports.py</code>, nunca se edita a mano.</footer>
</div></body></html>"""


# --------------------------------------------------------------------------- #
# Report 1 — the filter tree and the renaming algorithm
# --------------------------------------------------------------------------- #

def report_tree() -> str:
    data = json.loads((data_dir() / "index.json").read_text(encoding="utf-8"))
    sessions = data["sessions"]
    total = len(sessions)

    by_pillar = defaultdict(list)
    for s in sessions:
        by_pillar[s["pilar"] or "(sin pilar)"].append(s)

    cards = []
    for pillar, rows in sorted(by_pillar.items(), key=lambda kv: -len(kv[1])):
        branches = []
        t1 = Counter(r["tag1"] for r in rows if r["tag1"]).most_common(6)
        t2 = Counter(r["tag2"] for r in rows if r["tag2"]).most_common(4)
        if t1:
            branches.append("<b>tag1</b> " + " ".join(f"{html.escape(k)} <span class='num'>{v}</span>" for k, v in t1))
        if t2:
            branches.append("<b>tag2</b> " + " ".join(f"{html.escape(k)} <span class='num'>{v}</span>" for k, v in t2))
        cards.append(
            f'<div class="pillar"><h4>{html.escape(pillar)}</h4>'
            f'<span class="n">{len(rows)}</span> <span style="color:#8b8095;font-size:11px">sesiones</span>'
            f'<div class="br">{"<br>".join(branches) or "—"}</div></div>'
        )

    transversal = []
    for key, label, tag in (
        ("motor", "Motor de IA", "tag7"),
        ("tag6", "Máquina", "tag6"),
        ("prof", "Perfil", "tag8"),
    ):
        rows = Counter(s.get(key) or "—" for s in sessions).most_common(9)
        transversal.append(
            f"<tr><td>{label}</td><td>"
            + " ".join(pill(tag, f"{k} {v}") for k, v in rows)
            + "</td></tr>"
        )

    rules = yaml.safe_load((ROOT / "core" / "corrections.yaml").read_text(encoding="utf-8")) or []
    rule_cards = []
    for r in rules:
        q = r.get("control_question") or r.get("rule", "")[:220]
        rule_cards.append(
            f'<div class="rule"><span class="rid">{html.escape(r.get("id",""))}</span>'
            f'<div style="margin-top:4px;font-size:12.5px">{html.escape(r.get("rule","").strip())[:420]}</div>'
            f'<div class="q">¿{html.escape(str(q).strip())}</div></div>'
        )

    pal = "".join(
        f'<tr><td><span class="mono">{t}</span></td><td>{pill(t, d)}</td>'
        f'<td class="mono" style="color:{c}">{c}</td><td class="mono" style="color:#6f6579">{b}</td></tr>'
        for t, (c, b, d) in PALETTE.items()
    )

    body = f"""
<h2>1 · El formato del título</h2>
<div class="card"><span class="mono" style="font-size:14px">
NNN <span style="color:#8fd0f5">[Sujeto]</span> <span style="color:#f0d48a">MMM</span>
<span style="color:#f0d48a">[tag1]</span> <span style="color:#d3e3f3">[tag2]</span>
Descripción <span style="color:#8b8095">· Verbo</span></span></div>
<p class="lead">El ordinal va <b>fuera</b> del corchete del sujeto: dentro, el lector cree que el número es parte del nombre.
Sin fecha, sin costo, sin pilar. Límite duro de 100 caracteres.</p>

<h2>2 · El árbol: pilares y sus ramas</h2>
<p class="lead">{total} sesiones · {data['subjects']} sujetos · {len(by_pillar)} pilares. Cada tarjeta muestra con qué tag1 y tag2 se abre ese frente.</p>
<div class="grid">{"".join(cards)}</div>

<h2>3 · Filtros transversales</h2>
<p class="lead">No parten de un pilar: cruzan todos. Son los que convierten el catálogo en un mapa.</p>
<table><tbody>{"".join(transversal)}</tbody></table>

<h2>4 · Los nueve tags</h2>
<p class="lead">Solo tag1 y tag2 llegan al nombre. Los otros siete existen para que ganar inteligencia después no cueste una migración.</p>
<table><thead><tr><th>tag</th><th>eje</th><th>texto</th><th>fondo</th></tr></thead><tbody>{pal}</tbody></table>

<h2>5 · El algoritmo, en cuatro etapas</h2>
<ol>
<li><b>Extracción.</b> doce <code>state.db</code> abiertas en solo lectura; los turnos del usuario se limpian de preámbulos de cron y volcados de skill.</li>
<li><b>Comprensión.</b> el clasificador propone sujeto, tag1, tag2, pilar y descripción a partir de lo que la sesión hizo de verdad.</li>
<li><b>Curación determinista.</b> {len(rules)} reglas se aplican en orden: quitar la marca del sujeto, no dejar que un calificador nombre, unificar variantes, renumerar series.</li>
<li><b>Presentación.</b> el índice se escribe en <code>plugin-data/</code> y la ventana solo pinta. El plugin nunca lee <code>state.db</code>.</li>
</ol>

<h2>6 · Las {len(rules)} reglas aprendidas</h2>
<p class="lead">Cada una nació de una sesión concreta que llamó la atención. Con su pregunta de control, para poder volver a decidir.</p>
{"".join(rule_cards)}
"""
    return page("Árbol de filtros y algoritmo de renombre", f"{total} sesiones · {len(by_pillar)} pilares · {len(rules)} reglas", body)


# --------------------------------------------------------------------------- #
# Report 2 — the batería
# --------------------------------------------------------------------------- #

def report_bateria() -> str:
    bat = yaml.safe_load((ROOT / "core" / "bateria.yaml").read_text(encoding="utf-8")) or {}
    personal = ROOT / "core" / "bateria.personal.yaml"
    has_personal = personal.exists()

    def render(node, depth=0):
        out = []
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    out.append(f'<h3 style="margin-left:{depth*10}px">{html.escape(str(k))}</h3>')
                    out.append(render(v, depth + 1))
                else:
                    out.append(
                        f'<div class="kv" style="margin-left:{depth*10}px"><div class="mono">{html.escape(str(k))}</div>'
                        f"<div>{html.escape(str(v))}</div></div>"
                    )
        elif isinstance(node, list):
            out.append("<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in node) + "</ul>")
        else:
            out.append(f"<p>{html.escape(str(node))}</p>")
        return "".join(out)

    sections = []
    for name, content in bat.items():
        if name in ("version", "updated", "owner"):
            continue
        count = len(content) if isinstance(content, (dict, list)) else 0
        sections.append(
            f'<div class="card"><h3 style="margin-top:0">{html.escape(name)} '
            f'<span class="num" style="font-size:11px">({count})</span></h3>{render(content)}</div>'
        )

    body = f"""
<h2>1 · Qué es la batería</h2>
<div class="card">Es el papelito que uno copiaba en la escuela. Aquí guarda lo que el clasificador
debe saber de tu mundo para no volver a adivinarlo: qué es USPS Ground Advantage, quién hace
ThinkPad, que «Descuentos a Jubilados» es un nombre y no una oración.<br><br>
<b>Es data, no código.</b> Cada línea que agregues es una regla que se aplica sin corrección manual.</div>

<h2>2 · Las dos baterías</h2>
<table><thead><tr><th></th><th>Objetiva</th><th>Personal</th></tr></thead><tbody>
<tr><td>Archivo</td><td class="mono">core/bateria.yaml</td><td class="mono">core/bateria.personal.yaml</td></tr>
<tr><td>Contiene</td><td>lo que sabe cualquier manual</td><td>lo que solo sabes tú</td></tr>
<tr><td>Ejemplo</td><td>«Ground Advantage son 2–5 días»</td><td>«Con Miami Express los paquetes se pierden»</td></tr>
<tr><td>Viaja con el plugin</td><td class="good">sí</td><td class="bad">nunca — está en .gitignore</td></tr>
<tr><td>En conflicto</td><td>cede</td><td><b>manda</b></td></tr>
</tbody></table>
<p class="lead">Estado: la personal {"existe" if has_personal else "aún no existe"} en <code>core/bateria.personal.yaml</code>.</p>

<h2>3 · Secciones de la batería objetiva</h2>
<p class="lead">El clasificador las consulta en este orden: marcas → productos → programas → compañías → servicios → conceptos → logística → sin_marca.</p>
{"".join(sections)}
"""
    return page("La batería · chuleta del plugin", f"{len(bat)} secciones · {'personal separada' if has_personal else 'sin batería personal'}", body)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    a = OUT / f"{datetime.now():%Y-%m-%d}_[reporte]_arbol-filtros-y-algoritmo.html"
    b = OUT / f"{datetime.now():%Y-%m-%d}_[reporte]_bateria.html"
    a.write_text(report_tree(), encoding="utf-8")
    b.write_text(report_bateria(), encoding="utf-8")
    print(a)
    print(b)
    print(f"{a.stat().st_size//1024} KB · {b.stat().st_size//1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
