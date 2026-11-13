#!/usr/bin/env python3
"""Remove the date from every session title.

The date is a first-class filter in the catalog; repeating it inside the name
costs six of the hundred available characters and mixes identity with
circumstance. This script rewrites each title in the canonical shape without it.

Dry-run by default. `--apply` backs up first and writes through SessionDB.

It is idempotent: running it twice changes nothing the second time.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import (  # noqa: E402
    HermesTitleWriter,
    backup_databases,
    discover_databases,
    read_sessions,
)
from core.normalize import Facets, render  # noqa: E402

DATE_RE = re.compile(r"\s+\d{2}(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b")
SPLIT_RE = re.compile(r"^(?P<head>.*?\])", re.S)


def strip_date(title: str) -> tuple[str, str] | None:
    """Return (new_title, removed_date) or None when there is nothing to do."""
    t = (title or "").strip()
    if not t:
        return None
    head = SPLIT_RE.match(t)
    if not head:
        return None
    prefix = head.group("head")
    rest = t[len(prefix):]
    m = DATE_RE.search(rest[:40])
    if not m:
        return None
    removed = m.group(0).strip()
    new = (prefix + rest[: m.start()] + rest[m.end():]).strip()
    new = re.sub(r"\s{2,}", " ", new)
    return (new, removed) if new != t else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    changes: list[tuple[str, str, str, str]] = []  # id, profile, old, new
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            res = strip_date(rec.title or "")
            if res:
                changes.append((rec.id, profile, (rec.title or "").strip(), res[0]))

    print(f"titulos con fecha: {len(changes)}")

    longs = [c for c in changes if len(c[3]) > 100]
    print(f"chequeos: >100 chars = {len(longs)}")

    final: dict[str, str] = {}
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            final[rec.id] = (rec.title or "").strip()
    for c in changes:
        final[c[0]] = c[3]
    antes = collections.Counter(
        (rec.title or "").strip()
        for profile, path in discover_databases()
        for rec in read_sessions(profile, path)
    )
    dups = [t for t, n in collections.Counter(final.values()).items() if n > 1 and antes.get(t, 0) <= 1]
    print(f"chequeos: duplicados nuevos = {len(dups)}")

    print("\nmuestra:")
    for c in changes[:6]:
        print(f"  - {c[2][:96]}")
        print(f"  + {c[3][:96]}\n")

    if longs or dups:
        print("ABORTADO: titulos invalidos. Nada escrito.")
        return 1

    if not args.apply:
        print("(dry-run: nada escrito. Usa --apply.)")
        return 0

    dest = Path("/Volumes/1TB_HD/Backups-the assistant")
    print("backup…")
    bdir = backup_databases(dest, "pre-no-date")
    print(f"  {bdir}")

    writer = HermesTitleWriter()
    report = writer.rename_batch([(c[0], c[3]) for c in changes])
    print(f"\n{report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
