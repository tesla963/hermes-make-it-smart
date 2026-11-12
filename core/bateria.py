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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two batteries **by key**: the override wins only where it speaks.

    A section present in both is merged entry by entry, so a personal battery that
    defines one brand does not delete the other twenty-five. Scalars and lists
    replace whole.
    """
    out = dict(base)
    for key, value in (override or {}).items():
        if value is None:
            # An empty section in the personal battery means "nothing said here",
            # not "delete this section". Skipping None keeps the manual intact.
            continue
        current = out.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            out[key] = _deep_merge(current, value)
        else:
            out[key] = value
    return out


def _personal_path() -> Path | None:
    """The owner's own battery, or None when it cannot be resolved."""
    try:
        from .paths import bateria_personal  # noqa: PLC0415

        p = bateria_personal()
        return p if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def _load_packaged() -> dict[str, Any]:
    """The manual that travels with the plugin, cached for the process."""
    return _read_yaml(BATERIA_PATH)


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read one YAML battery. A missing PyYAML degrades to an empty sheet."""
    if not path.exists():
        return {}
    try:
        import yaml  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def load_bateria(path: str | None = None, merge_personal: bool = True) -> dict[str, Any]:
    """Read the cheatsheet: the packaged manual plus, by default, the owner's own.

    The contract at the top of ``bateria.personal.yaml`` says the classifier reads
    both and that the owner's experience wins over the manual. This is where that
    promise is kept: the two are merged key by key, and the personal battery
    overrides only the entries it actually defines.

    Pass ``merge_personal=False`` (or an explicit ``path``) for an objective-only
    read. The personal file is re-read on every call, so editing it takes effect
    on the next classification without restarting anything.
    """
    if path is not None:
        return _read_yaml(Path(path))

    data = _load_packaged()
    if not merge_personal or not data:
        return data

    personal = _personal_path()
    if personal is None:
        return data
    extra = _read_yaml(personal)
    return _deep_merge(data, extra) if extra else data


def brand_of(subject: str, bateria: dict[str, Any] | None = None) -> tuple[str, bool] | None:
    """(Iq1, strip_from_subject) for a subject, or None when unknown.

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
                candidates.append((name, str(spec.get("iq1") or key.title()), bool(spec.get("strip"))))

    for key, spec in (b.get("programas") or {}).items():
        spec = spec or {}
        names = [key] + ([str(spec["marca"]).lower()] if spec.get("marca") else [])
        for name in names:
            if name and low.startswith(name):
                candidates.append((name, str(spec.get("marca") or key.title()), False))

    if not candidates:
        return None
    candidates.sort(key=lambda c: -len(c[0]))
    _, iq1, strip = candidates[0]
    return iq1, strip


def strip_brand(subject: str, bateria: dict[str, Any] | None = None) -> tuple[str, str]:
    """Remove the brand from the subject when the batería says it should leave.

    Returns (new_subject, iq1). Unchanged subject when the rule does not apply
    or when stripping would leave something meaningless.
    """
    found = brand_of(subject, bateria)
    if not found:
        return subject, ""
    iq1, strip = found
    if not strip:
        return subject, iq1
    low = subject.lower()
    b = bateria if bateria is not None else load_bateria()

    # Every name that maps to this Iq1: the brand key, its products and its lines.
    names: set[str] = set()
    for group in ("marcas", "programas"):
        for key, spec in (b.get(group) or {}).items():
            spec = spec or {}
            owner = str(spec.get("iq1") or spec.get("marca") or key).lower()
            if owner != iq1.lower():
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
        return subject, iq1
    return rest, iq1


def for_prompt(bateria: dict[str, Any] | None = None, limit: int = 42) -> str:
    """A compact block the model can carry without blowing the prompt budget."""
    b = bateria if bateria is not None else load_bateria()
    lines: list[str] = []

    marcas = b.get("marcas") or {}
    if marcas:
        lines.append("Known brands (Iq1):")
        for key, spec in list(marcas.items())[:limit]:
            spec = spec or {}
            iq1 = spec.get("iq1") or key.title()
            extra = ""
            if spec.get("productos"):
                extra = " · " + ", ".join(str(x) for x in spec["productos"][:5])
            elif spec.get("lineas"):
                extra = " · lines: " + ", ".join(str(x) for x in spec["lineas"][:4])
            lines.append(f"  {key} -> {iq1}{extra}")

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
        lines.append("Product shape: subject = the generic object, Iq1 = brand, Iq2 = model.")
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
