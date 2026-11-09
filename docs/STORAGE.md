# Where the plugin keeps its things

Hermes defines the answer, and it is not negotiable: `plugins/plugin_storage.py`.

## The rule

```
<hermes home>/plugin-data/<plugin-name>/
```

That is the only correct home for a plugin's persistent state. Reach it through
the host API, never by building the path yourself:

```python
from plugins.plugin_storage import plugin_data_dir, plugin_db

data = plugin_data_dir("make-my-work-smart")   # creates it, follows the active profile
data / "exports"                                # CSVs handed to the owner
plugin_db("make-my-work-smart")                 # -> plugin-data/<name>/data.db
```

## What is forbidden, and why

| Path | Why not |
|---|---|
| `<hermes home>/plugins/<name>/` | the **install** dir: deleted by `remove`, overwritten by `update`. Anything written there is lost on the next upgrade. |
| `state.db` | the host's table. Reading is fine; writing goes through `SessionDB.set_session_title` and nothing else. |
| beside the source tree | a plugin installed from the catalog runs from a checkout the user does not own. |

`plugin_data_dir()` resolves `get_hermes_home()` on **every call**, so it follows
the active profile. Do not cache the path across a profile switch.

## What the plugin stores, and where

```
~/.hermes/plugin-data/make-my-work-smart/
├── data.db                 the index: sessions, facets, subject counters, export log
└── exports/
    ├── [0001] 20261109_1744_841sesiones.csv
    ├── [0002] 20261110_0912_884sesiones.csv
    └── index.json          the export log, so CCCC survives a reinstall
```

### Does the plugin have its own database?

Yes, and it must. Two reasons:

1. **The host's `state.db` is read-only territory.** The plugin indexes 12
   databases across 12 profiles; it cannot add tables to any of them.
2. **The index must outlive a rename.** The subject counter (`MMM`) and the
   learned corrections are the plugin's memory, not the host's. If the index
   lived in `state.db` it would be wiped by any schema migration and the
   numbering would restart.

The index is a **cache, not a source of truth**: it can be rebuilt from the
twelve `state.db` files at any time. That asymmetry is deliberate — it means a
corrupted index costs one reindex, never data.

### Export numbering

`[CCCC]` is a monotonic counter, four digits, kept in `exports/index.json`
(the desktop UI mirrors it in `localStorage` so the counter survives a page
reload). The file name carries it first so exports sort chronologically and can
be cited by number — "look at export 0007" — the same way sessions are cited by
`NNN`.

```
[0001] 20261109_1744_841sesiones.csv
  │     │        │     │
  │     │        │     └─ how many sessions the export contained
  │     │        └─────── HHMM the file was written
  │     └──────────────── YYYYMMDD
  └────────────────────── export number (never reused, never reset)
```
