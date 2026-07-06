# Illustrative sample - genericized, not production code.
"""
Skeleton of a remote MCP server that is ALSO its own OAuth 2.0 authorization
server (Dynamic Client Registration), so a hosted LLM client connects with a URL
and nothing else - no client id or secret to paste in.

Two ideas this sample demonstrates:
  1. Registering tools of two kinds: shared-service tools (server holds the
     credential) and per-user tools (scoped to whoever is signed in).
  2. An OAuth proxy in front of an upstream IdP, gated to one domain, that issues
     dynamically-registered clients and forwards the user's own upstream token.

All endpoints, ids, and secrets are placeholders read from the environment.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware

# --- Config (placeholders; never hardcode real values) ----------------------
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://mcp.example.com")
ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "example.com")
SERVICE_API_TOKEN = os.environ.get("SERVICE_API_TOKEN", "")  # shared backend cred
UPSTREAM_API_BASE = "https://api.example.com"


def _oauth_configured() -> bool:
    return bool(OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET)


# --- Auth: OAuth proxy in front of an upstream IdP, gated to one domain ------
# The provider implements Dynamic Client Registration + /authorize + /token, so
# the LLM client registers itself at connect time and its OAuth fields stay blank.
auth = None
if _oauth_configured():
    from fastmcp.server.auth.providers.google import GoogleProvider  # example IdP

    auth = GoogleProvider(
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET,
        base_url=PUBLIC_BASE_URL,
        # Identity is required so auth never breaks; richer scopes are optional
        # and enforced per call, so tools degrade gracefully if not granted.
        required_scopes=["openid", "email", "profile"],
        valid_scopes=["openid", "email", "profile",
                      "https://www.googleapis.com/auth/calendar.readonly"],
        redirect_path="/auth/callback",
        # Only let known LLM clients complete the redirect handshake.
        allowed_client_redirect_uris=["https://*.example-llm.com/*",
                                      "http://localhost:*"],
    )


def signed_in_email() -> str | None:
    """The verified email on this request, from the upstream token claims."""
    token = get_access_token() if _oauth_configured() else None
    claims = getattr(token, "claims", None) or {} if token else {}
    email = claims.get("email")
    return email.lower() if isinstance(email, str) else None


def user_upstream_token() -> str | None:
    """The signed-in user's OWN upstream access token (for per-user API calls)."""
    token = get_access_token() if _oauth_configured() else None
    return getattr(token, "token", None) if token else None


class DomainGuard(Middleware):
    """Defense-in-depth: reject any request whose verified email is off-domain."""

    async def on_request(self, context, call_next):
        email = signed_in_email()
        if email and not email.endswith("@" + ALLOWED_DOMAIN):
            raise ValueError(f"Access restricted to @{ALLOWED_DOMAIN} accounts.")
        return await call_next(context)


mcp = FastMCP("Illustrative MCP", auth=auth)
mcp.add_middleware(DomainGuard())


# --- A shared-service tool: server's own credential, same for every user ----
@mcp.tool
async def search_records(object_type: str, query: str, limit: int = 25) -> Any:
    """Search backend records with the server-held service token."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{UPSTREAM_API_BASE}/{object_type}/search",
            params={"q": query, "limit": limit},
            headers={"Authorization": f"Bearer {SERVICE_API_TOKEN}"},
        )
    return resp.json() if resp.is_success else {"error": resp.status_code}


# --- A user-scoped tool: filtered to whoever is signed in -------------------
@mcp.tool
async def my_items(limit: int = 25) -> Any:
    """Only the signed-in user's records, resolved from their verified identity."""
    email = signed_in_email()
    if not email:
        return {"error": "not_authenticated"}
    return await search_records("items", query=f"owner:{email}", limit=limit)


# --- A user-token tool: calls an upstream API AS the signed-in user ---------
@mcp.tool
async def my_calendar_next(days: int = 7) -> Any:
    """The user's own upstream data, using their token (no service account)."""
    token = user_upstream_token()
    if not token:
        return {"error": "not_authenticated"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            params={"maxResults": 25, "timeMin": "PLACEHOLDER_ISO_TS"},
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code in (401, 403):
        return {"error": "scope_not_granted",
                "hint": "reconnect and approve calendar access"}
    return resp.json() if resp.is_success else {"error": resp.status_code}


# uvicorn entrypoint: `uvicorn illustrative_mcp_oauth_server:app`
app = mcp.http_app(path="/mcp")
