"""Hermes Agent adapter.

Reads sessions from every profile's state.db in READ-ONLY mode and writes session
titles through the host's public API (``SessionDB.set_session_title``).

This module is the ONLY place in the project allowed to import ``hermes_state``.
``core/`` must stay host-free — see tests/test_core_purity.py.
"""

from __future__ import annotations

import glob
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

# --------------------------------------------------------------------------- #
# Normalized record — the boundary between host and classifier
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SessionRecord:
    id: str
    title: str | None
    title_source: str | None
    created_at: str
    messages: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    hours: float = 0.0
    tokens: int = 0
    posts: int = 0
    profile: str = "default"
    hidden: bool = False
    source: str | None = None
    # Mother session of a subagent transcript (delegate_task). None for a root session.
    parent_session_id: str | None = None
    # Last real use (state.db → sessions.last_activity_at), epoch seconds. None when the
    # host's schema has no such column or the value is empty.
    last_used_at: float | None = None


# --------------------------------------------------------------------------- #
# Text cleaning
# --------------------------------------------------------------------------- #

_ATTACHMENT_RE = re.compile(r"\[The user sent (?:an? )?\w+~?\s*\.\.\..*?\]", re.S)
_COMPACTION_RE = re.compile(r"\[CONTEXT COMPACTION[^\]]*\].*?(?=\n\n|\Z)", re.S)
_GROUP_ENVELOPE_RE = re.compile(r'^\[Group chat:\s*"[^"]*"\]\s*You are @[\w.-]+[,.]?\s*', re.S)
_CRON_RE = re.compile(r"^\[IMPORTANT:\s*You are running as a scheduled cron job.*?(?=\n\n|\Z)", re.S | re.I)
_SYSTEM_NOISE_RE = re.compile(r"^(?:\[IMPORTANT:|\[SYSTEM:|\[REMINDER:).*?(?=\n\n|\Z)", re.S)
_URL_RE = re.compile(r"https?://\S+")
_MD_FENCE_RE = re.compile(r"```.*?```", re.S)


def clean_message(text: str) -> str:
    """Strip everything that is not the user's actual words.

    A naive read sends attachment banners, group-chat envelopes and compaction
    carriers to the classifier as if they were the subject of the session. A
    comparable plugin shipped hash-like titles because of exactly this.
    """
    if not text:
        return ""
    t = _MD_FENCE_RE.sub(" ", text)
    t = _ATTACHMENT_RE.sub(" ", t)
    t = _COMPACTION_RE.sub(" ", t)
    t = _GROUP_ENVELOPE_RE.sub("", t)
    t = _CRON_RE.sub("", t)
    t = _SYSTEM_NOISE_RE.sub("", t)
    t = _URL_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


MIN_MESSAGE_CHARS = 12
MAX_MESSAGES = 5


def select_messages(rows: Iterable[str]) -> list[str]:
    """Keep up to MAX_MESSAGES cleaned user turns, in order, above the size floor."""
    out: list[str] = []
    for raw in rows:
        c = clean_message(raw)
        if len(c) >= MIN_MESSAGE_CHARS:
            out.append(c[:600])
        if len(out) >= MAX_MESSAGES:
            break
    return out


# --------------------------------------------------------------------------- #
# Discovery & reading (read-only)
# --------------------------------------------------------------------------- #


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def discover_databases(home: Path | None = None) -> list[tuple[str, Path]]:
    """Return [(profile_name, path)] for the default profile and every other one."""
    home = home or hermes_home()
    found: list[tuple[str, Path]] = []
    base = home / "state.db"
    if base.exists():
        found.append(("default", base))
    for path in sorted(glob.glob(str(home / "profiles" / "*" / "state.db"))):
        found.append((Path(path).parent.name, Path(path)))
    return found


def _connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _iso_date(value: Any) -> str:
    """started_at is stored as an epoch float in some profiles and as text in others."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        try:
            # Local time, not UTC: a session started at 23:20 in Panama is still
            # that day, not the next one. Using UTC shifted every evening session.
            return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(value)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else ""


def _epoch_seconds(value: Any) -> float | None:
    """Epoch seconds from an epoch number (s or ms), numeric text or ISO text. None if unusable."""
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        try:
            n = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    if not n or n <= 0 or n != n:
        return None
    return n / 1000.0 if n > 1e12 else n


ACTIVE_GAP_CAP_SECONDS = 300  # Cap consecutive message delta to 5 min (300 s) to discard idle periods.


def _session_message_stats(conn: sqlite3.Connection) -> tuple[dict[str, float], dict[str, float]]:
    """En una sola pasada sobre `messages`: (minutos_activos, max_timestamp_ultimo_mensaje)."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "messages" not in tables:
        return {}, {}

    cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
    active_filter = "AND active = 1 " if "active" in cols else ""
    sql = (
        "SELECT session_id, timestamp FROM messages "
        f"WHERE timestamp IS NOT NULL {active_filter}"
        "ORDER BY session_id, timestamp"
    )
    result: dict[str, float] = {}
    last_ts: dict[str, float] = {}
    current_session_id: str | None = None
    prev_ts: float | None = None
    acc_seconds: float = 0.0

    for row in conn.execute(sql):
        sess_id = row[0]
        try:
            ts = float(row[1])
        except (ValueError, TypeError):
            continue

        if sess_id != current_session_id:
            if current_session_id is not None:
                result[current_session_id] = round(acc_seconds / 60.0, 2)
            current_session_id = sess_id
            prev_ts = ts
            acc_seconds = 0.0
        else:
            if prev_ts is not None:
                delta = ts - prev_ts
                if delta > 0:
                    acc_seconds += min(delta, ACTIVE_GAP_CAP_SECONDS)
            prev_ts = ts

    if current_session_id is not None:
        result[current_session_id] = round(acc_seconds / 60.0, 2)

    max_sql = (
        "SELECT session_id, MAX(timestamp) FROM messages "
        f"WHERE timestamp IS NOT NULL {active_filter}"
        "GROUP BY session_id"
    )
    for row in conn.execute(max_sql):
        sess_id = row[0]
        ep = _epoch_seconds(row[1])
        if sess_id and ep is not None:
            last_ts[sess_id] = ep

    return result, last_ts


def active_minutes_by_session(conn: sqlite3.Connection) -> dict[str, float]:
    """Minutos de trabajo por sesión: Σ min(gap, 300 s) entre mensajes consecutivos."""
    return _session_message_stats(conn)[0]


def read_sessions(profile: str, path: Path, limit: int | None = None) -> list[SessionRecord]:
    """Read every session of one profile. Never writes."""
    out: list[SessionRecord] = []
    conn = _connect_ro(path)
    try:
        minutos, ultimo_msg = _session_message_stats(conn)
        # parent_session_id exists in current hosts; an older state.db without it must
        # still read, so the column is selected only when the table has it.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        parent_col = "parent_session_id" if "parent_session_id" in cols else "NULL AS parent_session_id"
        last_col = "last_activity_at" if "last_activity_at" in cols else "NULL AS last_activity_at"
        sql = (
            "SELECT id, title, title_source, started_at, message_count, "
            "input_tokens, output_tokens, estimated_cost_usd, actual_cost_usd, hidden, source, "
            f"{parent_col}, {last_col} "
            "FROM sessions ORDER BY started_at"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        for row in conn.execute(sql):
            keys = row.keys()
            out.append(
                SessionRecord(
                    id=row["id"],
                    title=row["title"],
                    title_source=row["title_source"] if "title_source" in keys else None,
                    created_at=_iso_date(row["started_at"]),
                    cost_usd=float(
                        (row["actual_cost_usd"] if "actual_cost_usd" in keys else 0)
                        or (row["estimated_cost_usd"] if "estimated_cost_usd" in keys else 0)
                        or 0
                    ),
                    hours=minutos.get(row["id"], 0.0),
                    tokens=int(
                        ((row["input_tokens"] or 0) if "input_tokens" in keys else 0)
                        + ((row["output_tokens"] or 0) if "output_tokens" in keys else 0)
                    ),
                    posts=int((row["message_count"] or 0) if "message_count" in keys else 0),
                    profile=profile,
                    hidden=bool(row["hidden"]) if "hidden" in keys else False,
                    source=row["source"] if "source" in keys else None,
                    parent_session_id=(row["parent_session_id"] or None) if "parent_session_id" in keys else None,
                    # Last real use: MAX(messages.timestamp WHERE active=1) -> last_activity_at -> started_at.
                    last_used_at=(
                        ultimo_msg.get(row["id"])
                        or (_epoch_seconds(row["last_activity_at"]) if "last_activity_at" in keys else None)
                        or _epoch_seconds(row["started_at"])
                    ),
                )
            )
    finally:
        conn.close()
    return out


def attach_messages(record: SessionRecord, path: Path) -> SessionRecord:
    """Fill in the cleaned user turns for one session."""
    conn = _connect_ro(path)
    try:
        rows = [
            r["content"]
            for r in conn.execute(
                "SELECT content FROM messages WHERE session_id = ? AND role = 'user' "
                "ORDER BY rowid LIMIT 40",
                (record.id,),
            )
        ]
    finally:
        conn.close()
    return SessionRecord(
        **{**record.__dict__, "messages": select_messages(rows or [])}
    )


def load_all(home: Path | None = None, with_messages: bool = True) -> list[SessionRecord]:
    records: list[SessionRecord] = []
    for profile, path in discover_databases(home):
        for rec in read_sessions(profile, path):
            records.append(attach_messages(rec, path) if with_messages else rec)
    return records


# --------------------------------------------------------------------------- #
# Writing — only through the host API
# --------------------------------------------------------------------------- #


class TitleWriteError(RuntimeError):
    pass


class HermesTitleWriter:
    """Write session titles through ``SessionDB``, never with raw SQL.

    ``SessionDB.set_session_title`` carries every invariant we would otherwise
    have to reimplement: the provenance ladder, an atomic compare-and-swap, the
    release of a duplicate held by a ghost or a compressed ancestor, character
    sanitizing, the 100-character ceiling, and the canonical Bot Chat guard.
    """

    def __init__(self, max_title: int = 100) -> None:
        try:
            from hermes_state import SessionDB  # local import: keeps core/ pure
        except Exception:  # not on sys.path yet: try the Hermes install
            import sys
            home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
            for candidate in (Path(home) / "hermes-agent", Path.cwd()):
                if (Path(candidate) / "hermes_state.py").exists() and str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))
            try:
                from hermes_state import SessionDB  # noqa: PLC0415
            except Exception as exc:  # pragma: no cover
                raise TitleWriteError(
                    "SessionDB is not importable. This adapter must run inside the "
                    "Hermes runtime (same interpreter/env as the gateway)."
                ) from exc
        self._SessionDB = SessionDB
        self._dbs: dict[str, Any] = {}
        self.max_title = max_title

    def _db_for(self, db_path: Any = None):
        """One SessionDB per database file, cached.

        A single default SessionDB is not enough: sessions live in the default
        database AND in ``~/.hermes/profiles/<name>/state.db``. Pointing every
        write at the default one made ``set_session_title`` return False for
        every session kept in another profile — silently, because a missing id
        is not an error.
        """
        key = str(db_path) if db_path else "__default__"
        db = self._dbs.get(key)
        if db is None:
            # SessionDB expects a Path: a bare str dies inside _open_writer on
            # db_path.parent with an AttributeError that reads like a host bug.
            db = self._SessionDB(Path(db_path)) if db_path else self._SessionDB()
            self._dbs[key] = db
        return db

    @property
    def _db(self):
        """The default database, kept for callers that still read through it."""
        return self._db_for(None)

    # -- reads ----------------------------------------------------------- #

    def current_title(self, session_id: str, db_path: Any = None) -> str | None:
        return self._db_for(db_path).get_session_title(session_id)

    def current_source(self, session_id: str, db_path: Any = None) -> str | None:
        return self._db_for(db_path).get_session_title_source(session_id)

    # -- writes ---------------------------------------------------------- #

    def rename(self, session_id: str, title: str, db_path: Any = None) -> bool:
        """Rename on the user's behalf. Returns True if the row changed ."""
        title = (title or "").strip()
        if len(title) > self.max_title:
            raise TitleWriteError(
                f"title is {len(title)} chars, over the {self.max_title} limit — "
                "cut it before calling, do not let the host raise"
            )
        return bool(self._db_for(db_path).set_session_title(session_id, title))

    def rename_batch(self, pairs: Iterable[tuple[str, str]], db_path: Any = None) -> dict[str, Any]:
        """Rename many. One conflict never costs the batch.

        Returns an honest receipt: attempted / written / conflicts, with the
        reasons. A cheerful "done" is not a report.
        """
        attempted = written = 0
        conflicts: list[dict[str, str]] = []
        for session_id, title in pairs:
            attempted += 1
            try:
                if self.rename(session_id, title, db_path):
                    written += 1
                else:
                    # False means the id is not in this database — a silent miss
                    # otherwise, and the batch still reports success.
                    conflicts.append({"id": session_id, "reason": "no such session in this database"})
            except ValueError as exc:  # genuine duplicate, not our bug
                conflicts.append({"id": session_id, "reason": str(exc)})
            except Exception as exc:  # noqa: BLE001 - never abort the batch
                conflicts.append({"id": session_id, "reason": f"{type(exc).__name__}: {exc}"})
        return {
            "attempted": attempted,
            "written": written,
            "conflicts": len(conflicts),
            "details": conflicts,
        }


# --------------------------------------------------------------------------- #
# Backup
# --------------------------------------------------------------------------- #


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_databases(dest_root: Path, reason: str, home: Path | None = None) -> Path:
    """Copy every state.db (gzipped) and write a MANIFEST.json with hashes."""
    home = home or hermes_home()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    dest = dest_root / f"{stamp}_{reason}"
    dest.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"created_at": stamp, "reason": reason, "files": []}
    for profile, path in discover_databases(home):
        target = dest / (f"{profile}.db.gz" if profile != "default" else "state.db.gz")
        with open(path, "rb") as src, gzip.open(target, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        manifest["files"].append(
            {
                "profile": profile,
                "source": str(path),
                "archive": target.name,
                "source_sha256": sha256_of(path),
                "source_bytes": path.stat().st_size,
                "archive_bytes": target.stat().st_size,
            }
        )
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dest


def verify_backup(dest: Path) -> bool:
    manifest = json.loads((dest / "MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        src = Path(entry["source"])
        if src.exists() and sha256_of(src) != entry["source_sha256"]:
            return False
    return True


__all__ = [
    "ACTIVE_GAP_CAP_SECONDS",
    "SessionRecord",
    "active_minutes_by_session",
    "clean_message",
    "select_messages",
    "discover_databases",
    "read_sessions",
    "load_all",
    "HermesTitleWriter",
    "TitleWriteError",
    "backup_databases",
    "verify_backup",
]
