# Illustrative sample - genericized, not production code.
"""LLM-as-judge audit pipeline (skeleton).

Reads a call transcript, scores it against a written rubric using a top-tier
Claude model, validates a strict JSON verdict, persists it, and routes a
notification. The rubric text and rules below are generic placeholders, not any
real team's rules of engagement.
"""
from __future__ import annotations

import json
import os

from anthropic import Anthropic

MODEL = os.environ.get("JUDGE_MODEL", "claude-opus-4-8")

# The rubric lives in the prompt, not in code, so it can be tuned without a
# deploy and the model stays swappable. Placeholder text, not a real rubric.
SYSTEM_PROMPT = """You are an independent reviewer scoring a sales qualification call.
Judge ONLY from the transcript and deal context provided; never infer the verdict
from what later happened to the deal.

Gate 0 (data sufficiency): if the transcript is empty or too short to contain a real
two-way conversation, you cannot score it. Cap the verdict at "yellow" and set
confidence to "low".

Hard gates (a failure caps the verdict at "yellow", never "green"):
  - target_market: the prospect is in the product's target market.
  - supported_stack: the prospect runs a tooling stack the product supports.

Soft signals (pass / weak / fail / unknown): pain_fit, role_fit, seat_fit, next_step_fit.

Return "green" (strong fit), "yellow" (borderline), or "red" (weak fit), with a short
rationale and transcript-grounded evidence per gate and signal. Confidence rates
EVIDENCE quality, not how strong the call was."""


def _signal(statuses=("pass", "weak", "fail", "unknown")) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "evidence"],
        "properties": {
            "status": {"type": "string", "enum": list(statuses)},
            "evidence": {"type": "string"},
        },
    }


# Structured-output schema: the Messages API guarantees the response validates
# against this, so verdict and confidence are always present and in-enum.
VERDICT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "summary", "reasons", "hard_gates", "soft_signals", "confidence"],
    "properties": {
        "verdict": {"type": "string", "enum": ["green", "yellow", "red"]},
        "summary": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "hard_gates": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_market", "supported_stack"],
            "properties": {
                "target_market": _signal(("pass", "fail", "unknown")),
                "supported_stack": _signal(),
            },
        },
        "soft_signals": {
            "type": "object",
            "additionalProperties": False,
            "required": ["pain_fit", "role_fit", "seat_fit", "next_step_fit"],
            "properties": {
                "pain_fit": _signal(),
                "role_fit": _signal(),
                "seat_fit": _signal(),
                "next_step_fit": _signal(),
            },
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}


def _first_text(resp) -> str:
    # With adaptive thinking, content[0] may be a thinking block, so scan for text.
    return next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")


def judge_call(client: Anthropic, transcript: str, deal_context: str) -> dict:
    """Score one call. Returns a schema-valid verdict dict, or a sentinel."""
    user_prompt = f"# Deal context\n{deal_context}\n\n# Transcript\n{transcript}\n"
    resp = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        # Opus 4.7/4.8 reject temperature/top_p/top_k (400). Depth is controlled
        # by adaptive thinking plus effort, not sampling params.
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )
    # A refusal or a truncated response is not a verdict; flag it so it cannot
    # masquerade downstream as a scored row.
    if resp.stop_reason in ("refusal", "max_tokens"):
        return {"verdict": "NO_VERDICT", "stop_reason": resp.stop_reason}
    # Structured outputs guarantee clean JSON; parse defensively anyway.
    try:
        return json.loads(_first_text(resp))
    except (json.JSONDecodeError, TypeError):
        return {"verdict": "PARSE_ERROR", "raw": _first_text(resp)[:500]}


def persist(cur, deal_id: str, verdict: dict) -> None:
    """Append-only insert; current state is read through a view, not by mutation."""
    cur.execute(
        "insert into audit (deal_id, verdict, confidence, payload) "
        "values (%s, %s, %s, %s::jsonb)",
        (deal_id, verdict.get("verdict"), verdict.get("confidence"), json.dumps(verdict)),
    )


def route_notification(notify, deal_id: str, verdict: dict) -> None:
    """Green/yellow deals get a coaching note to the rep; every scored deal rolls
    up into the leadership digest. `notify` is any injected send-a-message callable."""
    v = verdict.get("verdict")
    if v in ("green", "yellow"):
        notify(channel="rep_dm", deal_id=deal_id, body=verdict.get("summary", ""))
    notify(channel="leadership_digest", deal_id=deal_id, body=v)


def run(transcript: str, deal_context: str, deal_id: str, cur, notify) -> dict:
    client = Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],  # never hardcoded
        timeout=240.0,
        max_retries=3,
    )
    verdict = judge_call(client, transcript, deal_context)
    if verdict.get("verdict") in ("green", "yellow", "red"):
        persist(cur, deal_id, verdict)
        route_notification(notify, deal_id, verdict)
    return verdict
