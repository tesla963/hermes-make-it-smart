#!/usr/bin/env python3
"""La API key de BYO AI no puede volver a un archivo del plugin (regla 11 del catálogo).

Comprueba tres cosas, de fuera hacia dentro:

  1. `plugin.yaml` declara el secreto como `config_schema.api_key` de tipo `secret`, apuntando a
     `MMS_API_KEY`, que es el nombre que el código lee.
  2. `guardar()` escribe la configuración **sin** `api_key`, aunque se la pasen.
  3. `_clave()` la resuelve por `agent.secret_scope.get_secret` —la ruta de Hermes, que respeta el
     perfil activo— y no leyendo el `.env` a mano.

Se corre con: run-in-hermes-env python3 tests/test_secret_scope.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

fallos: list[str] = []
oks = 0


def ok(cond: bool, texto: str) -> None:
    global oks
    if cond:
        oks += 1
        print(f"  ok   {texto}")
    else:
        fallos.append(texto)
        print(f"  FALLA {texto}")


def main() -> int:
    # Un directorio propio: nunca toca los datos del dueño.
    tmp = tempfile.mkdtemp(prefix="mms-test-secret-")
    os.environ["HERMES_PLUGIN_DATA"] = tmp
    os.environ.pop("MMS_API_KEY", None)

    # Hermes sirviendo el secreto, como en producción.
    falso = types.ModuleType("agent.secret_scope")
    setattr(falso, "get_secret", lambda n: "sk-desde-hermes-123456" if n == "MMS_API_KEY" else None)
    sys.modules["agent.secret_scope"] = falso
    mod_agent = types.ModuleType("agent")
    setattr(mod_agent, "secret_scope", falso)
    sys.modules.setdefault("agent", mod_agent)

    from core import byo_ai as b

    # 1. manifiesto
    yaml_txt = (RAIZ / "plugin.yaml").read_text(encoding="utf-8")
    ok("config_schema:" in yaml_txt, "plugin.yaml declara config_schema")
    ok("type: secret" in yaml_txt, "el campo es de tipo secret")
    ok("env: MMS_API_KEY" in yaml_txt, "apunta a MMS_API_KEY, la variable que el código lee")

    # 2. guardar no persiste el secreto
    ruta = Path(tmp) / "byo-ai.json"
    ruta.write_text(
        json.dumps(
            {
                "motor": "deepseek",
                "modelo": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-vieja-en-disco",
                "allow_send_excerpts": True,
            }
        ),
        encoding="utf-8",
    )
    # 2. guardar no guarda credenciales: deja el archivo limpio, venga de donde venga la clave
    b.guardar({"motor": "deepseek", "api_key": "sk-intento-de-guardar", "allow_send_excerpts": True})
    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    ok("api_key" not in guardado, "guardar() deja el archivo sin api_key")
    ok("sk-vieja-en-disco" not in ruta.read_text(encoding="utf-8"),
       "la copia vieja que hubiera en disco desaparece")
    ok("sk-intento-de-guardar" not in ruta.read_text(encoding="utf-8"),
       "la clave que llegue del panel tampoco se escribe")
    ok(not hasattr(b, "migracion_pendiente"),
       "el plugin ya no tiene noción de claves viejas: esa función no existe")

    # 3. la clave sale de Hermes
    ok(b._clave() == "sk-desde-hermes-123456", "_clave() usa get_secret")
    cfg = b._leer()
    ok(cfg.get("api_key") == "sk-desde-hermes-123456", "_leer() inyecta la clave de Hermes")
    ok(cfg.get("allow_send_excerpts") is True, "el resto de la configuración se conserva")
    ok(b.configurado() is True, "configurado() con motor, modelo, base y clave")
    m = b.enmascarar(cfg)
    ok(m["api_key"].endswith("3456") and m["api_key"].count("•") > 0, "enmascarar() muestra solo los últimos 4")

    # 4. sin el secreto en Hermes, no hay clave — y el entorno NO la sustituye
    setattr(falso, "get_secret", lambda n: None)
    ok(b._clave() == "", "sin secreto en Hermes, _clave() devuelve vacío")
    os.environ["MMS_API_KEY"] = "sk-del-entorno-que-no-debe-ganar"
    os.environ["MMS_BASE_URL"] = "https://entorno.example"
    ok(b._clave() == "", "dentro de Hermes el entorno NO sustituye al secreto (regla 11)")
    cfg2 = b._leer()
    ok(not cfg2.get("api_key"), "_leer() no toma la clave del entorno")
    ok(cfg2.get("base_url") != "https://entorno.example", "_leer() no toma la base URL del entorno")

    # 5. fuera de Hermes (script suelto) el entorno es la única fuente
    original = b._fuera_de_hermes
    setattr(b, "_fuera_de_hermes", lambda: True)
    ok(b._clave() == "sk-del-entorno-que-no-debe-ganar", "standalone: el entorno sí se usa")
    ok(b._leer().get("base_url") == "https://entorno.example", "standalone: la base URL del entorno sí se usa")
    setattr(b, "_fuera_de_hermes", original)
    os.environ.pop("MMS_API_KEY", None)
    os.environ.pop("MMS_BASE_URL", None)
    ok("sk-vieja-en-disco" not in json.dumps(b.enmascarar(b._leer())), "nunca reaparece la clave vieja del archivo")

    # 6. hermes_root(): un HERMES_HOME que apunta a un perfil no puede limitar el índice
    from core import paths as cp

    perfil = Path(tmp) / "profiles" / "lisa"
    perfil.mkdir(parents=True, exist_ok=True)
    anterior = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(perfil)
    ok(cp.hermes_root().name != "lisa", "hermes_root() no se queda en el directorio del perfil")
    if anterior is None:
        os.environ.pop("HERMES_HOME", None)
    else:
        os.environ["HERMES_HOME"] = anterior

    print(f"\n{oks}/{oks + len(fallos)} comprobaciones · {'TODO OK' if not fallos else 'FALLOS: ' + '; '.join(fallos)}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    raise SystemExit(main())
