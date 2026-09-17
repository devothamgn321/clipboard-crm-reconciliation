import json

import httpx
import pytest
from fastapi.testclient import TestClient

from reconciliation.api import create_app
from reconciliation.crm import CRM
from reconciliation.scraper import canonical, parse_detail, scrape


def test_local_review_requires_session_and_reason(seeded):
    client = TestClient(create_app(seeded))
    p = seeded.proposals()[0]
    assert (
        client.post(
            f"/api/proposals/{p['id']}/reject", json={"reviewer": "A", "rationale": "R"}
        ).status_code
        == 403
    )
    token = client.get("/api/state").json()["review_token"]
    assert (
        client.post(
            f"/api/proposals/{p['id']}/reject",
            headers={"x-review-token": token},
            json={"reviewer": "A", "rationale": ""},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/proposals/{p['id']}/reject",
            headers={"x-review-token": token},
            json={"reviewer": "A", "rationale": "Test rejection"},
        ).status_code
        == 200
    )
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
    page = client.get("/")
    assert "Approve &amp; apply" not in page.text and "Approve & apply" in page.text
    assert page.headers["x-frame-options"] == "DENY"


def detail(name="Test"):
    return f'<h1>{name}</h1><dl class="detail"><dt>Address</dt><dd>12 Main Street<br>Town, OH 12345</dd><dt>Care Offerings</dt><dd><span class="badge">Assisted Living</span></dd></dl>'


def test_crawl_home_only_pagination_and_dedup():
    urls = []
    pages = {
        "/": 'We serve 2 communities <a href="/communities/home-only">New</a>',
        "/communities": '<a href="/communities?page=2">Next</a>',
        "/communities?page=2": '<a href="/communities/second">Second</a><a href="/communities/home-only?utm_source=x#top">again</a>',
        "/communities/home-only": detail(),
        "/communities/second": detail("Other").replace(
            "12 Main Street", "13 Main Street"
        ),
    }

    def handler(r):
        key = r.url.raw_path.decode()
        urls.append(key)
        return httpx.Response(200, text=pages[key])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = scrape("https://test", client)
    assert len(result["facilities"]) == 2 and urls.count("/communities/home-only") == 1
    assert (
        canonical("https://test/communities/?page=1#top") == "https://test/communities"
    )


def test_incomplete_crawl_stops():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text="We serve 35 communities")
        )
    )
    with pytest.raises(ValueError, match="Incomplete crawl"):
        scrape("https://test", client)


def test_parse_failure_stops():
    with pytest.raises(ValueError):
        parse_detail("<h1>Broken page</h1>", "https://test/detail")


def test_client_pages_and_exact_write_paths(accounts):
    seen = []

    def handler(r):
        seen.append(r)
        if r.method == "GET" and r.url.path.endswith("/accounts"):
            page = int(r.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "data": accounts[(page - 1) * 100 : page * 100],
                    "total": len(accounts),
                },
            )
        if r.method == "GET":
            return httpx.Response(200, json=accounts[0])
        return httpx.Response(
            201 if r.method == "POST" else 200,
            json={"account_id": "new", **json.loads(r.content)},
        )

    c = CRM(
        "test-token",
        httpx.Client(
            base_url="https://test/api/v1/", transport=httpx.MockTransport(handler)
        ),
    )
    assert len(c.accounts()) == 121
    c.get("abc")
    c.create({"name": "new"})
    c.patch("abc", {"status": "Needs Review"})
    assert [(r.method, r.url.path) for r in seen][-3:] == [
        ("GET", "/api/v1/accounts/abc"),
        ("POST", "/api/v1/accounts"),
        ("PATCH", "/api/v1/accounts/abc"),
    ]


def test_crm_missing_token(monkeypatch):
    monkeypatch.delenv("CRM_API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        CRM()


def test_token_on_every_api_request_including_pagination_and_writes(accounts):
    seen = []

    def handler(r):
        assert r.headers["authorization"] == "Bearer personal-test-token"
        seen.append((r.method, r.url.path))
        if r.url.path.endswith("/accounts") and r.method == "GET":
            page = int(r.url.params["page"])
            return httpx.Response(
                200,
                json={"data": accounts[(page - 1) * 100 : page * 100], "total": 121},
            )
        if r.method == "GET":
            return httpx.Response(200, json=accounts[0])
        return httpx.Response(
            201 if r.method == "POST" else 200,
            json={"account_id": "new", **json.loads(r.content)},
        )

    c = CRM(
        "personal-test-token",
        httpx.Client(
            base_url="https://test/api/v1/", transport=httpx.MockTransport(handler)
        ),
    )
    assert len(c.accounts()) == 121
    c.get("x")
    c.create({"name": "new"})
    c.patch("x", {"status": "Inactive"})
    c.get("x")
    assert len(seen) == 6
    assert [r["records"] for r in c.read_receipts[:2]] == [100, 21]
    assert all(r["authenticated"] for r in c.read_receipts)


def test_auth_redirect_is_not_followed():
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(
            307, headers={"Location": "https://untrusted.example/api"}
        )

    c = CRM(
        "secret-test",
        httpx.Client(
            base_url="https://test/api/v1/",
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ),
    )
    with pytest.raises(httpx.HTTPStatusError):
        c.get("x")
    assert len(calls) == 1


def test_incomplete_or_duplicate_crm_pages_rejected(accounts):
    def handler(r):
        return httpx.Response(
            200,
            json={
                "data": accounts[:100]
                if r.url.params["page"] == "1"
                else accounts[:21],
                "total": 121,
            },
        )

    c = CRM(
        "test",
        httpx.Client(
            base_url="https://test/api/v1/", transport=httpx.MockTransport(handler)
        ),
    )
    with pytest.raises(ValueError, match="inconsistent"):
        c.accounts()
