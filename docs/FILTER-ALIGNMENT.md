# Aligning the rules to the new filter structure

Date: 2026-11-10 · base: 884 sessions · 50 rules · 13 intents

---

## 1 · The structure, as it stands

| Key | Axis | Answers | Example |
|---|---|---|---|
| **iq1** | **Brand** | whose is the subject? — an adjective | `DJI` |
| **iq2** | **Context** | where, or inside what frame? | `Amazon` · `Ebay` · `Panamá` |
| **iq3** | **Intent** | what did the user want to do? | `Comparar` |
| **iq4** | **Place** | country or store | `Panamá` · `Ebay` |
| **iq5** | **Theme** | the work front | `IA Bot` · `VPS` |
| iq6 | Year | when | `2026` |
| iq7 | Machine | on which machine | `Mac mini M4` |

And the title:

```
NNN [Subject] MMM [iq1] [iq2] [iq3] Description
```

> **iq2 and iq4 overlap.** Both accept `Ebay` and `Panamá`. It has to be
> decided before writing anything: either **iq4 is the place** and iq2 is left
> for non-geographic context, or **they merge** and the country and the store live
> together. I recommend the first: `iq4 = Ebay`, `iq2 = "comparación de precios"`.

---

## 2 · «Automation» is not an intent

You were right to be suspicious. Measured:

```
Automation: 98 sessions
  ├─ 67 are cron          (the user did not ask for them: they were scheduled beforehand)
  └─ 31 are "turn on the gateway", "configure the bot"  → Instalar / Administrar
```

**Automation describes the absence of intent**, not an intent. An automatic task
is a task the user **no longer does**. Putting it as Iq3 would be like putting
«already done» in the column of what they wanted to do.

**What to do with those 98:**

| Group | How many | Correct Iq3 |
|---|---|---|
| They watch something periodically | 67 | **`Monitorear`** |
| They turn on or configure a service | ~23 | **`Administrar`** |
| The rest | ~8 | according to their description |

`Monitorear` is indeed an intent: someone decided that this had to be watched.
And it marks a useful difference in the filter — «what I did» against «what runs
on its own».

**Proposal:** retire `Automation` from the Iq3 vocabulary and add
`Monitorear`. The fact that it is cron is already said by the session id.

---

## 3 · The iq5 measurement

With the names you gave, mapping the current work fronts (iq4):

| Subcategory | Sessions | % of the total |
|---|---|---|
| **IA Bot** | 316 | 36 % |
| **VPS** | 187 | 21 % |
| **Data Backup** | 76 | 9 % |
| **Hardware** | 69 | 8 % |
| **MindMap** | 33 | 4 % |
| **IT Manager** (no subcategory) | 0 | — |
| **Network** | 13 | 1,5 % |
| **OS** | 27 | 3 % |
| **Total IT Manager** | **681** | **77 %** |

### The Network and OS problem

Those two are not work fronts today: they are **cross-cutting slices**.

```
Network = the 13 sessions with iq2 "Networking"
OS      = the 27 sessions with iq2 "File System"
```

But those sessions already live inside VPS, Data Backup or IA Bot. If Network and
OS rise to subcategory, **you have to decide whether they move or are copied**:

- **If they move:** VPS drops from 187 to ~180, Data Backup drops, and Network/OS rise.
  Each session in a single place. **Recommended.**
- **If they are copied:** a session would live in two subcategories. The filter stops
  being exclusive and the counts add up to more than the total — the same problem as the
  slice we fixed today.

### The underlying problem: 77 %

IT Manager eats three quarters of the catalogue. With those seven subcategories,
`IA Bot` alone has 316 — more than the other six together.

**Two possible readings:**

1. **It is correct:** your work *is* IT. The catalogue reflects your life, and your life is
   this one. The seven subcategories are enough to navigate.
2. **A level is missing:** `IA Bot` with 316 is what `Asistente IA` used to be — the drawer
   for everything that touches Hermes. It needs to be split: *the assistant* (voice, models,
   gateway), *the plugin* (this project), *the skills*, *the tests*.

I lean toward 2, but **it is your call**: you know whether those 316 sessions feel
like one thing or like five.

---

## 4 · The 203 sessions left outside IT Manager

| Current work front (iq4) | Sessions | What theme is it? |
|---|---|---|
| Derecho | 61 | missing declaration |
| Temas Varios | 43 | it is the waiting list |
| Compras | 41 | missing declaration |
| Youtuber | 33 | missing declaration |
| Geopolítica | 18 | missing declaration |
| Masoterapia | 7 | missing declaration |

You only named IT Manager as a theme. **The other five still have no iq5** — and they are
203 sessions, 23 % of the catalogue.

---

## 5 · The 50 rules, one by one

### 5.1 · Rules that do NOT change (still valid as they are) — 31

These speak about the **subject**, and the subject has not moved:

`subject-is-a-point-not-a-sentence` · `subject-never-carries-the-action` ·
`subject-strips-action-prefix` · `subject-does-not-repeat-iq1` ·
`subject-is-never-the-program` · `one-subject-only` ·
`qualifier-is-not-identity` · `subject-is-the-nearest-item` ·
`spelling-variants-are-one-subject` · `one-series-one-work-front` ·
`verb-first-then-subject` · `subject-preposition-exception` ·
`ventana-permisos-series` · `lisa-is-the-subject` ·
`third-party-program-is-iq1-not-subject` · `brand-equals-subject-exception` ·
`brand-and-product-are-two-things` · `brand-of-a-program-comes-from-its-site` ·
`brand-never-in-subject` · `closest-item-wins-in-compatibility` ·
and the eleven on series, dates and format.

### 5.2 · Rules that CHANGE destination — 4

| Rule | Before | Now |
|---|---|---|
| `iq2-carries-the-intent` | the intent went in **iq2** | it goes in **iq3** |
| `intent-not-topic` | «iq2 is the verb» | «**iq3** is the verb» |
| `two-layers-actors-then-intent` | resolved iq1 + iq2 | resolves iq1 + **iq3** |
| `python-decides-llm-investigates` | same, but the destination is iq3 | no change in substance |

**And a big consequence:** the 79 sessions we corrected yesterday by moving the
intent to iq2 **have to move again to iq3**. That work is not lost — the value
is the right one — but the field changes place.

### 5.3 · New rules that are needed — 5

**`iq1-is-an-adjective`**
> Iq1 qualifies the subject, it does not name it. `DJI` qualifies `Air 2S`; `DJI Avata 360`
> qualifies nothing, it is an adjective with the noun glued to it.

**`place-not-platform`**
> A country or a store is never Iq1. `Amazon` in Iq1 says «this is about
> Amazon»; in Iq4 it says «I bought it on Amazon». The second sentence is the useful one.

**`intent-is-what-the-user-did`**
> Iq3 is an infinitive verb that the user would recognize as their own. If it does not
> exist in the list of 13, `Investigar` is used — a new one is never invented.

**`automation-is-not-an-intent`**
> A scheduled task does not express what the user wanted: it expresses what they already
> decided before. It goes to `Monitorear`, and the session id already says it is cron.

**`one-session-one-theme`**
> Iq5 accepts a single subcategory. If a session falls into two, the subcategory
> is badly delimited, not the session.

### 5.4 · Rules that die — 2

**`productos-vs-compras`** — the distinction disappears. `Productos` becomes the
subcategory `Hardware`, and `Compras` stops being a work front: buying is an
**intent** (`Cotizar`) plus a **place** (`Amazon`).

**`one-series-one-work-front`** — it stays in substance, but is renamed to
`one-series-one-theme`: the series shares **iq5**, not a work front.

### 5.5 · The result

```
50 rules
 ├─ 31 intact
 ├─  4 change field (iq2 → iq3)
 ├─  5 new
 ├─  2 die or are renamed
 └─  8 pending decision (below)
```

---

## 6 · What has to be decided before migrating

1. **Do iq2 and iq4 overlap?** Both accept `Ebay`. Either they specialize
   (iq2 = frame, iq4 = place) or they merge.
2. **Do Network and OS move or are they copied** from VPS and Data Backup?
3. **Does IA Bot with 316 split** into assistant / plugin / skills / tests?
4. **What iq5 do Derecho, Compras, Youtuber, Geopolítica and Masoterapia carry?**
   They are 203 sessions with no theme.
5. **Does `Monitorear` come in** to the Iq3 vocabulary and `Automation` go out?
6. **Do yesterday's 79 corrections move to iq3** in the same run?

---

## 7 · Order of the migration, once it is decided

```
1. declare the missing iq5 (Derecho, Compras, Youtuber, Geopolítica, Medicina)
2. move the intent from iq2 → iq3 in all 884
3. retire Automation, add Monitorear, reclassify its 98
4. fill iq4 (place) from the cheat sheet: Amazon, Ebay, Panamá
5. clean the 303 sessions with iq1 = "Hermes Agent"
6. measure with a dry run before writing
7. apply with backup
```

Each step can be measured dry before touching the database. **None is applied without
having been seen in a dry run.**
