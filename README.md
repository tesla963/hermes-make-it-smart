# Hermes, Make it Smart!

**Session categorization, tagging and renaming to access all your sessions — faster than it takes to press 3 clicks.**

A Hermes Desktop plugin that turns hundreds of undifferentiated chat sessions into a
browsable, faceted catalog — and gives every session a name that actually means something.

---

## The problem

After a few months of daily work, a Hermes install accumulates hundreds of sessions.
They are called `Chat`, `Session 2026-10-28`, or the title of whatever sentence happened
to be first. Finding "that session where I debugged the DNS records" means scrolling.

Search helps only if you remember a word. It does not answer:

- How many sessions did I spend on my VPS this quarter?
- What did I actually do across the eleven sessions about the same subject?
- Which of my work fronts got the most of my time?

An agent that forgets the shape of your work is an agent you have to re-brief every day.

## What it does

1. **Indexes** every session from every Hermes profile into its own read-only index —
   **all of them**, titled or not. A session with no canonical title is not skipped: it
   gets a number after the last one in use. Importing is not a filter.
2. **Classifies** each one — subject, maker, context, intention, theme, year — using a
   host-agnostic pure module plus a language model. Empty fields are allowed and are
   never filled with the previous schema's leftovers.
3. **Renames** them into one canonical, sortable, telegraphic format (below), writing
   through the host's public title API.
4. **Presents** them as a facet catalog: filters with live counts, a synonym-aware
   search, a detail pane, and a map of where a word appears across the archive.
5. **Unifies** historical sessions that share a subject, so the `MMM` ordinal tells you
   at a glance that eleven sessions were one continuous piece of work.

## The paper trail

Everything the project produced while the algorithm was being decided — plans,
reports, evaluation sets and the CSVs the renames came from — is in
[`reports/`](reports/INDEX.md), with an index that says what each file is and
whether it still rules or is history.

## The naming format

```
NNN [Subject] MMM [Iq1] [Iq2] Description · Verb
```

| Part | Question it answers | Example |
|---|---|---|
| `NNN` | global sequence, never reused | `748` |
| `[Subject]` | *what* the session is about | `[Air 2S]` |
| `MMM` | which one of the series — the ordinal, **outside** the bracket | `003` |
| `[Iq1]` | *who/what* is the real protagonist | `[DJI]` |
| `[Iq2]` | *what kind of work* | `[Ebay]` |
| `Description` | everything the three previous fields could not say | `Compare the Fly More bundle` |
| `· Verb` | the action taken, as an appendix | `· Comparar` |

The ordinal stays outside the bracket on purpose: inside, a reader takes
`Air 2S 003` for the subject's name instead of its counter. There is no date —
the date is a column and a filter, and repeating it spends six characters of a
hundred to say something the table already says.

The result reads like a telegram. Three fields carry a complete idea:

```
748 [Air 2S] 003 [DJI] [Ebay] Compare the Fly More bundle · Comparar
```

Change the marketplace and the same shape still works:

```
812 [Trace Minerals] 001 [Dr. Berg] [Amazon] Evaluate the supplement facts · Analizar
```

That is the core insight of this project: **subject + two axes is enough to express a
complete idea, if each field answers exactly one question.**

The full rules live in [`docs/ALGORITHM.md`](docs/ALGORITHM.md).

## Install

[`docs/GUIA-DE-USO.md`](docs/GUIA-DE-USO.md) — the order that matters: back up,
define the pillars, feed the battery, look in the simulator, correct,
apply. The plugin is worth exactly what the names you have taught it are worth.

```bash
git clone https://github.com/tesla963/hermes-make-it-smart
cd hermes-make-it-smart

# 1. build the index the window reads (Python, reads state.db read-only)
~/.hermes/hermes-agent/scripts/run-in-hermes-env python3 tools/build_index.py

# 2. copy the plugin where Hermes Desktop looks for it
mkdir -p ~/.hermes/desktop-plugins/make-it-smart
cp desktop/plugin.js ~/.hermes/desktop-plugins/make-it-smart/

# 3. restart Hermes Desktop, then open "Make It Smart" in the sidebar
```

The plugin never touches `state.db`: step 1 reads it and writes one JSON file to
`~/.hermes/plugin-data/make-it-smart/index.json`, and the window only paints
that file. Re-run step 1 (or press **Refresh DB**) whenever you want new sessions
in the catalogue.

### Two names, on purpose

The manifest name and the data-directory name are different, and that is by design:

| What | Value | Where it comes from |
|---|---|---|
| Install / catalog name | `hermes-make-it-smart` | `plugin.yaml` → `name:` — this is the folder `hermes plugins install` creates |
| Internal data id | `make-it-smart` | `core/paths.py` → `PLUGIN`, and `desktop/plugin.js` → `ID` — this is the folder under `plugin-data/` |

So an install from the catalog puts the code in
`~/.hermes/desktop-plugins/hermes-make-it-smart/` while its data stays in
`~/.hermes/plugin-data/make-it-smart/`. Both are correct; see
[`docs/DATA-PATHS.md`](docs/DATA-PATHS.md) for the full map. Changing either name
orphans the existing index, so neither is renamed.

### Verify without the app

```bash
node tests/test_plugin.mjs      # 22 checks: shape, register(), first render, helpers
python3 tests/test_invariants.py   # 11 checks on the naming rules
```

The plugin smoke test loads the real `desktop/plugin.js` against the real React
and renders a frame, so a bad import or a syntax error fails here instead of
showing a white screen.

## Host-agnostic by design

> The classifier is host-agnostic: a pure module that turns session records into facets.
> The Hermes adapter is one implementation; the interface is documented for other hosts.

```
core/           Python, zero imports from Hermes
  taxonomy.py   pillars, platforms, IT families
  prompt.py     the classifier system prompt
  normalize.py  subject extraction, MMM ordinals, telegram mode
  classify.py   LLM + deterministic rules
adapters/
  hermes.py     SessionDB, state.db, write-through-title-API
desktop/
  plugin.js     the catalog UI on the Desktop SDK
```

`core/` never imports `hermes_state`. The boundary is a single normalized record:

```python
SessionRecord = {
    "id": str, "title": str, "title_source": str,
    "created_at": str, "messages": list[str],
    "cost_usd": float, "hours": float,
    "tokens": int, "posts": int,
}
```

Any host that can produce that record can use the classifier. Porting is a new adapter,
not a rewrite. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Writes go through the host API — always

This plugin **never** opens `state.db` to write. Renaming goes through `SessionDB`:

```python
from hermes_state import SessionDB

db = SessionDB()
db.set_session_title(session_id, title)   # 'user' provenance, always wins
```

That single call gives us, for free:

- **Provenance ladder** — `derived (0) < llm (1) < user (2)`. A user-set title is never
  overwritten by an automatic one.
- **Atomic compare-and-swap** — read and write happen in one transaction, so a rename
  racing the title generator loses instead of clobbering.
- **Duplicate resolution** — a compressed ancestor, an archived Bot Chat, or an abandoned
  empty session holding the same title is released; only a genuine conflict raises.
- **Sanitizing** — control, zero-width, bidi and lone-surrogate characters stripped, and
  the hard 100-character limit enforced.
- **Bot Chat protection** — the canonical Bot Chat's name *is* its identity.

Reads are read-only (`mode=ro`) and therefore safe to run while Hermes is working.

## Why this needs a plugin, not a prompt or a skill

A skill can advise. This plugin has to:

- open twelve SQLite databases and build an index,
- call a model per session and reconcile the result with deterministic rules,
- write titles back through the host's transactional API,
- and paint a native, faceted UI that reads and filters 900 rows without lag.

None of that is expressible as a prompt.

## Installation

```bash
# 1. install the plugin (the panel, the ten agent tools and the indexer)
hermes plugins install https://github.com/tesla963/hermes-make-it-smart --enable

# 2. build the index the panel paints — this is what names your sessions
cd ~/.hermes/plugins/hermes-make-it-smart
~/.hermes/hermes-agent/scripts/run-in-hermes-env python3 tools/build_index.py

# 3. restart Hermes Desktop and open "Make It Smart" in the sidebar
```

`hermes plugins install` downloads the whole repository — `plugin.yaml`, `tools/`, `core/`,
`desktop/plugin.js` — into `~/.hermes/plugins/hermes-make-it-smart/`; Electron copies the panel
from there into its own folder when the plugin is enabled, so nothing has to be copied by hand.

Step 2 is not optional: the panel only paints `index.json`. Installed without it, the window
opens but shows your sessions with the names Hermes gave them, unclassified — the plugin looks
broken when it is only unindexed. From then on you can re-run that command, or just ask Hermes
*"reindex the plugin catalogue"* (the `cellar_index` tool does the same thing).

Requires Hermes Agent with plugin support. Python 3.11+.

### Upgrading from 0.26.x or older

Nothing to do by hand. The panel reads both key sets, so `tag0`…`tag9` data keeps painting
correctly after the upgrade, and the first reindex migrates it: `tools/build_index.py` calls
`tools/migrate_axes.py` before rebuilding, which copies the old files to
`~/.hermes/plugin-data/make-it-smart/backups/`, renames the keys to `iq0`…`iq9`, stamps
`"schema": 2` and rewrites them atomically. Running it twice is harmless — the second pass
reports `already-current`.

## Disclosure

- **Reads** every profile's `state.db` in read-only mode to build its index. It does not
  modify anything while indexing.
- **Sends** short excerpts of each session (sampled user turns, cleaned of attachments
  and URLs) to the chat model you configure, to classify them. Nothing else leaves the
  machine.
- **Writes** session titles only when you press Rename, through `SessionDB`, with a
  timestamped backup taken first.
- **Never** edits `config.yaml`, never disables the host's own title generator, and leaves
  no state behind if removed.

## License

MIT — see [`LICENSE`](LICENSE).

The MIT license was chosen deliberately: this is a tool meant to be copied, forked and
built upon by anyone who keeps a long-running Hermes. The documentation in `docs/` is
part of the deliverable, not an afterthought — if our reasoning is not written down, it
cannot be reused.

---

Built by Jorge Matsufuji with Lisa (Hermes Agent), Panama, 2026.
