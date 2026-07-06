# Custom MCP Servers (LLM tooling infrastructure)

Two from-scratch Model Context Protocol servers that give an LLM safe, per-user,
authenticated access to the go-to-market stack, with zero client-side config.

## The problem

Off-the-shelf connectors get you part of the way and then stop. The native CRM
connector, for example, does not surface the Projects object our team runs
onboarding out of, and there is no ready-made connector for our call-intelligence
platform at all. On top of that, "just wire the model to the CRM" is the easy 20%.
The hard 80% is auth: how do you let a whole non-technical team connect from
claude.ai without handing out shared credentials, without every user seeing every
other user's calendar, and without asking anyone to paste a client secret into a
form? I wanted an LLM that could read the real signals (calls, meetings, Slack,
deals) and write status back into the CRM, gated to the company domain, and scoped
so each person only ever touches their own data.

## What I built

A primary Python server exposing 32 tools across four platforms, plus a second
server in TypeScript to prove the pattern generalizes across languages.

Primary server (Python, FastMCP, Streamable HTTP):

- Read/write CRM access, including a Projects API the native connector does not
  expose (routed to the dated Projects API automatically when a tool is called
  with the projects object type), plus engagements and a deals-derived forecast
  view.
- Read-only call-intelligence data: transcripts, smart-tracker occurrences, call
  details, and activity stats.
- A Slack bot for reading customer channels, cross-channel search, and posting
  status digests and surveys.
- Each signed-in user's OWN Google Calendar and Google Meet (their events,
  conference records, and transcripts), called with the user's own OAuth token so
  there is no service account and no impersonation.

How the auth works (the part I am proudest of): the server is itself a full
OAuth 2.0 resource plus authorization server with Dynamic Client Registration. It
acts as an OAuth proxy in front of Google, restricted to the company Workspace
domain. Because it implements DCR, the claude.ai connector's OAuth Client ID and
Secret fields stay blank, the user just adds a URL and signs in with Google. That
is what "zero client config" means in practice. Sign-in yields two things: the
user's verified company identity and their Google access token.

- Backend data (CRM, calls, Slack) flows through shared service tokens the server
  holds and never exposes to the client.
- Identity drives three things: a domain gate (defense-in-depth middleware rejects
  any off-domain email), the "my stuff" tools (my projects, my deals, my calls,
  resolved by mapping the signed-in email to CRM and call-platform user ids), and
  per-user Calendar/Meet access using the caller's own token.
- Required scope at sign-in is identity only (openid, email, profile). The
  calendar and meet scopes are advertised as optional, granted at sign-in, and
  enforced per call, so the tools degrade gracefully (a clear hint, not a crash)
  if a user declines them.

Second server (TypeScript/Node, official MCP SDK, Express, Zod, Streamable HTTP):
a leaner server exposing call and deal data (list calls, get transcript, search
transcripts) to show multi-language MCP authorship and that the same remote,
Streamable-HTTP connector pattern holds outside Python. Both plug into claude.ai
(as a custom connector) and Claude Code with no local process to run.

## My role

Sole author of both servers. I scoped them against verified API capabilities
(for instance, confirming the call platform has no forecast endpoint and sourcing
the forecast view from CRM deals instead), designed the OAuth and per-user scoping
model, and built the tool layer, the connector clients, and the Render deploy. The
adjacent CRM data-model work (renaming stages, adding fields) was owned by other
teammates, this writeup covers the MCP servers I built.

## Impact

Turned a manual weekly ritual (a CSM opening several tools to hand-write a
date-stamped status update per project) into something an LLM can do from
conversation: pull the week's signals, draft the update, and write stage, launch
date, and a status note back to the CRM, human-in-the-loop before anything
advances. Because auth is per-user and domain-gated, it was safe to hand to a
non-technical team rather than a couple of power users, they connect once with
Google and only ever see their own data.

## Tech

Python, FastMCP, Streamable HTTP, OAuth 2.0 (resource + authorization server,
Dynamic Client Registration), Google OAuth, httpx, Starlette/Uvicorn, HubSpot API
(incl. the dated Projects API), Gong API, Slack Web API, Google Calendar + Meet
APIs, Render. Second server: TypeScript/Node, official MCP SDK, Express, Zod.
