# Agent surface — the tools the assistant needs

Ten tools, no more. Every one exists because a real loop needs it: the owner talks, the assistant
looks, then acts, then leaves a trace. Names are prefixed `cellar_` (the catalogue, the "bodega").

Conventions used by all of them:

- **Rows are compact.** A row is `{n, id, title, sujeto, iq1…iq9, desc, verb, fecha, costo,
  horas, tok, posts, prof, motor, esCron, vacia}`. Never return whole session bodies unless asked.
- **Every read is paginated**: `limit` (default 50, max 500) and `offset`, plus `total` and
  `truncated` in the envelope so the assistant knows what it is missing.
- **Every write is gated**: `confirm: true` is required; without it the call returns
  `{ok: false, reason: "confirm required", preview: …}` and changes nothing.
- **Every write backs up first** and returns `backup_path` plus a `receipt` (timestamp, rows
  touched, index generation before/after).
- **Every write appends to `corrections.yaml`** in `plugin_data_dir()`: `{when, session_id (the
  Hermes session that issued the call), tool, before, after, rule?}`. That log is the plugin's
  memory of being corrected; nothing is learned unless it lands there.
- **No destructive verbs.** No delete tools. Clearing a tag is `set(null)`; a wrong rename is
  undone by renaming again, and the log has the previous value.

## Read — 4 tools

### 1. `cellar_search`
The workhorse. One call answers "what do I have about X".
- `q` (text, optional): matches title, sujeto, desc, raw, resumen.
- `tags`: partial map, e.g. `{"iq1":"Cyberpanel","iq3":"Troubleshooting"}`; ignored keys are fine.
- `date_from` / `date_to` (`YYYY-MM-DD`), `prof`, `motor`.
- `state`: `active` (default) | `cron` | `deleted` | `empty` | `all`.
- `sort`: `fecha_desc` (default) | `n_asc` | `costo_desc` | `horas_desc`.
- `limit` / `offset`.
- Returns: `{rows: [...], total, truncated, query_echo}`.

### 2. `cellar_session`
One session in full, by `n` or `id`.
- `include_messages` (default `false`): up to `messages_limit` (default 12) **key** user messages,
  filtered of cron preambles and skill dumps.
- `include_why` (default `true`): the "ADN" block the detail card shows.
- Returns: one row plus `{messages?, why, index_generation}`.

### 3. `cellar_stats`
Aggregates for any `cellar_search` filter — same parameters, no rows.
- Returns: `{count, sum: {costo, horas, tok, posts}, by_facet: {iq1: {...}, iq2: {...},
  iq3: {...}, iq4: {...}, fecha_year: {...}, prof: {...}}, empty_counts: {iq1: n, …}}`.
- `by_facet` honours a `facets` list so a caller can ask for one axis only.

### 4. `cellar_series`
The relationship view: every session that is the same piece of work.
- `subject` (normalised or raw) **or** `n`.
- Returns: `{subject, mmm_range, rows: [...], totals: {...}, gaps: [mmm values missing]}`.
- This is what answers "the eleven sessions about the gateway are one job".

## Write — 5 tools

### 5. `cellar_rename`
Rename one session or a batch. Two modes:
- `fields`: `{sujeto, iq1…iq9, desc, verb}` — the tool renders the title with the nomenclature in
  force. **Preferred**: it cannot drift from the format.
- `title`: a literal string — only for rare cases; the tool still validates length and structure.
- Selector: `n` / `id` / a `filter` object (same shape as `cellar_search`, max 50 rows per call).
- `dry_run` (default `true`): returns the before/after list and touches nothing.
- `confirm: true` required when `dry_run=false`.
- Returns: `{ok, changed, preview[], backup_path, receipt, rejected:[{n, reason}]}` where
  `rejected` covers host refusals (e.g. canonical bot chats) and 100-character breaches.

### 6. `cellar_tag`
Set or clear individual tags without touching the rest of the title.
- `selector` (`n`, `id`, or `filter`), `set`: `{iq1: "Cyberpanel", iq5: null}`, `dry_run`, `confirm`.
- Returns: same envelope as `cellar_rename`. Useful for the "wrong axis" cleanups.

### 7. `cellar_bateria`
The vocabulary and the cheatsheet — the file the classifier consults.
- `op`: `spec` | `sections` | `get` | `upsert` | `remove`.
  - `spec`: the nomenclature in force + the closed vocabularies (iq3's seven, iq4's themes) +
    counts per batería section. **Call this first** in any session: it replaces reading the docs.
  - `sections`: names and entry counts.
  - `get`: one section, or one entry.
  - `upsert`: `{section, key, value}` — e.g. `{section:"programas", key:"DaVinci Studio",
    value:{config_path:"…", notes:"…"}}`; `vocabulario` and `reglas` are sections too.
  - `remove`: soft removal (kept with `removed: true`), never a hard delete.
- `dry_run` (default `true`) and `confirm` for the two write ops.
- Writes go to `plugin_data_dir()/bateria.personal.yaml`, **never** to the repo's `core/bateria.yaml`.

### 8. `cellar_index`
Maintain the derived index. Executes in the plugin host process, so it **does not need an RPC** —
this is what finally makes *Actualizar BD* work.
- `op`: `status` | `detect` | `rebuild` | `classify`.
  - `status`: generation, counts, age, and how many sessions lack a canonical title.
  - `detect`: dry list of sessions added/changed since the last index.
  - `rebuild`: re-reads `state.db` and rewrites `index.json` + `facets.json`.
  - `classify`: runs the Python classifier over the untitled set (`limit` per call, default 25) and
    **does not rename** — it returns proposals.
- Returns: `{ok, counts:{new, changed, untitled, classified}, proposals[], backup_path?}`.

### 9. `cellar_verify`
Lint the archive before and after any batch — the assistant's own quality gate.
- Checks: title length ≤ 100; `NNN` unique; `MMM` without gaps per subject; `iq3` inside the seven;
  `iq4` inside the themes; `iq1` present in the batería or explicitly allowed empty; subject not
  equal to `iq1`; description present when the fields cannot say it.
- Returns: `{ok, offenders:[{n, id, rule, detail}], summary:{by_rule}}`.

## Export — 1 tool

### 10. `cellar_export`
Leaves the machine or comes back into the loop.
- `what`: `titles` | `corrections` | `bateria` | `facets`.
- `format`: `csv` | `yaml` | `json`.
- Writes to `plugin_data_dir()/exports/<what>_<[CCCC]>.csv` with the counter, and returns
  `{path, rows, bytes}`.
- Never overwrites: the counter is the citation contract the export system uses.

## What I deliberately did not ask for

- **A tool per tag.** `cellar_tag` covers all nine.
- **A delete tool.** Nothing in this plugin deletes; the host refuses and the log remembers.
- **A GUI editor for the batería.** The owner chats, the assistant calls `cellar_bateria`, and the
  change lands in an append-only log. A form would duplicate a surface the agent covers better.
- **A catch-up/transcript reader.** Session bodies are only read through
  `cellar_session(include_messages=true)`, on demand, for one session at a time.
