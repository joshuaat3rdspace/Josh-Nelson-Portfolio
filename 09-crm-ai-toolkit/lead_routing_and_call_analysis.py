# Illustrative sample - genericized, not production code.
#
# Two patterns from the CRM and AI toolkit, reduced to their essentials:
#   1) An area-code-aware round-robin lead-routing engine (RevOps).
#   2) A two-step LLM call-transcript analyzer (AI-ops).
#
# All identifiers, vendor keys, and property names here are placeholders.
# Real deployments read every credential from environment variables.

import os
import re
from itertools import cycle
from typing import Iterable

import pandas as pd


# ---------------------------------------------------------------------------
# 1) Lead routing: assign each area code to exactly one rep, round-robin.
#    Keeping all leads from an area code with a single rep improves local
#    presence and continuity, while round-robin keeps the load balanced.
# ---------------------------------------------------------------------------

def parse_area_code(phone: str) -> str | None:
    """Return the 3-digit US area code from a messy phone string, or None."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[:3] if len(digits) == 10 else None


def assign_owners_by_area_code(
    leads: pd.DataFrame,
    owner_ids: list[str],
    phone_column: str = "phone_number",
    owner_column: str = "assigned_owner_id",
) -> pd.DataFrame:
    """
    Assign an owner to every lead so that all leads sharing an area code go to
    the same owner. Area codes are handed out to owners in round-robin order.
    """
    if not owner_ids:
        leads[owner_column] = pd.NA
        return leads

    leads = leads.copy()
    leads["area_code"] = leads[phone_column].apply(parse_area_code)

    # Deterministic order so re-runs are stable, then round-robin over owners.
    unique_area_codes = sorted(c for c in leads["area_code"].dropna().unique())
    rotation = cycle(owner_ids)
    area_to_owner = {code: next(rotation) for code in unique_area_codes}

    leads[owner_column] = leads["area_code"].map(area_to_owner)
    return leads


def collect_team_owners(teams: dict[str, list[dict]], selected: Iterable[str]) -> list[str]:
    """Flatten the owner ids belonging to the selected teams (deduplicated)."""
    owners: list[str] = []
    for team_name in selected:
        for member in teams.get(team_name, []):
            owner_id = member.get("owner_id")
            if owner_id is not None and owner_id not in owners:
                owners.append(owner_id)
    return owners


# ---------------------------------------------------------------------------
# 2) Call analysis: turn a raw transcript into one normalized value.
#    Step one lets the model reason; step two forces a clean, parseable answer
#    so the result can be written straight back to the CRM.
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = (
    "You are an expert at reading sales-call transcripts and identifying the "
    "prospect's stated investable or liquid-asset amount."
)

NORMALIZE_INSTRUCTION = (
    "Based on your answer, return a single unformatted number. If a range is "
    "given, return the lower bound. If no amount is present, return N/A. "
    "Return only the number, with no text, symbols, or commas."
)


def analyze_transcript(client, transcript: str, model: str = "gpt-4o-mini") -> str:
    """
    Two-step extraction. `client` is any OpenAI-compatible chat client whose
    key is supplied via the environment, e.g. OpenAI(api_key=os.environ[...]).
    """
    reasoning = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ],
    )
    draft = reasoning.choices[0].message.content

    normalized = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
            {"role": "assistant", "content": draft},
            {"role": "user", "content": NORMALIZE_INSTRUCTION},
        ],
    )
    return normalized.choices[0].message.content.strip()


if __name__ == "__main__":
    # Placeholder data only - no real leads, numbers, or owners.
    sample = pd.DataFrame(
        {
            "email": ["a@example.com", "b@example.com", "c@example.com"],
            "phone_number": ["(212) 555-0100", "212-555-0111", "+1 415 555 0000"],
        }
    )
    teams = {
        "Team A": [{"name": "Rep One", "owner_id": "1001"}],
        "Team B": [{"name": "Rep Two", "owner_id": "1002"}],
    }
    owners = collect_team_owners(teams, ["Team A", "Team B"])
    routed = assign_owners_by_area_code(sample, owners)
    print(routed[["email", "area_code", "assigned_owner_id"]].to_string(index=False))

    # LLM step is illustrative; a client would be constructed from an env key:
    #   from openai import OpenAI
    #   client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    #   print(analyze_transcript(client, transcript_text))
