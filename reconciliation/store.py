"""Adapted from lead-routing-copilot's transactional Store and append-only event pattern."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, entity TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT, at TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations(proposal_id TEXT, step TEXT, state TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(proposal_id,step));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def event(self, db, pid, kind, detail):
        db.execute(
            "INSERT INTO events(proposal_id,at,kind,detail) VALUES(?,?,?,?)",
            (pid, now(), kind, json.dumps(detail)),
        )

    def get(self, pid):
        with self.connect() as db:
            row = db.execute("SELECT body FROM proposals WHERE id=?", (pid,)).fetchone()
        if not row:
            raise KeyError(pid)
        return json.loads(row[0])

    def proposals(self):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute("SELECT body FROM proposals ORDER BY rowid")
            ]

    def save_run(self, report):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ids = {p["id"] for p in report["proposals"]}
            for row in db.execute(
                "SELECT body FROM proposals WHERE status='pending_review'"
            ).fetchall():
                p = json.loads(row[0])
                if p["id"] not in ids:
                    p["status"] = "superseded"
                    db.execute(
                        "UPDATE proposals SET status=?,body=? WHERE id=?",
                        (p["status"], json.dumps(p), p["id"]),
                    )
                    self.event(
                        db,
                        p["id"],
                        "superseded",
                        {
                            "reason": "No longer supported by latest complete source/CRM snapshot"
                        },
                    )
            added = 0
            for p in report["proposals"]:
                cursor = db.execute(
                    "INSERT OR IGNORE INTO proposals VALUES(?,?,?,?)",
                    (p["id"], p["entity"], p["status"], json.dumps(p)),
                )
                if cursor.rowcount:
                    added += 1
                    self.event(db, p["id"], "proposed", p)
            body = {**report, "new_proposals": added, "at": now()}
            db.execute(
                "INSERT INTO runs(at,body) VALUES(?,?)", (body["at"], json.dumps(body))
            )
            self.event(
                db,
                None,
                "reconciliation_completed",
                {
                    "new_proposals": added,
                    "website_facilities": report["website_facilities"],
                },
            )
        return body

    def latest(self):
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return json.loads(row[0]) if row else None

    def transition(self, pid, expected, status, kind, detail):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM proposals WHERE id=?", (pid,)).fetchone()
            if not row:
                raise KeyError(pid)
            p = json.loads(row[0])
            if p["status"] not in expected:
                raise Conflict(
                    "Proposal is not in an eligible state; refresh the queue"
                )
            # Only one approval may be executing across processes. Crash locks need manual inspection.
            if (
                status == "applying"
                and db.execute(
                    "SELECT 1 FROM proposals WHERE status IN ('applying','recovery_required') AND id!=?",
                    (pid,),
                ).fetchone()
            ):
                raise Conflict(
                    "Another approval is executing or needs recovery; inspect its audit first"
                )
            p["status"] = status
            p["last_event"] = detail
            db.execute(
                "UPDATE proposals SET status=?,body=? WHERE id=?",
                (status, json.dumps(p), pid),
            )
            self.event(db, pid, kind, detail)
        return p

    def operation(self, pid, step, state, body):
        with self.connect() as db:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?) ON CONFLICT(proposal_id,step) DO UPDATE SET state=excluded.state,body=excluded.body",
                (pid, step, state, json.dumps(body)),
            )
            self.event(db, pid, "api_" + state, {"step": step, **body})

    def operations(self, pid):
        with self.connect() as db:
            return {
                r["step"]: {"state": r["state"], **json.loads(r["body"])}
                for r in db.execute(
                    "SELECT * FROM operations WHERE proposal_id=?", (pid,)
                )
            }

    def audit(self):
        with self.connect() as db:
            return [
                {**dict(r), "detail": json.loads(r["detail"])}
                for r in db.execute("SELECT * FROM events ORDER BY seq DESC")
            ]
