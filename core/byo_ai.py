#!/usr/bin/env python3
"""Bring Your Own AI: el plugin usa su propio motor y su propia clave.

Hermes tiene una vía oficial para esto —`ctx.llm` con `auxiliary.<task>`— donde el host resuelve
la credencial y el plugin nunca ve el token. Esta pieza es el complemento para cuando el dueño
quiere una clave **separada y propia** del plugin: así el gasto del housekeeping no se mezcla con
el del asistente y se puede cambiar de motor sin tocar la configuración de Hermes.

La **clave no vive en un archivo del plugin**. Se declara en `plugin.yaml` como
`config_schema.api_key` de tipo `secret` (variable `MMS_API_KEY`), Hermes la guarda en el `.env`
del perfil y acá se lee con `agent.secret_scope.get_secret`, que respeta el perfil activo cuando el
gateway multiplexa (regla 11 del catálogo). El resto de la configuración —motor, modelo, base URL,
límites y consentimiento— sigue en `~/.hermes/plugin-data/make-it-smart/byo-ai.json`, permisos 600.

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

from core.paths import data_dir, ui_data_dir

# Motores conocidos: base_url y modelo por defecto. `custom` acepta cualquier endpoint
# compatible con OpenAI (Ollama, vLLM, LM Studio, un proxy propio).
MOTORES = {
    "deepseek": {"base_url": "https://api.deepseek.com", "modelo": "deepseek-chat"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "modelo": "deepseek/deepseek-v4-flash"},
    "kimi": {"base_url": "https://api.moonshot.ai/v1", "modelo": "kimi-k2-0905-preview"},
    "google": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "modelo": "gemini-2.5-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "modelo": "gpt-4.1-mini"},
    "custom": {"base_url": "", "modelo": ""},
}


def ruta_config() -> Path:
    """Resuelve la ruta canónica de `byo-ai.json` y migra desde el espejo UI si es más reciente."""
    canon = data_dir() / "byo-ai.json"
    try:
        espejo = ui_data_dir() / "byo-ai.json"
        if espejo.exists() and espejo.resolve() != canon.resolve():
            if not canon.exists() or espejo.stat().st_mtime > canon.stat().st_mtime:
                canon.parent.mkdir(parents=True, exist_ok=True)
                tmp = canon.with_suffix(".tmp")
                tmp.write_text(espejo.read_text(encoding="utf-8"), encoding="utf-8")
                os.chmod(tmp, 0o600)
                tmp.replace(canon)
    except Exception:
        pass
    return canon


def _fuera_de_hermes() -> bool:
    """True solo cuando el módulo corre suelto (CLI, tests) y no hay secret scope que consultar.

    Sirve para decidir si las variables de entorno pueden usarse: dentro de un proceso de Hermes,
    incluso uno que sirve varios perfiles, el entorno es el del perfil de lanzamiento y no el de la
    tarea. Un `os.environ` pelado ahí filtraría la clave de un perfil a otro.
    """
    try:
        import agent.secret_scope  # noqa: F401

        return False
    except Exception:
        return True


def _clave() -> str:
    """La clave del motor, siempre por la ruta oficial de Hermes.

    `get_secret` honra el perfil activo. Si el import existe y el secreto no está, se devuelve vacío:
    **no** se cae al entorno, porque ese entorno es el del proceso y no el de la tarea (regla 11).
    El entorno se usa únicamente cuando el módulo corre fuera de Hermes.
    """
    if _fuera_de_hermes():
        return os.environ.get("MMS_API_KEY", "").strip()
    try:
        from agent.secret_scope import get_secret  # type: ignore

        return (get_secret("MMS_API_KEY") or "").strip()
    except Exception:
        return ""


def _leer() -> dict:
    ruta = ruta_config()
    d: dict = {}
    if ruta.exists():
        try:
            d = json.loads(ruta.read_text(encoding="utf-8")) or {}
        except Exception:
            d = {}
    if not isinstance(d, dict):
        d = {}
    d["allow_send_excerpts"] = bool(d.get("allow_send_excerpts", False))

    # La clave nunca se lee del archivo del plugin: si un JSON viejo la tiene, se ignora.
    d.pop("api_key", None)
    env_key = _clave()
    fuera = _fuera_de_hermes()
    env_url = os.environ.get("MMS_BASE_URL", "").strip().rstrip("/") if fuera else ""
    env_mod = os.environ.get("MMS_MODEL", "").strip() if fuera else ""
    if env_key:
        d["api_key"] = env_key
    if env_url:
        d["base_url"] = env_url
    if env_mod:
        d["modelo"] = env_mod
    if (env_key or env_url or env_mod) and (not d.get("base_url") or not d.get("modelo")):
        motor = str(d.get("motor") or "deepseek").strip().lower()
        base = MOTORES.get(motor, MOTORES["deepseek"])
        if not d.get("base_url"):
            d["base_url"] = base.get("base_url", "")
        if not d.get("modelo"):
            d["modelo"] = base.get("modelo", "")
    return d


def guardar(cfg: dict) -> dict:
    """Guarda la configuración con permisos 600. Devuelve lo guardado, con la clave enmascarada."""
    limpio = {
        "motor": str(cfg.get("motor") or "custom").strip().lower(),
        "modelo": str(cfg.get("modelo") or "").strip(),
        "base_url": str(cfg.get("base_url") or "").strip().rstrip("/"),
        "max_tokens": int(cfg.get("max_tokens") or 120),
        "timeout": int(cfg.get("timeout") or 60),
        "allow_send_excerpts": bool(cfg.get("allow_send_excerpts", False)),
        "actualizado": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    base = MOTORES.get(limpio["motor"], {})
    if not limpio["base_url"]:
        limpio["base_url"] = base.get("base_url", "")
    if not limpio["modelo"]:
        limpio["modelo"] = base.get("modelo", "")
    ruta = data_dir() / "byo-ai.json"
    # Este archivo no guarda credenciales: la clave vive en Hermes (regla 11). Si una copia vieja
    # quedó en disco, el próximo guardado la elimina; el plugin no la lee, no la copia y no la cuida.
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(limpio, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(ruta)
    return enmascarar(limpio)


def enmascarar(cfg: dict) -> dict:
    """Lo que la UI puede ver: la clave nunca completa."""
    c = dict(cfg or {})
    k = _clave()
    c["api_key"] = ("•" * max(len(k) - 4, 0) + k[-4:]) if len(k) > 4 else ("•" * len(k))
    c["tiene_key"] = bool(k)
    c["allow_send_excerpts"] = bool(c.get("allow_send_excerpts", False))
    return c


def configurado() -> bool:
    c = _leer()
    return bool(c.get("api_key") and c.get("modelo") and c.get("base_url"))


def consentimiento_activo() -> bool:
    """Exige consentimiento explícito (`allow_send_excerpts is True`) además de motor, modelo y clave."""
    c = _leer()
    return bool(
        c.get("allow_send_excerpts") is True
        and c.get("api_key")
        and c.get("modelo")
        and c.get("base_url")
    )


def redactar(texto: str) -> str:
    """Enmascara lo que no debe salir de la máquina antes de mandar texto a un modelo.

    Pasa primero por el redactor de Hermes (API pública de plugins) y **después** aplica los
    patrones propios: el de Hermes cubre credenciales pero deja pasar correos y rutas, y el texto
    que sale de acá son extractos de sesiones. Nunca se manda el texto crudo sin pasar por acá.
    """
    fuera = texto
    try:
        from agent.redact import redact_sensitive_text  # type: ignore
        fuera = redact_sensitive_text(texto, force=True)
    except Exception:
        fuera = texto
    patrones = [
        r"(?i)(api[_-]?key|token|password|secret|contrase[ñn]a)\s*[:=]\s*\S+",
        r"\bsk-[A-Za-z0-9_\-]{12,}\b",
        r"\b[A-Za-z0-9_\-]{32,}\b",
        r"[\w.+-]+@[\w-]+\.[\w.]+",
    ]
    for p in patrones:
        fuera = re.sub(p, "[REDACTED]", fuera)
    return fuera


def probar(cfg: dict | None = None) -> tuple[bool, str]:
    """Una llamada mínima para verificar motor, modelo y clave. Devuelve (ok, mensaje)."""
    c = dict(cfg or _leer())
    if not c.get("api_key"):
        c["api_key"] = _clave()
    if not (c.get("api_key") and c.get("modelo") and c.get("base_url")):
        return False, "faltan datos: motor, modelo, base_url y api_key"
    try:
        r = _post(c, [{"role": "user", "content": "Respondé solo: OK"}], max_tokens=8)
    except Exception as e:  # noqa: BLE001
        return False, f"error: {e}"
    return True, f"respuesta: {r[:40]!r}"


def completar(prompt: str, sistema: str = "", max_tokens: int | None = None) -> str:
    """Una llamada al motor del plugin. Sin configuración o sin consentimiento, falla con un mensaje claro."""
    c = _leer()
    if not consentimiento_activo():
        raise RuntimeError(
            "BYO AI no está activo: cargá motor, modelo y base URL en la pestaña 5 · BYO AI, "
            "poné la API key en Plugins → Ajustes (campo BYO AI API key) y activá el "
            "consentimiento para enviar extractos redactados."
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
            print("  falta la api_key: configurala en Plugins → Ajustes (BYO AI API key), "
                  "variable MMS_API_KEY")
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
