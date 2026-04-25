"""Streamlit demo UI — replays a real pipeline run with full audit trail.

Canonical demo per PROJECT_SPEC.md §13. The five collapsed sections mirror
§13.2's per-section timing. Tier-2 wiring: every section reads from
`data/runs/{run_id}/` + `data/memory.db` via `src/ui/run_loader.py`. Mock
fixtures only fire when an artifact is missing (Stage 4/5 pre-Tier-2).

The alternative menu-first instrument-panel design lives in
`src/ui/streamlit_proto.py` — kept for reference, not the demo.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import plotly.express as px
import streamlit as st

from src.ui.run_loader import list_runs, load_run
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
    margin-bottom: 0.4rem;
}
.cross-run-callout .body:last-child { margin-bottom: 0; }
.cross-run-callout.empty {
    border-left-color: #999;
    background: #f3f3f3;
}
.cross-run-callout.empty .label { color: #555; }
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
.cluster-card {
    border: 1px solid #d8d8d8;
    border-radius: 6px;
    padding: 0.7rem 0.95rem;
    margin-bottom: 0.55rem;
    background: #fafafa;
}
.cluster-card .header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.35rem;
}
.cluster-card .theme {
    font-weight: 600;
    font-size: 0.94rem;
    color: #222;
}
.cluster-card .count {
    font-size: 0.78rem;
    color: #666;
    font-family: ui-monospace, SFMono-Regular, monospace;
}
.cluster-card .reps {
    font-size: 0.84rem;
    color: #444;
    line-height: 1.4;
}
.absence-item {
    margin-bottom: 0.6rem;
    padding-left: 0.8rem;
    border-left: 3px solid #d8d8d8;
    line-height: 1.45;
}
.absence-item .body { font-size: 0.92rem; color: #222; margin-bottom: 0.25rem; }
.absence-item .gloss {
    font-size: 0.8rem; color: #666; line-height: 1.4;
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
.judge-row {
    font-size: 0.85rem;
    color: #333;
    margin-bottom: 0.45rem;
    line-height: 1.4;
}
.disclaimer {
    color: #555;
    font-size: 0.92rem;
    font-style: italic;
}
.action-row {
    font-size: 0.84rem;
    color: #333;
    line-height: 1.45;
    margin-bottom: 0.45rem;
    padding-left: 0.6rem;
    border-left: 2px solid #c9d6e5;
}
.action-row .actor { color: #34465f; font-weight: 600; }
.action-row .meta-line {
    font-size: 0.74rem; color: #666;
    font-family: ui-monospace, SFMono-Regular, monospace;
}
.run-header-bar {
    background: #f7f7f7;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    padding: 0.5rem 0.85rem;
    margin-bottom: 0.7rem;
    font-size: 0.86rem;
    color: #333;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.6rem;
}
.run-header-bar code { font-size: 0.8rem; }
.no-runs {
    color: #555;
    background: #fff8e6;
    border-left: 4px solid #b85c00;
    padding: 0.7rem 0.95rem;
    border-radius: 4px;
    font-size: 0.92rem;
    margin-bottom: 1rem;
}
</style>
"""


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{item}</span>' for item in items)


def _rating_dots(rating: int, max_rating: int = 5) -> str:
    filled = "".join('<span class="dot filled"></span>' for _ in range(max(0, min(rating, max_rating))))
    empty = "".join('<span class="dot empty"></span>' for _ in range(max(0, max_rating - rating)))
    return filled + empty


def _scenario_yaml_path(scenario_id: str) -> str | None:
    """Resolve a scenarios/*.yaml path matching `scenario_id`, if any."""
    for s in list_scenarios():
        if s.get("scenario_id") == scenario_id:
            return s.get("_path")
    return None


# ──────────────────────────────────────────────────────────────────────
# Sidebar — run picker
# ──────────────────────────────────────────────────────────────────────


def render_run_picker() -> tuple[str | None, dict | None]:
    """Sidebar dropdown of runs. Returns (run_id, run_data) or (None, None)."""
    st.sidebar.markdown("### Run")
    runs = list_runs()
    if not runs:
        st.sidebar.markdown(
            '<div class="no-runs">No runs found in <code>data/runs/</code>. '
            "Generate one with <code>uv run python -m src.pipeline.orchestrator "
            "scenarios/taiwan_strait_spring_2028.yaml</code>.</div>",
            unsafe_allow_html=True,
        )
        return None, None

    default_idx = next(
        (i for i, r in enumerate(runs) if r.get("status") == "complete"), 0
    )
    labels = [r["label"] for r in runs]
    choice = st.sidebar.selectbox("Select a run", labels, index=default_idx, label_visibility="collapsed")
    run = runs[labels.index(choice)]
    run_id = run["run_id"]

    st.sidebar.markdown(f"**Run ID** `{run_id}`")
    st.sidebar.markdown(f"**Scenario** `{run.get('scenario_id', '—')}`")
    st.sidebar.markdown(f"**Status** `{run.get('status', '—')}`")
    started = run.get("started_at") or "—"
    st.sidebar.markdown(f"**Started** `{started[:19]}`")
    st.sidebar.markdown(f"**Cost** `${run.get('total_cost', 0.0):.4f}`")
    st.sidebar.markdown(f"**Calls** `{run.get('call_count', 0)}`")
    st.sidebar.divider()

    data = load_run(run_id)
    if not data["is_real"]:
        st.sidebar.warning("Manifest not found; rendering with mock fallback.")
    return run_id, data


# ──────────────────────────────────────────────────────────────────────
# Sections
# ──────────────────────────────────────────────────────────────────────


def render_header(run: dict | None) -> None:
    st.title("Adversarial-Distribution Red Team")
    st.caption("SCSP Hackathon 2026 · Wargaming · Boston")
    st.markdown(
        '<p class="disclaimer">This is a menu of hypotheses, not a forecast.</p>',
        unsafe_allow_html=True,
    )
    if run:
        manifest = run["manifest"]
        scen = run["scenario"]
        scen_id = scen.get("scenario_id") or manifest.get("scenario_id") or "—"
        totals = manifest.get("totals", {})
        bits = [
            f"<span><strong>Scenario:</strong> <code>{scen_id}</code></span>",
            f"<span><strong>Run:</strong> <code>{run['run_id'][:8]}…</code></span>",
            f"<span><strong>Status:</strong> {manifest.get('status', '—')}</span>",
            f"<span><strong>Calls:</strong> {totals.get('llm_calls', '—')}</span>",
            f"<span><strong>Cost:</strong> ${totals.get('cost_usd', 0):.4f}</span>",
        ]
        st.markdown(
            f'<div class="run-header-bar">{"".join(bits)}</div>',
            unsafe_allow_html=True,
        )
    st.divider()


def render_scenario_section(run: dict | None) -> dict | None:
    """Section 1 — Scenario. Defaults to the run's scenario; the user can override."""
    with st.expander("1 — Scenario", expanded=True):
        scenarios = list_scenarios()
        if not scenarios:
            st.warning("No scenario YAMLs found under `scenarios/`.")
            return None

        labels = {s.get("title", s.get("scenario_id", s["_path"])): s for s in scenarios}
        run_scen_id = (run or {}).get("scenario", {}).get("scenario_id") if run else None
        default_idx = 0
        if run_scen_id:
            for i, (_, s) in enumerate(labels.items()):
                if s.get("scenario_id") == run_scen_id:
                    default_idx = i
                    break

        choice = st.selectbox(
            "Selected scenario",
            list(labels.keys()),
            index=default_idx,
            help="Defaults to the scenario the loaded run was executed against.",
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


def render_modal_ensemble_section(run: dict | None) -> None:
    moves = (run or {}).get("modal_moves") or []
    with st.expander(f"2 — Modal ensemble (N={len(moves)})", expanded=True):
        st.caption(
            "Independent calls across two model families. The point of "
            "this view: coherent, plausible, clustered. This is what an "
            "averaged AI red team produces — and the failure mode the rest "
            "of the system is built to address."
        )

        if not moves:
            st.info("No modal moves on disk for this run.")
            return

        for row_start in range(0, len(moves), 4):
            row = moves[row_start : row_start + 4]
            cols = st.columns(len(row), gap="small")
            for offset, (col, move) in enumerate(zip(cols, row)):
                idx = row_start + offset
                with col:
                    doctrine = move.get("doctrine_cited") or []
                    st.markdown(
                        f"""
<div class="modal-card">
  <div class="meta">
    instance {move.get('instance_idx', idx)} ·
    <code>{move.get('provider', '?')}</code> ·
    <code>{move.get('model', '?')}</code> ·
    temp {float(move.get('temperature', 0.0)):.2f}
  </div>
  <div class="title">{move.get('move_title', '(untitled)')}</div>
  <div class="summary">{move.get('summary', '')}</div>
  <div>{_chips(doctrine)}</div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    with st.expander("Show full move", expanded=False):
                        if intended := move.get("intended_effect"):
                            st.markdown("**Intended effect**")
                            st.markdown(intended)
                        actions = move.get("actions") or []
                        if actions:
                            st.markdown("**Actions**")
                            for a in actions:
                                st.markdown(
                                    f"""
<div class="action-row">
  <span class="actor">{a.get('actor', '?')}</span> — {a.get('action', '')}<br/>
  <span class="meta-line">target: {a.get('target', '—')} · day {a.get('timeline_days', '?')}</span><br/>
  <em>{a.get('purpose', '')}</em>
</div>
""",
                                    unsafe_allow_html=True,
                                )
                        risks = move.get("risks_red_accepts") or []
                        if risks:
                            st.markdown("**Risks Red accepts**")
                            for r in risks:
                                st.markdown(f"- {r}")
                        if move_id := move.get("move_id"):
                            st.caption(f"move_id: `{move_id}`")


def render_convergence_section(run: dict | None) -> None:
    convergence = (run or {}).get("convergence") or {}
    convergence_md = (run or {}).get("convergence_md")
    clusters = convergence.get("clusters") or []
    absences = convergence.get("notable_absences") or []
    cross_run = convergence.get("cross_run_observations") or []

    with st.expander("3 — Convergence and notable absences", expanded=True):
        # Cluster size bar (works for any cluster shape).
        if clusters:
            cluster_rows = [
                {
                    "theme": c.get("theme") or f"Cluster {c.get('cluster_id', '?')}",
                    "members": len(c.get("member_move_ids") or []),
                }
                for c in clusters
            ]
            fig = px.bar(
                cluster_rows,
                x="members",
                y="theme",
                orientation="h",
                text="members",
                height=max(180, 60 + 50 * len(cluster_rows)),
                color="theme",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                xaxis=dict(title="Modal moves in cluster", showgrid=True, gridcolor="#eee", zeroline=False),
                yaxis=dict(title=""),
                margin=dict(l=10, r=20, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")

            for c in clusters:
                theme = c.get("theme") or f"Cluster {c.get('cluster_id', '?')}"
                members = c.get("member_move_ids") or []
                reps = c.get("representative_actions") or []
                st.markdown(
                    f"""
<div class="cluster-card">
  <div class="header">
    <span class="theme">{theme}</span>
    <span class="count">{len(members)} move{'s' if len(members) != 1 else ''}</span>
  </div>
  <div class="reps">{'; '.join(reps) if reps else '—'}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

        if summary := convergence.get("convergence_summary"):
            st.markdown("**Convergence summary**")
            st.markdown(summary)
        elif convergence_md:
            st.markdown(convergence_md)

        if absences:
            st.markdown("**Notable absences**")
            for a in absences:
                if isinstance(a, str):
                    st.markdown(
                        f'<div class="absence-item"><div class="body">{a}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    body = a.get("absence", "")
                    why_proposed = a.get("why_it_might_be_proposed", "")
                    why_missed = a.get("why_the_ensemble_missed_it", "")
                    gloss_bits = []
                    if why_proposed:
                        gloss_bits.append(f"<strong>Why it might be proposed:</strong> {why_proposed}")
                    if why_missed:
                        gloss_bits.append(f"<strong>Why the ensemble missed it:</strong> {why_missed}")
                    gloss_html = "<br/>".join(gloss_bits) if gloss_bits else ""
                    st.markdown(
                        f"""
<div class="absence-item">
  <div class="body">{body}</div>
  {f'<div class="gloss">{gloss_html}</div>' if gloss_html else ''}
</div>
""",
                        unsafe_allow_html=True,
                    )

        # Cross-run callout — the §13.2 "moment". Render distinctly even when empty.
        if cross_run:
            body_html = "".join(f'<div class="body">{obs}</div>' for obs in cross_run)
            st.markdown(
                f"""
<div class="cross-run-callout">
  <div class="label">Cross-run observation · Convergence Cartographer memory</div>
  {body_html}
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
<div class="cross-run-callout empty">
  <div class="label">Cross-run observation · Convergence Cartographer memory</div>
  <div class="body">No cross-run patterns yet — this populates after the same scenario family runs multiple times and the Cartographer's reflection memory accumulates.</div>
</div>
""",
                unsafe_allow_html=True,
            )


def _render_proposal_card(proposal: dict, idx: int, expanded: bool = False) -> None:
    ratings = proposal.get("judge_ratings") or []
    would = proposal.get("would_have_generated") or []
    rationales = proposal.get("rationales") or []
    med = float(proposal.get("median_plausibility") or (median(ratings) if ratings else 0.0))
    wgc = int(proposal.get("would_have_generated_count") or sum(1 for w in would if w))
    n_judges = len(ratings) or 5
    surviving = bool(proposal.get("surviving"))
    surv_marker = "✓ surviving" if surviving else "✗ rejected"
    rejection = proposal.get("rejection_reason") or ""

    title = proposal.get("move_title", "(untitled)")
    header = (
        f"**{title}** · median plaus {med:.1f} · {wgc}/{n_judges} would-have-generated"
        f" · {surv_marker}"
    )
    if rejection and not surviving:
        header += f" · _{rejection}_"

    with st.expander(header, expanded=expanded):
        st.markdown(proposal.get("summary", ""))

        if pattern := proposal.get("which_convergence_pattern_it_breaks"):
            st.markdown("**Which convergence pattern it breaks**")
            st.markdown(f"> {pattern}")

        if intended := proposal.get("intended_effect"):
            st.markdown("**Intended effect**")
            st.markdown(intended)

        actions = proposal.get("actions") or []
        if actions:
            st.markdown("**Actions**")
            for a in actions:
                st.markdown(
                    f"""
<div class="action-row">
  <span class="actor">{a.get('actor', '?')}</span> — {a.get('action', '')}<br/>
  <span class="meta-line">target: {a.get('target', '—')} · day {a.get('timeline_days', '?')}</span><br/>
  <em>{a.get('purpose', '')}</em>
</div>
""",
                    unsafe_allow_html=True,
                )

        risks = proposal.get("risks_red_accepts") or []
        if risks:
            st.markdown("**Risks Red accepts**")
            for r in risks:
                st.markdown(f"- {r}")

        if ratings:
            st.markdown("**Judge ratings**")
            for ji in range(len(ratings)):
                rating = ratings[ji]
                wg = would[ji] if ji < len(would) else False
                rationale = rationales[ji] if ji < len(rationales) else ""
                marker = "would-have-generated" if wg else "novel-to-judge"
                st.markdown(
                    f"""
<div class="judge-row">
  <strong>Judge {ji + 1}</strong>
  &nbsp;{_rating_dots(int(rating))}
  &nbsp;<span class="chip">{marker}</span><br/>
  <em>{rationale}</em>
</div>
""",
                    unsafe_allow_html=True,
                )

        if pid := proposal.get("proposal_id"):
            st.caption(f"proposal_id: `{pid}`")


def render_menu_section(run: dict | None) -> None:
    menu = (run or {}).get("menu") or []
    surviving = [p for p in menu if p.get("surviving")]
    rejected = [p for p in menu if not p.get("surviving")]

    with st.expander(f"4 — Menu ({len(surviving)} surviving / {len(menu)} candidates)", expanded=True):
        st.caption(
            "Survival rule: median plausibility ≥ 3 and fewer than half of "
            "judges said they would have generated the move themselves. "
            "These are the candidates the modal didn't reach."
        )

        _render_rerun_button(run)

        if not surviving and not rejected:
            st.info(
                "No off-distribution candidates on disk yet — Stage 4 / 5 land in Tier-2 "
                "from the pipeline worktree. Use the live re-run button above to generate."
            )

        if surviving:
            st.markdown("#### Surviving candidates")
            for idx, p in enumerate(surviving, start=1):
                _render_proposal_card(p, idx, expanded=False)

        if rejected:
            show_rejected = st.toggle(
                f"Show {len(rejected)} non-surviving candidate{'s' if len(rejected) != 1 else ''}",
                value=False,
            )
            if show_rejected:
                for idx, p in enumerate(rejected, start=1):
                    _render_proposal_card(p, idx, expanded=False)


def _render_rerun_button(run: dict | None) -> None:
    """Live "re-run off-distribution stage" button — Stage 4 only.

    Uses the loaded run's Stage-3 convergence summary as input, calls
    `src.pipeline.adversarial.generate_off_distribution`, and stores the
    resulting proposals in `st.session_state` so they survive reruns.
    """
    rerun_col, status_col = st.columns([1, 4])
    with rerun_col:
        clicked = st.button(
            "Re-run off-distribution stage",
            disabled=run is None,
            help=(
                "Re-runs Stage 4 (off-distribution generator) against the loaded "
                "run's Stage-3 convergence summary and the scenario's red-team "
                "question. Costs roughly $0.30, takes ~20 seconds. Stages 1–3 "
                "and 5 are not re-run."
            ),
        )

    if clicked and run is not None:
        with status_col:
            with st.spinner("Calling the Off-Distribution Generator…"):
                try:
                    proposals = _do_rerun(run)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Re-run failed: {exc}")
                    return
        st.session_state["rerun_proposals"] = proposals
        st.session_state["rerun_at"] = time.time()

    proposals = st.session_state.get("rerun_proposals")
    if proposals:
        ts = st.session_state.get("rerun_at", 0)
        st.markdown(
            f"#### Live re-run output · {len(proposals)} proposals · "
            f"{time.strftime('%H:%M:%S', time.localtime(ts))}"
        )
        for idx, p in enumerate(proposals, start=1):
            _render_proposal_card(p, idx, expanded=False)


def _do_rerun(run: dict) -> list[dict]:
    """Wrapper: imports adversarial.py lazily so the UI loads even if Stage 4 isn't merged yet."""
    try:
        from src.pipeline.adversarial import generate_off_distribution  # type: ignore[attr-defined]
    except ImportError as exc:
        raise RuntimeError(
            "Stage 4 not available yet — `src.pipeline.adversarial.generate_off_distribution` "
            "is shipping in feature/pipeline. Re-merge Tier 2 before using this button."
        ) from exc

    base_run_id = run["run_id"]
    rerun_run_id = f"{base_run_id}_rerun_{int(time.time())}"
    proposals = asyncio.run(
        generate_off_distribution(
            convergence_summary=run.get("convergence") or {},
            scenario=run.get("scenario") or {},
            run_id=rerun_run_id,
        )
    )
    if not isinstance(proposals, list):
        raise RuntimeError(
            f"generate_off_distribution returned {type(proposals).__name__}, expected list."
        )
    return proposals


def render_audit_section(run: dict | None) -> None:
    with st.expander("5 — Audit", expanded=False):
        if run is None:
            st.info("No run loaded.")
            return

        manifest = run["manifest"]
        calls = run["llm_calls"] or []

        totals = manifest.get("totals", {})
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("LLM calls", totals.get("llm_calls", "—"))
        col2.metric("Input tokens", f"{totals.get('input_tokens', 0):,}")
        col3.metric("Output tokens", f"{totals.get('output_tokens', 0):,}")
        cost = totals.get("cost_usd", 0)
        col4.metric("Cost", f"${cost:.4f}" if isinstance(cost, (int, float)) else "—")

        st.markdown("**Manifest**")
        st.json(manifest, expanded=False)

        st.markdown("**Prompt versions** (git blob hash at call time)")
        for fname, version in sorted((manifest.get("prompt_versions") or {}).items()):
            st.markdown(f"- `{fname}` → `{version}`")

        st.markdown("**LLM call log**")
        if not calls:
            st.info("No `llm_calls` rows for this run in `data/memory.db`.")
            return

        stage_counts = Counter(c.get("stage") for c in calls)
        stage_options = ["(all)"] + sorted(stage_counts.keys())
        selected_stage = st.selectbox(
            "Filter by stage",
            stage_options,
            index=0,
            format_func=lambda s: s if s == "(all)" else f"{s} · {stage_counts.get(s, 0)} calls",
        )
        query = st.text_input(
            "Search calls",
            placeholder="filter by provider, model, agent_id, call_id, prompt_version…",
            label_visibility="collapsed",
        )

        rows = calls
        if selected_stage != "(all)":
            rows = [r for r in rows if r.get("stage") == selected_stage]
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

        st.caption(f"Showing {len(rows)} of {len(calls)} calls.")

        # Compact dataframe view first, then per-call expanders below.
        summary_view = [
            {
                "stage": r.get("stage"),
                "agent": r.get("agent_id") or "—",
                "provider": r.get("provider"),
                "model": r.get("model"),
                "temp": r.get("temperature"),
                "in_tok": r.get("input_tokens"),
                "out_tok": r.get("output_tokens"),
                "lat_ms": r.get("latency_ms"),
                "cost_usd": r.get("cost_usd"),
                "prompt_version": (r.get("prompt_version") or "")[:10],
                "call_id": (r.get("call_id") or "")[:12],
            }
            for r in rows
        ]
        st.dataframe(summary_view, width="stretch", hide_index=True)

        st.caption("Click a call below to inspect the full system + user prompt and the raw response.")
        for r in rows:
            label = (
                f"`{(r.get('call_id') or '')[:12]}…` · {r.get('stage')} · "
                f"{r.get('provider')}/{r.get('model')} · "
                f"{r.get('input_tokens') or 0}→{r.get('output_tokens') or 0} tok · "
                f"${(r.get('cost_usd') or 0):.4f}"
            )
            with st.expander(label, expanded=False):
                meta_cols = st.columns(3)
                meta_cols[0].markdown(f"**call_id:** `{r.get('call_id')}`")
                meta_cols[1].markdown(f"**prompt_version:** `{r.get('prompt_version')}`")
                meta_cols[2].markdown(f"**prompt_hash:** `{r.get('prompt_hash')}`")
                if r.get("system_prompt"):
                    st.markdown("**System prompt**")
                    st.code(r.get("system_prompt") or "", language="markdown")
                st.markdown("**User prompt**")
                st.code(r.get("user_prompt") or "", language="markdown")
                st.markdown("**Raw response**")
                st.code(r.get("raw_response") or "", language="markdown")
                if parsed := r.get("parsed_output"):
                    st.markdown("**Parsed output**")
                    try:
                        st.json(json.loads(parsed))
                    except (json.JSONDecodeError, TypeError):
                        st.code(parsed, language="markdown")


# ──────────────────────────────────────────────────────────────────────
# App entry
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    st.set_page_config(page_title="Adversarial-Distribution Red Team", layout="wide")
    st.markdown(CALLOUT_CSS, unsafe_allow_html=True)

    run_id, run = render_run_picker()

    render_header(run)
    render_scenario_section(run)
    render_modal_ensemble_section(run)
    render_convergence_section(run)
    render_menu_section(run)
    render_audit_section(run)


if __name__ == "__main__":
    main()
