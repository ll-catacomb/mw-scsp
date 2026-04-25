"""SQLite-backed store for memory + audit log.

Tier 0 ships: connection helper + init_db() runs the schema.
Tier 1 (`feature/memory`) extends with MemoryStore CRUD + retrieval.

See PROJECT_SPEC.md §7.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def db_path() -> Path:
    """Resolve the memory.db path from MEMORY_DB_PATH env var, default data/memory.db."""
    raw = os.environ.get("MEMORY_DB_PATH", "data/memory.db")
    p = Path(raw)
    if not p.is_absolute():
        # Repo root = parents[2] (this file is src/memory/store.py).
        p = Path(__file__).resolve().parents[2] / p
    return p


def init_db(path: Path | None = None) -> Path:
    """Create the database file (if missing) and apply the schema. Idempotent."""
    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(p) as conn:
        conn.executescript(schema)
        conn.commit()
    return p


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context-managed SQLite connection. Foreign keys on; row factory = sqlite3.Row."""
    p = path or db_path()
    if not p.exists():
        init_db(p)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
