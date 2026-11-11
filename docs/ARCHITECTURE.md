# Architecture

## The two halves

```
core/          pure Python — knows nothing about Hermes
adapters/      one adapter per host
desktop/       the UI, on the Desktop plugin SDK
```

The rule is absolute: **`core/` never imports `hermes_state`, `hermes_cli` or anything from
the host.** A test enforces it (`tests/test_core_purity.py`).

## The boundary: `SessionRecord`

Everything the classifier needs, and nothing about where it came from.

```python
@dataclass(frozen=True)
class SessionRecord:
    id: str
    title: str | None
    title_source: str | None      # derived | llm | user
    created_at: str               # ISO date
    messages: list[str]           # up to 5 cleaned user turns
    cost_usd: float
    hours: float
    tokens: int
    posts: int
    profile: str = "default"
    hidden: bool = False
```

The classifier consumes `SessionRecord` and returns a `Facets`:

```python
@dataclass(frozen=True)
class Facets:
    subject: str
    subject_ordinal: int          # MMM
    tag1: str
    tag2: str
    pillar: str
    country: str | None
    year: str | None
    machine: str | None
    description: str
    verb: str | None
```

Nothing else crosses the boundary in either direction.

## Why this matters

The same classifier can run against any host that can produce a `SessionRecord`:

| Host | How it would fill the record | How it would rename |
|---|---|---|
| Hermes Agent | `state.db` read-only | `SessionDB.set_session_title()` |
| OpenClaw | per-agent SQLite transcript store | `sessions.patch { label }` |
| A CSV export | parsed rows | write back to the CSV |

A port is a new adapter of ~300 lines. The 1,500 lines of taxonomy rules, prompt logic
and normalization stay untouched.

## The Hermes adapter

### Reading

Twelve databases: `~/.hermes/state.db` plus one per profile under
`~/.hermes/profiles/*/state.db`.

Every connection is opened **read-only**:

```python
sqlite3.connect(f"file:{path}?mode=ro", uri=True)
```

Reading while Hermes is running is safe. Writing is not done here at all.

Three things the adapter must strip before the text reaches the classifier:

1. **Attachment blocks** — `[The user sent an image~ ...]`.
2. **Tool envelopes** — group-chat wrappers such as `[Group chat: "X"] You are @name…`,
   which a naive read sends as the first user message and which produced hash-like titles
   in a comparable plugin.
3. **Compaction carriers** — `[CONTEXT COMPACTION: ...]` handoff rows.

### Writing

```python
from hermes_state import SessionDB

db = SessionDB()
db.set_session_title(session_id, title)
```

Never `UPDATE sessions`. The API is not a convenience — it is the only path that carries
the invariants:

| Invariant | Enforced by |
|---|---|
| `user` titles are never downgraded | provenance ladder |
| No torn write while the titler runs | compare-and-swap in one transaction |
| A duplicate held by a ghost / compressed ancestor is released | conflict resolution |
| 100-character ceiling and character sanitizing | `sanitize_title` |
| The canonical Bot Chat keeps its identity | explicit guard |

### The write loop

```python
attempted = written = conflicts = 0
for rec, facets in batch:
    title = render(rec, facets)          # our format, already <= 100 chars
    try:
        ok = db.set_session_title(rec.id, title)
        written += ok
    except ValueError as e:              # genuine conflict, not our bug
        conflicts += 1
        log.warning("skip %s: %s", rec.id, e)
    attempted += 1
```

Three things are deliberate here:

- **The title is cut to 100 characters *before* the call.** The API raises on overflow;
  discovering that in production would be a bug.
- **A `ValueError` skips one session, never the batch.** One bad title must not cost 883.
- **The report is honest**: `attempted / written / conflicts`, not a cheerful "done".

### Backups

Before the first write of any run:

```
/Volumes/1TB_HD/Backups-Lisa/<date>_<reason>/
    state.db, profiles/*/state.db      (compressed)
    MANIFEST.json                      sha256 per file, sizes, counts
```

Verified by hash before the write loop starts. Non-negotiable.

## The Desktop half

`desktop/plugin.js` — plain ESM, no build, no JSX (the loader does not compile):

- `ROUTES_AREA` — the catalog page
- `SIDEBAR_NAV_AREA` — its sidebar entry
- `SESSION_ROW_AREAS` — facet chips on session rows
- `ctx.rest('/sessions')` — reaches the Python backend

Theming uses `var(--ui-*)` variables so it follows the app, not a hardcoded palette.

## The backend

`dashboard/manifest.json` + `dashboard/plugin_api.py`, mounted under
`/api/plugins/hermes-make-it-smart/`.

| Route | Purpose |
|---|---|
| `GET /sessions` | the index, with facets and metrics |
| `GET /facets` | counts per facet value |
| `POST /classify` | classify a batch (dry-run by default) |
| `POST /rename` | write titles through `SessionDB` |
| `GET /report/{subject}` | unified report across a subject series |

`POST /rename` refuses to run without a `confirm: true` field and a fresh backup receipt.

## Testing

| Suite | What it protects |
|---|---|
| `test_core_purity.py` | `core/` has no host imports |
| `test_format.py` | 100 chars, no subject repeating Tag1, ordinals without gaps |
| `test_title_api.py` | every write goes through `SessionDB`, never raw SQL |
| `test_backup.py` | a backup exists and its hashes match before any write |
| `test_eval.py` | the owned corrections still classify correctly |
