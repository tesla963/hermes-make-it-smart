# Uninstalling the plugin

The plugin writes to two places, and they are not the same thing:

| Where | What it holds | Survives an uninstall? |
|---|---|---|
| `~/.hermes/plugin-data/make-it-smart/` | `index.json`, `facets.json`, `backups/` | **Yes** — nothing deletes it |
| `~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/` | the copy the panel paints, the commit backups, `titles-journal.jsonl`, `titles-origin.json` | **Yes** |
| each profile's `state.db` | the **session titles** already committed | **Yes** — and this is the one that matters |

Removing the plugin removes the window and the tools. It does **not** revert the titles it
already wrote: those live in Hermes' own database and stay there, renamed.

## The order that leaves nothing behind

1. **Restore the original titles first.** In the panel, **Testing** tab → *Restore original
   titles*. It reads `titles-origin.json`, which keeps the first title the plugin ever saw for
   each session, and writes it back through the host's own API. Nothing to undo afterwards.
2. Confirm the catalogue looks like it did before the plugin (`/sessions` still shows the
   sessions, with their old names).
3. Then remove it:

```bash
hermes plugins remove hermes-make-it-smart
```

4. If you also want the derived data gone, delete the two folders by hand — they are the
   plugin's, not Hermes':

```bash
~/.hermes/plugin-data/make-it-smart/                                     # index, facets, backups
~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/    # panel copy + journal
```

Nothing in Hermes breaks if you delete them: the plugin rebuilds the index from `state.db` on
the next install.

## If the plugin is already gone

`titles-journal.jsonl` and `titles-origin.json` are plain JSON, kept on purpose, so the record
is not lost with the app:

- `titles-origin.json` — `{ "<session id>": { "title": "<original title>", "ts": "…" } }`
- `titles-journal.jsonl` — one line per commit: `{ ts, count, changes: [{ id, before, after }] }`

With them you can put the titles back by hand: for each `id`, set the session's title to
`title` (what the plugin would have done), using whatever Hermes gives you — its own API, its
UI, or `sqlite3` against `state.db` **with the app closed and a copy taken first**.

## What a fresh start looks like

Reinstalling later is clean: the panel reads whatever `index.json` it finds, migrates it if it
is in the pre-0.27.0 shape (with a backup), and rebuilds it from `state.db` when you run
`tools/build_index.py`.
