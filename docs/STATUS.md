# Status — what actually works

Last verified: 2026-11-10, on the author's machine (12 profiles, 909 sessions).

## Working

| Piece | Evidence |
|---|---|
| Read-only adapter | Opens 12 `state.db` files, reads **909 sessions** (titled or not), never writes |
| Message cleaning | Strips attachments, group-chat envelopes, compaction carriers, cron preamble |
| Title rendering | Produces titles ≤100 chars, telegram fallback, verb appendix |
| Title writes | Through `SessionDB.set_session_title`: 848 written, 11 refused by the host (canonical Bot Chat), 50 skipped when the model found no evidence |
| Taxonomy folding | Model output is folded onto the 2026-11-10 vocabularies: makers, contexts, 7 intentions, themes |
| Classification | **10 of 10 sessions classified by the model, 0 fallbacks**, ~1,480 prompt tokens |
| Title write API | `SessionDB.set_session_title`, atomic, provenance-safe, batch receipt |
| Invariants | **11/11** unit tests pass, including "`core/` never imports the host" |
| Hygiene notice | Cron sessions with zero messages (and live cron jobs) surface as a banner above the table, with a copy-to-clipboard request for the assistant. Verified 2026-11-11: appears at 46 empties / 2 jobs, translates ES/EN, copies |

## Real output from the last run

```
748 [Modo Desarrollador 001] [Mac mini] [Troubleshooting] 28ago A55 no responde taps · Configurar   (97c)
754 [Case USB 007] [ORICO] [File System] 17oct medir velocidad case nuevo frente disco · Comparar   (97c)
755 [Gorgon Halo 192GB 008] [AMD] 27oct Jorge espera chip antes comprar; rastreo · Monitorear       (93c)
757 [Equipos 192GB 010] [Gorgon Halo] [Automation] 06nov vigilar anuncios Framework · Monitorear    (96c)
```

## Three failures found and fixed — read these before changing the model code

**1. `max_tokens` below ~1000 returns an empty string.**
The model spends part of the completion budget reasoning (`reasoning_tokens`), so
`finish_reason` came back `length` with `content: ""`. It looked like the API was broken.
It was not. **Keep `max_tokens` at 1200.**

**2. Cron sessions have no human subject.**
A scheduled job's first "user" message is
`[IMPORTANT: You are running as a scheduled cron job. DELIVERY: …]`.
Without stripping it, the classifier names the session after the wrapper. The adapter now
removes `[IMPORTANT:`, `[SYSTEM:` and `[REMINDER:` preambles before the text reaches the
model.

**3. The model invents brands.**
Asked about "a new drive case", it answered `iq1: ORICO` because ORICO is in the platform
list. A plausible brand is worse than no brand. The prompt now forbids naming a brand the
messages do not evidence, and the fallback folds unknown platforms to `Hermes Agent`.

## Not built yet

| Piece | State |
|---|---|
| `desktop/plugin.js` | Built — native catalog UI with Actual & Testing tabs, Commit, Revert, and facets |
| `dashboard/plugin_api.py` | Not started — the five planned routes |
| `POST /rename` from the UI | Not started; the writer class is ready |
| Subject unification report | Designed (`GET /report/{subject}`), not built |
| Evaluation set | Planned: 50 sessions labelled by hand |

## Cost reference

One classification run on 10 sessions: ~1,480 prompt tokens each, ~400 reasoning tokens,
~150 answer tokens. At `deepseek-flash` off-peak rates that is well under one cent for ten
sessions. Classifying all 908 would cost roughly **$0.40**, and the prompt cache makes
repeat runs cheaper (1,408 of 1,543 prompt tokens hit the cache on the second call).
