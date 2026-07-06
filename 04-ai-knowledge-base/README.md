# AI-Consumable Knowledge Base + Process Tracing

A queryable system of record for how the GTM stack actually works, so "how does this work / why is it broken" resolves in minutes instead of a Slack-archaeology dig.

## The problem

Tribal knowledge does not scale. Roughly 40 production GTM automations were spread across dozens of repos and deployed services, documented (if at all) in scattered help articles, Slack threads, and one or two people's heads. When something broke, or a new hire asked "how does lead routing work," answering it meant paging the one person who remembered, then manually tracing repo to service to entry point to whatever the job last did at runtime. Incident triage and onboarding both paid that tax.

## What I built

The org's Process Knowledge Base: 278 machine-readable process specs, ingested from 248 source articles, covering roughly 40 production GTM automations. Each spec is dual-audience by design: a plain-English summary a non-engineer can read, plus a technical reference (about 8,000 characters) that an agent can act on, capturing the repo, deployed service, entry point, triggers, dependencies, and where to check runtime state.

The knowledge base is the backing store for two agents:

- A process-tracer that answers "how does X work / why is it broken" by resolving a question down a fixed chain: repo -> deployed service -> entry point -> current runtime state.
- A knowledge-base curator that keeps specs in sync with reality, flags drift, and turns new source articles into specs.

The design is grounded in the real infrastructure. The automations run as Dockerized Python jobs deployed as cron services, each with a clear entry point (for example, an ETL runner like `run_crm_hourly_sync`) that writes status, watermarks, and metrics to a runtime-state table (`meta.etl_runs`) in a PostgreSQL analytics database. The agents read that runtime state through an MCP tool layer: a Node.js MCP server built on the `@modelcontextprotocol/sdk` streamable-HTTP transport, with Zod-validated tools and token auth, exposing read tools such as `execute_sql`, `describe_schema`, and `get_dashboard` over the same database. So a spec does not just describe an automation, it tells the tracer exactly which service and entry point to inspect and which table to query to see whether it ran, when, and with what error.

Least privilege is built in: the MCP layer ships a read-only variant for agents that only need to observe, kept separate from the read-write variant used for authoring.

## How a trace works

A "why is this broken" question walks a fixed, auditable chain:

1. Match the question to a process spec in the knowledge base by intent.
2. Read the spec's technical block to get the repo, deployed service, and entry point.
3. Follow the spec's `runtime_state` pointer to the exact table and lookup for that job.
4. Query live runtime state through the read-only MCP tool (`execute_sql` on `meta.etl_runs`).
5. Return a verdict: working (fresh success, row counts) or broken (surfacing the error, the stuck watermark, and the owning role to escalate to).

Because every spec resolves the same way, the tracer's answers are consistent and cite exactly where they looked, and the curator agent can detect when a spec has drifted from the code it describes. The illustrative sample in this folder (`process-spec-example.md`) shows one spec plus the resolution diagram.

## My role

I designed and built this end to end: the dual-audience spec schema, the ingestion that turns source articles into specs, the two agents and their resolution logic, and the MCP tool layer the tracer uses to reach live runtime state. This is a portfolio writeup, not the production system. The production specs and the underlying business rules are proprietary and are not published here, so the sample in this folder is an illustrative, genericized version that shows the pattern rather than any real automation.

## Impact

- Cut incident triage time. "Why is this broken" now resolves to a specific repo, service, entry point, and the job's last runtime state, instead of a manual hunt.
- Cut onboarding time. New hires query the knowledge base instead of interrupting the person who remembers.
- Turned tribal knowledge into a queryable system of record across roughly 40 automations, kept current by the curator agent rather than going stale.

## Tech

Anthropic Claude (agents), MCP (Model Context Protocol) via `@modelcontextprotocol/sdk`, Node.js, Express, Zod, PostgreSQL, Redash, Redis, Python (structlog, tenacity, pydantic-settings, SQLAlchemy), Docker, Render, OAuth 2.0 / token auth.
