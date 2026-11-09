# The Naming Algorithm

Every field answers **exactly one question**. If two fields answer the same question, the
catalog stops being navigable and becomes a list. This is the rule that governs all others.

## 1. The format

```
NNN [Subject MMM] [Tag1] [Tag2] Date Description · Verb
```

Hard limit: **100 characters**. Priority when space runs out:

```
Subject  >  Tag1  >  Tag2  >  Date  >  Description  >  Verb
```

The subject and the tags are never truncated. The description is compressed (telegram
mode) before it is cut. The verb is the first thing dropped.

## 2. NNN — the global sequence

- Computed as `total_sessions + 1`, **never** `max(nnn) + 1`. A gap in the sequence is a
  bug, not a feature.
- Width `max(3, len(str(total+1)))`; grows to four digits at 1000.
- Stable once assigned. Never renumbered.

## 3. Subject — what the session is about

The **object, problem or symptom**, in 2–4 words. Never the program.

**Rules**

| Rule | Why | Example |
|---|---|---|
| Strip the action prefix, keep the core | The verb goes to the description | `Suplemento Vitamina C` → `Vitamina C` |
| Drop state adjectives | "inusual", "trancado", "con error" describe, not name | `Dolor Interoseos` → `Interoseos` |
| Name the failure point | It is what you will search for later | `Protocolo` for a broken gateway |
| Never repeat Tag1 | Two fields, one answer = not navigable | If Tag1 is YouTube, the subject is `Transcripción` |
| Never repeat the platform in the subject | Same reason | `Video` was removed from a YouTube subject |

**The control question:** *would this subject help me find this session in six months?*

## 4. MMM — the series ordinal

This is what makes the catalog a *history* rather than a list.

- Ordinal per **normalized subject** (case-insensitive, bracket-bounded), stored in a
  counter table with `BEGIN IMMEDIATE`.
- Recalculated in chronological order, with **no gaps**.
- `[Air 2S 001]`, `[Air 2S 002]`, `[Air 2S 003]` — eleven sessions about the same subject
  read as one continuous body of work.
- Grows to four digits when a subject passes 999.

**The value:** it unifies historical sessions that predate the taxonomy. Nothing is
merged or deleted; the ordinal simply says *these belong together, and in this order*.

## 5. Tag1 — the protagonist

**Who or what is really doing the work.**

- A platform, a brand, a product, a real actor. `Hermes Agent`, `CyberPanel`, `DJI`,
  `Brave`, `Logseq`.
- If the session is not about software, or nothing else fits → `Hermes Agent`.
- **Never** the operating system by default. "macOS" explains almost every session and
  therefore explains nothing.
- Use the full product name, never an abbreviation: `Hermes Agent`, `Hermes Desktop`,
  `Hermes Terminal`, `Hermes Telegram` — never just "Hermes".

### The product-analysis pattern (marketplace)

When the session is about evaluating or buying a product, the shape is:

```
Tag1 = the brand        Tag2 = the marketplace
```

| Session | Subject | Tag1 | Tag2 |
|---|---|---|---|
| Used drone listing | `Air 2S` | `DJI` | `Ebay` |
| Supplement research | `Trace Minerals` | `Dr. Berg` | `Amazon` |
| USB-C enclosure | `Case USB` | `ORICO` | `Comparación` |

Read in one breath: **what** it is, **who** makes it, **where** we looked.

This is the strongest expression of the algorithm: three fields, a complete idea,
telegraphic, in under 40 characters.

## 6. Tag2 — the work family

**What kind of work this was.**

- **IT families:** IA, Data Mining, Automation, WebHosting, Troubleshooting, VPS,
  Data Security, Multimedia, Productivity, MCP/CLI, File System, IT Manager, Data Backup,
  Programming, Networking, Data Recovery, Repository.
- **Non-IT families:** Derecho Constitucional / Penal / Civil, Educación, Medicina,
  Nutrición, Compras, Geopolítica.
- **Troubleshooting** only when you *report something failing* — not when it is merely
  mentioned.
- **Marketplace** when the work was evaluating a listing.

**The control question:** *does this tag add anything about what the session is?*
If the subject already says it, remove it.

## 7. The internal tags (filters only, never in the title)

| Tag | Question | Values |
|---|---|---|
| Tag 3 · Pillar | which work front | 10 pillars |
| Tag 4 · Country | where | Panama, … |
| Tag 5 · Year | which edition | 2026, … |
| Tag 6 · Machine | which computer | Mac mini M4, VPS, Teléfono, P53, E580, T480s, Varios |

The pillar is **never** written into the title. Measured: adding it leaves 877 of 884
titles with no description at all.

**The ten pillars:** Asistente IA · VPS · Compras · Data Backup · Derecho · Youtuber ·
MindMap · Geopolítica · Masoterapia · Temas Varios (always last, even when it is largest).

## 8. The date

Short, lowercase, Spanish month: `19ago`, `07nov`. It sits between the tags and the
description so the eye can skip it.

## 9. The description — and its verb appendix

**Parameters**

| Rule | Value |
|---|---|
| Minimum to appear | 18 characters **and** 3 words |
| If it does not fit | **Telegram mode** first: drop articles and prepositions, keep the first word |
| If it still does not fit | Omit entirely — a cut phrase is worse than nothing |
| Language | Spanish, telegraphic, no filler |
| Content | only what subject + tags could not say |
| Ending | ` · Verb` — the action, as an appendix |

**The verb appendix**

The description says *what*; the verb says *what was done*. It is separated by a middle
dot and capitalised. It is the last field to survive and the first to be dropped.

| Verb | Use |
|---|---|
| `Investigar` | searching for something unknown |
| `Verificar` | confirming a suspicion or a state |
| `Comparar` | evaluating options |
| `Configurar` | changing settings |
| `Instalar` | bringing something into the machine |
| `Organizar` | restructuring existing material |
| `Analizar` | reading something to extract conclusions |
| `Respaldar` | copying for safety |
| `Corregir` | fixing an error |
| `Documentar` | writing it down for later |

**Example**

```
748 [Air 2S 003] [DJI] [Ebay] 19ago Compare the Fly More bundle · Comparar
```

Description: `Compare the Fly More bundle`. Verb: `Comparar`.

## 10. When subject and Tag1 collide

If they are nearly the same, **something is wrong**. The subject names a *thing or a
problem*; the tag names the *platform*. 187 sessions were corrected on this rule alone.

Legitimate exceptions exist — `[Precios Amazon] [Amazon] [Comparación]` — where the
subject is genuinely a topic, not a platform. Judge each case; do not apply the rule
blindly.

## 11. Corrections are part of the algorithm

Every correction the user dictates is:

1. written into `core/corrections.yaml` as a rule with examples,
2. injected into the classifier prompt as few-shot evidence,
3. added to the evaluation set as a regression test.

The algorithm does not "learn" by itself — it learns because a correction that is not
written down is a correction that will be made again. See
[`CORRECTIONS.md`](CORRECTIONS.md).
