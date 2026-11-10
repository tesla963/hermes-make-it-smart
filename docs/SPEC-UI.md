# UI specification — what the plugin must reproduce

Every rule here was decided on the simulator and is binding for
`desktop/plugin.js`. The simulator is the spec: if the window disagrees with it,
the window is wrong.

## 1 · The row shows only what the name shows

A session row carries the same four things its title does:

```
No.   Date        SUJETO · #
881   2026-11-07  [Gorgon Halo] 043  AMD  Automation    2¢   5m   219k   1
      ^ línea 1: [Gorgon Halo] 043 [AMD] [Automation] Tarea cron que monitorea…
```

The row is two lines, and each line has a job:

| Line | Carries |
|---|---|
| **1 — the name** | the whole title, unadorned: `NNN` · `[Sujeto] MMM` · `[tag1]` · `[tag2]` · description in bold. **No pills here.** |
| **2 — the data** | date · subject pill with its `MMM` · **tag1 and tag2 as coloured pills right after the MMM** · cost · hours · tokens · posts |

**There is no TAGS column.** The pills live inside the subject cell of the
second line, after the `MMM`, so the two tags stay readable as colour without
polluting the name. Anything that does not appear in the name —pillar (tag3),
country, year, machine, tags 7-9— lives in the detail card and in the filters,
never in the list.

Sizing: `tr.t` fills 2 cells (number + title/colspan 6), `tr.r` fills 7. The
`<th>` for Nº stays as scaffolding so the date lines up under the first bracket.

## 2 · The nine tags and their colours

Same lightness and saturation across the set: one hue each, none shouts on
`#0d0b0e`. The order runs cool → warm so two adjacent tags never compete.

| Tag | Axis | Text | Background | Border |
|---|---|---|---|---|
| **tag1** | platform | `#f0d48a` amber | `#2a2210` | `#55461f` |
| **tag2** | family | `#d3e3f3` pale blue | `#121d28` | `#24404f` |
| **tag3** | pillar | `#c9a8f0` violet | `#221634` | `#453063` |
| **tag4** | country | `#96e0b0` green | `#0f2618` | `#1f4a30` |
| **tag5** | year | `#f2a8c4` pink | `#2b1220` | `#55233d` |
| **tag6** | machine | `#f5b98f` orange | `#2b1a0f` | `#553620` |
| **tag7** | free | `#8fe6e0` turquoise | `#0d2725` | `#1f4a46` |
| **tag8** | free | `#b8b8f5` lavender | `#1a1a33` | `#33335f` |
| **tag9** | free | `#d8ec8f` lime | `#222b0f` | `#44551f` |

**The subject carries the brightest blue** — `#8fd0f5` on `#0f2431` — because it
is the heaviest word in the row and deserves the strongest colour. tag2 keeps a
paler blue so it reads as related but subordinate.

Tags 7, 8 and 9 have a colour reserved and no meaning yet: the slots exist so
gaining an axis later costs no migration.

## 3 · The interface language is not the classifier's language

A `ES | EN` switch sits at the **right edge of the title row**, not in the filter
bar: the filters need that space.

Switching translates every visible string — buttons, headers, KPI labels,
placeholders, the detail card, plurals — and persists in `localStorage`.

What it does **not** change: the classifier reads Spanish and English always
(bilingual dictionary, Spanglish when the base language is Spanish). A window in
English still understands «Cotizar» and «Temas Varios».

## 4 · Filters: three is the ceiling, not a wall

Three simultaneous filters is the realistic maximum, and the panel is sized for
it. But the bar must **not break** with five: chips wrap, buttons shrink, nothing
disappears. A filter that cannot be cleared is worse than a crowded row.

Active filters show as removable chips; clearing the panel returns to
`Fecha` descending.

## 5 · The KPI bar

Pinned at the bottom, five figures: **visible sessions · accumulated cost ·
work hours · total posts · total tokens**.

- Height `--kbar-h: 33px`, declared once in `:root`.
- The left panel ends **exactly** where the bar begins: `aside.bottom == kbar.top`,
  difference 0. Never a padding that hides an overlap — an exact edge, not a patch.
- Number and label on the same row, number resting on the label's baseline,
  sized so the two-line label and the number are the same height.

## 6 · Buttons

All base size — `padding: 3px 8px`, `font-size: 12px`, `white-space: nowrap`.
Never one button visibly larger than its neighbour.

```
[ Limpiar ]  [ Copiar · N ]  [ Exportar · N ]  [ Actualizar BD ]
```

- **Copiar** copies the visible titles, one per line, `title \t session_id`.
- **Exportar** writes a CSV with the correction columns empty and a `[CCCC]`
  running counter in the file name.
- **Actualizar BD** runs the incremental pass: only sessions whose title is not
  yet canonical get classified. Reports *"N nuevas, M sin cambios"*.
- The detail card carries **Copiar sesión** and **Abrir sesión** side by side,
  same size as the rest.

## 7 · The detail card

Title at 1.5× the list size, wrapped in its own bordered block. Below it the
nine tags with their **internal name** (`tag1 · platform`, `tag3 · pillar`,
`tag7 · free`…), so it is visible at a glance which axes exist and which are
still empty.

Then cost, hours, messages, date, engine, author, profile, and the user's own
key messages — filtered of cron preambles and skill dumps, because those are not
something the owner said.

The long session id goes **last**, small and monospaced: reference data, not a
headline.
