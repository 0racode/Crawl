"""FastAPI backend: job-based bulk crawl + extraction API for the Android app."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, HttpUrl

from crawler import CrawlConfig, Crawler, USER_AGENT
from extractor import extract_page
from safety import UnsafeURL, assert_public_url

DB_PATH = os.getenv("DB_PATH", "crawler.db")
API_KEY = os.getenv("API_KEY", "")  # optional shared secret; set it when exposing publicly
MAX_PAGES_HARD = int(os.getenv("MAX_PAGES_HARD", "2000"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

app = FastAPI(title="SiteCrawler API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------- storage ----------------
@contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, start_url TEXT, config TEXT, status TEXT,
            stats TEXT, error TEXT, created REAL, finished REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pages(
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, url TEXT, ok INTEGER, data TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_pages_job ON pages(job_id, id)")
        # jobs interrupted by a restart can't resume; mark them
        c.execute("UPDATE jobs SET status='interrupted' WHERE status IN ('running','queued')")


init_db()
RUNNING: dict[str, Crawler] = {}
SEM = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


def auth(x_api_key: str | None = Header(default=None), key: str | None = Query(default=None)):
    # `key` query param exists so the export link can be opened in a browser/download manager.
    if API_KEY and (x_api_key or key) != API_KEY:
        raise HTTPException(401, "Invalid or missing API key")


# ---------------- models ----------------
class CrawlRequest(BaseModel):
    start_url: HttpUrl
    max_pages: int = Field(100, ge=1, le=MAX_PAGES_HARD)
    max_depth: int = Field(3, ge=0, le=10)
    concurrency: int = Field(4, ge=1, le=10)
    delay_ms: int = Field(300, ge=0, le=10000)
    include_subdomains: bool = False
    respect_robots: bool = True
    use_sitemap: bool = True
    include_patterns: list[str] = []
    exclude_patterns: list[str] = []
    selectors: dict[str, str] = {}
    include_text: bool = True
    include_links: bool = True
    include_images: bool = True
    render_js: str = Field("auto", pattern="^(off|auto|always)$")


class ExtractRequest(BaseModel):
    url: HttpUrl
    selectors: dict[str, str] = {}
    include_text: bool = True
    include_links: bool = True
    include_images: bool = True


# ---------------- job runner ----------------
async def run_job(job_id: str, cfg: CrawlConfig):
    async with SEM:
        async def on_page(page: dict[str, Any]):
            with db() as c:
                c.execute("INSERT INTO pages(job_id,url,ok,data) VALUES(?,?,?,?)",
                          (job_id, page.get("url"), 1 if page.get("status") == "ok" else 0,
                           json.dumps(page, ensure_ascii=False)))

        async def on_status(stats: dict[str, Any]):
            with db() as c:
                c.execute("UPDATE jobs SET stats=? WHERE id=?", (json.dumps(stats), job_id))

        crawler = Crawler(cfg, on_page, on_status)
        RUNNING[job_id] = crawler
        with db() as c:
            c.execute("UPDATE jobs SET status='running' WHERE id=?", (job_id,))
        status, err = "done", None
        try:
            await crawler.run()
            if crawler.cancelled:
                status = "cancelled"
        except UnsafeURL as e:
            status, err = "failed", str(e)
        except Exception as e:  # noqa: BLE001
            status, err = "failed", f"{type(e).__name__}: {e}"
        finally:
            RUNNING.pop(job_id, None)
            with db() as c:
                c.execute("UPDATE jobs SET status=?, error=?, finished=?, stats=? WHERE id=?",
                          (status, err, time.time(), json.dumps(crawler.stats), job_id))


def job_row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"], "start_url": r["start_url"], "status": r["status"],
        "stats": json.loads(r["stats"] or "{}"), "error": r["error"],
        "created": r["created"], "finished": r["finished"],
        "config": json.loads(r["config"] or "{}"),
    }


# ---------------- routes ----------------
@app.get("/health")
def health():
    return {"ok": True, "user_agent": USER_AGENT, "active_jobs": len(RUNNING)}


@app.post("/jobs", dependencies=[Depends(auth)])
async def create_job(req: CrawlRequest):
    url = str(req.start_url)
    try:
        await assert_public_url(url)
    except UnsafeURL as e:
        raise HTTPException(400, str(e))
    for pat in req.include_patterns + req.exclude_patterns:
        try:
            __import__("re").compile(pat)
        except Exception:
            raise HTTPException(400, f"Invalid regex: {pat}")
    job_id = uuid.uuid4().hex[:12]
    cfg = CrawlConfig(start_url=url, **req.model_dump(exclude={"start_url"}))
    with db() as c:
        c.execute("INSERT INTO jobs(id,start_url,config,status,stats,created) VALUES(?,?,?,?,?,?)",
                  (job_id, url, json.dumps(req.model_dump(mode="json")), "queued",
                   json.dumps({"crawled": 0, "failed": 0, "queued": 0, "skipped": 0}), time.time()))
    asyncio.create_task(run_job(job_id, cfg))
    return {"id": job_id, "status": "queued"}


@app.get("/jobs", dependencies=[Depends(auth)])
def list_jobs(limit: int = Query(30, le=100)):
    with db() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [job_row(r) for r in rows]


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def get_job(job_id: str):
    with db() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Job not found")
    return job_row(r)


@app.get("/jobs/{job_id}/results", dependencies=[Depends(auth)])
def get_results(job_id: str, after: int = 0, limit: int = Query(50, le=200), only_ok: bool = False,
                slim: bool = True):
    """Cursor pagination: pass `next` back as `after`. slim=true trims heavy fields for list views."""
    with db() as c:
        q = "SELECT id,data FROM pages WHERE job_id=? AND id>?" + (" AND ok=1" if only_ok else "")
        rows = c.execute(q + " ORDER BY id LIMIT ?", (job_id, after, limit)).fetchall()
    items = []
    for r in rows:
        d = json.loads(r["data"])
        if slim:
            d = {k: d.get(k) for k in ("url", "title", "description", "status", "error", "depth",
                                       "word_count", "status_code", "custom") if k in d}
        d["_id"] = r["id"]
        items.append(d)
    return {"items": items, "next": rows[-1]["id"] if rows else after}


@app.get("/jobs/{job_id}/pages/{page_id}", dependencies=[Depends(auth)])
def get_page(job_id: str, page_id: int):
    with db() as c:
        r = c.execute("SELECT data FROM pages WHERE job_id=? AND id=?", (job_id, page_id)).fetchone()
    if not r:
        raise HTTPException(404, "Page not found")
    return json.loads(r["data"])


@app.get("/jobs/{job_id}/export", dependencies=[Depends(auth)])
def export(job_id: str, format: str = Query("json", pattern="^(json|ndjson)$")):
    def gen():
        with db() as c:
            rows = c.execute("SELECT data FROM pages WHERE job_id=? AND ok=1 ORDER BY id", (job_id,))
            if format == "ndjson":
                for r in rows:
                    yield r["data"] + "\n"
            else:
                yield '{"job_id":"%s","pages":[' % job_id
                first = True
                for r in rows:
                    yield ("" if first else ",") + r["data"]
                    first = False
                yield "]}"
    media = "application/x-ndjson" if format == "ndjson" else "application/json"
    return StreamingResponse(gen(), media_type=media,
                             headers={"Content-Disposition": f'attachment; filename="crawl-{job_id}.{format}"'})


@app.post("/jobs/{job_id}/cancel", dependencies=[Depends(auth)])
def cancel(job_id: str):
    c = RUNNING.get(job_id)
    if not c:
        raise HTTPException(404, "Job is not running")
    c.cancelled = True
    return {"id": job_id, "status": "cancelling"}


@app.delete("/jobs/{job_id}", dependencies=[Depends(auth)])
def delete_job(job_id: str):
    if job_id in RUNNING:
        raise HTTPException(409, "Cancel the job first")
    with db() as c:
        c.execute("DELETE FROM pages WHERE job_id=?", (job_id,))
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return {"deleted": job_id}


@app.post("/extract", dependencies=[Depends(auth)])
async def extract_single(req: ExtractRequest):
    """One-off extraction of the page the user is currently viewing."""
    import httpx
    url = str(req.url)
    try:
        await assert_public_url(url)
    except UnsafeURL as e:
        raise HTTPException(400, str(e))
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=False) as cl:
        r = None
        for _ in range(6):
            await assert_public_url(url)
            r = await cl.get(url)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = httpx.URL(url).join(r.headers["location"]).__str__()
                continue
            break
    if r is None or r.status_code >= 400:
        raise HTTPException(502, f"Upstream returned {r.status_code if r else 'no response'}")
    return extract_page(r.text, url, req.selectors, req.include_text, req.include_links, req.include_images)


@app.get("/", response_class=PlainTextResponse)
def root():
    return "SiteCrawler API. See /docs"
