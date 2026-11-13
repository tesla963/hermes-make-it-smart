# User Guide — Hermes, make all my work Smart!

This guide is for the user, not the programmer. It tells you **in what order**
to do things so the plugin works well, and why that order matters.

---

## Before touching anything: make a backup

The plugin **renames your sessions**. Renaming doesn't delete anything —the
messages, the costs and the dates stay intact— but a name is the only way to
recognize a session six months later. If something goes wrong, you want to be
able to go back.

```bash
cp -a ~/.hermes/state.db \
      ~/state.db.backup-$(date +%Y%m%d-%H%M)
```

And if you have more than one profile:

```bash
for f in ~/.hermes/profiles/*/state.db; do
  cp -a "$f" "$f.backup-$(date +%Y%m%d-%H%M)"
done
```

The plugin makes its own backup before writing, in
`/Volumes/<tu disco>/Backups-Lisa/<fecha>_<motivo>/`. **But don't trust it
alone**: your backup is the one you know where it is.

> Over time you'll want to version the names, not the database. A `titulos.txt`
> file with one line `id<TAB>titulo` is all it takes to rebuild the catalog
> without classifying anything again.

---

## Step 1 · Look before writing: the dry run

Nothing is written until you ask for it. The panel has a **Testing** tab that shows the
seven axes, the rules and a preview of what a change would do, and the command line
gives the same guarantee:

```bash
python3 tools/apply_protocol.py            # shows what would change, writes nothing
python3 tools/apply_protocol.py --apply    # backs up, writes, re-reads
```

The dry run prints every proposed change with its reason:

| In the dry run you see | Without risk because |
|---|---|
| which sessions would change | it is a read-only pass |
| the before and after of each field | it does not touch the database |
| the rule that justified it | it does not rename |

**This is the part that makes the plugin safe.** The dry run and the app read exactly
the same index, so if something looks wrong in the dry run it will look wrong in the
app — but fixing it stays your decision, never a side effect.

Rule of thumb: **no correction goes into the database without having been seen in a
dry run first.**

---

## Step 2 · The ten fields: iq0 to iq9

Every session is read through ten fields. Three of them appear in the name; the rest are
filters.

| Field | Question | Example | In the title |
|---|---|---|---|
| **iq0** | What is the session about? (the block or the part) | `Stuck Startup` | yes |
| **iq1** | Which program, platform or brand does the work? | `Firefox` | yes |
| **iq2** | What sits around it? (store, country, machine) | `Ebay` | yes |
| iq3 | What was asked? (seven closed values — see below) | `Troubleshooting` | no |
| iq4 | Which topic does it belong to? | `VPS` | no |
| iq5 | Which year? | `2026` | no |
| iq6 | Retired: the machine moved to iq2 | — | no |
| iq7 | Reserved | — | no |
| iq8 | Reserved | — | no |
| iq9 | Reserved | — | no |

Read in one breath: `Firefox` + `Stuck Startup` + `Troubleshooting` gives the program,
the block inside it, and what you were doing there.

**The seven intentions:** `Troubleshooting`, `Web Search`, `Compatibility`, `Buy`,
`Quote`, `Compare`, `Configuration`. `Install` is not one of them — configuring implies
installing, so both are `Configuration`.

### The topics (iq4)

A topic is the part of your world a session belongs to: Asistente IA, VPS, Data
Backup, Derecho, Productos, Compras, Youtuber, MindMap, Geopolítica, Masoterapia.

It is the filter you will use most often, and **the one the plugin cannot guess for
you**. A model can say "this is about servers"; only you know whether in your world
that is *VPS* or *WebHosting* or *Infrastructure*.

#### How they are defined

In `core/taxonomy.py`, the `PILLARS` tuple — the list keeps its historical name, the
concept is the topic. Each entry carries a hint:

```python
{"name": "VPS", "hint": "the server that is mine: CyberPanel, DNS, mail, certificates"}
```

The hint is not decoration: **it is what the classifier reads to decide**. A vague hint
("technical topics") attracts half the catalogue and ruins the filter. A clear boundary
("the server that is mine: …") keeps to its own.

#### Three questions to tell whether a topic is right

1. **Could you say in one sentence what it is NOT?** If not, it is a catch-all.
2. **Does it have at least five sessions?** A front with a single session is a label.
3. **Does each session fall into one and only one?** If two fronts fight over the same
   session, their boundaries are not written.

> The most common mistake is creating a front for every topic that shows up. The result
> is twenty fronts with three sessions each, and none of them is good for navigating.
> **One front fewer and well delimited is better.**

#### When in doubt, don't invent

Use `Temas Varios` — the honest drawer for what has no front of its own yet. It is not a
failure: it is the waiting list that tells you which fronts you are missing. When it
reaches twenty sessions about the same thing, that is where the front is born.

---

## Step 3 · The cheat sheet: the dictionary that makes the plugin yours

`core/cheat_sheet.yaml` is what the plugin knows about **your** world. It's not
code: it's a list of names with their context.

```yaml
marcas:
  dji:
    iq1: DJI
    productos: [Air 2S, Avata 360, RC 2]
programas:
  devonthink:
    marca: DEVONthink
    maker: Devon Technologies
    sitio: https://www.devontechnologies.com/
```

**Why this is what pays off the most:** every name you add is a future session
that the plugin resolves **without asking any model**. The cheat sheet is the
classifier's memory.

| Without the cheat sheet | With the cheat sheet |
|---|---|
| the model guesses whether "Avata 360" is a brand or a product | it reads it from the list, free |
| "Devon Technologies" comes out misspelled every time | it's written once, forever |
| every session costs tokens | the known ones cost zero |

### Rules for writing it well

- **The brand goes in Iq1, alone.** `Ground Advantage` is the product; `USPS`
  is the brand. Never `USPS Ground Advantage` in the same field.
- **A program's brand is on its site, not in its name.** `DEVONthink` is the
  program; `devontechnologies.com` tells you the company is *Devon
  Technologies*.
- **One line per thing.** If you hesitate between two forms, write both in
  `alias`.
- **No personal experience.** "Packages get lost with this courier" goes in
  `cheat_sheet.personal.yaml`, which **is not published**.

---

## Step 4 · Correct in the panel, not in the database

The flow is always the same:

```
look in the panel  →  export the CSV  →  correct  →  apply
```

The **Export** button generates a CSV with one row per session and empty
columns for whatever you want to change:

```
n, id, fecha, titulo_actual, sujeto, iq1, iq2, descripcion,
sujeto_nuevo, iq1_nuevo, iq2_nuevo, descripcion_nueva, observaciones
```

You fill in only what's wrong and let it come back. **Nothing is applied until
you ask for it.**

---

## Step 5 · Apply, and verify

```bash
python3 tools/apply_protocol.py           # muestra qué cambiaría, no escribe
python3 tools/apply_protocol.py --apply   # respalda, escribe, relee
```

The first command **is the one you use 90 % of the time**. It shows the list of
proposed changes with their reason:

```
propuestas: 89 · sin cambio: 795

    2  iq3: Web Search → Configuration
       - 002 [Hermes Desktop] 001 [Hermes Agent] [Web Search] Configurar la app…
       + 002 [Hermes Desktop] 001 [Hermes Agent] [Configuration] Configurar la app…
```

If you don't like something, you don't apply it and you adjust the rule.

---

## Why training the plugin matters so much

The plugin **knows nothing about your life when you install it**. It knows
about software in general, like any model. What makes it useful is what you
teach it:

| What you give it | What you gain |
|---|---|
| **topics** (iq4) | the filter you actually use |
| **cheat sheet** | sessions resolved without spending tokens |
| **corrections** | the rules that prevent repeating the error |
| **your names** | the catalog stops sounding like a machine and sounds like you |

And it works like this: **every correction is written as a rule**, not as a
patch. Session 369 came out wrong because the subject was the controller and
not the brand; from there `subject-is-the-nearest-item` was born, and that rule
fixes the next hundred before they exist.

> **The fastest way to improve the plugin is not to ask it for more
> intelligence. It's to give it more names.** A well-kept cheat sheet file does
> more than a bigger model.

### The sign that it's trained

- There are **few sessions in "Temas Varios"** and the ones there are recent.
- The **intentions are verbs** (`Troubleshooting`, `Configuration`, `Quote`), and they live in iq3, not iq2
  (`Electronica`, `IA`).
- **Adding a new session doesn't require renaming any old one.**
- A session's subject **doesn't repeat the brand** and carries no verbs.

If those four things hold, the plugin is already working on its own.

---

## The order, in one line

```
backup → topics (iq4) → cheat sheet → dry run → corrections → apply → repeat
```

And the step that is never skipped: **look before writing.**
