#!/usr/bin/env python3
"""Apply audit proposals to Hermes session titles — and never touch a session twice.

This script does ONE thing: it writes titles. It does not audit, it does not decide, it does not
invent. It reads what `tools/audit_titles.py` proposed and applies it.

The rule the owner asked for, enforced here: **a session this script already processed is never
touched again.** That is what the journal is for. Once a session id is in the journal, the script
skips it forever, even if a later audit proposes something else for it. To reprocess one on
purpose, remove its id from the journal by hand — the script will not do it.

    python3 tools/rename_sessions.py                 # dry run: what it would do
    python3 tools/rename_sessions.py --apply         # writes, with backup first
    python3 tools/rename_sessions.py --apply --only 967,971

Safety order, and there is no other order:
    1. read proposals         honest failure if the file or the fields are missing
    2. drop already-journaled sessions
    3. verify the live title still matches the proposal's `before`
    4. write the backup        abort if this fails
    5. rename one by one       a failure is counted, never assumed
    6. append to the journal   only what actually changed
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
DATA = HOME / ".hermes/plugin-data/make-it-smart"
BACKUPS = DATA / "backups"
JOURNAL = DATA / "rename-journal.json"
STATE = HOME / ".hermes/state.db"


def stamp() -> str:
    return time.strftime("%Y%m%d_%H%M")


def cargar_propuestas(ruta: Path) -> list[dict]:
    """Tolerante con la forma, estricto con el fondo: sin id/after no hay nada que aplicar."""
    d = json.loads(ruta.read_text(encoding="utf-8"))
    crudos = d.get("changes") or d.get("proposals") or d.get("items") or []
    fuera = []
    for c in crudos:
        ident = c.get("id") or c.get("session_id")
        despues = c.get("after") or c.get("title_after") or c.get("proposed")
        if not ident or not despues:
            continue
        fuera.append({
            "id": str(ident),
            "n": c.get("n"),
            "before": str(c.get("before") or c.get("title_before") or ""),
            "after": str(despues),
            "prof": c.get("prof") or c.get("profile") or "default",
            "rules": c.get("rules") or c.get("rule") or [],
        })
    return fuera


def cargar_journal() -> dict:
    if JOURNAL.exists():
        try:
            return json.loads(JOURNAL.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def titulo_vivo(ident: str) -> str | None:
    if not STATE.exists():
        return None
    con = sqlite3.connect(f"file:{STATE}?mode=ro", uri=True)
    try:
        row = con.execute("select title from sessions where id = ?", (ident,)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def respaldar(plan: list[dict]) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    f = BACKUPS / f"commit-backup-{stamp()}.json"
    payload = {
        "filename": f.name, "ts": int(time.time() * 1000), "committed": False,
        "reverted": False, "origin": "rename_sessions.py", "changedCount": len(plan),
        "entries": [{"id": c["id"], "n": c["n"], "title_before": c["before"],
                     "title_after": c["after"], "prof": c["prof"],
                     "ts": time.strftime("%Y-%m-%dT%H:%M:%S")} for c in plan],
    }
    f.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    # la DB también, por si el desastre es mayor que un título
    if STATE.exists():
        shutil.copy2(STATE, BACKUPS / f"state-{stamp()}.db") if (BACKUPS / f"state-{stamp()}.db").exists() is False else None
    return f


def renombrar(c: dict) -> tuple[bool, str]:
    cmd = ["hermes"]
    if c["prof"] and c["prof"] != "default":
        cmd += ["--profile", c["prof"]]
    cmd += ["sessions", "rename", c["id"], c["after"]]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr or r.stdout).strip().splitlines()[-1][:120] if (r.stderr or r.stdout) else "sin salida"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposals", default=str(DATA / "proposed-index.json"))
    ap.add_argument("--apply", action="store_true", help="escribe de verdad")
    ap.add_argument("--only", default="", help="ids o números separados por coma")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--journal", default=str(JOURNAL), help="journal alterno (para pruebas)")
    args = ap.parse_args()

    ruta = Path(args.proposals).expanduser()
    if not ruta.exists():
        print(f"  no hay propuestas en {ruta}: primero corre el auditor")
        return 2
    propuestas = cargar_propuestas(ruta)
    journal_path = Path(args.journal).expanduser()
    journal = {}
    if journal_path.exists():
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except Exception:
            journal = {}
    solo = {s.strip() for s in args.only.split(",") if s.strip()}

    plan, ya_procesadas, cambio_externo, sin_dato = [], [], [], 0
    for c in propuestas:
        if solo and str(c["n"]) not in solo and c["id"] not in solo:
            continue
        if c["id"] in journal:
            ya_procesadas.append(c)
            continue
        vivo = titulo_vivo(c["id"])
        if vivo is None:
            sin_dato += 1
            continue
        # primero: ¿ya está aplicado? (el panel pudo haberlo hecho antes)
        if vivo.strip() == c["after"].strip():
            sin_dato += 1
            continue
        if c["before"] and vivo.strip() != c["before"].strip():
            # alguien lo cambió afuera: se respeta ese cambio y se informa
            cambio_externo.append({**c, "vivo": vivo})
            continue
        plan.append(c)

    print(f"  propuestas: {len(propuestas)} · a renombrar: {len(plan)}")
    print(f"  ya procesadas por este script (no se tocan): {len(ya_procesadas)}")
    if cambio_externo:
        print(f"  cambiadas fuera de aquí (se respetan y se omiten): {len(cambio_externo)}")
        for c in cambio_externo[:3]:
            print(f"    #{c['n']} el título vivo dice «{c['vivo'][:40]}», la propuesta esperaba «{c['before'][:30]}»")
    if sin_dato:
        print(f"  sin dato o ya iguales: {sin_dato}")
    if args.limit and len(plan) > args.limit:
        plan = plan[: args.limit]
        print(f"  limitado a {args.limit}")

    for c in plan[:12]:
        print(f"    #{c['n']}  {c['before'][:38]:38s} → {c['after'][:50]}")

    if not args.apply:
        print("\n  dry run — nada escrito. Con --apply escribe, y respalda antes.")
        return 0
    if not plan:
        print("  nada que aplicar")
        return 0

    # El respaldo va antes de la primera escritura. Si falla, no se escribe nada.
    try:
        f = respaldar(plan)
        print(f"  respaldo: {f.name}")
    except Exception as e:  # noqa: BLE001
        print(f"  ABORTA: no se pudo respaldar ({e})")
        return 3

    ok, fallos = 0, []
    for c in plan:
        bien, err = renombrar(c)
        if bien:
            ok += 1
            journal[c["id"]] = {
                "n": c["n"], "before": c["before"], "after": c["after"],
                "prof": c["prof"], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "by": "rename_sessions.py",
            }
            journal_path.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            fallos.append({"id": c["id"], "n": c["n"], "error": err})

    print(f"\n  {len(plan)} en el plan · {ok} renombradas · {len(fallos)} fallaron")
    if fallos:
        for f2 in fallos[:5]:
            print(f"    #{f2['n']} falló: {f2['error']}")
        print("  los fallos NO entran al journal: se reintentan la próxima corrida")
    print(f"  journal: {journal_path} ({len(journal)} sesiones procesadas en total)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
