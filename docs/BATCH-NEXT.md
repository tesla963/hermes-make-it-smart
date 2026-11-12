# Batch 2 — UI interaction (queued, starts after the agent tools land)

Order matters: 1–3 make the list usable without a mouse; 4–6 make opening a session fast; 7–9 add
the mouse affordances; 10–11 polish.

Every item is done when `hermes plugins validate .` and `node tests/test_plugin.mjs` pass **and** the
manual check in the last column is observed.

| # | Item | Detail | Manual check |
|---|---|---|---|
| 1 | **Zones + Tab** | `Tab` / `Shift+Tab` cycle Filters → List → Card; the active zone gets a 2 px inset focus ring | Tab three times returns to where it started, ring always visible |
| 2 | **Roving focus in the List** | entering the List selects the **first visible row**; exactly one row carries the selection (`aria-selected="true"`, table `aria-activedescendant`) | open the page: first row is already selected, `↓` moves it |
| 3 | **List keys** | `↓`/`↑` one row, `PageDown`/`PageUp` 10, `Home`/`End` first/last, always `scrollIntoView({block:'center'})` inside the 22 %–74 % band | hold `↓` to the bottom: no jump, counter follows |
| 4 | **`Enter` opens** | same call as the *Abrir sesión* button (`host.openSession`) | Enter on a selected row opens that session |
| 5 | **`Space` toggles the Card** | opens/closes the detail card for the selected row without leaving the List | Space opens the card, Space again closes it |
| 6 | **`Esc`** | closes the Card if open; otherwise returns the selection to the first visible row | Esc twice behaves as described |
| 7 | **Right click opens** | `contextmenu` on a row calls `host.openSession`, no menu | right-click any row opens it |
| 8 | **`⌥` + right click = menu** | *Abrir sesión · Copiar título · Copiar ficha · Ver la serie · Limpiar filtros* | menu appears only with `⌥` held |
| 9 | **`⌥↓` / `⌥↑`** | previous/next visible session with the Card following; the card's ▲/▼ buttons mirror the same handler | with the card open, `⌥↓` moves card and selection together |
| 10 | **Keybinds registered** | `KEYBINDS_AREA`: `smarts.open` = `mod+shift+s`, `smarts.search` = `mod+shift+f`, `smarts.nextSession` = `alt+down`, `smarts.prevSession` = `alt+up` | the four appear in Settings → Keybinds and are rebindable |
| 11 | **`/` focuses search; pill click filters** | `/` jumps to the aside search box; clicking a pill adds that axis as an active chip | type after `/` and the list narrows; click a pill and a chip appears |

## Deliberate deviations from platform convention

- **Right click opens instead of showing a menu.** Faster from "that's the one" to "I'm in it". The
  menu survives behind `⌥` and every menu action also has a key, so nothing is mouse-only.
- **`Enter`, `Space`, arrows and `/` are page-local, not app keybinds.** Registering them app-wide
  would break the composer and every list in Hermes. Only the four `smarts.*` commands are global.

## Explicitly out of scope for this batch

- The hours statistic (frozen by decision, not a bug to fix now).
- Resizing the Card by keyboard — mouse drag only, and reading does not require it.
- Any change to the naming algorithm or the axis set.
