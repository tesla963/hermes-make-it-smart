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

## 3 · The nine tag slots

Nine slots, so a new axis never forces a migration. Six in use, three reserved.

| Slot | Axis | What it holds | In the title |
|---|---|---|---|
| **iq1** | Protagonist | brand, **or program / platform / service** | yes |
| **iq2** | Context | place, machine, country, store | yes |
| **iq3** | Intention | closed vocabulary — see §4 | no |
| **iq4** | Theme | work front, or a sub-theme under it | no |
| **iq5** | **Date** | when it happened | no |
| **iq6** | Machine | which computer | no |
| **iq7** | *free* | reserved | no |
| **iq8** | *free* | reserved | no |
| **iq9** | *free* | reserved | no |

**The date is `iq5`** — not part of `iq2`, and not part of the name. The name says *what*; the
tags say *when, where and why*.

## 4 · The code is still on the old axis order

Both vocabularies are closed in code — a free-form tag is a filter that cannot be clicked twice —
but **the axes are mapped the old way**, and that is the real work item:

| In the new nomenclature (§3) | What `core/taxonomy.py` actually implements |
|---|---|
| iq2 = **context** (place, machine, country, store) | **iq2 = work family**: `IT_FAMILIES` (IA, Data Mining, Automation, WebHosting, **Troubleshooting**, VPS, Data Security, Multimedia, Productivity, MCP/CLI, File System, **IT Manager**, Data Backup, Programming, Networking, Data Recovery, Repository), `NON_IT_FAMILIES` (Derecho Constitucional/Penal/Civil, Educación, **Medicina**, **Nutrición**, Compras, Geopolítica) and `MARKET_FAMILIES` (Ebay, Amazon, Comparación) |
| iq3 = **intention** | **iq3 = pillar**: `PILLARS` (Asistente IA, VPS, Compras, Productos, Servicios, Data Backup, Derecho, Youtuber, MindMap, Geopolítica, Masoterapia, Temas Varios) |
| iq4 = **theme** | exists only as `IT_SUBCATEGORIES` (IA Bot, VPS, Data Backup, Hardware, MindMap, Network, OS) + `OTHER_THEMES`, not as iq4 |

Every value from your four example cases **does exist** — `Troubleshooting`, `IT Manager`,
`Medicina`, `Nutrición`, `Ebay`, `Amazon` — but they sit on the wrong axis today. `Compra` is the
only one missing: the code has `Compras` as a family and as a pillar, never as an intention.

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


## 5 · The batería — how the plugin gets smart

The classifier does not rely on general knowledge: it consults a **batería**, a YAML cheatsheet
that is *data, not code*. Editing the YAML teaches the system a new machine or program without
touching a line of Python.

| Section | Entries today | Answers |
|---|---|---|
| `marcas` | 25 | who makes this |
| `programas` | 17 | programs (DaVinci Studio, Cyberpanel, Hermes Gateway…) **and how to configure them** |
| `productos` | 7 | model numbers and aliases |
| `companias` · `servicios` · `conceptos` · `logistica` · `sin_marca` | 5 · 3 · 7 · 5 · 3 | the rest of the world |

The personal layer (`bateria.personal.yaml`) is the owner's own: **his computers, his programs,
his drone, his camera** — every piece of equipment or program needs configuration, so the batería
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
  **updates the batería** — the plugin gets smarter with each pass.
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
| `desktop/plugin.js` (catalogue page, nine tags) | **built** — `v0.25` |
| Agent tools | **built** — 10 tools declared and functional |
| Backend routes (`dashboard/plugin_api.py`) | **not built** — five routes, zero lines |
| Validator | `hermes plugins validate .` → **passed**, no warnings |

## 11 · Future star features

1. **External bookmarks.** Managed from the plugin, imported into the
   batería — the agent understands the owner better.
2. **The same algorithm for YouTube titles** — the same language, a different archive.
3. **Obsidian bridge.** A folder of `.md` files maintained externally, so the archive is
   searchable outside Hermes too.

## 12 · Architecture — one engine, native UI

The plugin provides a unified native interface with **Actual** and **Testing** tabs:

| Mode | Runs in | Reads | Writes |
|---|---|---|---|
| **Actual** | Hermes Desktop (`desktop/plugin.js`) | the live session database (`state.db`) | Read-only |
| **Testing** | Hermes Desktop (`desktop/plugin.js`) | simulated nomenclature over index/DB | Commit (`session.title`) with Revert |

Both views provide the full feature set: the same row shape, the same nine tags, the same
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

