"""Fail-closed crawl: homepage, directory pagination, and discovered detail links."""

import hashlib
import re
from collections import deque
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from .normalize import address

WEBSITE = "https://analyst-assessment-production.up.railway.app"


def canonical(url):
    p = urlsplit(url)
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(p.query) if k == "page" and v != "1")
    )
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip("/") or "/", query, ""))


def parse_detail(html, url):
    soup = BeautifulSoup(html, "html.parser")
    dl = soup.select_one("dl.detail")
    if not dl:
        raise ValueError(f"Detail layout missing: {url}")
    fields = {
        dt.get_text(strip=True): dt.find_next_sibling("dd") for dt in dl.select("dt")
    }
    lines = list(fields["Address"].stripped_strings)
    m = re.fullmatch(r"(.+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)", lines[-1])
    if len(lines) != 2 or not m:
        raise ValueError(f"Unrecognized address: {url}")
    offerings = [
        x.get_text(strip=True) for x in fields["Care Offerings"].select(".badge")
    ]
    if not offerings:
        raise ValueError(f"Care offerings missing: {url}")
    return dict(
        name=soup.h1.get_text(" ", strip=True),
        address=lines[0],
        city=m[1],
        state=m[2],
        zip=m[3],
        care_offerings=sorted(offerings),
        url=canonical(url),
    )


def scrape(base=WEBSITE, client=None):
    own = client is None
    client = client or httpx.Client(timeout=25, follow_redirects=False)
    todo, seen, facilities, pages = (
        deque([base + "/", base + "/communities"]),
        set(),
        {},
        [],
    )
    expected = None
    try:
        while todo:
            url = canonical(todo.popleft())
            if url in seen:
                continue
            if len(seen) >= 200:
                raise ValueError("Crawl exceeded page limit")
            seen.add(url)
            response = client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            pages.append(
                {"url": url, "sha256": hashlib.sha256(response.content).hexdigest()}
            )
            if urlsplit(url).path == "/":
                m = re.search(
                    r"serve\s+(\d+)\s+communities", soup.get_text(" ", strip=True)
                )
                expected = int(m[1]) if m else None
            if urlsplit(url).path.startswith("/communities/"):
                f = parse_detail(response.text, url)
                key = address(f)
                if key in facilities:
                    existing = facilities[key]
                    if any(existing[k] != f[k] for k in ("name", "care_offerings")):
                        raise ValueError(
                            "Conflicting website facilities at one address; manual review required"
                        )
                    existing["source_urls"] = sorted(
                        set(existing["source_urls"] + [f["url"]])
                    )
                else:
                    f["source_urls"] = [f["url"]]
                    facilities[key] = f
            for a in soup.select("a[href]"):
                link = canonical(urljoin(url, a["href"]))
                p = urlsplit(link)
                if p.netloc == urlsplit(base).netloc and (
                    p.path == "/communities"
                    or p.path.startswith("/communities/")
                    or p.path == "/about"
                ):
                    if link not in seen:
                        todo.append(link)
        if not facilities or (expected and len(facilities) < expected):
            raise ValueError(
                f"Incomplete crawl: {len(facilities)} found; homepage expects {expected}"
            )
        return {
            "facilities": sorted(facilities.values(), key=lambda f: f["name"]),
            "pages": pages,
            "homepage_expected": expected,
        }
    finally:
        if own:
            client.close()
