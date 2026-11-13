#!/usr/bin/env python3
"""Cuando el título no alcanza para saber qué fue la sesión, se lee la sesión.

Principio elemental, y es del dueño: si los campos no están en el título, hay que leer la
sesión hasta encontrar lo que se busca. No inventar, no dejar el campo vacío, no reconstruir a
ciegas: leer.

De dónde lee: `messages` en state.db. Primero lo que el usuario pidió (los mensajes del usuario
son la intención declarada); después lo que se hizo, si hace falta contexto.

Uso:

    from core.session_reader import textos_sesion, inferir_intencion, inferir_programa
    textos = textos_sesion(session_id)
    iq3 = inferir_intencion(textos)      # una de las siete canónicas, o None
    iq1 = inferir_programa(textos)       # programa o marca encontrada

Ninguna de estas funciones inventa: si no encuentra evidencia, devuelve None y lo dice.
"""
from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path

import yaml

HOME = Path.home()
STATE = HOME / ".hermes/state.db"
REPO = Path(__file__).resolve().parent.parent

# Cuánto texto se lee por sesión: suficiente para encontrar la intención, sin arrastrar la base.
MAX_MENSAJES = 14
MAX_CHARS = 6000


@lru_cache(maxsize=1)
def _intenciones() -> dict[str, tuple[str, ...]]:
    """Las siete canónicas con sus señales, del catálogo, no de la memoria del script."""
    from core.taxonomy import INTENTIONS, _INTENT_ALIASES  # noqa: PLC0415
    señales: dict[str, set[str]] = {i: set() for i in INTENTIONS}
    for alias, destino in _INTENT_ALIASES.items():
        if destino in señales:
            señales[destino].add(alias.lower())
    return {k: tuple(sorted(v)) for k, v in señales.items()}


@lru_cache(maxsize=1)
def _programas() -> tuple[str, ...]:
    """Programas y marcas del cheat sheet, en minúsculas."""
    try:
        d = yaml.safe_load((REPO / "core/cheat_sheet.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return ()
    nombres = list((d.get("programas") or {})) + list((d.get("marcas") or {}))
    return tuple(sorted({str(n).lower() for n in nombres}))


def textos_sesion(session_id: str, max_mensajes: int = MAX_MENSAJES) -> list[tuple[str, str]]:
    """Los mensajes de la sesión, del usuario primero. [(rol, texto)] — '' si no hay nada."""
    if not STATE.exists():
        return []
    con = sqlite3.connect(f"file:{STATE}?mode=ro", uri=True)
    try:
        filas = con.execute(
            "select role, content from messages where session_id = ? "
            "and role in ('user','assistant') and content is not null and length(content) > 0 "
            "order by timestamp asc limit ?",
            (session_id, max_mensajes),
        ).fetchall()
    finally:
        con.close()
    fuera, total = [], 0
    for rol, texto in filas:
        t = re.sub(r"\s+", " ", str(texto)).strip()
        if not t:
            continue
        t = t[:1200]
        fuera.append((rol, t))
        total += len(t)
        if total > MAX_CHARS:
            break
    # el usuario primero: es la intención declarada, no la respuesta del asistente
    fuera.sort(key=lambda x: 0 if x[0] == "user" else 1)
    return fuera


def _texto(textos: list[tuple[str, str]], solo_usuario: bool = False) -> str:
    return " ".join(t for r, t in textos if (r == "user" or not solo_usuario)).lower()


def inferir_intencion(textos: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    """(intención canónica, la frase que lo prueba). Se busca en el usuario y, si no hay, en todo.

    Si ninguna señal aparece, devuelve (None, None): no se inventa una intención.
    """
    if not textos:
        return None, None
    # Primero el pedido real: el primer mensaje del usuario, sin los tramos entre acentos graves
    # (los backticks suelen citar vocabulario del propio plugin y dan falsos positivos).
    primero = next((t for r, t in textos if r == "user"), "")
    limpio = re.sub(r"`[^`]*`", " ", primero)[:600].lower()
    for ambito, cuerpo in ((True, limpio), (True, _texto(textos, solo_usuario=True)), (False, _texto(textos))):
        if not cuerpo:
            continue
        for intencion, señales in _intenciones().items():
            for señal in señales:
                if len(señal) < 3:
                    continue
                m = re.search(r"(?<![\w])" + re.escape(señal) + r"(?![\w])", cuerpo)
                if m:
                    ini = max(0, m.start() - 40)
                    return intencion, cuerpo[ini:m.end() + 40].strip()
    return None, None


def inferir_programa(textos: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    """(programa o marca, la frase que lo prueba), buscando primero en lo que pidió el usuario."""
    if not textos:
        return None, None
    # Primero el pedido real: el primer mensaje del usuario, sin los tramos entre acentos graves
    # (los backticks suelen citar vocabulario del propio plugin y dan falsos positivos).
    primero = next((t for r, t in textos if r == "user"), "")
    limpio = re.sub(r"`[^`]*`", " ", primero)[:600].lower()
    for ambito, cuerpo in ((True, limpio), (True, _texto(textos, solo_usuario=True)), (False, _texto(textos))):
        if not cuerpo:
            continue
        for nombre in _programas():
            if len(nombre) < 3:
                continue
            m = re.search(r"(?<![\w])" + re.escape(nombre) + r"(?![\w])", cuerpo)
            if m:
                ini = max(0, m.start() - 40)
                return nombre[:1].upper() + nombre[1:], cuerpo[ini:m.end() + 40].strip()
    return None, None


def evidencia(session_id: str) -> dict:
    """Todo lo que la sesión puede decir sobre sí misma, con la prueba de cada campo."""
    textos = textos_sesion(session_id)
    iq3, prueba3 = inferir_intencion(textos)
    iq1, prueba1 = inferir_programa(textos)
    return {
        "leidos": len(textos),
        "iq3": iq3, "iq3_evidencia": prueba3,
        "iq1": iq1, "iq1_evidencia": prueba1,
        "primer_prompt": next((t for r, t in textos if r == "user"), ""),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(0)
    d = evidencia(sys.argv[1])
    print(f"  mensajes leídos: {d['leidos']}")
    print(f"  iq3: {d['iq3']}   ← {d['iq3_evidencia']}")
    print(f"  iq1: {d['iq1']}   ← {d['iq1_evidencia']}")
