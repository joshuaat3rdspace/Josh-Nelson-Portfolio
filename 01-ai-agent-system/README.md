# Internal AI Agent System (the RevOps "brain")

A 16-agent Claude Code system that turns a RevOps team's institutional knowledge into safe, reusable operators for the tools they run on every day.

> Note on this writeup: the production system runs against a company's live CRM, warehouse, and billing data, so its real source is proprietary. What follows is an architecture writeup plus an illustrative, genericized code sample. The patterns are authentic, the business logic and identifiers are not.

## The problem

RevOps work is a coordination problem across a dozen disconnected systems. A single question ("why did this account route to the wrong rep, and does its ARR match billing?") touches the CRM, the routing tool, the warehouse, and the billing system, each with its own API, its own quirks, and its own ways to do damage. The knowledge for how to answer safely lived in one person's head. That does not scale, and it does not survive turnover.

I wanted the institutional knowledge (which property means what, which endpoints are destructive, when to snapshot before you write) to live in version control as executable operators, not in a wiki nobody reads.

## What I built

A multi-agent system built on Claude Code, organized as one orchestrator plus 15 domain specialists.

- **Orchestrator ("revops-brain").** Parses a request, classifies the work type against a routing table, and delegates to the right specialist(s). It has the delegation tool but not the raw system tools, so it plans and synthesizes rather than acting directly. For multi-system asks it fans out to specialists in parallel and collapses their output into one answer.
- **15 domain specialists.** Each owns one surface: CRM, call intelligence, analytics and BI (SQL against the warehouse), deploy and infrastructure, source control, Slack, billing and ARR reconciliation, inbound routing, issue tracking, docs, and a knowledge-base curator. Each agent gets a curated, minimal tool list (only the MCP and CLI tools it needs), which keeps it focused and its context small.
- **Auto-routing by description.** Each agent's frontmatter `description` is written as trigger keywords, so the host delegates to the correct specialist without the user naming it. Ambiguous requests fall through to the orchestrator.
- **Version-controlled config with a sync step.** The whole agent roster, permission policy, MCP templates, and global rules live in a git repo. A teammate clones it and an install step copies the config into their local Claude Code home, substituting paths and pulling secrets from a local env file (never committed). Updating an agent is a commit and a pull.
- **Guardrails at two layers.** A declarative permission policy (allow / ask / deny lists) blocks or gates dangerous shell and data operations, and destructive-action hooks enforce the rest: deploy env-var writes must snapshot first (the vendor's PUT replaces the whole set, not a merge), bulk CRM archives are confirm-first, and database drop/truncate is blocked outright. The same conventions (snapshot before write, timestamped backups, revert logs) are also baked into every agent's system prompt as non-negotiable rules.
- **Knowledge base as data.** The curator agent ports hundreds of process specs (278 workflow specs, 248 source articles) into structured, queryable KB entries, so the agents reason from written procedure rather than guesswork.

It runs against a real footprint: dozens of live services, 47 repos, ~175 CRM properties, and a warehouse replica of the CRM, all reachable through 2 MCP servers (one exposing 32 tools).

## My role

I designed and built the whole system: the orchestrator, every specialist prompt, the routing heuristics, the permission policy, the guardrail hooks, and the version-controlled install flow. I own it end to end and use it daily to run RevOps investigations and routine operations. The design bias throughout is mine: least-privilege tool lists per agent, human confirmation on anything visible or destructive, and no mock data ever.

## Impact

- Turned one person's institutional knowledge into a shared, version-controlled toolkit any teammate can clone and run.
- Made routine multi-system investigations (attribution audits, billing-to-CRM reconciliation, data-hygiene sweeps) a single natural-language request instead of an afternoon of manual API work.
- Encoded safety into the system itself, so the fast path is also the safe path: snapshots before writes, confirmation before bulk or visible actions, and hard blocks on the truly destructive ones.

## Tech

Claude Code and the Claude / Anthropic API, MCP (Model Context Protocol) servers, a declarative permission policy plus PreToolUse guardrail hooks, Python and Bash for the operational scripts, HubSpot, Gong, Redash and PostgreSQL (the warehouse), Render, Slack, Subskribe, and git-based config distribution.
