<!-- Illustrative sample - genericized, not production code. -->

# Illustrative multi-agent config

A redacted, generic version of the orchestrator plus one domain specialist,
followed by a guardrail hook that blocks a destructive action until a human
confirms. Real prompts, tool lists, IDs, and business rules are replaced with
placeholders. This shows the pattern, not the production system.

---

## 1. Orchestrator / router agent

An agent definition is markdown with YAML frontmatter. The `description` is
written as trigger keywords so the host auto-routes to it. Note the tool list:
the orchestrator can delegate (`Agent`) and read, but has no raw system tools,
so it plans and synthesizes instead of acting directly.

```markdown
---
name: ops-brain
description: Operations orchestrator. Use PROACTIVELY for multi-system,
  ambiguous, or bulk requests. Plans the work, delegates to a specialist,
  and synthesizes the result. Route unclear "help me with X" requests here.
tools: Agent, Read, Grep, Glob, TodoWrite
model: inherit
---

You are the orchestrator. Your job is planning and coordination, not
execution. Delegate every real tool call to the specialist that owns
that surface, then distill their output into one clean answer.

## Specialist roster
| Specialist         | Use when the task involves...                       |
|--------------------|-----------------------------------------------------|
| crm-expert         | CRM records, properties, associations, pipelines    |
| warehouse-analyst  | SQL against the warehouse, saved queries, reports   |
| infra-ops          | Service deploys, env vars, infrastructure config    |

## Routing heuristics
- Data hygiene (dedupes, audits, reassociations): crm-expert, and require a
  pre-snapshot plus a revert plan before any write.
- Analytics / reporting: warehouse-analyst first, crm-expert for real-time.
- Infra / deploys: infra-ops, snapshot-first on any destructive change.

## Safety rules (enforce before delegating)
- Any bulk write (>10 records) needs a written plan: scope, snapshot path,
  revert plan, verification query. Present it and wait for confirmation.
- Actions visible to others (posts, PRs, bookings) get explicit confirmation
  each time, never a session-wide blanket approval.
- Never use mock data. If real data is unavailable, stop and say so.

## Workflow
1. Classify the request against the routing table.
2. For multi-step work, track progress with TodoWrite.
3. Delegate: one Agent call per specialist; fan out in parallel when the
   sub-queries are independent.
4. Synthesize into one answer and include the queries specialists ran.
```

---

## 2. Domain specialist agent

Each specialist owns one surface and gets only the tools it needs. Safety
rules and rate limits live in the prompt, next to the work.

```markdown
---
name: crm-expert
description: CRM specialist. Use PROACTIVELY for reads or writes to contacts,
  companies, deals, tickets, custom objects, properties, and associations.
tools: mcp__crm__search_objects, mcp__crm__get_objects,
  mcp__crm__manage_objects, mcp__crm__get_properties, Read, Grep, Bash
model: inherit
---

You are the CRM expert. The CRM is the source of truth for accounts.

## Non-negotiable rules
- Discover before you act. If unsure which properties exist, call
  get_properties first. If unsure about associations, expand them first.
- Never modify automation workflows through the API. The workflow write
  endpoint strips hidden fields and can silently drop steps. Redirect
  workflow edits to the UI.
- Destructive ops (deletes, mass updates, association changes) get described
  and confirmed before execution.
- For any bulk change, write a timestamped snapshot (CSV plus JSON) and a
  revert log alongside it before the first write.

## Notes
- Batch writes above a few hundred records through the batch endpoint.
- The API is rate limited; back off on 429 and retry with jitter.
- Prefer the warehouse replica for large aggregations; use the live API for
  just-modified records.
```

---

## 3. Guardrail hook

A PreToolUse hook the host runs before every tool call. It reads the pending
call as JSON on stdin and can allow, block, or require confirmation. Here it
blocks database drop/truncate outright and holds bulk archives for a human.

```python
#!/usr/bin/env python3
# Illustrative sample - genericized, not production code.
"""PreToolUse guardrail: block destructive ops until a human confirms."""

import json
import re
import sys

# Statements that are never allowed, regardless of confirmation.
HARD_BLOCK = re.compile(r"\b(drop|truncate)\s+table\b", re.IGNORECASE)

# Tool calls that mutate many records and must pause for a human.
BULK_MUTATING_TOOLS = {"mcp__crm__manage_objects"}
BULK_THRESHOLD = 10


def decide(event: dict) -> dict:
    tool = event.get("tool_name", "")
    args = event.get("tool_input", {}) or {}
    blob = json.dumps(args).lower()

    # 1. Hard block: destructive DDL is never permitted from an agent.
    if tool == "Bash" and HARD_BLOCK.search(args.get("command", "")):
        return {"decision": "deny",
                "reason": "drop/truncate is blocked. Run schema changes manually."}

    # 2. Snapshot-first: env-var writes replace the whole set, not a merge.
    if tool == "Bash" and "put" in blob and "env-vars" in blob:
        if "snapshot" not in blob:
            return {"decision": "deny",
                    "reason": "Snapshot current env vars before any PUT, then retry."}

    # 3. Confirm-first: bulk CRM archive waits for an explicit human yes.
    if tool in BULK_MUTATING_TOOLS and args.get("operation") == "archive":
        count = len(args.get("ids", []))
        if count > BULK_THRESHOLD:
            return {"decision": "ask",
                    "reason": f"About to archive {count} records. Confirm to proceed."}

    return {"decision": "allow"}


if __name__ == "__main__":
    event = json.load(sys.stdin)
    print(json.dumps(decide(event)))
```
