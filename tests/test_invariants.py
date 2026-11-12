"""Invariants that must never regress.

Run with:  python3 -m pytest tests/ -q
           or: python3 tests/test_invariants.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.normalize import Facets, core_subject, fit_description, render, short_date, validate  # noqa: E402
from core.taxonomy import normalize_platform, normalize_pillar, normalize_verb  # noqa: E402


# --------------------------------------------------------------------------- #
# core/ must stay host-free
# --------------------------------------------------------------------------- #


def test_core_has_no_host_imports() -> None:
    forbidden = re.compile(r"^\s*(from|import)\s+(hermes_state|hermes_cli|adapters)\b", re.M)
    offenders = []
    for path in (ROOT / "core").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in forbidden.finditer(text):
            offenders.append(f"{path.name}: {m.group(0).strip()}")
    assert not offenders, "core/ imported the host:\n" + "\n".join(offenders)


# --------------------------------------------------------------------------- #
# The 100-character ceiling
# --------------------------------------------------------------------------- #


def test_titles_never_exceed_100() -> None:
    long_desc = "Revisar " + " ".join(["palabra"] * 40)
    f = Facets(
        subject="Diagnóstico de red inalámbrica",
        subject_ordinal=12,
        iq1="Hermes Agent",
        iq2="Networking",
        description=long_desc,
        verb="Investigar",
    )
    t = render(999, f, "19ago")
    assert len(t) <= 100, f"{len(t)} chars: {t}"


def test_short_title_keeps_full_description() -> None:
    f = Facets(subject="Air 2S", subject_ordinal=3, iq1="DJI", iq2="Ebay",
               description="Evaluar el bundle Fly More", verb="Comparar")
    t = render(748, f, "19ago")
    assert "Evaluar el bundle Fly More" in t
    assert t.endswith("· Comparar")
    assert len(t) <= 100


def test_telegram_mode_when_it_does_not_fit() -> None:
    desc = "Evaluar el paquete de accesorios y comparar con la oferta del vendedor anterior"
    f = Facets(subject="Air 2S", subject_ordinal=3, iq1="DJI", iq2="Ebay",
               description=desc, verb="Comparar")
    t = render(748, f, "19ago")
    assert len(t) <= 100
    # something of the description survived, or nothing did — never half a word
    assert not re.search(r"\w-$", t)


def test_description_dropped_when_unusable() -> None:
    assert fit_description("de la", 40) == ""
    assert fit_description("Ok", 40) == ""


# --------------------------------------------------------------------------- #
# Subject rules
# --------------------------------------------------------------------------- #


def test_subject_strips_action_prefix() -> None:
    assert core_subject("Suplemento Vitamina C") == "Vitamina C"
    assert core_subject("Instalación de Logseq 2.0") == "Logseq 2.0"
    assert core_subject("Auto-arranque Gateway Telegram") == "Gateway Telegram"


def test_subject_repeating_tag1_is_flagged() -> None:
    t = "748 [DJI 001] [DJI] 19ago algo que decir"
    problems = validate(t, subject="DJI", iq1="DJI")
    assert "subject repeats iq1" in problems


# --------------------------------------------------------------------------- #
# Taxonomy folds
# --------------------------------------------------------------------------- #


def test_platform_folding() -> None:
    assert normalize_platform("dji ronin") == "DJI"
    assert normalize_platform("Cyberpanel") == "CyberPanel"
    assert normalize_platform("HERMES") == "Hermes Agent"
    # Per docs/FEATURES.md an unknown protagonist stays EMPTY: the old
    # "Hermes Agent" fallback is banned, so this assertion must stay "".
    assert normalize_platform("inventado-xyz") == ""


def test_pillar_folding() -> None:
    assert normalize_pillar("asistente ia") == "Asistente IA"
    assert normalize_pillar("nada") == "Temas Varios"


def test_verb_folding() -> None:
    assert normalize_verb("comparar") == "Comparar"
    assert normalize_verb("· Verificar") == "Verificar"
    assert normalize_verb("xyz") == ""


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #


def test_short_date() -> None:
    assert short_date("2026-08-19") == "19ago"
    assert short_date("2026-11-07") == "07nov"
    assert short_date("") == ""


# --------------------------------------------------------------------------- #
# Runner (no pytest needed)
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
