"""Async same-site crawler: BFS with sitemap seeding, robots.txt, politeness, and safety checks."""
from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from extractor import extract_links, extract_page
from safety import UnsafeURL, assert_public_url

USER_AGENT = "SiteCrawlerBot/1.0 (+personal research crawler; respects robots.txt)"
SKIP_EXT = re.compile(
    r"\.(?:jpe?g|png|gif|webp|svg|ico|bmp|pdf|zip|gz|tar|rar|7z|mp[34]|avi|mov|wmv|webm|"
    r"css|js|json|xml|woff2?|ttf|eot|exe|dmg|apk|iso|docx?|xlsx?|pptx?)$",
    re.I,
)
TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_)", re.I)
MAX_BYTES = 3_000_000


@dataclass
class CrawlConfig:
    start_url: str
    max_pages: int = 100
    max_depth: int = 3
    concurrency: int = 4
    delay_ms: int = 300
    include_subdomains: bool = False
    respect_robots: bool = True
    use_sitemap: bool = True
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    selectors: dict[str, str] = field(default_factory=dict)
    include_text: bool = True
    include_links: bool = True
    include_images: bool = True
    timeout_s: float = 20.0
    render_js: str = "auto"  # off | auto (render only when static HTML looks empty) | always


def normalize(url: str) -> str:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    path = re.sub(r"/{2,}", "/", p.path or "/")
    q = urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)))
    return urlunparse((p.scheme.lower(), host + port, path, "", q, ""))


def _root(host: str) -> str:
    host = host.lower().removeprefix("www.")
    return host


def same_site(url: str, start: str, subdomains: bool) -> bool:
    a, b = _root(urlparse(url).hostname or ""), _root(urlparse(start).hostname or "")
    return a == b or (subdomains and a.endswith("." + b))


ProgressCB = Callable[[dict], Awaitable[None]]


class Crawler:
    def __init__(self, cfg: CrawlConfig, on_page: ProgressCB, on_status: ProgressCB):
        self.cfg = cfg
        self.on_page = on_page
        self.on_status = on_status
        self.cancelled = False
        self.render_unavailable: str | None = None
        self.seen: set[str] = set()
        self.queue: asyncio.Queue[tuple[str, int, str | None]] = asyncio.Queue()
        self.stats = {"crawled": 0, "failed": 0, "queued": 0, "skipped": 0}
        self.robots: dict[str, RobotFileParser | None] = {}
        self._inc = [re.compile(p) for p in cfg.include_patterns]
        self._exc = [re.compile(p) for p in cfg.exclude_patterns]
        self._last_hit = 0.0
        self._lock = asyncio.Lock()
        self._pw = None
        self._browser = None
        self._ctx = None
        self._render_sem = asyncio.Semaphore(min(cfg.concurrency, 3))

    # ---------- helpers ----------
    def _allowed_by_patterns(self, url: str) -> bool:
        if self._inc and not any(r.search(url) for r in self._inc):
            return False
        return not any(r.search(url) for r in self._exc)

    def _enqueue(self, url: str, depth: int, parent: str | None) -> bool:
        if self.stats["queued"] >= self.cfg.max_pages * 5:  # bound memory on huge sites
            return False
        if not url.startswith(("http://", "https://")) or SKIP_EXT.search(urlparse(url).path):
            return False
        n = normalize(url)
        if n in self.seen:
            return False
        if not same_site(n, self.cfg.start_url, self.cfg.include_subdomains):
            return False
        if not self._allowed_by_patterns(n):
            self.stats["skipped"] += 1
            return False
        self.seen.add(n)
        self.queue.put_nowait((n, depth, parent))
        self.stats["queued"] += 1
        return True

    async def _robots_for(self, client: httpx.AsyncClient, url: str) -> RobotFileParser | None:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin in self.robots:
            return self.robots[origin]
        rp: RobotFileParser | None = None
        try:
            await assert_public_url(origin)
            r = await client.get(origin + "/robots.txt")
            if r.status_code == 200 and "html" not in r.headers.get("content-type", "").lower():
                rp = RobotFileParser()
                rp.parse(r.text.splitlines())
                rp._sitemaps = [  # type: ignore[attr-defined]
                    ln.split(":", 1)[1].strip() for ln in r.text.splitlines()
                    if ln.lower().startswith("sitemap:")
                ]
        except Exception:
            rp = None
        self.robots[origin] = rp
        return rp

    async def _can_fetch(self, client: httpx.AsyncClient, url: str) -> bool:
        if not self.cfg.respect_robots:
            return True
        rp = await self._robots_for(client, url)
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    async def _polite_wait(self):
        async with self._lock:
            wait = self._last_hit + self.cfg.delay_ms / 1000 - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_hit = time.monotonic()

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """GET with manual redirect handling so every hop is SSRF-checked."""
        for _ in range(6):
            await assert_public_url(url)
            await self._polite_wait()
            last_exc: Exception | None = None
            for attempt in range(3):
                try:
                    r = await client.get(url)
                    break
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    last_exc = e
                    await asyncio.sleep(0.5 * (attempt + 1))
            else:
                raise last_exc or RuntimeError("fetch failed")
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code in (429, 503):
                await asyncio.sleep(min(float(r.headers.get("retry-after", 2) or 2), 10))
            r.extensions["final_url"] = url
            return r
        raise RuntimeError("Too many redirects")

    async def _sitemap_urls(self, client: httpx.AsyncClient, limit: int = 2000) -> list[str]:
        start = self.cfg.start_url
        p = urlparse(start)
        origin = f"{p.scheme}://{p.netloc}"
        candidates = [origin + "/sitemap.xml", origin + "/sitemap_index.xml"]
        rp = await self._robots_for(client, start)
        candidates += getattr(rp, "_sitemaps", []) if rp else []
        urls: list[str] = []
        todo, done = list(dict.fromkeys(candidates)), set()
        while todo and len(urls) < limit and len(done) < 15:
            sm = todo.pop(0)
            if sm in done:
                continue
            done.add(sm)
            try:
                await assert_public_url(sm)
                r = await client.get(sm)
                if r.status_code != 200:
                    continue
                root = ET.fromstring(r.content)
            except Exception:
                continue
            for loc in root.iter():
                if loc.tag.endswith("loc") and loc.text:
                    u = loc.text.strip()
                    (todo if u.endswith(".xml") else urls).append(u)
        return urls[:limit]

    # ---------- JavaScript rendering (optional, needs Playwright + Chromium) ----------
    async def _start_browser(self):
        if self.cfg.render_js == "off":
            return
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(args=["--no-sandbox"])
            self._ctx = await self._browser.new_context(user_agent=USER_AGENT, java_script_enabled=True)
        except Exception as e:  # noqa: BLE001
            self._ctx = None
            self.render_unavailable = f"{type(e).__name__}"

    async def _stop_browser(self):
        for obj in (self._ctx, self._browser):
            try:
                if obj:
                    await obj.close()
            except Exception:
                pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    @staticmethod
    def _looks_empty(html: str) -> bool:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        return len((soup.body or soup).get_text(" ", strip=True)) < 200

    async def _render(self, url: str) -> tuple[str, str, int]:
        async with self._render_sem:
            page = await self._ctx.new_page()
            try:
                async def guard(route):
                    req = route.request
                    if req.resource_type in ("image", "media", "font"):
                        return await route.abort()
                    if req.url.startswith(("data:", "blob:", "about:")):
                        return await route.continue_()
                    try:  # every sub-request and redirect hop must stay public
                        await assert_public_url(req.url)
                    except UnsafeURL:
                        return await route.abort()
                    await route.continue_()

                await page.route("**/*", guard)
                status = 200
                try:
                    resp = await page.goto(url, wait_until="networkidle",
                                           timeout=int(self.cfg.timeout_s * 1000))
                    status = resp.status if resp else 200
                except Exception:  # networkidle can time out on chatty pages; keep what rendered
                    pass
                return page.url, await page.content(), status
            finally:
                await page.close()

    # ---------- worker ----------
    async def _worker(self, client: httpx.AsyncClient):
        while not self.cancelled:
            try:
                url, depth, parent = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if self._idle():
                    return
                continue
            self._active += 1
            try:
                if self.stats["crawled"] >= self.cfg.max_pages:
                    continue
                await self._process(client, url, depth, parent)
            finally:
                self._active -= 1
                self.queue.task_done()

    def _idle(self) -> bool:
        return self.queue.empty() and self._active == 0

    async def _process(self, client, url: str, depth: int, parent: str | None):
        t0 = time.monotonic()
        try:
            if not await self._can_fetch(client, url):
                self.stats["skipped"] += 1
                await self.on_page({"url": url, "status": "blocked_by_robots", "depth": depth})
                return
            r = await self._fetch(client, url)
            final = r.extensions.get("final_url", url)
            ctype = r.headers.get("content-type", "").lower()
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            if "html" not in ctype and "xml" not in ctype:
                self.stats["skipped"] += 1
                return
            if len(r.content) > MAX_BYTES:
                raise RuntimeError("Page too large")
            html = r.text
            rendered = False
            if self._ctx and (self.cfg.render_js == "always" or
                              (self.cfg.render_js == "auto" and self._looks_empty(html))):
                if not await self._can_fetch(client, final):
                    raise RuntimeError("blocked by robots.txt")
                final, html, _st = await self._render(final)
                rendered = True
            if same_site(final, self.cfg.start_url, self.cfg.include_subdomains):
                self.seen.add(normalize(final))
            page = extract_page(
                html, final, self.cfg.selectors, self.cfg.include_text,
                self.cfg.include_links, self.cfg.include_images,
            )
            page.update(status_code=r.status_code, depth=depth, parent=parent,
                        fetched_ms=int((time.monotonic() - t0) * 1000), status="ok", rendered=rendered)
            self.stats["crawled"] += 1
            await self.on_page(page)
            if depth < self.cfg.max_depth:
                for ln in extract_links(html, final):
                    self._enqueue(ln["url"], depth + 1, final)
        except UnsafeURL as e:
            self.stats["failed"] += 1
            await self.on_page({"url": url, "status": "error", "error": str(e), "depth": depth})
        except Exception as e:  # noqa: BLE001
            self.stats["failed"] += 1
            await self.on_page({"url": url, "status": "error", "error": f"{type(e).__name__}: {e}", "depth": depth})
        await self.on_status(dict(self.stats))

    # ---------- entry ----------
    async def run(self):
        self._active = 0
        await assert_public_url(self.cfg.start_url)
        limits = httpx.Limits(max_connections=self.cfg.concurrency * 2)
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                     "Accept-Language": "en"},
            timeout=self.cfg.timeout_s, follow_redirects=False, limits=limits,
        ) as client:
            await self._start_browser()
            self._enqueue(self.cfg.start_url, 0, None)
            if self.cfg.use_sitemap:
                # Pages not linked from the start page are discovered via sitemaps (depth 1).
                for u in await self._sitemap_urls(client):
                    self._enqueue(u, 1, "sitemap")
            workers = [asyncio.create_task(self._worker(client)) for _ in range(self.cfg.concurrency)]
            try:
                await asyncio.gather(*workers)
            finally:
                await self._stop_browser()
        await self.on_status(dict(self.stats))
