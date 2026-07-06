# Masterworks CRM and AI Toolkit

A suite of CRM, sales-ops, and AI tools I built to run the go-to-market machine at a high-growth outbound sales org.

## The problem

Outbound sales at scale breaks in unglamorous ways. Leads pile up faster than a manager can hand them out. Reps need to text prospects from inside the CRM, not a separate app. Every SMS has to be archived for SEC compliance. Thousands of call recordings hold answers that no one has time to listen for. HubSpot's native automation runs out of room the moment the logic gets interesting. Rather than buy a point solution for each gap, I built the tooling in-house so it fit the exact shape of the sales floor.

## What it is

A toolkit of roughly two dozen apps and scripts spanning lead routing, AI voice and SMS, call analysis, compliance archiving, and CRM automation. Everything is grounded in HubSpot as the system of record and wired to the vendors the team already used (Aircall, Bland AI, Gong, Global Relay, OpenAI, and Anthropic). Below are the strongest pieces.

## What I built

- Lead Assigner 3000 - a Flask web app that routes inbound leads to reps. It ingests lead CSVs, normalizes and parses each phone number to an area code, then assigns owners with a round-robin engine so that every lead sharing an area code lands with the same rep (better local presence and continuity). Teams and area-code-to-owner maps are managed in the UI and persisted as JSON, with round-robin state saved between runs so assignment stays balanced across uploads. Built on Flask, pandas, and a small templated front end.

- Bland AI Call Controller - a Flask service that drives AI voice calling. It reads a call list, builds per-contact Bland AI payloads (conversation pathway, timezone-aware scheduling derived from each contact's time zone, voicemail behavior, and clean metadata), and fires calls with retry/backoff via tenacity. A webhook endpoint receives call results, always logs the raw payload so partial data is never lost, and posts formatted summaries to Slack once a call's final fields arrive.

- Aircall and HubSpot SMS cards - a Next.js CRM extension that lets reps text prospects from inside a HubSpot record. A CRM card surfaces every phone property on the contact, a send API relays outbound messages to the Aircall API, and a webhook logs inbound and outbound messages back onto the HubSpot timeline as communication engagements. Phone numbers are normalized to E.164 with libphonenumber, and an Aircall number is mapped back to the owning rep so replies thread to the right person.

- JoshGPT - an early self-hosted LLM assistant, built before internal AI chat tools were common. A FastAPI backend exposes a chat API that is provider-agnostic (it can route to OpenAI or Anthropic Claude), supports file upload with text extraction so documents can be injected as context, and persists chat histories. A React and Vite front end adds a model selector, chat history, code-block rendering, and file uploads.

- Call analysis pipeline - an LLM pipeline that turns raw sales calls into structured data. It pulls a set of call IDs from a reporting query, fetches transcripts from Gong, preprocesses them, and runs a two-step GPT prompt that first reasons over the transcript and then coerces the answer into a single normalized value (for example an inferred portfolio or liquid-asset figure). A companion Hubspot Transcript Maker transcribes call recordings, including a self-hosted Whisper based path in addition to a hosted API path, renders PDF transcripts, and writes them back to HubSpot.

- HubSpot custom-code workflow actions - a library of Node.js custom-code actions that extend HubSpot workflows past the point-and-click ceiling: mapping inconsistent Aircall call tags onto standardized call-outcome fields, cleaning phone numbers and searching for duplicate cold-outreach contacts, and creating and updating tasks. Each action reads its private-app token from an environment secret and uses the official HubSpot API client.

Additional tools round out the breadth: a phone_deduper Next.js app that authenticates to HubSpot via OAuth and merges duplicate contacts by normalized phone number, a Call Report Reporter desktop-style reporting app (Python plus a local web front end) that summarizes call activity with OpenAI, a Global Relay Convert and Send job that packages sent SMS into an archive format and delivers it over SFTP for SEC recordkeeping, plus smaller utilities for Aircall number configuration, log backfills, Calendly slot counting, and recording cleanup.

## My role

Sole designer and builder of the toolkit. I owned each tool end to end: identifying the operational bottleneck, choosing the stack, integrating the vendor APIs (HubSpot, Aircall, Bland AI, Gong, Global Relay, OpenAI, and Anthropic), and shipping and maintaining it for the sales team that used it daily.

## Impact

- Replaced manual, spreadsheet-driven lead handoff with automated, area-code-aware round-robin routing that kept assignment fair and fast as volume grew.
- Let reps send and receive SMS without leaving HubSpot, with every message archived for compliance.
- Made AI voice outreach and AI call analysis usable by a non-technical sales team through simple internal apps.
- Turned thousands of unstructured call recordings into searchable transcripts and structured fields.

## Tech

Python (Flask, FastAPI, pandas, tenacity), Node.js and TypeScript, Next.js, React and Vite, HubSpot API and OAuth, Aircall API, Bland AI, Gong API, OpenAI (GPT), Anthropic (Claude), self-hosted Whisper transcription (torch and torchaudio), Slack, libphonenumber, and Global Relay SFTP archiving. Secrets are read from environment variables in every tool.

Note: this page describes tools I built in a production environment. Code shown in this repository is illustrative and genericized. No secrets, customer data, or internal identifiers are included.
