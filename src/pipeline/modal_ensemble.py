"""Stage 2 — N=8 modal-ensemble calls, mixed Claude + GPT, doctrine-grounded.

See PROJECT_SPEC.md §3, §6. Doctrine retrieval (markdown corpus, two-pass keyword/topic
+ LLM-router fallback) runs ONCE per run; the same passages feed all 8 calls. The
temperature does the variance work; the prompt does the grounding work.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import uuid
from pathlib import Path

import yaml

from src.doctrine.retrieve import retrieve
from src.llm.wrapper import logged_completion
from src.memory.store import connect, init_db
from src.pipeline.schemas import ModalMoveSchema

# Path resolved from this file's location so the module works regardless of cwd.
_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "modal_red.md"
)
_PROMPT_PATH_STR = str(_PROMPT_PATH.relative_to(Path(__file__).resolve().parents[2]))

# Match the frontmatter delimiters used by every prompt file in src/prompts/.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

# Default top-k for doctrine retrieval feeding the modal stage. PROJECT_SPEC.md §5.
_DOCTRINE_TOP_K = 6


def _split_prompt(template_text: str) -> tuple[str, str]:
    """Strip frontmatter, split on `# System` / `# User` headings.

    Returns (system_text, user_template). The user template still contains
    `{{ scenario_block }}`, `{{ doctrine_block }}`, `{{ k }}`, and
    `{{ red_team_question }}` placeholders for str.replace() substitution.
    """
    body = _FRONTMATTER_RE.sub("", template_text, count=1)
    sys_match = re.search(r"^#\s+System\s*\n", body, re.MULTILINE)
    usr_match = re.search(r"^#\s+User\s*\n", body, re.MULTILINE)
    if sys_match is None or usr_match is None:
        raise ValueError(
            f"modal_red.md missing required '# System' or '# User' headings"
        )
    system_text = body[sys_match.end():usr_match.start()].strip()
    user_template = body[usr_match.end():].strip()
    return system_text, user_template


def _render_doctrine_block(hits: list[dict]) -> str:
    """Render retrieval hits as `## {id} — {source} {section} (p.{page})\\n\\n{body}` separated by `---`."""
    if not hits:
        return "(no doctrine passages retrieved)"
    chunks = []
    for h in hits:
        page = h.get("page")
        page_str = f" (p.{page})" if page not in (None, "") else ""
        chunks.append(
            f"## {h['id']} — {h['source']} {h['section']}{page_str}\n\n{h['body']}"
        )
    return "\n\n---\n\n".join(chunks)


def _render_scenario_block(scenario: dict) -> str:
    """Dump the scenario dict as readable YAML, omitting the red-team question (rendered separately)."""
    payload = {k: v for k, v in scenario.items() if k != "red_team_question"}
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False).strip()


def _pick_model(instance_idx: int) -> str:
    if instance_idx < 4:
        return os.environ.get("MODAL_CLAUDE_MODEL", "claude-sonnet-4-6")
    return os.environ.get("MODAL_GPT_MODEL", "gpt-5.5")


def _pick_temperature(run_id: str, instance_idx: int) -> float:
    """Reproducible per-(run, instance) temperature in [0.8, 1.0].

    GPT-5/5.5 are reasoning models and only accept the default temperature=1.0
    (HTTP 400: "Only the default (1) value is supported"). For instance_idx >= 4
    (GPT side) we pin to 1.0; the Claude side (0..3) keeps the spec's 0.8–1.0
    spread for cross-instance variance. Cross-family variance still comes from
    the two model families having different distributional centers.
    """
    if instance_idx >= 4:
        return 1.0
    rng = random.Random(f"{run_id}:{instance_idx}")
    return rng.uniform(0.8, 1.0)


def _provider_for(model: str) -> str:
    m = model.lower()
    if m.startswith("claude") or m.startswith("anthropic/"):
        return "anthropic"
    return "openai"


async def _one_modal_call(
    *,
    run_id: str,
    instance_idx: int,
    system_text: str,
    user_text: str,
) -> dict:
    """Single modal-ensemble instance. Returns a dict ready to persist + return."""
    model = _pick_model(instance_idx)
    temperature = _pick_temperature(run_id, instance_idx)
    result = await logged_completion(
        run_id=run_id,
        stage="modal_ensemble",
        agent_id=None,
        model=model,
        system=system_text,
        user=user_text,
        temperature=temperature,
        prompt_path=_PROMPT_PATH_STR,
        response_format=ModalMoveSchema,
    )
    parsed: ModalMoveSchema = result["parsed"]
    move_dict = parsed.model_dump()
    move_dict["move_id"] = str(uuid.uuid4())
    move_dict["instance_idx"] = instance_idx
    move_dict["provider"] = _provider_for(model)
    move_dict["model"] = model
    move_dict["temperature"] = temperature
    return move_dict


def _persist_moves(moves: list[dict], run_id: str) -> None:
    init_db()
    with connect() as conn:
        for m in moves:
            move_json = json.dumps(
                {
                    "move_title": m["move_title"],
                    "summary": m["summary"],
                    "actions": m["actions"],
                    "intended_effect": m["intended_effect"],
                    "risks_red_accepts": m["risks_red_accepts"],
                    "doctrine_cited": m["doctrine_cited"],
                },
                ensure_ascii=False,
            )
            conn.execute(
                """
                INSERT INTO modal_moves (
                  move_id, run_id, instance_idx, provider, model, temperature,
                  move_json, doctrine_cited, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    m["move_id"],
                    run_id,
                    m["instance_idx"],
                    m["provider"],
                    m["model"],
                    m["temperature"],
                    move_json,
                    json.dumps(m["doctrine_cited"]),
                ),
            )


async def generate_modal_moves(scenario: dict, run_id: str) -> list[dict]:
    """Run the 8-call modal ensemble for `scenario`, persist to SQLite, return parsed moves.

    - Single doctrine retrieval (`stage='modal-grounding'`, top_k=6) feeds all 8 calls.
    - Instances 0..3 use MODAL_CLAUDE_MODEL; 4..7 use MODAL_GPT_MODEL.
    - Temperature is reproducible from (run_id, instance_idx) in [0.8, 1.0].
    - All 8 calls dispatched concurrently; the wrapper's per-provider semaphores
      (ANTHROPIC_MAX_CONCURRENCY / OPENAI_MAX_CONCURRENCY) bound the actual fan-out.
    """
    template_text = _PROMPT_PATH.read_text(encoding="utf-8")
    system_text, user_template = _split_prompt(template_text)

    red_team_question = scenario.get("red_team_question", "").strip()
    if not red_team_question:
        raise ValueError("scenario is missing a non-empty `red_team_question`")
    scenario_block = _render_scenario_block(scenario)

    doctrine_hits = await retrieve(
        red_team_question,
        stage="modal-grounding",
        top_k=_DOCTRINE_TOP_K,
        run_id=run_id,
    )
    doctrine_block = _render_doctrine_block(doctrine_hits)

    user_text = (
        user_template
        .replace("{{ scenario_block }}", scenario_block)
        .replace("{{ doctrine_block }}", doctrine_block)
        .replace("{{ k }}", str(_DOCTRINE_TOP_K))
        .replace("{{ red_team_question }}", red_team_question)
    )

    moves = await asyncio.gather(
        *(
            _one_modal_call(
                run_id=run_id,
                instance_idx=i,
                system_text=system_text,
                user_text=user_text,
            )
            for i in range(8)
        )
    )

    _persist_moves(list(moves), run_id)
    return list(moves)
