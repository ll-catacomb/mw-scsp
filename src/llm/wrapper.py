"""logged_completion — every LLM call goes through here.

Direct SDKs, no LiteLLM (per `_context/agent-output/ra6-cross-family-api.md` §"LiteLLM unified
layer": for two providers at hackathon scale, the abstraction cost outweighs the benefit and
LiteLLM's cost reporting is unreliable for budget enforcement).

Responsibilities (PROJECT_SPEC.md §6, §9):
  1. SHA256 of (system + user) -> prompt_hash.
  2. Git blob hash of the prompt file at call time -> prompt_version.
  3. Bounded-concurrency async call to the provider SDK with tenacity retries.
  4. Optional pydantic structured output via messages.parse / chat.completions.parse.
     One retry on parse / refusal failure with a clarifying nudge.
  5. Persist a full row to llm_calls (master audit log).
  6. Compute cost from a vendored price table (per RA-6 §"Cost reporting in callbacks ...
     Don't trust it for budget enforcement; recompute from usage tokens against a vendored
     price table you control").
  7. Enforce RUN_COST_CAP_USD and TOTAL_COST_CAP_USD; raise CostCapExceeded if breached.

Downstream code awaits `logged_completion()` like any async function. No bare SDK calls
should appear in pipeline code — the wrapper is the audit spine.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from anthropic import AsyncAnthropic
from anthropic import APIStatusError as AnthropicAPIStatusError
from anthropic import APITimeoutError as AnthropicAPITimeoutError
from anthropic import RateLimitError as AnthropicRateLimitError
from openai import APIStatusError as OpenAIAPIStatusError
from openai import APITimeoutError as OpenAIAPITimeoutError
from openai import AsyncOpenAI
from openai import RateLimitError as OpenAIRateLimitError
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from src.memory.store import connect, init_db


class CostCapExceeded(RuntimeError):
    """Raised when adding the next call would exceed RUN_COST_CAP_USD or TOTAL_COST_CAP_USD."""


class StructuredOutputParseError(RuntimeError):
    """Raised when the model returned text that does not validate against the requested schema."""


class ProviderRefusal(RuntimeError):
    """Raised when the model refused to answer (Anthropic stop_reason='refusal' or OpenAI message.refusal)."""


# Vendored price table (USD per 1M tokens). Source: RA-6 §"Pricing", verified 2026-04-25.
# Update when rates change. Used for budget enforcement, NOT for accounting.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    # (input_per_1m, output_per_1m)
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.5-pro": (30.00, 180.00),
    "gpt-5": (2.50, 15.00),
    "gpt-5-mini": (0.25, 2.00),  # approximate; confirm at https://openai.com/api/pricing/
}


# Per-provider semaphores (lazy-init so import doesn't bind to an event loop).
# Per RA-6: providers have independent rate buckets; one slow provider must not starve the
# other.
_anthropic_semaphore: asyncio.Semaphore | None = None
_openai_semaphore: asyncio.Semaphore | None = None
_anthropic_client: AsyncAnthropic | None = None
_openai_client: AsyncOpenAI | None = None


def _provider_for(model: str) -> Literal["anthropic", "openai", "unknown"]:
    m = model.lower()
    if m.startswith("claude") or m.startswith("anthropic/"):
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4", "openai/")):
        return "openai"
    return "unknown"


def _anthropic() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(timeout=120.0)
    return _anthropic_client


def _openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(timeout=120.0)
    return _openai_client


def _semaphore_for(provider: str) -> asyncio.Semaphore:
    global _anthropic_semaphore, _openai_semaphore
    if provider == "anthropic":
        if _anthropic_semaphore is None:
            n = int(os.environ.get("ANTHROPIC_MAX_CONCURRENCY", "8"))
            _anthropic_semaphore = asyncio.Semaphore(n)
        return _anthropic_semaphore
    if provider == "openai":
        if _openai_semaphore is None:
            n = int(os.environ.get("OPENAI_MAX_CONCURRENCY", "16"))
            _openai_semaphore = asyncio.Semaphore(n)
        return _openai_semaphore
    raise ValueError(f"Unknown provider: {provider!r}")


def _git_blob_hash(content: bytes) -> str:
    """Compute git's blob hash for a byte string. Matches `git hash-object`."""
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def _prompt_version(prompt_path: str | Path | None) -> str:
    if prompt_path is None:
        return "inline"
    p = Path(prompt_path)
    if not p.exists():
        return f"missing:{p.name}"
    return _git_blob_hash(p.read_bytes())


def _prompt_hash(system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\0")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


def _price(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """USD cost for a call. Returns None if model isn't priced or tokens unknown."""
    if input_tokens is None or output_tokens is None:
        return None
    rates = PRICE_TABLE.get(model)
    if rates is None:
        return None
    rin, rout = rates
    return (input_tokens * rin + output_tokens * rout) / 1_000_000


def _check_cost_cap(conn: sqlite3.Connection, run_id: str) -> None:
    run_cap = float(os.environ.get("RUN_COST_CAP_USD", "1.10"))
    total_cap = float(os.environ.get("TOTAL_COST_CAP_USD", "50.0"))
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_calls WHERE run_id = ?", (run_id,)
    ).fetchone()
    run_total = float(row[0] or 0.0)
    if run_total >= run_cap:
        raise CostCapExceeded(
            f"Run {run_id} has spent ${run_total:.3f}, at or above RUN_COST_CAP_USD=${run_cap:.2f}."
        )
    row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_calls").fetchone()
    grand_total = float(row[0] or 0.0)
    if grand_total >= total_cap:
        raise CostCapExceeded(
            f"Project has spent ${grand_total:.3f}, at or above TOTAL_COST_CAP_USD=${total_cap:.2f}."
        )


_ANTHROPIC_RETRYABLE = (
    AnthropicRateLimitError,
    AnthropicAPITimeoutError,
)
_OPENAI_RETRYABLE = (
    OpenAIRateLimitError,
    OpenAIAPITimeoutError,
)
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 529})


def _is_retryable_status(exc: Exception) -> bool:
    """Match RA-6's policy: retry only on 429 + 5xx (incl. Anthropic 529 overload)."""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int) and code in _RETRYABLE_STATUS:
        return True
    return False


async def _call_anthropic(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    response_format: type[BaseModel] | None,
) -> tuple[str, str | None, int | None, int | None]:
    """Returns (text, refusal_or_none, input_tokens, output_tokens)."""
    client = _anthropic()
    messages = [{"role": "user", "content": user}]

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(_ANTHROPIC_RETRYABLE)
        | retry_if_exception_type(AnthropicAPIStatusError),
        wait=wait_random_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    ):
        with attempt:
            try:
                if response_format is not None:
                    # SDK helper: parse() converts the Pydantic model to a JSON Schema, sends
                    # output_config, and parses the result back into the model.
                    resp = await client.messages.parse(
                        model=model,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        output_format=response_format,
                    )
                    # parsed_output is set when stop_reason='end_turn' and parsing succeeded.
                    parsed = getattr(resp, "parsed_output", None)
                    text = parsed.model_dump_json() if parsed else _join_anthropic_text(resp)
                else:
                    resp = await client.messages.create(
                        model=model,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    text = _join_anthropic_text(resp)
            except AnthropicAPIStatusError as e:
                if not _is_retryable_status(e):
                    raise
                raise

    refusal = None
    stop_reason = getattr(resp, "stop_reason", None)
    if stop_reason == "refusal":
        refusal = "anthropic stop_reason=refusal"
    elif stop_reason == "max_tokens":
        # Caller may want to retry with higher max_tokens; we don't, but record the fact.
        refusal = None
    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "input_tokens", None) if usage else None
    out_tok = getattr(usage, "output_tokens", None) if usage else None
    return text, refusal, in_tok, out_tok


def _join_anthropic_text(resp: Any) -> str:
    parts: list[str] = []
    for block in getattr(resp, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


async def _call_openai(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    response_format: type[BaseModel] | None,
) -> tuple[str, str | None, int | None, int | None]:
    """Returns (text, refusal_or_none, prompt_tokens, completion_tokens)."""
    client = _openai()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(_OPENAI_RETRYABLE)
        | retry_if_exception_type(OpenAIAPIStatusError),
        wait=wait_random_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    ):
        with attempt:
            try:
                if response_format is not None:
                    resp = await client.chat.completions.parse(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_completion_tokens=max_tokens,
                        response_format=response_format,
                    )
                    msg = resp.choices[0].message
                    if msg.refusal:
                        return "", str(msg.refusal), None, None
                    parsed = getattr(msg, "parsed", None)
                    text = parsed.model_dump_json() if parsed else (msg.content or "")
                else:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_completion_tokens=max_tokens,
                    )
                    msg = resp.choices[0].message
                    if msg.refusal:
                        return "", str(msg.refusal), None, None
                    text = msg.content or ""
            except OpenAIAPIStatusError as e:
                if not _is_retryable_status(e):
                    raise
                raise

    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", None) if usage else None
    out_tok = getattr(usage, "completion_tokens", None) if usage else None
    return text, None, in_tok, out_tok


def _parse_structured(text: str, schema: type[BaseModel]) -> BaseModel:
    """JSON load + pydantic validation. Tolerates fenced code blocks."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
        stripped = stripped.strip()
    data = json.loads(stripped)
    return schema.model_validate(data)


async def logged_completion(
    *,
    run_id: str,
    stage: str,
    agent_id: str | None,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    prompt_path: str | Path | None = None,
    response_format: type[BaseModel] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Make an LLM call, log it to llm_calls, return the parsed result.

    Returns:
      {
        "call_id":   str,
        "raw_text":  str,                 # assistant text content (or JSON for structured)
        "parsed":    BaseModel | None,    # validated pydantic instance, or None
        "input_tokens":  int | None,
        "output_tokens": int | None,
        "cost_usd":  float | None,
        "latency_ms": int,
      }

    Raises:
      CostCapExceeded — pre- or post-call, when cumulative cost for run_id (or globally)
        crosses the cap.
      ProviderRefusal — when the model refused (Anthropic stop_reason='refusal' or OpenAI
        message.refusal). Caller decides whether to retry with different framing.
      StructuredOutputParseError — when both initial and clarifying-retry parses fail.
    """
    init_db(db_path)
    call_id = str(uuid.uuid4())
    p_hash = _prompt_hash(system, user)
    p_version = _prompt_version(prompt_path)
    provider = _provider_for(model)
    if provider not in ("anthropic", "openai"):
        raise ValueError(f"Cannot route model {model!r}: unknown provider.")

    with connect(db_path) as conn:
        _check_cost_cap(conn, run_id)

    sem = _semaphore_for(provider)
    started = time.perf_counter()
    async with sem:
        if provider == "anthropic":
            raw_text, refusal, in_tok, out_tok = await _call_anthropic(
                model=model, system=system, user=user, temperature=temperature,
                max_tokens=max_tokens, response_format=response_format,
            )
        else:
            raw_text, refusal, in_tok, out_tok = await _call_openai(
                model=model, system=system, user=user, temperature=temperature,
                max_tokens=max_tokens, response_format=response_format,
            )

        if refusal is not None:
            latency_ms = int((time.perf_counter() - started) * 1000)
            cost_usd = _price(model, in_tok, out_tok)
            _persist(
                call_id=call_id, run_id=run_id, stage=stage, agent_id=agent_id,
                provider=provider, model=model, temperature=temperature,
                system=system, user=user, raw_text=raw_text, parsed_text=None,
                p_hash=p_hash, p_version=p_version,
                in_tok=in_tok, out_tok=out_tok, latency_ms=latency_ms, cost_usd=cost_usd,
                db_path=db_path,
            )
            raise ProviderRefusal(refusal)

        parsed: BaseModel | None = None
        if response_format is not None:
            try:
                parsed = _parse_structured(raw_text, response_format)
            except (json.JSONDecodeError, ValidationError) as first_err:
                # One clarifying retry with the parser error fed back.
                retry_user = (
                    f"{user}\n\n"
                    "Your previous response could not be parsed as the requested JSON schema. "
                    f"Parser said: {first_err}. "
                    "Return ONLY valid JSON conforming to the schema; no commentary, no fences."
                )
                if provider == "anthropic":
                    raw_text, refusal, in_tok2, out_tok2 = await _call_anthropic(
                        model=model, system=system, user=retry_user, temperature=temperature,
                        max_tokens=max_tokens, response_format=response_format,
                    )
                else:
                    raw_text, refusal, in_tok2, out_tok2 = await _call_openai(
                        model=model, system=system, user=retry_user, temperature=temperature,
                        max_tokens=max_tokens, response_format=response_format,
                    )
                # Sum tokens across both attempts so cost reflects total usage.
                in_tok = (in_tok or 0) + (in_tok2 or 0) if (in_tok or in_tok2) else None
                out_tok = (out_tok or 0) + (out_tok2 or 0) if (out_tok or out_tok2) else None
                if refusal is not None:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    cost_usd = _price(model, in_tok, out_tok)
                    _persist(
                        call_id=call_id, run_id=run_id, stage=stage, agent_id=agent_id,
                        provider=provider, model=model, temperature=temperature,
                        system=system, user=user, raw_text=raw_text, parsed_text=None,
                        p_hash=p_hash, p_version=p_version,
                        in_tok=in_tok, out_tok=out_tok, latency_ms=latency_ms, cost_usd=cost_usd,
                        db_path=db_path,
                    )
                    raise ProviderRefusal(refusal)
                try:
                    parsed = _parse_structured(raw_text, response_format)
                except (json.JSONDecodeError, ValidationError) as second_err:
                    raise StructuredOutputParseError(
                        f"Could not parse structured output after retry: {second_err}"
                    ) from second_err
    latency_ms = int((time.perf_counter() - started) * 1000)
    cost_usd = _price(model, in_tok, out_tok)

    parsed_serialized = parsed.model_dump_json() if parsed is not None else None

    _persist(
        call_id=call_id, run_id=run_id, stage=stage, agent_id=agent_id,
        provider=provider, model=model, temperature=temperature,
        system=system, user=user, raw_text=raw_text, parsed_text=parsed_serialized,
        p_hash=p_hash, p_version=p_version,
        in_tok=in_tok, out_tok=out_tok, latency_ms=latency_ms, cost_usd=cost_usd,
        db_path=db_path,
    )

    return {
        "call_id": call_id,
        "raw_text": raw_text,
        "parsed": parsed,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
    }


def _persist(
    *,
    call_id: str, run_id: str, stage: str, agent_id: str | None,
    provider: str, model: str, temperature: float,
    system: str, user: str, raw_text: str, parsed_text: str | None,
    p_hash: str, p_version: str,
    in_tok: int | None, out_tok: int | None, latency_ms: int, cost_usd: float | None,
    db_path: Path | None,
) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO llm_calls (
              call_id, run_id, stage, agent_id, provider, model, temperature,
              system_prompt, user_prompt, raw_response, parsed_output,
              prompt_hash, prompt_version,
              input_tokens, output_tokens, latency_ms, cost_usd, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id, run_id, stage, agent_id, provider, model, temperature,
                system, user, raw_text, parsed_text,
                p_hash, p_version,
                in_tok, out_tok, latency_ms, cost_usd,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        _check_cost_cap(conn, run_id)
