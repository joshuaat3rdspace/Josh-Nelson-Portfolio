# Illustrative sample - genericized, not production code.
"""Async "one-click report" job runner (FastAPI).

Shape of the pattern: a CRM card POSTs a request; a background worker pulls live
metrics from an analytics warehouse, asks an LLM for narrative bullets, renders a
slide deck into the requester's Drive folder, and notifies them. The card polls a
status endpoint by job id so the UI never blocks.

Config comes from environment variables. No real endpoints, ids, customer data,
or secrets appear here; the network/render/notify bodies are stubs.
"""
from __future__ import annotations

import datetime as dt
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Config placeholders, read from env.
WAREHOUSE_API = os.environ.get("WAREHOUSE_API_URL", "https://warehouse.example.com")
WAREHOUSE_KEY = os.environ.get("WAREHOUSE_API_KEY", "")
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.example-llm.com/v1/messages")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")

app = FastAPI(title="one-click-report")

# In-memory job store: fine for short jobs on a single service; swap for a real
# store (e.g. Postgres) once concurrency or persistence matter.
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="report-worker")


class StartRequest(BaseModel):
    account_id: str
    requester_email: str


def _set(job_id: str, **fields) -> None:
    with _lock:
        _jobs.setdefault(job_id, {}).update(fields)


def fetch_metrics(account_id: str) -> dict:
    """Run a parameterized query against the analytics warehouse."""
    resp = requests.post(
        f"{WAREHOUSE_API}/query",
        headers={"Authorization": f"Key {WAREHOUSE_KEY}"},
        json={"account_id": account_id, "window": "last_quarter"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def compose_bullets(metrics: dict) -> list[str]:
    """Ask an LLM to turn the metrics into concise, data-grounded review bullets."""
    resp = requests.post(
        LLM_API_URL,
        headers={"x-api-key": LLM_API_KEY, "content-type": "application/json"},
        json={
            "model": LLM_MODEL,
            "max_tokens": 1024,
            "system": "Write concise business-review bullets grounded in the given metrics.",
            "messages": [{"role": "user", "content": str(metrics)}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["bullets"]


def render_deck(bullets: list[str], folder_id: str) -> str:
    """Copy a template deck, fill it via the Slides API into the requester's Drive
    folder, and return its share URL. Stubbed here."""
    return f"https://slides.example.com/d/{uuid.uuid4().hex}"


def notify(requester_email: str, url: str) -> None:
    """DM the requester a link to the finished deck (e.g. via a chat API)."""
    ...


def _run(job_id: str, account_id: str, requester_email: str) -> None:
    """Worker body. Runs in a pool thread; records status at each step."""
    _set(job_id, status="running")
    try:
        metrics = fetch_metrics(account_id)
        bullets = compose_bullets(metrics)
        url = render_deck(bullets, folder_id=DRIVE_FOLDER_ID)
        notify(requester_email, url)
        _set(job_id, status="done", url=url,
             finished_at=dt.datetime.utcnow().isoformat() + "Z")
    except Exception as exc:  # keep failures in the job record, don't crash the pool
        _set(job_id, status="failed", error=str(exc))


@app.post("/api/report/start")
def start(req: StartRequest):
    """Enqueue a generation job and return immediately with a job id to poll."""
    job_id = str(uuid.uuid4())
    _set(job_id, job_id=job_id, status="queued",
         created_at=dt.datetime.utcnow().isoformat() + "Z")
    _pool.submit(_run, job_id, req.account_id, req.requester_email)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/report/status")
def status(job_id: str):
    """Poll job status by id: queued / running / done (+ url) / failed (+ error)."""
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job
