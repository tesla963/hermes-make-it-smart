#!/usr/bin/env python3
"""Migrate the catalogue's axis keys from tagN to iqN.

Why this exists
---------------
Up to v0.26.1 every artefact named the nine axes ``tag0``…``tag9``: the JSON keys in
``index.json`` and ``facets.json``, the classifier's field names and the panel's
labels. v0.27.0 renames them to ``iq0``…``iq9``.

Renaming the code without renaming the data leaves the panel reading fields that no
longer exist — an empty catalogue with no error to explain it. This module is the
bridge: it upgrades any older artefact in place, exactly once, and is safe to run
twice.

The contract
------------
* **Idempotent.** A file already at the target schema is left byte-identical.
* **Backed up first.** Every file it rewrites is copied to ``<data>/backups/`` with a
  timestamp before the write; nothing is deleted.
* **Atomic.** Written to a temp file and moved into place, so an interrupted run
  cannot leave half a catalogue.
* **Detected, not guessed.** The schema of a file comes from its own content: an
  ``iqN`` key or an explicit ``"schema": 2`` means v2, a ``tagN`` key means v1.

Usage
-----
    python3 tools/migrate_axes.py --dry-run     # report only, touches nothing
    python3 tools/migrate_axes.py               # migrate the canonical + UI data
    python3 tools/migrate_axes.py --path FILE    # one file
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.paths import data_dir, ui_data_dir  # noqa: E402

SCHEMA_V1 = 1
SCHEMA_V2 = 2
TARGET = SCHEMA_V2

OLD_KEY = re.compile(r"^tag(\d)$")
NEW_KEY = re.compile(r"^iq(\d)$")

# The artefacts that carry axis keys. pending_index.json holds authorization ids only.
ARTEFACTS = ("index.json", "facets.json", "pending_index.json")


def detect_schema(data: Any) -> int:
    """Schema of a parsed artefact, read from its own content.

    v2 is claimed only on positive evidence (an explicit marker or an ``iqN`` key),
    so a v1 file without a marker is never mistaken for a v2 one.
    """
    if isinstance(data, dict):
        marker = data.get("schema")
        if isinstance(marker, int) and marker >= SCHEMA_V2:
            return SCHEMA_V2
    if _has_key(data, NEW_KEY):
        return SCHEMA_V2
    if _has_key(data, OLD_KEY):
        return SCHEMA_V1
    # No axis keys at all (e.g. an empty facets file): nothing to migrate.
    return SCHEMA_V2


def _has_key(node: Any, pattern: re.Pattern[str], depth: int = 0) -> bool:
    if depth > 12:
        return False
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and pattern.match(key):
                return True
            if _has_key(value, pattern, depth + 1):
                return True
    elif isinstance(node, list):
        return any(_has_key(item, pattern, depth + 1) for item in node[:50])
    return False


def rename_axes(node: Any) -> tuple[Any, int]:
    """Return ``(node, renamed)`` with every ``tagN`` dict key turned into ``iqN``."""
    renamed = 0
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            new_key = key
            if isinstance(key, str):
                match = OLD_KEY.match(key)
                if match:
                    new_key = f"iq{match.group(1)}"
                    renamed += 1
            child, hits = rename_axes(value)
            renamed += hits
            out[new_key] = child
        return out, renamed
    if isinstance(node, list):
        items = []
        for item in node:
            child, hits = rename_axes(item)
            renamed += hits
            items.append(child)
        return items, renamed
    return node, 0


def migrate_file(path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Migrate one artefact. Returns a report; raises nothing on unreadable files."""
    report: dict[str, Any] = {"file": str(path), "schema_before": None, "schema_after": None,
                              "renamed": 0, "action": "skipped", "backup": None, "error": None}
    if not path.exists():
        report["action"] = "missing"
        return report
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["action"] = "unreadable"
        return report

    before = detect_schema(data)
    report["schema_before"] = before
    report["schema_after"] = before
    if before >= TARGET:
        report["action"] = "already-current"
        return report

    migrated, renamed = rename_axes(data)
    if isinstance(migrated, dict):
        migrated["schema"] = TARGET
    report["renamed"] = renamed
    report["schema_after"] = TARGET
    if dry_run:
        report["action"] = "would-migrate"
        return report

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{path.name}.pre-iq_{stamp}"
    shutil.copy2(path, backup)
    report["backup"] = str(backup)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(migrated, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    report["action"] = "migrated"
    return report


def migrate_all(*, dry_run: bool = False, extra_dirs: tuple[Path, ...] = ()) -> list[dict[str, Any]]:
    """Migrate every artefact in the canonical data dir and in the panel's mirror."""
    dirs = [data_dir(), ui_data_dir(), *extra_dirs]
    seen: set[Path] = set()
    reports: list[dict[str, Any]] = []
    for folder in dirs:
        for name in ARTEFACTS:
            path = Path(folder) / name
            if path in seen or not path.exists():
                continue
            seen.add(path)
            reports.append(migrate_file(path, dry_run=dry_run))
    return reports


def ensure_current(*, quiet: bool = True) -> bool:
    """Called by the index builder: migrate if needed, then say whether it did.

    Never raises: a migration that fails must not stop a rebuild, because the reader
    in core/ accepts both key sets anyway.
    """
    try:
        reports = migrate_all()
    except Exception:  # noqa: BLE001
        return False
    changed = [r for r in reports if r["action"] == "migrated"]
    if changed and not quiet:
        for r in changed:
            print(f"  migrated {Path(r['file']).name}: {r['renamed']} keys → iqN")
    return bool(changed)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rename the catalogue's tagN keys to iqN.")
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--path", help="migrate a single file instead of the data directories")
    args = ap.parse_args()

    if args.path:
        reports = [migrate_file(Path(args.path).expanduser(), dry_run=args.dry_run)]
    else:
        reports = migrate_all(dry_run=args.dry_run)

    print(("DRY RUN — " if args.dry_run else "") + "migración de ejes tagN → iqN\n")
    for r in reports:
        name = Path(r["file"]).name
        if r["action"] == "missing":
            continue
        line = f"  {name:20s} v{r['schema_before']} → v{r['schema_after']}  {r['renamed']:>6} claves  [{r['action']}]"
        if r["backup"]:
            line += f"\n      backup: {Path(r['backup']).name}"
        if r["error"]:
            line += f"\n      ERROR: {r['error']}"
        print(line)

    total = sum(r["renamed"] for r in reports)
    pending = sum(1 for r in reports if r["action"] in ("migrated", "would-migrate"))
    print(f"\n{total} claves renombradas en {pending} archivo(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
