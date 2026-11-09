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

DEFAULT_PLATFORM: Final[str] = "Hermes Agent"

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
    "Investigar",
    "Verificar",
    "Comparar",
    "Configurar",
    "Instalar",
    "Organizar",
    "Analizar",
    "Respaldar",
    "Corregir",
    "Documentar",
    "Migrar",
    "Monitorear",
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
]
