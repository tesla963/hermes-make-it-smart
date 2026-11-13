# Obsolete rules — the review list

Everything below **no longer applies**. This page exists so the owner can mark what to delete,
what to keep as history, and what to rename. Nothing here is deleted without his word.

Legend: **DELETE** = remove it · **RENAME** = the concept survives, the name does not ·
**KEEP** = history, do not touch · **MIGRATE** = data still carries it.

---

## 1. Intentions

| What | Where | Why it is obsolete | Action |
|---|---|---|---|
| 13-value list (`Instalar`, `Update`, `Version`, `Feature`, `Comparación`, `Diagnosticar`, `Testear`, `Cotizar`, `Costo`, `Administrar`, `Respaldar`, `Investigar`) | `core/intent.py` history | collapsed into the seven canonical intentions | **KEEP as signals** |
| `Investigar` as the default intention | rules, docs, prompt | retired: the verb is `Web Search` | **DELETE** |
| `Instalar` as its own intention | rules, docs | `Configuration` implies installation | **DELETE** |
| `Testear`, `Verificar`, `Reparar`, `Fixing` as intentions | rules | folded into `Troubleshooting` | **DELETE** |
| `Comparar`, `Cotizar`, `Compatibilidad` in Spanish | rules, docs, data | the seven are English | **DELETE from docs / MIGRATE data** |
| "Compra is missing as an intention" | `FEATURES.md` §4 | `Buy` exists now | **DELETE** |
| The section "two intention lists that disagree" | `FEATURES.md` | there is one list now | **DELETE** |

## 2. The axes

| What | Where | Why | Action |
|---|---|---|---|
| `tag0…tag9` | old data, migration note in README | renamed `iq0…iq9` in v0.27.0 | **KEEP** (the reader accepts both) |
| "nine axes" | `FEATURES.md`, `ROADMAP.md`, `SPEC-UI.md` | there are ten fields, iq0 to iq9 | **DELETE** |
| `iq6 = Machine` | `FEATURES.md` | retired: the machine lives in iq2 | **DELETE** |
| `iq5 = Date` described as "when it happened" | `FEATURES.md` | it is the year, and it is contaminated | **RENAME + clean** |
| `iq1 = maker of the subject, an adjective` | rules, taxonomy comment | iq1 is the program/brand, or its maker | **DELETE** |
| `iq1` called "the protagonist" | `taxonomy.py`, `ALGORITHM.md` | **iq0 is the protagonist** | **DELETE** |
| `iq4 = Theme` described as "work front" | docs | the owner does not use that word; it is a **topic** | **RENAME** |
| Subject "2–4 words" | `ALGORITHM.md` | three is the limit; four is a description leak | **DELETE** |
| "Never the program" in the subject | `ALGORITHM.md`, rules | the program **is** the subject when the intention makes it the object | **DELETE** |
| "iq1 or empty" when a program is the subject | rules | it carries the company or the author | **DELETE** |

## 3. Words the owner retired

| Word | Why | Action |
|---|---|---|
| **pillar / pilar** | nobody outside the project understands it; it is a **topic** | **RENAME** everywhere, including `PILLARS` and `normalize_pillar` |
| **simulator / simulador** | the HTML simulator was removed; the dry run and the Testing tab replaced it | **DELETE** every reference |
| **battery / batería** | it is the **cheat sheet** | **DONE** (`core/cheat_sheet.py`) |
| **cellar_bateria** (tool name) | renamed `cellar_cheatsheet` | **DONE** |

## 4. Code that still wears the old name

| Symbol | File | Status |
|---|---|---|
| `PILLARS` | `core/taxonomy.py` | the values are the topics; the name is historical |
| `normalize_pillar()` | `core/taxonomy.py` | normalises iq4, not a "pillar" |
| `pilar` key in the index | `adapters/hermes.py` / index rows | legacy column, still written |
| `cellar_tag` (tool) | `tools/cellar_tools.py` | a tool named after a retired word |
| `ui_battery_obsolete` | was in `cellar_tools.py` | check for leftovers |
| `tagN` in test fixtures | `tests/test_migrate_axes.py` | **intentional**: the fixture must contain the old schema |

## 5. Documents that describe a product that no longer exists

| Document | Problem | Action |
|---|---|---|
| `SPEC-BATCH.md` | historical batch spec, superseded by v0.27.0 (already carries a banner) | **KEEP** |
| `BATCH-NEXT.md` | plan written for the hackathon week | **REVIEW** |
| `FILTER-ALIGNMENT.md` | analysis of the 13-intention list and "pillars"; the mapping is done | **REVIEW**, may be history |
| `SPEC-UI.md` | colour table still calls iq3 "pillar"; mentions «Cotizar» | **RENAME** |
| `ROADMAP.md` | "nine axes" and the seven-value Spanish list | **DELETE stale parts** |
| `STATUS.md` | counts from before the rename | **REFRESH** |
| `reports/*.html` (Spanish names) | generated before the English pass | **DELETE** (already asked once) |

## 6. What is decided and needs no discussion

- `iq0` subject, 1–3 words, no verb, no sentence.
- `iq1` program/brand/company — the wide word of the pair.
- `iq2` context only: store, country, machine.
- `iq3` the seven intentions in English.
- `iq4` topic.
- `iq5` year; `iq6` retired; `iq7…iq9` reserved.
- Narrow + wide pair, in both directions; a brand may be the subject.
- Vocabulary: a model never alone, one idea one value, sizes are attributes, acronyms and file
  names are not subjects, companies carry their trade, events are a category.

## 7. What the owner still has to decide

1. `iq2` has one slot and the context can be double (store **and** city). Priority, two values,
   or the second one to `iq5`.
2. Whether `PILLARS` / `normalize_pillar` / `cellar_tag` get renamed now or after the first run.
3. Which documents of §5 are history and which get deleted.
4. Whether the 424 intention values are migrated before the first run (recommended: yes).
