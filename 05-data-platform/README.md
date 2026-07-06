# RevOps Data Platform (Warehouse + ETL)

One unified PostgreSQL warehouse that every dashboard, ETL, and bot at Nooks joins against, fed by roughly 13 incremental pipelines with snapshot-before-mutate safety on anything that touches live revenue data.

> A note on this writeup: the production system is proprietary, so this page describes the architecture and shows illustrative, genericized code. The patterns are real; the specifics (endpoints, IDs, business rules) are not published here.

## The problem

RevOps data lived in silos: the CRM held pipeline and custom objects, a product-analytics tool held usage events, a billing system held subscriptions and invoices, and a separate application database held its own slice of truth. Answering a question like "which accounts are expanding, and are they healthy in-product?" meant exporting three or four systems and reconciling them by hand. There was no shared identity layer, no single place to query, and no safe way to write derived revenue data back without risking the numbers leadership depends on.

## What I built

**db_ultra**, a production data platform on Render that mirrors every source into one analytics database and exposes it through Redash OSS for self-service querying.

- **Layered schemas.** A `raw` schema holds immutable JSON payloads plus load metadata per source and stream. Typed, join-ready schemas (`crm`, `product`, `billing`, and a mirrored external Postgres) sit on top. A `common` schema does cross-source identity resolution, and a `meta` schema tracks ETL runs, watermarks, and data-quality checks.
- **Identity resolution.** Records are stitched across sources on normalized lowercase email, CRM RecordIDs, and company domain, with billing linked to CRM opportunities by ID. That layer is what makes a single "person 360" or "account 360" query possible.
- **Incremental ETLs.** Roughly 13 containerized Python jobs run on hourly and daily cron. Each one is idempotent (upsert via `INSERT ... ON CONFLICT`), incremental (high-watermark per source/stream/key in `meta.watermarks`), rate-limit aware (exponential backoff with jitter plus a token-bucket limiter), and observable (every run logs status and row counts to `meta.etl_runs`).
- **Schema drift handling.** When the CRM adds a property (175+ tracked), the sync detects it and adds the column online with a per-statement lock timeout and retry, so DDL never blocks live readers. Removed properties are kept, not dropped, to preserve history.
- **Safe writes to live data.** Any job that writes derived revenue data runs a snapshot-before-mutate pattern: snapshot the target rows, compute a diff, and in dry-run mode just report it. On apply it writes inside a transaction, verifies with a read-back, and rolls back on any mismatch. The illustrative version of this is in the code sample beside this README.

## My role

I designed and built this end to end: the schema layering, the identity-resolution model, the ETL framework (config, structured logging, DB access, watermarks, backoff), each source connector, the Redash deployment, and the operational runbooks and monitoring. It is the central source of truth the rest of my RevOps systems (agents, bots, dashboards) query against.

## Impact

- Collapsed four siloed systems into one queryable warehouse, so cross-source questions became a single SQL query instead of a manual export-and-reconcile exercise.
- Gave the RevOps team self-service analytics through Redash instead of one-off data pulls.
- Made live-revenue writes safe by default: nothing mutates production numbers without a snapshot, a dry-run diff, and a verified read-back it can roll back.
- Became the join target for downstream automation across the org, which is the real measure of trust in the data.

## Tech

Python 3.11, PostgreSQL, psycopg2 / SQLAlchemy, Redash OSS, Redis, Docker, Render (cron workers), structlog, tenacity, pydantic-settings. Sources integrated over their APIs and an external Postgres over a proxy. Secrets are read from environment variables, never committed.
