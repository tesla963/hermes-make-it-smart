"""Taxonomy: the closed vocabularies the classifier is allowed to use.

No host imports. Plain data plus small helpers.

A taxonomy exists to keep the catalog navigable: if the model can invent a new
platform on every session, the facet list grows to hundreds of one-off values
and filtering stops working. Closed vocabularies are a feature, not a limit.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# iq3 — work fronts (themes, iq4 in the title numbering). Order matters for display.
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
# iq1 — the program or platform. The work is done inside it; the protagonist is iq0 (the subject).
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
# every session; that makes it the AUTHOR, never the platform. An empty Iq1 is
# honest: it says nobody knew, and it leaves the slot free for the maker.
DEFAULT_PLATFORM: Final[str] = ""

# --------------------------------------------------------------------------- #
# iq2 — work families
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
# iq4 / iq5 / iq6
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
# short form means nothing to a human. Keep the full string and let Iq1 carry
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


def is_redundant_axis(subject: str, axis: str) -> bool:
    """True when the axis only repeats what the subject already says."""
    if not axis:
        return False
    s = subject.strip().lower()
    t = axis.strip().lower()
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
    "normalize_intention",
    "normalize_context",
    "normalize_theme",
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
    "is_redundant_axis",
    "ABBREVIATIONS",
    "KEEP_FULL",
]

# --------------------------------------------------------------------------- #
# The 2026-11-10 schema
# --------------------------------------------------------------------------- #
# iq1 = the program the work happens in (or that the work is about)
# iq2 = the context that qualifies it (store, country or machine)
# iq3 = the intention (a verb)
# iq4 = the work front (theme, with subcategories)
# iq5 = the year
# --------------------------------------------------------------------------- #

# Closed vocabulary. Seven verbs the owner approved; a word outside this list
# is not an intention, and an empty iq3 is honest — it says nobody read one.
INTENTIONS: Final[tuple[str, ...]] = (
    "Troubleshooting",
    "Search the Web",
    "Compatibility",
    "Buy",
    "Quote",
    "Compare",
    "Configuration",
)
# "Install" is not a separate intention: Configuration implies installation. You
# cannot configure what you did not install, so both fold onto Configuration.

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
    # Data Mining and Data Security were Iq2 values; the owner moved them here,
    # to a theme, because they name a front and not a verb.
    "Data Mining",
    "Data Security",
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


# --------------------------------------------------------------------------- #
# Normalisers for the 2026-11-10 schema
# --------------------------------------------------------------------------- #

_INTENT_ALIASES: Final[dict[str, str]] = {
    # Compare
    "comparar": "Compare", "comparacion": "Compare", "comparación": "Compare",
    "comparativo": "Compare", "vs": "Compare", "compare": "Compare",
    "comparison": "Compare",
    # Configuration — installation is folded in, never a separate intention
    "instalar": "Configuration", "instalacion": "Configuration",
    "instalación": "Configuration", "install": "Configuration",
    "configurar": "Configuration", "configuracion": "Configuration",
    "configuración": "Configuration", "configuration": "Configuration",
    "configure": "Configuration", "setup": "Configuration",
    # Search the Web
    "investigar": "Search the Web", "investigacion": "Search the Web",
    "investigación": "Search the Web", "investigate": "Search the Web",
    "consultar": "Search the Web", "buscar": "Search the Web",
    "search": "Search the Web", "search the web": "Search the Web",
    "web": "Search the Web", "googlear": "Search the Web",
    # Quote
    "cotizar": "Quote", "cotizacion": "Quote", "cotización": "Quote",
    "quote": "Quote", "precio": "Quote", "precios": "Quote", "price": "Quote",
    # Buy
    "comprar": "Buy", "compra": "Buy", "buy": "Buy", "purchase": "Buy",
    # Troubleshooting — 'testear' folded here: it verifies a state
    "troubleshooting": "Troubleshooting", "diagnosticar": "Troubleshooting",
    "reparar": "Troubleshooting", "arreglar": "Troubleshooting",
    "componer": "Troubleshooting", "fix": "Troubleshooting",
    "fixing": "Troubleshooting", "repair": "Troubleshooting",
    "diagnostico": "Troubleshooting", "diagnóstico": "Troubleshooting",
    "testear": "Troubleshooting", "testing": "Troubleshooting",
    "test": "Troubleshooting", "verificar": "Troubleshooting",
    "comprobar": "Troubleshooting", "probar": "Troubleshooting",
    # Compatibility
    "compatibilidad": "Compatibility", "compatible": "Compatibility",
    "compatibility": "Compatibility",
}


def normalize_intention(raw: str) -> str:
    """Fold any spelling of a verb onto the closed list, or return "".

    "Administrar" is deliberately absent: the owner was unsure and left it out.
    An intention the list does not know is not an intention — it is silence,
    and silence is better than a field nobody can filter by twice.
    """
    key = (raw or "").strip().lower()
    if not key:
        return ""
    if key in _INTENT_ALIASES:
        return _INTENT_ALIASES[key]
    for name in INTENTIONS:
        if name.lower() == key:
            return name
    return ""


_THEME_ALIASES: Final[dict[str, str]] = {
    "it manager": "IT Manager", "it": "IT Manager", "sistemas": "IT Manager",
    "derecho constitucional": "Derecho", "derecho civil": "Derecho",
    "derecho": "Derecho",
    "medicina": "Medicina", "masoterapia": "Medicina", "salud": "Medicina",
    "geopolitica": "Geopolitica", "geopolítica": "Geopolitica",
    "educacion": "Educacion", "educación": "Educacion",
    "economista": "Economista", "economia": "Economista", "finanzas": "Economista",
    "compras": "Compras", "youtuber": "Youtuber", "youtube": "Youtuber",
    "temas varios": "Temas Varios",
    "data mining": "Data Mining", "mineria de datos": "Data Mining",
    "minería de datos": "Data Mining",
    "data security": "Data Security", "seguridad": "Data Security",
}


def normalize_theme(raw: str) -> str:
    """Fold a theme or a subcategory onto the closed list, or return ""."""
    key = (raw or "").strip().lower()
    if not key:
        return ""
    for name in IT_SUBCATEGORIES:          # subcategories win over the theme
        if name.lower() == key:
            return name
    if key in _THEME_ALIASES:
        return _THEME_ALIASES[key]
    for name in THEMES:
        if name.lower() == key:
            return name
    return ""


_KNOWN_STORES: Final[tuple[str, ...]] = (
    "Ebay", "Amazon", "AliExpress", "Alibaba", "Walmart", "Newegg",
    "MercadoLibre", "Aliexpress", "Banggood", "Temu", "Best Buy", "eBay",
)
_KNOWN_COUNTRIES: Final[tuple[str, ...]] = (
    "Panamá", "Panama", "Estados Unidos", "USA", "United States", "China",
    "Japón", "Japon", "España", "Mexico", "México", "Colombia", "Costa Rica",
)
_KNOWN_MACHINES: Final[tuple[str, ...]] = (
    "Mac mini M4", "Mac mini M6", "Mac Studio", "MacBook Air", "MacBook Pro",
    "ThinkPad P53", "ThinkPad E580", "ThinkPad T480s", "ThinkPad P15",
    "Precision 7760", "Inspiron 5570", "VPS", "Teléfono", "iPhone",
    "iPad", "Android", "Gorgon Halo", "Sofía", "Sofia",
)


def normalize_context(raw: str) -> str:
    """iq2 accepts a store, a country or a machine — nothing else.

    Left open, the model filled it with whatever it had at hand: "Comparación"
    91 times, "Automation" 76, "WebHosting" 25. Those are intentions and
    families, and they already have their own field. A context the list does not
    recognise is an empty context: the session simply had none.
    """
    key = (raw or "").strip()
    if not key:
        return ""
    low = key.lower()
    for group in (_KNOWN_STORES, _KNOWN_COUNTRIES, _KNOWN_MACHINES):
        for name in group:
            if name.lower() == low:
                return name
    return ""

