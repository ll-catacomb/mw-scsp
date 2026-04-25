"""Pipeline orchestrator. Tier 1 ships through Stage 3 (clustering placeholder).

End-to-end: scenario YAML → modal ensemble (8 calls) → cluster_moves placeholder →
artifacts on disk + run row in SQLite. Tier 2 wires in the Cartographer narration,
the Off-Distribution Generator, and the Judge Pool.

CLI:
    uv run python -m src.pipeline.orchestrator scenarios/taiwan_strait_spring_2028.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from datetime import date as _date, datetime as _datetime

from src.llm.manifest import run_dir, write_manifest
from src.memory.store import connect, init_db
from src.pipeline.convergence import cartographer_narrate, cluster_moves
from src.pipeline.modal_ensemble import generate_modal_moves


def _json_safe(value):
    """Recursively convert YAML-loaded values into JSON-serializable form.

    PyYAML parses bare ISO dates (e.g. `start: 2028-04-01`) into `datetime.date`
    objects, which the manifest writer's `json.dumps` rejects. Convert dates and
    datetimes to ISO strings; leave everything else alone.
    """
    if isinstance(value, _datetime):
        return value.isoformat()
    if isinstance(value, _date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _load_scenario(scenario_path: str) -> dict:
    p = Path(scenario_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.exists():
        raise FileNotFoundError(f"scenario not found: {p}")
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"scenario YAML must be a mapping at top level: {p}")
    return _json_safe(data)


def _pipeline_config() -> dict:
    """Knobs that change run behaviour. Recorded in manifest.json + hashed into runs.config_hash."""
    return {
        "modal_claude_model": os.environ.get("MODAL_CLAUDE_MODEL", "claude-sonnet-4-6"),
        "modal_gpt_model": os.environ.get("MODAL_GPT_MODEL", "gpt-5.5"),
        "doctrine_top_k": 6,
        "modal_ensemble_n": 8,
        "tier": 1,
    }


def _config_hash(config: dict) -> str:
    import hashlib
    blob = json.dumps(config, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _insert_run(run_id: str, scenario_id: str, config: dict) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (run_id, scenario_id, started_at, config_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                scenario_id,
                datetime.now(timezone.utc).isoformat(),
                _config_hash(config),
                "running",
            ),
        )


def _mark_run_complete(run_id: str, status: str = "complete") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = ? WHERE run_id = ?",
            (status, datetime.now(timezone.utc).isoformat(), run_id),
        )


async def run_pipeline(scenario_path: str, run_id: str | None = None) -> str:
    """Run the Tier 1 pipeline end-to-end. Returns the run_id."""
    scenario = _load_scenario(scenario_path)
    scenario_id = scenario.get("scenario_id") or Path(scenario_path).stem
    if run_id is None:
        run_id = str(uuid.uuid4())

    config = _pipeline_config()
    _insert_run(run_id, scenario_id, config)

    try:
        write_manifest(run_id, scenario, config)

        modal_moves = await generate_modal_moves(scenario, run_id)
        clusters = cluster_moves(modal_moves)

        # Stage 3 — Cartographer narration. Drives notable_absences for Stage 4 and the
        # cross-run callout in the demo. Failures here don't kill the run; convergence.json
        # is written best-effort so the rest of the pipeline (and the UI's Tier-1 fallback)
        # still works if the Cartographer call has issues.
        narration: dict | None = None
        try:
            narration = await cartographer_narrate(modal_moves, scenario, run_id)
        except Exception as exc:  # noqa: BLE001 — pipeline-level non-fatal stage
            narration = {"_error": str(exc), "_stage": "3_convergence"}

        out_dir = run_dir(run_id)
        (out_dir / "modal_moves.json").write_text(
            json.dumps(modal_moves, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (out_dir / "clusters.json").write_text(
            json.dumps(clusters, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (out_dir / "convergence.json").write_text(
            json.dumps(narration, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        if narration and isinstance(narration, dict) and not narration.get("_error"):
            _write_convergence_md(out_dir, narration)

        _mark_run_complete(run_id, status="complete")
    except Exception:
        _mark_run_complete(run_id, status="failed")
        raise

    return run_id


def _write_convergence_md(out_dir: Path, narration: dict) -> None:
    """Render the Cartographer's narration as readable markdown for the UI's Section 3."""
    lines: list[str] = []
    if summary := narration.get("convergence_summary"):
        lines.append("# Convergence summary\n")
        lines.append(f"{summary}\n")
    clusters = narration.get("clusters") or []
    if clusters:
        lines.append("# Clusters\n")
        for c in clusters:
            cid = c.get("cluster_id", "?")
            theme = c.get("theme", "(no theme)")
            members = c.get("member_move_ids") or []
            actions = c.get("representative_actions") or []
            lines.append(f"## Cluster {cid} — {theme}\n")
            lines.append(f"Members: {members}\n")
            if actions:
                lines.append("Representative actions:\n")
                for a in actions:
                    lines.append(f"- {a}")
                lines.append("")
    absences = narration.get("notable_absences") or []
    if absences:
        lines.append("# Notable absences\n")
        for a in absences:
            lines.append(f"- **{a.get('absence', '')}**")
            if w := a.get("why_it_might_be_proposed"):
                lines.append(f"  - Why a planner might propose it: {w}")
            if w := a.get("why_the_ensemble_missed_it"):
                lines.append(f"  - Why the ensemble missed it: {w}")
        lines.append("")
    cross = narration.get("cross_run_observations") or []
    if cross:
        lines.append("# Cross-run observations\n")
        for o in cross:
            lines.append(f"- {o}")
        lines.append("")
    (out_dir / "convergence.md").write_text("\n".join(lines), encoding="utf-8")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="src.pipeline.orchestrator", description=__doc__)
    ap.add_argument("scenario_path", help="Path to a scenario YAML (e.g. scenarios/...).")
    ap.add_argument("--run-id", default=None, help="Optional run_id; default is a fresh uuid.")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # Load .env so MODAL_*_MODEL and ANTHROPIC_API_KEY / OPENAI_API_KEY are available
    # when the script is invoked directly. No-op if python-dotenv isn't installed or
    # the .env file is absent.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    args = _parse_args(argv)
    run_id = asyncio.run(run_pipeline(args.scenario_path, run_id=args.run_id))
    print(run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
