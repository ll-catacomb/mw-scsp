"""SQLite-backed store for memory + audit log.

Tier 0 shipped: connection helper + init_db() runs the schema.
Tier 1 (`feature/memory`) extends with MemoryStore CRUD + retrieval.

See PROJECT_SPEC.md §7.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np

from src.memory.retrieval import Memory, score_memories

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _embedding_blob(embedding: np.ndarray | Sequence[float]) -> bytes:
    arr = np.asarray(embedding, dtype=np.float32)
    if arr.ndim != 1:
        raise ValueError(f"embedding must be 1-D, got shape {arr.shape}")
    return arr.tobytes()


def _row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        memory_id=row["memory_id"],
        agent_id=row["agent_id"],
        memory_type=row["memory_type"],
        description=row["description"],
        embedding=np.frombuffer(row["embedding"], dtype=np.float32),
        importance=int(row["importance"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
        source_run_id=row["source_run_id"],
        cited_memory_ids=(
            json.loads(row["cited_memory_ids"]) if row["cited_memory_ids"] else None
        ),
    )


class MemoryStore:
    """Generative-agents memory store backed by SQLite (`agent_memory` table).

    All methods are synchronous; the wrapper around LLM calls is async, but persistence
    itself is fast enough that holding the GIL through a SQLite write is fine for our
    pipeline volume.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path = path or db_path()
        init_db(self.path)

    # --- writes ------------------------------------------------------------

    def add_observation(
        self,
        agent_id: str,
        description: str,
        importance: int,
        embedding: np.ndarray | Sequence[float],
        source_run_id: str | None = None,
    ) -> str:
        return self._add(
            memory_type="observation",
            agent_id=agent_id,
            description=description,
            importance=importance,
            embedding=embedding,
            source_run_id=source_run_id,
            cited_memory_ids=None,
        )

    def add_reflection(
        self,
        agent_id: str,
        description: str,
        importance: int,
        embedding: np.ndarray | Sequence[float],
        cited_memory_ids: Sequence[str],
        source_run_id: str | None = None,
    ) -> str:
        return self._add(
            memory_type="reflection",
            agent_id=agent_id,
            description=description,
            importance=importance,
            embedding=embedding,
            source_run_id=source_run_id,
            cited_memory_ids=list(cited_memory_ids),
        )

    def _add(
        self,
        *,
        memory_type: str,
        agent_id: str,
        description: str,
        importance: int,
        embedding: np.ndarray | Sequence[float],
        source_run_id: str | None,
        cited_memory_ids: list[str] | None,
    ) -> str:
        if not 1 <= int(importance) <= 10:
            raise ValueError(f"importance must be 1..10, got {importance!r}")
        memory_id = str(uuid.uuid4())
        now = _now_iso()
        blob = _embedding_blob(embedding)
        cited = json.dumps(cited_memory_ids) if cited_memory_ids else None
        with connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO agent_memory (
                  memory_id, agent_id, memory_type, description, embedding,
                  importance, created_at, last_accessed_at, source_run_id, cited_memory_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    agent_id,
                    memory_type,
                    description,
                    blob,
                    int(importance),
                    now,
                    now,
                    source_run_id,
                    cited,
                ),
            )
        return memory_id

    def bump_last_accessed(
        self, memory_ids: Iterable[str], now: datetime | None = None
    ) -> None:
        ids = list(memory_ids)
        if not ids:
            return
        ts = _aware(now or datetime.now(timezone.utc)).isoformat()
        placeholders = ",".join("?" * len(ids))
        with connect(self.path) as conn:
            conn.execute(
                f"UPDATE agent_memory SET last_accessed_at = ? WHERE memory_id IN ({placeholders})",
                (ts, *ids),
            )

    # --- reads -------------------------------------------------------------

    def all_for_agent(
        self, agent_id: str, memory_types: Sequence[str] | None = None
    ) -> list[Memory]:
        with connect(self.path) as conn:
            if memory_types:
                placeholders = ",".join("?" * len(memory_types))
                rows = conn.execute(
                    f"SELECT * FROM agent_memory WHERE agent_id = ? AND memory_type IN ({placeholders})",
                    (agent_id, *memory_types),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_memory WHERE agent_id = ?", (agent_id,)
                ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def retrieve(
        self,
        agent_id: str,
        query_embedding: np.ndarray | Sequence[float],
        k: int = 8,
        now: datetime | None = None,
        memory_types: Sequence[str] | None = None,
    ) -> list[Memory]:
        """Top-k by Park et al. score; bumps last_accessed_at on returned rows."""
        candidates = self.all_for_agent(agent_id, memory_types=memory_types)
        if not candidates:
            return []
        scored = score_memories(candidates, np.asarray(query_embedding, dtype=np.float32), now=now)
        top = [m for m, _s in scored[:k]]
        self.bump_last_accessed((m.memory_id for m in top), now=now)
        # Update in-memory copies too so callers see the new timestamp.
        ts = _aware(now or datetime.now(timezone.utc))
        for m in top:
            m.last_accessed_at = ts
        return top

    def recent(self, agent_id: str, n: int = 100) -> list[Memory]:
        """Most recent memories by created_at, descending. For reflection question generation.

        Compares ISO-8601 strings directly — this preserves microsecond precision that
        SQLite's `datetime()` function would truncate.
        """
        with connect(self.path) as conn:
            rows = conn.execute(
                "SELECT * FROM agent_memory WHERE agent_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (agent_id, n),
            ).fetchall()
        return [_row_to_memory(r) for r in rows]

    def unreflected_importance_sum(self, agent_id: str) -> int:
        """Sum importance of observations created after this agent's most recent reflection.

        If no reflection exists yet, sum all observation importance. Park et al. reset the
        cumulative count at each reflection (§4.3); this matches that semantics.

        Compares ISO-8601 timestamps as strings to keep microsecond precision.
        """
        with connect(self.path) as conn:
            row = conn.execute(
                "SELECT MAX(created_at) AS last_reflect_at "
                "FROM agent_memory WHERE agent_id = ? AND memory_type = 'reflection'",
                (agent_id,),
            ).fetchone()
            cutoff = row["last_reflect_at"] if row else None
            if cutoff is None:
                row = conn.execute(
                    "SELECT COALESCE(SUM(importance), 0) AS s "
                    "FROM agent_memory WHERE agent_id = ? AND memory_type = 'observation'",
                    (agent_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COALESCE(SUM(importance), 0) AS s "
                    "FROM agent_memory "
                    "WHERE agent_id = ? AND memory_type = 'observation' "
                    "AND created_at > ?",
                    (agent_id, cutoff),
                ).fetchone()
        return int(row["s"])

    def cached_summary(self, agent_id: str) -> str | None:
        """Most recent cached agent_summary paragraph, or None."""
        with connect(self.path) as conn:
            row = conn.execute(
                "SELECT summary FROM agent_summary WHERE agent_id = ? "
                "ORDER BY version DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        return row["summary"] if row else None

    def write_summary(self, agent_id: str, summary: str) -> int:
        """Append a new versioned summary paragraph. Returns the new version number."""
        with connect(self.path) as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM agent_summary WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            next_version = int(row["v"]) + 1
            conn.execute(
                "INSERT INTO agent_summary (agent_id, version, summary, created_at) "
                "VALUES (?, ?, ?, ?)",
                (agent_id, next_version, summary, _now_iso()),
            )
        return next_version


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
