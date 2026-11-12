"""The tagN → iqN migration must be lossless, idempotent and reversible.

Run with:  python3 tests/test_migrate_axes.py
           or: python3 -m pytest tests/ -q
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from migrate_axes import (  # noqa: E402
    SCHEMA_V1,
    SCHEMA_V2,
    detect_schema,
    migrate_file,
    rename_axes,
)

failures = 0


def ok(cond: bool, msg: str) -> None:
    global failures
    print(f"  {'ok  ' if cond else 'FAIL'} {msg}")
    if not cond:
        failures += 1


# --------------------------------------------------------------------------- #
# Pure mapping
# --------------------------------------------------------------------------- #

print("\n§ detección de esquema")
ok(detect_schema({"sessions": [{"tag1": "Apple"}]}) == SCHEMA_V1, "un tagN sin marcador es v1")
ok(detect_schema({"schema": 2, "sessions": []}) == SCHEMA_V2, "el marcador schema:2 es v2")
ok(detect_schema({"sessions": [{"iq1": "Apple"}]}) == SCHEMA_V2, "un iqN es v2")
ok(detect_schema({"facets": {}}) == SCHEMA_V2, "sin ejes no hay nada que migrar")

print("\n§ renombrado")
migrated, hits = rename_axes({"sessions": [{"tag0": "A", "tag1": "B", "id": "x"}], "facets": {"tag3": {"v": 1}}})
ok(hits == 3, f"cuenta las claves renombradas ({hits})")
ok(migrated["sessions"][0] == {"iq0": "A", "iq1": "B", "id": "x"}, "renombra dentro de listas de sesiones")
ok(migrated["facets"] == {"iq3": {"v": 1}}, "renombra dentro de objetos anidados")
ok("tag0" not in json.dumps(migrated), "no queda ningún tagN")

print("\n§ los valores no se tocan")
source = {"sessions": [{"tag1": "Apple", "sujeto": "Mac mini M4", "desc": "tag1 aparece en el texto"}]}
out, _ = rename_axes(source)
ok(out["sessions"][0]["sujeto"] == "Mac mini M4", "el sujeto sobrevive")
ok(out["sessions"][0]["desc"] == "tag1 aparece en el texto", "un tagN dentro de un VALOR no se toca")

# --------------------------------------------------------------------------- #
# File level: backup, marker, idempotency
# --------------------------------------------------------------------------- #

print("\n§ migración de archivo")
tmp = Path(tempfile.mkdtemp(prefix="mig-test-"))
try:
    target = tmp / "index.json"
    original = {
        "generated": "2026-11-12T00:00:00",
        "count": 2,
        "sessions": [
            {"id": "a", "tag0": "Sujeto", "tag1": "Apple", "tag3": "Investigar"},
            {"id": "b", "tag0": "Otro", "tag1": "", "tag3": ""},
        ],
    }
    target.write_text(json.dumps(original), encoding="utf-8")

    report = migrate_file(target)
    after = json.loads(target.read_text())

    ok(report["action"] == "migrated", "reporta que migró")
    ok(report["renamed"] == 6, f"renombró 6 claves ({report['renamed']})")
    ok(after["schema"] == SCHEMA_V2, "deja el marcador schema:2")
    ok(after["count"] == 2 and len(after["sessions"]) == 2, "no pierde sesiones")
    ok(after["sessions"][0]["iq1"] == "Apple", "conserva los valores")
    ok(report["backup"] and Path(report["backup"]).exists(), "escribe el backup antes de tocar el archivo")
    ok(json.loads(Path(report["backup"]).read_text()) == original, "el backup es el archivo original exacto")

    again = migrate_file(target)
    ok(again["action"] == "already-current", "la segunda pasada no hace nada")
    ok(json.loads(target.read_text()) == after, "y el archivo queda byte-idéntico")

    dry = migrate_file(Path(report["backup"]), dry_run=True)
    ok(dry["action"] == "would-migrate" and dry["renamed"] == 6, "el dry-run informa sin escribir")
    ok(json.loads(Path(report["backup"]).read_text()) == original, "el dry-run no modifica el archivo")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if failures:
    print(f"{failures} FALLOS")
    raise SystemExit(1)
print("TODO OK")
