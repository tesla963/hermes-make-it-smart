# Changelog

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
cp desktop/plugin.js ~/.hermes/desktop-plugins/make-all-my-work-smart/plugin.js
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
