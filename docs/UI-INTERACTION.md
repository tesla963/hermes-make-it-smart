# Interaction model — mouse and keyboard

The window is three zones: **Filters** (aside), **List** (table), **Card** (detail panel).
Navigation must never make the user guess where the focus is, and must never fight the app's own
shortcuts.

## Zones and Tab

`Tab` moves Filters → List → Card, `Shift+Tab` the other way. The active zone gets a visible focus
ring (2 px accent outline, inset so it does not shift layout).

**On entering the List, the first visible row is selected automatically**, so `↓` works immediately
without a click. The selection is a roving focus: exactly one row carries it at any time.

## Keys inside the List

| Key | Action |
|---|---|
| `↓` / `↑` | one row down / up, scrolling the row into the 22 %–74 % band of the viewport |
| `PageDown` / `PageUp` | 10 rows |
| `Home` / `End` | first / last visible row |
| **`Enter`** | **opens the selected session** — the same call as the *Abrir sesión* button |
| `Space` | opens / closes the **Card** for the selected row, without leaving the List |
| `Esc` | closes the Card; a second `Esc` returns the selection to the first visible row |
| `/` | jumps to the search box in Filters |

With the Card open, `⌥↓` / `⌥↑` walk to the previous/next visible session **and the Card follows**
(this is what the ▲/▼ buttons in the card header do today).

## Mouse

| Gesture | Action |
|---|---|
| Left click on a row | selects it |
| Double click on a row | opens the session |
| **Right click on a row** | **opens the session** — the same as `Enter`, without a menu |
| `⌥` + right click | context menu: *Abrir sesión*, *Copiar título*, *Copiar ficha*, *Ver la serie*, *Limpiar filtros* |
| Click on a pill | filters by that axis value (the pill becomes a chip) |
| Drag the divider | resizes the Card (already specified in SPEC-UI) |

Right click opening the session directly is deliberate: it is the fastest path from "that's the one"
to "I'm in it", and the menu stays available behind `⌥` for the slower operations.

## App-level keybinds (registered, user-rebindable)

Only these go through `KEYBINDS_AREA`, because they must work from anywhere in the app and do not
collide with typing:

| Command | Default | Why |
|---|---|---|
| `smarts.open` | `mod+shift+s` | jump to **Make It Smart** |
| `smarts.search` | `mod+shift+f` | focus this page's search box |
| `smarts.nextSession` | `alt+down` | next session with the Card following |
| `smarts.prevSession` | `alt+up` | previous session with the Card following |

**`Enter`, `Space`, the arrows and `/` are deliberately NOT registered app-wide.** They stay local
to the page while it has focus: registering `Enter` globally would break the composer and every list
in the app, and the app's own shortcuts are already user-rebindable — a plugin must not fight them.

## What this replaces

The Card's ▲/▼ buttons stay (they are discoverable by mouse), but they become a mirror of
`⌥↑ / ⌥↓` instead of the only way to move between sessions.

## Accessibility floor

- The selected row is announced with `aria-selected="true"` and the table carries
  `aria-activedescendant`.
- Every action available by mouse has a keyboard equivalent (open, copy, filter, resize is mouse-only
  by nature but not required for reading).
- Right click never *only* opens: `Enter` does the same, so no functionality is hidden behind a
  pointing device.
