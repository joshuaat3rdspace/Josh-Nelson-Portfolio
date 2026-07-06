# LLM-as-Judge Revenue Auditing

A service that reads each deal's sales-call transcript, scores the rep's decision against the team's written rules of engagement using a top-tier Claude model, and emits a green/yellow/red verdict that drives per-rep coaching, a leadership digest, and a real-time pipeline ping.

## The problem

Reps make a 24-hour call on every SDR-booked qualification meeting: advance the deal into the pipeline, or send it back. Those decisions are high-volume and inconsistent. Some strong meetings get dropped (missed pipeline); some weak ones get advanced (pipeline that inflates the forecast and pollutes hygiene). Nobody has time to listen to every recording and grade it against the qualification bar. The result is a slow, subjective, and unauditable process that leadership cannot trust or measure, and no way to enforce the 24-hour decision SLA.

## What I built

An automated audit service that puts a top-tier Claude model in the seat of a second-opinion reviewer. For every deal that hits the qualification pipeline, the service:

1. Pulls the deal cohort from the BI/warehouse query layer and enriches it with the rep roster.
2. Fetches the matching call transcript from the call-recording platform and flattens it into a speaker-tagged timeline (every line marked as internal seller or external prospect, which is load-bearing for scoring).
3. Sends the transcript plus deal context to Claude under a long system prompt that encodes the team's qualification rules: a data-sufficiency gate, a small set of hard gates (is this the right kind of company at all), and several weighted soft signals. The exact criteria are proprietary and are not reproduced here.
4. Gets back a strict, schema-validated JSON verdict (green/yellow/red) with per-gate and per-signal evidence quoted from the transcript.
5. Persists every verdict to Postgres (append-only, current state served through a view) with a JSONL backup.
6. Routes the result: a per-rep coaching DM carrying the full reasoning, a compact leadership digest, and a real-time pipeline-value ping when a just-advanced deal looks materially mis-sized.

Two audits share one rubric and one runner: one finds missed advances (deals that should have moved but did not), the other finds over-advances (weak deals that entered the pipeline), which is the pipeline-hygiene KPI.

The design choices that make it trustworthy:

- The judge is blinded. It never sees what the rep actually decided or the deal's later stage, so it forms an independent verdict instead of rationalizing the known outcome. Tests assert the prompt stays blinded.
- Verdict logic lives in the prompt, not in Python, so the rules of engagement can be tuned without a code change and the model is swappable by config.
- Confidence rates evidence quality, not verdict severity, and is forced low under truncation, conflicting signals, or a failed sufficiency gate, so leadership can tell a well-grounded call from a guess.
- Everything degrades gracefully: a missing transcript trips the sufficiency gate instead of crashing, and every downstream write (Slack, pricing, CRM) sits behind a feature flag that no-ops when its env is unset.

## My role

I built and operate this system as part of the RevOps team at Nooks. The rules of engagement themselves were authored by RevOps leadership; I designed and built the judging service around them: the prompt and rubric engineering, the structured-output schema, the transcript rendering and speaker attribution, the Postgres model, the notification routing, and a FastAPI on-demand endpoint for real-time single-deal audits. It is one of three repos in a shared audit suite (this judge, a leadership dashboard, and a Slack assistant); I own this repo and its integration with the other two.

## Impact

- Turns a subjective, unauditable 24-hour decision into a consistent, evidence-backed second opinion on every qualified meeting, with the decision SLA now measurable.
- Surfaces both missed pipeline and over-credited pipeline, giving leadership a hygiene KPI they can actually track.
- Delivers coaching to reps with the full transcript-grounded reasoning, not just a score, so each nudge is defensible.
- Runs unattended on a nightly and weekly schedule across sales segments, with a real-time path for just-advanced deals.

## Tech

Python, Anthropic Claude (Opus-tier model, adaptive thinking plus schema-enforced JSON outputs), FastAPI, PostgreSQL, Docker, and Render for deployment. Integrations with the CRM, the call-recording platform, the BI/warehouse query layer, and Slack. Config-driven and secret-free by construction (all credentials read from environment variables).
