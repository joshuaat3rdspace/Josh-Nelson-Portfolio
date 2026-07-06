# Josh Nelson

**AI Operations & RevOps Systems Engineer** · San Francisco, CA
[LinkedIn](https://www.linkedin.com/in/joshmichaelnelson/)

I build the AI, data, and automation systems that a revenue org runs on. Over the past year at Nooks (an AI sales-tech startup), I designed and now operate a 16-agent internal AI system, two from-scratch MCP servers, LLM-as-judge auditing, an AI-consumable knowledge base, and the PostgreSQL data platform underneath all of it. My bias is to turn manual, error-prone work into systems that are automated, auditable, and safe for non-technical teams to use.

**About this portfolio.** The production systems below run against a company's live CRM, warehouse, and customer data, so their source is proprietary and is not published here. Each folder is an architecture writeup plus one illustrative, genericized code sample: the patterns and design decisions are real, the business logic, identifiers, and data are not. This is the right way to show this kind of work without compromising an employer.

## Selected work

| Project | What it is |
|---|---|
| [01 - Internal AI Agent System](01-ai-agent-system/) | A 16-agent Claude Code system (orchestrator plus 15 specialists) that runs RevOps investigations and operations daily, with least-privilege tools and guardrails that gate destructive actions. |
| [02 - Custom MCP Servers](02-mcp-servers/) | Two from-scratch MCP servers, including a 32-tool server with its own OAuth 2.0 authorization server and Dynamic Client Registration for per-user, domain-gated access. |
| [03 - LLM-as-Judge Auditing](03-llm-as-judge/) | A blinded LLM reviewer that scores sales calls against the team's qualification rules, enforces a 24-hour decision SLA, and surfaces mis-credited pipeline. |
| [04 - AI Knowledge Base + Process Tracing](04-ai-knowledge-base/) | 278 machine-readable process specs that let agents resolve "how does X work / why is it broken" down to repo, service, entry point, and live runtime state. |
| [05 - RevOps Data Platform](05-data-platform/) | A unified PostgreSQL warehouse fed by roughly 13 incremental ETLs, with cross-source identity resolution and snapshot-before-mutate safety on live-revenue writes. |
| [06 - One-Click AI Reporting](06-one-button-qbr/) | A CRM card that turns live product usage into a narrated Quarterly Business Review deck in about a minute, via an async job runner and Claude. |

## By the numbers

The scope of what I have built and operate (my own footprint, not company financials):

- 16-agent internal AI system: one orchestrator plus 15 domain specialists
- 2 custom MCP servers, one exposing 32 tools with OAuth 2.0 and Dynamic Client Registration
- 278 machine-readable process specs ingested from 248 source articles
- roughly 47 repositories and 79 production services operated on Render
- roughly 13 incremental ETL pipelines into one PostgreSQL warehouse
- 175+ custom CRM properties and 6 embedded CRM card apps
- 100+ teammates onboarded onto internal AI tooling; 697+ support requests handled at a 97.3% completion rate

## Tech

Claude (Opus / Sonnet) and the Anthropic API, GPT, LLM APIs, MCP server development, multi-agent orchestration (Claude Code), LLM-as-judge and structured extraction, prompt engineering · Python, Node.js, TypeScript, SQL / PostgreSQL, Bash · Redash, ETL and data warehousing · HubSpot (CRM, Automation, UI Extensions), Chili Piper, Subskribe, Gong, Slack, Notion, Zapier, Google Workspace APIs · Render, GitHub Actions, Docker, FastAPI · AWS, GCP

## A note on the code samples

Every code file here starts with an "Illustrative sample" comment. Each is a genericized skeleton that shows a real pattern (an MCP OAuth server, an LLM-as-judge pipeline, a snapshot-before-mutate ETL, an async report job runner) with placeholder config read from environment variables. They contain no real endpoints, identifiers, customer data, or secrets. Production implementations are proprietary.
