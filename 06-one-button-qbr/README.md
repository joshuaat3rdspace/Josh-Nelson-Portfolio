# One-Click AI Reporting (One-Button QBR)

One button on a CRM record that turns a customer's live product usage into a finished, narrated Quarterly Business Review deck in about 60 to 90 seconds.

## The problem

Quarterly Business Reviews are high-stakes customer meetings, and building the deck for one is slow, manual work. A Customer Success Manager (CSM) has to pull the customer's usage numbers from the analytics warehouse, reconcile them against the same definitions reps see in-product, compute quarter-over-quarter deltas, benchmark against peers, write the narrative, and lay it all out in slides. That is hours of copy-paste per account, it is easy to get a metric definition wrong, and it does not scale across a full book of business.

## What I built

A CRM company-record card (front end) backed by an async job runner (back end) that collapses the whole workflow into a single click.

Flow, end to end:

- **Trigger.** A React / JSX card lives on the company record in the CRM (a sidebar card plus a full-tab view). The CSM picks a window (last full quarter, current quarter to date, or a custom range) and clicks Generate. The card calls the backend over HTTPS and then polls for status, showing live progress and the last log line.
- **Enqueue.** A FastAPI service on Render accepts the request, validates it, and hands it to an in-process worker pool, returning a job id immediately so the UI never blocks.
- **Pull live metrics.** The worker resolves the account and its owner from the CRM, then queries the production analytics warehouse (via a query API over PostgreSQL) for dials, connects, conversations, meetings, talk time, per-rep detail, persona breakdowns, and a peer benchmark cohort. Long scans are chunked month by month, and any chunk that hits a statement timeout is transparently re-split into weekly windows and retried, so both tiny and very large accounts complete reliably.
- **Reconcile the definitions.** The warehouse queries deliberately mirror the exact metric definitions the customer's reps see in the product (the same connect / conversation / meeting logic, weekend exclusion, and customer-local time zone bucketing), so the QBR numbers reconcile with the in-app reporting instead of quietly disagreeing with it.
- **Narrate with Claude.** The assembled metrics are sent to Claude (Sonnet) with a tightly scoped system prompt. It returns structured JSON: an executive headline, the biggest quarter-over-quarter movement, and wins / opportunities / rep spotlights per metric, each grounded in the actual numbers and framed against the benchmark. Deterministic fallbacks fill any field if the model call fails, so a deck always renders.
- **Render the deck.** Using the Google Slides and Drive APIs (service-account auth), the worker copies a branded template and does a batched text-replacement pass to fill every slide, writing the finished deck into the requester's own folder on a shared drive. Regenerating archives the prior version instead of overwriting it.
- **Notify.** When the job finishes, the requester gets a Slack DM with a direct link to the deck.

## My role

I designed and built this end to end, as the sole engineer: the CRM UI extension (React / JSX), the FastAPI backend and job model, the warehouse query layer and its chunking / retry logic, the metric-definition reconciliation, the Claude prompt and JSON contract, the Slides / Drive rendering pipeline, and the Slack notifier. I also owned deployment (a Render blueprint with secrets injected as environment variables) and the operational runbooks for data access and ETL health.

The production implementation is proprietary to my employer, so this page is an architecture writeup. The code sample beside it is an illustrative, genericized skeleton of the async job-runner pattern (no real endpoints, ids, customer data, or secrets), not the production source.

## Impact

- Turned a multi-hour, error-prone manual deck-build into a self-serve, one-click action for the customer-success team.
- Made the output trustworthy by construction: QBR metrics match what customers already see in-product, removing a whole class of "the numbers do not agree" conversations.
- Reliable across the full range of account sizes thanks to adaptive query chunking, and safe to re-run because prior decks are archived rather than lost.

## Tech

- **Front end:** React / JSX CRM UI extension (sidebar plus custom tab), status polling, HTTPS calls to the backend.
- **Back end:** Python, FastAPI, Uvicorn, an in-process ThreadPoolExecutor job queue with a polled status API.
- **Data:** production analytics warehouse (PostgreSQL) queried through a query API, with month-to-week adaptive chunking and timeout retries.
- **AI:** Claude (Sonnet) for narrative composition against a strict JSON schema, with deterministic fallbacks.
- **Output and delivery:** Google Slides and Drive APIs (service-account auth) for deck rendering; Slack API for notifications; CRM API for account, subscription, and owner lookups.
- **Infra:** Render (blueprint deploy, health checks, secrets via environment variables).
