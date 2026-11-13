"""Who is in this session? The script's half of the protocol.

The model should never be asked *what this session is about* when the cheat_sheet
already holds the names. Asking it to re-derive "DJI", "DEVONthink" or "RayNeo"
from a transcript costs tokens to produce an answer a YAML key already had —
and, worse, it lets the model invent a brand when it is unsure.

So the work is split in two layers:

    1. actors.py  (this file)  — deterministic: pull every name out of the text
                                 using the cheat_sheet, and say which one is the
                                 subject, which is the brand, which is the
                                 product. No tokens. Same answer every time.
    2. intent.py              — the one judgement left: what did the user want
                                 DONE. Keywords first; the model only when the
                                 keywords are silent.

The split is not an optimisation. It is what makes the classifier auditable:
when a title is wrong you can point at the layer that was wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from core.cheat_sheet import load_cheat_sheet

# Kinds, ordered by how specific they are. When two actors overlap in the text,
# the more specific one wins the subject.
BRAND = "brand"
PROGRAM = "program"
PRODUCT = "product"
CONCEPT = "concept"
PERSON = "person"

_SPECIFICITY = {PRODUCT: 4, PROGRAM: 3, BRAND: 2, CONCEPT: 1, PERSON: 1}

# Words that never name anything, even when they look capitalised.
STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "en", "con", "por",
    "para", "que", "y", "o", "mi", "tu", "su", "lo", "se", "es", "son", "ya",
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "it",
    "how", "what", "why", "when", "lisa", "hermes", "hoy", "ayer",
}


@dataclass
class Actor:
    """A name found in the session, with where it came from."""

    name: str
    kind: str
    source: str = "cheat_sheet"  # cheat_sheet | text | model
    hits: int = 0
    aliases: list[str] = field(default_factory=list)

    @property
    def specificity(self) -> int:
        return _SPECIFICITY.get(self.kind, 0)

    def __str__(self) -> str:
        return f"{self.name} ({self.kind}, {self.hits})"


def _candidates(cheat_sheet: dict[str, Any]) -> list[tuple[str, str, list[str]]]:
    """Every name the cheat_sheet knows, as (canonical, kind, aliases)."""
    out: list[tuple[str, str, list[str]]] = []

    for key, val in (cheat_sheet.get("marcas") or {}).items():
        if not isinstance(val, dict):
            continue
        name = val.get("iq1") or key
        out.append((name, BRAND, [key]))
        # A product is its own actor, not an alias of its maker. "DJI Avata 360"
        # must resolve to the drone, never to the brand — otherwise every DJI
        # session collapses into "[DJI]" and the product disappears.
        for prod in val.get("productos") or []:
            # "DJI Avata 360", "Avata 360" and "avata360" are the same product:
            # people drop the maker and the space when they type quickly.
            out.append((prod, PRODUCT, [f"{name} {prod}", prod, prod.replace(" ", "")]))

    for key, val in (cheat_sheet.get("programas") or {}).items():
        if not isinstance(val, dict):
            continue
        name = val.get("marca") or key
        # People write "DEVONthink", "Devon Think" and "devonthink" for the same
        # programme. The spellings are declared in the cheat_sheet rather than
        # guessed from the capitalisation — a regex cannot know that DEVON is a
        # company and think is a verb.
        out.append((name, PROGRAM, [key, *(val.get("alias") or [])]))

    for key, val in (cheat_sheet.get("companias") or {}).items():
        if not isinstance(val, dict):
            continue
        name = val.get("nombre") or key
        out.append((name, BRAND, [key]))

    for key, val in (cheat_sheet.get("conceptos") or {}).items():
        if not isinstance(val, dict):
            continue
        name = val.get("nombre") or key.replace("_", " ")
        out.append((name, CONCEPT, [key.replace("_", " ")]))

    for key, val in (cheat_sheet.get("logistica") or {}).items():
        if not isinstance(val, dict) or "iq1" not in val:
            continue
        out.append((val["iq1"], BRAND, [key]))
        for pname, prod in (val.get("productos") or {}).items():
            if isinstance(prod, dict) and prod.get("sujeto"):
                out.append((prod["sujeto"], PRODUCT, [pname]))

    return out


def _word_re(name: str) -> re.Pattern[str]:
    """Boundary-safe matcher: 'mini' must not hit 'minimo'."""
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I)


def find_actors(
    text: str,
    cheat_sheet: dict[str, Any] | None = None,
    *,
    extra: Sequence[str] = (),
) -> list[Actor]:
    """Every name the cheat_sheet can see in `text`, most specific first."""
    bat = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()
    found: dict[str, Actor] = {}

    for canonical, kind, aliases in _candidates(bat):
        hits = 0
        matched: list[str] = []
        for alias in [canonical, *aliases]:
            if not alias or len(alias) < 2:
                continue
            n = len(_word_re(alias).findall(text))
            if n:
                hits += n
                matched.append(alias)
        if hits:
            found[canonical] = Actor(canonical, kind, "cheat_sheet", hits, matched)

    for name in extra:
        if name and name not in found and _word_re(name).search(text):
            found[name] = Actor(name, CONCEPT, "text", 1)

    # Length before frequency: "V4.1 Flash" and "V4" both match the same phrase,
    # and the short one always wins on hits because it is a substring of the
    # long one. The longer name is the more specific fact.
    return sorted(found.values(), key=lambda a: (-a.specificity, -len(a.name), -a.hits, a.name))


def subject_candidate(actors: Iterable[Actor]) -> Actor | None:
    """The subject is the most specific name the user actually touched.

    Not the most frequent: a session that mentions "DJI" nine times while
    comparing two of its controllers is about the controllers, not about DJI.
    Frequency counts mentions; specificity counts relevance.
    """
    ranked = sorted(actors, key=lambda a: (-a.specificity, -len(a.name), -a.hits))
    return ranked[0] if ranked else None


def brand_of_subject(
    subject: Actor | None,
    actors: Iterable[Actor],
    cheat_sheet: dict[str, Any] | None = None,
) -> str:
    """Which actor is the maker of the subject."""
    bat = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()
    if subject is None:
        return ""
    if subject.kind == BRAND:
        return subject.name

    low = subject.name.lower()
    for key, val in (bat.get("programas") or {}).items():
        if not isinstance(val, dict):
            continue
        if (val.get("marca") or "").lower() == low or key == low:
            return val.get("maker") or val.get("marca") or ""

    for brand in actors:
        if brand.kind != BRAND:
            continue
        for key, val in (bat.get("marcas") or {}).items():
            prods = [p.lower() for p in (val.get("productos") or [])]
            if low in prods or low.startswith(brand.name.lower() + " "):
                return brand.name
    return ""


def other_party(subject: Actor | None, actors: Iterable[Actor]) -> list[Actor]:
    """The actors that are not the subject — what the description must carry."""
    return [a for a in actors if subject is None or a.name != subject.name]


def describe(text: str, cheat_sheet: dict[str, Any] | None = None) -> dict[str, Any]:
    """One call the rest of the pipeline can use without knowing the rules."""
    bat = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()
    actors = find_actors(text, bat)
    subject = subject_candidate(actors)
    return {
        "actors": [{"name": a.name, "kind": a.kind, "hits": a.hits} for a in actors],
        "subject": subject.name if subject else "",
        "subject_kind": subject.kind if subject else "",
        "brand": brand_of_subject(subject, actors, bat),
        "others": [a.name for a in other_party(subject, actors)],
        # True when the script found nothing: the model must be asked.
        "needs_model": subject is None,
    }
