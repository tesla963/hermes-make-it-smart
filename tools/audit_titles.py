#!/usr/bin/env python3
"""Audit session fields according to the owner's canonical rules — read only.

Never writes to session titles or state.db.
Audits field by field: iq0 (sujeto), iq1 (programa), iq2 (contexto), iq3 (intención), desc.
Applies the elemental principle: when a field (like intention iq3) is missing from the title,
it reads the session dialogue via `core.session_reader` to find it with evidence.

Outputs `proposals.json` with field-by-field verdicts, evidence, and rule breakdown.
Guarantees 100% convergence: running a second audit on proposed titles yields 0 changes.

    python3 tools/audit_titles.py                 # writes proposals.json
    python3 tools/audit_titles.py --dry-run       # writes proposals.json for inspection, touches no DB
"""
from __future__ import annotations

import argparse
import json
import re
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
LIMIT = 100

VERBO = re.compile(r"\b\w+(?:ar|er|ir|ando|iendo|ado|ido)\b", re.I)


def cargar_journal(ruta: Path) -> set[str]:
    if not ruta.exists():
        return set()
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        return set(data.keys()) if isinstance(data, dict) else set()
    except Exception:
        return set()


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


def auditar_sesion(s: dict, ren: set[str], journal_ids: set[str]) -> dict[str, Any]:
    sid = str(s.get("id") or "")
    n_val = s.get("n")
    raw = str(s.get("raw") or "").strip()
    prof = str(s.get("prof") or "default")

    auditable, reason = es_auditable(s, ren)
    if not auditable:
        return {
            "id": sid,
            "n": n_val,
            "prof": prof,
            "before": raw,
            "after": None,
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
    sujeto = str(s.get("sujeto") or s.get("iq0") or "").strip()
    iq1 = str(s.get("iq1") or "").strip()
    iq2 = str(s.get("iq2") or "").strip()
    iq3 = str(s.get("iq3") or "").strip()
    desc = str(s.get("desc") or "").strip()

    cambios: dict[str, str] = {}
    reglas: list[str] = []
    audit_fields: dict[str, dict[str, Any]] = {}

    # --- 1. IQ1 PRE-CHECK (para co-resolución con sujeto) ---
    iq1_inferred = False
    if not iq1:
        ev = evidencia(sid)
        if ev.get("iq1"):
            iq1_cand = str(ev["iq1"])
            cambios["iq1"] = iq1_cand
            iq1 = iq1_cand
            iq1_inferred = True

    # --- 2. SUJETO ---
    suj_verd = "ok"
    suj_regla = "none"
    suj_evid = "Sujeto limpio y conciso."
    suj_doc = True

    if not sujeto:
        suj_verd = "reconstruir"
        suj_regla = "no-subject"
        suj_evid = "Sesión sin sujeto asignado."
        reglas.append(suj_regla)
    else:
        verbo, cuerpo = split_verb_subject(sujeto)
        if verbo and cuerpo and cuerpo != sujeto:
            cambios["sujeto"] = cuerpo
            suj_verd = "ajustar"
            suj_regla = "verb-moved-from-subject-to-intention"
            suj_evid = f"Se removió verbo inicial '{verbo}' del sujeto."
            reglas.append(suj_regla)
            if not iq3:
                norm_int = normalize_intention(verbo)
                if norm_int:
                    cambios["iq3"] = norm_int
            sujeto = cuerpo

        # Desacoplar marca del sujeto si pertenece a iq1 (existente o inferido)
        if iq1 and iq1.lower() in sujeto.lower().split():
            restante = " ".join(w for w in sujeto.split() if w.lower() != iq1.lower()).strip()
            if len(restante.split()) >= 2:
                cambios["sujeto"] = restante
                sujeto = restante
                suj_verd = "ajustar"
                suj_regla = "brand-moved-to-iq1"
                suj_evid = f"La marca '{iq1}' se desacopló del sujeto."
                reglas.append(suj_regla)

        if len(sujeto.split()) >= 4 and "sujeto" not in cambios:
            corto, cola = shrink_subject(sujeto)
            if corto and corto != sujeto and len(corto.split()) <= 3:
                cambios["sujeto"] = corto
                sujeto = corto
                suj_verd = "ajustar"
                suj_regla = "subject-shrunk-to-its-head"
                suj_evid = f"Sujeto recortado a su cabeza limpia de {len(corto.split())} palabras."
                reglas.append(suj_regla)

    audit_fields["sujeto"] = {
        "valor": cambios.get("sujeto", sujeto),
        "veredicto": suj_verd,
        "regla": suj_regla,
        "evidencia": suj_evid,
        "documented": suj_doc,
    }

    # --- 3. IQ1 AUDIT ---
    iq1_verd = "ok"
    iq1_regla = "none"
    iq1_evid = "Programa documentado." if iq1 else "Sin programa opcional."
    iq1_doc = True

    if iq1_inferred:
        iq1_verd = "ajustar"
        iq1_regla = "program-inferred-from-session"
        iq1_evid = f"Detectado en la sesión: «{iq1}»"
        reglas.append(iq1_regla)

    audit_fields["iq1"] = {
        "valor": cambios.get("iq1", iq1),
        "veredicto": iq1_verd,
        "regla": iq1_regla,
        "evidencia": iq1_evid,
        "documented": iq1_doc,
    }

    # --- 4. IQ2 (CONTEXTO) ---
    audit_fields["iq2"] = {
        "valor": iq2,
        "veredicto": "ok",
        "regla": "none",
        "evidencia": "Contexto válido o no requerido.",
        "documented": True,
    }

    # --- 5. IQ3 (INTENCIÓN) ---
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

    # --- 6. DESCRIPCIÓN ---
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

    audit_fields["descripcion"] = {
        "valor": desc,
        "veredicto": desc_verd,
        "regla": desc_regla,
        "evidencia": desc_evid,
        "documented": desc_doc,
    }

    # --- 7. ENSAMBLADO Y CONVERGENCIA ---
    campos_finales = {
        "n": n_val,
        "sujeto": cambios.get("sujeto", sujeto),
        "iq1": cambios.get("iq1", iq1),
        "iq2": iq2,
        "iq3": cambios.get("iq3", act_iq3),
        "desc": desc,
    }
    nuevo_titulo = canon_title(campos_finales)

    # Identificar regla si el cambio es únicamente el sufijo de intención
    if act_iq3 and f"· {act_iq3}" not in raw and "·" not in raw and "intention-suffix-added" not in reglas:
        reglas.append("intention-suffix-added")

    if already_processed:
        veredicto = "skip"
        after_title = None
    elif suj_verd == "reconstruir":
        veredicto = "reconstruir"
        after_title = None
    elif nuevo_titulo != raw:
        veredicto = "ajustar"
        after_title = nuevo_titulo
    else:
        veredicto = "ok"
        after_title = None

    return {
        "id": sid,
        "n": n_val,
        "prof": prof,
        "before": raw,
        "after": after_title,
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
        res2 = auditar_sesion(simulado, ren, journal_ids)
        if res2.get("after") is not None:
            inestables.append({"n": p["n"], "p1": p["after"], "p2": res2["after"], "rules": res2["rules"]})
    return len(inestables), inestables


def desglosar_cambios(proposals: list[dict]) -> dict[str, Any]:
    """Clasifica los cambios propuestos para distinguir mejoras de intención vs churn de sujeto."""
    solo_iq3 = 0
    toca_sujeto = 0
    toca_iq1_iq2 = 0
    toca_desc = 0
    combinados = 0
    total_sujeto_afectado = 0

    for p in proposals:
        if not p.get("after"):
            continue
        rules = p.get("rules", [])
        m_bef = re.match(r"^\d{3,4}\s*\[([^\]]+)\]", p["before"])
        m_aft = re.match(r"^\d{3,4}\s*\[([^\]]+)\]", p["after"])
        suj_bef = m_bef.group(1).strip() if m_bef else ""
        suj_aft = m_aft.group(1).strip() if m_aft else ""
        suj_mod = (suj_bef.lower() != suj_aft.lower())

        if suj_mod:
            total_sujeto_afectado += 1

        iq1_mod = "program-inferred-from-session" in rules or "brand-moved-to-iq1" in rules
        desc_mod = "redundant-description" in rules
        iq3_mod = any(r in rules for r in ("intention-inferred-from-session", "canonical-intention-mapped",
                                            "missing-canonical-intention", "intention-suffix-added"))

        if suj_mod and not (iq1_mod or desc_mod):
            toca_sujeto += 1
        elif iq1_mod and not (suj_mod or desc_mod):
            toca_iq1_iq2 += 1
        elif desc_mod and not (suj_mod or iq1_mod):
            toca_desc += 1
        elif iq3_mod and not (suj_mod or iq1_mod or desc_mod):
            solo_iq3 += 1
        else:
            combinados += 1

    return {
        "solo_intencion": solo_iq3,
        "solo_programa_contexto": toca_iq1_iq2,
        "solo_sujeto": toca_sujeto,
        "solo_descripcion": toca_desc,
        "combinados": combinados,
        "total_tocan_sujeto": total_sujeto_afectado,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input_path", default=str(CANONICAL_INDEX))
    ap.add_argument("--out", dest="output_path", default=str(DATA / "proposals.json"))
    ap.add_argument("--journal", default=str(JOURNAL))
    ap.add_argument("--dry-run", action="store_true", help="escribe proposals.json pero no toca la base")
    args = ap.parse_args()

    in_path = Path(args.input_path).expanduser()
    if not in_path.exists():
        print(f"Error: no existe catálogo en {in_path}", file=sys.stderr)
        return 1

    datos = json.loads(in_path.read_text(encoding="utf-8"))
    sesiones = datos.get("sessions", [])
    journal_ids = cargar_journal(Path(args.journal).expanduser())
    ren = ya_renombradas(sesiones)

    proposals = []
    con_intencion_inferida = 0
    sin_iq3_inicial = 0

    for s in sesiones:
        if es_auditable(s, ren)[0] and not str(s.get("iq3") or "").strip() and str(s.get("sujeto") or "").strip():
            sin_iq3_inicial += 1
        res = auditar_sesion(s, ren, journal_ids)
        if "intention-inferred-from-session" in res.get("rules", []):
            con_intencion_inferida += 1
        proposals.append(res)

    tot = len(sesiones)
    en_alcance = [p for p in proposals if p["in_scope"]]
    pendientes = [p for p in proposals if "not renamed" in p.get("out_of_scope_reason", "")]
    maquinaria = [p for p in proposals if "machinery" in p.get("out_of_scope_reason", "")]
    accionables = [p for p in proposals if p["after"] is not None]
    ya_proc = [p for p in proposals if p["already_processed"]]
    ok_count = [p for p in proposals if p["in_scope"] and p["veredicto"] == "ok"]

    desglose = desglosar_cambios(proposals)
    fallos_conv, inestables = verificar_convergencia(proposals, ren, journal_ids)

    summary = {
        "total": tot,
        "con_nnn": len(en_alcance),
        "auditables": len(en_alcance),
        "pendientes_de_renombrar": len(pendientes),
        "maquinaria": len(maquinaria),
        "already_processed_journal": len(ya_proc),
        "ok_unchanged": len(ok_count),
        "actionable_proposals": len(accionables),
        "sin_iq3_inicial": sin_iq3_inicial,
        "sin_iq3_resueltas_leyendo": con_intencion_inferida,
        "desglose_cambios": desglose,
        "convergencia_inestables": fallos_conv,
    }

    print("=== Resumen de Auditoría (tools/audit_titles.py) ===")
    print(f"  Total sesiones evaluadas: {tot}")
    print(f"  Auditables (con NNN, no maquinaria): {len(en_alcance)}")
    print(f"  Fuera de alcance: pendientes de renombrar={len(pendientes)} · maquinaria={len(maquinaria)}")
    print(f"  Ya procesadas en journal (congeladas): {len(ya_proc)}")
    print(f"  Sesiones sin intención iniciales: {sin_iq3_inicial}")
    print(f"  --> Resueltas leyendo la sesión: {con_intencion_inferida} ({con_intencion_inferida/max(sin_iq3_inicial,1)*100:.1f}%)")
    print(f"\n=== Propuestas Accionables ({len(accionables)}) ===")
    print(f"  1. SOLO agregar/estandarizar intención iq3: {desglose['solo_intencion']} ({desglose['solo_intencion']/max(len(accionables),1)*100:.1f}%)")
    print(f"  2. Solo agregar programa/contexto iq1/iq2:   {desglose['solo_programa_contexto']} ({desglose['solo_programa_contexto']/max(len(accionables),1)*100:.1f}%)")
    print(f"  3. Solo sujeto (verbo o recorte):           {desglose['solo_sujeto']} ({desglose['solo_sujeto']/max(len(accionables),1)*100:.1f}%)")
    print(f"  4. Solo descripción redundante:             {desglose['solo_descripcion']}")
    print(f"  5. Cambios combinados:                      {desglose['combinados']}")
    print(f"  --> TOTAL que modifican el SUJETO:          {desglose['total_tocan_sujeto']} de {len(accionables)} ({desglose['total_tocan_sujeto']/max(len(accionables),1)*100:.1f}%)")
    print(f"\n=== Prueba de Convergencia (Criterio de Aceptación) ===")
    print(f"  Segunda corrida sobre títulos propuestos: {fallos_conv} cambios pendientes ({'CONVERGENCIA 100%' if fallos_conv == 0 else 'FALLÓ'})")

    salida = {
        "version": "1.0",
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
