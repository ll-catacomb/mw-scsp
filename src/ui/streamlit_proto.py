"""Throwaway proto — menu-first, U.S.-Graphics-CMX-7500-style instrument panel.

Iterating on the look. The committed Tier 1 shell (streamlit_app.py) is
untouched. When the aesthetic is locked in, fold the chosen pieces back
into streamlit_app.py.
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

PROTO_CSS = """
<style>
:root {
    --bg: #07090a;
    --panel: #0d1112;
    --panel-edge: #2a3032;
    --ink: #e8ece6;
    --ink-dim: #8b9088;
    --ink-faint: #555a55;
    --accent: #d6c25a;        /* dim amber for highlights */
    --accent-hot: #f0a020;    /* hotter amber for the cross-run moment */
    --warn: #c84e2a;
    --good: #6ec07a;
    --rule: #1c2123;
    --mono: "JetBrains Mono", "Berkeley Mono", "SF Mono", Menlo, Consolas, monospace;
}

html, body, [class*="css"], [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main, .block-container {
    background: var(--bg) !important;
    color: var(--ink) !important;
    font-family: var(--mono) !important;
}

.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1280px !important;
}

/* Default text bigger — readability is the priority */
html, body, p, li, span, div {
    font-size: 17px;
    line-height: 1.6;
}

/* Streamlit chrome */
header[data-testid="stHeader"] { display: none; }
[data-testid="stToolbar"] { display: none; }
footer { display: none; }

/* The bordered panel idiom */
.panel {
    border: 1px solid var(--panel-edge);
    background: var(--panel);
    margin-bottom: 1.1rem;
    position: relative;
}
.panel-head {
    border-bottom: 1px solid var(--panel-edge);
    padding: 0.45rem 0.9rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(0deg, transparent, rgba(214, 194, 90, 0.04));
}
.panel-head .label {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.92rem;
    color: var(--accent);
}
.panel-head .meta {
    font-size: 0.86rem;
    color: var(--ink-dim);
    letter-spacing: 0.08em;
}
.panel-body {
    padding: 0.9rem 1.05rem;
}

/* Header strip — the "system identifier" of the rig */
.id-strip {
    border: 1px solid var(--panel-edge);
    background: #000;
    padding: 0.55rem 0.95rem;
    margin-bottom: 0.6rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.id-strip .id {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: var(--accent);
    font-size: 0.96rem;
}
.id-strip .id .sub {
    color: var(--ink-dim);
    margin-left: 0.6rem;
    letter-spacing: 0.12em;
    font-size: 0.86rem;
}
.id-strip .badge {
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 0.1rem 0.6rem;
    font-size: 0.84rem;
    letter-spacing: 0.18em;
}

/* Status row — the SCEN/RUN/HORIZON line under the id strip */
.status-row {
    display: flex;
    gap: 1.6rem;
    border: 1px solid var(--panel-edge);
    border-top: none;
    padding: 0.5rem 0.95rem;
    background: var(--panel);
    margin-bottom: 1.4rem;
    flex-wrap: wrap;
}
.status-cell {
    font-size: 0.9rem;
    color: var(--ink-dim);
    letter-spacing: 0.06em;
}
.status-cell strong {
    color: var(--ink);
    margin-left: 0.4rem;
    letter-spacing: 0.08em;
}

/* Dot leader: monospace fill with periods */
.leader {
    display: flex;
    font-size: 0.85rem;
    color: var(--ink);
    margin: 0.15rem 0;
}
.leader .l-key { color: var(--ink-dim); }
.leader .l-fill {
    flex: 1;
    border-bottom: 1px dotted var(--ink-faint);
    margin: 0 0.4rem;
    transform: translateY(-0.32rem);
}
.leader .l-val {
    color: var(--ink);
    text-align: right;
    white-space: nowrap;
}

/* Bar — unicode block fill */
.bar {
    font-family: var(--mono);
    letter-spacing: 0.05em;
}
.bar .filled { color: var(--accent); }
.bar .empty  { color: var(--ink-faint); }

/* Menu candidate row */
.candidate {
    border-top: 1px solid var(--rule);
    padding: 0.85rem 0;
}
.candidate:first-child { border-top: none; padding-top: 0.2rem; }
.candidate .idx {
    color: var(--accent);
    margin-right: 0.6rem;
    letter-spacing: 0.1em;
}
.candidate .title {
    color: var(--ink);
    font-size: 1.18rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.candidate .breaks {
    color: var(--ink-dim);
    font-style: italic;
    font-size: 1.0rem;
    margin: 0.55rem 0;
    padding-left: 0.55rem;
    border-left: 2px solid var(--accent);
}
.candidate .summary {
    font-size: 1.02rem;
    color: var(--ink);
    margin-top: 0.55rem;
}
.candidate .stat-row {
    display: flex;
    gap: 1.6rem;
    margin-top: 0.6rem;
    flex-wrap: wrap;
    font-size: 0.95rem;
}
.candidate .stat-row .stat {
    color: var(--ink-dim);
}
.candidate .stat-row .stat .v {
    color: var(--ink);
    margin-left: 0.35rem;
}

/* Chip */
.chip {
    display: inline-block;
    padding: 0.1rem 0.55rem;
    margin: 0.12rem 0.3rem 0.12rem 0;
    background: transparent;
    border: 1px solid var(--panel-edge);
    border-radius: 0;
    font-size: 0.84rem;
    color: var(--ink-dim);
    font-family: var(--mono);
    letter-spacing: 0.06em;
}

/* Cross-run callout — the §13.2 "moment" */
.callout {
    border: 1px solid var(--accent-hot);
    background: linear-gradient(90deg, rgba(240,160,32,0.08), transparent 70%);
    padding: 1rem 1.15rem;
    margin: 0.5rem 0 0 0;
}
.callout .label {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.74rem;
    color: var(--accent-hot);
    margin-bottom: 0.5rem;
}
.callout .body {
    font-size: 1.05rem;
    color: var(--ink);
    line-height: 1.55;
}
.callout .triangles {
    color: var(--accent-hot);
    margin-right: 0.45rem;
}

/* Modal ensemble subsystem table */
.subsys-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.96rem;
}
.subsys-table th {
    text-align: left;
    color: var(--ink-dim);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: normal;
    font-size: 0.84rem;
    padding: 0.5rem 0.6rem;
    border-bottom: 1px solid var(--panel-edge);
}
.subsys-table td {
    padding: 0.55rem 0.6rem;
    border-bottom: 1px solid var(--rule);
    vertical-align: top;
}
.subsys-table td.t { color: var(--good); letter-spacing: 0.08em; }
.subsys-table td.cluster-cell { color: var(--accent); }
.subsys-table .move-cell {
    color: var(--ink);
    font-size: 0.96rem;
}
.subsys-table .doctrine-cell {
    font-size: 0.82rem;
    color: var(--ink-dim);
}

/* Section heading inside panels */
.subhead {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem;
    color: var(--ink-dim);
    margin: 0.95rem 0 0.4rem 0;
}

/* Briefing — front matter */
.briefing-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.4rem;
}
.briefing-col h4 {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.84rem;
    color: var(--accent);
    margin: 0 0 0.55rem 0;
    font-weight: normal;
}
.briefing-col .lede {
    font-size: 1.0rem;
    color: var(--ink);
    margin-bottom: 0.7rem;
    line-height: 1.55;
}
.briefing-col .term {
    font-size: 0.95rem;
    margin-bottom: 0.55rem;
    line-height: 1.5;
}
.briefing-col .term .k {
    color: var(--accent);
    letter-spacing: 0.06em;
    margin-right: 0.45rem;
}
.briefing-col .term .v { color: var(--ink); }
.briefing-col .src {
    font-size: 0.92rem;
    color: var(--ink-dim);
    margin-bottom: 0.45rem;
    line-height: 1.5;
}
.briefing-col .src a { color: var(--accent); text-decoration: none; }
.briefing-col .src a:hover { text-decoration: underline; }
.briefing-col .src .tag {
    color: var(--ink-faint);
    margin-right: 0.45rem;
    letter-spacing: 0.08em;
}
.briefing-limits {
    margin-top: 0.95rem;
    padding-top: 0.85rem;
    border-top: 1px dashed var(--rule);
    font-size: 0.92rem;
    color: var(--ink-dim);
    line-height: 1.55;
}
.briefing-limits strong { color: var(--warn); letter-spacing: 0.1em; }

/* Collapsible panel — the whole panel header is the click target */
details.panel {
    padding: 0;
}
details.panel > summary {
    list-style: none;
    cursor: pointer;
    border-bottom: 1px solid transparent;
    padding: 0.55rem 0.95rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(0deg, transparent, rgba(214, 194, 90, 0.04));
}
details.panel > summary::-webkit-details-marker { display: none; }
details.panel > summary::marker { content: ""; }
details.panel[open] > summary {
    border-bottom: 1px solid var(--panel-edge);
}
details.panel > summary .label {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.92rem;
    color: var(--accent);
}
details.panel > summary .label::before {
    content: "▸";
    margin-right: 0.55rem;
    color: var(--accent);
    display: inline-block;
    transition: transform 0.15s ease;
}
details.panel[open] > summary .label::before {
    transform: rotate(90deg);
}
details.panel > summary .meta {
    font-size: 0.86rem;
    color: var(--ink-dim);
    letter-spacing: 0.08em;
}
details.panel > summary:hover .label,
details.panel > summary:hover .label::before {
    color: var(--accent-hot);
}
details.panel > .panel-body {
    padding: 0.9rem 1.05rem;
}

/* Native <details> accordion inside the briefing panel */
.briefing-col details {
    margin-top: 1.0rem;
    border-top: 1px dashed var(--rule);
    padding-top: 0.85rem;
}
.briefing-col details > summary {
    list-style: none;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.84rem;
    color: var(--accent);
    user-select: none;
    padding: 0.1rem 0;
}
.briefing-col details > summary::-webkit-details-marker { display: none; }
.briefing-col details > summary::marker { content: ""; }
.briefing-col details > summary::before {
    content: "▸";
    margin-right: 0.55rem;
    color: var(--accent);
    display: inline-block;
    transition: transform 0.15s ease;
}
.briefing-col details[open] > summary::before {
    transform: rotate(90deg);
}
.briefing-col details > summary:hover { color: var(--accent-hot); }
.briefing-col details > summary:hover::before { color: var(--accent-hot); }
.briefing-col details > .details-body {
    margin-top: 0.7rem;
}

/* Funnel — atop the menu, single line */
.funnel {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: nowrap;
    overflow-x: auto;
    white-space: nowrap;
    font-size: 0.92rem;
    margin-bottom: 1.0rem;
    padding-bottom: 0.85rem;
    border-bottom: 1px dashed var(--rule);
}
.funnel .stage {
    border: 1px solid var(--panel-edge);
    padding: 0.3rem 0.6rem;
    color: var(--ink-dim);
    letter-spacing: 0.05em;
    flex-shrink: 0;
}
.funnel .stage .n {
    color: var(--ink);
    font-size: 1.1rem;
    margin-right: 0.35rem;
}
.funnel .stage.alive {
    border-color: var(--good);
}
.funnel .stage.alive .n { color: var(--good); }
.funnel .stage.dead {
    border-color: var(--warn);
    color: var(--ink-dim);
}
.funnel .stage.dead .n { color: var(--warn); }
.funnel .arrow {
    color: var(--ink-faint);
    letter-spacing: 0.2em;
}

/* Rejected-candidate row */
.dead-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-top: 1px solid var(--rule);
    padding: 0.55rem 0;
    font-size: 0.92rem;
}
.dead-row:first-child { border-top: none; }
.dead-row .title {
    color: var(--ink-dim);
    text-decoration: line-through;
    text-decoration-color: var(--ink-faint);
}
.dead-row .reason {
    color: var(--warn);
    letter-spacing: 0.06em;
    font-size: 0.84rem;
    white-space: nowrap;
    margin-left: 1.0rem;
}

/* Streamlit overrides */
.stMarkdown, .stMarkdown p { color: var(--ink); }
.stExpander {
    border: 1px solid var(--panel-edge) !important;
    background: var(--panel) !important;
    border-radius: 0 !important;
}
[data-testid="stExpander"] details summary {
    color: var(--accent) !important;
    font-family: var(--mono) !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.78rem;
}
[data-testid="stMetricLabel"] {
    color: var(--ink-dim) !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.7rem !important;
}
[data-testid="stMetricValue"] {
    color: var(--accent) !important;
    font-family: var(--mono) !important;
}
[data-baseweb="select"] > div {
    background: var(--panel) !important;
    border: 1px solid var(--panel-edge) !important;
    border-radius: 0 !important;
    color: var(--ink) !important;
    font-family: var(--mono) !important;
}
.stTextInput input, .stSelectbox div[role="combobox"] {
    background: var(--panel) !important;
    color: var(--ink) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
}
.stButton button {
    background: transparent !important;
    border: 1px solid var(--panel-edge) !important;
    color: var(--ink-dim) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.78rem !important;
}
.stButton button:hover:enabled {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
hr { border-color: var(--rule) !important; }
code, pre { color: var(--accent) !important; background: transparent !important; }
a { color: var(--accent) !important; }
</style>
"""

BLOCK_FILLED = "█"
BLOCK_EMPTY = "░"


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def bar(value: int, maximum: int, width: int = 5) -> str:
    """Unicode block-filled bar, with markup for color."""
    filled_n = round((value / maximum) * width)
    empty_n = width - filled_n
    return (
        f'<span class="bar">'
        f'<span class="filled">{BLOCK_FILLED * filled_n}</span>'
        f'<span class="empty">{BLOCK_EMPTY * empty_n}</span>'
        f"</span>"
    )


def chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{i}</span>' for i in items)


def panel_open(label: str, meta: str = "") -> None:
    st.markdown(
        f"""
<div class="panel">
  <div class="panel-head">
    <span class="label">{label}</span>
    <span class="meta">{meta}</span>
  </div>
  <div class="panel-body">
""",
        unsafe_allow_html=True,
    )


def panel_close() -> None:
    st.markdown("</div></div>", unsafe_allow_html=True)


def panel_collapsible_open(label: str, meta: str = "", open_: bool = False) -> None:
    """Bordered panel whose header is the click target. Body collapsed by default."""
    open_attr = " open" if open_ else ""
    st.markdown(
        f"""
<details class="panel"{open_attr}>
  <summary>
    <span class="label">{label}</span>
    <span class="meta">{meta}</span>
  </summary>
  <div class="panel-body">
""",
        unsafe_allow_html=True,
    )


def panel_collapsible_close() -> None:
    st.markdown("</div></details>", unsafe_allow_html=True)


def _runs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "runs"


def _list_run_ids() -> list[str]:
    runs = _runs_dir()
    if not runs.exists():
        return []
    return sorted([p.name for p in runs.iterdir() if p.is_dir()], reverse=True)


def _load_manifest(run_id: str) -> dict:
    path = _runs_dir() / run_id / "manifest.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return MOCK_MANIFEST


# ──────────────────────────────────────────────────────────────────────
# Header strip + status row
# ──────────────────────────────────────────────────────────────────────


def render_header(scenario: dict | None, manifest: dict) -> None:
    st.markdown(
        """
<div class="id-strip">
  <span class="id">
    ADRT-001 · ADVERSARIAL DISTRIBUTION RED TEAM
    <span class="sub">TEAM REISSWITZ · SCSP HACKATHON 2026 · WARGAMING · BOSTON</span>
  </span>
  <span class="badge">REPLAY · ARMED</span>
</div>
""",
        unsafe_allow_html=True,
    )

    scen_id = (scenario or {}).get("scenario_id", "—")
    horizon = (scenario or {}).get("timeframe", {}).get("decision_horizon_days", "—")
    totals = manifest.get("totals", {})
    cells = [
        ("SCEN", scen_id),
        ("RUN", manifest.get("run_id", "—")[:46] + "…"),
        ("HORIZON", f"{horizon}D"),
        ("MODE", "REPLAY · MOCK"),
        ("CALLS", str(totals.get("llm_calls", "—"))),
        ("COST", f"${totals.get('cost_usd', 0):.2f}"),
    ]
    cells_html = "".join(
        f'<span class="status-cell">{k}<strong>{v}</strong></span>' for k, v in cells
    )
    st.markdown(f'<div class="status-row">{cells_html}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# Briefing — how to read this readout, and the method behind it
# ──────────────────────────────────────────────────────────────────────


def render_briefing() -> None:
    panel_open("BRIEFING · METHOD · SOURCES", "READ BEFORE INTERPRETING THE MENU")

    st.markdown(
        """
<div class="briefing-grid">
  <div class="briefing-col">
    <h4>HOW TO READ THIS READOUT</h4>
    <div class="lede">
      Each candidate below is a Red move the modal LLM ensemble did <em>not</em>
      converge on, that survived a separate panel of judges. The system's job is
      to surface candidates the human red team has not considered — not to predict
      what an adversary will do.
    </div>
    <div class="term"><span class="k">PLAUS</span><span class="v">
      Median plausibility (1–5) across five mixed-provider judges. Survival
      threshold ≥ 3.0.</span></div>
    <div class="term"><span class="k">WGEN</span><span class="v">
      Number of judges who said "I would have generated this myself." Survival
      threshold &lt; 3 of 5 — the lower the score, the further off the modal.</span></div>
    <div class="term"><span class="k">BREAKS</span><span class="v">
      Which convergence pattern this candidate explicitly violates. Read it as
      the candidate's reason-to-exist.</span></div>
    <div class="term"><span class="k">CROSS-RUN</span><span class="v">
      A reflection drawn from the Convergence Cartographer's persistent memory
      of prior runs. Patterns stable across scenarios are flagged as
      ensemble-wide tendencies rather than scenario-specific.</span></div>
  </div>
  <div class="briefing-col">
    <h4>METHOD, IN FIVE LINES</h4>
    <div class="term"><span class="k">▸</span><span class="v">
      Cross-family ensemble of N=8 (Claude + GPT). Convergence between
      different model families is more meaningful than within one.</span></div>
    <div class="term"><span class="k">▸</span><span class="v">
      The off-distribution generator is told not to retrieve doctrine —
      its job is to escape the comfortable cluster, not stay in it.</span></div>
    <div class="term"><span class="k">▸</span><span class="v">
      Persistent generative-agent memory (Park et al., UIST '23) lets the
      Cartographer accumulate convergence patterns across runs.</span></div>
    <div class="term"><span class="k">▸</span><span class="v">
      Survival = median plausibility ≥ 3 <em>and</em> fewer than half of judges
      would have generated it themselves. Both filters together.</span></div>
    <div class="term"><span class="k">▸</span><span class="v">
      Every LLM call logged with prompt git blob hash. A run_id reconstructs
      the system's reasoning end to end.</span></div>
    <details>
      <summary>FURTHER READING &nbsp;·&nbsp; LIMITS</summary>
      <div class="details-body">
        <div class="src"><span class="tag">[GEN-AGT]</span>
          Park, O'Brien, Cai, Morris, Liang, Bernstein.
          <em>Generative Agents: Interactive Simulacra of Human Behavior.</em>
          UIST '23. <a href="https://arxiv.org/abs/2304.03442"
          target="_blank">arXiv:2304.03442</a></div>
        <div class="src"><span class="tag">[DOCTRINE]</span>
          Joint Publication 3-0 (Joint Operations) and 5-0 (Joint Planning).
          <a href="https://www.jcs.mil/Doctrine/" target="_blank">jcs.mil/Doctrine</a></div>
        <div class="src"><span class="tag">[PLA]</span>
          CSIS open-access analysis on PLA Taiwan operational concepts.
          <a href="https://www.csis.org/topics/defense-and-security"
          target="_blank">csis.org</a></div>
        <div class="src"><span class="tag">[KRIEGSSPIEL]</span>
          Reisswitz père et fils, Berlin, 1812 / 1824 — the original Prussian
          Kriegsspiel. The genre's first commitment to wargames as
          hypothesis-generation devices for the General Staff, not as
          prediction.</div>
        <div class="briefing-limits">
          <strong>LIMITS.</strong>
          A wargame is a hypothesis generator, not a predictor. This system
          narrows what an averaged AI red team produces; it does not replace
          human red-team judgment, and it does not produce forecasts. External
          validity is not claimed. Documented, reproducible, auditable — and
          bounded.
        </div>
      </div>
    </details>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    panel_close()


# ──────────────────────────────────────────────────────────────────────
# Menu — front and center
# ──────────────────────────────────────────────────────────────────────


def render_menu(menu: list[dict]) -> None:
    surviving = [p for p in menu if p["surviving"]]
    rejected = [p for p in menu if not p["surviving"]]
    panel_open(
        "MENU · OFF-DISTRIBUTION CANDIDATES",
        f"{len(surviving):02d} SURVIVING  ·  THRESH PLAUS≥3.0 ∧ WGEN<3/5",
    )

    # Funnel header — show the sift literally
    st.markdown(
        f"""
<div class="funnel">
  <span class="stage"><span class="n">08</span>MODAL</span>
  <span class="arrow">›››</span>
  <span class="stage"><span class="n">{len(menu):02d}</span>OFF-DIST</span>
  <span class="arrow">›››</span>
  <span class="stage"><span class="n">{len(menu) * 5:03d}</span>JUDGMENTS · 5×{len(menu)}</span>
  <span class="arrow">›››</span>
  <span class="stage alive"><span class="n">{len(surviving):02d}</span>SURVIVED</span>
  <span class="stage dead"><span class="n">{len(rejected):02d}</span>REJECTED</span>
</div>
""",
        unsafe_allow_html=True,
    )

    rerun_col, _ = st.columns([1, 5])
    with rerun_col:
        st.button(
            "▶ LIVE RE-RUN · OFF-DIST STAGE",
            disabled=True,
            help=(
                "Wired up in Tier 2. Will re-run the off-distribution generator "
                "against the current scenario and append the result without "
                "touching prior judgments."
            ),
        )

    for idx, prop in enumerate(surviving, start=1):
        med = median(prop["judge_ratings"])
        wgc = prop["would_have_generated_count"]
        st.markdown(
            f"""
<div class="candidate">
  <div>
    <span class="idx">{idx:02d}</span>
    <span class="title">{prop['move_title']}</span>
  </div>
  <div class="stat-row">
    <span class="stat">PLAUS {bar(int(med), 5)} <span class="v">{med:.1f}/5</span></span>
    <span class="stat">WGEN  {bar(wgc, 5)} <span class="v">{wgc}/5</span></span>
    <span class="stat">SURV <span class="v">▲▲▲ OK</span></span>
  </div>
  <div class="breaks">BREAKS · {prop['which_convergence_pattern_it_breaks']}</div>
  <div class="summary">{prop['summary']}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.expander(f"AUDIT TRAIL · CANDIDATE {idx:02d}", expanded=False):
            st.markdown('<div class="subhead">JUDGE RATINGS</div>', unsafe_allow_html=True)
            for ji, (rating, would_gen, rationale) in enumerate(
                zip(prop["judge_ratings"], prop["would_have_generated"], prop["rationales"]),
                start=1,
            ):
                marker = "WOULD-GEN" if would_gen else "NOVEL"
                st.markdown(
                    f"""
<div style="margin-bottom:0.55rem;">
  <span class="leader">
    <span class="l-key">JUDGE {ji:02d}</span>
    <span class="l-fill"></span>
    <span class="l-val">PLAUS {bar(rating, 5)} {rating}/5 · {marker}</span>
  </span>
  <div style="font-size:0.85rem; color:var(--ink); padding-left:0.4rem; margin-top:0.2rem;">
    <em>{rationale}</em>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

    panel_close()


# ──────────────────────────────────────────────────────────────────────
# Judgment matrix — every candidate plotted, survivors and rejects
# ──────────────────────────────────────────────────────────────────────


def render_judgment_matrix(menu: list[dict]) -> None:
    panel_open(
        "JUDGMENT MATRIX · ALL CANDIDATES",
        f"X PLAUSIBILITY  ·  Y NOVELTY (5 − WGEN)  ·  N={len(menu)}",
    )

    rows = []
    for idx, p in enumerate(menu, start=1):
        rows.append(
            {
                "id": f"{idx:02d}",
                "title": p["move_title"],
                "median_plaus": float(p["median_plausibility"]),
                "novelty": 5 - p["would_have_generated_count"],
                "status": "SURVIVED" if p["surviving"] else "REJECTED",
                "reason": p.get("rejection_reason", "—"),
            }
        )

    fig = px.scatter(
        rows,
        x="median_plaus",
        y="novelty",
        color="status",
        text="id",
        color_discrete_map={"SURVIVED": "#6ec07a", "REJECTED": "#c84e2a"},
        hover_data={
            "title": True,
            "median_plaus": ":.1f",
            "novelty": True,
            "status": True,
            "reason": True,
            "id": False,
        },
        height=440,
    )
    fig.update_traces(
        marker=dict(size=22, line=dict(width=1.2, color="#0d1112")),
        textfont=dict(family="JetBrains Mono, SF Mono, Menlo, monospace", color="#0d1112", size=11),
        textposition="middle center",
    )
    # Survival threshold lines: PLAUS ≥ 3 and WGEN < 3 ⇒ novelty ≥ 3 (since
    # novelty = 5 − WGEN, WGEN < 3 means novelty > 2, i.e. novelty ≥ 3 for ints).
    fig.add_vline(x=2.5, line_color="#d6c25a", line_dash="dot", line_width=1)
    fig.add_hline(y=2.5, line_color="#d6c25a", line_dash="dot", line_width=1)
    fig.add_annotation(
        x=4.7, y=4.7, text="SURVIVED →", showarrow=False,
        font=dict(color="#6ec07a", size=11, family="JetBrains Mono, SF Mono, Menlo, monospace"),
    )
    fig.add_annotation(
        x=4.7, y=0.3, text="TOO MODAL", showarrow=False,
        font=dict(color="#c84e2a", size=11, family="JetBrains Mono, SF Mono, Menlo, monospace"),
    )
    fig.add_annotation(
        x=1.3, y=4.7, text="TOO IMPLAUSIBLE", showarrow=False,
        font=dict(color="#c84e2a", size=11, family="JetBrains Mono, SF Mono, Menlo, monospace"),
    )
    fig.add_annotation(
        x=1.3, y=0.3, text="REJECTED · BOTH", showarrow=False,
        font=dict(color="#c84e2a", size=11, family="JetBrains Mono, SF Mono, Menlo, monospace"),
    )
    fig.update_layout(
        paper_bgcolor="#0d1112",
        plot_bgcolor="#0d1112",
        font=dict(family="JetBrains Mono, SF Mono, Menlo, monospace", color="#8b9088", size=12),
        xaxis=dict(
            title="MEDIAN PLAUSIBILITY (1–5)",
            range=[0.5, 5.5],
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            gridcolor="#1c2123",
            zeroline=False,
        ),
        yaxis=dict(
            title="NOVELTY  (5 − judges who would have generated it)",
            range=[-0.5, 5.5],
            tickmode="array",
            tickvals=[0, 1, 2, 3, 4, 5],
            gridcolor="#1c2123",
            zeroline=False,
        ),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
    )
    st.plotly_chart(fig, width="stretch")

    # Rejected candidates list
    rejected = [p for p in menu if not p["surviving"]]
    if rejected:
        st.markdown('<div class="subhead">REJECTED CANDIDATES</div>', unsafe_allow_html=True)
        for idx, p in enumerate(menu, start=1):
            if p["surviving"]:
                continue
            st.markdown(
                f"""
<div class="dead-row">
  <span><span class="idx" style="color:var(--accent); margin-right:0.55rem;">{idx:02d}</span>
        <span class="title">{p['move_title']}</span></span>
  <span class="reason">{p.get('rejection_reason', '—')}</span>
</div>
""",
                unsafe_allow_html=True,
            )

    panel_close()


# ──────────────────────────────────────────────────────────────────────
# Convergence — map + absences side by side, callout below
# ──────────────────────────────────────────────────────────────────────


def render_convergence() -> None:
    col_left, col_right = st.columns([3, 2], gap="medium")

    with col_left:
        panel_open("CONVERGENCE MAP", "8 CALLS · 3 CLUSTERS")
        rows = []
        for m in MOCK_MODAL_MOVES:
            x, y = m["xy"]
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "cluster": MOCK_CONVERGENCE["cluster_labels"][m["cluster"]],
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
            color_discrete_sequence=["#d6c25a", "#6ec07a", "#5a9fd6"],
            height=360,
        )
        fig.update_traces(marker=dict(size=15, line=dict(width=1, color="#0d1112")))
        fig.update_layout(
            paper_bgcolor="#0d1112",
            plot_bgcolor="#0d1112",
            font=dict(family="JetBrains Mono, SF Mono, Menlo, monospace", color="#8b9088", size=11),
            xaxis=dict(showgrid=False, zeroline=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, visible=False),
            margin=dict(l=8, r=8, t=8, b=8),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
                bgcolor="rgba(0,0,0,0)",
                font=dict(size=10),
            ),
        )
        st.plotly_chart(fig, width="stretch")
        st.markdown(
            f'<div style="font-size:0.85rem; color:var(--ink-dim); margin-top:0.4rem;">'
            f"{MOCK_CONVERGENCE['convergence_summary']}</div>",
            unsafe_allow_html=True,
        )
        panel_close()

    with col_right:
        panel_open("NOTABLE ABSENCES", f"{len(MOCK_CONVERGENCE['notable_absences']):02d} GAPS")
        for absence in MOCK_CONVERGENCE["notable_absences"]:
            st.markdown(
                f'<div style="font-size:0.86rem; margin-bottom:0.65rem;">'
                f'<span style="color:var(--accent); margin-right:0.4rem;">▸</span>{absence}</div>',
                unsafe_allow_html=True,
            )
        panel_close()

    # Cross-run callout — full width below
    st.markdown(
        f"""
<div class="callout">
  <div class="label">CROSS-RUN OBSERVATION · CARTOGRAPHER MEMORY</div>
  <div class="body">
    <span class="triangles">▲▲▲</span>{MOCK_CONVERGENCE['cross_run_observations']}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Modal ensemble — subsystem readout
# ──────────────────────────────────────────────────────────────────────


def render_modal_ensemble() -> None:
    rows_html = []
    for m in MOCK_MODAL_MOVES:
        provider_short = {"anthropic": "ANTHRC", "openai": "OPENAI"}.get(
            m["provider"], m["provider"].upper()
        )
        rows_html.append(
            f"""<tr>
  <td>{m['instance_idx']:02d}</td>
  <td>{provider_short}</td>
  <td><code>{m['model']}</code></td>
  <td>{m['temperature']:.2f}</td>
  <td class="cluster-cell">C{m['cluster']}</td>
  <td class="move-cell">{m['move_title']}</td>
  <td class="doctrine-cell">{chips(m['doctrine_cited'])}</td>
  <td class="t">▲▲▲ OK</td>
</tr>"""
        )
    # Single st.markdown call: <details> must contain its body in the same DOM
    # subtree, otherwise Streamlit's per-call wrappers leak the body outside.
    st.markdown(
        f"""
<details class="panel">
  <summary>
    <span class="label">MODAL ENSEMBLE · 8 SUBSYSTEMS REPORTING</span>
    <span class="meta">TEMP 0.85–1.00 · DOCTRINE-GROUNDED · CLICK TO EXPAND</span>
  </summary>
  <div class="panel-body">
    <table class="subsys-table">
      <thead>
        <tr>
          <th>INST</th><th>PROV</th><th>MODEL</th><th>TEMP</th>
          <th>CLUSTER</th><th>CANDIDATE MOVE</th><th>DOCTRINE</th><th>STATUS</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
  </div>
</details>
""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Audit
# ──────────────────────────────────────────────────────────────────────


def render_audit() -> None:
    with st.expander("AUDIT · MANIFEST · PROMPT VERSIONS · LLM CALL LOG", expanded=False):
        run_ids = _list_run_ids()
        if run_ids:
            run_id = st.selectbox("Run", run_ids, index=0)
        else:
            st.markdown(
                f'<div style="color:var(--ink-dim); font-size:0.85rem; margin-bottom:0.6rem;">'
                f"NO RUNS ON DISK · SHOWING MOCK MANIFEST <code>{MOCK_RUN_ID}</code></div>",
                unsafe_allow_html=True,
            )
            run_id = MOCK_RUN_ID

        manifest = _load_manifest(run_id)
        totals = manifest.get("totals", {})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("LLM CALLS", totals.get("llm_calls", "—"))
        c2.metric("INPUT TOKENS", f"{totals.get('input_tokens', 0):,}")
        c3.metric("OUTPUT TOKENS", f"{totals.get('output_tokens', 0):,}")
        cost = totals.get("cost_usd", 0)
        c4.metric("COST USD", f"${cost:.2f}" if isinstance(cost, (int, float)) else "—")

        # Judge calibration — surfaces drift / outlier judges across the panel.
        st.markdown('<div class="subhead">JUDGE CALIBRATION · NOVEL-RATE PER JUDGE</div>', unsafe_allow_html=True)
        n_candidates = len(MOCK_MENU)
        judge_rows = []
        for ji in range(5):
            would_count = sum(p["would_have_generated"][ji] for p in MOCK_MENU)
            mean_plaus = sum(p["judge_ratings"][ji] for p in MOCK_MENU) / n_candidates
            judge_rows.append(
                {
                    "judge": f"JUDGE {ji + 1:02d}",
                    "would_have_generated_pct": round(100 * would_count / n_candidates, 1),
                    "novel_pct": round(100 * (n_candidates - would_count) / n_candidates, 1),
                    "mean_plausibility": round(mean_plaus, 2),
                }
            )
        cal_fig = px.bar(
            judge_rows,
            x="novel_pct",
            y="judge",
            orientation="h",
            text="novel_pct",
            hover_data={"would_have_generated_pct": True, "mean_plausibility": True, "novel_pct": False},
            color_discrete_sequence=["#d6c25a"],
            height=220,
        )
        cal_fig.update_traces(
            texttemplate="%{text}%",
            textposition="outside",
            textfont=dict(family="JetBrains Mono, SF Mono, Menlo, monospace", color="#e8ece6", size=11),
            marker_line_color="#0d1112",
            marker_line_width=1,
        )
        cal_fig.update_layout(
            paper_bgcolor="#0d1112",
            plot_bgcolor="#0d1112",
            font=dict(family="JetBrains Mono, SF Mono, Menlo, monospace", color="#8b9088", size=11),
            xaxis=dict(
                title="% OF CANDIDATES THIS JUDGE FOUND NOVEL",
                range=[0, 110],
                gridcolor="#1c2123",
                zeroline=False,
            ),
            yaxis=dict(title="", gridcolor="#1c2123", zeroline=False),
            margin=dict(l=10, r=20, t=10, b=10),
            showlegend=False,
        )
        st.plotly_chart(cal_fig, width="stretch")

        st.markdown('<div class="subhead">PROMPT VERSIONS · GIT BLOB HASH AT CALL TIME</div>', unsafe_allow_html=True)
        for fname, version in sorted(manifest.get("prompt_versions", {}).items()):
            st.markdown(
                f'<div class="leader">'
                f'<span class="l-key">{fname}</span>'
                f'<span class="l-fill"></span>'
                f'<span class="l-val"><code>{version}</code></span>'
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown('<div class="subhead">MANIFEST</div>', unsafe_allow_html=True)
        st.json(manifest, expanded=False)

        st.markdown('<div class="subhead">LLM CALL LOG</div>', unsafe_allow_html=True)
        query = st.text_input(
            "FILTER",
            placeholder="filter by stage, provider, agent, call_id, prompt_version…",
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
# Scenario picker — small, tucked above the menu
# ──────────────────────────────────────────────────────────────────────


def render_scenario_picker() -> dict | None:
    scenarios = list_scenarios()
    if not scenarios:
        return None
    labels = {s.get("title", s.get("scenario_id", s["_path"])): s for s in scenarios}
    keys = list(labels.keys())
    # Default to Taiwan if present (the demo scenario)
    default_idx = next((i for i, k in enumerate(keys) if "taiwan" in k.lower()), 0)
    choice = st.selectbox("SCENARIO", keys, index=default_idx, label_visibility="collapsed")
    return labels[choice]


# ──────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    st.set_page_config(
        page_title="ADRT-001 · Adversarial-Distribution Red Team",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(PROTO_CSS, unsafe_allow_html=True)

    scenario = render_scenario_picker()
    manifest = _load_manifest(MOCK_RUN_ID)

    render_header(scenario, manifest)
    render_briefing()
    render_menu(MOCK_MENU)
    render_judgment_matrix(MOCK_MENU)
    render_convergence()
    render_modal_ensemble()
    render_audit()

    # Footer epigraph — Reisswitz callback + the Wong-register disclaimer
    # in one line. Lands without lecturing.
    st.markdown(
        """
<div style="text-align:center; color:var(--ink-faint); font-size:0.78rem;
            letter-spacing:0.18em; margin-top:2.5rem; padding-top:1.2rem;
            border-top:1px solid var(--rule);">
  AFTER REISSWITZ · BERLIN · 1824
  &nbsp;·&nbsp;
  AN AID TO DELIBERATION, NOT A FORECAST
</div>
""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
