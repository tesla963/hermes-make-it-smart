"""La batería: the cheatsheet the classifier consults.

Pure Python, no host imports. Every user keeps their own `bateria.yaml`; this
module only knows how to read it and answer two questions:

    brand_of(subject)  -> who makes this, and does the brand leave the subject?
    for_prompt()       -> the compact block the model carries

The batería is data, not code. Editing the YAML is how the system learns a new
brand without touching a single line of Python.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

BATERIA_PATH = Path(__file__).with_name("bateria.yaml")


@lru_cache(maxsize=1)
def load_bateria(path: str | None = None) -> dict[str, Any]:
    """Read the cheatsheet. A missing PyYAML degrades to an empty sheet."""
    p = Path(path) if path else BATERIA_PATH
    if not p.exists():
        return {}
    try:
        import yaml  # noqa: PLC0415
    except Exception:
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def brand_of(subject: str, bateria: dict[str, Any] | None = None) -> tuple[str, bool] | None:
    """(Tag1, strip_from_subject) for a subject, or None when unknown.

    Longest key wins, so "gorgon halo" beats "amd" and "mac mini" beats "apple".
    """
    b = bateria if bateria is not None else load_bateria()
    low = (subject or "").strip().lower()
    if not low:
        return None

    candidates: list[tuple[str, str, bool]] = []

    for key, spec in (b.get("marcas") or {}).items():
        spec = spec or {}
        names = [key] + [str(x).lower() for x in (spec.get("productos") or [])]
        names += [str(x).lower() for x in (spec.get("lineas") or [])]
        for name in names:
            if name and low.startswith(name):
                candidates.append((name, str(spec.get("tag1") or key.title()), bool(spec.get("strip"))))

    for key, spec in (b.get("programas") or {}).items():
        spec = spec or {}
        names = [key] + ([str(spec["marca"]).lower()] if spec.get("marca") else [])
        for name in names:
            if name and low.startswith(name):
                candidates.append((name, str(spec.get("marca") or key.title()), False))

    if not candidates:
        return None
    candidates.sort(key=lambda c: -len(c[0]))
    _, tag1, strip = candidates[0]
    return tag1, strip


def strip_brand(subject: str, bateria: dict[str, Any] | None = None) -> tuple[str, str]:
    """Remove the brand from the subject when the batería says it should leave.

    Returns (new_subject, tag1). Unchanged subject when the rule does not apply
    or when stripping would leave something meaningless.
    """
    found = brand_of(subject, bateria)
    if not found:
        return subject, ""
    tag1, strip = found
    if not strip:
        return subject, tag1
    low = subject.lower()
    b = bateria if bateria is not None else load_bateria()

    # Every name that maps to this Tag1: the brand key, its products and its lines.
    names: set[str] = set()
    for group in ("marcas", "programas"):
        for key, spec in (b.get(group) or {}).items():
            spec = spec or {}
            owner = str(spec.get("tag1") or spec.get("marca") or key).lower()
            if owner != tag1.lower():
                continue
            names.add(key.lower())
            for field in ("productos", "lineas"):
                for x in spec.get(field) or []:
                    names.add(str(x).lower())

    rest = subject
    # Shortest first: strip only the brand token, not the whole product name
    # ("Gemini Flash Lite" must lose "Gemini", not all three words).
    for name in sorted(names, key=len):
        if name and low.startswith(name):
            rest = subject[len(name):].strip(" -–—:,")
            break
    # A remainder that starts with a digit ("3.8 27B", "5570") is not a subject:
    # keep the brand in place rather than leave something unreadable.
    if len(rest) < 4 or not any(c.isalpha() for c in rest) or rest[0].isdigit():
        return subject, tag1
    return rest, tag1


def for_prompt(bateria: dict[str, Any] | None = None, limit: int = 42) -> str:
    """A compact block the model can carry without blowing the prompt budget."""
    b = bateria if bateria is not None else load_bateria()
    lines: list[str] = []

    marcas = b.get("marcas") or {}
    if marcas:
        lines.append("Known brands (Tag1):")
        for key, spec in list(marcas.items())[:limit]:
            spec = spec or {}
            tag1 = spec.get("tag1") or key.title()
            extra = ""
            if spec.get("productos"):
                extra = " · " + ", ".join(str(x) for x in spec["productos"][:5])
            elif spec.get("lineas"):
                extra = " · lines: " + ", ".join(str(x) for x in spec["lineas"][:4])
            lines.append(f"  {key} -> {tag1}{extra}")

    programas = b.get("programas") or {}
    if programas:
        lines.append("")
        lines.append("Software that names itself (no corporate owner):")
        pairs = []
        for key, spec in list(programas.items())[:limit]:
            spec = spec or {}
            marca = spec.get("marca") or key.title()
            maker = f" ({spec['maker']})" if spec.get("maker") and spec["maker"] != marca else ""
            pairs.append(f"{marca}{maker}")
        lines.append("  " + " · ".join(pairs))

    conceptos = b.get("conceptos") or {}
    if conceptos:
        lines.append("")
        lines.append("Concepts that must survive as filters:")
        for key, spec in conceptos.items():
            spec = spec or {}
            nombre = spec.get("nombre") or key
            what = " ".join(str(spec.get("que_es") or "").split())[:150]
            lines.append(f"  {nombre}: {what}")

    productos = b.get("productos") or {}
    if productos:
        lines.append("")
        lines.append("Product shape: subject = the generic object, Tag1 = brand, Tag2 = model.")
        for key, spec in list(productos.items())[:10]:
            spec = spec or {}
            if spec.get("nota"):
                lines.append(f"  {key}: {' '.join(str(spec['nota']).split())}")

    return "\n".join(lines)


def stats(bateria: dict[str, Any] | None = None) -> dict[str, int]:
    b = bateria if bateria is not None else load_bateria()
    return {
        "marcas": len(b.get("marcas") or {}),
        "programas": len(b.get("programas") or {}),
        "productos": len(b.get("productos") or {}),
        "companias": len(b.get("companias") or {}),
        "servicios": len(b.get("servicios") or {}),
        "conceptos": len(b.get("conceptos") or {}),
    }


__all__ = ["load_bateria", "brand_of", "strip_brand", "for_prompt", "stats", "BATERIA_PATH"]
