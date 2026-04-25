"""Pipeline orchestrator. Tier 2 chains Stages 2 → 3 → 4 → 5.

End-to-end: scenario YAML → modal ensemble (8 calls) → Cartographer narration →
off-distribution proposals (K) → judge pool (5×K×2 calls) → menu of survivors,
plus full audit trail in SQLite.

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
from datetime import date as _date
from datetime import datetime as _datetime
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from src.llm.manifest import run_dir, write_manifest
from src.memory.store import MemoryStore, connect, init_db
from src.pipeline.adversarial import generate_off_distribution
from src.pipeline.convergence import cartographer_narrate
from src.pipeline.judging import compute_survival, judge_proposals
from src.pipeline.modal_ensemble import generate_modal_moves

# BGE-v1.5 asymmetric query prefix (RA-7 §4). Applied to queries only — never to docs.
MEMORY_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _embedding_model_id() -> str:
    return os.environ.get("MEMORY_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")


@lru_cache(maxsize=1)
def _load_sentence_transformer():
    """Lazy load — import + model load are expensive and we don't want them at import time."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(_embedding_model_id())


def default_embedder() -> Callable[..., np.ndarray]:
    """Build the BGE embedder callable expected by GenerativeAgent.

    Signature: `embed(text, *, is_query: bool) -> np.ndarray`. The query prefix
    is applied only when `is_query=True`; documents are encoded raw (asymmetric
    encoding — adding the prefix to docs degrades recall, RA-7 §"BGE prefix at ingest").
    """

    def _embed(text: str, *, is_query: bool) -> np.ndarray:
        model = _load_sentence_transformer()
        payload = (MEMORY_QUERY_PREFIX + text) if is_query else text
        vec = model.encode(payload, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32)

    return _embed


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
        "heavy_claude_model": os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7"),
        "judge_claude_model": os.environ.get("JUDGE_CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        "judge_gpt_model": os.environ.get("JUDGE_GPT_MODEL", "gpt-5"),
        "embedding_model": _embedding_model_id(),
        "doctrine_top_k": 6,
        "modal_ensemble_n": 8,
        "off_dist_k": int(os.environ.get("OFF_DIST_K", "10")),
        "tier": 2,
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


def _format_convergence_md(narration: dict[str, Any]) -> str:
    """Render the Cartographer narration as a readable markdown document."""
    summary = narration.get("convergence_summary", "").strip()
    parts: list[str] = []
    if summary:
        parts.append("## Convergence summary\n\n" + summary)

    absences = narration.get("notable_absences") or []
    if absences:
        bullets: list[str] = []
        for a in absences:
            line = f"- **{a.get('absence', '?')}**"
            why_p = a.get("why_it_might_be_proposed", "").strip()
            why_m = a.get("why_the_ensemble_missed_it", "").strip()
            if why_p:
                line += f"\n  - *Why a planner might propose:* {why_p}"
            if why_m:
                line += f"\n  - *Why the ensemble missed it:* {why_m}"
            bullets.append(line)
        parts.append("## Notable absences\n\n" + "\n".join(bullets))

    cross = narration.get("cross_run_observations") or []
    if cross:
        parts.append(
            "## Cross-run observations\n\n" + "\n".join(f"- {c}" for c in cross)
        )
    return "\n\n".join(parts) + "\n"


def build_menu(
    proposals: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Assemble the survival menu. Returns (markdown, json-shaped-dict-for-ui)."""
    # Group judgments by proposal_id.
    by_proposal: dict[str, list[dict[str, Any]]] = {p["proposal_id"]: [] for p in proposals}
    for j in judgments:
        by_proposal.setdefault(j["proposal_id"], []).append(j)

    surviving_entries: list[dict[str, Any]] = []
    rejected_entries: list[dict[str, Any]] = []
    for p in proposals:
        plist = by_proposal.get(p["proposal_id"], [])
        med, wgc, surviving = compute_survival(plist)
        entry = {
            "proposal": p,
            "judgments": plist,
            "median_plausibility": med,
            "would_have_gen_count": wgc,
            "n_judges": len(plist),
            "surviving": surviving,
        }
        (surviving_entries if surviving else rejected_entries).append(entry)

    md_parts: list[str] = ["# Survival menu\n"]
    md_parts.append(
        f"**{len(surviving_entries)} surviving** of {len(proposals)} proposals "
        f"(median plausibility ≥ 3 AND fewer than half of judges said "
        f"\"I would have generated this\").\n"
    )

    if surviving_entries:
        md_parts.append("## Surviving proposals\n")
        for e in surviving_entries:
            md_parts.append(_format_menu_entry(e))
    else:
        md_parts.append("*(no proposals survived the filter)*\n")

    if rejected_entries:
        md_parts.append("\n## Rejected (audit trail preserved)\n")
        for e in rejected_entries:
            md_parts.append(_format_menu_entry(e, terse=True))

    menu_md = "\n".join(md_parts)
    menu_dict = {
        "n_proposals": len(proposals),
        "n_surviving": len(surviving_entries),
        "surviving": surviving_entries,
        "rejected": rejected_entries,
    }
    return menu_md, menu_dict


def _format_menu_entry(entry: dict[str, Any], *, terse: bool = False) -> str:
    p = entry["proposal"]
    plist = entry["judgments"]
    head = (
        f"### {p.get('move_title', '(untitled)')}\n\n"
        f"_proposal_id: `{p['proposal_id']}`_  "
        f"_median plausibility: {entry['median_plausibility']:.1f}_  "
        f"_would-have-generated: {entry['would_have_gen_count']}/{entry['n_judges']}_\n\n"
        f"{p.get('summary', '')}\n"
    )
    if terse:
        return head

    sections: list[str] = [head]

    pattern = p.get("which_convergence_pattern_it_breaks", "").strip()
    if pattern:
        sections.append(f"**Convergence pattern broken:** {pattern}\n")

    justification = p.get("why_a_red_planner_could_justify_this", "").strip()
    if justification:
        sections.append(f"**Red planner's justification:** {justification}\n")

    actions = p.get("actions") or []
    if actions:
        action_lines = ["#### Actions"]
        for a in actions:
            if isinstance(a, dict):
                action_lines.append(
                    f"- **{a.get('actor', '?')}** — {a.get('action', '')} "
                    f"(target: {a.get('target', '?')}, day {a.get('timeline_days', '?')})"
                )
            else:
                action_lines.append(f"- {a}")
        sections.append("\n".join(action_lines) + "\n")

    risks = p.get("risks_red_accepts") or []
    if risks:
        sections.append("#### Risks Red accepts\n" + "\n".join(f"- {r}" for r in risks) + "\n")

    if plist:
        judge_lines = ["#### Judgments"]
        for j in plist:
            judge_lines.append(
                f"- **{j['judge_id']}** ({j.get('judge_family', '?')}): "
                f"plausibility={j['plausibility']}, "
                f"would_have_gen={'YES' if j['would_have_generated'] else 'NO'}"
            )
            if j.get("rationale"):
                judge_lines.append(f"  - *plausibility rationale:* {j['rationale']}")
            if j.get("would_have_generated_rationale"):
                judge_lines.append(
                    f"  - *would-have-gen rationale:* {j['would_have_generated_rationale']}"
                )
        sections.append("\n".join(judge_lines) + "\n")

    return "\n".join(sections)


async def run_pipeline(scenario_path: str, run_id: str | None = None) -> str:
    """Run the Tier 2 pipeline end-to-end through Stage 5. Returns the run_id."""
    scenario = _load_scenario(scenario_path)
    scenario_id = scenario.get("scenario_id") or Path(scenario_path).stem
    if run_id is None:
        run_id = str(uuid.uuid4())

    config = _pipeline_config()
    _insert_run(run_id, scenario_id, config)

    try:
        write_manifest(run_id, scenario, config)

        # Build embedder + store ONCE so all stages share state and the SentenceTransformer
        # model isn't re-loaded per stage.
        embed = default_embedder()
        store = MemoryStore()

        # Stage 2 — modal ensemble (8 cross-family calls).
        modal_moves = await generate_modal_moves(scenario, run_id)

        # Stage 3 — Cartographer narration.
        narration = await cartographer_narrate(
            modal_moves, scenario, run_id, embedder=embed, store=store
        )

        # Stage 4 — off-distribution proposals.
        proposals = await generate_off_distribution(
            narration, scenario, run_id, embedder=embed, store=store
        )

        # Stage 5 — judge pool.
        judgments = await judge_proposals(
            proposals, scenario, run_id, embedder=embed, store=store
        )

        menu_md, menu_dict = build_menu(proposals, judgments)

        out_dir = run_dir(run_id)
        (out_dir / "modal_moves.json").write_text(
            json.dumps(modal_moves, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "convergence.md").write_text(
            _format_convergence_md(narration), encoding="utf-8"
        )
        (out_dir / "clusters.json").write_text(
            json.dumps(narration, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "candidates.json").write_text(
            json.dumps(proposals, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "judgments.json").write_text(
            json.dumps(judgments, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "menu.md").write_text(menu_md, encoding="utf-8")
        (out_dir / "menu.json").write_text(
            json.dumps(menu_dict, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        _mark_run_complete(run_id, status="complete")
    except Exception:
        _mark_run_complete(run_id, status="failed")
        raise

    return run_id


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
