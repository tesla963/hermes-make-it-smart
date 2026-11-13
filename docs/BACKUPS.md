# Backups — when they are written and where they live

A rename touches the titles of the owner's sessions. That is not a cache: it is the database of
what he called his own work. So the rule is short and it is not negotiable:

> **No title is written before a backup of the current state exists on disk.**

---

## 1 · When the backup happens

| Moment | Backup? | Why |
|---|---|---|
| Opening the panel | **no** | opening a window looks, it does not touch |
| Entering **Process** | **no** | entering only refreshes the catalogue |
| Entering **New Rules** | **no** | the proposal is read, nothing is written |
| Confirming **Process** → process the sessions | **yes, first** | the user asked for a change: back up, then write |
| Confirming **New Rules** → back up and apply | **yes, first** | same rule, same order |
| Restoring original titles | **no new one** | it already writes its own ledger entry |

The order inside an action is invariable:

```
1 · write the backup      (catches the titles as they are right now)
2 · write the titles
3 · patch index.json so the snapshot stops lying
4 · record commit-last.json, which is what Revert reads
```

If step 1 fails, steps 2 and 3 never run. A backup that could not be written is a reason to stop,
not a warning to ignore.

**No backup is reused across actions.** One taken ten minutes ago describes a catalogue that may
already have changed; the backup is always written at the moment of the action.

---

## 2 · Where the files live, by platform

The plugin writes in **two** places, because there are two readers: the scripts (Python) and the
panel (the HTML app). Each has its own data directory, and both are backed up.

| Platform | Canonical (scripts write) | Mirror (the panel reads) |
|---|---|---|
| **macOS** | `~/.hermes/plugin-data/make-it-smart/` | `~/Library/Application Support/Hermes/plugin-files/data/make-it-smart/` |
| **Windows** | `%USERPROFILE%\.hermes\plugin-data\make-it-smart\` | `%APPDATA%\Hermes\plugin-files\data\make-it-smart\` |
| **Linux** | `~/.hermes/plugin-data/make-it-smart/` | `~/.config/Hermes/plugin-files/data/make-it-smart/` |

Inside each directory:

```
make-it-smart/
  index.json                    the catalogue (887 sessions in the current profile)
  facets.json                   the values of the ten fields
  proposed-index.json           the New Rules proposal — read, never applied by itself
  commit-last.json              the ledger of the last change: this is what Revert reads
  titles-origin.json            the day-0 title of every session, written once
  titles-journal.jsonl          every rename, with who asked for it
  publish-blocklist.yaml        personal terms that must never be published (canonical only)
  backups/
    index.json.pre-iq_20261112_120251        before the tag→iq migration
    index.json.pre-intent_20261113_100159    before the intention migration
    commit-backup-20261113_101500.json       before a rename
```

### Why two directories and not one

Hermes Desktop gives a plugin a sandboxed `files` API that resolves to the mirror, while the
Python tools work from the real home directory. Both point at the same conceptual data, so the
index builder copies the canonical file over the mirror after building it — and refuses to let an
older schema overwrite a newer one (the `_pisa_espejo()` guard).

The consequence for backups: **a restore has to be checked in both trees.** Restoring the
canonical file and leaving the mirror stale shows the owner old titles in his own panel.

---

## 3 · What each backup is for

| File | Written by | Restores |
|---|---|---|
| `index.json.pre-iq_*` | the axis migration | the catalogue before `tag0…tag9` became `iq0…iq9` |
| `index.json.pre-intent_*` | `tools/migrate_intentions.py` | the catalogue before the intention names were folded |
| `commit-backup-*.json` | the panel, at the moment of an action | the exact titles a commit replaced |
| `titles-origin.json` | the first time the plugin sees a session | the title the session had **before the plugin existed** |

`titles-origin.json` is the one that matters for uninstalling: without it, the titles the plugin
wrote stay written in Hermes after the plugin is gone.

---

## 4 · How to restore

**From the panel:** the **Revert** button, in Process, reads `commit-last.json` and puts every
title back. It respects a title the owner edited afterwards: if the current title no longer
matches the one the commit wrote, that session is skipped and counted as "respected".

**By hand**, on any platform: copy `backups/commit-backup-<stamp>.json` over `commit-last.json`
and press Revert. Or copy the whole `index.json.pre-*` file over `index.json` and rebuild:

```bash
python3 tools/build_index.py
```

**Never** restore the mirror without the canonical file, or the reverse. Both, or neither.

---

## 5 · What is not backed up, and why

- **Nothing personal leaves the machine.** The backups contain titles and ids: they are personal
  data, they live outside the repository, and `tools/check_publish.py` refuses to publish
  anything containing the owner's terms.
- **The model's reasoning is not backed up**: it is not data, it is reproducible.
- **The proposals are not backed up**: `proposed-index.json` can be regenerated with
  `python3 tools/propose_rename.py` at any time.
