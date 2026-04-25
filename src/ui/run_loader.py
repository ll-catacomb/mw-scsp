"""Adapter layer: real reads from `data/runs/{run_id}/` and `data/memory.db`.

Tier 2 swaps the Tier-1 mock fixtures (`src/ui/fixtures.py`) for this module.
Each artifact missing on disk falls back to the corresponding mock so the UI
still renders during Tier-2 development before every stage has run.

Artifact contract (lives in `data/runs/{run_id}/`):
- `manifest.json`      — written by `src/llm/manifest.py::write_manifest`. Always present.
- `modal_moves.json`   — `list[ModalMoveSchema]` rows + provider/model/temp/instance_idx/move_id.
- `clusters.json`      — Stage-3 clustering. Tier-1 shape `{cluster_assignments, cluster_themes}`.
- `convergence.json`   — Stage-3 narration (ConvergenceNarration dump). Tier-2 pipeline writes it.
- `convergence.md`     — Optional prose rendering of the narration.
- `candidates.json`    — Stage-4 off-distribution proposals.
- `judgments.json`     — Stage-5 judge outputs.
- `menu.md`            — Optional rendered menu prose.

`llm_calls` rows live in `data/memory.db` keyed by `run_id` per `schema.sql`.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from src.ui import fixtures


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runs_dir() -> Path:
    raw = os.environ.get("RUN_ARTIFACTS_DIR", "data/runs")
    p = Path(raw)
    if not p.is_absolute():
        p = _repo_root() / p
    return p


def _db_path() -> Path:
    raw = os.environ.get("MEMORY_DB_PATH", "data/memory.db")
    p = Path(raw)
    if not p.is_absolute():
        p = _repo_root() / p
    return p


@contextmanager
def _connect() -> Iterator[sqlite3.Connection | None]:
    """Yield a row-factory'd connection, or None if the db is missing."""
    p = _db_path()
    if not p.exists():
        yield None
        return
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def list_runs() -> list[dict]:
    """All runs known to the system, newest first.

    Reads the `runs` table primarily; any on-disk run with a manifest but no DB
    row gets surfaced too (covers manual artifact drops). Returns dicts with
    `run_id`, `scenario_id`, `started_at`, `completed_at`, `status`,
    `total_cost`, plus a derived `label` for the picker.
    """
    rows: dict[str, dict] = {}

    with _connect() as conn:
        if conn is not None:
            for r in conn.execute(
                """
                SELECT r.run_id, r.scenario_id, r.started_at, r.completed_at, r.status,
                       COALESCE(SUM(c.cost_usd), 0.0) AS total_cost,
                       COUNT(c.call_id) AS call_count
                FROM runs r
                LEFT JOIN llm_calls c ON c.run_id = r.run_id
                GROUP BY r.run_id
                """
            ).fetchall():
                rows[r["run_id"]] = {
                    "run_id": r["run_id"],
                    "scenario_id": r["scenario_id"],
                    "started_at": r["started_at"],
                    "completed_at": r["completed_at"],
                    "status": r["status"],
                    "total_cost": float(r["total_cost"]) if r["total_cost"] else 0.0,
                    "call_count": int(r["call_count"]) if r["call_count"] else 0,
                }

    runs_root = _runs_dir()
    if runs_root.exists():
        for sub in runs_root.iterdir():
            if not sub.is_dir() or sub.name in rows:
                continue
            manifest = _read_json(sub / "manifest.json")
            if not manifest:
                continue
            scen = manifest.get("scenario") or {}
            rows[sub.name] = {
                "run_id": sub.name,
                "scenario_id": scen.get("scenario_id") or manifest.get("scenario_id") or "—",
                "started_at": manifest.get("started_at"),
                "completed_at": None,
                "status": "manifest-only",
                "total_cost": 0.0,
                "call_count": 0,
            }

    out = list(rows.values())
    out.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    for r in out:
        scen = r.get("scenario_id") or "—"
        cost = r.get("total_cost") or 0.0
        status = r.get("status") or "—"
        r["label"] = f"{r['run_id'][:8]}… · {scen} · {status} · ${cost:.2f}"
    return out


def _llm_calls_for(run_id: str) -> list[dict]:
    with _connect() as conn:
        if conn is None:
            return list(fixtures.MOCK_LLM_CALLS)
        rows = conn.execute(
            """
            SELECT call_id, run_id, stage, agent_id, provider, model, temperature,
                   system_prompt, user_prompt, raw_response, parsed_output,
                   prompt_hash, prompt_version,
                   input_tokens, output_tokens, latency_ms, cost_usd, timestamp
            FROM llm_calls
            WHERE run_id = ?
            ORDER BY timestamp ASC
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def _totals_from_calls(calls: list[dict]) -> dict:
    total_in = sum((c.get("input_tokens") or 0) for c in calls)
    total_out = sum((c.get("output_tokens") or 0) for c in calls)
    total_cost = sum((c.get("cost_usd") or 0.0) for c in calls)
    return {
        "llm_calls": len(calls),
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cost_usd": round(total_cost, 4),
    }


def _runs_row_for(run_id: str) -> dict | None:
    with _connect() as conn:
        if conn is None:
            return None
        row = conn.execute(
            "SELECT run_id, scenario_id, started_at, completed_at, status FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None


def load_run(run_id: str) -> dict:
    """Load every artifact for `run_id`, falling back to mocks for missing pieces.

    Returns a dict with these keys:

    - `run_id`            — the requested id
    - `scenario`          — dict from manifest.json's `scenario` block (or mock)
    - `manifest`          — full manifest dict, augmented with `totals`, `completed_at`, `status`
    - `modal_moves`       — list of ModalMoveSchema-shaped dicts (or mock fallback)
    - `clusters_raw`      — `{cluster_assignments, cluster_themes}` (Tier-1 shape) or None
    - `convergence`       — ConvergenceNarration dict (or mock fallback)
    - `convergence_md`    — optional prose rendering (str or None)
    - `candidates`        — Stage-4 proposals (or mock fallback if missing)
    - `judgments`         — Stage-5 judge rows (or empty list)
    - `menu`              — surviving + non-surviving proposals reshaped for UI consumption
    - `menu_md`           — optional prose rendering (str or None)
    - `llm_calls`         — full row list from data/memory.db (or mock fallback)
    - `is_real`           — True iff a manifest.json was actually found on disk
    """
    run_path = _runs_dir() / run_id
    manifest = _read_json(run_path / "manifest.json")
    is_real = manifest is not None
    if manifest is None:
        manifest = dict(fixtures.MOCK_MANIFEST)

    runs_row = _runs_row_for(run_id)
    if runs_row:
        manifest.setdefault("scenario_id", runs_row["scenario_id"])
        manifest["completed_at"] = runs_row["completed_at"]
        manifest["status"] = runs_row["status"]
        manifest.setdefault("started_at", runs_row["started_at"])

    scenario = manifest.get("scenario") or {}

    modal_moves = _read_json(run_path / "modal_moves.json")
    if modal_moves is None:
        modal_moves = list(fixtures.MOCK_MODAL_MOVES)

    clusters_raw = _read_json(run_path / "clusters.json")

    convergence = _read_json(run_path / "convergence.json")
    if convergence is None:
        convergence = _convergence_from_clusters(clusters_raw, modal_moves)
    if not convergence.get("clusters") and not convergence.get("convergence_summary"):
        convergence = dict(fixtures.MOCK_CONVERGENCE)

    convergence_md = _read_text(run_path / "convergence.md")

    candidates = _read_json(run_path / "candidates.json")
    judgments = _read_json(run_path / "judgments.json") or []
    menu = _menu_from_artifacts(candidates, judgments)
    if not menu:
        menu = list(fixtures.MOCK_MENU)

    menu_md = _read_text(run_path / "menu.md")

    calls = _llm_calls_for(run_id)
    if not calls and not is_real:
        calls = list(fixtures.MOCK_LLM_CALLS)

    if calls and is_real:
        manifest["totals"] = _totals_from_calls(calls)

    return {
        "run_id": run_id,
        "scenario": scenario,
        "manifest": manifest,
        "modal_moves": modal_moves,
        "clusters_raw": clusters_raw,
        "convergence": convergence,
        "convergence_md": convergence_md,
        "candidates": candidates,
        "judgments": judgments,
        "menu": menu,
        "menu_md": menu_md,
        "llm_calls": calls,
        "is_real": is_real,
    }


def _convergence_from_clusters(
    clusters_raw: dict | None, modal_moves: list[dict]
) -> dict:
    """Build a minimal ConvergenceNarration-shaped dict from raw clustering.

    Used when `convergence.json` doesn't exist yet. Tier-1's `clusters.json` is
    `{cluster_assignments: list[int|None], cluster_themes: list|None}` — we turn
    that into the richer per-cluster shape the UI expects, leaving themes blank
    when none are available.
    """
    out = {
        "convergence_summary": "",
        "clusters": [],
        "notable_absences": [],
        "cross_run_observations": [],
    }
    if not clusters_raw:
        return out

    assignments = clusters_raw.get("cluster_assignments") or []
    themes = clusters_raw.get("cluster_themes") or []
    if not assignments or all(a is None for a in assignments):
        return out

    by_cluster: dict[int, list] = {}
    for idx, cid in enumerate(assignments):
        if cid is None:
            continue
        by_cluster.setdefault(int(cid), []).append(idx)

    for cid, members in sorted(by_cluster.items()):
        member_ids = []
        rep_actions = []
        for mi in members:
            if mi < len(modal_moves):
                m = modal_moves[mi]
                member_ids.append(m.get("move_id") or f"m{mi}")
                if not rep_actions and (title := m.get("move_title")):
                    rep_actions.append(title)
        theme = ""
        if cid < len(themes) and themes[cid]:
            theme = str(themes[cid])
        out["clusters"].append(
            {
                "cluster_id": cid,
                "theme": theme or f"Cluster {cid}",
                "member_move_ids": member_ids,
                "representative_actions": rep_actions,
            }
        )
    return out


def _menu_from_artifacts(
    candidates: list[dict] | None, judgments: list[dict] | None
) -> list[dict]:
    """Join Stage-4 candidates with Stage-5 judgments into the UI's `menu` shape.

    The UI consumes:
      `proposal_id`, `move_title`, `summary`, `which_convergence_pattern_it_breaks`,
      `actions` (optional), `intended_effect` (optional), `risks_red_accepts` (optional),
      `judge_ratings`, `would_have_generated`, `rationales`,
      `median_plausibility`, `would_have_generated_count`, `surviving`,
      `rejection_reason` (optional).

    We assume `candidates.json` is `list[dict]` of off-distribution proposals and
    `judgments.json` is `list[dict]` of `{proposal_id, judge_id, plausibility,
    would_have_generated, rationale}` rows, mirroring the SQLite schema.
    """
    if not candidates:
        return []

    by_proposal: dict[str, list[dict]] = {}
    for j in judgments or []:
        pid = j.get("proposal_id")
        if pid is None:
            continue
        by_proposal.setdefault(pid, []).append(j)

    out: list[dict] = []
    for c in candidates:
        pid = c.get("proposal_id") or c.get("id") or c.get("move_id") or ""
        rows = sorted(by_proposal.get(pid, []), key=lambda r: r.get("judge_id", ""))
        ratings = [int(r.get("plausibility") or 0) for r in rows]
        would = [bool(r.get("would_have_generated")) for r in rows]
        rationales = [str(r.get("rationale") or "") for r in rows]
        median = _median(ratings) if ratings else c.get("median_plausibility", 0)
        wgc = sum(1 for w in would if w)
        surviving = c.get("surviving")
        if surviving is None and ratings:
            surviving = (median >= 3) and (wgc < (len(ratings) + 1) // 2)
        rejection = c.get("rejection_reason")
        if rejection is None and surviving is False and ratings:
            if median < 3:
                rejection = f"PLAUS<3 (median {median:.1f})"
            elif wgc >= (len(ratings) + 1) // 2:
                rejection = f"WGEN≥{(len(ratings) + 1) // 2} ({wgc}/{len(ratings)} modal)"

        out.append(
            {
                "proposal_id": pid,
                "move_title": c.get("move_title", ""),
                "summary": c.get("summary", ""),
                "which_convergence_pattern_it_breaks": c.get(
                    "which_convergence_pattern_it_breaks", ""
                ),
                "actions": c.get("actions", []),
                "intended_effect": c.get("intended_effect", ""),
                "risks_red_accepts": c.get("risks_red_accepts", []),
                "judge_ratings": ratings,
                "would_have_generated": would,
                "rationales": rationales,
                "median_plausibility": median,
                "would_have_generated_count": wgc,
                "surviving": bool(surviving),
                "rejection_reason": rejection,
            }
        )
    return out


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0
