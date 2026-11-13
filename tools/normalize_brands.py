#!/usr/bin/env python3
"""Normalize session titles against the brand / spec rules.

Reads every Hermes profile, parses the canonical title, applies the rules the
owner dictated, and rewrites the title through SessionDB.

Dry-run by default. `--apply` performs the rename after a verified backup.

Rules applied
-------------
R1  A corporate brand never lives in the subject; it belongs in Iq1.
    "Dell Inspiron 5570" -> Iq1 Dell, subject "Inspiron 5570".
    Exception: a product LINE stays in the subject ("ThinkPad P53", Iq1 Lenovo).
R2  A numeric spec does not live in the subject unless the session is about it.
    "Gorgon Halo 192GB" -> "Gorgon Halo".  "16 GB Ram" stays.
R3  When the subject equals Iq1, Iq1 moves to the maker (or to the software's
    own name when it has no corporate owner, as is usual with open source).
R4  Every brand found in a subject gets a Iq1 even when the title was fine.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import HermesTitleWriter, backup_databases, discover_databases  # noqa: E402
from core.normalize import Facets, render, short_date  # noqa: E402

TITLE_RE = re.compile(
    r"^(?P<nnn>\d{3,4})\s+\[(?P<subject>.+?)\s+(?P<mmm>\d{3,4})\]\s*"
    r"(?:\[(?P<iq1>[^\]]*)\])?\s*"
    r"(?:\[(?P<iq2>[^\]]*)\])?\s*"
    r"(?P<date>\d{2}[a-z]{3})?\s*"
    r"(?P<desc>.*?)(?:\s*·\s*(?P<verb>[^·]+))?\s*$"
)

# brand name as it appears at the start of a subject -> (Iq1, strip_from_subject)
BRANDS: dict[str, tuple[str, bool]] = {
    "dell": ("Dell", True),
    "gemini": ("Google", True),
    "claude": ("Anthropic", True),
    "kimi": ("Moonshot", True),
    "qwen": ("Alibaba", True),
    "grok": ("xAI", True),
    "copilot": ("Microsoft", True),
    "deepseek": ("DeepSeek", True),
    "ollama": ("Ollama", False),
    "pinokio": ("Pinokio", False),
    "ornith": ("Ornith", False),
    "skillspector": ("Nvidia", True),
    "logseq": ("Logseq", False),
    "obsidian": ("Obsidian", False),
    "brave": ("Brave", False),
    "cyberpanel": ("CyberPanel", False),
    "rustdesk": ("RustDesk", False),
    "dji": ("DJI", False),
    "insta360": ("Insta360", False),
    "gorgon halo": ("AMD", False),
    "strix halo": ("AMD", False),
    "ryzen": ("AMD", False),
    "thinkpad": ("Lenovo", False),   # the LINE stays in the subject
    "macbook": ("Apple", False),
    "mac mini": ("Apple", False),
    "mac studio": ("Apple", False),
    "iphone": ("Apple", False),
    "apple": ("Apple", False),
    "nvidia": ("NVIDIA", False),
    "geforce": ("NVIDIA", False),
    "quadro": ("NVIDIA", False),
}

# Numeric specifications that must not stay in the subject unless the session
# is about the number itself.
SPEC_RE = re.compile(r"\s+\d+\s?(?:GB|TB|MB|g\b|GB RAM|de RAM)\s*$", re.I)
SPEC_IS_THE_SUBJECT = re.compile(r"^\d+\s?(?:GB|TB|MB)\s+RAM$", re.I)

# Owner-dictated exact fixes.
OVERRIDES: dict[str, tuple[str, str, str]] = {
    # subject (lower) -> (new subject, new iq1, note)
    "dell inspiron 5570": ("Inspiron 5570", "Dell", "marca al iq1"),
    "gemini flash lite": ("Flash Lite", "Google", "marca al iq1"),
    "pinokio": ("Control CLI", "Pinokio", "sujeto no repite iq1"),
    "gorgon halo 192gb": ("Gorgon Halo", "AMD", "spec a la descripción"),
    "thinkpad p53": ("ThinkPad P53", "Lenovo", "marca corporativa al iq1"),
}


def _usable_subject(text: str) -> bool:
    """A subject must still name something after the brand is stripped."""
    t = (text or "").strip()
    if len(t) < 4:
        return False
    words = t.split()
    if all(w[0].isdigit() or not any(c.isalpha() for c in w) for w in words):
        return False
    return True


@dataclass
class Change:
    session_id: str
    profile: str
    old: str
    new: str
    reason: str


def parse(title: str) -> dict | None:
    m = TITLE_RE.match((title or "").strip())
    return m.groupdict() if m else None


def fix(parts: dict) -> tuple[dict, str] | None:
    subject = (parts["subject"] or "").strip()
    iq1 = (parts["iq1"] or "").strip()
    iq2 = (parts["iq2"] or "").strip()
    low = subject.lower()
    reasons: list[str] = []

    if low in OVERRIDES:
        new_subject, new_iq1, note = OVERRIDES[low]
        subject, iq1 = new_subject, new_iq1
        reasons.append(f"override: {note}")
    else:
        # R2 — a trailing numeric spec leaves the subject
        if SPEC_RE.search(subject) and not SPEC_IS_THE_SUBJECT.match(subject):
            subject = SPEC_RE.sub("", subject).strip()
            reasons.append("spec a la descripción")

        # R1 / R4 — brand in the subject
        for brand, (maker, strip) in sorted(BRANDS.items(), key=lambda kv: -len(kv[0])):
            if low.startswith(brand):
                if strip:
                    rest = subject[len(brand):].strip(" -\u2013\u2014:,")
                    # Never leave a subject that stops meaning anything: "Bot"
                    # or "3.8 27B" is worse than repeating the brand.
                    if _usable_subject(rest):
                        subject = rest
                        reasons.append(f"marca {brand.title()} fuera del sujeto")
                if iq1.lower() != maker.lower():
                    iq1 = maker
                    reasons.append(f"iq1 -> {maker}")
                break

        # R3 — subject equals iq1
        if subject and iq1 and subject.strip().lower() == iq1.strip().lower():
            maker = BRANDS.get(subject.lower(), (None, False))[0]
            if maker and maker.lower() != subject.lower():
                iq1 = maker
                reasons.append(f"iq1 -> {maker} (no repetir el sujeto)")
            else:
                reasons.append("sujeto == iq1: requiere revisión")

    if not reasons:
        return None
    return (
        {
            "subject": subject,
            "mmm": int(parts["mmm"]),
            "iq1": iq1,
            "iq2": iq2,
            "date": parts["date"] or "",
            "desc": (parts["desc"] or "").strip(),
            "verb": (parts["verb"] or "").strip(),
        },
        "; ".join(dict.fromkeys(reasons)),
    )


def build_title(nnn: str, p: dict) -> str:
    f = Facets(
        subject=p["subject"],
        subject_ordinal=p["mmm"],
        iq1=p["iq1"],
        iq2=p["iq2"],
        description=p["desc"],
        verb=p["verb"],
    )
    return render(int(nnn), f, p["date"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    changes: list[Change] = []
    for profile, path in discover_databases():
        from adapters.hermes import read_sessions  # local import: same module

        for rec in read_sessions(profile, path):
            title = (rec.title or "").strip()
            parts = parse(title)
            if not parts:
                continue
            fixed = fix(parts)
            if not fixed:
                continue
            p, reason = fixed
            new = build_title(parts["nnn"], p)
            if new != title:
                changes.append(Change(rec.id, profile, title, new, reason))

    if args.limit:
        changes = changes[: args.limit]

    print(f"cambios propuestos: {len(changes)}\n")
    by_reason: dict[str, int] = {}
    for c in changes:
        by_reason[c.reason.split(";")[0]] = by_reason.get(c.reason.split(";")[0], 0) + 1
    for r, n in sorted(by_reason.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  {r}")

    print("\nmuestra:")
    for c in changes[:12]:
        print(f"\n  [{c.profile}] {c.reason}")
        print(f"    - {c.old}")
        print(f"    + {c.new}")

    # ---- safety checks -------------------------------------------------
    import collections

    longs = [c for c in changes if len(c.new) > 100]
    print(f"\nchequeos: >100 chars = {len(longs)}")
    for c in longs[:3]:
        print(f"   {len(c.new)}  {c.new[:100]}")

    final: dict[str, str] = {}
    for profile, path in discover_databases():
        from adapters.hermes import read_sessions  # local import
        for rec in read_sessions(profile, path):
            final[rec.id] = (rec.title or "").strip()
    for c in changes:
        final[c.session_id] = c.new
    antes = collections.Counter(
        (r.title or "").strip()
        for profile, path in discover_databases()
        for r in __import__("adapters.hermes", fromlist=["read_sessions"]).read_sessions(profile, path)
    )
    # A duplicate that already existed (canonical "Bot Chat", empty titles) is
    # not ours to fix here; only a NEW collision blocks the run.
    dups = [t for t, n in collections.Counter(final.values()).items() if n > 1 and antes.get(t, 0) <= 1]
    print(f"chequeos: titulos duplicados nuevos = {len(dups)}")
    for t in dups[:3]:
        print(f"   {t[:90]}")
    mmm = [c for c in changes if c.old.split("]")[0].rsplit(" ", 1)[-1] != c.new.split("]")[0].rsplit(" ", 1)[-1]]
    print(f"chequeos: MMM alterado = {len(mmm)}")

    if longs or dups:
        print("\nABORTADO: hay titulos invalidos. Nada escrito.")
        return 1

    if not args.apply:
        print("\n(dry-run: nada escrito. Usa --apply tras revisar.)")
        return 0

    dest = Path("/Volumes/1TB_HD/Backups-the assistant")
    print("\nbackup…")
    bdir = backup_databases(dest, "pre-brand-rules") if dest.exists() else None
    print(f"  {bdir}" if bdir else "  (sin destino de backup — abortado)")
    if not bdir:
        return 1

    writer = HermesTitleWriter()
    report = writer.rename_batch([(c.session_id, c.new) for c in changes])
    print(f"\n{report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
