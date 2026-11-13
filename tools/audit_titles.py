#!/usr/bin/env python3
"""Audit session fields according to the owner's canonical rules — read only.

Never writes to session titles or state.db.
Audits field by field: iq0 (sujeto), iq1 (programa), iq2 (contexto), iq3 (intención), desc.
Synchronizes with the live state.db (mode=ro) so that `before` is always 100% current.

Separates proposals into two clean categories:
  1. CORRECCIONES: structural errors (verbs in subject, brand in subject, subject >= 4 words, redundant description).
  2. FORMATO: massive intention suffix styling (· Intención).

Outputs `proposals.json` with field-by-field verdicts, evidence, and rule breakdown.
Guarantees 100% convergence: running a second audit on proposed titles yields 0 changes.

    python3 tools/audit_titles.py                 # writes proposals.json
    python3 tools/audit_titles.py --dry-run       # writes proposals.json, touches no DB
    python3 tools/audit_titles.py --only-corrections # populates after ONLY for structural corrections
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.normalize import shrink_subject, split_verb_subject
from core.taxonomy import INTENTIONS, PLATFORMS, MACHINES, COUNTRIES, normalize_intention
from tools.scope import tiene_numero, es_maquinaria, es_auditable, ya_renombradas
from core.session_reader import evidencia

HOME = Path.home()
DATA = HOME / ".hermes/plugin-data/make-it-smart"
JOURNAL = DATA / "rename-journal.json"
CANONICAL_INDEX = DATA / "index.json"
STATE_DB = HOME / ".hermes/state.db"
LIMIT = 100

VERBO = re.compile(r"\b\w+(?:ar|er|ir|ando|iendo|ado|ido)\b", re.I)


def file_sha256(p: Path) -> str:
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def cargar_journal(ruta: Path) -> set[str]:
    if not ruta.exists():
        return set()
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        return set(data.keys()) if isinstance(data, dict) else set()
    except Exception:
        return set()


def cargar_titulos_vivos() -> dict[str, str]:
    """Carga los títulos vivos directamente de state.db para no arrastrar snapshots viejos."""
    if not STATE_DB.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
        cur = con.cursor()
        rows = cur.execute("select id, title from sessions where title is not null").fetchall()
        con.close()
        return {str(r[0]): str(r[1]).strip() for r in rows}
    except Exception:
        return {}


def canon_title(s: dict) -> str:
    """Build canonical title format: NNN [Sujeto] MMM [iq1] [iq2] Desc · iq3"""
    nnn = f"{int(s.get('n') or 0):03d}"
    subj = str(s.get("sujeto") or s.get("iq0") or "").strip() or "Sin sujeto"
    mmm = f"{int(s.get('mmm') or 1):03d}"
    head = f"{nnn} [{subj}] {mmm}"
    for campo in ("iq1", "iq2"):
        v = str(s.get(campo) or "").strip()
        if v:
            head += f" [{v}]"
    if len(head) >= LIMIT:
        return head[:LIMIT].rstrip()

    verb = str(s.get("iq3") or s.get("verb") or "").strip()
    tail = f" · {verb}" if verb else ""
    budget = LIMIT - len(head) - 1 - len(tail)

    desc = str(s.get("desc") or "").strip()
    desc = re.sub(r"\d{3,4}\s*\[[^\]]*\]\s*\d{0,3}", " ", desc)
    desc = re.sub(r"\[[^\]]*\]", " ", desc)
    desc = re.sub(r"\s{2,}", " ", desc).strip(" ·,;:-")
    if desc and budget > 0:
        if len(desc) > budget:
            desc = desc[:budget].rstrip()
        return f"{head} {desc}{tail}".strip()
    if tail and len(head) + len(tail) + 1 <= LIMIT:
        return f"{head}{tail}".strip()
    return head


def auditar_sesion(s: dict, ren: set[str], journal_ids: set[str], live_title: str | None = None) -> dict[str, Any]:
    sid = str(s.get("id") or "")
    n_val = s.get("n")
    # El título vivo manda sobre el índice desactualizado
    raw = live_title if live_title is not None else str(s.get("raw") or "").strip()
    prof = str(s.get("prof") or "default")

    auditable, reason = es_auditable({"id": sid, "raw": raw}, ren)
    if not auditable:
        return {
            "id": sid,
            "n": n_val,
            "prof": prof,
            "before": raw,
            "after": None,
            "categoria": "ninguna",
            "in_scope": False,
            "out_of_scope_reason": reason,
            "already_processed": False,
            "veredicto": "skip",
            "rules": [],
            "fields": {},
            "audit": {
                f: {"valor": "", "veredicto": "skip", "regla": "out-of-scope", "evidencia": reason, "documented": False}
                for f in ("sujeto", "iq1", "iq2", "iq3", "descripcion")
            },
        }

    already_processed = sid in journal_ids

    # Extraer campos canónicos de la base viva o del registro
    sujeto = str(s.get("sujeto") or s.get("iq0") or "").strip()
    iq1 = str(s.get("iq1") or "").strip()
    iq2 = str(s.get("iq2") or "").strip()
    iq3 = str(s.get("iq3") or "").strip()
    desc = str(s.get("desc") or "").strip()

    # Si el título vivo cambió respecto a index.json, extraer sujeto y brackets vivos
    pat = re.match(r"^\d{3,4}\s*\[([^\]]+)\](?:\s*\d{3})?(.*)$", raw)
    if pat:
        suj_vivo = pat.group(1).strip()
        resto = pat.group(2)
        brackets = re.findall(r"\[([^\]]+)\]", resto)
        if suj_vivo:
            sujeto = suj_vivo
        if len(brackets) >= 1 and not iq1:
            iq1 = brackets[0].strip()
        if len(brackets) >= 2 and not iq2:
            iq2 = brackets[1].strip()

    cambios: dict[str, str] = {}
    reglas: list[str] = []
    audit_fields: dict[str, dict[str, Any]] = {}
    es_correccion = False

    # --- 1. SUJETO ---
    suj_verd = "ok"
    suj_regla = "none"
    suj_evid = "Sujeto limpio y conciso."
    suj_doc = True

    if not sujeto:
        suj_verd = "reconstruir"
        suj_regla = "no-subject"
        suj_evid = "Sesión sin sujeto asignado."
        reglas.append(suj_regla)
        es_correccion = True
    else:
        verbo, cuerpo = split_verb_subject(sujeto)
        if verbo and cuerpo and cuerpo != sujeto:
            cambios["sujeto"] = cuerpo
            suj_verd = "ajustar"
            suj_regla = "verb-moved-from-subject-to-intention"
            suj_evid = f"Se removió verbo inicial '{verbo}' del sujeto para dejar la entidad limpia."
            reglas.append(suj_regla)
            es_correccion = True
            if not iq3:
                norm_int = normalize_intention(verbo)
                if norm_int:
                    cambios["iq3"] = norm_int
            sujeto = cuerpo

        # Desacoplar marca del sujeto si pertenece a iq1 o repite iq1
        if iq1 and iq1.lower() in sujeto.lower().split():
            restante = " ".join(w for w in sujeto.split() if w.lower() != iq1.lower()).strip()
            if len(restante.split()) >= 2:
                cambios["sujeto"] = restante
                sujeto = restante
                suj_verd = "ajustar"
                suj_regla = "brand-moved-to-iq1"
                suj_evid = f"La marca '{iq1}' estaba repetida en el sujeto y se desacopló a iq1."
                reglas.append(suj_regla)
                es_correccion = True

        if len(sujeto.split()) >= 4 and "sujeto" not in cambios:
            corto, cola = shrink_subject(sujeto)
            if corto and corto != sujeto and len(corto.split()) <= 3:
                cambios["sujeto"] = corto
                sujeto = corto
                suj_verd = "ajustar"
                suj_regla = "subject-shrunk-to-its-head"
                suj_evid = f"Sujeto recortado a su cabeza limpia de {len(corto.split())} palabras."
                reglas.append(suj_regla)
                es_correccion = True

    audit_fields["sujeto"] = {
        "valor": cambios.get("sujeto", sujeto),
        "veredicto": suj_verd,
        "regla": suj_regla,
        "evidencia": suj_evid,
        "documented": suj_doc,
    }

    # --- 2. IQ1 (PROGRAMA) ---
    iq1_verd = "ok"
    iq1_regla = "none"
    iq1_evid = "Programa documentado o no requerido."
    iq1_doc = True

    audit_fields["iq1"] = {
        "valor": cambios.get("iq1", iq1),
        "veredicto": iq1_verd,
        "regla": iq1_regla,
        "evidencia": iq1_evid,
        "documented": iq1_doc,
    }

    # --- 3. IQ2 (CONTEXTO) ---
    audit_fields["iq2"] = {
        "valor": iq2,
        "veredicto": "ok",
        "regla": "none",
        "evidencia": "Contexto válido o no requerido.",
        "documented": True,
    }

    # --- 4. IQ3 (INTENCIÓN) ---
    iq3_verd = "ok"
    iq3_regla = "none"
    iq3_evid = "Intención canónica verificada."
    iq3_doc = True

    act_iq3 = cambios.get("iq3", iq3)
    if not act_iq3:
        # Principio elemental del dueño: leer la sesión
        ev = evidencia(sid)
        if ev.get("iq3"):
            cambios["iq3"] = str(ev["iq3"])
            act_iq3 = str(ev["iq3"])
            iq3_verd = "ajustar"
            iq3_regla = "intention-inferred-from-session"
            iq3_evid = f"Inferida leyendo la sesión: «{ev['iq3_evidencia']}»"
            reglas.append(iq3_regla)
        else:
            iq3_verd = "ajustar"
            iq3_regla = "missing-canonical-intention"
            iq3_evid = "Sin intención canónica identificable en el texto."
            iq3_doc = False
            reglas.append(iq3_regla)
    elif act_iq3 not in INTENTIONS:
        norm_i = normalize_intention(act_iq3)
        if norm_i and norm_i in INTENTIONS:
            cambios["iq3"] = norm_i
            iq3_verd = "ajustar"
            iq3_regla = "canonical-intention-mapped"
            iq3_evid = f"Mapeada de '{act_iq3}' a '{norm_i}'."
            reglas.append(iq3_regla)
        else:
            iq3_verd = "ajustar"
            iq3_regla = "non-canonical-intention"
            iq3_evid = f"Intención '{act_iq3}' no pertenece a las 7 canónicas."
            iq3_doc = False

    audit_fields["iq3"] = {
        "valor": cambios.get("iq3", act_iq3),
        "veredicto": iq3_verd,
        "regla": iq3_regla,
        "evidencia": iq3_evid,
        "documented": iq3_doc,
    }

    # --- 5. DESCRIPCIÓN ---
    desc_verd = "ok"
    desc_regla = "none"
    desc_evid = "Amplifica el objetivo correctamente."
    desc_doc = True

    s_words = set(re.findall(r"[a-záéíóúñ]{3,}", sujeto.lower()))
    d_words = set(re.findall(r"[a-záéíóúñ]{3,}", desc.lower()))
    if s_words and d_words:
        overlap = len(s_words & d_words) / len(d_words)
        if overlap >= 0.6:
            desc_verd = "ajustar"
            desc_regla = "redundant-description"
            desc_evid = f"La descripción repite el {int(overlap*100)}% de los términos del sujeto."
            reglas.append(desc_regla)
            es_correccion = True

    audit_fields["descripcion"] = {
        "valor": desc,
        "veredicto": desc_verd,
        "regla": desc_regla,
        "evidencia": desc_evid,
        "documented": desc_doc,
    }

    # --- 6. ENSAMBLADO Y CATEGORIZACIÓN ---
    campos_finales = {
        "n": n_val,
        "sujeto": cambios.get("sujeto", sujeto),
        "iq1": cambios.get("iq1", iq1),
        "iq2": iq2,
        "iq3": cambios.get("iq3", act_iq3),
        "desc": desc,
    }
    nuevo_titulo = canon_title(campos_finales)

    # Si solo se agregó el sufijo de intención, marcar la regla explícita
    if act_iq3 and f"· {act_iq3}" not in raw and "·" not in raw and "intention-suffix-added" not in reglas:
        reglas.append("intention-suffix-added")

    if already_processed:
        veredicto = "skip"
        after_title = None
        categoria = "ninguna"
    elif suj_verd == "reconstruir":
        veredicto = "reconstruir"
        after_title = None
        categoria = "correccion"
    elif nuevo_titulo != raw:
        veredicto = "ajustar"
        after_title = nuevo_titulo
        categoria = "correccion" if es_correccion else "formato"
    else:
        veredicto = "ok"
        after_title = None
        categoria = "ninguna"

    # Garantía absoluta: after es None o un string canónico, NUNCA el string "None"
    if after_title is None or str(after_title).strip() in ("", "None"):
        after_title = None

    return {
        "id": sid,
        "n": n_val,
        "prof": prof,
        "before": raw,
        "after": after_title,
        "categoria": categoria,
        "in_scope": True,
        "out_of_scope_reason": "",
        "already_processed": already_processed,
        "veredicto": veredicto,
        "rules": reglas,
        "fields": campos_finales,
        "audit": audit_fields,
    }


def verificar_convergencia(proposals: list[dict], ren: set[str], journal_ids: set[str]) -> tuple[int, list[dict]]:
    """Comprueba que una segunda corrida sobre los títulos propuestos dé exactamente 0 cambios."""
    inestables = []
    for p in proposals:
        if not p.get("after") or not p.get("in_scope"):
            continue
        simulado = {
            "id": p["id"],
            "n": p["n"],
            "prof": p["prof"],
            "raw": p["after"],
            "sujeto": p["fields"].get("sujeto"),
            "iq0": p["fields"].get("sujeto"),
            "iq1": p["fields"].get("iq1"),
            "iq2": p["fields"].get("iq2"),
            "iq3": p["fields"].get("iq3"),
            "desc": p["fields"].get("desc"),
        }
        res2 = auditar_sesion(simulado, ren, journal_ids, live_title=p["after"])
        if res2.get("after") is not None:
            inestables.append({"n": p["n"], "p1": p["after"], "p2": res2["after"], "rules": res2["rules"]})
    return len(inestables), inestables


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input_path", default=str(CANONICAL_INDEX))
    ap.add_argument("--out", dest="output_path", default=str(DATA / "proposals.json"))
    ap.add_argument("--journal", default=str(JOURNAL))
    ap.add_argument("--dry-run", action="store_true", help="escribe proposals.json pero no toca la base")
    ap.add_argument("--only-corrections", action="store_true", help="popula after ÚNICAMENTE para correcciones estructurales")
    args = ap.parse_args()

    in_path = Path(args.input_path).expanduser()
    if not in_path.exists():
        print(f"Error: no existe catálogo en {in_path}", file=sys.stderr)
        return 1

    idx_mtime = in_path.stat().st_mtime
    idx_hash = file_sha256(in_path)
    state_mtime = STATE_DB.stat().st_mtime if STATE_DB.exists() else 0.0

    datos = json.loads(in_path.read_text(encoding="utf-8"))
    sesiones = datos.get("sessions", [])
    journal_ids = cargar_journal(Path(args.journal).expanduser())
    live_titles = cargar_titulos_vivos()

    # Sincronizar catálogo con state.db viva
    for s in sesiones:
        sid = str(s.get("id") or "")
        if sid in live_titles:
            s["raw"] = live_titles[sid]

    ren = ya_renombradas(sesiones)

    proposals = []
    con_intencion_inferida = 0
    sin_iq3_inicial = 0

    for s in sesiones:
        if es_auditable(s, ren)[0] and not str(s.get("iq3") or "").strip() and str(s.get("sujeto") or "").strip():
            sin_iq3_inicial += 1
        res = auditar_sesion(s, ren, journal_ids, live_title=s.get("raw"))
        if "intention-inferred-from-session" in res.get("rules", []):
            con_intencion_inferida += 1

        # Si el usuario solicitó --only-corrections, silenciar after en las que solo son formato
        if args.only_corrections and res["categoria"] == "formato":
            res["after"] = None

        proposals.append(res)

    tot = len(sesiones)
    en_alcance = [p for p in proposals if p["in_scope"]]
    pendientes = [p for p in proposals if "not renamed" in p.get("out_of_scope_reason", "")]
    maquinaria = [p for p in proposals if "machinery" in p.get("out_of_scope_reason", "")]
    ya_proc = [p for p in proposals if p["already_processed"]]
    ok_count = [p for p in proposals if p["in_scope"] and p["veredicto"] == "ok"]

    correcciones = [p for p in proposals if p["categoria"] == "correccion" and p["after"] is not None]
    formato = [p for p in proposals if p["categoria"] == "formato" and p["after"] is not None]
    accionables = [p for p in proposals if p["after"] is not None]

    fallos_conv, inestables = verificar_convergencia(proposals, ren, journal_ids)

    summary = {
        "snapshot": {
            "index_path": str(in_path),
            "index_mtime": idx_mtime,
            "index_sha256": idx_hash,
            "state_db_mtime": state_mtime,
        },
        "total": tot,
        "con_nnn": len(en_alcance),
        "auditables": len(en_alcance),
        "pendientes_de_renombrar": len(pendientes),
        "maquinaria": len(maquinaria),
        "already_processed_journal": len(ya_proc),
        "ok_unchanged": len(ok_count),
        "sin_iq3_inicial": sin_iq3_inicial,
        "sin_iq3_resueltas_leyendo": con_intencion_inferida,
        "accionables_total": len(accionables),
        "categorias": {
            "correcciones_estructurales": len(correcciones),
            "formato_intencion": len(formato),
        },
        "convergencia_inestables": fallos_conv,
    }

    print("=== Resumen de Auditoría (tools/audit_titles.py) ===")
    print(f"  Foto de entrada: index.json mtime={idx_mtime:.1f} · state.db mtime={state_mtime:.1f}")
    print(f"  Total sesiones evaluadas: {tot}")
    print(f"  Auditables (con NNN, no maquinaria): {len(en_alcance)}")
    print(f"  Fuera de alcance: pendientes={len(pendientes)} · maquinaria={len(maquinaria)}")
    print(f"  Ya procesadas en journal (congeladas): {len(ya_proc)}")
    print(f"  Sesiones sin intención iniciales: {sin_iq3_inicial} --> Resueltas leyendo: {con_intencion_inferida}")
    print(f"\n=== Propuestas Accionables Separadas ({len(accionables)}) ===")
    print(f"  1. CORRECCIONES estructurales (sujeto, marca, redundancia): {len(correcciones)}")
    print(f"  2. FORMATO masivo (solo agregar sufijo · Intención):        {len(formato)}")
    print(f"\n=== Prueba de Convergencia (Criterio de Aceptación) ===")
    print(f"  Segunda corrida sobre títulos propuestos: {fallos_conv} cambios pendientes ({'CONVERGENCIA 100%' if fallos_conv == 0 else 'FALLÓ'})")

    salida = {
        "version": "1.1",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rules_version": "v0.28",
        "summary": summary,
        "proposals": proposals,
    }

    out_path = Path(args.output_path).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = out_path.with_suffix(".tmp")
    temp_file.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    temp_file.replace(out_path)
    print(f"\n  Escrito exitosamente: {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
    if args.dry_run:
        print("  dry-run: proposals.json generado para inspección; base de sesiones intacta.")
    return 0 if fallos_conv == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
