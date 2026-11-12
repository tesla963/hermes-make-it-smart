#!/usr/bin/env python3
"""The protocol, pinned to the sessions that taught it.

Every case here is a real title that came out wrong. If a future change to the
batería or to the intent vocabulary breaks one of them, this fails before the
database is touched — which is the whole reason the script exists.

    python3 tests/test_protocol.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.actors import describe, find_actors  # noqa: E402
from core.bateria import load_bateria  # noqa: E402
from core.intent import INTENTS, classify_intent  # noqa: E402

BAT = load_bateria()

# nnn -> (user text, expected subject, expected brand)
ACTORS = {
    100: (
        "estoy evaluando la compra de un drone dji avata360 analiza este video",
        "Avata 360", "DJI",
    ),
    71: (
        "Devon Think 3.0, acabo de instalar este programa ubicalo, quiero evaluar "
        "si me va a permitir organizar todos los pdfs",
        "DEVONthink", "Devon Technologies",
    ),
    397: (
        "verifica con la gente de deepseek que nosotros tenemos deepseek v4 flash, "
        "pero yo creo que ellos ya sacaron deepseek v4.1 flash",
        "V4.1 Flash", "DeepSeek",
    ),
    369: (
        "Compara estos dos lentes, quiero usarlos para volar drone. hay un DJI RC 2, "
        "Remote Controller",
        "RC 2", "DJI",
    ),
    353: (
        "GoveeLife 2.0 WiFi Hygrometer Thermometer with Gateway. Me llego este "
        "hygrometer aydame a instalarlo",
        None, "GoveeLife",  # the exact noun varies; the maker must not
    ),
}

# nnn -> (user text, expected tag3)
INTENTS_CASES = {
    462: ("Comprobar si ya salió la versión de iOS 27", "Instalar"),
    353: ("Me llego este hygrometer aydame a instalarlo", "Instalar"),
    369: ("Compara estos dos lentes, quiero usarlos para volar drone", "Comparar"),
    397: ("verifica si ellos ya sacaron deepseek v4.1 flash", "Instalar"),
}

failures = 0


def ok(cond: bool, msg: str) -> None:
    global failures
    print(f"  {'ok  ' if cond else 'FAIL'} {msg}")
    if not cond:
        failures += 1


print("\n§ actores: el script los encuentra sin gastar un token")
for nnn, (text, subject, brand) in ACTORS.items():
    d = describe(text, BAT)
    if subject is not None:
        ok(d["subject"] == subject, f"{nnn}: sujeto = {subject!r} (dio {d['subject']!r})")
    else:
        ok(bool(d["subject"]), f"{nnn}: encontró un sujeto ({d['subject']!r})")
    ok(d["brand"] == brand, f"{nnn}: marca = {brand!r} (dio {d['brand']!r})")

print("\n§ el sujeto nunca es la marca cuando hay un producto")
for nnn in (100, 369, 397):
    d = describe(ACTORS[nnn][0], BAT)
    ok(d["subject_kind"] == "product", f"{nnn}: el sujeto es un producto, no la marca")

print("\n§ intención: el verbo se decide antes de preguntarle al modelo")
for nnn, (text, want) in INTENTS_CASES.items():
    got = classify_intent(text)
    ok(got.name == want, f"{nnn}: {want} (dio {got.name or '(ninguna)'} por {got.source})")

print("\n§ vocabulario cerrado")
# The seven come from the rule tag-structure-2026-11-10 in core/corrections.yaml.
CANONICAL_INTENTS = {"Comparar", "Instalar", "Investigar", "Testear",
                     "Cotizar", "Troubleshooting", "Compatibilidad"}
ok(set(INTENTS) == CANONICAL_INTENTS,
   f"{len(INTENTS)} intenciones, exactamente las siete de tag-structure-2026-11-10")
ok(all(v.get("means") for v in INTENTS.values()), "todas traen su significado en una línea")
ok(all(v.get("signals") for v in INTENTS.values()), "todas traen señales léxicas")

print("\n§ sin actor conocido, el script lo dice en vez de inventar")
d = describe("Comprobar si ya salió la versión de iOS 27", BAT)
ok(d["needs_model"] is True, "pide ayuda al modelo cuando la batería no conoce el nombre")
ok(d["subject"] == "", "no inventa un sujeto")

print(f"\n{'' if failures else 'TODO OK'}" if failures else "\nTODO OK")
sys.exit(1 if failures else 0)
