#!/usr/bin/env python3
"""Tests for session active hours/minutes calculation.

Run with:  python3 -m pytest tests/ -q
           or: python3 tests/test_hours.py
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.hermes import (  # noqa: E402
    ACTIVE_GAP_CAP_SECONDS,
    SessionRecord,
    active_minutes_by_session,
    attach_messages,
    read_sessions,
)


def _create_synthetic_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                title_source TEXT,
                started_at REAL,
                message_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                estimated_cost_usd REAL,
                actual_cost_usd REAL,
                hidden INTEGER,
                source TEXT,
                parent_session_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL
            )
            """
        )

        # 5 sessions: a, b, c, d, e
        sessions_data = [
            ("a", "Session A", "user", 1000.0, 1, 10, 20, 0.01, 0.01, 0, "test", None),
            ("b", "Session B", "user", 1000.0, 2, 10, 20, 0.01, 0.01, 0, "test", None),
            ("c", "Session C", "user", 1000.0, 3, 10, 20, 0.01, 0.01, 0, "test", None),
            ("d", "Session D", "user", 1000.0, 2, 10, 20, 0.01, 0.01, 0, "test", None),
            ("e", "Session E", "user", 1000.0, 4, 10, 20, 0.01, 0.01, 0, "test", None),
            ("empty", "Session Empty", "user", 1000.0, 0, 0, 0, 0.0, 0.0, 0, "test", None),
        ]
        conn.executemany(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            sessions_data,
        )

        messages_data = [
            # 1. 'a': 1 mensaje -> 0.0
            ("m_a1", "a", "user", "Message A1: inspecting some code here", 1000.0),

            # 2. 'b': 2 mensajes a 600 s -> 5.0 (topado a 300 s = 5.0 min)
            ("m_b1", "b", "user", "Message B1: initial question about system", 1000.0),
            ("m_b2", "b", "assistant", "Message B2: answer after 600s gap", 1600.0),

            # 3. 'c': 3 mensajes (0, 300, 900) -> 10.0 (300 s + 300 s topado = 600 s = 10.0 min)
            ("m_c1", "c", "user", "Message C1: starting task", 1000.0),
            ("m_c2", "c", "assistant", "Message C2: intermediate reply at 300s", 1300.0),
            ("m_c3", "c", "user", "Message C3: follow up reply at 900s", 1900.0),

            # 4. 'd': 2 mensajes con delta no positivo (timestamp identico -> delta 0) -> 0.0
            ("m_d1", "d", "user", "Message D1: rapid message turn one", 1000.0),
            ("m_d2", "d", "assistant", "Message D2: rapid message turn two", 1000.0),

            # 5. 'e': 4 mensajes: 0, 60, 120, 480 -> 60 + 60 + 300 (topado) = 420 s = 7.0 min
            ("m_e1", "e", "user", "Message E1: step one", 1000.0),
            ("m_e2", "e", "assistant", "Message E2: step two at +60s", 1060.0),
            ("m_e3", "e", "user", "Message E3: step three at +120s", 1120.0),
            ("m_e4", "e", "assistant", "Message E4: step four at +480s", 1480.0),
        ]
        conn.executemany(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
            messages_data,
        )
        conn.commit()
    finally:
        conn.close()


def test_active_minutes_by_session_cases() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        _create_synthetic_db(db_path)

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            mins = active_minutes_by_session(conn)
        finally:
            conn.close()

        # 1. 'a': 1 mensaje -> 0.0
        assert mins["a"] == 0.0, f"Expected 0.0 for 'a', got {mins['a']}"

        # 2. 'b': 2 mensajes a 600 s -> 5.0 (topado a 300 s)
        assert mins["b"] == 5.0, f"Expected 5.0 for 'b', got {mins['b']}"

        # 3. 'c': 3 mensajes (0, 300, 900) -> 10.0 (5.0 + 5.0)
        assert mins["c"] == 10.0, f"Expected 10.0 for 'c', got {mins['c']}"

        # 4. 'd': 2 mensajes con delta no positivo -> 0.0
        assert mins["d"] == 0.0, f"Expected 0.0 for 'd', got {mins['d']}"

        # 5. 'e': 4 mensajes (0, 60, 120, 480) -> 7.0 min (1 + 1 + 5)
        assert mins["e"] == 7.0, f"Expected 7.0 for 'e', got {mins['e']}"

        # 6. Suma de todas las claves requeridas = 22.0
        keys = ["a", "b", "c", "d", "e"]
        total = round(sum(mins[k] for k in keys), 2)
        assert total == 22.0, f"Expected sum 22.0, got {total}"


def test_delta_negative_invariance() -> None:
    """A negative or zero delta must never contribute active seconds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("CREATE TABLE messages (id TEXT, session_id TEXT, role TEXT, content TEXT, timestamp REAL)")
            # Two messages with equal timestamps (delta 0)
            conn.execute("INSERT INTO messages VALUES ('m1', 'zero_delta', 'user', 'hi', 100.0)")
            conn.execute("INSERT INTO messages VALUES ('m2', 'zero_delta', 'user', 'hi', 100.0)")
            conn.commit()

            mins = active_minutes_by_session(conn)
            assert mins["zero_delta"] == 0.0
        finally:
            conn.close()


def test_read_sessions_integration() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        _create_synthetic_db(db_path)

        records = read_sessions("synthetic", db_path)
        rec_by_id = {r.id: r for r in records}

        assert rec_by_id["a"].hours == 0.0
        assert rec_by_id["b"].hours == 5.0
        assert rec_by_id["c"].hours == 10.0
        assert rec_by_id["d"].hours == 0.0
        assert rec_by_id["e"].hours == 7.0
        assert rec_by_id["empty"].hours == 0.0

        # Last message timestamp wins over started_at (1000.0) when last_activity_at is absent
        assert rec_by_id["b"].last_used_at == 1600.0
        assert rec_by_id["c"].last_used_at == 1900.0
        assert rec_by_id["e"].last_used_at == 1480.0
        assert rec_by_id["empty"].last_used_at == 1000.0


def test_attach_messages_preserves_hours() -> None:
    """attach_messages reconstructs SessionRecord; verify hours field survives."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        _create_synthetic_db(db_path)

        records = read_sessions("synthetic", db_path)
        rec_b = next(r for r in records if r.id == "b")
        assert rec_b.hours == 5.0

        attached = attach_messages(rec_b, db_path)
        assert attached.hours == 5.0, f"Expected hours to survive attach_messages, got {attached.hours}"
        assert len(attached.messages) > 0


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"  ERROR {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
