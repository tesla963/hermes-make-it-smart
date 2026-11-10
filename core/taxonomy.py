"""Taxonomy: the closed vocabularies the classifier is allowed to use.

No host imports. Plain data plus small helpers.

A taxonomy exists to keep the catalog navigable: if the model can invent a new
platform on every session, the facet list grows to hundreds of one-off values
and filtering stops working. Closed vocabularies are a feature, not a limit.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Tag 3 — pillars (work fronts). Order matters for display.
# --------------------------------------------------------------------------- #

PILLARS: Final[tuple[str, ...]] = (
    "Asistente IA",
    "VPS",
    "Compras",
    "Productos",      # sub-pillar of Compras: a thing you buy
    "Servicios",      # sub-pillar of Compras: a service you hire
    "Data Backup",
    "Derecho",
    "Youtuber",
    "MindMap",
    "Geopolítica",
    "Masoterapia",
    "Temas Varios",  # always last, even when it is the largest bucket
)

PILLAR_LAST: Final[str] = "Temas Varios"

# --------------------------------------------------------------------------- #
# Tag 1 — platforms. The protagonist of the session.
# --------------------------------------------------------------------------- #

PLATFORMS: Final[tuple[str, ...]] = (
    # Host family — never abbreviated to a bare "Hermes"
    "Hermes Agent",
    "Hermes Desktop",
    "Hermes Terminal",
    "Hermes Telegram",
    # Infrastructure
    "CyberPanel",
    "OpenLiteSpeed",
    "WordPress",
    "VPS",
    "RustDesk",
    "Cloudflare",
    # Desktop & OS
    "MacOS Tahoe",
    "Windows",
    "Debian",
    # Apps
    "Brave",
    "Chromium",
    "Logseq",
    "Obsidian",
    "DEVONthink",
    "Tinderbox",
    "DaVinci Resolve",
    "HandBrake",
    "Insta360 Studio",
    "Ollama",
    "DeepSeek",
    "Gemini",
    "Kimi",
    "Ornith",
    # Messaging
    "WhatsApp",
    "Telegram",
    "YouTube",
    # Hardware & brands
    "DJI",
    "ORICO",
    "Apple",
    "ThinkPad",
    "Mac mini",
    "Mac Studio",
    "AMD",
    "NVIDIA",
    "Gorgon Halo",
    "Insta360",
    "Amazon",
    "Ebay",
)

# No default platform. "Hermes Agent" used to fill this slot, which meant every
# session the classifier could not place became a session "about Hermes Agent" —
# 303 of 884, spread across all eleven pillars. The assistant does the work in
# every session; that makes it the AUTHOR, never the platform. An empty Tag1 is
# honest: it says nobody knew, and it leaves the slot free for the maker.
DEFAULT_PLATFORM: Final[str] = ""

# --------------------------------------------------------------------------- #
# Tag 2 — work families
# --------------------------------------------------------------------------- #

IT_FAMILIES: Final[tuple[str, ...]] = (
    "IA",
    "Data Mining",
    "Automation",
    "WebHosting",
    "Troubleshooting",
    "VPS",
    "Data Security",
    "Multimedia",
    "Productivity",
    "MCP/CLI",
    "File System",
    "IT Manager",
    "Data Backup",
    "Programming",
    "Networking",
    "Data Recovery",
    "Repository",
)

NON_IT_FAMILIES: Final[tuple[str, ...]] = (
    "Derecho Constitucional",
    "Derecho Penal",
    "Derecho Civil",
    "Educación",
    "Medicina",
    "Nutrición",
    "Compras",
    "Geopolítica",
)

MARKET_FAMILIES: Final[tuple[str, ...]] = ("Ebay", "Amazon", "Comparación")

# --------------------------------------------------------------------------- #
# Tag 4 / 5 / 6
# --------------------------------------------------------------------------- #

COUNTRIES: Final[tuple[str, ...]] = (
    "Panamá",
    "Ciudad de Panamá",
    "El Cangrejo",
    "Dorado",
)

MACHINES: Final[tuple[str, ...]] = (
    "Mac mini M4",
    "VPS",
    "Teléfono",
    "ThinkPad P53",
    "ThinkPad E580",
    "ThinkPad T480s",
    "Varios",
)

# --------------------------------------------------------------------------- #
# Verbs — the description appendix
# --------------------------------------------------------------------------- #

VERBS: Final[tuple[str, ...]] = (
    # --- knowledge work ---
    "Investigar",
    "Verificar",
    "Testing",       # testing a configuration, the tech word for "verificar"
    "Comparar",
    "Analizar",
    "Documentar",
    "Organizar",
    "Vocabulario",   # building a vocabulary / glossary
    "Indexación",    # indexing, reindexing a store
    "Scrapping",     # harvesting pages, PDFs, listings to keep a local copy
    # --- money ---
    "Costo",         # what did this cost / what is the real cost
    "Cotizar",       # pricing a product or a service
    # --- machines ---
    "Configurar",
    "Instalar",
    "Corregir",
    "Solucionar",
    "Respaldar",
    "Migrar",
    "Monitorear",
    "Falta de Espacio",   # a disk problem is an action, not a subject
)

# Abbreviations that make a title shorter without losing meaning, for people who
# live in the domain. Applied only when the long form would be redundant.
ABBREVIATIONS: Final[dict[str, str]] = {
    "macos tahoe": "Tahoe",
    "macos sequoia": "Sequoia",
    "macos ventura": "Ventura",
    "hermes agent": "Hermes Agent",   # never a bare "Hermes"
}

# Names that must NOT be abbreviated: they are not common vocabulary, and the
# short form means nothing to a human. Keep the full string and let Tag1 carry
# the maker.
KEEP_FULL: Final[tuple[str, ...]] = (
    "Gorgon Halo",
    "Strix Halo",
    "Ryzen AI Max",
    "Insta360",
)


def normalize_platform(value: str | None) -> str:
    """Fold a proposed platform onto the closed vocabulary, case-insensitively."""
    if not value:
        return DEFAULT_PLATFORM
    needle = value.strip().lower()
    for known in PLATFORMS:
        if known.lower() == needle:
            return known
    for known in PLATFORMS:  # containment, longest first to prefer specific matches
        if needle and needle in known.lower():
            return known
    for known in sorted(PLATFORMS, key=len, reverse=True):
        if needle and known.lower() in needle:
            return known
    return DEFAULT_PLATFORM


def normalize_pillar(value: str | None) -> str:
    if not value:
        return "Temas Varios"
    needle = value.strip().lower()
    for known in PILLARS:
        if known.lower() == needle:
            return known
    return "Temas Varios"


def normalize_family(value: str | None) -> str:
    if not value:
        return ""
    needle = value.strip().lower()
    for group in (IT_FAMILIES, NON_IT_FAMILIES, MARKET_FAMILIES):
        for known in group:
            if known.lower() == needle:
                return known
    return value.strip()


def apply_abbreviation(text: str) -> str:
    """Shorten only what is common vocabulary; never touch what is not."""
    if not text:
        return text
    low = text.strip().lower()
    for keep in KEEP_FULL:
        if keep.lower() in low:
            return text.strip()
    for long_form, short in ABBREVIATIONS.items():
        if low == long_form:
            return short
        if low.startswith(long_form + " "):
            return short + text.strip()[len(long_form):]
    return text.strip()


def is_redundant_tag(subject: str, tag: str) -> bool:
    """True when the tag only repeats what the subject already says."""
    if not tag:
        return False
    s = subject.strip().lower()
    t = tag.strip().lower()
    if not s or not t:
        return False
    if s == t:
        return True
    return t in s.split() or s in t.split()


def normalize_verb(value: str | None) -> str:
    if not value:
        return ""
    needle = value.strip().lower().lstrip("·").strip()
    for known in VERBS:
        if known.lower() == needle:
            return known
    return ""


__all__ = [
    "PILLARS",
    "INTENTIONS",
    "IT_SUBCATEGORIES",
    "OTHER_THEMES",
    "THEMES",
    "PILLAR_LAST",
    "PLATFORMS",
    "DEFAULT_PLATFORM",
    "IT_FAMILIES",
    "NON_IT_FAMILIES",
    "MARKET_FAMILIES",
    "COUNTRIES",
    "MACHINES",
    "VERBS",
    "normalize_platform",
    "normalize_pillar",
    "normalize_family",
    "normalize_verb",
    "apply_abbreviation",
    "is_redundant_tag",
    "ABBREVIATIONS",
    "KEEP_FULL",
]

# --------------------------------------------------------------------------- #
# The 2026-11-10 schema
# --------------------------------------------------------------------------- #
# tag1 = the maker of the subject (adjective)
# tag2 = the context that qualifies it (store, country or machine)
# tag3 = the intention (a verb)
# tag4 = the work front (theme, with subcategories)
# tag5 = the year
# --------------------------------------------------------------------------- #

# Closed vocabulary. Seven verbs the owner approved; a word outside this list
# is not an intention, and an empty tag3 is honest — it says nobody read one.
INTENTIONS: Final[tuple[str, ...]] = (
    "Comparar",
    "Instalar",
    "Investigar",
    "Testear",
    "Cotizar",
    "Troubleshooting",
    "Compatibilidad",
)

# The theme IT Manager and its subcategories. A session that fits none of them
# stays as "IT Manager" alone until somebody decides.
IT_SUBCATEGORIES: Final[tuple[str, ...]] = (
    "IA Bot",
    "VPS",
    "Data Backup",
    "Hardware",
    "MindMap",
    "Network",
    "OS",
)

# Themes without subcategories yet.
OTHER_THEMES: Final[tuple[str, ...]] = (
    "Derecho",
    "Medicina",
    "Geopolitica",
    "Educacion",
    "Economista",
    "Compras",
    "Youtuber",
    "Temas Varios",
)

THEMES: Final[tuple[str, ...]] = ("IT Manager", *OTHER_THEMES)
