"""Run manifest: every pipeline run writes data/runs/{run_id}/manifest.json.

A reviewer should be able to take a run_id and reconstruct exactly what the system did:
which scenario, which prompt-file versions, which model ids, which config knobs.
See PROJECT_SPEC.md §9.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.llm.wrapper import _git_blob_hash  # noqa: PLC2701  (intentional internal use)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def _runs_root() -> Path:
    raw = os.environ.get("RUN_ARTIFACTS_DIR", "data/runs")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p


def run_dir(run_id: str) -> Path:
    d = _runs_root() / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def prompt_versions() -> dict[str, str]:
    """Map every src/prompts/*.md file to its current git blob hash."""
    versions: dict[str, str] = {}
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        versions[path.name] = _git_blob_hash(path.read_bytes())
    return versions


def write_manifest(run_id: str, scenario: dict[str, Any], config: dict[str, Any]) -> Path:
    """Write the pipeline run's manifest to data/runs/{run_id}/manifest.json."""
    config_blob = json.dumps(config, sort_keys=True).encode("utf-8")
    manifest = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
        "config": config,
        "config_hash": hashlib.sha256(config_blob).hexdigest(),
        "prompt_versions": prompt_versions(),
    }
    out = run_dir(run_id) / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out
