# Pending Items

> **Naming note (2026-11-11).** This document is a historical snapshot from the
> 2026-11-10 session, so it still prints the names in use at that time. The current
> names are: repo `hermes-make-it-smart`, install/catalog name `hermes-make-it-smart`
> (`plugin.yaml`), and internal data id `make-it-smart` (`core/paths.py`, `desktop/plugin.js`).
> Paths below that say `make-all-my-work-smart` are history — the real data directory is
> `~/.hermes/plugin-data/make-it-smart/`. See `docs/DATA-PATHS.md` for the live map.

Status at the close of the **2026-11-10** session. Ordered by priority, not by
size.

## 1 · Rotate the DeepSeek key  🔴 urgent

The key pasted in session 23 ("API Key", 11-Aug) travelled inside the `claves`
field of the dataset, from there to the plugin UI and to this repo's history.
It is already redacted in `tools/sim80.json` and in the HTML (`[REDACTED-API-KEY]`),
but **sanitizing the files does not erase the history or what already travelled**.

Steps:

1. DeepSeek panel → revoke the 11-Aug DeepSeek key and create a new one.
2. Update `~/.hermes/auth.json` (hermes config / the credentials panel).
3. Check that Hermes responds with the new one.
4. Optional: rewrite this repo's history to purge the blob
   (`git filter-repo`). Only if it is decided that the repo will be published;
   with the key rotated the risk disappears and the history is not worth the work.

## 2 · Internal identifier — ✅ DONE (2026-11-11)

The internal id is `make-all-my-work-smart` everywhere, same as the visible
name. Verified: the index rebuilds at
`~/.hermes/plugin-data/make-all-my-work-smart/index.json` with **910 sessions**,
460 subjects, tag3 in 570 and tag4 in 854.

| File | Before | Now |
|---|---|---|
| `core/paths.py` | `PLUGIN = "make-my-work-smart"` | `"make-all-my-work-smart"` |
| `desktop/plugin.js` | `ID = 'make-my-work-smart'` | `'make-all-my-work-smart'` |
| `README.md`, `docs/STORAGE.md`, `tests/` | old id | new id |

The data directories were **copied** (`cp -R`) to
`~/.hermes/plugin-data/make-all-my-work-smart/` and
`~/.hermes/desktop-plugins/make-all-my-work-smart/`. The old directory is still
in place: it is only deleted after restarting Desktop and seeing that it loads.

## 3 · The 15 sessions with subject = brand

```
41,71,76,80,93,102,110,136,137,139,218,365,446,454,835
```

They are pasted into the plugin's search box as is. The rule: the brand goes in
tag1 and the subject describes what was done with it. Watch out for the two
cases that Jorge himself already resolved earlier:

- **365 Pinokio** → tag1 `Pinokio`, subject `Control CLI`.
- **93** → the correct subject is `Unsloth Studio` (the one compared), not Ollama.

And the saved exception: if removing the brand leaves the subject meaningless (`Bot`,
`3.8 27B`), **it is not removed** — an empty subject is worse than a repeated one.

## 4 · Refine the tag rules

Jorge left it for tomorrow. Useful context: out of **460 subjects**, **369 appear
only once**; four of them concentrate 206 sessions. The full map is in
`~/Documents/Reportes - [Lisa]/2026-11-10_[reporte]_sujetos-del-plugin-frecuencia.md`.

## 5 · Run the evaluation set

`tests/eval/` and the 50-session set are frozen and **have not been run against
the new schema**. Without that, refining the rules is guesswork.

## 6 · Publish the delivery repo — Wednesday

```bash
gh repo edit tesla963/make-all-my-work-smart \
  --visibility public --accept-visibility-change-consequences
```

Only that repo. `hermes-make-all-my-work-smart` (data and internal documents)
stays private **always**.

## 7 · Cron hygiene notice — ✅ implemented in the native plugin

A cron job with a monitor leaves empty sessions (Hermes bug #140222: the session
is created before the gate decides that there is nothing to report). The plugin
now detects it and says so.

**Done (2026-11-11):**

- Detection of `source=cron` sessions with no message at all and the live cron
  jobs by reading `~/.hermes/cron/jobs.json`.
- The template paints a banner above the table, in ES/EN. **It does not order a pause:**
  it names the cause with a link to the [issue #140222](https://github.com/NousResearch/hermes-agent/issues/140222),
  points out the direction (pause and recreate in `no_agent` mode) and makes clear that
  the panel does not touch the cron jobs: that is asked of the Hermes agent.
- Button to copy the ready-made text: «Lisa, I have N empty cron sessions…».
- **"Vacío"/"Empty" filter**, the third one in the status row and **enabled by
  default**: sessions with no messages do not appear in the listing. It is
  disabled with one click.
- Hours in **active time** (intervals between messages < 30 min), in whole
  minutes and with days once it goes past 24 h (`1d 20h`). Before, it was
  computed open→close and a session reopened over months marked 2.019 hours.

**Project rule:** the panel only paints and reports. Pausing jobs, deleting sessions or
writing to the database belongs to the owner or their agent. "We are not invited to that wake."

**Pending (once `desktop/plugin.js` exists):**

| Piece | Status |
|---|---|
| The same notice in the plugin panel, on import | not started |
| Button to pause the job from the UI | not started — the panel only paints by design |
| Link to issue #140222 as long as there is no upstream fix | not started |

**Why it makes the MVP:** detecting it is one query and one JSON read; the
generator already opens the 12 databases. Without the notice, the user blames the
plugin for garbage that the cron generated.

## Status at close

```
Hermes database    848 titles written through the official API · 809 sessions
                   46 empty cron sessions deleted on 2026-11-11
catalog            864 sessions · 851 with a subject · 570 with an intent
cron jobs          0 — the 4 deleted; definitions in the 11-nov registry
repos              work: code, 0 data · delivery: native plugin
```
