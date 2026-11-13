# Publishing rules — what never leaves this machine

This plugin reads a person's whole working life. Some of what it learns is **theirs** and must
never reach the repository, a screenshot, a report sent to a third party, or a demo.

The rule is simple and it has no exceptions:

> **The repository may describe the shape of a vocabulary. It may never contain the words.**

---

## 1. What is personal

| Personal | Why | Where it may live |
|---|---|---|
| The **name of the agent** the owner chose | it identifies the person | the owner's config |
| The **owner's name**, the partner's, the family's | direct identity | the personal file |
| **Usernames, home paths, emails, phone numbers** | direct identity | nowhere in the repo |
| **Suppliers, forwarders, couriers, shops they use** | business relationships | the personal file |
| **Prices paid, order numbers, addresses** | financial and physical | the personal file |
| **Their machines, by serial or by nickname** | identifies the household | the personal file |
| **Session titles, prompts, transcripts** | the raw life | the local database |
| **The mined vocabulary and its frequencies** | it is a fingerprint: nobody else owns a `Gorgon Halo` 61 times | the personal folder |
| **Merge proposals, evaluation cases built from their data** | same reason | the personal folder |

## 2. What is not personal, and should be published

- The **rules** that the vocabulary follows (a model is never alone, one idea one value).
- The **types**: `Forwarder`, `Marketplace`, `Retailer`, `Laptop`, `Drone`, `Tarjeta Gráfica`.
- The **device families**: `Celular Android`, `iPhone`, `iPad`, `Smartwatch`.
- The **brands that exist in the world**: Apple, Lenovo, Dell, Nvidia, AMD, Samsung, DJI.
- The **example files**, with fictional or blanked names: `(your forwarder)`, `(your hosting)`.
- **This document.**

A supplier name is personal. The **word "Forwarder"** is knowledge every user can use.

## 3. How the guard works

The list of forbidden terms does **not** live in the repository — a blocklist that contains the
names would leak exactly what it protects. It lives with the owner's data:

```
~/.hermes/plugin-data/make-it-smart/publish-blocklist.yaml
```

The checker reads it and refuses to pass if any tracked file contains a forbidden term:

```bash
python3 tools/check_publish.py            # scans every tracked file
python3 tools/check_publish.py --staged   # scans only what is staged, before committing
```

Exit code `0` means clean; `1` means a leak, and it prints the file, the line and the term
**redacted** (it shows how many characters, never the word itself).

### What the blocklist looks like

```yaml
# publish-blocklist.yaml — personal, never published
terms:
  - "(the agent's name)"
  - "(the owner's name)"
  - "(the partner's name)"
  - "(the username)"
  - "(the supplier)"
paths:
  - "/home/<user>"
  - "/Users/<user>"
patterns:
  - "\\b\\d{3}[- ]?\\d{3}[- ]?\\d{4}\\b"     # phone numbers
  - "[\\w.+-]+@[\\w-]+\\.[\\w.]+"            # emails
allow:
  - "cheat_sheet.personal.yaml"             # ignored files are not published anyway
```

Adding a term is one line. Nothing is deleted automatically: the checker **reports**, the owner
decides.

## 4. Before any publish

1. `python3 tools/check_publish.py` → must exit `0`.
2. `git status --short` → nothing personal staged: no `*.personal.yaml`, no `reports/`.
3. The README and the screenshots: re-read them. A screenshot is a file like any other, and it
   shows exactly what the panel shows.
4. If a demo was recorded on real data, it is not published. It is rebuilt on the example file.

## 5. What was done on 2026-11-13

- `core/cheat_sheet.personal.yaml` was **tracked** and is now untracked and ignored: the owner's
  vocabulary is not in the repository history from that commit forward. The file stays on disk.
- Six personal terms were removed from 27 tracked files (agent name, owner name, partner name,
  username, supplier, home paths).
- Code defaults that hard-coded the agent's name now default to empty: an unnamed assistant,
  until the owner names it.
- `examples/vocab-personal.ejemplo.yaml` was added with fictional names, so the repository still
  teaches the format without teaching anyone's life.

> Note on history: earlier commits still contain what was published before this policy. Cleaning
> the history is a separate, destructive operation and it is the owner's decision, not the
> agent's.
