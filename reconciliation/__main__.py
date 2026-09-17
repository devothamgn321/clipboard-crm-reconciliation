import argparse
import json
import os
from pathlib import Path

from .rules import reconcile
from .scraper import scrape
from .service import run
from .store import Store


def main():
    parser = argparse.ArgumentParser(
        description="Read-only proposal generation; approvals are only in the review UI."
    )
    parser.add_argument(
        "command", choices=["scrape", "reconcile", "demo", "serve", "summary"]
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("reconciliation.api:app", host="127.0.0.1", port=args.port)
        return
    store = Store(os.environ.get("CRM_DB", "runtime/reconciliation.sqlite3"))
    if args.command == "scrape":
        result = scrape()
        Path("runtime").mkdir(exist_ok=True)
        Path("runtime/website.json").write_text(json.dumps(result, indent=2))
        print(
            f"Discovered {len(result['facilities'])} facilities; saved runtime/website.json"
        )
        return
    if args.command == "reconcile":
        result = run(store)
    elif args.command == "demo":
        root = Path(__file__).parent.parent / "data"
        source = json.loads((root / "website-snapshot.json").read_text())
        accounts = json.loads((root / "crm-snapshot.json").read_text())["data"]
        report = reconcile(source["facilities"], accounts)
        report["crm_snapshot"] = accounts
        report["crawl"] = {
            "pages": source["pages"],
            "homepage_expected": source["homepage_expected"],
        }
        report["snapshot_mode"] = True
        result = store.save_run(report)
    else:
        result = store.latest()
    if not result:
        print("No successful run yet.")
        return
    summary = {
        k: v
        for k, v in result.items()
        if k
        not in (
            "proposals",
            "findings",
            "crm_snapshot",
            "crawl",
            "account_coverage",
            "crm_read_receipts",
        )
    }
    summary["queue_statuses"] = {
        s: sum(p["status"] == s for p in store.proposals())
        for s in sorted({p["status"] for p in store.proposals()})
    }
    print(json.dumps(summary, indent=2))
    Path("runtime").mkdir(exist_ok=True)
    Path("runtime/latest-report.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
