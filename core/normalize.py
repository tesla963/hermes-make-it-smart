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
# "A vs B" description was silently dropped and the title ended in a bare tag.
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

    Subject and tags are never truncated. The description is compressed, then
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
    "slug_key",
    "render",
    "validate",
]
