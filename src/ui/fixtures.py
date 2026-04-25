"""Mock data fixtures for the Tier 1 Streamlit shell.

Every fixture below is shaped like the eventual schema so that Tier 2 can
swap mocks for reads from `data/runs/{run_id}/*.json` (and SQLite tables
for the audit section) with minimal UI churn.

Tone note (per RA-5 / PROJECT_SPEC.md §2): the mock content uses Wong's
register — candidate moves, hypotheses, off-distribution, audit — and
avoids forecast / prediction language. The cross-run reflection in
`MOCK_CONVERGENCE["cross_run_observations"]` is the line PROJECT_SPEC.md
§13.2 calls "the moment" of the demo.
"""

from __future__ import annotations

# TIER 2: replace this with a real run_id read from data/runs/.
MOCK_RUN_ID = "run_2026-04-25T09-12-04Z_taiwan_strait_spring_2028"


# TIER 2: replace with read from data/runs/{run_id}/modal_moves.json,
# joined against `modal_moves` rows in memory.db for provider/model/temp.
MOCK_MODAL_MOVES: list[dict] = [
    {
        "instance_idx": 0,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.9,
        "move_title": "Quarantine declaration with customs inspection",
        "summary": (
            "PLAN announces a maritime customs inspection regime around "
            "Taiwan's principal ports; PLA Coast Guard boards inbound "
            "merchants while PLAN holds outside the contiguous zone. "
            "Calibrated below the kinetic threshold to test allied "
            "cohesion before any amphibious commitment."
        ),
        "doctrine_cited": ["jp3-0-phasing", "pla-quarantine-ops", "jp5-0-coa-screening"],
        "cluster": 0,
        "xy": [-1.85, 0.42],
    },
    {
        "instance_idx": 1,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.85,
        "move_title": "PLARF conventional missile demonstration",
        "summary": (
            "Salvo of conventional SRBMs into closure boxes east and "
            "north of Taiwan, escalating the August 2022 template. "
            "Intent: shock allied decision cycles, force CSG repositioning, "
            "demonstrate A2/AD reach without crossing US red lines."
        ),
        "doctrine_cited": ["jp3-0-phasing", "pla-rocket-force-doctrine"],
        "cluster": 1,
        "xy": [1.92, 0.18],
    },
    {
        "instance_idx": 2,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 1.0,
        "move_title": "Joint Sword-style encirclement exercise extended into open-ended posture",
        "summary": (
            "Convert announced exercise window into indefinite encirclement "
            "posture; PLAN/PLAAF maintain saturation patrols inside the "
            "median line. Intent: normalize PLA presence inside Taiwan's "
            "claimed operational space without a discrete escalation event."
        ),
        "doctrine_cited": ["jp3-0-operational-design", "pla-quarantine-ops"],
        "cluster": 0,
        "xy": [-1.62, 0.71],
    },
    {
        "instance_idx": 3,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.95,
        "move_title": "Cyber and undersea-cable interdiction package",
        "summary": (
            "Coordinated PLASSF cyber operations against Taiwan financial "
            "infrastructure paired with cable-cutting against the Matsu "
            "and trans-Pacific cables. Intent: degrade civilian governance "
            "tempo and isolate the island below the kinetic threshold."
        ),
        "doctrine_cited": ["jp3-0-systems-perspective", "pla-strategic-support"],
        "cluster": 2,
        "xy": [0.18, -1.74],
    },
    {
        "instance_idx": 4,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.9,
        "move_title": "Maritime quarantine framed as anti-smuggling enforcement",
        "summary": (
            "PRC declares a domestic-law anti-smuggling regime applied to "
            "Taiwan-bound shipping; PLA Coast Guard executes selective "
            "boardings. Designed to fracture allied legal framing of the "
            "action and slow third-party convoy proposals."
        ),
        "doctrine_cited": ["jp5-0-coa-screening", "pla-legal-warfare"],
        "cluster": 0,
        "xy": [-2.05, 0.05],
    },
    {
        "instance_idx": 5,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.85,
        "move_title": "Targeted PLARF salvo against Taiwan air-defense sites",
        "summary": (
            "Limited conventional missile strike against fixed Patriot and "
            "Sky Bow sites on Taiwan's west coast; explicit messaging that "
            "US bases were not targeted. Intent: degrade Blue IADS while "
            "managing the US escalation calculus."
        ),
        "doctrine_cited": ["jp3-0-phasing", "pla-rocket-force-doctrine"],
        "cluster": 1,
        "xy": [2.21, -0.04],
    },
    {
        "instance_idx": 6,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 1.0,
        "move_title": "Civilian RoRo mobilization under disaster-relief pretext",
        "summary": (
            "PRC orders civilian RoRo fleet to muster in Fujian ports under "
            "an announced typhoon-season humanitarian readiness exercise. "
            "Intent: pre-position amphibious lift while preserving "
            "ambiguity about intent and complicating Blue indications and "
            "warnings."
        ),
        "doctrine_cited": ["jp5-0-branches-sequels", "pla-civilian-mobilization"],
        "cluster": 1,
        "xy": [1.55, 0.92],
    },
    {
        "instance_idx": 7,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.9,
        "move_title": "Air and naval blockade with declared exclusion zone",
        "summary": (
            "Announce a maritime and air exclusion zone around Taiwan; "
            "PLAN/PLAAF enforce with intercept and divert. Intent: present "
            "Blue with the binary choice of running the blockade or "
            "negotiating, on PRC tempo."
        ),
        "doctrine_cited": ["jp3-0-phasing", "pla-blockade-ops"],
        "cluster": 0,
        "xy": [-1.40, -0.18],
    },
]


# TIER 2: replace with read from data/runs/{run_id}/convergence.md
# (parsed) plus the Cartographer's reflection memories pulled from
# agent_memory where memory_type='reflection' and agent_id='convergence_cartographer'.
MOCK_CONVERGENCE: dict = {
    "cluster_labels": {
        0: "Quarantine / sub-kinetic coercion",
        1: "Visible kinetic demonstration",
        2: "Cyber and infrastructure interdiction",
    },
    "convergence_summary": (
        "Eight modal candidates resolve into three families: a quarantine / "
        "sub-kinetic coercion cluster (4 moves), a visible kinetic "
        "demonstration cluster (3 moves) anchored on PLARF salvos and "
        "civilian-lift mobilization, and a single cyber/cable cluster. "
        "Both Claude and GPT instances populate the quarantine and kinetic "
        "clusters; the cyber cluster is populated by a single Claude "
        "instance, suggesting it sits near the edge of the modal."
    ),
    "notable_absences": [
        "No move targets Taiwan's electoral or referendum machinery directly, "
        "despite the scenario placing the crisis inside Taiwan's electoral "
        "cycle.",
        "No move uses third-country financial leverage (e.g., RMB-settled "
        "energy contracts or sanctions on Taiwan-linked semiconductor "
        "supply chains) as the opening instrument.",
        "No move sequences a deniable maritime accident (collision, "
        "fishing-fleet incident) as the trigger for declared escalation.",
        "No move treats the first 72 hours as a window for information-"
        "operations preparation rather than visible posture change.",
    ],
    "cross_run_observations": (
        "Quarantine-as-opening-move appeared in 4 of the last 5 PLA Taiwan "
        "runs across both model families. Kinetic-demonstration packages "
        "appeared in all 5. Cable-cutting appeared in 3 of 5 but never as "
        "the primary instrument. The pattern is stable across scenario "
        "variants and decision horizons — read as a recurring ensemble-"
        "wide tendency, not a feature of this scenario."
    ),
}


# TIER 2: replace with read from data/runs/{run_id}/menu.md
# (parsed) joined against `off_dist_proposals` and `judgments` rows.
MOCK_MENU: list[dict] = [
    {
        "proposal_id": "od_001",
        "move_title": "Election-week disinformation cascade synchronized to a Taiwan referendum window",
        "summary": (
            "PRC times a multi-channel disinformation operation against "
            "Taiwan's referendum infrastructure during the 14-day pre-poll "
            "window the modal cluster ignored. Combines deepfaked Central "
            "Election Commission notices, coordinated inauthentic behavior "
            "across LINE/Threads, and selective leaks of authentic "
            "compromised material from Taiwanese party servers. Stated "
            "objective is process delegitimation, not poll outcome."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal candidates treat the electoral cycle as scenery. This "
            "treats the electoral machinery as the primary terrain."
        ),
        "judge_ratings": [4, 4, 5, 3, 4],  # plausibility 1-5
        "would_have_generated": [False, False, False, True, False],
        "rationales": [
            "Plausible and well-targeted to the scenario's stated electoral "
            "context. The 14-day window is concrete enough to wargame against.",
            "Realistic in scope. The choice to leak authentic material rather "
            "than fabricate it tracks recent PRC IO tradecraft.",
            "Strong. Hits a gap the modal genuinely missed and is operationally "
            "specific — channel mix, target type, success criterion.",
            "I would have generated something in this space because the "
            "scenario flags the electoral cycle. The specificity here is "
            "above what I would have produced, though.",
            "Plausible. Worth pairing with a quarantine variant to wargame "
            "the joint effect on Taiwanese decision tempo.",
        ],
        "median_plausibility": 4,
        "would_have_generated_count": 1,
        "surviving": True,
    },
    {
        "proposal_id": "od_002",
        "move_title": "Deniable bulk-carrier collision in the Taiwan Strait as escalation trigger",
        "summary": (
            "PRC-linked maritime militia stages a collision between a "
            "PRC-flagged bulk carrier and a Taiwanese-flagged civilian "
            "vessel in the median-line area, then uses the resulting loss "
            "of life as the trigger for an announced PLA Coast Guard "
            "investigation regime that functions as a quarantine in legal "
            "drag. Sequencing is the move; the quarantine itself is "
            "modal."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal quarantine candidates begin with a declaration. This "
            "manufactures the casus belli first and lets the declaration "
            "ride on grief."
        ),
        "judge_ratings": [3, 4, 3, 4, 3],
        "would_have_generated": [False, False, True, False, False],
        "rationales": [
            "Plausible. Maritime-militia tradecraft is well-attested. The "
            "deniability claim is weaker than the move assumes.",
            "Operationally crisp. The legal-drag framing is the strongest "
            "element.",
            "I would have generated the collision angle separately, though "
            "I had not connected it to the quarantine sequencing.",
            "Plausible if PRC accepts the attribution risk. Worth scoring "
            "against PRC's recent pattern of denying maritime-militia control.",
            "Acceptable plausibility. The move's value is in surfacing the "
            "sequencing question, not the specific collision device.",
        ],
        "median_plausibility": 3,
        "would_have_generated_count": 1,
        "surviving": True,
    },
    {
        "proposal_id": "od_003",
        "move_title": "Coordinated semiconductor-supply-chain sanctions framed as compliance enforcement",
        "summary": (
            "PRC announces enforcement of existing dual-use export controls "
            "against named Taiwanese semiconductor firms operating in "
            "Mainland-controlled jurisdictions, paired with administrative "
            "freezes on cross-strait financial settlement. Intent is to "
            "convert Taiwan's industrial leverage into a hostage rather "
            "than confront it militarily."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal candidates do not use Taiwan's industrial position as "
            "the opening instrument; they treat it as a downstream "
            "consideration."
        ),
        "judge_ratings": [4, 3, 4, 3, 4],
        "would_have_generated": [False, True, False, False, False],
        "rationales": [
            "Plausible. PRC has the legal apparatus in place. The sequencing "
            "matters more than the policy itself.",
            "I would have generated something in the financial/industrial "
            "space, though not with the compliance-enforcement framing.",
            "Strong on operational specificity. The administrative-freeze "
            "device is the part that's most distinctive from prior modal "
            "outputs.",
            "Plausible but slow. Decision horizon is 30 days; this move's "
            "effects accrue over months.",
            "Worth pairing with the disinformation move for joint effect on "
            "Taiwanese governance tempo.",
        ],
        "median_plausibility": 4,
        "would_have_generated_count": 1,
        "surviving": True,
    },
    {
        "proposal_id": "od_004",
        "move_title": "Hold posture and message restraint while pre-positioning",
        "summary": (
            "PRC publicly de-escalates routine PLA exercise tempo for the "
            "first 14 days of the crisis window while quietly accelerating "
            "civilian-lift mobilization and PLARF readiness changes that "
            "are not externally observable. The visible move is the "
            "absence of a visible move."
        ),
        "which_convergence_pattern_it_breaks": (
            "Every modal candidate is a visible posture change. This "
            "candidate is the opposite of a visible posture change."
        ),
        "judge_ratings": [3, 2, 3, 2, 3],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Plausible in the abstract. The move is hard to wargame because "
            "it routes around the indications-and-warnings apparatus.",
            "Less plausible than presented. Domestic political pressure on "
            "PRC leadership argues against visible restraint.",
            "Acceptable. The value is in forcing the Blue team to consider "
            "what 'no signal' would mean.",
            "I score this lower on plausibility but high on usefulness as a "
            "wargaming prompt.",
            "Plausible enough to include. Surfaces the Blue assumption that "
            "PRC tempo will be observable.",
        ],
        "median_plausibility": 3,
        "would_have_generated_count": 0,
        "surviving": True,
    },
    # ── Rejected candidates ─────────────────────────────────────────
    {
        "proposal_id": "od_005",
        "move_title": "Tactical nuclear demonstration over uninhabited Pacific waters",
        "summary": (
            "PLA Rocket Force conducts a low-yield demonstration "
            "detonation in international waters east of Taiwan as a "
            "coercive signal."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal candidates stay below the kinetic threshold or use "
            "conventional kinetics; this proposes a nuclear signal."
        ),
        "judge_ratings": [1, 1, 2, 1, 2],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Implausible. PRC nuclear doctrine and political constraints "
            "make this a non-starter at this rung of the ladder.",
            "Rejected. The escalation calculus is wrong by orders of magnitude.",
            "Generative as a stress-test, but not as a candidate move.",
            "Implausible at the operational decision-horizon being modeled.",
            "Useful only as a boundary marker on the ladder; not a candidate.",
        ],
        "median_plausibility": 1,
        "would_have_generated_count": 0,
        "surviving": False,
        "rejection_reason": "PLAUS<3 (median 1.0)",
    },
    {
        "proposal_id": "od_006",
        "move_title": "Cyberattack against TSMC fabrication systems",
        "summary": (
            "PLASSF executes a destructive cyber operation against TSMC "
            "production lines as the opening blow of the campaign."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal cyber candidates target Taiwanese governance and cable "
            "infrastructure; this proposes industrial sabotage."
        ),
        "judge_ratings": [4, 3, 4, 4, 3],
        "would_have_generated": [True, True, True, False, True],
        "rationales": [
            "I would have generated this; it is the canonical industrial-"
            "leverage move and well-trodden in the literature.",
            "Plausible but not novel; already saturating the analytic "
            "discourse.",
            "Standard. I would have generated it as a baseline option.",
            "Plausible and concrete; barely escapes the modal frame.",
            "Modal. The interesting question is downstream — what comes after.",
        ],
        "median_plausibility": 4,
        "would_have_generated_count": 4,
        "surviving": False,
        "rejection_reason": "WGEN≥3 (4/5 modal)",
    },
    {
        "proposal_id": "od_007",
        "move_title": "Diplomatic démarche through ASEAN as opening move",
        "summary": (
            "PRC opens with an ASEAN-fronted diplomatic initiative offering "
            "off-ramps in exchange for Taiwanese political concessions."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal candidates are operational; this is purely diplomatic."
        ),
        "judge_ratings": [3, 4, 3, 3, 3],
        "would_have_generated": [True, True, False, True, True],
        "rationales": [
            "Plausible and would generate; ASEAN-routed messaging is well "
            "in the modal repertoire.",
            "Standard diplomatic-track option. Modal.",
            "Slight novelty in the off-ramp framing, but not enough.",
            "I would have generated this as a baseline diplomatic posture.",
            "Modal. Useful only paired with operational moves.",
        ],
        "median_plausibility": 3,
        "would_have_generated_count": 4,
        "surviving": False,
        "rejection_reason": "WGEN≥3 (4/5 modal)",
    },
    {
        "proposal_id": "od_008",
        "move_title": "Direct PLAAF attack on Andersen AFB Guam in opening 24h",
        "summary": (
            "PLAAF conducts a saturation cruise- and ballistic-missile "
            "strike on Andersen AFB in the opening 24 hours."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal candidates avoid striking US territory in the opening; "
            "this proposes immediate escalation against a US base."
        ),
        "judge_ratings": [2, 1, 2, 2, 2],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Implausible at the opening. Crosses every reasonable PRC "
            "escalation threshold and triggers the alliance.",
            "Rejected. Wrong against PRC's stated goal of avoiding direct "
            "US confrontation.",
            "The move ignores the explicit Red constraint of avoiding "
            "sustained kinetic conflict with US forces.",
            "Implausible as an opener. Plausible later in the ladder, "
            "conditional on Blue moves.",
            "Worth surfacing as a stress-test, not as a candidate.",
        ],
        "median_plausibility": 2,
        "would_have_generated_count": 0,
        "surviving": False,
        "rejection_reason": "PLAUS<3 (median 2.0)",
    },
    {
        "proposal_id": "od_009",
        "move_title": "Standard PLARF salvo against fixed Taiwan air-defense sites",
        "summary": (
            "PLARF executes a calibrated conventional missile strike on "
            "Patriot and Sky Bow batteries on Taiwan's west coast."
        ),
        "which_convergence_pattern_it_breaks": (
            "(none — this is in-cluster with modal instance #5)."
        ),
        "judge_ratings": [4, 4, 3, 4, 4],
        "would_have_generated": [True, True, True, True, False],
        "rationales": [
            "I would have generated this; it is essentially modal #5.",
            "Modal. Generated by every standard playbook.",
            "Plausible and would generate. No off-distribution content.",
            "Modal. The judge pool will not learn from this candidate.",
            "Slight novelty in the precise sequencing, but otherwise modal.",
        ],
        "median_plausibility": 4,
        "would_have_generated_count": 4,
        "surviving": False,
        "rejection_reason": "WGEN≥3 (4/5 modal)",
    },
    {
        "proposal_id": "od_010",
        "move_title": "Stage a Taiwanese-flag false-flag attack on Mainland infrastructure",
        "summary": (
            "PRC manufactures a false-flag operation in which apparent "
            "Taiwanese-aligned actors attack a Mainland petrochemical "
            "facility, providing a casus belli."
        ),
        "which_convergence_pattern_it_breaks": (
            "Modal candidates accept the scenario's stated trigger; this "
            "manufactures a different one."
        ),
        "judge_ratings": [2, 2, 3, 2, 1],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Implausible at this scale; attribution risk is severe and the "
            "PRC track record argues against this device.",
            "Plausible only if Taiwanese intelligence is implausibly weak; "
            "rejected on that ground.",
            "Generative as a frame, but the operational details are weak.",
            "Implausible. Cost-benefit ratio is wrong for PRC.",
            "Rejected. The move is a literary device more than an OPLAN.",
        ],
        "median_plausibility": 2,
        "would_have_generated_count": 0,
        "surviving": False,
        "rejection_reason": "PLAUS<3 (median 2.0)",
    },
]


# TIER 2: replace with read from data/runs/{run_id}/manifest.json.
MOCK_MANIFEST: dict = {
    "run_id": MOCK_RUN_ID,
    "scenario_id": "taiwan_strait_spring_2028",
    "started_at": "2026-04-25T09:12:04Z",
    "completed_at": "2026-04-25T09:21:38Z",
    "config": {
        "modal_n": 8,
        "modal_split": {"anthropic": 4, "openai": 4},
        "judge_n": 5,
        "judge_split": {"anthropic": 3, "openai": 2},
        "off_distribution_k": 10,
        "survival_thresholds": {
            "median_plausibility": 3,
            "would_have_generated_max": 2,
        },
    },
    "prompt_versions": {
        "modal_red.md": "b3e1f2d4a8c0",
        "convergence_summary.md": "9c4a7e1b22fa",
        "off_distribution.md": "417dca0ee9b8",
        "judge_plausibility.md": "5fa10c39bb44",
        "judge_off_dist_check.md": "08bc4d1af7e2",
        "reflection_questions.md": "ccf2d9871061",
        "reflection_insights.md": "2a90e3148a73",
        "importance_score.md": "11ee4d6b9caa",
    },
    "totals": {
        "llm_calls": 71,
        "input_tokens": 58_234,
        "output_tokens": 17_902,
        "cost_usd": 0.84,
    },
    "artifacts": [
        "manifest.json",
        "modal_moves.json",
        "convergence.md",
        "candidates.json",
        "judgments.json",
        "menu.md",
    ],
}


# TIER 2: replace with a paginated query against the `llm_calls` table in
# data/memory.db filtered by run_id. The shape below matches that schema.
MOCK_LLM_CALLS: list[dict] = [
    {
        "call_id": "c_0001",
        "stage": "modal_ensemble",
        "agent_id": None,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.9,
        "prompt_version": "b3e1f2d4a8c0",
        "input_tokens": 4123,
        "output_tokens": 612,
        "latency_ms": 7821,
        "cost_usd": 0.0291,
    },
    {
        "call_id": "c_0002",
        "stage": "modal_ensemble",
        "agent_id": None,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.85,
        "prompt_version": "b3e1f2d4a8c0",
        "input_tokens": 4123,
        "output_tokens": 588,
        "latency_ms": 7104,
        "cost_usd": 0.0286,
    },
    {
        "call_id": "c_0009",
        "stage": "modal_ensemble",
        "agent_id": None,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.9,
        "prompt_version": "b3e1f2d4a8c0",
        "input_tokens": 4140,
        "output_tokens": 701,
        "latency_ms": 6240,
        "cost_usd": 0.0312,
    },
    {
        "call_id": "c_0017",
        "stage": "convergence_cartographer",
        "agent_id": "convergence_cartographer",
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "temperature": 0.4,
        "prompt_version": "9c4a7e1b22fa",
        "input_tokens": 6022,
        "output_tokens": 1105,
        "latency_ms": 11_402,
        "cost_usd": 0.1142,
    },
    {
        "call_id": "c_0018",
        "stage": "off_distribution_generator",
        "agent_id": "off_distribution_generator",
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "temperature": 1.0,
        "prompt_version": "417dca0ee9b8",
        "input_tokens": 5180,
        "output_tokens": 2402,
        "latency_ms": 18_244,
        "cost_usd": 0.1640,
    },
    {
        "call_id": "c_0028",
        "stage": "judge_pool",
        "agent_id": "judge_a",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.3,
        "prompt_version": "5fa10c39bb44",
        "input_tokens": 1880,
        "output_tokens": 412,
        "latency_ms": 4992,
        "cost_usd": 0.0144,
    },
    {
        "call_id": "c_0029",
        "stage": "judge_pool",
        "agent_id": "judge_b",
        "provider": "openai",
        "model": "gpt-5",
        "temperature": 0.3,
        "prompt_version": "5fa10c39bb44",
        "input_tokens": 1880,
        "output_tokens": 388,
        "latency_ms": 4214,
        "cost_usd": 0.0152,
    },
]
