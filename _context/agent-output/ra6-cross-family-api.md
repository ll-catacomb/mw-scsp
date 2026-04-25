# RA-6: Cross-Family API Operational Details, April 2026

*Research date: 2026-04-25. Verified against docs.anthropic.com (now `platform.claude.com`),
developers.openai.com, and the BerriAI/litellm repo.*

This brief is the implementation reference for an SCSP 2026 hackathon prototype that
ensembles Anthropic Claude and OpenAI GPT in a single wargaming/red-team pipeline.
Every LLM call in this project goes through `src/llm/wrapper.py::logged_completion()`,
which records the prompt-file git-blob hash as `prompt_version`. Code below is shaped
around that constraint.

## Quick reference table

| Provider  | Model              | Context  | Max out | $/1M in | $/1M out | RPM (T1) | ITPM (T1) | OTPM (T1) |
|-----------|--------------------|----------|---------|---------|----------|----------|-----------|-----------|
| Anthropic | claude-opus-4-7    | 1M       | 128k    | $5.00   | $25.00   | 50       | 30,000    | 8,000     |
| Anthropic | claude-sonnet-4-6  | 1M       | 64k     | $3.00   | $15.00   | 50       | 30,000    | 8,000     |
| Anthropic | claude-haiku-4-5   | 200k     | 64k     | $1.00   | $5.00    | 50       | 50,000    | 10,000    |
| OpenAI    | gpt-5.5            | 1.05M    | 128k    | $5.00   | $30.00   | ~1,000   | 500,000 (combined TPM) | (combined TPM) |
| OpenAI    | gpt-5.5-pro        | 1.05M    | 128k    | $30.00  | $180.00  | lower    | lower     | lower     |
| OpenAI    | gpt-5 (legacy)     | 400k     | 128k    | $2.50   | $15.00   | ~1,000   | 500,000   | (combined) |

Notes: Anthropic separates ITPM/OTPM; OpenAI uses a combined TPM bucket. Anthropic Tier 1
is reached after a $5 credit purchase; OpenAI Tier 1 after $5 + 7 days. The Opus and
Sonnet rate limits apply to **combined** traffic across all 4.x snapshots, so don't
expect to gain capacity by spreading requests across `opus-4-7` and `opus-4-6`.

## Anthropic Claude API

### Current models (verified at platform.claude.com/docs)

- **`claude-opus-4-7`** (alias) — most capable, agentic-coding step change. 1M context
  natively (no separate beta tier, no long-context premium). 128k max output. New
  tokenizer that can produce up to ~35% more tokens for the same English text vs
  Opus 4.6, so dollar bills can rise even though the rate card didn't.
- **`claude-sonnet-4-6`** (alias) — best speed/intelligence ratio, 1M context, 64k out.
- **`claude-haiku-4-5`** (alias) — fastest near-frontier, 200k context, 64k out. Tier-1
  ITPM is 50k (higher than Sonnet/Opus's 30k), making it the right workhorse for
  fan-out steps in the pipeline.

Snapshot strings if you need pinning: `claude-haiku-4-5-20251001`. Opus 4.7 and
Sonnet 4.6 currently expose only the floating alias.

### Pricing (per million tokens)

| Model     | Input | Output | Cache write (5m) | Cache read |
|-----------|-------|--------|------------------|------------|
| Opus 4.7  | $5.00 | $25.00 | $6.25            | $0.50      |
| Sonnet 4.6| $3.00 | $15.00 | $3.75            | $0.30      |
| Haiku 4.5 | $1.00 | $5.00  | $1.25            | $0.10      |

50% discount on the Message Batches API. US-only inference is +10%. For most models
(non-`†`), `cache_read_input_tokens` does **not** count against ITPM, so caching boosts
effective throughput.

### Rate limits — Tier 1 (verified at platform.claude.com/docs/en/api/rate-limits)

| Model class       | RPM | ITPM   | OTPM   |
|-------------------|-----|--------|--------|
| Claude Opus 4.x   | 50  | 30,000 | 8,000  |
| Claude Sonnet 4.x | 50  | 30,000 | 8,000  |
| Claude Haiku 4.5  | 50  | 50,000 | 10,000 |

Headers for backoff: `anthropic-ratelimit-input-tokens-remaining`,
`anthropic-ratelimit-output-tokens-remaining`, `anthropic-ratelimit-requests-remaining`,
`retry-after`. On 429, honour `retry-after`; on 529 (overload) start backoff at 4s, not 2s.

### Structured output

Anthropic shipped **native structured outputs** GA via `output_config.format`
(constrained decoding, not tool-use round-tripping). The old tool-use trick still works
but is no longer the recommended path. Working Python:

```python
# src/llm/anthropic_structured.py
from pydantic import BaseModel
from anthropic import AsyncAnthropic

class ThreatAssessment(BaseModel):
    severity: int          # 1-5
    confidence: float      # 0.0-1.0
    rationale: str
    suggested_action: str

client = AsyncAnthropic()

async def assess(scenario: str) -> ThreatAssessment:
    # SDK helper: parse() converts the Pydantic model to a JSON Schema,
    # sends output_config, and parses the result back into the model.
    resp = await client.messages.parse(
        model="claude-opus-4-7",
        max_tokens=2048,
        messages=[{"role": "user", "content": scenario}],
        output_format=ThreatAssessment,
    )
    return resp.parsed_output
```

If you need the raw form for LiteLLM compatibility:

```python
output_config={
    "format": {
        "type": "json_schema",
        "schema": ThreatAssessment.model_json_schema(),
    }
}
```

**Failure modes that bypass the schema**: `stop_reason: "refusal"` and
`stop_reason: "max_tokens"`. Code defensively — check `stop_reason` before treating
`parsed_output` as truth.

The legacy forced-tool-call pattern (`tool_choice={"type": "tool", "name": "..."}`,
optionally `strict: true`) still works on every 4.x model and is the recommended
fallback if `output_config` ever returns weird results in your pipeline.

### Async pattern

```python
import asyncio
from anthropic import AsyncAnthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential
from anthropic import APIStatusError, APITimeoutError, RateLimitError

client = AsyncAnthropic(timeout=120.0)
sem = asyncio.Semaphore(8)  # below T1 50 RPM with headroom for bursts

@retry(
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIStatusError)),
    wait=wait_random_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
async def call_claude(messages, model="claude-opus-4-7", **kw):
    async with sem:
        return await client.messages.create(model=model, messages=messages,
                                            max_tokens=4096, **kw)
```

`APIStatusError` is the parent for 5xx/529; if you want to be stricter, retry only
when `e.status_code in {429, 500, 502, 503, 504, 529}`.

### Refusal behaviour in research scenarios

Claude refuses by reasoning about principles rather than keyword matching, which means
**legitimate research framing works** when it is actually true. For a wargaming
red-team prototype, frontload the system prompt with concrete, verifiable framing:

> *You are assisting with a tabletop wargaming exercise for the Special Competitive
> Studies Project (SCSP) 2026 hackathon. Outputs are reviewed by a human red-team
> facilitator before any operational use. The goal is to surface failure modes and
> weak assumptions in the planning document, not to generate operational guidance.
> Stay at the level of strategic abstraction; refuse anything that requests specific
> targeting, weaponisation, or operational tradecraft details.*

This is **not a jailbreak** — it both establishes the legitimate context and invites
the model to refuse the specific things it should refuse. Anthropic's published
position: Claude will not be configured for mass surveillance of US persons or fully
autonomous lethal weapons regardless of framing, so don't waste prompt budget arguing
those edges.

## OpenAI GPT API

### Current models (verified at developers.openai.com)

OpenAI shipped **GPT-5.5** on 2026-04-23 (two days before this brief). It is the
current frontier model; GPT-5 remains available as a cheaper alternative.

- **`gpt-5.5`** — 1,050,000 context, 128k max output, structured outputs supported.
  Pricing roughly doubled from GPT-5.
- **`gpt-5.5-pro`** — same family, higher reasoning, 6x the price. Skip for hackathon.
- **`gpt-5`** — still available, ~half the price of 5.5; reasonable fallback.
- **`gpt-5-mini`** — cheap class, useful for fan-out.

[unverified] The exact dated snapshot string for GPT-5.5 (e.g. `gpt-5.5-2026-04-23`)
was not directly visible in the docs page that was reachable; use the floating alias
unless you need pinning, and confirm in your API console.

### Pricing (per million tokens)

| Model        | Input  | Cached input | Output  |
|--------------|--------|--------------|---------|
| gpt-5.5      | $5.00  | $0.50        | $30.00  |
| gpt-5.5-pro  | $30.00 | n/a          | $180.00 |
| gpt-5        | $2.50  | $0.25        | $15.00  |

Batch and Flex pricing: 50% off standard. Priority: 2.5x. Regional residency: +10%.

### Rate limits — Tier 1

`gpt-5` Tier 1: ~1,000 RPM and 500,000 TPM (raised from 30k TPM in Sep 2025).
[unverified] GPT-5.5 Tier 1 limits are not yet broken out in the public docs page;
the safe assumption is they inherit GPT-5's tier structure. The OpenAI dashboard at
`platform.openai.com/settings/organization/limits` is authoritative.

Headers: `x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`,
`x-ratelimit-reset-requests`, `x-ratelimit-limit-tokens`, `x-ratelimit-remaining-tokens`,
`x-ratelimit-reset-tokens`. Plus `retry-after` on 429.

### Structured output

OpenAI's `chat.completions.parse()` (and the newer `responses.parse()`) take a Pydantic
model, generate the JSON Schema, and return a typed object:

```python
# src/llm/openai_structured.py
from pydantic import BaseModel
from openai import AsyncOpenAI

class ThreatAssessment(BaseModel):
    severity: int
    confidence: float
    rationale: str
    suggested_action: str

client = AsyncOpenAI()

async def assess(scenario: str) -> ThreatAssessment:
    completion = await client.chat.completions.parse(
        model="gpt-5.5",
        messages=[{"role": "user", "content": scenario}],
        response_format=ThreatAssessment,
    )
    msg = completion.choices[0].message
    if msg.refusal:
        raise RuntimeError(f"Model refused: {msg.refusal}")
    return msg.parsed
```

OpenAI's structured outputs supports a tighter subset of JSON Schema than full Pydantic
(no arbitrary regex on strings, limited number constraints, no `$ref` cycles, etc.).
If `model_json_schema()` produces unsupported features, simplify the model or define
the schema by hand.

**Refusal handling**: OpenAI signals refusals as `message.refusal` (a string). Always
branch on it before reading `message.parsed`.

### Async pattern

```python
import asyncio
from openai import AsyncOpenAI, APITimeoutError, RateLimitError, APIStatusError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

client = AsyncOpenAI(timeout=120.0)
sem = asyncio.Semaphore(16)  # OpenAI T1 ~1000 RPM gives much more headroom

@retry(
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIStatusError)),
    wait=wait_random_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
async def call_gpt(messages, model="gpt-5.5", **kw):
    async with sem:
        return await client.chat.completions.create(
            model=model, messages=messages, **kw
        )
```

### Refusal behaviour

OpenAI tends to refuse less aggressively than Claude on adversarial-creative content
at high temperature, but is more willing to soft-refuse via long disclaimers. For
military scenarios, the same research-context framing works. OpenAI accepted the
"all lawful purposes" framing for federal contracts in early 2026, so its policy
posture is broader than Anthropic's, but model-level refusals on specific weaponisation
or targeting prompts remain similar in practice. At `temperature=1.2+` GPT-5.5 will
sometimes drift into self-censoring meta-commentary that Claude does not — keep
temperature ≤1.0 on the GPT side if you want symmetric ensemble behaviour.

## LiteLLM unified layer

**Recommendation for THIS use case: skip LiteLLM, call SDKs directly.**

Reasoning:

1. We have exactly two providers and a 30-run hackathon budget. The abstraction
   cost (1.83.x is on a nightly release cadence with an active issue tracker for
   structured-output fallbacks) outweighs the benefit.
2. Per-call audit logging is a hard requirement (`prompt_version` git-blob hash). The
   direct SDK paths give us cleaner hooks than LiteLLM's callback system.
3. Native structured outputs are a moving target. Anthropic shipped `output_config` GA
   recently; LiteLLM has open issues (#20533, #18625, etc.) about parity gaps and
   silent fallbacks on Vertex AI Anthropic, GitHub Copilot routing, and streamed
   tool-call truncation when `finish_reason=length`.
4. Streaming + 429 + fallback combinations are buggy enough that you'd want to
   disable LiteLLM's router fallback and write our own — at which point what's the
   abstraction buying us?

LiteLLM is genuinely useful when you have 5+ providers, want a proxy server, or want
unified cost tracking out of the box. For this prototype, we aren't in that regime.

### Gotchas if you do use LiteLLM anyway

- **Silent streaming truncation**: when `max_tokens` is hit mid tool-call, LiteLLM
  drops the partial response without raising. (BerriAI/litellm #4482 / google adk #4482)
- **429 mid-stream + no fallback configured** can pin CPU to 100% in some versions
  (#26015). Always configure at least a degenerate fallback.
- **`response_format` parity**: works for OpenAI; works for Anthropic via the
  Messages API but historically lagged on Bedrock and Vertex AI Anthropic.
- **Cost reporting** in callbacks via `kwargs["response_cost"]` uses LiteLLM's own
  pricing table, which can drift from current rate cards. Don't trust it for budget
  enforcement; recompute from `usage.input_tokens` + `usage.output_tokens` against a
  vendored price table you control.

### Example: `logged_completion()` wrapper through LiteLLM

If we did go this route, the wrapper would look like:

```python
# src/llm/wrapper.py
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any
import litellm
from pydantic import BaseModel

def _git_blob_hash(prompt_path: Path) -> str:
    """Match the hash that `git ls-files -s` would record — git-blob, not file-sha."""
    return subprocess.check_output(
        ["git", "hash-object", str(prompt_path)], text=True
    ).strip()

async def logged_completion(
    *,
    model: str,                       # e.g. "claude-opus-4-7" or "gpt-5.5"
    prompt_path: Path,                # path to the prompt file on disk
    rendered_messages: list[dict],
    response_format: type[BaseModel] | None = None,
    audit_log: Path,
    run_id: str,
    **kw: Any,
) -> dict:
    prompt_version = _git_blob_hash(prompt_path)
    started = time.time()

    # LiteLLM auto-routes 'claude-*' to Anthropic and 'gpt-*' to OpenAI
    # given the right env vars (ANTHROPIC_API_KEY, OPENAI_API_KEY).
    extra = {}
    if response_format is not None:
        extra["response_format"] = response_format  # Pydantic class accepted directly

    resp = await litellm.acompletion(
        model=model,
        messages=rendered_messages,
        **extra,
        **kw,
    )

    # Compute cost from a vendored table, NOT from response_cost (see gotcha above).
    record = {
        "run_id": run_id,
        "model": model,
        "prompt_path": str(prompt_path),
        "prompt_version": prompt_version,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "stop_reason": resp.choices[0].finish_reason,
        "elapsed_s": time.time() - started,
    }
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with audit_log.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return resp
```

The same shape works without LiteLLM by branching `model.startswith("claude-")` to
`AsyncAnthropic` vs `AsyncOpenAI` and normalising the response object.

## Cost estimate for our pipeline

Assume a single run is 75k tokens total, biased toward input (typical for a
red-team pipeline that feeds in a planning document and asks for analysis):
60k input + 15k output, mixed across providers in roughly equal turns.

**Mixed Opus 4.7 + GPT-5.5 (worst case, all on frontier):**
- Input: 60k × ($5 + $5)/2 / 1e6 = 60k × $5/1e6 = **$0.30**
- Output: 15k × ($25 + $30)/2 / 1e6 = 15k × $27.50/1e6 = **$0.41**
- **Per run ≈ $0.71**, 30 runs ≈ **$21**.

**Realistic mix (Opus + Sonnet for Anthropic side, GPT-5.5 for OpenAI side, Haiku
for fan-out summarisation, half the input cached after first pass):**
- Input: 30k uncached @ ~$3/1e6 + 30k cached @ ~$0.30/1e6 = **$0.10**
- Output: 15k @ ~$20/1e6 (avg) = **$0.30**
- **Per run ≈ $0.40**, 30 runs ≈ **$12**.

**If we get aggressive with Haiku 4.5 + GPT-5 for non-frontier turns:**
- Per run could land at **~$0.15**, 30 runs ≈ **$5**.

The original $1–3/run estimate is conservative. We are well inside the hackathon
budget at frontier-only and have lots of headroom to add ablations.

## Concurrency strategy

- **Semaphore size**: 8 for Anthropic (T1: 50 RPM ≈ 0.83 req/sec; sem of 8 with
  ~1–3 sec latency stays under). 16 for OpenAI (T1: ~1000 RPM is much looser).
- **Per-provider semaphores, not a global one** — they have independent buckets and
  you want the slower provider not to starve the faster one.
- **Retry policy**: tenacity with `wait_random_exponential(min=2, max=60)`,
  `stop_after_attempt(6)`. Retry on `RateLimitError`, `APITimeoutError`, and
  `APIStatusError` where `status_code in {500, 502, 503, 504, 529}`. **Don't** retry
  on 4xx other than 429 — they are bugs in our request, not transient failures.
- **Per-run cost cap**: the wrapper accumulates `input_tokens + output_tokens` per
  `run_id` and compares against a vendored price table. Trip a `BudgetExceeded`
  exception at 1.5× the per-run estimate ($1.10) to catch runaway prompt loops.

```python
# Sketch — add to logged_completion
RUN_COST: dict[str, float] = {}
PER_RUN_CAP_USD = 1.10

def _price(model, in_tok, out_tok) -> float:
    # vendored table; update when rates change
    rates = {
        "claude-opus-4-7":   (5.00, 25.00),
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-4-5":  (1.00,  5.00),
        "gpt-5.5":           (5.00, 30.00),
        "gpt-5":             (2.50, 15.00),
    }
    rin, rout = rates[model]
    return (in_tok * rin + out_tok * rout) / 1_000_000

# inside logged_completion, after the call:
cost = _price(model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
RUN_COST[run_id] = RUN_COST.get(run_id, 0.0) + cost
if RUN_COST[run_id] > PER_RUN_CAP_USD:
    raise RuntimeError(f"run {run_id} exceeded ${PER_RUN_CAP_USD} cap "
                       f"(at ${RUN_COST[run_id]:.3f})")
```

## Cross-family ensemble best practices

- **Prompt portability**: keep prompts in single Markdown files with front-matter for
  variants. Both providers honour a system message, but Claude tends to weight system
  prompts more heavily; if a prompt over-anchors GPT or under-anchors Claude, split
  the system prompt into a "framing" block (system) and a "task" block (user).
- **Structured-output normalisation**: define the canonical schema as a Pydantic
  model. For Claude, `messages.parse(output_format=Model)`. For OpenAI,
  `chat.completions.parse(response_format=Model)`. Both return a typed Pydantic
  instance, so downstream code is provider-agnostic. Wrap both in your
  `logged_completion()` so the audit log records the schema's git-blob hash too.
- **Refusal and max-tokens handling**: always check the stop reason. Claude's
  `stop_reason` values include `"end_turn"`, `"max_tokens"`, `"refusal"`,
  `"tool_use"`. OpenAI's `finish_reason` includes `"stop"`, `"length"`,
  `"content_filter"`. If `length`/`max_tokens`, the parsed output may be junk —
  retry with higher `max_tokens` or a chunked prompt.
- **Provider-failure mid-pipeline**: if Claude 429s through your full retry budget,
  the ensemble step should degrade gracefully. Concretely: mark the run as
  `partial`, log the failure, and have the orchestrator either (a) fall back to the
  other provider with a flag indicating loss of cross-family signal, or (b) skip the
  step entirely if the missing model was nominally redundant. Don't silently
  substitute — the whole point of the ensemble is the disagreement signal.
- **Don't compare token counts across providers** for any quantitative claim — Opus
  4.7's new tokenizer plus GPT-5.5's tokenizer differ by ~30% on similar text. If
  you need apples-to-apples, count UTF-8 codepoints or words.
- **Temperature**: keep both at the same value for ensemble fairness, default `0.7`.
  Push to `1.0` only on creative-divergence steps. GPT-5.5 above ~1.0 starts
  meta-commenting; Claude tolerates higher temperatures more cleanly.

## Bibliography

- Claude models overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Claude rate limits: https://platform.claude.com/docs/en/api/rate-limits
- Claude structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Claude tool use: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python
- OpenAI models / GPT-5.5: https://developers.openai.com/api/docs/models/gpt-5.5
- OpenAI pricing: https://openai.com/api/pricing/
- OpenAI rate limits: https://developers.openai.com/api/docs/guides/rate-limits
- OpenAI structured outputs: https://platform.openai.com/docs/guides/structured-outputs
- OpenAI Python helpers: https://github.com/openai/openai-python/blob/main/helpers.md
- LiteLLM repo: https://github.com/BerriAI/litellm
- LiteLLM Anthropic provider docs: https://docs.litellm.ai/docs/providers/anthropic
- LiteLLM custom callbacks: https://docs.litellm.ai/docs/observability/custom_callback
- LiteLLM streaming bugs: https://github.com/BerriAI/litellm/issues/22296,
  https://github.com/BerriAI/litellm/issues/26015,
  https://github.com/BerriAI/litellm/issues/20533
- Tenacity: https://tenacity.readthedocs.io/
- Anthropic on military contracting (context for refusal posture):
  https://www.humanintheloop.online/p/36-edition-can-ai-firms-set-limits-on-how-and-where-the-military-uses-their-models
- GPT-5.5 launch coverage: https://openai.com/index/introducing-gpt-5-5/
- GPT-5.5 pricing breakdown: https://apidog.com/blog/gpt-5-5-pricing/
