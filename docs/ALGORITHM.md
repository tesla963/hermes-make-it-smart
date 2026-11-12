# The Naming Algorithm

Every field answers **exactly one question**. If two fields answer the same question, the
catalog stops being navigable and becomes a list. This is the rule that governs all others.

## 1. The format

```
NNN [Subject MMM] [Iq1] [Iq2] Date Description · Verb
```

Hard limit: **100 characters**. Priority when space runs out:

```
Subject  >  Iq1  >  Iq2  >  Date  >  Description  >  Verb
```

The subject and the axes are never truncated. The description is compressed (telegram
mode) before it is cut. The verb is the first thing dropped.

## 2. NNN — the global sequence

- Computed as `total_sessions + 1`, **never** `max(nnn) + 1`. A gap in the sequence is a
  bug, not a feature.
- Width `max(3, len(str(total+1)))`; grows to four digits at 1000.
- Stable once assigned. Never renumbered.
- **Every session gets a number, titled or not.** The first importer only read
  titles that already had the `NNN [Subject] MMM` shape, so 25 sessions — six
  without a title and nineteen with a free-form one — were silently left out of
  the catalogue. They are now read like any other and numbered after the last
  number in use, oldest first. *A catalogue that skips what does not fit its
  format is not a catalogue of the archive; it is a catalogue of the archive's
  good examples.*

## 3. Subject — what the session is about

The **object, problem or symptom**, in 2–4 words. Never the program.

**Rules**

| Rule | Why | Example |
|---|---|---|
| Strip the action prefix, keep the core | The verb goes to the description | `Suplemento Vitamina C` → `Vitamina C` |
| Drop state adjectives | "inusual", "trancado", "con error" describe, not name | `Dolor Interoseos` → `Interoseos` |
| Name the failure point | It is what you will search for later | `Protocolo` for a broken gateway |
| Never repeat Iq1 | Two fields, one answer = not navigable | If Iq1 is YouTube, the subject is `Transcripción` |
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

## 5. Iq1 — the protagonist

**Who or what is really doing the work.**

- A platform, a brand, a product, a real actor. `Hermes Agent`, `CyberPanel`, `DJI`,
  `Brave`, `Logseq`.
- If nothing fits, **leave it empty**. `Hermes Agent` as a fallback is banned: the
  assistant does the work in every session, which makes it the author, never the maker.
  An empty Iq1 is honest — it says nobody knew, and it leaves the slot free.
- **Never** the operating system by default. "macOS" explains almost every session and
  therefore explains nothing.
- Use the full product name, never an abbreviation: `Hermes Agent`, `Hermes Desktop`,
  `Hermes Terminal`, `Hermes Telegram` — never just "Hermes".

### The product-analysis pattern (marketplace)

When the session is about evaluating or buying a product, the shape is:

```
Iq1 = the brand        Iq2 = the marketplace
```

| Session | Subject | Iq1 | Iq2 |
|---|---|---|---|
| Used drone listing | `Air 2S` | `DJI` | `Ebay` |
| Supplement research | `Trace Minerals` | `Dr. Berg` | `Amazon` |
| USB-C enclosure | `Case USB` | `ORICO` | — (the comparison is Iq3) |

Read in one breath: **what** it is, **who** makes it, **where** we looked.

This is the strongest expression of the algorithm: three fields, a complete idea,
telegraphic, in under 40 characters.

## 6. Iq2 — context, and only context

Iq2 is what sits *around* the subject and changes how you read it. Three things,
nothing else:

| Kind | Values | Example |
|---|---|---|
| **Store** | Amazon, Ebay, … | `Air 2S` · DJI · **Ebay** |
| **Country** | Panamá, … | `Fletes` · — · **Panamá** |
| **Machine** | Mac mini M4, VPS, P53, … | `16 GB Ram` · — · **Mac mini M4** |

A work family (`WebHosting`), an intention (`Comparar`) or a theme (`Hardware`) in
Iq2 is an **error, not a judgement call**. Those used to live here and the field
became a sack: it mixed families, topics and intentions in one column, so no filter
built on it could be trusted.

**The control question:** *would this value still make sense printed next to the
subject on a shelf label?*

## 6b. Iq3 — the intention (seven, closed)

Comparar · Instalar · Investigar · Testear · Cotizar · Troubleshooting ·
Compatibilidad.

- Closed on purpose: a vocabulary that grows on every session stops being a filter.
- **Empty is a valid answer.** It says nobody read an intention here, which is true.
- `Administrar` was retired; `Feature` and `Version` do not exist.

## 6c. Iq4 — the theme

The work front, with the subcategories of IT Manager: IA Bot, VPS, Data Backup,
Hardware, MindMap, Network, OS. `Data Mining` and `Data Security` are themes, not
families.

## 7. The internal axes (filters only, never in the title)

| Key | Question | Values |
|---|---|---|
| iq3 · Intention | what was asked | the seven above |
| iq4 · Theme | which work front | IT Manager and its subcategories |
| iq5 · Year | which edition | 2026, … |

**iq6 no longer means the machine** — the machine belongs in Iq2, next to the
store and the country. Slots 7 to 9 are reserved: present in the model, empty in
the data, waiting for an axis that earns its place.

None of these is written into the title except Iq1 and Iq2. Measured: adding the
theme leaves 877 of 884 titles with no description at all.

## 8. The date

Short, lowercase, Spanish month: `19ago`, `07nov`. It sits between the axes and the
description so the eye can skip it.

## 9. The description — and its verb appendix

**Parameters**

| Rule | Value |
|---|---|
| Minimum to appear | 18 characters **and** 3 words |
| If it does not fit | **Telegram mode** first: drop articles and prepositions, keep the first word |
| If it still does not fit | Omit entirely — a cut phrase is worse than nothing |
| Language | Spanish, telegraphic, no filler |
| Content | only what subject + axes could not say |
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

## 10. When subject and Iq1 collide

If they are nearly the same, **something is wrong**. The subject names a *thing or a
problem*; the axis names the *platform*. 187 sessions were corrected on this rule alone.

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
