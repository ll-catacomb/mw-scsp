"""Streamlit demo UI — replays a pre-computed run with full audit trail.

See PROJECT_SPEC.md §13 (demo flow) and §15 (definition of done).
Tier 1: shell with mocked data shaped like the eventual schemas
(`src/ui/fixtures.py`). Tier 2 swaps the mocks for reads from
`data/runs/{run_id}/*.json` and `data/memory.db`.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

import plotly.express as px
import streamlit as st

from src.ui.fixtures import (
    MOCK_CONVERGENCE,
    MOCK_LLM_CALLS,
    MOCK_MANIFEST,
    MOCK_MENU,
    MOCK_MODAL_MOVES,
    MOCK_RUN_ID,
)
from src.ui.scenarios_loader import list_scenarios


# ──────────────────────────────────────────────────────────────────────
# Style
# ──────────────────────────────────────────────────────────────────────

CALLOUT_CSS = """
<style>
.cross-run-callout {
    border-left: 5px solid #b85c00;
    background: #fff6ec;
    padding: 1.1rem 1.3rem;
    margin: 0.5rem 0 1rem 0;
    border-radius: 4px;
}
.cross-run-callout .label {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
    color: #b85c00;
    font-weight: 600;
    margin-bottom: 0.4rem;
}
.cross-run-callout .body {
    font-size: 0.98rem;
    line-height: 1.5;
    color: #2d2316;
}
.modal-card {
    border: 1px solid #d8d8d8;
    border-radius: 6px;
    padding: 0.85rem 0.95rem;
    margin-bottom: 0.6rem;
    background: #fcfcfc;
    height: 100%;
}
.modal-card .meta {
    font-size: 0.75rem;
    color: #666;
    margin-bottom: 0.35rem;
}
.modal-card .title {
    font-weight: 600;
    font-size: 0.95rem;
    margin-bottom: 0.45rem;
}
.modal-card .summary {
    font-size: 0.85rem;
    line-height: 1.4;
    color: #333;
    margin-bottom: 0.55rem;
}
.chip {
    display: inline-block;
    padding: 0.12rem 0.5rem;
    margin: 0.1rem 0.2rem 0.1rem 0;
    background: #eef1f5;
    border-radius: 10px;
    font-size: 0.72rem;
    color: #34465f;
    font-family: ui-monospace, SFMono-Regular, monospace;
}
.absence-item {
    margin-bottom: 0.45rem;
    line-height: 1.45;
}
.dot {
    display: inline-block;
    width: 0.85rem;
    height: 0.85rem;
    border-radius: 50%;
    margin-right: 0.18rem;
    vertical-align: middle;
}
.dot.filled { background: #2e7d32; }
.dot.empty  { background: #d8d8d8; }
.dot.would  { background: #c97c1c; }
.judge-row {
    font-size: 0.85rem;
    color: #333;
    margin-bottom: 0.35rem;
    line-height: 1.4;
}
.disclaimer {
    color: #555;
    font-size: 0.92rem;
    font-style: italic;
}
</style>
"""


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{item}</span>' for item in items)


def _rating_dots(rating: int, max_rating: int = 5) -> str:
    filled = "".join('<span class="dot filled"></span>' for _ in range(rating))
    empty = "".join('<span class="dot empty"></span>' for _ in range(max_rating - rating))
    return filled + empty


def _runs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "runs"


def _list_run_ids() -> list[str]:
    runs = _runs_dir()
    if not runs.exists():
        return []
    return sorted([p.name for p in runs.iterdir() if p.is_dir()], reverse=True)


def _load_manifest_for(run_id: str) -> dict:
    """Load `data/runs/{run_id}/manifest.json` if present, else mock."""
    path = _runs_dir() / run_id / "manifest.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return MOCK_MANIFEST


# ──────────────────────────────────────────────────────────────────────
# Sections
# ──────────────────────────────────────────────────────────────────────


def render_header() -> None:
    st.title("Adversarial-Distribution Red Team")
    st.caption("SCSP Hackathon 2026 · Wargaming · Boston")
    st.markdown(
        '<p class="disclaimer">This is a menu of hypotheses, not a forecast.</p>',
        unsafe_allow_html=True,
    )
    st.divider()


def render_scenario_section() -> dict | None:
    with st.expander("1 — Scenario", expanded=True):
        scenarios = list_scenarios()
        if not scenarios:
            st.warning("No scenario YAMLs found under `scenarios/`.")
            return None

        labels = {s.get("title", s.get("scenario_id", s["_path"])): s for s in scenarios}
        choice = st.selectbox(
            "Selected scenario",
            list(labels.keys()),
            index=0,
            help="Switch the scenario the demo replays.",
        )
        scenario = labels[choice]

        st.markdown(f"**Scenario ID:** `{scenario.get('scenario_id', '—')}`")
        st.markdown(f"**Source:** `{scenario['_path']}`")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Red force:** {scenario.get('red_force', '—')}")
        with col2:
            st.markdown(f"**Blue force:** {scenario.get('blue_force', '—')}")

        timeframe = scenario.get("timeframe", {}) or {}
        if timeframe:
            horizon = timeframe.get("decision_horizon_days")
            start = timeframe.get("start")
            tf_bits = []
            if start:
                tf_bits.append(f"start `{start}`")
            if horizon is not None:
                tf_bits.append(f"decision horizon **{horizon} days**")
            if tf_bits:
                st.markdown("**Timeframe:** " + ", ".join(tf_bits))

        if situation := scenario.get("situation"):
            st.markdown("**Situation**")
            st.markdown(situation)

        goals = scenario.get("red_strategic_goals") or []
        if goals:
            st.markdown("**Red strategic goals**")
            for g in goals:
                st.markdown(f"- {g}")

        if rtq := scenario.get("red_team_question"):
            st.markdown("**Red-team question**")
            st.markdown(f"> {rtq}")

        return scenario


def render_modal_ensemble_section() -> None:
    with st.expander("2 — Modal ensemble (N=8)", expanded=True):
        st.caption(
            "Eight independent calls across two model families. The point of "
            "this view: coherent, plausible, clustered. This is what an "
            "averaged AI red team produces — and the failure mode the rest "
            "of the system is built to address."
        )

        # 4-wide, 2-deep
        for row_start in (0, 4):
            cols = st.columns(4, gap="small")
            for offset, col in enumerate(cols):
                move = MOCK_MODAL_MOVES[row_start + offset]
                with col:
                    st.markdown(
                        f"""
<div class="modal-card">
  <div class="meta">
    instance {move['instance_idx']} · <code>{move['provider']}</code> ·
    <code>{move['model']}</code> · temp {move['temperature']:.2f}
  </div>
  <div class="title">{move['move_title']}</div>
  <div class="summary">{move['summary']}</div>
  <div>{_chips(move['doctrine_cited'])}</div>
</div>
""",
                        unsafe_allow_html=True,
                    )


def render_convergence_section() -> None:
    with st.expander("3 — Convergence and notable absences", expanded=True):
        # Cluster scatter — synthetic 2D points from fixtures (Tier 1 mock).
        cluster_labels = MOCK_CONVERGENCE["cluster_labels"]
        rows = []
        for m in MOCK_MODAL_MOVES:
            x, y = m["xy"]
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "cluster": cluster_labels[m["cluster"]],
                    "move": m["move_title"],
                    "provider": m["provider"],
                }
            )

        fig = px.scatter(
            rows,
            x="x",
            y="y",
            color="cluster",
            symbol="provider",
            hover_data={"move": True, "provider": True, "x": False, "y": False, "cluster": False},
            labels={"cluster": "Cluster"},
            height=380,
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=1, color="#333")))
        fig.update_layout(
            xaxis=dict(showgrid=False, zeroline=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, visible=False),
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig, width="stretch")

        st.markdown("**Convergence summary**")
        st.markdown(MOCK_CONVERGENCE["convergence_summary"])

        st.markdown("**Notable absences**")
        for absence in MOCK_CONVERGENCE["notable_absences"]:
            st.markdown(f'<div class="absence-item">— {absence}</div>', unsafe_allow_html=True)

        # Visually distinct callout — this is "the moment" per §13.2.
        st.markdown(
            f"""
<div class="cross-run-callout">
  <div class="label">Cross-run observation · Convergence Cartographer memory</div>
  <div class="body">{MOCK_CONVERGENCE['cross_run_observations']}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def render_menu_section() -> None:
    with st.expander("4 — Menu of surviving off-distribution candidates", expanded=True):
        st.caption(
            "Survival rule: median plausibility ≥ 3 and fewer than half of "
            "judges said they would have generated the move themselves. "
            "These are the candidates the modal didn't reach."
        )

        rerun_col, _ = st.columns([1, 4])
        with rerun_col:
            st.button(
                "Live re-run · off-distribution stage",
                disabled=True,
                help=(
                    "Wired up in Tier 2. Will re-run the off-distribution "
                    "generator against the current scenario and append the "
                    "result below without touching prior judgments."
                ),
            )

        for proposal in MOCK_MENU:
            judges = list(
                zip(proposal["judge_ratings"], proposal["would_have_generated"], proposal["rationales"])
            )
            med = median(proposal["judge_ratings"])
            wgc = proposal["would_have_generated_count"]
            header = (
                f"**{proposal['move_title']}** · median plausibility "
                f"{med:.1f} · {wgc}/5 judges said they would have generated it"
            )
            with st.expander(header, expanded=False):
                st.markdown(proposal["summary"])

                st.markdown("**Which convergence pattern it breaks**")
                st.markdown(f"> {proposal['which_convergence_pattern_it_breaks']}")

                st.markdown("**Judge ratings**")
                for idx, (rating, would_gen, rationale) in enumerate(judges, start=1):
                    would_marker = "would-have-generated" if would_gen else "novel-to-judge"
                    st.markdown(
                        f"""
<div class="judge-row">
  <strong>Judge {idx}</strong>
  &nbsp;{_rating_dots(rating)}
  &nbsp;<span class="chip">{would_marker}</span><br/>
  <em>{rationale}</em>
</div>
""",
                        unsafe_allow_html=True,
                    )


def render_audit_section() -> None:
    with st.expander("5 — Audit", expanded=False):
        run_ids = _list_run_ids()
        if run_ids:
            run_id = st.selectbox("Run", run_ids, index=0)
        else:
            st.info(
                f"No runs on disk under `data/runs/`. Showing the mock manifest "
                f"(`{MOCK_RUN_ID}`). Tier 2 will populate this from real runs."
            )
            run_id = MOCK_RUN_ID

        manifest = _load_manifest_for(run_id)

        col1, col2, col3, col4 = st.columns(4)
        totals = manifest.get("totals", {})
        col1.metric("LLM calls", totals.get("llm_calls", "—"))
        col2.metric("Input tokens", f"{totals.get('input_tokens', 0):,}")
        col3.metric("Output tokens", f"{totals.get('output_tokens', 0):,}")
        cost = totals.get("cost_usd", 0)
        col4.metric("Cost", f"${cost:.2f}" if isinstance(cost, (int, float)) else "—")

        st.markdown("**Manifest**")
        st.json(manifest, expanded=False)

        st.markdown("**Prompt versions** (git blob hash at call time)")
        prompt_versions = manifest.get("prompt_versions", {})
        for fname, version in sorted(prompt_versions.items()):
            st.markdown(f"- `{fname}` → `{version}`")

        st.markdown("**LLM call log**")
        query = st.text_input(
            "Search calls",
            placeholder="filter by stage, provider, agent_id, call_id, prompt_version…",
            label_visibility="collapsed",
        )
        rows = MOCK_LLM_CALLS
        if query:
            q = query.lower()
            rows = [
                r
                for r in rows
                if any(
                    q in str(v).lower()
                    for v in (
                        r.get("stage"),
                        r.get("provider"),
                        r.get("model"),
                        r.get("agent_id") or "",
                        r.get("call_id"),
                        r.get("prompt_version"),
                    )
                )
            ]
        st.dataframe(rows, width="stretch", hide_index=True)


# ──────────────────────────────────────────────────────────────────────
# App entry
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    st.set_page_config(page_title="Adversarial-Distribution Red Team", layout="wide")
    st.markdown(CALLOUT_CSS, unsafe_allow_html=True)

    render_header()
    render_scenario_section()
    render_modal_ensemble_section()
    render_convergence_section()
    render_menu_section()
    render_audit_section()


if __name__ == "__main__":
    main()
