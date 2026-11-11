# Data Paths & Storage Architecture

> Documento de referencia para **agentes autónomos de Hermes**. Define las raíces de almacenamiento, los archivos de estado, las responsabilidades de escritura y el protocolo de verificación.

---

## 1. Raíces de almacenamiento

| Raíz | Ruta absoluta (macOS) | Contenido | Quién escribe | Quién lee |
|---|---|---|---|---|
| **Canónica (Herramientas / Python)** | `~/.hermes/plugin-data/make-it-smart/` | `index.json`, `facets.json`, `pending_index.json`, `data.db`, `corrections.yaml`, `bateria.personal.yaml`, `backups/`, `exports/` | `tools/cellar_tools.py`, `tools/build_index.py` | Herramientas cellar, clasificadores Python |
| **Espejo UI (Desktop)** | `~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/` | `index.json`, `facets.json`, `pending_index.json` | Pipeline automático (`build_index.py`, `cellar_index op=rebuild`) | `desktop/plugin.js` vía `ctx.files.readText('data', ...)` |
| **Código del Plugin** | `~/.hermes/desktop-plugins/make-it-smart/` | `plugin.js` | Instalador / despliegue | Host Hermes Desktop |
| **Paquete (Batería Objetiva)** | `<repo>/core/bateria.yaml` | Taxonomía, intenciones, marcas, plataformas objetivas | Control de versiones (repo) | `core/bateria.py`, clasificador |

---

## 2. Regla de Oro (Golden Rule)

> [!IMPORTANT]
> **La batería personal vive y se resuelve ÚNICAMENTE en el directorio canónico:**
> `~/.hermes/plugin-data/make-it-smart/bateria.personal.yaml`
> 
> Si un archivo `bateria.personal.yaml` aparece en otra ruta (por ejemplo en el Escritorio o en una carpeta de trabajo temporal), el agente **DEBE AVISAR** al usuario reportando la ruta exacta encontrada en vez de adivinar o mover archivos por cuenta propia.

---

## 3. Resolución programática (`core/paths.py`)

Cualquier herramienta o módulo de Python debe resolver rutas a través de las funciones canónicas de `core/paths.py`:

```python
from core.paths import (
    data_dir,          # ~/.hermes/plugin-data/make-it-smart/ (respeta HERMES_PLUGIN_DATA)
    ui_data_dir,       # ~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/
    bateria_dir,       # == data_dir()
    bateria_objetiva,  # <repo>/core/bateria.yaml
    bateria_personal,  # data_dir() / "bateria.personal.yaml"
)
```

### Orden de resolución
1. Variable de entorno `HERMES_PLUGIN_DATA` (si está definida).
2. Raíz estándar `~/.hermes/plugin-data/<plugin>/`.
3. Para UI: `~/Library/Application Support/Hermes/plugin-files/data/<plugin>/` (o fallback a `HERMES_HOME/plugin-files/data/<plugin>/`).

---

## 4. Publicación automática y sincronización de espejo

El indexador (`tools/build_index.py`) y la herramienta de indexado (`cellar_index op="rebuild"`) escriben automáticamente de forma dual:
1. Escriben `index.json` y `facets.json` en la raíz canónica.
2. Copian idénticamente los mismos bytes (mismo hash md5) a la raíz del espejo de la UI.
3. Si existe `pending_index.json`, se preserva sincronizado entre ambas carpetas.

**Nunca realizar copias manuales entre carpetas**: el pipeline garantiza la paridad de datos.

---

## 5. Verificación rápida para agentes

### A. Inspección vía herramienta `cellar_bateria`
Llamar a `cellar_bateria` con `op="spec"`:
```json
{
  "tool": "cellar_bateria",
  "arguments": { "op": "spec" }
}
```
Campos devueltos para validación:
- `canonical_dir`: Ruta canónica absoluta en uso.
- `ui_dir`: Ruta del espejo de la UI en uso.
- `personal_bateria_path`: Ruta canónica de la batería personal.
- `bateria_objetiva_exists`: Booleano de presencia de `core/bateria.yaml`.
- `bateria_personal_exists`: Booleano de presencia de `bateria.personal.yaml`.
- `ui_bateria_obsolete`: `true` si existe una copia huérfana en el espejo UI que deba considerarse obsoleta.

### B. Inspección vía terminal
```bash
# 1. Comprobar rutas y estado de batería
python3 -c "from tools.cellar_tools import handle_cellar_bateria; import json; print(json.dumps(json.loads(handle_cellar_bateria({'op': 'spec'})), indent=2))"

# 2. Verificar paridad de hashes del índice
md5 ~/.hermes/plugin-data/make-it-smart/index.json ~/Library/Application\ Support/Hermes/plugin-files/data/make-it-smart/index.json
```

---

## 6. Primera instalación y migración

1. **Primera instalación limpia**:
   Si `bateria.personal.yaml` no existe en la raíz canónica, la llamada a `cellar_bateria` crea automáticamente la plantilla copiando `core/bateria.personal.yaml` con sus comentarios de cabecera intactos.
2. **Deduplicación**:
   Si el archivo existe en ambas raíces (canónica y espejo UI), la versión canónica toma precedencia absoluta y la versión del espejo se reporta como obsoleta (`ui_bateria_obsolete: true`).
