# Data Paths & Storage Architecture

> Reference document for **Hermes autonomous agents**. It defines the storage roots, the state files, the write responsibilities and the verification protocol.

---

## 1. Storage roots

| Root | Absolute path (macOS) | Content | Who writes | Who reads |
|---|---|---|---|---|
| **Canonical (Tools / Python)** | `~/.hermes/plugin-data/make-it-smart/` | `index.json`, `facets.json`, `pending_index.json`, `data.db`, `corrections.yaml`, `cheat_sheet.personal.yaml`, `backups/`, `exports/` | `tools/cellar_tools.py`, `tools/build_index.py` | Cellar tools, Python classifiers |
| **UI mirror (Desktop)** | `~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/` | `index.json`, `facets.json`, `pending_index.json` | Automatic pipeline (`build_index.py`, `cellar_index op=rebuild`) | `desktop/plugin.js` via `ctx.files.readText('data', ...)` |
| **Plugin code** | `~/.hermes/desktop-plugins/make-it-smart/` | `plugin.js` | Installer / deployment | Hermes Desktop host |
| **Package (Objective cheat sheet)** | `<repo>/core/cheat_sheet.yaml` | Taxonomy, intents, brands, objective platforms | Version control (repo) | `core/cheat_sheet.py`, classifier |

---

## 2. Golden Rule

> [!IMPORTANT]
> **The personal cheat sheet lives and resolves ONLY in the canonical directory:**
> `~/.hermes/plugin-data/make-it-smart/cheat_sheet.personal.yaml`
> 
> If a `cheat_sheet.personal.yaml` file appears at another path (for example on the Desktop or in a temporary working folder), the agent **MUST WARN** the user by reporting the exact path found instead of guessing or moving files on its own.

---

## 3. Programmatic resolution (`core/paths.py`)

Any Python tool or module must resolve paths through the canonical functions in `core/paths.py`:

```python
from core.paths import (
    data_dir,          # ~/.hermes/plugin-data/make-it-smart/ (honors HERMES_PLUGIN_DATA)
    ui_data_dir,       # ~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/
    cheat_sheet_dir,       # == data_dir()
    cheat sheet_objective,  # <repo>/core/cheat_sheet.yaml
    cheat_sheet_personal,  # data_dir() / "cheat_sheet.personal.yaml"
)
```

### Resolution order
1. Environment variable `HERMES_PLUGIN_DATA` (if defined).
2. Standard root `~/.hermes/plugin-data/<plugin>/`.
3. For the UI: `~/Library/Application Support/Hermes/plugin-files/data/<plugin>/` (or fallback to `HERMES_HOME/plugin-files/data/<plugin>/`).

---

## 4. Automatic publication and mirror synchronization

The indexer (`tools/build_index.py`) and the indexing tool (`cellar_index op="rebuild"`) write automatically in a dual fashion:
1. They write `index.json` and `facets.json` in the canonical root.
2. They copy identically the same bytes (same md5 hash) to the UI mirror root.
3. If `pending_index.json` exists, it is kept synchronized across both folders.

**Never make manual copies between folders**: the pipeline guarantees data parity.

---

## 5. Quick verification for agents

### A. Inspection via the `cellar_cheatsheet` tool
Call `cellar_cheatsheet` with `op="spec"`:
```json
{
  "tool": "cellar_cheatsheet",
  "arguments": { "op": "spec" }
}
```
Fields returned for validation:
- `canonical_dir`: Absolute canonical path in use.
- `ui_dir`: UI mirror path in use.
- `personal_cheat_sheet_path`: Canonical path of the personal cheat sheet.
- `cheat sheet_objective_exists`: Boolean for the presence of `core/cheat_sheet.yaml`.
- `cheat_sheet_personal_exists`: Boolean for the presence of `cheat_sheet.personal.yaml`.
- `ui_cheat_sheet_obsolete`: `true` if an orphan copy exists in the UI mirror that must be considered obsolete.

### B. Inspection via terminal
```bash
# 1. Check paths and cheat sheet status
python3 -c "from tools.cellar_tools import handle_cellar_cheatsheet; import json; print(json.dumps(json.loads(handle_cellar_cheatsheet({'op': 'spec'})), indent=2))"

# 2. Verify index hash parity
md5 ~/.hermes/plugin-data/make-it-smart/index.json ~/Library/Application\ Support/Hermes/plugin-files/data/make-it-smart/index.json
```

---

## 6. First installation and migration

1. **Clean first installation**:
   If `cheat_sheet.personal.yaml` does not exist in the canonical root, the call to `cellar_cheatsheet` automatically creates the template by copying `core/cheat_sheet.personal.yaml` with its header comments intact.
2. **Deduplication**:
   If the file exists in both roots (canonical and UI mirror), the canonical version takes absolute precedence and the mirror version is reported as obsolete (`ui_cheat_sheet_obsolete: true`).
