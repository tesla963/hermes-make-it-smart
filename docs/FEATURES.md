# Features — Hermes, Make it Smart!

## 1 · What it really is

A plugin that renames sessions does what everyone already does: paste the subject in. This one
builds a **language** — a compact, structured way of saying *what a session is about, with what,
where, for what purpose and under which theme*. It is not a prettifier for titles: it is an
encoding with far higher information density than the sentence a human or a model would have
picked, and it is written the way a machine reads best.

That is why the same nomenclature renames a **Hermes session** and a **YouTube video title**: the
thing being described is the same — an intention about a subject.

The problem it solves: after months, sessions are called `Chat`, `Session 2026-10-28` or the
first sentence typed. Search only works if you remember a word. It cannot answer *how many
sessions did I spend on my VPS*, or *what were the eleven sessions about the same subject*. An
agent that forgets the shape of your work is an agent you must re-brief every day.

## 2 · The nomenclature

```
NNN [Sujeto] MMM [Iq1] [Iq2] Descripción · Verbo
```

The **title identifies the subject**. `Iq1` **amplifies** it — the brand, or the program.
`Iq2` is context: place, machine, country, store. The description states the essence (the
intention in words), and `Iq3`/`Iq4` — intention and theme — stay **invisible** in the title
while driving every filter.

### The four reference cases

| | Sujeto | Iq1 | Iq2 | Iq3 (intención) | Iq4 (tema) |
|---|---|---|---|---|---|
| **1** | **Air 2S** | DJI | Ebay | *la intención* — la aclara la descripción | el tema |
| **2** | **DNS + Email** | Cyberpanel *(programa)* | VPS | Troubleshooting | — |
| **3** | **Protocolo** | Hermes Gateway | MacMini M4 | Troubleshooting | IT Manager *(o la subcategoría que cuelga de ese tema)* |
| **4** | **Trace Minerals** | Dr. Berg | Amazon | Compra | Medicina / Nutrición |

Cases 2 and 3 are why `Iq1` was widened: **it holds a brand *or* a program.** A troubleshooting
session is about a program, not a manufacturer, and forcing it into "brand" produced wrong
titles.

Case 4 is what the density buys: *investigating a product on Amazon, possibly asking for an
analysis of the reviews* becomes six words in the title plus three clickable filters underneath.

## 3 · The ten fields, iq0 to iq9

Ten slots, so a new field never forces a migration. Six carry data today.
Counts measured over **879 sessions**.

| Slot | Field | What it holds | In the title | Filled |
|---|---|---|---|---|
| **iq0** | Subject | the block or part, 1–3 words, no verb | **yes** | 873 |
| **iq1** | Program | the program, platform or brand the work happens in — or is the object of | **yes** | 478 |
| **iq2** | Context | store, country or machine around it | **yes** | 212 |
| iq3 | Intention | closed vocabulary of seven — see §4 | no | 570 |
| iq4 | Topic | the topic, or a sub-topic under it | no | 854 |
| iq5 | Year | which edition | no | 17 |
| iq6 | — | retired: the machine moved to iq2 | no | 0 |
| iq7 | — | reserved | no | 0 |
| iq8 | — | reserved | no | 0 |
| iq9 | — | reserved | no | 0 |

What each one actually contains, from the live index:

| Slot | Most frequent values |
|---|---|
| iq1 | `CyberPanel` 77 · `Apple` 62 · `AMD` 62 · `Mac mini M4` 38 · `Panamá` 25 |
| iq2 | `Mac mini M4` 97 · `Panamá` 33 · `VPS` 25 · `Teléfono` 19 · `Amazon` 13 |
| iq3 | `Investigar` 261 · `Troubleshooting` 146 · `Comparar` 50 · `Testear` 39 · `Compatibilidad` 34 |
| iq4 | `IT Manager` 252 · `Hardware` 141 · `IA Bot` 83 · `Data Mining` 62 · `Derecho` 58 |
| iq5 | `Panamá` 10 · `1972` 3 · then noise — **this axis is contaminated and must be cleaned** |

**The name carries iq0, iq1 and iq2 — never iq3 or iq4.** The name says *what, who and
where*; the rest are filters.

## 4 · Where the fields landed in the code

The mapping the code implements matches the data:

| Field | Implementation |
|---|---|
| iq0 | the `sujeto` column of the index; declared as `iq0` in `cellar_tools` |
| iq1 | `PLATFORMS` + the brands of the cheat sheet |
| iq2 | `CONTEXT`: store, country or machine — `normalize_*` rejects anything else |
| iq3 | `INTENTIONS`, closed at seven |
| iq4 | `IT_SUBCATEGORIES` + `OTHER_THEMES`, seeded from `PILLARS` (the list keeps its historical name) |

`Troubleshooting`, `IT Manager`, `Medicina`, `Nutrición`, `Ebay`, `Amazon` all exist and sit
on the axis they belong to. `Compra` is still missing as an intention: the vocabulary has
`Compras` as a topic, never as a verb.

**And there are two intention lists that disagree** — another thing to fix, not to document away:

| Source | List |
|---|---|
| `taxonomy.py` → `INTENTIONS` (the one the rename path reads) | 7: `Comparar · Instalar · Investigar · Testear · Cotizar · Troubleshooting · Compatibilidad` |
| `intent.py` → `INTENTS` (the signal dictionary) | 13: `Instalar · Update · Version · Feature · Compatibilidad · Comparación · Diagnosticar · Testear · Cotizar · Costo · Administrar · Respaldar · Investigar` |

So the intention vocabulary is 7 in one file and 13 in another, with `Troubleshooting` vs
`Diagnosticar` and `Comparar` vs `Comparación` naming the same idea twice. **One list wins before
anything else touches the classifier.**

> **Decided 2026-11-10 — this settles it.** The **7-value list** is the only intention vocabulary:
> `Comparar · Instalar · Investigar · Testear · Cotizar · Troubleshooting · Compatibilidad`.
> `intent.py`'s 13-value list adapts to it or is deleted; `Compra` is expressed as the existing
> intention plus the `Compras` theme, not as a new intention.
>
> **And this page is the authority.** `ALGORITHM.md`, `STATUS.md` and any contradicting comment in
> the code are stale: they are corrected to match this document, never the other way round. The
> old axis order is not a reference — it is work to be removed.


## 5 · The cheat sheet — how the plugin gets smart

The classifier does not rely on general knowledge: it consults a **cheat sheet**, a YAML cheatsheet
that is *data, not code*. Editing the YAML teaches the system a new machine or program without
touching a line of Python.

| Section | Entries today | Answers |
|---|---|---|
| `marcas` | 25 | who makes this |
| `programas` | 17 | programs (DaVinci Studio, Cyberpanel, Hermes Gateway…) **and how to configure them** |
| `productos` | 7 | model numbers and aliases |
| `companias` · `servicios` · `conceptos` · `logistica` · `sin_marca` | 5 · 3 · 7 · 5 · 3 | the rest of the world |

The personal layer (`cheat_sheet.personal.yaml`) is the owner's own: **his computers, his programs,
his drone, his camera** — every piece of equipment or program needs configuration, so the cheat sheet
also carries *how to use it*. Its `vocabulario`, `reglas` and `servicios` slots exist today but
are **empty**: the mechanism is built, filling it is the next step.

## 6 · Language

The catalogue is written in **English and Spanglish** — Spanish with the technical terms left in
English because they are what the owner actually says and searches for (`Troubleshooting`,
`Hardware`, `Data Backup`, `Gateway`). The **vocabulary file** exists precisely so the classifier
uses *his* words instead of translating them.

## 7 · The plugin workbench — live & testing modes

The desktop plugin (`desktop/plugin.js`) is the full interactive workbench and the fastest way to work.

- **Search** works because the description carries the keywords, so a half-remembered phrase
  finds the session.
- **Copy** and **Export** are its strongest features: copy a corrected title, export the
  corrections as CSV.
- **Side by side**: with the plugin open in the Desktop view next to a live session, the
  owner copies from the session, pastes into the search, and the plugin fixes the subject and
  **updates the cheat sheet** — the plugin gets smarter with each pass.
- **Bidirectional bridge**: Hermes reports a sequence of session numbers (`45, 76, 450, 32`), the
  owner pastes them into the plugin's search, opens each one and issues the corrections. That
  loop — *reach a large archive, improve it, and never let it rot* — is the main feature.

## 8 · Modularity (decision from session 897)

The renaming algorithm will keep improving. The plugin is built
so the nomenclature engine can be reused
outside Hermes — in OpenClaw, in another agent host, or standalone. Nothing in the algorithm
needs Hermes; only the write-back does.

## 9 · What the agent gains

Because the agent can talk to the plugin **over the CLI**, it can search the session database
better than by keyword: **relations between sessions**, series that belong to the same subject,
and reports built from those relations. The plugin does not only rename — it makes the archive
answerable.

## 10 · What exists today

| Surface | State |
|---|---|
| `register(ctx)` + `on_session_end` hook | **built** — refreshes `index.json` with `build(with_messages=False)` |
| `desktop/plugin.js` (catalogue page, nine axes) | **built** — `v0.25` |
| Agent tools | **built** — 10 tools declared and functional |
| Backend routes (`dashboard/plugin_api.py`) | **not built** — five routes, zero lines |
| Validator | `hermes plugins validate .` → **passed**, no warnings |

## 11 · Future star features

1. **External bookmarks.** Managed from the plugin, imported into the
   cheat sheet — the agent understands the owner better.
2. **The same algorithm for YouTube titles** — the same language, a different archive.
3. **Obsidian bridge.** A folder of `.md` files maintained externally, so the archive is
   searchable outside Hermes too.

## 12 · Architecture — one engine, native UI

The plugin provides a unified native interface with **Actual** and **Testing** tabs:

| Mode | Runs in | Reads | Writes |
|---|---|---|---|
| **Actual** | Hermes Desktop (`desktop/plugin.js`) | the live session database (`state.db`) | Read-only |
| **Testing** | Hermes Desktop (`desktop/plugin.js`) | simulated nomenclature over index/DB | Commit (`session.title`) with Revert |

Both views provide the full feature set: the same row shape, the same nine axes, the same
filters, the same search, the same detail card, the same copy/export. Testing mode enables safe
simulation with automated backups before writing back to Hermes.

## 13 · Acceptance criteria

```bash
hermes plugins validate .          # passed, no ⚠
python3 -m pytest tests/test_invariants.py -q
node tests/test_plugin.mjs
```

For UI work the window must match `docs/SPEC-UI.md`. **No network. No writes to `state.db`
outside the host API. No title write without a backup.**

## 14 · Doc sync owed

- `ALGORITHM.md` still lists `Date` as a **name field**; this page puts the date in **`iq5`**.
  `ALGORITHM.md` gets corrected, not this page.
- `SPEC-UI.md`'s axis names for `iq5`/`iq6` must match §3 (date, machine).

## 15 · Branding — one product, three names

The name is not repeated where the context already says it. Inside Hermes Desktop "Hermes" is noise.

| Context | Name | Where it lives |
|---|---|---|
| Short name **inside** the app | `Make It Smart` | `SIDEBAR_NAV_AREA` label in `desktop/plugin.js` |
| Full name **outside** the app | `Hermes, Make it Smart!` | repo description, README H1, release notes, `plugin.yaml` description |
| Plugin id | `hermes-make-it-smart` | `plugin.yaml` → `name:` |
| Storage key | `make-it-smart` | `core/paths.py` → `PLUGIN`; folder name under `desktop-plugins/` and `plugin-data/` |

Rules that follow from this:

- **Never** put "Hermes" in the sidebar label: the user is already inside Hermes.
- The exported `id` in `desktop/plugin.js` is the **storage key**, not the plugin id. It must match the
  folder name under `desktop-plugins/`, or the page will not mount.
- Renaming the id renames the data folders: migrate `plugin-data/<key>/` and
  `desktop-plugins/<key>/` together, then **fully restart** Hermes Desktop (⌘Q) — it scans the folder
  only at launch.

