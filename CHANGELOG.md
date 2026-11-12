# Changelog

## 0.27.1 — 12-nov-2026 · sub-sessions hang from their mother, and the rename finishes

### Added
- **Sub-sessions are drawn as children.** The index carries `parent`, read from
  `sessions.parent_session_id`, and the table reorders a subagent row right under the session
  it came from, indented with a gold `↳` and a tooltip in both languages. The measurement
  changed the design: 158 sessions across all profiles carry that column, but only **7** are
  subagents — the rest are desktop sessions continuing one reaped at startup
  (`end_reason *_orphan_reap`). Indenting on the field alone would have bled 151 normal rows,
  so the index writes `parent` for subagents only *and* `isChildRow()` requires `esBot` and
  rejects a self-parent. A child whose mother is filtered out is drawn as a root; a cycle
  (a→b→a) is drawn as one root and never loops.

### Fixed
- **Axis filtering through the tool layer was broken both ways.** `cellar_tools` validated
  axis names with the regex `^tag[1-9]$`, which the v0.27.0 rename could not see: a filter
  using `iq3` was silently ignored (770 rows returned as if unfiltered) and one using `tag3`
  matched nothing. `cellar_tag`, the tool that writes axis values, rejected `iqN` outright
  with "No valid tag keys". `_axis_key()` now normalises `tagN` and `iqN` to `iqN`, the
  argument is `iqs` with `tags` still accepted as an alias, and `empty_counts` reports on
  `iqN`. Measured: `iqs={iq3: Investigar}` returns 209 rows instead of 770.
- **22 identifiers the first rename could not see** (`tag1_nuevo`/`tag2_nuevo` in the title
  CSV, `_known_tag1_set`, `tag3_vocabulary`, `tag3i`, one test name) and a real crash:
  renaming `--tag2-only` to `--iq2-only` changed argparse's dest while the body still read
  `args.tag2_only`, so `tools/apply_protocol.py` died with `AttributeError`. The dry run now
  ends in "dry run — nada escrito".

### Changed
- **The word "tag" is gone from the product and the documentation.** The panel no longer says
  `Tag 6 · Máquina` or `Tags`; the docs say *axes*; the classifier prompt, the batteries and
  the rule prose speak of axes. `is_redundant_tag()` became `is_redundant_axis()`.
- **`desktop/_desactivado_plugin.js` removed** — the disabled copy of the panel, dead code
  carrying 16 old axis keys.
- **`SPEC-BATCH.md` now opens with a historical banner**: it is the week's internal spec,
  written when the axes were `tagN` and a rename to `dnaN` was being considered. That rename
  was cancelled; the banner says so and points at `tools/migrate_axes.py`.

### Where the word survives, on purpose
`CHANGELOG.md` (it records the rename), `tools/migrate_axes.py` and its test (they must name
both schemas), the `iqs`/`tags` alias in `cellar_tools`, the `tag{n}` fallback in
`build_index`, and the stable rule id `tag-structure-2026-11-10`, which docs and the owner's
personal overrides reference — renaming a key would break them, so the id stays and carries a
comment saying so.

## 0.27.0 — 12-nov-2026 · the nine axes are called iq0…iq9

### Changed
- **Axis keys renamed**: `tag0`…`tag9` became `iq0`…`iq9` in the JSON artefacts
  (`index.json`, `facets.json`), in the field names of `core/`, `tools/` and
  `desktop/plugin.js`, in the YAML batteries, in the panel's labels and in the
  documentation — 1,247 occurrences across 37 files. History is deliberately untouched:
  `CHANGELOG.md`, `docs/PENDIENTES.md` and `SPEC-BATCH.md` keep the old names because they
  describe what shipped at the time.

### Added
- **`tools/migrate_axes.py`** — the algorithm that upgrades any artefact from v0.26.1 or
  older, in place and exactly once:
  - it reads the schema from the file's own content (`tagN` ⇒ v1; `iqN` or
    `"schema": 2` ⇒ v2), so nothing has to be declared;
  - it renames every key at any depth, leaving values untouched — a `tag1` inside a
    description stays a description;
  - it copies the file to `plugin-data/make-it-smart/backups/<name>.pre-iq_<stamp>`
    before writing, then replaces it atomically through a temp file;
  - it stamps `"schema": 2` and is **idempotent**: a second run reports
    `already-current` and leaves the file byte-identical;
  - `--dry-run` reports the counts and writes nothing.
- **Tolerant readers**: `withAxes()` in the panel and `load_facets()` in the indexer accept
  either key set, so installing v0.27.0 over an old data directory never renders an empty
  catalogue.
- **`tests/test_migrate_axes.py`**: schema detection, key renaming, value preservation,
  backup integrity, dry-run and idempotency.

### Migration
`tools/build_index.py` migrates first and rebuilds after, so an existing installation
upgrades by rebuilding the catalogue. Verified on the live data: 7,913 keys in
`index.json`, 8,181 in `facets.json`, zero `tagN` left, 879 sessions intact.

## 0.26.1 — 12-nov-2026 · empty-state message and a Bots filter

### Added
- **Bots chip**: a fourth state chip next to Deleted / Empty / Cron. Bot Chat and subagent transcripts are machinery, not work, so the list hides them by default (19 rows in this catalogue: 12 Bot Chat + 7 subagents) and shows only them when the chip is on. The count rides on the chip: `Bots · 19`.
- **Empty state**: when nothing is pending, Testing says so instead of leaving a dead button — `No sessions to process` in English (the default) or `No hay sesiones para procesar` when the user switches language. 14 px, weight 700, primary text colour: readable at a glance without borrowing the panel's error red.
- **`esBot` in the index**: `build_index` now writes a flag from the session's `source` column. Two subagents had already been renamed, so detecting them by the `Subagent:` title prefix was not enough — the database had the answer.

## 0.26.0 — 12-nov-2026 · window tabs, an honest Testing tab, classifier alignment

### Added
- **Window tabs**: `Actual Hermes DB Sessions` and `Testing` are real tabs now — a 2px bar on each side plus the bottom underline in the tab's own colour (`--ok` green, `--gold` gold), 40% opacity when idle, 75% on hover, full when selected. The panel always opens on the real database; Testing is a deliberate step and is never restored from `localStorage`.
- **Testing lists only real work**: the tab shows just the sessions a commit would change. Cron, empty, deleted, Bot Chat and subagent transcripts are never renamed and never counted (`esIntocable`).
- **The commit button states the work**: `Commit Changes to Hermes DB (N Sessions to Process)`, disabled at 0.
- **Testing is the refresh moment**: entering the tab re-reads the catalogue and picks up gateway sessions the snapshot does not contain yet. The index stays a cache everywhere else.

### Fixed
- **Renamed titles came back as pending**: `loadCatalogue` preferred `index.json`'s snapshot over the live gateway title, so 117 already-renamed sessions reappeared as work after a commit. The live title now wins, and the commit ledger stands in for sessions the gateway no longer lists.
- **Zero pending while the sidebar showed unrenamed sessions**: after a revert the snapshot kept the canonical titles. `syncIndexRaw()` patches the snapshot right after a commit **and** after a revert, so panel and `state.db` cannot disagree.
- **A canonical title became its own description**: `925 [Sin título] 001` was written as `925 [Sin título] 001 925 [Sin título] 001`. A title that parses as canonical no longer contributes a description.
- **Invented number, subject and ordinal**: rows without a canonical title printed `[<36-char slice>] 001` before them. They now print the title exactly as Hermes wrote it, with no subject pill and no `MMM`.
- **Entering Testing looked like the rename had happened**: the table swapped every title for the proposal on entry. The table always shows the real title; renamed names appear only after Commit.
- **Tab borders repainted red**: the generic `.mmws button:hover{border-color:var(--wine)}` and `.mmws button.on` outranked the tab selector, and the OS focus ring (pink on some Macs) was never reset. The tab now owns its border in every state with `!important`, scoped to the tab.
- **Grey hairline under the idle tab**: `.headtabs` painted a 1px `--line2` baseline that showed through the 2px *transparent* bottom border of any tab that was not selected, so both idle tabs (green and gold) carried a thin grey thread along their bottom edge, breaking the window-tab silhouette. Root cause: the coloured side bars (`.headtab::before/::after`) close the tab on the left and right, but the bottom stayed transparent and let the container rule through.
- **Fix**: the tab strip no longer paints a baseline (`border-bottom:1px solid transparent` keeps the geometry), and each tab closes its bottom edge in its own hue — `--ok40` / `--gold40` (40% alpha) when idle, full `--ok` / `--gold` on hover and when selected. Because the grey rule is gone, the attenuated border composites over one single background and no longer renders half-over-grey / half-over-black.
- Verified by pixel measurement at DPR 2 (static page, real stylesheet, four states): zero `#3a3040` pixels in the border rows and a uniform 2px line per state.

### Changed
- **"New Rules Update" removed**: teaching rules is the user's conversation with Hermes, not a button in the panel. The handler and its i18n keys are gone.
- **Retry conversation accumulates** (`core/classify.py`): the model now sees its rejected answer plus the rejection, instead of the same prompt every attempt.
- **Intention vocabulary aligned** (`core/intent.py`): the seven of `tag-structure-2026-11-10`; the retired names survive as signals (`Update`+`Version`+`Feature` → Instalar, `Costo` → Cotizar, `Administrar`+`Respaldar` → Troubleshooting).
- **The owner's battery is merged** (`core/bateria.py`): `load_bateria(path=None, merge_personal=True)` deep-merges `bateria.personal.yaml` by key and skips empty sections, so the contract in its header is finally kept. `to_facets()` passes the merged sheet to `strip_brand()`.
- **Duplicate `google:` key merged** (`core/bateria.yaml`): the second definition silently dropped Chrome, Chromium and Gemini Desktop.

## 0.25.0 — 11-nov-2026 · data paths architecture, tag0/tag8/tag9 axes, Actual/Testing tabs, commit/revert and removal of the simulator

### Added
- **Actual / Testing tabs (§22.2)**: top double tab `[ Actual Hermes DB Sessions ]` (read-only of real titles in `state.db` via RPC) and `[ Testing ]` (live simulation of titles applying the canonical nomenclature, `TESTING` badge visible in the header and persistence in `localStorage`).
- **Unified bottom row (§22.3, §22.4)**: single bottom strip with the action buttons on the left (`Commit Changes to Hermes DB` in red, `Revert` in green and neutral `New Rules Update`) and statistics on the right. The hours KPI (`Work hours`) was removed to gain horizontal space.
- **Backup and Revert system (§22.5)**: mandatory generation of `commit-backup-<YYYYMMDD_HHMM>.json` and `commit-last.json` in `ctx.files` when entering the Testing tab. Commit writes to `state.db` via `session.title` only differing titles (excluding cron and empty ones), refreshing the backup beforehand if it is more than 10 minutes old. Revert restores the previous titles in one click with a confirmation dialog. Commit and Revert never coexist.
- **Rules update («New Rules Update», §22.7)**: re-reads `index.json` and `facets.json` via `ctx.files`, recomputes the simulation and reports how many sessions would change, warning if the index is more than 24 hours old.
- **Canonical and mirror data paths (`core/paths.py`)**: functions `ui_data_dir()`, `bateria_dir()`, `bateria_objetiva()`, `bateria_personal()`, with resolution order `HERMES_PLUGIN_DATA` → `~/.hermes/plugin-data/make-it-smart/` → `plugin-files/data/make-it-smart/`.
- **Dual automatic publishing**: `tools/build_index.py` and `cellar_index op="rebuild"` write `index.json` and `facets.json` identically in the canonical root and in the UI mirror (same MD5 hash guaranteed).
- **`plugin.yaml` manifest**: `data:` section detailing the canonical and UI mirror paths, index files, facets, battery and pending items. Version bumped to `0.25.0`.
- **`docs/DATA-PATHS.md`**: guide and reference table for Hermes agents with the golden rule: the personal battery is read from and written to the canonical root; if it shows up at another path, warn instead of guessing.
- **`cellar_bateria op="spec"` tool**: returns `canonical_dir`, `ui_dir`, `bateria_objetiva_exists`, `bateria_personal_exists` and `ui_bateria_obsolete`. On a first clean install it initializes `bateria.personal.yaml`, preserving the header comments intact.
- **`tag8 · Project` axis**: added as a filterable facet in the side panel and shown with its `tag8` pill in the detail card.

### Changed
- **Definitive removal of the simulator (§22.1)**: `tools/simulator_template.html` (88.710 B) deleted and every reference in tools, specifications and documentation cleaned up. The plugin's native interface is now the only environment.
- **«Get Info» on the plugin name (§22.6)**: the `V 0.25` badge is removed from the footer; the information and learned-rules modal (`vModal`) opens by clicking the plugin name (`Make It Smart` / `h1`) in the header.
- **Vertical session tab (R1 / §17)**: simplified to a single word and a single `span` (`Sesión` in ES / `Session` in EN), removing the clipping and stuck-together letters problem (`SESSIONINFO`).
- **Filter location (R4)**: the "Pending" and "Subject" facet blocks moved to the top of the left panel, before "tag1 · Maker".
- **tag0/tag8/tag9 axes (R3 / §15)**: the Subject filter and facet read `tag0` (`tag0 · Sujeto` / `tag0 · Subject`); the merge preserves `tag8` intact and switches only `tag9` to `'Pending'` if there are pending authorizations.
- Version bumped to `0.25.0` in `plugin.yaml`, `desktop/plugin.js` and `CHANGELOG.md`.

## 0.24.0 — 11-nov-2026 · pending approval visible per session

### Added
- **Right panel**: `Pending Authorization IDs — Memory` and `— Skills` blocks, with the copy button **above** each title, the ids in monospace and a confidence tooltip (`exact` / `window` / `window_amb` / `orphan`).
- **`Pending` column** in the listing, after Posts, with its sort key.
- **Pending filter** (tag9) and **Subject filter** (tag0) in the left panel, with counters, and combinable with the existing month filter.
- **`PENDING AUTH` KPI** in the footer, clickable to activate the filter.
- Collapsible **«Unattributable session»** block with the proposals that could not be attributed to any session.
- CSV: `pending`, `pend_mem`, `pend_skl` columns aligned with the table.
- `pending_index.json` as the source of the ids (generated by an external indexer, not by the plugin).

### Changed
- The **Session Info** side tab is drawn on two lines: it no longer clips.
- The **Copy session / Open session** buttons also appear at the top of the detail panel.
- If `pending_index.json` is missing, the whole feature hides without visible errors.

### Notes
- Read-only: the plugin never approves, rejects or deletes proposals.
- The hours counter (`HOURS` column and KPI) is still zero: **documented bug, not fixed in this version** (§13 of the batch spec).

## Unreleased — plugin id renamed to `hermes-make-it-smart`

The plugin id and its storage key were renamed to match the repository:

| Before | After |
|---|---|
| `plugin.yaml` → `name: hermes-make-all-my-work-smart` | `hermes-make-it-smart` |
| `core/paths.py` → `PLUGIN` | `make-it-smart` |
| `tools/cellar_tools.py` → `PLUGIN_NAME` / `TOOLSET_NAME` | `make-it-smart` |
| Plugin data | `plugin-data/make-it-smart/` |
| Desktop half | `desktop-plugins/make-it-smart/` |

Migrated, not rebuilt: the existing `index.json` (910 sessions) and `facets.json` were moved with the
data directory, so nothing is lost. `hermes plugins validate .` → passed · `node tests/test_plugin.mjs`
→ OK · `tests/test_invariants.py` → 11/11. **Hermes Desktop must be restarted** so it scans the new
folder name.

> **Operational note:** the plugin id *is* the folder name under `desktop-plugins/`, and Hermes Desktop
> scans that folder **only at launch**. Between the rename and the next full quit (⌘Q, not just closing
> the window) the plugin looks uninstalled — the sidebar entry disappears with no error anywhere.
> Verified 2026-11-10: after quitting and reopening, **Make It Smart** came back on its own.


## v0.1.2-preview — 2026-11-11 · Last known good (CLI tools + English default)

**Install this one.** Content is exactly commit **`6365c9b`**: the ten `cellar_*` agent tools,
the native GUI reading real sessions from the gateway, English as the default language, and **no
keyboard or mouse interaction layer**.

`desktop/plugin.js` — 2,773 lines, SHA-256 `b46e4005010f…`. Verified: `hermes plugins validate .`
passed · `node tests/test_plugin.mjs` OK · `tests/test_invariants.py` 11/11.

### Withdrawn — batch 2 (commit `6d90737`): DO NOT USE

An experimental UI batch was built on top of this version and **did not work in practice**:
`Tab` zones, roving focus, `Enter` to open, `Space` to toggle the card, right-click to open,
`⌥`+right-click context menu and the four `smarts.*` keybinds. It was reverted in **`2372694`**.

- **Do not install** commit `6d90737` or any build produced from it.
- It stays in the history only as a record of what was tried.
- The failure was not diagnosed item by item; when it is retried, it should go one feature at a
  time instead of eleven at once.

## v0.1.1-preview — 2026-11-10 · Port of the 2026-11-11 simulator

**What it is:** the native GUI now behaves like the current simulator, not the November 7 one.
Still **read-only**: it lists, filters, searches and copies; it does not rename, classify or write
to the database.

Ported from `2026-11-11_simulador-solo-codigo.html` (1.5 MB, 40 functions) into
`desktop/plugin.js`: **+640 / −330 lines, one file**. Verified with `hermes plugins validate .`
(passed) and `node tests/test_plugin.mjs` (all green); the copy in `~/.hermes/desktop-plugins/` was
synchronised to the same SHA-256.

### Added

- **Exclusive state filters + an `Empty` state** (`setEstado`). Three mutually exclusive buttons
  under *Mostrar* — `Deleted · N`, `Empty · N`, `Cron · N`. With none active the list hides deleted
  sessions, cron sessions and empty ones; activating one shows only that subset; pressing it again
  turns it off. `esCron` now also detects `profile`/`id` matching `cron[_-]…`.
- **Sequential navigation between sessions from the detail card** (`filasVisibles`,
  `sesionActualIdx`, `navSesion`, `updNaveg`). ▲/▼ arrows walk the *visible* rows, call
  `scrollIntoView({block:'center'})` when the row leaves the 22 %–74 % band of the viewport, disable
  themselves at the ends, and mark `.sele` on both the body row (with the wine left bar) and the
  aside row.
- **Vertical `Info sesión` / `Session Info` tab** on the right edge of the toolbar: one click opens
  the detail card of the first visible session without the global click-outside listener closing it.
- **Cron hygiene notice** (`pintaAviso` + `CRON_INFO`): a banner above the table appears when there
  are empty cron sessions or live jobs, explains the cause, and offers **Copy** to put a ready-to-use
  prompt on the clipboard for the assistant.
- **Full bilingual detail card** (`pintaPanel` + `fichaTexto`): switching ES | EN repaints the open
  card in place without losing the selection, translating labels that used to be hard-coded in
  Spanish (path, messages, description, ADN, note, empty pill).

### Changed

- **Toolbar reorganised.** `.trow` groups the actions on the left (`Limpiar`, `Copiar · N`,
  `Exportar · N`) followed by *Mostrar* filters; four redundant controls (sort, update DB, filter
  drawer, fit check) were removed. Below them, `.chipsrow` holds the active-filter chips on the left
  and the row counter on the right.
- **Aside and facets.** The search input `#q` is pinned in `.abarra`, outside the scrolling
  `.ascroll`; `tag1` always pins `Bot` (`FIJOS1`); the date tree keeps **one month open at a time**
  (`openSoloUnMes`) and no longer repeats the year in each month name.
- **Search index** (`_s`) now indexes `raw` and `resumen` too, so half-remembered phrases match.
- **Duration formatter** (`fmtHoras`): `—` for zero or negative, `Xd Yh` / `Xd` above 1440 minutes,
  `Xh` when fewer than 5 minutes remain. `fmtH` stays exported for the unit test.
- `calling` in the new simulator is **text inside `DATA`**, not a function — the earlier count of
  "new functions" over-counted it.

### Known limitations of this version

- **It does not write.** Editing and persisting titles from the window, and the batch classifier,
  are the next stage.
- **The hours statistic does not work yet** — the KPI column formats correctly but the value comes
  from `state.db` and is not being computed for every session. Deferred: the GUI was frozen by
  decision, not by oversight.
- *Actualizar BD* detects sessions without a canonical title but does not run the Python classifier:
  the host exposes no RPC method that triggers it.
- Tag axes still follow the old order in `core/taxonomy.py`; the remap to the nomenclature in
  `docs/FEATURES.md` is pending.
- Parity gaps remaining: synonym-aware search, clickable row pills, deleted-session filter wired to
  the new state buttons, export with `[CCCC]` counter and `verb`/`verb_nuevo` columns.

### Install

```bash
git clone https://github.com/tesla963/hermes-make-it-smart
cd hermes-make-it-smart
python3 tools/build_index.py          # builds index.json from your state.db (read-only)
cp desktop/plugin.js ~/.hermes/desktop-plugins/make-it-smart/plugin.js   # id in use since v0.25.0
```

Restart Hermes Desktop and open **Make It Smart** in the sidebar. The full functional specification
is in `docs/FEATURES.md`.

---

## v0.1.0-preview — 2026-11-10 · Installable GUI, no write functionality

**What it is:** the first version a third party can install and see working against their own data.
The native Hermes Desktop window reads the real sessions from the gateway and shows them in the
catalogue. **It writes nothing**: it does not rename, classify or update the database.

### Milestone — the native GUI shows the real 910 sessions

Verified on the author's install: the table with the simulator's columns, the aside with the date
tree, and the KPI bar reading **768 visible sessions · $69.85 accumulated · 267M tokens**.

### Added

- `register(ctx)` with the `on_session_end` hook, refreshing `index.json` via
  `build(with_messages=False)` so message bodies are not rebuilt on every turn.
- Native page (`desktop/plugin.js`) registered in `ROUTES_AREA` (`/smart`) and in the sidebar as
  **Make It Smart**: two-line row, nine tag slots, pills, faceted aside, five-figure KPI bar, detail
  card, copy/export and ES | EN switch.
- Data loaded from the host: `session.list` per profile (through `host.request` /
  `host.listPersistedSessions`), with cost, hours, tokens and engine computed from `state.db`.
- **Visible diagnostic banner:** when an RPC fails it shows the method, the literal message and a
  Retry button, instead of swallowing the error.

### Fixed

- The table came up empty because `ctx.files.readText('data', …)` reads from
  `~/Library/Application Support/Hermes/plugin-files/data/<plugin>/` and not from
  `~/.hermes/plugin-data/<plugin>/`. Data is now published where the host actually reads it.
- The loaders swallowed failures with `catch(_)`, which made the cause invisible.

### Install

Same as above.
