"""Streamlit demo UI — replays a pre-computed run with full audit trail.

See PROJECT_SPEC.md §13. Implemented in Tier 2 on `feature/ui`.
"""

from __future__ import annotations

import streamlit as st


def main() -> None:
    st.set_page_config(page_title="Adversarial-Distribution Red Team", layout="wide")
    st.title("Adversarial-Distribution Red Team")
    st.caption("SCSP Hackathon 2026 · Wargaming track · Boston")
    st.warning("UI scaffold only — Tier 2 builds the demo flow on `feature/ui`.")


if __name__ == "__main__":
    main()
