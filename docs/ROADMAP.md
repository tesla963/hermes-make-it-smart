# Roadmap and architecture decisions

Decisions taken on 2026-11-09, recorded so they are not re-argued later.

## 1 · Nine tags, and the numbering was settled on 2026-11-10

The session title shows two tags, but the **data model carries nine**. The owner
reorganised what each slot means on 2026-11-10; the 2026-11-09 meanings are dead.

```
tag1  maker — adjective for the subject      tag6  reserved
tag2  context — store, country or machine    tag7  reserved
tag3  intention — seven, closed              tag8  reserved
tag4  theme                                  tag9  reserved
tag5  year
```

Only `tag1` and `tag2` reach the name. `tag3`, `tag4` and `tag5` are filters.

Why nine and not five: gaining intelligence later must not cost a schema
migration. A new axis is a column already present, not a rewrite of 909 titles
and every query. An unused tag is not waste; it is a socket.

Why the meanings changed: tag2 had become a sack — it held work families, themes
and intentions in one column, so no filter built on it could be trusted, and the
same value meant "WebHosting" in one session and "Comparar" in another. Splitting
it cost one re-classification and bought three filters that mean exactly one
thing each. The machine moved into tag2 because a machine is context, exactly
like a store: `ThinkPad P53 · Lenovo · Mac mini M4` reads as one idea.

**Tag6 is no longer the machine** — it is reserved, like 7, 8 and 9.

## 2 · The renaming engine is not the plugin

The boundary, in one sentence:

> The engine turns records into facets. It knows nothing about Hermes.

```
core/                    pure Python, zero host imports
  taxonomy.py            pillars, platforms, families, verbs
  prompt.py              the classifier prompt
  classify.py            LLM + rules
  normalize.py           rendering, the 100-char ceiling, telegraph mode
  bateria.yaml           the owner's cheat sheet
  corrections.yaml       41 learned rules
adapters/
  hermes.py              one implementation: SessionDB, state.db, 12 profiles
  openclaw.py            (future) the same contract, another host
desktop/plugin.js        one window: this app's page and sidebar
tools/                   CLIs: index, audit, export, report, rename
```

**Whoever wants this on another agent takes `core/` and writes an adapter.**
They own their own glue. Support for their host is theirs, not ours — that is
explicit, and it is what keeps the maintenance surface honest.

## 3 · The engine also reads YouTube

The same classifier that names a session can name a video. The inputs differ,
the contract does not:

| | Session | YouTube video |
|---|---|---|
| id | `session_id` | `video_id` |
| title | `sessions.title` | the video's title |
| body | `messages` | **transcript** |
| facets | out: subject, tags, pillar | the same |

Video titles are frequently bad at saying what the video is about, so the
engine proposes a better one from the transcript. This is not a separate
product: it is the same `classify()` with a different reader.

## 4 · Bookmarks: a paid module, not in the repo

A bookmark module that ingests YouTube tabs (via the Obsidian plugin and the
browser) and files them **next to the sessions** makes the catalog smarter: the
same facets, the same search, the same reports, one more source.

Decisions:

- It is a **separate module**, distributed privately, **not** in the public repo.
- The free plugin keeps working without it. No crippled free tier — a clean seam.
- Business model: **open core, paid support** (the Red Hat shape). Copy the code,
  use it free; if you want help, you pay.

### The security question, still open

A plugin that installs plugins is a privilege escalation surface: it decides
what code runs next. Before shipping one, verify:

1. Whether the Nous catalog rules allow a plugin to install other plugins.
2. What the sandbox actually bounds — filesystem, network, `ctx.files` scope.
3. Whether the hosted module needs the user's browser cookies or only a file the
   user exports themselves. **File-in beats credential-in**, always.

Until those three are answered with evidence, the bookmarks module stays a
local tool, not a distributed plugin.

## 5 · "Actualizar BD" — the incremental pass

The open question was *when* the plugin names the sessions that have none.
Answer: **on demand, from the window.**

```
[ Limpiar ] [ Copiar · N ] [ Exportar · N ] [ Actualizar BD ]
```

The button runs the pipeline and reports what it did:

1. Read the twelve databases.
2. Take every session whose title is **not** canonical (or whose content changed
   since the last pass, by hash).
3. Classify only those — never the 884 again.
4. Write through `SessionDB.set_session_title`.
5. Rebuild `index.json` and repaint.
6. Report: *"7 nuevas clasificadas, 0 conflictos, 877 sin cambios."*

A session already canonical is never touched, so the pass is idempotent and
cheap. That is what makes it safe to press.

## 6 · What is deliberately not done

- **No auto-renaming on session close.** The owner reviews; the machine proposes.
- **No schema for the seven unused tags yet.** They exist as fields; their
  semantics get decided when a real axis needs one.
- **No write to `state.db` outside `set_session_title`.** Reading is free;
  every write goes through the host's own API.
- **No cloud dependency.** The index is local, the classifier runs on the
  configured model, and a machine with no network still browses its history.
