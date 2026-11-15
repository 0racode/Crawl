"""General-purpose structured extraction from an HTML page -> JSON-serialisable dict."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}(?!\d)")


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _meta(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in soup.find_all("meta"):
        key = m.get("property") or m.get("name") or m.get("itemprop")
        val = m.get("content")
        if key and val:
            out[key.strip().lower()] = val.strip()
    return out


def _json_ld(soup: BeautifulSoup) -> list[Any]:
    items: list[Any] = []
    for s in soup.find_all("script", type="application/ld+json"):
        raw = (s.string or s.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items.extend(data if isinstance(data, list) else [data])
    return items


def _tables(soup: BeautifulSoup, limit: int = 10) -> list[dict[str, Any]]:
    tables = []
    for t in soup.find_all("table")[:limit]:
        rows = []
        for tr in t.find_all("tr"):
            cells = [_text(c) for c in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append({"headers": rows[0], "rows": rows[1:]})
    return tables


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        url = urldefrag(urljoin(base_url, href))[0]
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "text": _text(a)[:200]})
    return out


def extract_page(
    html: str,
    url: str,
    selectors: dict[str, str] | None = None,
    include_text: bool = True,
    include_links: bool = True,
    include_images: bool = True,
    max_text_chars: int = 20000,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    meta = _meta(soup)
    data: dict[str, Any] = {
        "url": url,
        "title": _text(soup.title) or meta.get("og:title", ""),
        "description": meta.get("description") or meta.get("og:description", ""),
        "canonical": (soup.find("link", rel="canonical") or {}).get("href"),
        "language": (soup.html or {}).get("lang") if soup.html else None,
        "open_graph": {k: v for k, v in meta.items() if k.startswith("og:")},
        "twitter": {k: v for k, v in meta.items() if k.startswith("twitter:")},
        "headings": {
            f"h{i}": [_text(h) for h in soup.find_all(f"h{i}")][:50] for i in (1, 2, 3)
        },
        "json_ld": _json_ld(soup),
        "tables": _tables(soup),
    }

    if include_links:
        data["links"] = extract_links(html, url)
    if include_images:
        imgs = []
        for im in soup.find_all("img", src=True)[:200]:
            imgs.append({"src": urljoin(url, im["src"]), "alt": im.get("alt", "")})
        data["images"] = imgs

    # Custom CSS selectors: {"price": ".price", "title": "h1"}; "sel@attr" reads an attribute.
    if selectors:
        custom: dict[str, Any] = {}
        for name, sel in selectors.items():
            attr = None
            if "@" in sel:
                sel, attr = sel.rsplit("@", 1)
            try:
                els = soup.select(sel.strip())
            except Exception:
                custom[name] = None
                continue
            vals = [(e.get(attr) if attr else _text(e)) for e in els]
            vals = [v for v in vals if v]
            custom[name] = vals[0] if len(vals) == 1 else vals
        data["custom"] = custom

    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    body = soup.body or soup
    text = _text(body)
    data["emails"] = sorted(set(EMAIL_RE.findall(text)))[:50]
    data["phones"] = sorted({p.strip() for p in PHONE_RE.findall(text) if len(re.sub(r"\D", "", p)) >= 9})[:50]
    data["word_count"] = len(text.split())
    if include_text:
        data["text"] = text[:max_text_chars]
    return data
