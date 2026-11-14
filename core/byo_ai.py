#!/usr/bin/env python3
"""Bring Your Own AI: el plugin usa su propio motor y su propia clave.

Hermes tiene una vía oficial para esto —`ctx.llm` con `auxiliary.<task>`— donde el host resuelve
la credencial y el plugin nunca ve el token. Esta pieza es el complemento para cuando el dueño
quiere una clave **separada y propia** del plugin, guardada en su carpeta de datos y no en el
`.env` del agente: así el gasto del housekeeping no se mezcla con el del asistente y se puede
cambiar de motor sin tocar la configuración de Hermes.

Configuración: `~/.hermes/plugin-data/make-it-smart/byo-ai.json`, permisos 600.

    from core.byo_ai import configurado, completar, probar
    if configurado():  frase = completar("...")

Reglas que se respetan acá:
  · la clave nunca se imprime ni se devuelve completa desde la UI;
  · el archivo se escribe con permisos 600;
  · si no hay configuración, `completar` levanta una excepción clara en vez de caer a otro motor
    en silencio — el housekeeping no debe gastar en el motor del agente sin que el dueño lo sepa;
  · el texto de la sesión se redacta antes de salir (ver `redactar`).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
RUTA = HOME / ".hermes/plugin-data/make-it-smart/byo-ai.json"

# Motores conocidos: base_url y modelo por defecto. `custom` acepta cualquier endpoint
# compatible con OpenAI (Ollama, vLLM, LM Studio, un proxy propio).
MOTORES = {
    "deepseek": {"base_url": "https://api.deepseek.com", "modelo": "deepseek-flash"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "modelo": "deepseek/deepseek-v4-flash"},
    "kimi": {"base_url": "https://api.moonshot.ai/v1", "modelo": "kimi-k2-0905-preview"},
    "google": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "modelo": "gemini-2.5-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "modelo": "gpt-4.1-mini"},
    "custom": {"base_url": "", "modelo": ""},
}


def _leer() -> dict:
    if not RUTA.exists():
        return {}
    try:
        return json.loads(RUTA.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def guardar(cfg: dict) -> dict:
    """Guarda la configuración con permisos 600. Devuelve lo guardado, con la clave enmascarada."""
    limpio = {
        "motor": str(cfg.get("motor") or "custom").strip().lower(),
        "modelo": str(cfg.get("modelo") or "").strip(),
        "base_url": str(cfg.get("base_url") or "").strip().rstrip("/"),
        "api_key": str(cfg.get("api_key") or "").strip(),
        "max_tokens": int(cfg.get("max_tokens") or 120),
        "timeout": int(cfg.get("timeout") or 60),
        "actualizado": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    base = MOTORES.get(limpio["motor"], {})
    if not limpio["base_url"]:
        limpio["base_url"] = base.get("base_url", "")
    if not limpio["modelo"]:
        limpio["modelo"] = base.get("modelo", "")
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUTA.with_suffix(".tmp")
    tmp.write_text(json.dumps(limpio, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(RUTA)
    return enmascarar(limpio)


def enmascarar(cfg: dict) -> dict:
    """Lo que la UI puede ver: la clave nunca completa."""
    c = dict(cfg or {})
    k = str(c.get("api_key") or "")
    c["api_key"] = ("•" * max(len(k) - 4, 0) + k[-4:]) if len(k) > 4 else ("•" * len(k))
    c["tiene_key"] = bool(k)
    return c


def configurado() -> bool:
    c = _leer()
    return bool(c.get("api_key") and c.get("modelo") and c.get("base_url"))


def redactar(texto: str) -> str:
    """Enmascara lo que no debe salir de la máquina antes de mandar texto a un modelo.

    Usa el redactor de Hermes si está disponible (API pública de plugins); si no, aplica un
    conjunto mínimo propio. Nunca se manda el texto crudo sin pasar por acá.
    """
    try:
        from agent.redact import redact_sensitive_text  # type: ignore
        return redact_sensitive_text(texto, force=True)
    except Exception:
        patrones = [
            r"(?i)(api[_-]?key|token|password|secret|contrase[ñn]a)\s*[:=]\s*\S+",
            r"\bsk-[A-Za-z0-9_\-]{12,}\b",
            r"\b[A-Za-z0-9_\-]{32,}\b",
            r"[\w.+-]+@[\w-]+\.[\w.]+",
        ]
        fuera = texto
        for p in patrones:
            fuera = re.sub(p, "[REDACTED]", fuera)
        return fuera


def probar(cfg: dict | None = None) -> tuple[bool, str]:
    """Una llamada mínima para verificar motor, modelo y clave. Devuelve (ok, mensaje)."""
    c = cfg or _leer()
    if not (c.get("api_key") and c.get("modelo") and c.get("base_url")):
        return False, "faltan datos: motor, modelo, base_url y api_key"
    try:
        r = _post(c, [{"role": "user", "content": "Respondé solo: OK"}], max_tokens=8)
    except Exception as e:  # noqa: BLE001
        return False, f"error: {e}"
    return True, f"respuesta: {r[:40]!r}"


def completar(prompt: str, sistema: str = "", max_tokens: int | None = None) -> str:
    """Una llamada al motor del plugin. Sin configuración, falla con un mensaje claro."""
    c = _leer()
    if not configurado():
        raise RuntimeError(
            "BYO AI no está configurado: abrí la pestaña 5 · BYO AI en el panel y cargá motor, "
            "modelo y api_key. El housekeeping no usa el motor del agente sin permiso."
        )
    mensajes = []
    if sistema:
        mensajes.append({"role": "system", "content": sistema})
    mensajes.append({"role": "user", "content": redactar(prompt)})
    return _post(c, mensajes, max_tokens=max_tokens or c.get("max_tokens") or 120)


def _post(c: dict, mensajes: list[dict], max_tokens: int = 120, reintentos: int = 2) -> str:
    cuerpo = json.dumps({
        "model": c["modelo"],
        "messages": mensajes,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{c['base_url'].rstrip('/')}/chat/completions",
        data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {c['api_key']}"},
        method="POST",
    )
    for intento in range(reintentos + 1):
        try:
            with urllib.request.urlopen(req, timeout=int(c.get("timeout") or 60)) as r:
                d = json.loads(r.read().decode("utf-8"))
            return (d["choices"][0]["message"]["content"] or "").strip()
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "ignore")[:160]
            if e.code == 429 and intento < reintentos:
                time.sleep(4 * (intento + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detalle}") from e
        except Exception:
            if intento < reintentos:
                time.sleep(2)
                continue
            raise
    return ""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "estado":
        print(json.dumps(enmascarar(_leer()), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "probar":
        print(probar())
    elif len(sys.argv) > 1 and sys.argv[1] == "modelos":
        c = _leer()
        if not c.get("api_key"):
            print("  falta la api_key: cargala en la pestaña 5 · BYO AI")
            raise SystemExit(2)
        req = urllib.request.Request(f"{c['base_url'].rstrip('/')}/models",
                                     headers={"Authorization": f"Bearer {c['api_key']}"})
        try:
            with urllib.request.urlopen(req, timeout=int(c.get("timeout") or 30)) as r:
                d = json.loads(r.read().decode("utf-8"))
            for m in d.get("data", []):
                print("  ", m.get("id"))
        except Exception as e:  # noqa: BLE001
            print(f"  error: {e}")
    else:
        print(__doc__)
