# Icarus - a sovereign, two-tier AI assistant

Own your AI stack end to end: cloud for the ceiling, local for daily private work at $0.

## The problem / what it is

Using frontier AI usually means renting someone else's models, sending your data to
their servers, and paying per token whether the thing is busy or idle. Icarus is my
answer to that: a personal AI stack I own end to end, built as a Third Space project.
It has two tiers behind one design. The cloud tier serves near-frontier open models for
raw ceiling; the local tier runs a private, offline-capable assistant for everyday work.
Both are OpenAI-compatible under the hood, so the same client or agent can point at
either one.

## What I built

Cloud tier (Modal serverless GPUs):
- Near-frontier open models on GPUs that scale to zero, so idle cost is literally $0.
- A single model registry is the source of truth: each entry maps a model key to its
  Hugging Face repo, GPU layout, context window, and vLLM serve flags. Redeploying with a
  different key swaps the active brain behind the SAME endpoint and the SAME client-facing
  model id, so callers never change and adding a model is a one-entry edit.
- Each engine is its own scale-to-zero app with hard cost guardrails: a container cap so a
  traffic burst can never fan out into a runaway GPU bill, scale-to-zero when idle, and
  proxy auth that rejects unauthenticated callers before a GPU ever starts.
- A FastAPI/ASGI gateway puts it behind Google sign-in locked to a company Workspace
  domain, with streaming responses, a model picker, web search, image and audio upload,
  artifacts, voice, KaTeX math, and a live admin console to tune the assistant with no
  redeploy.
- Conversations persist in Turso (libSQL over its HTTP pipeline API, no driver
  dependency), and a nightly cron job dumps the database to S3, since your conversations
  are the one thing you cannot re-download. Model weights cache once in a Modal Volume;
  the giant idle models are archived to S3 Glacier Deep Archive to stay under the free
  Volume tier and rehydrated on demand.

Local tier (a Mac, via Ollama):
- A private, offline-capable assistant. Everything runs on the machine; the only things
  that ever leave it are an optional web-search query and an explicit "Ask Claude" call.
- Web search with inline citations (Tavily), RAG over uploaded PDFs and text using LOCAL
  embeddings and cosine ranking (the documents never leave the machine), vision, voice,
  and live HTML/SVG/Mermaid artifact previews in a sandboxed frame.
- Human-approved code execution: the model proposes Python or bash, a Run button appears,
  and nothing executes until I approve it; the output is fed back so it can self-correct.
- An "Ask Claude" escape hatch escalates hard problems to Claude (Opus) through the Claude
  Code CLI on my Max subscription (not the metered API), with read-only tools so the
  consult can inspect the repo but not change it.

Shared: a dependency-light agent harness implements a plan, act, observe, self-correct
loop with tool use and cold-start retry, and gates file-write and shell tools behind human
confirmation. Because everything is OpenAI-compatible, third-party agents can reuse the
same endpoint.

## My role

Sole architect and builder. I designed the two-tier model, the model registry and cost
guardrails, the OpenAI-compatible gateway and auth, the persistence and nightly-backup
pipeline, and the local RAG, approved-execution, and escalation features, and wrote all of
the code.

## Impact

- Idle cost is $0 (GPUs scale to zero), and active cost is bounded by hard workspace caps
  plus a per-engine container cap, so a burst can never become a surprise bill.
- Data stays private: the local tier is fully offline-capable, and RAG documents are
  embedded and searched on-device.
- Model-agnostic: swapping in a newer near-frontier open model is a one-entry registry
  change behind a stable URL, so nothing downstream has to be touched.
- Demonstrates end-to-end ownership of a production-shaped AI system: GPU serving, auth,
  streaming, persistence, backup, cost control, and agent tooling.

## Tech

Modal (serverless GPUs, Volumes, Secrets, Cron), vLLM, FastAPI/ASGI, Google OAuth,
Turso/libSQL, S3 (Glacier Deep Archive), Ollama, Tavily, Claude (via CLI on a Max plan),
open models (DeepSeek, Qwen3, Qwen3-VL, GLM), Python, server-sent events, KaTeX.
