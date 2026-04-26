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
import plotly.graph_objects as go
import streamlit as st

from src.ui.run_loader import list_runs, load_run
from src.ui.scenarios_loader import list_scenarios


# ──────────────────────────────────────────────────────────────────────
# Style
# ──────────────────────────────────────────────────────────────────────

INSTRUMENT_CSS = """
<style>
:root {
    --bg: #fafafa;
    --paper: #ffffff;
    --ink: #0a0a0a;
    --ink-2: #2a2a2a;
    --ink-dim: #555;
    --ink-faint: #a8a8a8;
    --rule: #0a0a0a;
    --rule-dim: #d8d8d8;
    --rule-faint: #ececec;
    --accent: #c81e1e;
    --accent-bg: #fff0f0;
    --mono: "Berkeley Mono", "JetBrains Mono", "IBM Plex Mono", "SF Mono",
            ui-monospace, Menlo, Consolas, monospace;
}

/* App-wide reset to monospace, white bg, black ink */
html, body, [class*="css"], [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main, .block-container,
.stApp, .stApp > header, [data-testid="stSidebar"] {
    background: var(--bg) !important;
    color: var(--ink) !important;
    font-family: var(--mono) !important;
}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 4rem !important;
    max-width: 1400px !important;
}

html, body, p, li, span, div, label {
    font-size: 16px;
    line-height: 1.55;
    color: var(--ink);
    font-family: var(--mono);
}

/* Strip Streamlit chrome */
header[data-testid="stHeader"] { display: none; }
[data-testid="stToolbar"] { display: none; }
footer { display: none; }

/* Headings — uppercase, blocky, letter-spaced */
h1, h2, h3, h4, h5, h6 {
    font-family: var(--mono) !important;
    color: var(--ink) !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}
h1 { font-size: 1.6rem; letter-spacing: 0.18em; margin-bottom: 0.4rem; }
h2 { font-size: 1.2rem; }
h3 { font-size: 1.05rem; }
h4 { font-size: 0.95rem; }

/* The header strip — system identifier */
.id-strip {
    border: 2px solid var(--rule);
    background: var(--paper);
    padding: 0.5rem 0.9rem;
    margin-bottom: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.92rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}
.id-strip .id-l { color: var(--ink); font-weight: 700; }
.id-strip .id-r { color: var(--ink-dim); letter-spacing: 0.12em; }
.id-strip .badge {
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 0.1rem 0.55rem;
    font-size: 0.84rem;
    letter-spacing: 0.18em;
    font-weight: 700;
}

/* Status row under id strip */
.status-row {
    display: flex;
    gap: 0;
    border: 2px solid var(--rule);
    border-top: none;
    background: var(--paper);
    margin-bottom: 1.2rem;
    flex-wrap: wrap;
}
.status-cell {
    padding: 0.45rem 0.95rem;
    font-size: 0.85rem;
    color: var(--ink-dim);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-right: 1px solid var(--rule-dim);
    flex: 1;
    min-width: 130px;
}
.status-cell:last-child { border-right: none; }
.status-cell .v {
    color: var(--ink);
    margin-left: 0.45rem;
    letter-spacing: 0.04em;
    font-weight: 700;
}

/* Bordered panel idiom */
.panel {
    border: 2px solid var(--rule);
    background: var(--paper);
    margin-bottom: 1.1rem;
}
.panel-head {
    border-bottom: 2px solid var(--rule);
    padding: 0.4rem 0.85rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--paper);
}
.panel-head .label {
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.92rem;
    color: var(--ink);
    font-weight: 700;
}
.panel-head .meta {
    font-size: 0.82rem;
    color: var(--ink-dim);
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.panel-body { padding: 0.85rem 1rem; }

/* ASCII rules */
.hr-double {
    color: var(--ink);
    letter-spacing: -0.05em;
    font-family: var(--mono);
    line-height: 1;
    margin: 0.3rem 0;
    overflow: hidden;
    white-space: nowrap;
}
.hr-single {
    color: var(--ink-dim);
    letter-spacing: -0.05em;
    font-family: var(--mono);
    line-height: 1;
    margin: 0.3rem 0;
    overflow: hidden;
    white-space: nowrap;
}

/* Dot leader: KEY ............ VALUE */
.leader {
    display: flex;
    align-items: baseline;
    font-size: 0.95rem;
    margin: 0.18rem 0;
    font-family: var(--mono);
}
.leader .l-key { color: var(--ink-dim); text-transform: uppercase; letter-spacing: 0.1em; font-size: 0.82rem; }
.leader .l-fill {
    flex: 1;
    border-bottom: 1px dotted var(--ink-faint);
    margin: 0 0.45rem;
    transform: translateY(-0.32rem);
}
.leader .l-val {
    color: var(--ink);
    text-align: right;
    font-weight: 700;
    white-space: nowrap;
}

/* Block-character bar */
.bar {
    font-family: var(--mono);
    letter-spacing: 0.02em;
    color: var(--ink);
}
.bar .filled { color: var(--accent); }
.bar .empty  { color: var(--ink-faint); }

/* Funnel — pipeline counts */
.funnel {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
    font-size: 0.86rem;
    margin: 0.4rem 0 1rem 0;
    padding: 0.6rem 0.85rem;
    border: 2px solid var(--rule);
    background: var(--paper);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.funnel .stage {
    border: 1px solid var(--rule);
    padding: 0.25rem 0.6rem;
    color: var(--ink-dim);
    background: var(--paper);
}
.funnel .stage .n {
    color: var(--ink);
    font-size: 1.1rem;
    margin-right: 0.35rem;
    font-weight: 700;
}
.funnel .stage.alive { border-color: var(--accent); }
.funnel .stage.alive .n { color: var(--accent); }
.funnel .arrow {
    color: var(--ink);
    letter-spacing: 0.2em;
    font-weight: 700;
}

/* Modal ensemble cards — instrument-panel grid cells */
.modal-card {
    border: 1.5px solid var(--rule);
    background: var(--paper);
    padding: 0.65rem 0.8rem;
    margin-bottom: 0.5rem;
    height: 100%;
}
.modal-card .meta {
    font-size: 0.74rem;
    color: var(--ink-dim);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid var(--rule-dim);
    padding-bottom: 0.32rem;
    margin-bottom: 0.45rem;
}
.modal-card .title {
    font-size: 0.95rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ink);
    margin-bottom: 0.45rem;
    line-height: 1.3;
}
.modal-card .summary {
    font-size: 0.86rem;
    line-height: 1.45;
    color: var(--ink-2);
}

/* Cluster table inside convergence */
.cluster-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
    margin: 0.5rem 0 0.8rem 0;
}
.cluster-table th {
    text-align: left;
    color: var(--ink-dim);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    font-size: 0.78rem;
    padding: 0.45rem 0.55rem;
    border-bottom: 2px solid var(--rule);
}
.cluster-table td {
    padding: 0.5rem 0.55rem;
    border-bottom: 1px solid var(--rule-dim);
    vertical-align: top;
    color: var(--ink);
}
.cluster-table td.cluster-bar {
    width: 30%;
    color: var(--accent);
    font-family: var(--mono);
    letter-spacing: 0.02em;
}
.cluster-table td.cluster-n {
    text-align: right;
    color: var(--ink);
    font-weight: 700;
    width: 6%;
}
.cluster-table td.cluster-theme {
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* Absences */
.absence-item {
    border-left: 3px solid var(--rule);
    padding: 0.4rem 0 0.4rem 0.7rem;
    margin: 0.5rem 0;
}
.absence-item .body {
    font-size: 0.96rem;
    color: var(--ink);
    margin-bottom: 0.2rem;
}
.absence-item .gloss {
    font-size: 0.82rem;
    color: var(--ink-dim);
    line-height: 1.45;
}

/* Cross-run callout — single red bar */
.callout {
    border: 2px solid var(--accent);
    background: var(--accent-bg);
    padding: 0.85rem 1rem;
    margin: 0.6rem 0 0.2rem 0;
}
.callout.empty {
    border-color: var(--ink-faint);
    background: var(--paper);
}
.callout .label {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.78rem;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 0.4rem;
}
.callout.empty .label { color: var(--ink-dim); }
.callout .body {
    font-size: 0.96rem;
    color: var(--ink);
    line-height: 1.5;
    margin-bottom: 0.4rem;
}
.callout .body:last-child { margin-bottom: 0; }

/* Chips */
.chip {
    display: inline-block;
    padding: 0.08rem 0.5rem;
    margin: 0.1rem 0.25rem 0.1rem 0;
    background: var(--paper);
    border: 1px solid var(--rule);
    border-radius: 0;
    font-size: 0.78rem;
    color: var(--ink);
    font-family: var(--mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}
.chip.accent { background: var(--accent); color: #fff; border-color: var(--accent); }
.chip.dim { color: var(--ink-dim); border-color: var(--rule-dim); }
.chip.tier-A { background: var(--accent); color: #fff; border-color: var(--accent); }
.chip.tier-B { background: var(--paper); color: var(--ink); border-color: var(--ink); }
.chip.tier-C { background: var(--paper); color: var(--ink-dim); border-color: var(--rule-dim); }
.chip.surv-yes { background: var(--paper); color: var(--accent); border-color: var(--accent); }
.chip.surv-no { background: var(--paper); color: var(--ink-faint); border-color: var(--ink-faint); text-decoration: line-through; }

/* Curator preamble block */
.curator-block {
    border: 2px solid var(--rule);
    border-left: 6px solid var(--accent);
    background: var(--paper);
    padding: 0.85rem 1rem;
    margin: 0.6rem 0 1rem 0;
}
.curator-block .head {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.curator-block .body {
    font-size: 0.96rem;
    line-height: 1.55;
    color: var(--ink);
}

/* Survivor card */
.survivor {
    border-top: 1.5px solid var(--rule-dim);
    padding: 0.7rem 0;
}
.survivor:first-child {
    border-top: 2px solid var(--rule);
    padding-top: 0.85rem;
}
.survivor .head-row {
    display: flex;
    align-items: baseline;
    gap: 0.7rem;
    flex-wrap: wrap;
    margin-bottom: 0.3rem;
}
.survivor .idx {
    font-size: 0.86rem;
    color: var(--ink-dim);
    letter-spacing: 0.08em;
    font-weight: 700;
    min-width: 2.5rem;
}
.survivor .title {
    font-size: 1.05rem;
    color: var(--ink);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex: 1;
}
.survivor .breaks {
    margin: 0.4rem 0;
    padding: 0.3rem 0 0.3rem 0.6rem;
    border-left: 3px solid var(--accent);
    color: var(--ink-2);
    font-size: 0.94rem;
}
.survivor .summary {
    color: var(--ink);
    font-size: 0.94rem;
    margin: 0.3rem 0;
    line-height: 1.55;
}
.survivor .stat-row {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-top: 0.5rem;
    font-size: 0.86rem;
    color: var(--ink-dim);
}
.survivor .stat-row .stat .v {
    color: var(--ink);
    font-weight: 700;
    margin-left: 0.3rem;
}

/* Curator rating block under a survivor */
.rating-block {
    border-top: 1px dashed var(--rule-dim);
    margin-top: 0.7rem;
    padding-top: 0.6rem;
}
.rating-block .head {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 0.45rem;
}
.rating-block .row {
    display: flex;
    align-items: flex-start;
    gap: 1.4rem;
    margin: 0.35rem 0;
    padding: 0.4rem 0;
    border-bottom: 1px dashed var(--rule-faint);
    font-size: 0.92rem;
    line-height: 1.55;
}
.rating-block .row:last-child { border-bottom: none; }
.rating-block .row .k {
    flex: 0 0 13rem;
    color: var(--ink-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.76rem;
    padding-top: 0.18rem;
    line-height: 1.4;
    word-break: break-word;
}
.rating-block .row .v {
    flex: 1;
    min-width: 0;
    color: var(--ink);
}

/* Action rows */
.action-row {
    font-size: 0.86rem;
    color: var(--ink);
    line-height: 1.5;
    margin: 0.32rem 0;
    padding-left: 0.6rem;
    border-left: 2px solid var(--rule-dim);
}
.action-row .actor {
    color: var(--ink);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.action-row .meta-line {
    font-size: 0.78rem;
    color: var(--ink-dim);
    letter-spacing: 0.06em;
}

/* Dead row */
.dead-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-top: 1px solid var(--rule-dim);
    padding: 0.4rem 0;
    font-size: 0.88rem;
}
.dead-row:first-child { border-top: none; }
.dead-row .title {
    color: var(--ink-faint);
    text-decoration: line-through;
    text-decoration-color: var(--ink-faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.dead-row .reason {
    color: var(--accent);
    letter-spacing: 0.06em;
    font-size: 0.78rem;
    text-transform: uppercase;
    white-space: nowrap;
    margin-left: 1rem;
}

/* Disclaimer */
.disclaimer {
    color: var(--ink-dim);
    font-size: 0.92rem;
    font-style: normal;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 0.3rem 0 0.8rem 0;
}

/* Cluster card (legacy fallback) */
.cluster-card {
    border: 1.5px solid var(--rule);
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.4rem;
    background: var(--paper);
}

/* No-runs */
.no-runs {
    color: var(--ink);
    background: var(--paper);
    border: 2px solid var(--accent);
    padding: 0.7rem 0.95rem;
    border-radius: 0;
    font-size: 0.92rem;
    margin-bottom: 1rem;
}

/* Streamlit overrides */
.stMarkdown, .stMarkdown p { color: var(--ink); }

[data-testid="stExpander"] {
    border: 2px solid var(--rule) !important;
    background: var(--paper) !important;
    border-radius: 0 !important;
    margin-bottom: 0.9rem;
}
[data-testid="stExpander"] > details > summary {
    padding: 0.5rem 0.85rem !important;
    background: var(--paper) !important;
}
[data-testid="stExpander"] details summary p {
    color: var(--ink) !important;
    font-family: var(--mono) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.14em !important;
    font-size: 0.92rem !important;
    font-weight: 700 !important;
}
[data-testid="stExpander"] details[open] > summary {
    border-bottom: 2px solid var(--rule);
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 0.85rem 1rem !important;
}

[data-testid="stMetricLabel"] {
    color: var(--ink-dim) !important;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.74rem !important;
}
[data-testid="stMetricValue"] {
    color: var(--ink) !important;
    font-family: var(--mono) !important;
    font-weight: 700 !important;
}

[data-baseweb="select"] > div, .stTextInput input, .stSelectbox div[role="combobox"] {
    background: var(--paper) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
}

.stButton button {
    background: var(--paper) !important;
    border: 2px solid var(--rule) !important;
    color: var(--ink) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    padding: 0.4rem 0.9rem !important;
}
.stButton button:hover:enabled {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}
.stButton button:disabled {
    border-color: var(--rule-dim) !important;
    color: var(--ink-faint) !important;
}

hr { border-color: var(--rule) !important; }
code, pre {
    color: var(--ink) !important;
    background: var(--rule-faint) !important;
    border: 1px solid var(--rule-dim);
    padding: 0.05rem 0.3rem;
    font-family: var(--mono) !important;
}
a { color: var(--accent) !important; text-decoration: underline; }

/* DataFrame */
[data-testid="stDataFrame"] {
    border: 2px solid var(--rule) !important;
    border-radius: 0 !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--paper) !important;
    border-right: 2px solid var(--rule);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.86rem;
    color: var(--ink) !important;
}
[data-testid="stSidebar"] hr { display: none; }
[data-testid="stSidebar"] code {
    background: var(--rule-faint) !important;
    color: var(--ink) !important;
}

/* Tooltips — Streamlit's BaseWeb dark popovers must go white */
[data-baseweb="tooltip"],
[data-baseweb="popover"],
[role="tooltip"] {
    background: var(--paper) !important;
    color: var(--ink) !important;
    border: 2px solid var(--rule) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
    box-shadow: 4px 4px 0 var(--rule) !important;
}
[data-baseweb="tooltip"] *,
[data-baseweb="popover"] *,
[role="tooltip"] * {
    color: var(--ink) !important;
    background: transparent !important;
    font-family: var(--mono) !important;
}

/* Help icon (the ? next to widget labels) */
[data-testid="stTooltipHoverTarget"],
[data-testid="stTooltipIcon"] svg {
    color: var(--ink-dim) !important;
    fill: var(--ink-dim) !important;
}

/* Dropdown menus */
[data-baseweb="menu"], [data-baseweb="select-dropdown"] {
    background: var(--paper) !important;
    border: 2px solid var(--rule) !important;
    border-radius: 0 !important;
    color: var(--ink) !important;
}
[data-baseweb="menu"] li, [data-baseweb="menu"] [role="option"] {
    color: var(--ink) !important;
    background: var(--paper) !important;
    font-family: var(--mono) !important;
}
[data-baseweb="menu"] li:hover, [data-baseweb="menu"] [role="option"]:hover,
[data-baseweb="menu"] [aria-selected="true"] {
    background: var(--accent-bg) !important;
    color: var(--ink) !important;
}

/* Toggle / checkbox / radio */
[data-testid="stToggle"] label, .stCheckbox label, .stRadio label {
    color: var(--ink) !important;
    font-family: var(--mono) !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.84rem !important;
}

/* Spinner / status */
[data-testid="stStatusWidget"] {
    background: var(--paper) !important;
    color: var(--ink) !important;
    border: 1px solid var(--rule) !important;
}

/* Alert / info / warning / error boxes */
.stAlert, [data-testid="stAlert"] {
    background: var(--paper) !important;
    border: 2px solid var(--rule) !important;
    border-radius: 0 !important;
    color: var(--ink) !important;
}
.stAlert *, [data-testid="stAlert"] * {
    color: var(--ink) !important;
    font-family: var(--mono) !important;
}

/* Captions */
[data-testid="stCaptionContainer"], .stCaption, small {
    color: var(--ink-dim) !important;
    font-family: var(--mono) !important;
}

/* JSON viewer — Streamlit wraps react-json-view tokens in nested divs.
   The default theme is dark. Force every nested element to white-bg/black ink,
   then re-color by token type (red accent for strings, dim for keys). */
.stJson, [data-testid="stJson"] {
    background: var(--paper) !important;
    color: var(--ink) !important;
    border: 2px solid var(--rule) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    padding: 0.4rem !important;
}
.stJson *, [data-testid="stJson"] * {
    background: transparent !important;
    background-color: transparent !important;
    font-family: var(--mono) !important;
    font-size: 0.85rem !important;
}
[data-testid="stJson"] .object-key,
[data-testid="stJson"] .object-key-val,
[data-testid="stJson"] [class*="object-name"],
[data-testid="stJson"] [class*="key-text"] {
    color: var(--ink-dim) !important;
}
[data-testid="stJson"] .string-value,
[data-testid="stJson"] [class*="string-value"] {
    color: var(--accent) !important;
}
[data-testid="stJson"] .boolean,
[data-testid="stJson"] .number,
[data-testid="stJson"] [class*="boolean"],
[data-testid="stJson"] [class*="number"] {
    color: var(--ink) !important;
    font-weight: 700;
}
[data-testid="stJson"] .null,
[data-testid="stJson"] [class*="null"] {
    color: var(--ink-faint) !important;
}
[data-testid="stJson"] .icon-container,
[data-testid="stJson"] [class*="icon-container"] svg,
[data-testid="stJson"] svg {
    color: var(--ink) !important;
    fill: var(--ink) !important;
}
[data-testid="stJson"] [class*="copy-to-clipboard"] {
    color: var(--ink-dim) !important;
}
/* Nuke any inline color styles set by react-json-view */
[data-testid="stJson"] [style*="color:"] {
    color: var(--ink) !important;
}
[data-testid="stJson"] [style*="background"] {
    background: transparent !important;
}

/* Code blocks — st.code() renders inside [data-testid="stCodeBlock"] with
   a syntax-highlighting theme that defaults to dark. Force white-bg + black ink. */
[data-testid="stCodeBlock"], [data-testid="stCode"], .stCodeBlock {
    background: var(--paper) !important;
    border: 2px solid var(--rule) !important;
    border-radius: 0 !important;
}
[data-testid="stCodeBlock"] pre,
[data-testid="stCode"] pre,
.stCodeBlock pre,
[data-testid="stCodeBlock"] code,
.stCodeBlock code {
    background: var(--paper) !important;
    color: var(--ink) !important;
    font-family: var(--mono) !important;
    font-size: 0.85rem !important;
    padding: 0.6rem !important;
    border: none !important;
}
/* highlight.js token classes — kill any colors and force monochrome */
[data-testid="stCodeBlock"] .hljs,
[data-testid="stCodeBlock"] .hljs *,
.hljs, .hljs * {
    background: transparent !important;
    color: var(--ink) !important;
    font-family: var(--mono) !important;
}
.hljs-string, .hljs-attr-value, .hljs-meta-string,
[class*="hljs-string"] { color: var(--accent) !important; }
.hljs-keyword, .hljs-built_in, .hljs-type, .hljs-literal,
[class*="hljs-keyword"], [class*="hljs-built"] { color: var(--ink) !important; font-weight: 700; }
.hljs-comment, .hljs-quote,
[class*="hljs-comment"] { color: var(--ink-faint) !important; font-style: italic; }
.hljs-number, .hljs-regexp,
[class*="hljs-number"] { color: var(--ink) !important; font-weight: 700; }
.hljs-attr, .hljs-attribute, .hljs-name,
[class*="hljs-attr"], [class*="hljs-name"] { color: var(--ink-dim) !important; }
.hljs-tag, .hljs-section,
[class*="hljs-tag"], [class*="hljs-section"] { color: var(--ink-2) !important; }
/* Copy-to-clipboard icon button on code blocks */
[data-testid="stCodeBlock"] button,
.stCodeBlock button {
    background: var(--paper) !important;
    color: var(--ink-dim) !important;
    border: 1px solid var(--rule-dim) !important;
}
[data-testid="stCodeBlock"] button svg,
.stCodeBlock button svg {
    color: var(--ink) !important;
    fill: var(--ink) !important;
}

/* Dataframe cells */
[data-testid="stDataFrame"] *, [data-testid="stTable"] * {
    background: var(--paper) !important;
    color: var(--ink) !important;
    font-family: var(--mono) !important;
    border-color: var(--rule-dim) !important;
}
[data-testid="stDataFrame"] [role="columnheader"] {
    background: var(--paper) !important;
    color: var(--ink-dim) !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.78rem !important;
    border-bottom: 2px solid var(--rule) !important;
}

/* Strong / bold default to ink */
strong, b { color: var(--ink) !important; }

/* Em / italic */
em, i { color: var(--ink-2) !important; }

/* Blockquote */
blockquote {
    border-left: 4px solid var(--accent) !important;
    background: var(--paper) !important;
    color: var(--ink) !important;
    padding: 0.5rem 0.9rem !important;
    margin: 0.6rem 0 !important;
}
blockquote p { color: var(--ink) !important; }
</style>
"""


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _chips(items: list[str]) -> str:
    return "".join(f'<span class="chip dim">{item}</span>' for item in items)


def _bar_html(value: float, maximum: float, width: int = 14) -> str:
    """Block-character bar like ████████░░░░░░ — used for plausibility/wgen displays."""
    if maximum <= 0:
        return ""
    n_filled = max(0, min(width, round(width * (value / maximum))))
    n_empty = max(0, width - n_filled)
    return (
        f'<span class="bar">'
        f'<span class="filled">{"█" * n_filled}</span>'
        f'<span class="empty">{"░" * n_empty}</span>'
        f'</span>'
    )


def _rating_bar(rating: int, max_rating: int = 5) -> str:
    """Compact 5-cell block-char bar for plausibility scores."""
    rating = max(0, min(int(rating), max_rating))
    return (
        f'<span class="bar">'
        f'<span class="filled">{"█" * rating}</span>'
        f'<span class="empty">{"░" * (max_rating - rating)}</span>'
        f'</span>'
    )


def _leader_html(key: str, value: str) -> str:
    return (
        f'<div class="leader">'
        f'<span class="l-key">{key}</span>'
        f'<span class="l-fill"></span>'
        f'<span class="l-val">{value}</span>'
        f'</div>'
    )


def _hr_double() -> str:
    return '<div class="hr-double">' + "═" * 220 + "</div>"


def _hr_single() -> str:
    return '<div class="hr-single">' + "─" * 220 + "</div>"


# Mono stack used everywhere — plotly accepts a CSS-style comma-separated
# fallback chain, but every font= declaration must include it; otherwise
# plotly falls back to its own default (Open Sans / serif), which renders
# as Times-like serif on systems where it can't load.
_MONO_STACK = "'Berkeley Mono', 'JetBrains Mono', 'IBM Plex Mono', 'SF Mono', Menlo, Monaco, Consolas, 'Courier New', monospace"

# Plotly default styling for the white-bg / black / red palette
_PLOTLY_LAYOUT = dict(
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    font=dict(family=_MONO_STACK, color="#0a0a0a", size=13),
    margin=dict(l=50, r=20, t=20, b=40),
    hoverlabel=dict(
        bgcolor="#ffffff",
        bordercolor="#0a0a0a",
        font=dict(family=_MONO_STACK, color="#0a0a0a"),
    ),
)
_AXIS_STYLE = dict(
    showgrid=True,
    gridcolor="#ececec",
    zeroline=True,
    zerolinecolor="#0a0a0a",
    zerolinewidth=1,
    linecolor="#0a0a0a",
    linewidth=1.5,
    tickcolor="#0a0a0a",
    tickfont=dict(family=_MONO_STACK, color="#0a0a0a", size=11),
    title=dict(font=dict(family=_MONO_STACK, color="#555", size=11)),
)


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
    # Top identifier strip
    st.markdown(
        '<div class="id-strip">'
        '<span class="id-l">ADVERSARIAL-DISTRIBUTION RED TEAM '
        '<span style="color:var(--ink-dim);margin-left:0.7rem;letter-spacing:0.1em;">SCSP-2026 / WARGAMING</span></span>'
        '<span class="badge">MENU OF HYPOTHESES — NOT A FORECAST</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if run:
        manifest = run["manifest"]
        scen = run["scenario"]
        scen_id = scen.get("scenario_id") or manifest.get("scenario_id") or "—"
        totals = manifest.get("totals", {})
        run_id_short = run['run_id'][:8] if run.get("run_id") else "—"
        cells = [
            ("SCENARIO", scen_id),
            ("RUN", run_id_short),
            ("STATUS", manifest.get('status', '—')),
            ("CALLS", str(totals.get('llm_calls', '—'))),
            ("COST", f"${totals.get('cost_usd', 0):.2f}"),
        ]
        cells_html = "".join(
            f'<div class="status-cell">{label}<span class="v">{value}</span></div>'
            for label, value in cells
        )
        st.markdown(
            f'<div class="status-row">{cells_html}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div style="height:1.2rem;"></div>', unsafe_allow_html=True)

    # Pipeline funnel
    if run:
        moves = run.get("modal_moves") or []
        clusters = (run.get("convergence") or {}).get("clusters") or []
        menu = run.get("menu") or []
        n_surv = sum(1 for p in menu if p.get("surviving"))
        n_total = len(menu)
        ratings = (run.get("branch_curation") or {}).get("ratings") or []
        n_rated_a = sum(1 for r in ratings if r.get("wargame_prep_value") == "A")

        stages = [
            ("MODAL", len(moves), False),
            ("CLUSTERS", len(clusters), False),
            ("CANDIDATES", n_total, False),
            ("SURVIVING", n_surv, True),
        ]
        if ratings:
            stages.append(("TIER-A", n_rated_a, True))

        funnel_html = ['<div class="funnel">']
        for i, (label, n, alive) in enumerate(stages):
            cls = "stage alive" if alive else "stage"
            funnel_html.append(f'<span class="{cls}"><span class="n">{n:02d}</span>{label}</span>')
            if i < len(stages) - 1:
                funnel_html.append('<span class="arrow">→</span>')
        funnel_html.append("</div>")
        st.markdown("".join(funnel_html), unsafe_allow_html=True)


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
    with st.expander(f"2 — Modal ensemble (N={len(moves)})", expanded=False):
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

    with st.expander("3 — Convergence and notable absences", expanded=False):
        # Cluster table — block-character bar per cluster, instrument-panel idiom.
        if clusters:
            max_members = max((len(c.get("member_move_ids") or []) for c in clusters), default=1)
            rows_html = []
            for c in clusters:
                theme = c.get("theme") or f"Cluster {c.get('cluster_id', '?')}"
                members = c.get("member_move_ids") or []
                reps = c.get("representative_actions") or []
                bar = _bar_html(len(members), max_members, width=20)
                reps_html = "<br/>".join(f"  · {r}" for r in reps) if reps else "—"
                rows_html.append(
                    f"<tr>"
                    f"<td class='cluster-n'>{len(members)}</td>"
                    f"<td class='cluster-bar'>{bar}</td>"
                    f"<td class='cluster-theme'><strong>{theme}</strong><br/>"
                    f"<span style='font-size:0.82rem;color:var(--ink-dim);text-transform:none;letter-spacing:0;'>{reps_html}</span></td>"
                    f"</tr>"
                )
            st.markdown(
                f"""
<table class="cluster-table">
  <thead>
    <tr><th style="width:6%">N</th><th style="width:30%">Distribution</th><th>Theme · representative actions</th></tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>
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
<div class="callout">
  <div class="label">▲▲▲ Cross-run observation · Convergence Cartographer memory</div>
  {body_html}
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
<div class="callout empty">
  <div class="label">Cross-run observation · Convergence Cartographer memory</div>
  <div class="body">No cross-run patterns yet — this populates after the same scenario family runs multiple times and the Cartographer's reflection memory accumulates.</div>
</div>
""",
                unsafe_allow_html=True,
            )


def render_signal_panel(run: dict | None) -> None:
    """Section 3.5 — quantitative signal panel.

    Three views of the same survival math:
      - Plausibility × would-have-generated scatter (each leaf as a dot;
        strict-filter quadrant boundaries drawn).
      - Per-judge × per-proposal plausibility heatmap (5 × N grid;
        shows judge agreement and where a single judge held out).
      - Curator A/B/C distribution across surviving moves.
    """
    if not run:
        return
    menu = run.get("menu") or []
    if not menu:
        return

    branch_curation = run.get("branch_curation") or {}
    ratings_by_pid = {r.get("proposal_id"): r for r in branch_curation.get("ratings", [])}

    with st.expander("3.5 — Signal panel · plausibility × novelty math", expanded=True):
        # Calibration note — surfaced inline so the demo audience sees the
        # honest accounting of judge behavior on this run.
        score_dist: dict[int, int] = {}
        for p in menu:
            for r in (p.get("judge_ratings") or []):
                score_dist[int(r)] = score_dist.get(int(r), 0) + 1
        if score_dist:
            score_summary = " · ".join(
                f"{k}={v}" for k, v in sorted(score_dist.items())
            )
            st.markdown(
                f'<div style="background:var(--paper);border:1px solid var(--rule-dim);'
                f'padding:0.55rem 0.85rem;margin-bottom:0.9rem;font-size:0.84rem;'
                f'color:var(--ink-dim);text-transform:uppercase;letter-spacing:0.08em;">'
                f'<strong style="color:var(--ink);">JUDGE SCORE DISTRIBUTION (THIS RUN):</strong> '
                f'{score_summary}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ============================================================
        # 3.5a — PLAUSIBILITY × WOULD-HAVE-GENERATED SCATTER
        # ============================================================
        st.markdown(
            '<div class="leader" style="margin-top:0.3rem;">'
            '<span class="l-key">3.5A · SCATTER</span>'
            '<span class="l-fill"></span>'
            '<span class="l-val">PLAUSIBILITY × WOULD-HAVE-GENERATED</span>'
            '</div>'
            '<div style="font-size:0.86rem;color:var(--ink-dim);margin-bottom:0.5rem;'
            'line-height:1.5;">'
            'Each candidate plotted at (median plausibility, would-have-generated count). '
            'The strict-filter quadrant is shaded red: <strong style="color:var(--accent);">'
            'plaus ≥ 4 AND wgen = 0</strong>. '
            'Surviving = red squares; rejected = black ×. '
            'Points jittered slightly so co-located candidates remain visible.'
            '</div>',
            unsafe_allow_html=True,
        )
        col_a, _spacer = st.columns([5, 1])

        with col_a:
            xs = [float(p.get("median_plausibility") or 0) for p in menu]
            ys = [int(p.get("would_have_generated_count") or 0) for p in menu]
            survs = [bool(p.get("surviving")) for p in menu]
            titles = [p.get("move_title", "?") for p in menu]
            tiers = [
                (ratings_by_pid.get(p.get("proposal_id"), {}) or {}).get("wargame_prep_value", "")
                for p in menu
            ]

            # Jitter overlapping points slightly so the scatter is readable
            import collections
            counts: dict[tuple[float, int], int] = collections.defaultdict(int)
            jx, jy = [], []
            for x, y in zip(xs, ys):
                k = (x, y)
                n = counts[k]
                counts[k] += 1
                # Offset along a hexagonal lattice
                offset = 0.06 * n
                angle = (n * 2.39996)  # golden-angle spread
                import math
                jx.append(x + offset * math.cos(angle))
                jy.append(y + offset * math.sin(angle))

            fig = go.Figure()

            # Strict-filter quadrant guides
            fig.add_shape(type="line", x0=4.0, x1=4.0, y0=-0.3, y1=5.3,
                          line=dict(color="#0a0a0a", width=1.5, dash="dash"))
            fig.add_shape(type="line", x0=0.5, x1=5.5, y0=0.5, y1=0.5,
                          line=dict(color="#0a0a0a", width=1.5, dash="dash"))
            # Survival quadrant shading
            fig.add_shape(type="rect", x0=4.0, x1=5.3, y0=-0.3, y1=0.5,
                          fillcolor="rgba(200,30,30,0.06)", line=dict(width=0))

            # Killed (rejected) — open black
            kx, ky, kt, ktier = [], [], [], []
            sx, sy, st_titles, stier = [], [], [], []
            for x, y, sv, t, tr in zip(jx, jy, survs, titles, tiers):
                if sv:
                    sx.append(x); sy.append(y); st_titles.append(t); stier.append(tr or "—")
                else:
                    kx.append(x); ky.append(y); kt.append(t); ktier.append(tr or "—")

            if kx:
                fig.add_trace(go.Scatter(
                    x=kx, y=ky, mode="markers", name="rejected",
                    marker=dict(symbol="x", size=12, color="#0a0a0a", line=dict(width=1.5)),
                    text=kt, hovertemplate="%{text}<br>plaus=%{x:.1f} wgen=%{y}<extra>rejected</extra>",
                ))
            if sx:
                fig.add_trace(go.Scatter(
                    x=sx, y=sy, mode="markers", name="surviving",
                    marker=dict(symbol="square", size=14, color="#c81e1e",
                                line=dict(color="#0a0a0a", width=1.2)),
                    text=st_titles, customdata=stier,
                    hovertemplate="%{text}<br>plaus=%{x:.1f} wgen=%{y}<br>tier=%{customdata}<extra>surviving</extra>",
                ))

            fig.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis=dict(**_AXIS_STYLE, range=[0.5, 5.4], tickvals=[1, 2, 3, 4, 5]),
                yaxis=dict(**_AXIS_STYLE, range=[-0.4, 5.4], tickvals=[0, 1, 2, 3, 4, 5]),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1.0,
                            bgcolor="rgba(255,255,255,0.9)",
                            bordercolor="#0a0a0a", borderwidth=1,
                            font=dict(family=_MONO_STACK, size=11)),
                height=380,
                annotations=[
                    dict(x=4.6, y=0.0, text="STRICT<br>SURVIVAL",
                         showarrow=False, font=dict(size=10, color="#c81e1e", family=_MONO_STACK),
                         xanchor="left"),
                ],
            )
            fig.update_xaxes(title_text="MEDIAN PLAUSIBILITY (5 JUDGES)")
            fig.update_yaxes(title_text="WOULD-HAVE-GENERATED COUNT")
            fig.update_layout(height=440)
            st.plotly_chart(fig, use_container_width=True)

        # ============================================================
        # 3.5b — PER-JUDGE × PER-PROPOSAL HEATMAP
        # ============================================================
        st.markdown(
            '<div class="hr-single">' + "─" * 220 + '</div>'
            '<div class="leader" style="margin-top:0.6rem;">'
            '<span class="l-key">3.5B · HEATMAP</span>'
            '<span class="l-fill"></span>'
            '<span class="l-val">JUDGE × PROPOSAL · PLAUSIBILITY</span>'
            '</div>'
            '<div style="font-size:0.86rem;color:var(--ink-dim);margin-bottom:0.5rem;'
            'line-height:1.5;">'
            'Each cell shows one judge\'s plausibility score on one candidate. '
            'Reading across a row = how much agreement the candidate drew. '
            'Reading down a column = whether a single judge ran calibration-low. '
            '<strong style="color:var(--ink);">This is the most informative chart on '
            'this run</strong>, since plausibility ceiling at 4 mutes the scatter.'
            '</div>',
            unsafe_allow_html=True,
        )
        # Heatmap goes full-width
        col_b, _ = st.columns([5, 1])
        with col_b:
            judge_matrix = []
            row_labels = []
            n_judges = 0
            for p in menu:
                ratings = p.get("judge_ratings") or []
                if not ratings:
                    continue
                judge_matrix.append([int(r) for r in ratings])
                title = p.get("move_title", "?")
                if len(title) > 32:
                    title = title[:30] + "…"
                row_labels.append(title)
                n_judges = max(n_judges, len(ratings))

            if judge_matrix and n_judges:
                # Pad rows to n_judges
                judge_matrix = [r + [0] * (n_judges - len(r)) for r in judge_matrix]
                col_labels = [f"J{i+1}" for i in range(n_judges)]
                # Custom red→white→accent colorscale, monotone
                heat = go.Figure(go.Heatmap(
                    z=judge_matrix,
                    x=col_labels,
                    y=row_labels,
                    colorscale=[
                        [0.0, "#ffffff"],
                        [0.2, "#f7d4d4"],
                        [0.5, "#e87a7a"],
                        [0.8, "#d63333"],
                        [1.0, "#a00000"],
                    ],
                    zmin=1, zmax=5,
                    text=judge_matrix,
                    texttemplate="%{text}",
                    textfont=dict(family=_MONO_STACK, size=12, color="#0a0a0a"),
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="PLAUS", font=dict(size=10, family=_MONO_STACK, color="#0a0a0a")),
                        thickness=10, len=0.7,
                        tickfont=dict(family=_MONO_STACK, size=10, color="#0a0a0a"),
                        outlinecolor="#0a0a0a", outlinewidth=1,
                    ),
                    xgap=2, ygap=2,
                ))
                heat_height = max(220, 70 + 28 * len(row_labels))
                heat_layout = {**_PLOTLY_LAYOUT, "margin": dict(l=240, r=20, t=40, b=20)}
                heat.update_layout(
                    **heat_layout,
                    xaxis=dict(side="top", linecolor="#0a0a0a",
                               tickfont=dict(family=_MONO_STACK, color="#0a0a0a", size=12)),
                    yaxis=dict(autorange="reversed", linecolor="#0a0a0a",
                               tickfont=dict(family=_MONO_STACK, color="#0a0a0a", size=11)),
                    height=heat_height,
                )
                st.plotly_chart(heat, use_container_width=True)
            else:
                st.markdown(
                    '<div style="color:var(--ink-dim);font-size:0.88rem;">'
                    'No judge ratings on disk for this run.'
                    '</div>',
                    unsafe_allow_html=True,
                )

        # ============================================================
        # 3.5c — CURATOR A/B/C DISTRIBUTION
        # ============================================================
        if branch_curation:
            ratings = branch_curation.get("ratings") or []
            tier_counts = {"A": 0, "B": 0, "C": 0}
            for r in ratings:
                t = r.get("wargame_prep_value")
                if t in tier_counts:
                    tier_counts[t] += 1
            total = sum(tier_counts.values())
            if total:
                branch = branch_curation.get("branch", "?")
                st.markdown(
                    '<div class="hr-single">' + "─" * 220 + '</div>'
                    '<div class="leader" style="margin-top:0.6rem;">'
                    '<span class="l-key">3.5C · CURATOR TIERS</span>'
                    '<span class="l-fill"></span>'
                    f'<span class="l-val">{branch} · {total} RATED</span>'
                    '</div>'
                    '<div style="font-size:0.86rem;color:var(--ink-dim);margin-bottom:0.6rem;'
                    'line-height:1.5;">'
                    '<strong style="color:var(--ink);">Wargame-prep value</strong> '
                    'as scored by the per-scenario branch curator. '
                    '<strong style="color:var(--accent);">A</strong> = stage in next exercise. '
                    '<strong>B</strong> = worth a tabletop. '
                    'C = read-ahead only / refer to other cell.'
                    '</div>',
                    unsafe_allow_html=True,
                )
                cols = st.columns(3)
                for col, tier in zip(cols, ["A", "B", "C"]):
                    n = tier_counts[tier]
                    bar = _bar_html(n, total, width=18)
                    pct = (100 * n / total) if total else 0
                    tier_class = f"tier-{tier}"
                    col.markdown(
                        f'<div style="border:2px solid var(--rule);padding:0.7rem 0.85rem;'
                        f'background:var(--paper);height:100%;">'
                        f'<div style="display:flex;align-items:baseline;gap:0.6rem;'
                        f'margin-bottom:0.4rem;">'
                        f'<span class="chip {tier_class}" style="font-size:0.95rem;'
                        f'padding:0.18rem 0.7rem;">TIER {tier}</span>'
                        f'<span style="font-size:1.4rem;font-weight:700;color:var(--ink);">'
                        f'{n}<span style="color:var(--ink-dim);font-size:1rem;'
                        f'font-weight:400;"> / {total}</span></span>'
                        f'<span style="margin-left:auto;color:var(--ink-dim);'
                        f'font-size:0.84rem;">{pct:.0f}%</span>'
                        f'</div>'
                        f'<div style="font-size:1.1rem;letter-spacing:0;">{bar}</div>'
                        f'</div>',
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
    rejection = proposal.get("rejection_reason") or ""
    branch_rating = proposal.get("branch_rating") or {}

    title = proposal.get("move_title", "(untitled)")
    chip_parts = []
    if branch_rating:
        branch = branch_rating.get("branch", "?")
        tier = branch_rating.get("wargame_prep_value", "?")
        chip_parts.append(f'<span class="chip tier-{tier}">{branch} · TIER {tier}</span>')
    chip_parts.append(
        f'<span class="chip surv-yes">SURVIVING</span>' if surviving
        else f'<span class="chip surv-no">REJECTED</span>'
    )
    chips_html = "".join(chip_parts)
    header_text = f"#{idx:02d}  ·  {title.upper()}  ·  PLAUS {med:.1f}  ·  WGEN {wgc}/{n_judges}"
    if rejection and not surviving:
        header_text += f"  ·  {rejection}"

    with st.expander(header_text, expanded=expanded):
        # Top chip row + bar visualizations
        plaus_bar = _bar_html(med, 5.0, width=14)
        wgen_bar = _bar_html(wgc, n_judges, width=10)
        st.markdown(
            f'<div style="margin-bottom:0.6rem;">{chips_html}</div>'
            f'<div class="leader"><span class="l-key">PLAUSIBILITY</span>'
            f'<span class="l-fill"></span><span class="l-val">{plaus_bar}  {med:.1f} / 5.0</span></div>'
            f'<div class="leader"><span class="l-key">WOULD-HAVE-GENERATED</span>'
            f'<span class="l-fill"></span><span class="l-val">{wgen_bar}  {wgc} / {n_judges}</span></div>',
            unsafe_allow_html=True,
        )

        if branch_rating:
            branch = branch_rating.get("branch", "?")
            tier = branch_rating.get("wargame_prep_value", "?")
            rows_html = []
            for label, key in [
                ("ASSUMPTION IT BREAKS", "assumption_it_breaks"),
                ("CELL TO RUN IT AGAINST", "cell_to_run_it_against"),
                ("QUESTION FOR PLAYERS", "next_question_for_players"),
                ("BRANCH CONCEPT STRESSED", "nearest_branch_concept_to_check"),
                ("WHERE IT OVERSTATES", "where_it_overstates"),
                ("CURATOR'S RATIONALE", "rationale"),
            ]:
                val = (branch_rating.get(key) or "").strip()
                if val:
                    rows_html.append(
                        f'<div class="row"><span class="k">{label}</span>'
                        f'<span class="v">{val}</span></div>'
                    )
            refer = (branch_rating.get("refer_to_other_cell") or "").strip()
            if refer:
                rows_html.append(
                    f'<div class="row"><span class="k">REFER TO OTHER CELL</span>'
                    f'<span class="v">{refer}</span></div>'
                )
            st.markdown(
                f'<div class="rating-block">'
                f'<div class="head">▣ WARGAME-PREP READ ({branch}) · TIER {tier}</div>'
                f'{"".join(rows_html)}'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f'<div class="survivor"><div class="summary">{proposal.get("summary", "")}</div></div>',
                    unsafe_allow_html=True)

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
            st.markdown(
                '<div class="leader" style="margin-top:0.8rem;">'
                '<span class="l-key">JUDGE RATINGS</span>'
                '<span class="l-fill"></span>'
                f'<span class="l-val">N={len(ratings)}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            for ji in range(len(ratings)):
                rating = int(ratings[ji])
                wg = would[ji] if ji < len(would) else False
                rationale = rationales[ji] if ji < len(rationales) else ""
                marker_chip = (
                    '<span class="chip surv-no" style="text-decoration:none;">WOULD-HAVE-GEN</span>'
                    if wg else
                    '<span class="chip surv-yes">NOVEL TO JUDGE</span>'
                )
                bar = _rating_bar(rating)
                st.markdown(
                    f'<div style="border-top:1px solid var(--rule-dim);padding:0.45rem 0;'
                    f'font-size:0.86rem;">'
                    f'<div style="display:flex;align-items:center;gap:0.7rem;flex-wrap:wrap;">'
                    f'<strong style="text-transform:uppercase;letter-spacing:0.06em;">JUDGE {ji + 1:02d}</strong>'
                    f'<span style="font-family:var(--mono);">{bar}</span>'
                    f'<span style="color:var(--ink-dim);">{rating}/5</span>'
                    f'{marker_chip}'
                    f'</div>'
                    f'<div style="margin-top:0.3rem;color:var(--ink-2);line-height:1.45;">{rationale}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if pid := proposal.get("proposal_id"):
            st.markdown(
                f'<div style="margin-top:0.6rem;font-size:0.78rem;color:var(--ink-dim);'
                f'text-transform:uppercase;letter-spacing:0.1em;">proposal_id · '
                f'<code>{pid}</code></div>',
                unsafe_allow_html=True,
            )


def render_menu_section(run: dict | None) -> None:
    menu = (run or {}).get("menu") or []
    surviving = [p for p in menu if p.get("surviving")]
    rejected = [p for p in menu if not p.get("surviving")]
    branch_curation = (run or {}).get("branch_curation") or {}

    with st.expander(f"4 — Menu ({len(surviving)} surviving / {len(menu)} candidates)", expanded=True):
        st.markdown(
            '<div style="font-size:0.85rem;color:var(--ink-dim);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem;">'
            "Strict survival: median plausibility ≥ 4 AND zero of five judges would have generated the move. "
            "These are the candidates the modal didn't reach."
            "</div>",
            unsafe_allow_html=True,
        )

        if branch_curation:
            preamble = (branch_curation.get("preamble") or "").strip()
            branch = branch_curation.get("branch", "?")
            if preamble:
                st.markdown(
                    f'<div class="curator-block">'
                    f'<div class="head">▣ Curator\'s read · {branch}</div>'
                    f'<div class="body">{preamble}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
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
    # generate_off_distribution returns (proposals, judgments) when invoked with
    # judge_fn; without judge_fn it returns (proposals, []). The "live re-run"
    # button uses the no-judge_fn path so it's fast and the user sees fresh
    # candidates without re-judging.
    result = asyncio.run(
        generate_off_distribution(
            convergence_summary=run.get("convergence") or {},
            scenario=run.get("scenario") or {},
            run_id=rerun_run_id,
        )
    )
    if isinstance(result, tuple) and len(result) == 2:
        proposals, _judgments = result
    else:
        proposals = result  # legacy single-value return shape, just in case
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


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PAGE_ICON_PATH = _REPO_ROOT / "src" / "public" / "cube.png"


def main() -> None:
    icon = str(_PAGE_ICON_PATH) if _PAGE_ICON_PATH.exists() else None
    st.set_page_config(
        page_title="Adversarial-Distribution Red Team",
        page_icon=icon,
        layout="wide",
    )
    st.markdown(INSTRUMENT_CSS, unsafe_allow_html=True)

    run_id, run = render_run_picker()

    render_header(run)
    render_scenario_section(run)
    render_modal_ensemble_section(run)
    render_convergence_section(run)
    render_signal_panel(run)
    render_menu_section(run)
    render_audit_section(run)


if __name__ == "__main__":
    main()
