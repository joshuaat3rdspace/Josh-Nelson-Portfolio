# Revenue Integrity & Data-Quality Forensics

> Finding the silent, revenue-distorting data bugs that nobody noticed, proving them adversarially, and shipping durable guards so they stay fixed.

## The problem

In a fast-scaling revenue org, the most dangerous bugs are not the loud ones. They are the quiet ones: a dead sync that undercounts wins, an enrichment job that rewrites a live customer's domain, an auto-calculated amount that sums a ramp deal at full annual price. Nothing crashes. The dashboards still render. The numbers are just wrong, and every downstream workflow, forecast, and commission calculation inherits the error. This is the class of work I was repeatedly trusted with at Nooks: treat revenue and CRM data as a forensic surface, find the distortion, and remove the whole class of failure rather than patching one record.

## What I did

The through-line across every incident is the same pattern: snapshot before mutate, dry-run before write, and adversarially verify a finding before trusting it. Root-cause is done through property and rollup history, not guesswork, and the deliverable is a durable guard, not a one-off cleanup. Representative anonymized incidents:

- **A dead CRM-to-product sync undercounting outbound wins by ~3.5x.** A product-side "became a customer" flag had silently stopped syncing from the CRM, so outbound-win reporting showed a small fraction of reality. I diagnosed it, then ran an adversarial verifier over a 20-of-20 sampled set of discrepancies (all 20 confirmed genuine, not false positives) before redirecting all win and customer analysis onto the CRM as the source of truth.

- **A production company-deduplication / auto-merge engine over a large (~68K to 79K company) CRM.** I operate the auto-merge engine that dedupes the company database through a match-strength chokepoint (domain / LinkedIn slam-dunk versus review versus skip) with a safe unmerge and rollback path. When two unrelated companies were wrongly cross-merged through a faulty enrichment-vendor LinkedIn match bridge, I diagnosed the bad match signal and remediated it by decommissioning that vendor bridge.

- **An enrichment sync that rewrote a live customer's domain (entity collapse).** An enrichment source collapsed two entities, letting a sync overwrite a real customer's primary domain (a top-level-domain swap, customer.us to customer.com) and cascade into wrong-company workspaces, personas, and bots. I root-caused it, cleaned the corrupted record, shipped three defensive guards (expanded protected stages, a top-level-domain-swap refusal, and an open-deal check), and audited roughly 700 suspected victims out of ~2,964 candidates.

- **ARR and amount reconciliation bugs.** I traced a wrong closed-won notification to a CRM auto-calculated amount that summed ramp line items at full annual price, mapped how it cascaded through 8 downstream ARR and revenue workflows, and produced a prioritized (P0 to P3) fix plan. Separately, on composite billing orders I reverse-engineered how amount and ARR reconcile and break at close-won and established the durable fix for an amount-versus-ARR stomp race (write the reporting-ARR field alone) that the deal-desk owner's manual corrections now rely on.

- **A frozen segment-attribution snapshot system.** I built and hardened the system that froze accurate historical sales-segment attribution across roughly 79,000 companies and ~19,800 deals. After discovering the mirror workflows were structurally broken (the CRM cannot re-enroll a deal on a company-side trigger), I hardened it with a nightly reconciliation cron so the snapshot cannot silently drift.

Supporting cleanups in the same vein: proving via rollup-history forensics that a "catch-all" company was a one-time bulk associate (not a live sync) and detaching 580 spurious note associations with a full rollback map and zero errors.

## How I work

- **Snapshot before mutate.** Every production write is preceded by a captured before-state so any change is reversible.
- **Dry-run first.** Remediations run in report-only mode and print the exact diff before a single record is touched.
- **Adversarial verification.** A finding is not trusted until it survives an independent re-sample. I re-check fixed records and assert they truly changed, and I sample suspected-genuine discrepancies to rule out false positives before acting on them.
- **Forensic root-cause.** I reconstruct what happened from property and rollup history rather than from the current state alone, which separates a live sync from a one-time event and a real defect from a symptom.
- **Durable guards over cleanups.** The output is a guard, a reconciliation cron, or a redirected source of truth, so the same bug cannot silently recur.

## My role

Nooks runs a shared engineering org, so I am precise about attribution. I diagnosed, remediated, and analyzed the incidents above; where an engine or system was primarily mine to operate I say so, and where a fix supports a teammate's workflow I frame it that way. The reconciliation, audit, verification, and root-cause analysis in these incidents are my work; the ARR stomp-race fix, for example, is the durable pattern that a teammate's manual corrections depend on rather than a solo rewrite of their process.

## Impact

- Corrected a silent ~3.5x undercount so leadership's outbound-win and customer reporting reflected reality.
- Protected roughly 700 records from a domain-corruption cascade and shipped guards that block the entire failure class.
- Kept a large CRM's company graph clean through an operated auto-merge engine with a safe rollback path, and closed a cross-merge defect at its source.
- Gave Finance and RevOps a trustworthy ARR and amount reconciliation with a prioritized fix plan across the affected downstream workflows.
- Froze and reconciled historical segment attribution across tens of thousands of companies and deals so past performance stays accurate.

(Scale figures are point-in-time from internal audits; no confidential revenue figures are included here.)

## Tech

Python, PostgreSQL, SQL, HubSpot (CRM v3, Associations v4, Automations, property and rollup history), Subskribe (billing / composite orders), third-party enrichment sources, Redash, Render (cron and worker services), snapshot-and-rollback tooling, adversarial-verification and dry-run harnesses.
