# Adversarial-Distribution Red Team

**Track:** Wargaming · **Location:** Boston · **Event:** SCSP Hackathon 2026

A Red-team tool that uses an ensemble of LLMs as a *mirror of the modal* to surface adversary moves that are plausible but **off-distribution** — the moves a smart-but-average AI red team doesn't think of. The output is a menu of hypotheses for a human red team to evaluate. **Not a forecast. Not a replacement for human judgment.**

## What's different

1. **Adversarial-distribution generation.** The system explicitly searches the gap between *plausible* and *predictable* by using ensemble convergence as a map of what *not* to propose.
2. **Persistent generative-agent memory.** The Convergence Cartographer, Off-Distribution Generator, and Judge Pool are implemented as generative agents in the [Park et al. (2023)](https://arxiv.org/abs/2304.03442) sense — full memory stream with recency / importance / relevance retrieval and periodic reflection. The system gets sharper across runs.
3. **Cross-family ensemble.** The modal stage runs Claude and GPT side by side. Convergence between families is more meaningful than convergence within one.
4. **Full audit trail.** Every LLM call, parsed output, and judge rationale is logged at the decision level. A reviewer can reproduce a run from its `run_id`.

## How to run

```bash
uv sync
cp .env.example .env  # add ANTHROPIC_API_KEY, OPENAI_API_KEY
uv run python -m src.doctrine.index --validate   # validate the curated passage corpus
uv run streamlit run src/ui/streamlit_app.py
```

Source PDFs in `data/doctrine/raw/` are gitignored; the curated markdown corpus they're distilled into lives in `data/doctrine/passages/` (tracked) and is what the pipeline actually reads. Schema in `data/doctrine/passages/SCHEMA.md`.

## Datasets and APIs

- Joint Chiefs Doctrine Library — Joint Publication 3-0 (Joint Operations), Joint Publication 5-0 (Joint Planning)
- CSIS open-access analysis — PLA Taiwan operational concepts; Iran/Hezbollah/Houthi dynamics
- Anthropic API (Claude Sonnet 4.6, Claude Opus 4.7)
- OpenAI API (GPT-4-class)

## Limitations

This system inherits known failure modes of generative-agent architectures (Park et al. 2023, §6.3): memory-retrieval failures, hallucinated embellishment, and instruction-tuning-induced over-cooperation. Beyond those:

- **Outputs are hypotheses, not predictions.** Median-plausibility ≥ 3 from a five-judge LLM panel is a low bar by design — the filter is "non-modal AND not obviously implausible," not "likely to occur."
- **Convergence within an ensemble is a property of the ensemble, not of the world.** A move the ensemble fails to generate may be off-distribution for the models, off-distribution for the doctrine corpus, or off-distribution for reality. The system cannot distinguish these.
- **Doctrine corpus is open-source-only.** Real adversary planning draws on classified analysis the system has never seen. Treat the doctrine grounding as a coherence anchor, not as ground truth about adversary intent.
- **Judge calibration is rough.** Five LLM judges are not a panel of subject-matter experts. The "would you have generated this?" check is a proxy for novelty, not a measure of operational realism.
- **No live OPSEC review.** Every move on the menu is fictional and constructed from open sources. Use accordingly.

The system tells you what it is, every time. That's the discipline AI red-teaming needs.

## License

See `LICENSE`.
