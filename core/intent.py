"""What did the user want done? The one judgement the script cannot make alone.

iq3 is not a topic — it is an intention. "Electronica" says nothing; "Instalar"
says the user had a box in his hands. The difference is what makes iq3 worth
filtering by.

This module reads the intention in two passes:

    1. keywords — cheap, deterministic, and right most of the time. "me llegó",
      "ayúdame a instalarlo" is Instalar without asking anyone.
    2. the model — only when the keywords are silent or tie. It receives the
      actors the script already found and one question: what did he want done?
      It never re-derives the names, so it cannot invent them.

That order is the point. Asking the model first would work, and would cost a
token for every session whose intent is written plainly in the first line.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

# Closed vocabulary. iq3 must be one of these seven or empty — a free-form tag
# is a filter that cannot be clicked twice. The seven come from the rule
# `tag-structure-2026-11-10` in core/corrections.yaml, which outranks every older
# intention rule: the older names (Update, Version, Feature, Costo, Administrar,
# Respaldar, Comparación, Diagnosticar) survive as signals inside the canonical
# intention they belong to, not as tags of their own.
INTENTS: dict[str, dict[str, Any]] = {
    "Instalar": {
        # was: Instalar + Update + Version + Feature
        "signals": ["instalar", "instalarlo", "instalarla", "instalé", "instale",
                    "me llegó", "me llego", "recién llegó", "montar", "poner a andar",
                    "install", "set up", "setup", "configurar", "dejar listo",
                    "ya salió", "ya salio", "nueva versión", "nueva version",
                    "actualizar", "actualización", "actualizacion", "update",
                    "salio la version", "salió la versión", "hay versión", "hay version",
                    "me conviene actualizar", "ya sacaron", "sacaron", "ya salido",
                    "ya está disponible", "ya esta disponible",
                    "qué versión", "que version", "cuál versión", "cual version",
                    "version instalada", "versión instalada", "número de versión",
                    # "puede", "hace", "permite" appear in half the sentences ever
                    # written; only phrases asking what the object IS CAPABLE OF count.
                    "sirve para", "maneja", "soporta", "capacidad de",
                    "qué funciones", "que funciones", "es capaz de",
                    "tiene la función", "tiene la funcion", "qué puede hacer",
                    "que puede hacer", "maneja pdf", "soporta pdf"],
        "means": "quiere instalar, actualizar o identificar la versión de algo que ya tiene",
    },
    "Compatibilidad": {
        "signals": ["compatible", "compatibilidad", "funciona con", "sirve con",
                    "se puede usar con", "anda con", "trabaja con", "soporta el"],
        "means": "dos cosas que ya existen: pregunta si se hablan",
    },
    "Comparar": {
        # was: Comparación
        "signals": ["compara", "comparar", "comparación", "comparacion", " vs ",
                    "cuál es mejor", "cual es mejor", "diferencia entre", "mejor que"],
        "means": "dos o más candidatos y hay que elegir",
    },
    "Troubleshooting": {
        # was: Diagnosticar + Administrar + Respaldar
        "signals": ["no funciona", "falla", "error", "no abre", "no arranca",
                    "se cae", "problema", "roto", "no responde", "por qué no",
                    "administrar", "gestionar", "configurar el servidor", "panel",
                    "usuario", "permisos", "crear cuenta", "alta de",
                    "respaldo", "backup", "copiar a", "copia de seguridad",
                    "guardar en el disco", "exportar a disco"],
        "means": "algo está roto, desconfigurado o sin respaldo y hay que intervenir",
    },
    "Testear": {
        "signals": ["verificar", "comprobar", "probar", "test", "confirmar",
                    "revisar si", "asegurar", "validar"],
        "means": "hay que confirmar que algo cumple lo que promete",
    },
    "Cotizar": {
        # was: Cotizar + Costo
        "signals": ["precio", "cuánto cuesta", "cuanto cuesta", "cotizar",
                    "cotización", "cotizacion", "barato", "oferta", "descuento",
                    "cuánto gasté", "cuanto gaste", "cuánto he gastado", "gasto",
                    "factura", "costo total", "cuánto llevo", "cuanto llevo"],
        "means": "el dinero está en juego: un precio por pagar o un gasto ya hecho",
    },
    "Investigar": {
        "signals": ["investiga", "investigar", "busca información", "buscar info",
                    "averiguar", "qué se sabe", "que se sabe", "documentación"],
        "means": "todavía no hay objeto, hay una pregunta abierta",
    },
}

# When two intents tie, the one closer to the top of this list wins. Order is by
# how much the verb changes the object: installing is not the same as pricing.
_PRIORITY = [
    "Instalar", "Compatibilidad", "Comparar", "Troubleshooting", "Testear",
    "Cotizar", "Investigar",
]

_PRIORITY_INDEX = {k: i for i, k in enumerate(_PRIORITY)}


@dataclass
class Intent:
    name: str
    source: str  # rules | model | none
    score: float = 0.0
    alternatives: list[tuple[str, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.alternatives is None:
            self.alternatives = []

    @property
    def needs_model(self) -> bool:
        return not self.name and self.source == "none"

    def __str__(self) -> str:
        return f"{self.name or '(sin intención)'} [{self.source} {self.score:.1f}]"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def score_intents(text: str) -> list[tuple[str, float]]:
    """Weighted keyword score per intention, best first.

    A longer signal is a stronger signal: "me llegó" says more about installing
    than "puede" says about a feature. Multiplying by the length of the phrase
    keeps the specific ones ahead of the generic ones.
    """
    low = _norm(text)
    scores: dict[str, float] = {}
    for name, spec in INTENTS.items():
        total = 0.0
        for sig in spec["signals"]:
            if sig.lower() in low:
                total += 1.0 + len(sig) / 20.0
        if total:
            scores[name] = total
    return sorted(scores.items(), key=lambda kv: (-kv[1], _PRIORITY_INDEX.get(kv[0], 99)))


def classify_intent(
    text: str,
    *,
    focus: str = "",
    min_score: float = 2.0,
    margin: float = 0.4,
) -> Intent:
    """`focus` is the description: the sentence the user would use himself.

    A signal that appears only in the transcript is a topic; a signal in the
    description is the request. When `focus` is given, an intention that does
    not appear there is not proposed, however loud the rest of the text is.

    The intention, decided by keywords when they are clear enough.

    `min_score` is the floor below which a hit is noise. `margin` is how far
    ahead the winner must be: two intentions that both fire once are a tie, and
    a tie goes to the model rather than to the alphabet.
    """
    if focus.strip():
        in_focus = {k for k, _ in score_intents(focus)}
        ranked = [kv for kv in score_intents(text) if kv[0] in in_focus]
    else:
        ranked = score_intents(text)
    if not ranked:
        return Intent("", "none")
    best, score = ranked[0]

    # One candidate and one word is enough: "compara estos dos lentes" is a
    # comparison whether or not a second intention also fired. The high bar is
    # only for a contest, where a wrong winner is worse than asking.
    if len(ranked) == 1:
        if score >= min_score / 2:
            return Intent(best, "rules", score, ranked[:3])
        return Intent("", "none", score, ranked[:3])

    runner = ranked[1][1]
    if score < min_score or score - runner < margin:
        return Intent("", "none", score, ranked[:3])
    return Intent(best, "rules", score, ranked[:3])


# --------------------------------------------------------------------------- #
# The question for the model — deliberately about the verb, never about names
# --------------------------------------------------------------------------- #

def prompt_for_intent(
    actor_summary: dict[str, Any],
    user_turns: list[str],
    *,
    limit: int = 4,
) -> str:
    """Build the one question the script could not answer.

    The names are already resolved and handed over as facts. The model is asked
    for a verb in a closed list, so its answer is one token from a vocabulary
    the filters can use — not a sentence to be parsed.
    """
    subject = actor_summary.get("subject") or "(sin resolver)"
    brand = actor_summary.get("brand") or "(sin marca)"
    others = ", ".join(actor_summary.get("others") or []) or "(ninguno)"
    turns = "\n".join(f"- {t[:300]}" for t in user_turns[:limit]) or "(sin turnos)"

    vocab = "\n".join(f"- {k}: {v['means']}" for k, v in INTENTS.items())
    return f"""Un usuario de Hermes Agent tuvo esta sesión.

Datos ya resueltos (NO los cambies, NO los repitas, NO inventes otros):
- Sujeto: {subject}
- Marca del sujeto: {brand}
- Otros actores mencionados: {others}

Sus palabras, en orden:
{turns}

Tu única tarea: decidir QUÉ QUISO HACER, eligiendo una y solo una de estas
intenciones:

{vocab}

Reglas:
- Responde solo con JSON: {{"intent": "<una de la lista>", "why": "<máximo 12 palabras>"}}
- Si ninguna encaja, usa "Investigar".
- No expliques la sesión. No nombres actores. Solo el verbo."""


def parse_intent_reply(raw: str) -> str:
    """Read the model's answer, refusing anything outside the vocabulary."""
    try:
        obj = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except (ValueError, AttributeError):
        return ""
    name = str(obj.get("intent", "")).strip()
    return name if name in INTENTS else ""
