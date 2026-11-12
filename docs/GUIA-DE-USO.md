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

## Step 1 · Look before writing: the simulator

The plugin generates an **HTML simulator** — a single file that opens in the
browser, with no server and no connection.

```
~/Documents/Reportes - [Lisa]/<fecha>/<fecha>_simulador-plugin-bodega-de-sesiones.html
```

There you see **the 884 sessions as they would end up**, with their filters,
their search box and their card. And the most important thing: **it writes
nothing**.

| In the simulator you can | Without risk because |
|---|---|
| filter by pillar, platform, family | it's a read-only copy |
| search by number (`126,305`, `50-75`) | it doesn't touch the database |
| review the intent of each session | it doesn't rename |
| export a CSV of corrections | the file is yours |

**This is the part that makes the plugin safe.** The simulator and the app read
exactly the same index; if something looks wrong there, it will look wrong in
the app. But fixing it is your decision, not a side effect.

Rule of thumb: **no correction goes into the database without having been seen
first in the simulator.**

---

## Step 2 · Pillars: the first thing to define

A pillar is **the work front a session belongs to**: Asistente IA, VPS, Data
Backup, Derecho, Productos, Compras, Youtuber, MindMap, Geopolítica,
Masoterapia.

It's the filter you'll use most often, and **it's the one the plugin cannot
guess for you**. A model can say "this is about servers"; only you know whether
in your world that's *VPS* or *WebHosting* or *Infrastructure*.

### How they are defined

In `core/taxonomy.py`, the `PILLARS` list. Each one with:

```python
{"name": "VPS", "hint": "el servidor propio: CyberPanel, DNS, correo, certificados"}
```

The `hint` is not decoration: **it's what the classifier reads to decide**. A
pillar with a vague hint ("technical topics") attracts half the catalog and
ruins the filter. A pillar with a clear boundary ("the server that's mine: …")
keeps to its own.

### The three questions to tell whether a pillar is right

1. **Could you say in one sentence what it is NOT?** If not, it's a
   catch-all.
2. **Does it have at least five sessions?** A pillar with a single session is
   a label, not a front.
3. **Does each session fall into one and only one?** If two pillars fight over
   the same session, their boundaries aren't written.

> The most common mistake is creating a pillar for every topic that shows up.
> The result is twenty pillars with three sessions each, and none of them is
> any good for navigating. **One pillar fewer and well delimited is better.**

### When in doubt, don't invent: use "Temas Varios"

It's the honest drawer for what doesn't have a front of its own yet. **It is
not a failure**: it's a waiting list that tells you which pillars you're
missing. When "Temas Varios" reaches twenty sessions about the same thing,
that's where the pillar is born.

---

## Step 3 · The battery: the dictionary that makes the plugin yours

`core/bateria.yaml` is what the plugin knows about **your** world. It's not
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
that the plugin resolves **without asking any model**. The battery is the
classifier's memory.

| Without the battery | With the battery |
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
  `bateria.personal.yaml`, which **is not published**.

---

## Step 4 · Correct in the simulator, not in the database

The flow is always the same:

```
look in the simulator  →  export the CSV  →  correct  →  apply
```

The **Export** button generates a CSV with one row per session and empty
columns for whatever you want to change:

```
n, id, fecha, titulo_actual, sujeto, iq1, iq2, descripcion,
sujeto_nuevo, tag1_nuevo, tag2_nuevo, descripcion_nueva, observaciones
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

    2  iq2: IA → Instalar
       - 002 [Hermes Desktop] 001 [Hermes Agent] [IA] Instalar la app…
       + 002 [Hermes Desktop] 001 [Hermes Agent] [Instalar] Instalar la app…
```

If you don't like something, you don't apply it and you adjust the rule.

---

## Why training the plugin matters so much

The plugin **knows nothing about your life when you install it**. It knows
about software in general, like any model. What makes it useful is what you
teach it:

| What you give it | What you gain |
|---|---|
| **pillars** | the filter you actually use |
| **battery** | sessions resolved without spending tokens |
| **corrections** | the rules that prevent repeating the error |
| **your names** | the catalog stops sounding like a machine and sounds like you |

And it works like this: **every correction is written as a rule**, not as a
patch. Session 369 came out wrong because the subject was the controller and
not the brand; from there `subject-is-the-nearest-item` was born, and that rule
fixes the next hundred before they exist.

> **The fastest way to improve the plugin is not to ask it for more
> intelligence. It's to give it more names.** A well-kept battery file does
> more than a bigger model.

### The sign that it's trained

- There are **few sessions in "Temas Varios"** and the ones there are recent.
- The **Iq2 are verbs** (`Instalar`, `Testear`, `Cotizar`), not shelves
  (`Electronica`, `IA`).
- **Adding a new session doesn't require renaming any old one.**
- A session's subject **doesn't repeat the brand** and carries no verbs.

If those four things hold, the plugin is already working on its own.

---

## The order, in one line

```
backup → pillars → battery → simulator → corrections → apply → repeat
```

And the step that is never skipped: **look before writing.**
