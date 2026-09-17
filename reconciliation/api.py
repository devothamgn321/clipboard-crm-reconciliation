import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import service
from .store import Conflict, Store


class Decision(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=2000)


def create_app(store=None):
    app = FastAPI(title="Clipboard CRM Reconciliation", docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    store = store or Store(os.environ.get("CRM_DB", "runtime/reconciliation.sqlite3"))
    nonce = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method not in ("GET", "HEAD"):
            if not secrets.compare_digest(
                request.headers.get("x-review-token", ""), nonce
            ):
                return JSONResponse(
                    {"detail": "Local review session required"}, status_code=403
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (Path(__file__).parent / "templates" / "ui.html").read_text()

    @app.get("/api/state")
    def state():
        return {
            "proposals": store.proposals(),
            "latest": store.latest(),
            "review_token": nonce,
            "live_configured": bool(os.environ.get("CRM_API_TOKEN")),
        }

    @app.get("/api/audit")
    def audit():
        return store.audit()

    @app.post("/api/run")
    def run():
        try:
            return service.run(store)
        except Exception as exc:
            raise HTTPException(
                409,
                "Read-only reconciliation failed: "
                + type(exc).__name__
                + ". Check token/network and source schema; the last successful queue is retained.",
            ) from exc

    @app.post("/api/proposals/{pid}/{action}")
    def review(pid: str, action: str, body: Decision):
        try:
            if action == "approve":
                return service.apply(store, pid, body.reviewer, body.rationale)
            if action == "reject":
                return service.reject(store, pid, body.reviewer, body.rationale)
            raise HTTPException(404, "Unknown action")
        except KeyError:
            raise HTTPException(404, "Proposal not found")
        except (Conflict, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                502,
                "CRM operation failed. Refresh and inspect the audit; do not retry a recovery-required item.",
            ) from exc

    return app


app = create_app()
