# Excerpt, sanitized - not the full production source.
#
# Icarus local tier: a private, offline-capable assistant that runs on your own
# Mac via Ollama. This slice shows three of the "sovereign" features that make
# the local tier the daily driver:
#   1. RAG over uploaded docs using LOCAL embeddings (documents never leave the box)
#   2. Approved code-execution: the model proposes Python/bash, and a HUMAN clicks
#      Run before anything executes; the output is fed back so it can self-correct
#   3. An "Ask Claude" escape hatch that consults Claude via the user's Max plan
#
# Config comes from the environment or a gitignored .env; no secrets are inlined.

import io
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import httpx
from fastapi import FastAPI, Body, File, UploadFile
from fastapi.responses import JSONResponse

OLLAMA = "http://localhost:11434"      # local inference server (nothing remote)
TEXT_MODEL = "qwen3:30b-a3b"           # MoE daily driver, ~40 tok/s on an M1 Max
EMBED_MODEL = "nomic-embed-text"       # local embeddings for RAG
REPO = str(Path(__file__).parent)

app = FastAPI()


def _env():
    """Tiny .env loader (gitignored). Real secrets live in the environment, never here."""
    d = {}
    p = Path(__file__).with_name(".env")
    if p.exists():
        for ln in p.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, _, v = ln.partition("=")
                d[k.strip()] = v.strip()
    return d


ENV = _env()


# --- RAG: chat with uploaded docs using LOCAL embeddings (fully private) --------
RAG_STORE = Path(__file__).with_name("rag_store.json")


def _rag_load():
    try:
        return json.loads(RAG_STORE.read_text()) if RAG_STORE.exists() else {"chunks": []}
    except Exception:
        return {"chunks": []}


def _rag_save(d):
    RAG_STORE.write_text(json.dumps(d))


def _chunk(text, size=900, overlap=150):
    text = " ".join(text.split())
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return [c for c in out if c.strip()]


def _cos(a, b):
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


async def _embed(texts):
    """Embed locally via Ollama. The document text never leaves the machine."""
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(OLLAMA + "/api/embed", json={"model": EMBED_MODEL, "input": texts})
        return r.json().get("embeddings", [])


@app.post("/api/rag/upload")
async def rag_upload(file: UploadFile = File(...)):
    """Ingest: extract text, chunk it, embed each chunk locally, persist the vectors."""
    data = await file.read()
    name = file.filename or "doc"
    try:
        if name.lower().endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        else:
            text = data.decode("utf-8", "ignore")
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:140]})
    chunks = _chunk(text)
    if not chunks:
        return JSONResponse({"ok": False, "error": "no extractable text"})
    vecs = await _embed(chunks)
    store = _rag_load()
    for ch, v in zip(chunks, vecs):
        store["chunks"].append({"doc": name, "text": ch, "vec": v})
    _rag_save(store)
    return JSONResponse({"ok": True, "doc": name, "chunks": len(chunks)})


async def retrieve(query, k=5):
    """Query: embed the question locally, cosine-rank stored chunks, return the top-k
    as grounding context plus the source doc names for inline citation."""
    store = _rag_load()
    if not store["chunks"]:
        return "", []
    qv = (await _embed([query]) or [[]])[0]
    if not qv:
        return "", []
    top = sorted(store["chunks"], key=lambda c: _cos(qv, c["vec"]), reverse=True)[:k]
    ctx = "\n\n".join("[from " + c["doc"] + "] " + c["text"] for c in top)
    sources = []
    for c in top:
        if c["doc"] not in sources:
            sources.append(c["doc"])
    return ctx, sources[:4]


# --- Optional web search with citations (the one thing that leaves the box) ------
async def web_search(query):
    key = ENV.get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY")
    if not key or not query:
        return [], ""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post("https://api.tavily.com/search",
                             headers={"Authorization": "Bearer " + key},
                             json={"query": query, "max_results": 5, "include_answer": True})
            d = r.json()
    except Exception:
        return [], ""
    res = d.get("results", [])
    cites = [{"title": x.get("title", ""), "url": x.get("url", "")} for x in res]
    ctx = ("Quick answer: " + d["answer"] + "\n\n") if d.get("answer") else ""
    ctx += "\n\n".join(
        f"[{i+1}] {x.get('title','')} - {x.get('url','')}\n{(x.get('content') or '')[:700]}"
        for i, x in enumerate(res)
    )
    return cites, ctx


# --- Approved code-execution: the model proposes, the HUMAN approves, then it runs
@app.post("/api/run")
async def run_code(payload: dict = Body(...)):
    """Execute code the USER explicitly approved (clicked Run) in the chat. Localhost
    only, single user, per-script approval = the trust model. 30s timeout, output
    capped. Runs with your user privileges in the repo dir."""
    code = (payload.get("code") or "").strip()
    lang = payload.get("lang", "python")
    if not code:
        return JSONResponse({"output": "(empty)", "exit": 0})
    cwd = str(Path(__file__).parent)
    try:
        if lang == "python":
            r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                               text=True, timeout=30, cwd=cwd)
        else:
            r = subprocess.run(["/bin/bash", "-c", code], capture_output=True,
                               text=True, timeout=30, cwd=cwd)
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return JSONResponse({"output": (out[:8000] or "(no output)"), "exit": r.returncode})
    except subprocess.TimeoutExpired:
        return JSONResponse({"output": "(timed out after 30s)", "exit": 124})
    except Exception as e:
        return JSONResponse({"output": "run error: " + str(e), "exit": 1})


# --- Escape hatch: consult Claude (Opus) via the user's Max plan, not the metered API
@app.post("/api/ask_claude")
async def ask_claude(payload: dict = Body(...)):
    """Escalate to Claude (Opus) via the Claude Code CLI, which uses the user's Claude
    subscription (Max), NOT the metered API. Read-only tools so the consult can inspect
    the repo but not change it."""
    q = (payload.get("question") or "").strip()
    if not q:
        return JSONResponse({"answer": "(nothing to ask)", "exit": 0})
    try:
        r = subprocess.run(
            ["claude", "-p", q, "--allowedTools", "Read,Grep,Glob,WebSearch,WebFetch"],
            capture_output=True, text=True, timeout=240, cwd=str(Path(__file__).parent))
        out = (r.stdout or "").strip() or (r.stderr or "").strip() or "(no output)"
        return JSONResponse({"answer": out[:12000], "exit": r.returncode})
    except subprocess.TimeoutExpired:
        return JSONResponse({"answer": "(Claude timed out after 4 min)", "exit": 124})
    except FileNotFoundError:
        return JSONResponse({"answer": "Claude Code CLI not found; install it and log in.", "exit": 127})
    except Exception as e:
        return JSONResponse({"answer": "error: " + str(e), "exit": 1})
