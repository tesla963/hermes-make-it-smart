"""Title rendering: the canonical format and its invariants.

NNN [Subject MMM] [Iq1] [Iq2] Date Description · Verb

Pure Python. No host imports.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .taxonomy import normalize_verb

MAX_TITLE_LENGTH = 100
MIN_DESCRIPTION_CHARS = 18
MIN_DESCRIPTION_WORDS = 3

# Words removed first when the description does not fit (telegram mode).
_FILLER = frozenset(
    """el la los las un una unos unas de del al a en con por para que y o u
    se su sus mi mis tu tus lo le les es son fue era como cual cuales
    cuando donde sobre desde hasta entre sin tras muy mas menos""".split()
)


@dataclass(frozen=True)
class Facets:
    subject: str
    subject_ordinal: int
    iq1: str                      # the maker — an adjective of the subject
    iq2: str = ""                 # the context: store, country or machine
    iq3: str = ""                 # the intention — a verb
    iq4: str = ""                 # the work front (theme, with subcategory)
    iq5: str = ""                 # the year
    # Reserved sockets. The model carries nine so that a new axis later does not
    # cost a schema migration; they stay empty until one earns its meaning.
    iq6: str = ""
    iq7: str = ""
    iq8: str = ""
    iq9: str = ""
    # Kept so older call sites keep working; they now mirror the new fields.
    pillar: str = ""
    country: str = ""
    year: str = ""
    machine: str = ""
    description: str = ""
    verb: str = ""


# --------------------------------------------------------------------------- #
# Date
# --------------------------------------------------------------------------- #

_MONTHS_ES = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)


def short_date(iso_date: str) -> str:
    """'2026-08-19' -> '19ago'. Empty on anything unparseable."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso_date or "")
    if not m:
        return ""
    _, month, day = m.groups()
    idx = int(month) - 1
    if not 0 <= idx < 12:
        return ""
    return f"{int(day):02d}{_MONTHS_ES[idx]}"


# --------------------------------------------------------------------------- #
# Description
# --------------------------------------------------------------------------- #


def telegram(text: str) -> str:
    """Drop articles and prepositions, keep the first word and the meaning."""
    words = text.split()
    if not words:
        return ""
    head, rest = words[0], words[1:]
    kept = [w for w in rest if w.lower().strip(".,;:") not in _FILLER]
    return " ".join([head, *kept]).strip()


def fit_description(text: str, budget: int) -> str:
    """Full text, else telegram, else nothing. Never a half-cut phrase."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text or budget <= 0:
        return ""
    if len(text) <= budget:
        return text if _is_usable(text) else ""
    compact = telegram(text)
    if len(compact) <= budget and _is_usable(compact):
        return compact
    # last resort: cut on a word boundary, but only if what remains still reads
    cut = compact or text
    if len(cut) > budget:
        cut = cut[:budget].rsplit(" ", 1)[0]
    cut = cut.rstrip(" ,;:.-—·")
    return cut if _is_usable(cut) else ""


# A comparison is short by nature ("Gemma vs Qwen", 13 chars) but carries real
# information, so it is exempt from the minimum length. Without this, every
# "A vs B" description was silently dropped and the title ended in a bare axis.
_COMPARATOR = re.compile(r"\s(vs\.?|versus|frente a)\s", re.I)


def _is_usable(text: str) -> bool:
    if _COMPARATOR.search(text):
        return len(text.split()) >= 2
    return len(text) >= MIN_DESCRIPTION_CHARS and len(text.split()) >= MIN_DESCRIPTION_WORDS


# --------------------------------------------------------------------------- #
# Subject
# --------------------------------------------------------------------------- #

_ACTION_PREFIXES = (
    "instalacion de", "instalación de", "instalar", "configurar", "configuracion de",
    "configuración de", "revisar", "verificar", "investigar", "analizar", "comparar",
    "monitorear", "respaldar", "organizar", "limpiar", "migrar", "corregir",
    "suplemento", "auto-arranque", "arreglar", "solucionar",
)

_STATE_ADJECTIVES = (
    "inusual", "trancado", "con error", "colgado", "lento", "roto", "fallando",
)


def core_subject(subject: str) -> str:
    """Strip the action prefix and the state adjectives, keep the core noun."""
    s = re.sub(r"\s+", " ", (subject or "").strip())
    low = s.lower()
    for prefix in _ACTION_PREFIXES:
        if low.startswith(prefix + " "):
            s = s[len(prefix) + 1 :].strip()
            low = s.lower()
            break
    for adj in _STATE_ADJECTIVES:
        s = re.sub(rf"\s+{re.escape(adj)}\b", "", s, flags=re.I).strip()
    return s


_SPEC_TAIL = re.compile(r"\s+\d+\s?(?:GB|TB|MB)\s*$", re.I)
_SPEC_IS_SUBJECT = re.compile(r"^\d+\s?(?:GB|TB|MB)\s+RAM$", re.I)


def strip_spec(subject: str) -> tuple[str, str]:
    """Take a trailing capacity out of the subject and return it as the spec.

    "Gorgon Halo 192GB" -> ("Gorgon Halo", "192GB").
    "16 GB Ram" is left alone: there the spec IS the subject.
    """
    s = (subject or "").strip()
    if not s or _SPEC_IS_SUBJECT.match(s):
        return s, ""
    m = _SPEC_TAIL.search(s)
    if not m:
        return s, ""
    rest = s[: m.start()].strip()
    if len(rest) < 3:
        return s, ""
    return rest, m.group(0).strip()


DANG_WORDS = frozenset({
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "y", "o", "u", "a", "en", "con", "por", "para", "al", "que",
    "este", "esta", "estos", "estas", "su", "sus", "mi", "mis", "tu", "tus",
    "se", "si", "no", "desd", "co", "ma"
})

ACTION_VERBS = frozenset({
    "crear", "hacer", "instalar", "configurar", "recuperar", "eliminar",
    "listar", "abrir", "verificar", "explicar", "consultar", "revisar",
    "analizar", "comparar", "arreglar", "renombrar", "borrar", "actualizar",
    "modificar", "rename", "use", "testear", "buscar", "comprar", "cotizar"
})

QUESTION_WORDS = frozenset({
    "qué", "que", "cómo", "como", "cuál", "cual", "quién", "quien",
    "dónde", "donde", "cuándo", "cuando", "esto", "eso", "aquello"
})

KNOWN_ENTITIES = {
    "deepseek": "DeepSeek",
    "brave": "Brave",
    "handbrake": "Handbrake",
    "antigravity": "Antigravity",
    "nous": "Nous",
    "logseq": "Logseq",
    "firefox": "Firefox",
    "apple": "Apple",
    "google": "Google",
    "hermes": "Hermes",
    "gemini": "Gemini",
    "macmini": "Mac mini",
    "steren": "Steren",
}


def _is_mutilated(w: str) -> bool:
    """True when a word was sliced mid-word by an earlier naive length cut."""
    low = w.lower().strip(".,;:¡!¿?()\"'")
    if not low:
        return False
    if low in {"perdid", "proyect", "desd", "co", "ma"}:
        return True
    if low.endswith("sd"):
        return True
    if low.endswith("ct") and low not in {
        "aspect", "compact", "contact", "correct", "direct", "distinct", "exact",
        "impact", "inspect", "object", "perfect", "product", "project", "protect",
        "react", "respect", "select", "strict", "struct"
    }:
        return True
    if len(low) > 4 and low.endswith("did") and low not in {"madrid", "candid", "sordid", "ardid"}:
        return True
    return False


def _is_clean_head(head: str, limit: int = 3) -> bool:
    """Enforces nominal invariants: 1-3 words, no verbs, no hanging prepositions, no sliced words."""
    words = head.split()
    if not (1 <= len(words) <= limit):
        return False
    if words[0].lower() in DANG_WORDS or words[-1].lower() in DANG_WORDS:
        return False
    if any(_is_mutilated(w) for w in words):
        return False
    if any(w.lower() in ACTION_VERBS for w in words):
        return False
    if any(w.lower() in QUESTION_WORDS for w in words):
        return False
    for w in words:
        if len(w) < 2:
            return False
        if len(w) == 2 and w.lower() not in {"dr", "ai", "ui", "os", "ip", "id"}:
            return False
    return True


def _is_proper_word(w: str) -> bool:
    """True if w is capitalized or CamelCase, and not an action verb or common stopword."""
    if not w or _is_mutilated(w):
        return False
    low = w.lower().strip(".,;:¡!¿?()\"'")
    if low in ACTION_VERBS or low in DANG_WORDS:
        return False
    return w[:1].isupper() or any(c.isupper() for c in w[1:])


VERBO_INF = re.compile(r"^(recuperar|restaurar|reparar|arreglar|instalar|configurar|comparar|"
                        r"investigar|buscar|consultar|cotizar|comprar|verificar|revisar|eliminar|"
                        r"crear|listar|explicar|mostrar|activar|desactivar|migrar|actualizar|"
                        r"corregir|limpiar|resolver|monitorear|vigilar)\b", re.I)
ADJ_ESTADO = {"perdida", "perdidas", "perdido", "perdidos", "gris", "roto", "rota",
              "lento", "lenta", "viejo", "vieja", "nuevo", "nueva", "raro", "rara"}


def split_verb_subject(subject: str) -> tuple[str, str]:
    """Separa el verbo del sujeto: el verbo es intención, nunca sujeto.

    («Recuperar ventas y pestañas perdidas») → («Recuperar», «Ventas y Pestañas»)
    («Eliminar línea gris en tabs»)          → («Eliminar», «Línea Tabs»)
    """
    texto = (subject or "").strip()
    if not texto:
        return "", ""
    palabras = [w.strip(".,;:¡!¿?()") for w in texto.split() if w.strip(".,;:¡!¿?()")]
    if not palabras:
        return "", ""
    verbo = ""
    m = VERBO_INF.match(palabras[0])
    if m:
        verbo = palabras.pop(0)
    conectores = ("de", "del", "la", "el", "los", "las", "un", "una", "a", "en", "con",
                  "por", "para", "al", "que", "si", "no", "ya", "aun", "aún", "esta",
                  "está", "estan", "están", "puede", "puedo", "se", "me", "te", "le",
                  "lo", "hay", "fue", "era", "son", "es")
    cuerpo = [w for w in palabras if w.lower() not in ADJ_ESTADO and w.lower() not in conectores]
    while cuerpo and cuerpo[-1].lower() in ("y", "o", "e", "u"):
        cuerpo.pop()
    if not cuerpo:
        cuerpo = palabras
    sujeto = " ".join(cuerpo[:3]).strip(" ,.;:-")
    if sujeto[:1].islower():
        sujeto = sujeto[0].upper() + sujeto[1:]
    return verbo, sujeto


def shrink_subject(subject: str, limit: int = 3) -> tuple[str, str]:
    """Cut a long subject down to a clean nominal head, and return the remaining words.

    El sujeto es el bloque o entidad, no la frase (1–3 palabras, sin verbo ni conectores
    colgando). Si se detectan palabras mutiladas o no se puede derivar un núcleo limpio,
    devuelve ('', '') para que la sesión no sea tocada ni contaminada.

    («brave no esta abriendo»)          → («Brave», «no esta abriendo»)
    («Hola DeepSeek estás funcionando») → («DeepSeek», «Hola estás funcionando»)
    («Crear proyecto Nous Hackaton 2026 en») → («Nous Hackaton», «Crear proyecto 2026 en»)
    («Recuperar ventanas y pestañas perdid») → («», «»)  # mutilada, no tocar
    """
    texto = (subject or "").strip()
    if not texto:
        return "", ""
    palabras = [w.strip(".,;:¡!¿?()\"'") for w in texto.split()]
    palabras = [w for w in palabras if w]
    if not palabras:
        return "", ""

    # 1. Entidad conocida en cualquier posición (DeepSeek, Brave, Nous...)
    for i, w in enumerate(palabras):
        low = w.lower()
        if low in KNOWN_ENTITIES:
            head_words = [KNOWN_ENTITIES[low]]
            if i + 1 < len(palabras):
                next_w = palabras[i + 1]
                if (_is_proper_word(next_w) and not _is_mutilated(next_w)):
                    head_words.append(next_w)
            head = " ".join(head_words)
            if _is_clean_head(head, limit):
                cola_words = [cw for j, cw in enumerate(palabras)
                              if not (i <= j < i + len(head_words)) and not _is_mutilated(cw)]
                sub_cola = [
                    cw for cw in cola_words
                    if _is_proper_word(cw) and cw.lower() not in {"hola", "buenas", "hey", "aria", "agent", "by", "use"}
                ]
                if sub_cola:
                    return "", ""
                cola = " ".join(cola_words).strip(" ,.;:-")
                return head, cola

    # 2. Bloque contiguo de nombres propios (sin arrancar con verbos o conectores)
    proper_spans = []
    current_span = []
    for w in palabras:
        if _is_proper_word(w):
            current_span.append(w)
        else:
            if current_span:
                proper_spans.append(current_span)
                current_span = []
    if current_span:
        proper_spans.append(current_span)

    if proper_spans:
        best_span = max(proper_spans, key=len)[:limit]
        # Debe ser una entidad real o al menos 2 nombres propios contiguos (no una palabra genérica en pos 0)
        is_real = (len(best_span) >= 2
                   or best_span[0].lower() in KNOWN_ENTITIES
                   or any(c.isupper() for c in best_span[0][1:]))
        if is_real:
            head = " ".join(best_span)
            if _is_clean_head(head, limit):
                cola_words = [cw for cw in palabras if cw not in best_span and not _is_mutilated(cw)]
                sub_cola = [
                    cw for cw in cola_words
                    if _is_proper_word(cw) and cw.lower() not in {"hola", "buenas", "hey", "aria", "agent", "by", "use"}
                ]
                if sub_cola:
                    return "", ""
                cola = " ".join(cola_words).strip(" ,.;:-")
                return head, cola

    # 3. Si contiene palabras mutiladas o no tiene entidad y supera el límite: descartar
    if any(_is_mutilated(w) for w in palabras):
        return "", ""
    if len(palabras) > limit:
        return "", ""

    # 4. Si tiene <= limit palabras y es un núcleo limpio completo:
    if _is_clean_head(texto, limit):
        return texto, ""

    return "", ""


def slug_key(subject: str) -> str:
    """Case- and accent-insensitive key used for the MMM counter."""
    s = unicodedata.normalize("NFKD", (subject or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def render(
    nnn: int,
    facets: Facets,
    date: str = "",
    *,
    max_len: int = MAX_TITLE_LENGTH,
    with_date: bool = False,
) -> str:
    """Build the title, spending the budget in priority order.

    Subject and axes are never truncated. The description is compressed, then
    cut, then dropped. The verb is the first thing to go.
    """
    subject = core_subject(facets.subject) or facets.subject or "Sin Sujeto"
    # The ordinal sits OUTSIDE the subject bracket. Inside, a reader takes
    # "Chat en Telegram 001" for the subject's name instead of its counter.
    head = f"{nnn:03d} [{subject}] {facets.subject_ordinal:03d}"
    if facets.iq1:
        head += f" [{facets.iq1}]"
    if facets.iq2:
        head += f" [{facets.iq2}]"
    # The date is a first-class filter in the catalog, and repeating it inside
    # the title spends six of the hundred characters on a duplicate. It is off
    # by default; `with_date=True` restores the old shape.
    if date and with_date:
        head += f" {date}"

    if len(head) >= max_len:
        # The fixed part alone does not fit: drop the surrounding decoration
        # rather than cut a word of the subject.
        return head[:max_len].rstrip()

    verb = normalize_verb(facets.verb)
    tail = f" · {verb}" if verb else ""
    budget = max_len - len(head) - 1  # the space before the description

    desc = fit_description(facets.description, budget - len(tail))
    if desc:
        return f"{head} {desc}{tail}".strip()

    # No room for a description: try just the verb, then nothing.
    if verb and len(head) + len(tail) + 1 <= max_len:
        return f"{head}{tail}".strip()
    return head


def validate(title: str, subject: str = "", iq1: str = "") -> list[str]:
    """Return a list of problems; empty means the title is sound."""
    problems: list[str] = []
    if len(title) > MAX_TITLE_LENGTH:
        problems.append(f"too long: {len(title)} > {MAX_TITLE_LENGTH}")
    if title != title.strip():
        problems.append("leading or trailing whitespace")
    if re.search(r"\s{2,}", title):
        problems.append("double space")
    if subject and iq1 and slug_key(core_subject(subject)) == slug_key(iq1):
        problems.append("subject repeats iq1")
    if "]" in title and title.count("[") != title.count("]"):
        problems.append("unbalanced brackets")
    return problems


__all__ = [
    "MAX_TITLE_LENGTH",
    "Facets",
    "short_date",
    "telegram",
    "fit_description",
    "core_subject",
    "strip_spec",
    "shrink_subject",
    "slug_key",
    "render",
    "validate",
]
