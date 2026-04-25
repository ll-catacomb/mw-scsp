"""Mock data fixtures — fallback when artifacts are missing on disk.

Tier 2 promotes `src/ui/run_loader.py` to be the primary data source. These
fixtures are kept as a drop-in fallback for development sessions where not
every pipeline stage has produced an artifact yet (e.g. before Stage 4 / 5
are wired up). Shapes mirror:

- modal moves → `src/pipeline/schemas.py::ModalMoveSchema` (with actions /
  intended_effect / risks_red_accepts / move_id added in Tier 2).
- convergence → `src/agents/convergence_cartographer.py::ConvergenceNarration`
  (clusters list with cluster_id / theme / member_move_ids / representative_actions).
- menu → projection of `off_dist_proposals` + `judgments` SQLite tables.
- manifest → `src/llm/manifest.py::write_manifest` plus the loader-derived
  `totals` dict synthesized from llm_calls rows.

Tone note: the mock content uses Wong's register — candidate moves,
hypotheses, off-distribution, audit — and avoids forecast/prediction language.
The cross-run observation in `MOCK_CONVERGENCE["cross_run_observations"][0]`
is the line PROJECT_SPEC.md §13.2 calls "the moment" of the demo.
"""

from __future__ import annotations

# Used only when the canonical run on disk has no manifest. Format mirrors
# `src/pipeline/orchestrator.py`'s uuid4 default.
MOCK_RUN_ID = "00000000-mock-fixt-ures-000000000000"


# Mirrors ModalMoveSchema + the metadata orchestrator.py adds before persisting
# (move_id, instance_idx, provider, model, temperature). xy/cluster keys are
# UI-only artifacts kept on the mocks so the legacy plot in streamlit_proto
# still has coordinates to render — the canonical streamlit_app.py uses the
# Cartographer's structured `clusters` list instead.
MOCK_MODAL_MOVES: list[dict] = [
    {
        "move_id": "mock-mv-0001",
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
        "actions": [
            {
                "actor": "PRC State Council, Ministry of Transport, China Coast Guard",
                "action": "Announce a seven-day customs and safety inspection regime for Taiwan-bound shipping under domestic-law authority",
                "target": "Approaches to Kaohsiung, Taichung, Keelung",
                "timeline_days": 1,
                "purpose": "Frame coercion as law enforcement; complicate Blue authorization to escalate kinetically",
            },
            {
                "actor": "China Coast Guard Fujian formations + PAFMM",
                "action": "Selective hailing, shadowing, and boarding of Taiwan-bound merchants while avoiding lethal force",
                "target": "Taiwan-bound commercial traffic and ROC Coast Guard patrols",
                "timeline_days": 2,
                "purpose": "Impose maritime friction without crossing armed-conflict threshold",
            },
        ],
        "intended_effect": "Force Taipei into a phase-transition dilemma: accept a coercive new baseline or escalate first against a law-enforcement-framed regime, while stressing alliance cohesion.",
        "risks_red_accepts": [
            "US or allies may treat inspections as a blockade and respond with escort operations",
            "A boarding incident could escalate uncontrollably",
        ],
        "doctrine_cited": ["jp3-0-phasing", "pla-quarantine-ops", "jp5-0-coa-screening"],
        "cluster": 0,
        "xy": [-1.85, 0.42],
    },
    {
        "move_id": "mock-mv-0002",
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
        "actions": [
            {
                "actor": "PLA Rocket Force conventional SRBM brigades",
                "action": "Live-fire SRBM salvo into announced closure boxes east and north of Taiwan",
                "target": "Closure boxes in international waters east and north of Taiwan",
                "timeline_days": 2,
                "purpose": "Shock decision cycles and force CSG repositioning without striking US territory",
            }
        ],
        "intended_effect": "Coerce US to delay forward CSG movement while demonstrating PLARF reach.",
        "risks_red_accepts": [
            "Closure-box overflight risks on civilian aviation",
            "Allied unification on red-line response",
        ],
        "doctrine_cited": ["jp3-0-phasing", "pla-rocket-force-doctrine"],
        "cluster": 1,
        "xy": [1.92, 0.18],
    },
    {
        "move_id": "mock-mv-0003",
        "instance_idx": 2,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 1.0,
        "move_title": "Joint Sword-style encirclement extended into open-ended posture",
        "summary": (
            "Convert announced exercise window into indefinite encirclement "
            "posture; PLAN/PLAAF maintain saturation patrols inside the "
            "median line."
        ),
        "actions": [
            {
                "actor": "PLAAF Eastern Theater + PLAN East Sea Fleet",
                "action": "Maintain saturation sortie tempo inside the median line past the announced exercise window with no scheduled end date",
                "target": "Taiwan ADIZ and median-line operating areas",
                "timeline_days": 7,
                "purpose": "Normalize PLA presence inside Taiwan operational space without a discrete escalation event",
            }
        ],
        "intended_effect": "Make encirclement the new baseline without giving Blue a discrete trigger to anchor a response on.",
        "risks_red_accepts": [
            "Sortie attrition costs to PLA airframes and crews",
            "ROCAF accidental engagement under sustained pressure",
        ],
        "doctrine_cited": ["jp3-0-operational-design", "pla-quarantine-ops"],
        "cluster": 0,
        "xy": [-1.62, 0.71],
    },
    {
        "move_id": "mock-mv-0004",
        "instance_idx": 3,
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.95,
        "move_title": "Cyber and undersea-cable interdiction package",
        "summary": (
            "Coordinated PLASSF cyber operations against Taiwan financial "
            "infrastructure paired with cable-cutting against Matsu and "
            "trans-Pacific cables. Intent: degrade civilian governance "
            "tempo and isolate the island below the kinetic threshold."
        ),
        "actions": [
            {
                "actor": "PLA Strategic Support Force cyber + maritime militia",
                "action": "Coordinated cyber intrusion against Taiwan financial settlement infrastructure paired with anchor-drag cable severance",
                "target": "Taiwan financial system + Matsu and trans-Pacific cables",
                "timeline_days": 3,
                "purpose": "Degrade civilian governance tempo and isolate the island below the kinetic threshold",
            }
        ],
        "intended_effect": "Compress Taipei's decision tempo while preserving deniability on the maritime side.",
        "risks_red_accepts": [
            "Attribution from forensic analysis",
            "Spillover to cables PRC also depends on",
        ],
        "doctrine_cited": ["jp3-0-systems-perspective", "pla-strategic-support"],
        "cluster": 2,
        "xy": [0.18, -1.74],
    },
    {
        "move_id": "mock-mv-0005",
        "instance_idx": 4,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.9,
        "move_title": "Maritime quarantine framed as anti-smuggling enforcement",
        "summary": (
            "PRC declares a domestic-law anti-smuggling regime applied to "
            "Taiwan-bound shipping; PLA Coast Guard executes selective "
            "boardings."
        ),
        "actions": [
            {
                "actor": "PRC Ministry of Public Security, China Coast Guard",
                "action": "Declare an anti-smuggling enforcement regime under PRC domestic law and execute selective boardings of Taiwan-bound vessels",
                "target": "Taiwan-bound commercial shipping",
                "timeline_days": 2,
                "purpose": "Fracture allied legal framing of the action; slow third-party convoy proposals",
            }
        ],
        "intended_effect": "Move the dispute into legal-discursive terrain where allied military response looks disproportionate.",
        "risks_red_accepts": [
            "Allied legal counter-narratives prevail in international fora",
            "Insurance markets reroute traffic, blunting coercive pressure",
        ],
        "doctrine_cited": ["jp5-0-coa-screening", "pla-legal-warfare"],
        "cluster": 0,
        "xy": [-2.05, 0.05],
    },
    {
        "move_id": "mock-mv-0006",
        "instance_idx": 5,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.85,
        "move_title": "Targeted PLARF salvo against Taiwan air-defense sites",
        "summary": (
            "Limited conventional missile strike against fixed Patriot and "
            "Sky Bow sites on Taiwan's west coast; explicit messaging that "
            "US bases were not targeted."
        ),
        "actions": [
            {
                "actor": "PLA Rocket Force conventional brigades",
                "action": "Calibrated SRBM strike on fixed ROC Patriot and Sky Bow batteries on Taiwan's west coast with explicit non-targeting of US bases",
                "target": "Fixed ROC IADS sites on Taiwan's west coast",
                "timeline_days": 1,
                "purpose": "Degrade Blue IADS while managing US escalation calculus",
            }
        ],
        "intended_effect": "Open the air-superiority window over the strait while keeping the US escalation ladder intact.",
        "risks_red_accepts": [
            "US treats strike on Taiwan-soil targets as casus belli regardless of base targeting",
            "Mobile IADS preserves more capability than expected",
        ],
        "doctrine_cited": ["jp3-0-phasing", "pla-rocket-force-doctrine"],
        "cluster": 1,
        "xy": [2.21, -0.04],
    },
    {
        "move_id": "mock-mv-0007",
        "instance_idx": 6,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 1.0,
        "move_title": "Civilian RoRo mobilization under disaster-relief pretext",
        "summary": (
            "PRC orders civilian RoRo fleet to muster in Fujian ports under "
            "an announced typhoon-season humanitarian readiness exercise."
        ),
        "actions": [
            {
                "actor": "PRC Ministry of Transport, civilian RoRo operators",
                "action": "Order civilian RoRo fleet to muster in Fujian ports under an announced typhoon-season humanitarian readiness exercise",
                "target": "Fujian port infrastructure and PRC civilian RoRo fleet",
                "timeline_days": 5,
                "purpose": "Pre-position amphibious lift while preserving ambiguity about intent",
            }
        ],
        "intended_effect": "Compress the warning window for any follow-on amphibious option while preserving plausible deniability of intent.",
        "risks_red_accepts": [
            "Commercial satellite imagery reveals lift-readiness ambiguity",
            "RoRo crews refuse activation under hostilities",
        ],
        "doctrine_cited": ["jp5-0-branches-sequels", "pla-civilian-mobilization"],
        "cluster": 1,
        "xy": [1.55, 0.92],
    },
    {
        "move_id": "mock-mv-0008",
        "instance_idx": 7,
        "provider": "openai",
        "model": "gpt-5.5",
        "temperature": 0.9,
        "move_title": "Air and naval blockade with declared exclusion zone",
        "summary": (
            "Announce a maritime and air exclusion zone around Taiwan; "
            "PLAN/PLAAF enforce with intercept and divert."
        ),
        "actions": [
            {
                "actor": "PRC State Council, Eastern Theater Command",
                "action": "Declare a maritime and air exclusion zone around Taiwan; enforce with PLAN intercept and PLAAF divert orders",
                "target": "Maritime and air approaches to Taiwan",
                "timeline_days": 1,
                "purpose": "Force Blue into the binary of running the blockade or negotiating, on PRC tempo",
            }
        ],
        "intended_effect": "Convert the crisis into a maritime-access question on PRC's preferred legal and operational terrain.",
        "risks_red_accepts": [
            "US-led convoy operations directly challenge enforcement",
            "Civilian aviation incident accelerates international opprobrium",
        ],
        "doctrine_cited": ["jp3-0-phasing", "pla-blockade-ops"],
        "cluster": 0,
        "xy": [-1.40, -0.18],
    },
]


# Mirrors `ConvergenceNarration` (src/agents/convergence_cartographer.py).
# Keys: convergence_summary, clusters[], notable_absences[], cross_run_observations[].
MOCK_CONVERGENCE: dict = {
    "convergence_summary": (
        "Eight modal candidates resolve into three families: a quarantine / "
        "sub-kinetic coercion cluster (4 moves), a visible kinetic "
        "demonstration cluster (3 moves) anchored on PLARF salvos and "
        "civilian-lift mobilization, and a single cyber/cable cluster. "
        "Both Claude and GPT instances populate the quarantine and kinetic "
        "clusters; the cyber cluster is populated by a single Claude "
        "instance, suggesting it sits near the edge of the modal."
    ),
    "clusters": [
        {
            "cluster_id": 0,
            "theme": "Quarantine / sub-kinetic coercion",
            "member_move_ids": [
                "mock-mv-0001",
                "mock-mv-0003",
                "mock-mv-0005",
                "mock-mv-0008",
            ],
            "representative_actions": [
                "Customs-inspection regime under domestic-law authority",
                "Open-ended encirclement posture",
                "Anti-smuggling enforcement against Taiwan-bound shipping",
                "Declared maritime / air exclusion zone",
            ],
        },
        {
            "cluster_id": 1,
            "theme": "Visible kinetic demonstration",
            "member_move_ids": ["mock-mv-0002", "mock-mv-0006", "mock-mv-0007"],
            "representative_actions": [
                "PLARF salvo into closure boxes east of Taiwan",
                "Calibrated SRBM strike on Taiwan's IADS sites",
                "Civilian RoRo muster under disaster-relief pretext",
            ],
        },
        {
            "cluster_id": 2,
            "theme": "Cyber and infrastructure interdiction",
            "member_move_ids": ["mock-mv-0004"],
            "representative_actions": [
                "Coordinated cyber + cable interdiction package",
            ],
        },
    ],
    "notable_absences": [
        {
            "absence": "No move targets Taiwan's electoral or referendum machinery directly, despite the scenario placing the crisis inside Taiwan's electoral cycle.",
            "why_it_might_be_proposed": "The scenario explicitly flags an electoral-cycle backdrop; targeting the process is the highest-leverage low-kinetic option.",
            "why_the_ensemble_missed_it": "Modal training data privileges visible military posture as the canonical Red opening move; civilian-process targeting reads as off-genre.",
        },
        {
            "absence": "No move uses third-country financial leverage (e.g., RMB-settled energy contracts or sanctions on Taiwan-linked semiconductor supply chains) as the opening instrument.",
            "why_it_might_be_proposed": "Taiwan's industrial position is the most concrete leverage PRC has against US tech alliances.",
            "why_the_ensemble_missed_it": "Financial coercion is treated as a downstream consequence rather than an opening instrument in standard wargaming literature.",
        },
        {
            "absence": "No move sequences a deniable maritime accident as the trigger for declared escalation.",
            "why_it_might_be_proposed": "Maritime-militia tradecraft has well-attested precedent and the deniability device routes around the casus belli problem.",
            "why_the_ensemble_missed_it": "The ensemble defaults to declared, attributable openings — the casus-belli-manufacturing path requires actively choosing ambiguity.",
        },
        {
            "absence": "No move treats the first 72 hours as a window for information-operations preparation rather than visible posture change.",
            "why_it_might_be_proposed": "PRC IO doctrine emphasizes shaping the information environment before kinetic action.",
            "why_the_ensemble_missed_it": "Doctrinal focus on Phase 0 IO doesn't translate into Phase-I-style move proposals when the prompt asks for an opening move.",
        },
    ],
    "cross_run_observations": [
        (
            "Quarantine-as-opening-move appeared in 4 of the last 5 PLA Taiwan "
            "runs across both model families. Kinetic-demonstration packages "
            "appeared in all 5. Cable-cutting appeared in 3 of 5 but never as "
            "the primary instrument. The pattern is stable across scenario "
            "variants and decision horizons — read as a recurring ensemble-"
            "wide tendency, not a feature of this scenario."
        ),
    ],
}


# Mirrors candidates.json + judgments.json joined for UI consumption.
# Each dict's required keys: proposal_id, move_title, summary, judge_ratings,
# would_have_generated, rationales, median_plausibility,
# would_have_generated_count, surviving, which_convergence_pattern_it_breaks.
# Tier 2 additions: actions, intended_effect, risks_red_accepts.
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
        "actions": [
            {
                "actor": "PLA Strategic Support Force IO units + Ministry of State Security",
                "action": "Coordinate multi-channel deepfake + inauthentic-amplification campaign timed to the 14-day pre-poll window",
                "target": "Taiwan electorate via LINE / Threads, plus selective leaks to local media",
                "timeline_days": 14,
                "purpose": "Delegitimize the referendum process without claiming an outcome",
            },
        ],
        "intended_effect": "Hollow out trust in the electoral apparatus during the scenario's stated electoral cycle.",
        "risks_red_accepts": [
            "Attribution from authentic-material leak forensics",
            "Domestic blowback if Taiwanese institutions consolidate against external interference",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal candidates treat the electoral cycle as scenery. This "
            "treats the electoral machinery as the primary terrain."
        ),
        "judge_ratings": [4, 4, 5, 3, 4],
        "would_have_generated": [False, False, False, True, False],
        "rationales": [
            "Plausible and well-targeted to the scenario's stated electoral context.",
            "Realistic in scope. The choice to leak authentic material rather than fabricate it tracks recent PRC IO tradecraft.",
            "Strong. Hits a gap the modal genuinely missed and is operationally specific.",
            "I would have generated something in this space because the scenario flags the electoral cycle. Specificity is above what I would have produced.",
            "Plausible. Worth pairing with a quarantine variant to wargame the joint effect on Taiwanese decision tempo.",
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
            "vessel, then uses the resulting loss of life as the trigger "
            "for an announced PLA Coast Guard investigation regime that "
            "functions as a quarantine in legal drag."
        ),
        "actions": [],
        "intended_effect": "Manufacture the casus belli first; let the declaration ride on grief.",
        "risks_red_accepts": [
            "Maritime-militia attribution chain",
            "Domestic PRC backlash if civilian deaths read as engineered",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal quarantine candidates begin with a declaration. This "
            "manufactures the casus belli first and lets the declaration "
            "ride on grief."
        ),
        "judge_ratings": [3, 4, 3, 4, 3],
        "would_have_generated": [False, False, True, False, False],
        "rationales": [
            "Plausible. Maritime-militia tradecraft is well-attested. Deniability claim is weaker than the move assumes.",
            "Operationally crisp. The legal-drag framing is the strongest element.",
            "I would have generated the collision angle separately, though I had not connected it to the quarantine sequencing.",
            "Plausible if PRC accepts the attribution risk.",
            "Acceptable plausibility. The move's value is in surfacing the sequencing question.",
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
            "freezes on cross-strait financial settlement."
        ),
        "actions": [],
        "intended_effect": "Convert Taiwan's industrial leverage into a hostage rather than confront it militarily.",
        "risks_red_accepts": [
            "Effects accrue over months; decision horizon is 30 days",
            "Mainland firms dependent on TSMC supply chain absorb collateral damage",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal candidates do not use Taiwan's industrial position as "
            "the opening instrument; they treat it as a downstream "
            "consideration."
        ),
        "judge_ratings": [4, 3, 4, 3, 4],
        "would_have_generated": [False, True, False, False, False],
        "rationales": [
            "Plausible. PRC has the legal apparatus in place.",
            "I would have generated something in the financial/industrial space, though not with this framing.",
            "Strong on operational specificity. The administrative-freeze device is the part that's most distinctive.",
            "Plausible but slow. Decision horizon is 30 days; this move's effects accrue over months.",
            "Worth pairing with the disinformation move for joint effect on Taiwanese governance tempo.",
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
        "actions": [],
        "intended_effect": "Route around the indications-and-warnings apparatus by removing the indications.",
        "risks_red_accepts": [
            "Domestic political pressure on PRC leadership argues against visible restraint",
            "Restraint signal misread as concession",
        ],
        "which_convergence_pattern_it_breaks": (
            "Every modal candidate is a visible posture change. This "
            "candidate is the opposite of a visible posture change."
        ),
        "judge_ratings": [3, 2, 3, 2, 3],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Plausible in the abstract. Hard to wargame because it routes around the I&W apparatus.",
            "Less plausible than presented. Domestic political pressure argues against visible restraint.",
            "Acceptable. Value is in forcing Blue to consider what 'no signal' would mean.",
            "I score this lower on plausibility but high on usefulness as a wargaming prompt.",
            "Plausible enough to include. Surfaces the Blue assumption that PRC tempo will be observable.",
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
        "actions": [],
        "intended_effect": "Reset the escalation ladder by introducing a nuclear coercive signal.",
        "risks_red_accepts": [
            "PRC nuclear doctrine and political constraints make this a non-starter at this rung",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal candidates stay below the kinetic threshold or use "
            "conventional kinetics; this proposes a nuclear signal."
        ),
        "judge_ratings": [1, 1, 2, 1, 2],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Implausible. PRC nuclear doctrine and political constraints make this a non-starter.",
            "Rejected. Escalation calculus is wrong by orders of magnitude.",
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
        "actions": [],
        "intended_effect": "Destroy the global semiconductor leverage Taiwan provides US tech alliances.",
        "risks_red_accepts": [
            "PRC firms downstream of TSMC absorb collateral damage",
            "Industrial-attribution forensics resolve faster than expected",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal cyber candidates target Taiwanese governance and cable "
            "infrastructure; this proposes industrial sabotage."
        ),
        "judge_ratings": [4, 3, 4, 4, 3],
        "would_have_generated": [True, True, True, False, True],
        "rationales": [
            "I would have generated this; it is the canonical industrial-leverage move.",
            "Plausible but not novel; already saturating the analytic discourse.",
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
        "actions": [],
        "intended_effect": "Front-run a coercive operation with a diplomatic off-ramp that fractures coalition response.",
        "risks_red_accepts": [
            "ASEAN states decline to front the initiative",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal candidates are operational; this is purely diplomatic."
        ),
        "judge_ratings": [3, 4, 3, 3, 3],
        "would_have_generated": [True, True, False, True, True],
        "rationales": [
            "Plausible and would generate; ASEAN-routed messaging is well in the modal repertoire.",
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
        "actions": [],
        "intended_effect": "Eliminate the closest US power-projection node before US response can mobilize.",
        "risks_red_accepts": [
            "Triggers the alliance and likely terminates PRC's preferred end-state path",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal candidates avoid striking US territory in the opening; "
            "this proposes immediate escalation against a US base."
        ),
        "judge_ratings": [2, 1, 2, 2, 2],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Implausible at the opening. Crosses every reasonable PRC escalation threshold.",
            "Rejected. Wrong against PRC's stated goal of avoiding direct US confrontation.",
            "The move ignores the explicit Red constraint of avoiding sustained kinetic conflict with US forces.",
            "Implausible as an opener. Plausible later in the ladder, conditional on Blue moves.",
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
        "actions": [],
        "intended_effect": "Open the air-superiority window over the strait.",
        "risks_red_accepts": [
            "Effectively in-cluster with modal #5 — no off-distribution content",
        ],
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
        "actions": [],
        "intended_effect": "Manufacture a self-justifying casus belli on Mainland soil.",
        "risks_red_accepts": [
            "Attribution risk is severe given Taiwanese intelligence visibility",
        ],
        "which_convergence_pattern_it_breaks": (
            "Modal candidates accept the scenario's stated trigger; this "
            "manufactures a different one."
        ),
        "judge_ratings": [2, 2, 3, 2, 1],
        "would_have_generated": [False, False, False, False, False],
        "rationales": [
            "Implausible at this scale; attribution risk is severe.",
            "Plausible only if Taiwanese intelligence is implausibly weak.",
            "Generative as a frame, but operational details are weak.",
            "Implausible. Cost-benefit ratio is wrong for PRC.",
            "Rejected. The move is a literary device more than an OPLAN.",
        ],
        "median_plausibility": 2,
        "would_have_generated_count": 0,
        "surviving": False,
        "rejection_reason": "PLAUS<3 (median 2.0)",
    },
]


# Mirrors `src/llm/manifest.py::write_manifest` plus the loader-derived
# `totals` dict synthesized from llm_calls rows.
MOCK_MANIFEST: dict = {
    "run_id": MOCK_RUN_ID,
    "scenario_id": "taiwan_strait_spring_2028",
    "started_at": "2026-04-25T09:12:04Z",
    "completed_at": "2026-04-25T09:21:38Z",
    "status": "complete",
    "config": {
        "modal_claude_model": "claude-sonnet-4-6",
        "modal_gpt_model": "gpt-5.5",
        "doctrine_top_k": 6,
        "modal_ensemble_n": 8,
        "tier": 1,
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
}


# Mirrors `llm_calls` rows. The audit panel adds `system_prompt`, `user_prompt`,
# `raw_response`, `parsed_output`, and `prompt_hash` from the real DB on
# expansion; these mocks include only summary metadata.
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
        "call_id": "c_0017",
        "stage": "3_convergence",
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
        "stage": "off_distribution",
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
        "stage": "judging",
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
]
