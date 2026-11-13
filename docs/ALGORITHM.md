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

The **object, problem or symptom**, in 1–3 words: the block, or the program itself when
the intention turns the program into the object of the work (see §5c). Never a sentence.

**Rules**

| Rule | Why | Example |
|---|---|---|
| Strip the action prefix, keep the core | The verb goes to the description | `Vitamin C Supplement` → `Vitamin C` |
| Drop state adjectives | "unusual", "stuck", "with error" describe, not name | `Interosseous Pain` → `Interosseous` |
| Name the failure point | It is what you will search for later | `Protocol` for a broken gateway |
| Never repeat Iq1 | Two fields, one answer = not navigable | If Iq1 is YouTube and the work happens inside it, the subject is `Transcription`, not `Video` |
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

## 5. iq0 — the protagonist (the subject)

**The subject is what the session is about, and it is the field that leads the name.**
It is the only one that opens the title, so it carries the weight of the search.

- It names the **block or part** of the thing: `Protocol` inside a gateway,
  `Stuck Startup` inside Firefox, `Hermes Desktop` inside Hermes Agent.
- It is the program itself **only when the intention makes the program the object**
  (`Web Search`, `Compare`, `Quote`, `Buy`) — and then iq1 takes the company or the
  author, never the program twice. When the work happens *inside* the program
  (`Troubleshooting`, `Configuration`), the subject is the part that broke and the
  program goes to iq1.
- Two to four words. If it needs a verb, the verb belongs in the description.

**The hard limit: three words.** A subject of four words or more is not a subject,
it is a description that leaked into the field. Measured over 873 sessions: **23 carry a
four-word-or-longer subject (2.6 %)**, and every one of them is a phrase —
`brave no esta abriendo`, `consultar deepseek si esta`, `Hola DeepSeek estás funcionando`.
A phrase in iq0 means the description was written twice.

| Signal in iq0 | What it really is | Where it goes |
|---|---|---|
| a verb (`abrir`, `instalar`, `consultar`) | an action | the description, or ` · Verb` |
| four or more words | a sentence | compress to the block, rest to the description |
| a greeting or a question | chat, not a session about something | no subject |

**The control question:** *if I had to find this session in six months, what would I
type?* That word is iq0 — and it is never a sentence.

## 5b. iq1 — the program

**The program, platform, brand or person that does the work.**

- A program, a platform, a brand, a real actor. `Hermes Agent`, `Firefox`, `CyberPanel`,
  `DJI`, `Brave`, `Logseq`.
- Together with iq0 it reads as one idea: `Firefox` (program) + `Stuck Startup`
  (block) + `Troubleshooting` (intent). Three fields, one sentence.
- If nothing fits, **leave it empty**. `Hermes Agent` as a fallback is banned: the
  assistant does the work in every session, which makes it the author, never the maker.
  An empty Iq1 is honest — it says nobody knew, and it leaves the slot free.
- **Never** the operating system by default. "macOS" explains almost every session and
  therefore explains nothing.
- Use the full product name, never an abbreviation: `Hermes Agent`, `Hermes Desktop`,
  `Hermes Terminal`, `Hermes Telegram` — never just "Hermes".

### Where the program sits — iq3 decides

The same program can be the subject or the axis. It is not a matter of taste: **the
intention tells you which**.

| iq3 (intention) | Program is… | iq0 | iq1 |
|---|---|---|---|
| `Troubleshooting`, `Configuration` | the **container** of the work | the part that broke: `Protocol` | the whole: `Hermes Gateway` |
| `Web Search`, `Compare`, `Quote`, `Buy` | the **object** of the work | the program: `Firefox` | **its company or author**: `Mozilla` |
| `Testear`, `Compatibilidad` | the **object**, under test | the program: `Antigravity` | its maker: `Google` |

**Read it as a test:** ask *"is the program the thing I am looking at, or the thing the
problem lives in?"* Looking at it → iq0. A part of it → iq1, and the part goes to iq0.

```
Firefox · Stuck Startup · Troubleshooting      ← the problem lives inside Firefox
Hermes Gateway · Protocol · Troubleshooting    ← Protocol is a part of Hermes Gateway
Firefox · Mozilla · Web Search             ← Firefox itself is the object
```

Two consequences worth writing down, because they resolve most doubtful cases:

1. **A program in iq0 is not an error when the intention makes it the object.** It is
   the correct answer — and then **iq1 carries the company that makes the program or the
   name of its author**, never an empty slot: `Firefox · Mozilla`, `Antigravity · Google`,
   `Brave · Brave Software`, `Hermes Agent · Nous Research`.
2. **A program in iq1 requires that the subject be a part of it.** If no part can be
   named, the program belongs in iq0 and the session has no iq1.

### The pair is narrow + wide — in both directions

The same logic covers products and brands, which is where most sessions actually live.
**iq0 is the narrower word, iq1 the wider one.** Nothing else changes: the intention keeps
iq3 and the context keeps iq2, whatever sits in the first two fields.

| Direction | iq0 (narrow) | iq1 (wide) | Sessions today |
|---|---|---|---|
| product → brand | `Avata 360` | `DJI` | 5 |
| codename → brand | `Gorgon Halo` | `AMD` | 61 |
| model → brand | `ThinkPad P53` | `Lenovo` | 4 |
| program → company | `Firefox` | `Mozilla` | — |
| **brand → amplifier** | `Apple` | the product it is discussed through: `Mac mini M4` | 1 (broken) |

**A brand may be the subject.** It is not an exception: it is the same pair turned around.
`Apple · Mac mini M4` says "the brand, seen through that machine", exactly as
`Gorgon Halo · AMD` says "that chip, seen through its brand".

**The one case that leaves iq1 empty** is the brand as a whole — its strategy, its
catalogue, whether to stay with it. The maker of a brand is the brand, so filling iq1
with it would be the same word twice.

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

Troubleshooting · Web Search · Compatibility · Buy · Quote · Compare ·
Configuration.
**Install is not one of them.** Configuration implies installation: you cannot configure
what you did not install, so both verbs fold onto `Configuration`. **"Investigar" was
retired** and replaced by `Web Search` — the intention is the act of going out to find
something, and the name says it.

- Closed on purpose: a vocabulary that grows on every session stops being a filter.
- **Empty is a valid answer.** It says nobody read an intention here, which is true.
- `Administrar` was retired; `Feature` and `Version` do not exist.
- `Testear` folded into `Troubleshooting`: both confirm a state.

## 6c. Iq4 — the topic

The topic, with the subcategories of IT Manager: IA Bot, VPS, Data Backup,
Hardware, MindMap, Network, OS. `Data Mining` and `Data Security` are themes, not
families.

## 7. The ten fields, iq0 to iq9

| Key | Field | Question | In the title |
|---|---|---|---|
| **iq0** | Subject | what the session is about (block or part) | **yes** |
| **iq1** | Program | which program, platform or brand does the work | **yes** |
| **iq2** | Context | store, country or machine around it | **yes** |
| iq3 | Intention | what was asked (seven, closed) | no |
| iq4 | Theme | which topic | no |
| iq5 | Year | which edition | no |
| iq6 | — | retired: the machine moved to iq2 | no |
| iq7 | — | reserved | no |
| iq8 | — | reserved | no |
| iq9 | — | reserved | no |

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

Two identical fields answer the same question twice, and a catalogue where two fields
carry one answer stops being navigable. The rule survives the correction: **when the
program is the subject, iq1 must hold the maker or stay empty** — never the same word.

| Subject | iq1 | Verdict |
|---|---|---|
| `Firefox` | `Mozilla` | right: the program and the company that makes it |
| `Firefox` | `—` | **wrong**: a program in iq0 always names its company or author |
| `Firefox` | `Firefox` | **wrong**: one answer in two fields |
| `Stuck Startup` | `Firefox` | right: the part and the whole |

187 sessions were corrected on this rule before the program could be a subject at all.

## 11. Corrections are part of the algorithm

Every correction the user dictates is:

1. written into `core/corrections.yaml` as a rule with examples,
2. injected into the classifier prompt as few-shot evidence,
3. added to the evaluation set as a regression test.

The algorithm does not "learn" by itself — it learns because a correction that is not
written down is a correction that will be made again. See
[`CORRECTIONS.md`](CORRECTIONS.md).

## 12. What the teacher taught us

Evaluating title generation rules against the reference database of 862 canonical sessions
established five concrete invariants. Each resolves a measured failure pattern:

### Rule 1 · Never duplicate the subject name in Iq1 (15 cases measured)

When the subject in `iq0` is already the application, program, or brand name, `iq1` must never repeat
that exact token. Repeating the program in both slots creates "one answer in two fields" and degrades
faceted navigation.

- **Rule**: If `sujeto.lower() == iq1.lower()`, blank `iq1` so `iq2` can cleanly hold the machine or environment.
- **Wrong**: `041 [Logseq] 001 [Logseq] [Mac mini M4] Instalación Logseq 2.0 vía Homebrew; confiabilidad gestor`
- **Right**: `041 [Logseq] 001 [Mac mini M4] Instalación Logseq 2.0 vía Homebrew; confiabilidad gestor`

### Rule 2 · Extract known entities from conversational sentences (5 cases measured)

Sessions initiated with conversational greetings or prompts must not retain full chat sentences
in the subject slot.

- **Rule**: Identify known entities (`DeepSeek`, `Brave`, `Handbrake`, `Nous`) inside the sentence, promote the entity to `iq0`, and transfer the predicate to the description without duplicating the header.
- **Wrong**: `024 [Hola DeepSeek estás funcionando] 001 [DeepSeek] [IA] 024 [Hola DeepSeek estás funcionando] 001`
- **Right**: `024 [DeepSeek] 001 [IA] Hola estás funcionando`

### Rule 3 · Do not amputate prepositional complements or model tiers (2 cases measured)

A 4-word nominal syntagm bound by prepositions or model qualifiers (`Migración Android a iPhone`, `Gemini 3.1 Flash Lite`) is a single semantic block. Severing it between words strands hanging prepositions or broken version fragments.

- **Rule**: If a nominal subject cannot be reduced to 1–3 words without leaving a hanging preposition (`a iPhone`) or orphaned model tier (`3.1 Lite`) in the tail, leave it intact. Never append trailing fragments into the description using `·`.
- **Wrong**: `091 [Migración Android] 001 [Apple] [Teléfono] Backup WhatsApp Android Gmail antes · a iPhone`
- **Right**: `091 [Migración Android a iPhone] 001 [Apple] [Teléfono] Backup WhatsApp Android Gmail antes`

### Rule 4 · Recover entities from description when subject is sliced mid-word (5 cases measured)

Sessions previously processed with naive length slicing (e.g. at 35 characters) contain sliced words
(`perdid`, `proyect`, `plugin Ma`).

- **Rule**: Detect mutilated word endings (`_is_mutilated`). Inspect the description or raw text for the intact known entity (`Brave`, `Make It Smart`), assign that clean entity to `iq0`, and restore the description.
- **Wrong**: `947 [Recuperar ventanas y pestañas perdid] 001 Recuperar ventanas y pestañas perdidas de Brave`
- **Right**: `947 [Brave] 001 Recuperar ventanas y pestañas perdidas`

### Rule 5 · Transfer the predicate to description on uncanonical titles (5 cases measured)

When extracting a subject from a virgin title, discarding the remaining words empties the description.

- **Rule**: When deriving `iq0` from a free-form title, pass the remaining words directly into `desc` so the session purpose is preserved.
- **Wrong**: `Firefox tarda mucho en arrancar` → `972 [Firefox] 001` (empty description)
- **Right**: `Firefox tarda mucho en arrancar` → `972 [Firefox] 001 tarda mucho en arrancar`
