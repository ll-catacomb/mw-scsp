"""Scenario YAML loader for the demo UI.

Reads `scenarios/*.yaml` from the repo root and returns lightweight dicts
the Streamlit app uses to populate the scenario picker.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def list_scenarios() -> list[dict]:
    """Return one dict per `scenarios/*.yaml`, sorted by title.

    Each dict is the parsed YAML with a `_path` field added so the UI can
    show provenance.
    """
    scenarios_dir = _repo_root() / "scenarios"
    if not scenarios_dir.exists():
        return []

    scenarios: list[dict] = []
    for yaml_path in sorted(scenarios_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_path.read_text()) or {}
        except yaml.YAMLError as exc:
            data = {
                "scenario_id": yaml_path.stem,
                "title": yaml_path.stem,
                "_load_error": str(exc),
            }
        data["_path"] = str(yaml_path.relative_to(_repo_root()))
        scenarios.append(data)

    scenarios.sort(key=lambda d: d.get("title", d.get("scenario_id", "")))
    return scenarios
