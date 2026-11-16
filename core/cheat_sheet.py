"""La cheat_sheet: the cheatsheet the classifier consults.

Pure Python, no host imports. Every user keeps their own `cheat_sheet.yaml`; this
module only knows how to read it and answer two questions:

    brand_of(subject)  -> who makes this, and does the brand leave the subject?
    for_prompt()       -> the compact block the model carries

The cheat_sheet is data, not code. Editing the YAML is how the system learns a new
brand without touching a single line of Python.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

CHEAT_SHEET_PATH = Path(__file__).with_name("cheat_sheet.yaml")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two batteries **by key**: the override wins only where it speaks.

    A section present in both is merged entry by entry, so a personal cheat_sheet that
    defines one brand does not delete the other twenty-five. Scalars and lists
    replace whole.
    """
    out = dict(base)
    for key, value in (override or {}).items():
        if value is None:
            # An empty section in the personal cheat_sheet means "nothing said here",
            # not "delete this section". Skipping None keeps the manual intact.
            continue
        current = out.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            out[key] = _deep_merge(current, value)
        else:
            out[key] = value
    return out


def _personal_path() -> Path | None:
    """The owner's own cheat_sheet, or None when it cannot be resolved."""
    try:
        from .paths import cheat_sheet_personal  # noqa: PLC0415

        p = cheat_sheet_personal()
        return p if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def _load_packaged() -> dict[str, Any]:
    """The manual that travels with the plugin, cached for the process."""
    return _read_yaml(CHEAT_SHEET_PATH)


def _parse_inline_list(raw: str) -> list[str]:
    inner = raw.strip()[1:-1]
    return [x.strip().strip("\"'") for x in inner.split(",") if x.strip().strip("\"'")]


def _fallback_parse_cheat_sheet(text: str) -> dict[str, Any]:
    """Minimal stdlib parser for `cheat_sheet.yaml` when PyYAML is not installed."""
    import re
    out: dict[str, Any] = {}
    section = ""
    entry_key = ""
    sub_section = ""
    sub_key = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.split("#", 1)[0].rstrip() if not raw_line.lstrip().startswith("#") else ""
        i += 1
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        s = stripped.strip()
        if indent == 0 and ":" in s:
            k, v = [x.strip() for x in s.split(":", 1)]
            if not v:
                section = k
                out[section] = {}
                entry_key = ""
                sub_section = ""
            else:
                out[k] = v.strip("\"'")
        elif indent == 2 and section and ":" in s:
            k, v = [x.strip() for x in s.split(":", 1)]
            k = k.strip("\"'")
            entry_key = k
            sub_section = ""
            if v.startswith("{") and v.endswith("}"):
                obj: dict[str, Any] = {}
                for part in re.split(r",\s*(?=[a-zA-Z0-9_]+\s*:)", v[1:-1]):
                    if ":" in part:
                        pk, pv = [x.strip() for x in part.split(":", 1)]
                        obj[pk] = _parse_inline_list(pv) if pv.startswith("[") and pv.endswith("]") else pv.strip("\"'")
                out[section][entry_key] = obj
            elif v.startswith("[") and v.endswith("]"):
                out[section][entry_key] = _parse_inline_list(v)
            elif not v or v == ">":
                out[section][entry_key] = {}
            else:
                out[section][entry_key] = v.strip("\"'")
        elif indent == 4 and section and entry_key and isinstance(out[section].get(entry_key), dict) and ":" in s:
            k, v = [x.strip() for x in s.split(":", 1)]
            k = k.strip("\"'")
            while v.startswith("[") and not v.endswith("]") and i < len(lines):
                nxt = lines[i].split("#", 1)[0].strip()
                v = v + " " + nxt
                i += 1
            if v.startswith("[") and v.endswith("]"):
                out[section][entry_key][k] = _parse_inline_list(v)
                sub_section = ""
            elif not v:
                sub_section = k
                out[section][entry_key][sub_section] = {}
            elif v in ("true", "false"):
                out[section][entry_key][k] = (v == "true")
                sub_section = ""
            elif v == ">":
                out[section][entry_key][k] = ""
                sub_section = ""
            else:
                out[section][entry_key][k] = v.strip("\"'")
                sub_section = ""
        elif indent == 6 and section and entry_key and sub_section and ":" in s:
            k, v = [x.strip() for x in s.split(":", 1)]
            k = k.strip("\"'")
            sub_key = k
            target = out[section][entry_key].get(sub_section)
            if isinstance(target, dict) and not v:
                target[sub_key] = {}
        elif indent == 8 and section and entry_key and sub_section and sub_key and ":" in s:
            k, v = [x.strip() for x in s.split(":", 1)]
            target = out[section][entry_key].get(sub_section, {}).get(sub_key)
            if isinstance(target, dict) and v and v != ">":
                target[k.strip("\"'")] = v.strip("\"'")
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read one YAML cheat_sheet. A missing PyYAML falls back to the stdlib parser."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        try:
            return _fallback_parse_cheat_sheet(text)
        except Exception:  # noqa: BLE001
            return {}
    try:
        data = yaml.safe_load(text)
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def load_cheat_sheet(path: str | None = None, merge_personal: bool = True) -> dict[str, Any]:
    """Read the cheatsheet: the packaged manual plus, by default, the owner's own.

    The contract at the top of ``cheat_sheet.personal.yaml`` says the classifier reads
    both and that the owner's experience wins over the manual. This is where that
    promise is kept: the two are merged key by key, and the personal cheat_sheet
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


def brand_of(subject: str, cheat_sheet: dict[str, Any] | None = None) -> tuple[str, bool] | None:
    """(Iq1, strip_from_subject) for a subject, or None when unknown.

    Longest key wins, so "gorgon halo" beats "amd" and "mac mini" beats "apple".
    """
    b = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()
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


def strip_brand(subject: str, cheat_sheet: dict[str, Any] | None = None) -> tuple[str, str]:
    """Remove the brand from the subject when the cheat_sheet says it should leave.

    Returns (new_subject, iq1). Unchanged subject when the rule does not apply
    or when stripping would leave something meaningless.
    """
    found = brand_of(subject, cheat_sheet)
    if not found:
        return subject, ""
    iq1, strip = found
    if not strip:
        return subject, iq1
    low = subject.lower()
    b = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()

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


def for_prompt(cheat_sheet: dict[str, Any] | None = None, limit: int = 42) -> str:
    """A compact block the model can carry without blowing the prompt budget."""
    b = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()
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


def stats(cheat_sheet: dict[str, Any] | None = None) -> dict[str, int]:
    b = cheat_sheet if cheat_sheet is not None else load_cheat_sheet()
    return {
        "marcas": len(b.get("marcas") or {}),
        "programas": len(b.get("programas") or {}),
        "productos": len(b.get("productos") or {}),
        "companias": len(b.get("companias") or {}),
        "servicios": len(b.get("servicios") or {}),
        "conceptos": len(b.get("conceptos") or {}),
    }


__all__ = ["load_cheat_sheet", "brand_of", "strip_brand", "for_prompt", "stats", "CHEAT_SHEET_PATH"]
