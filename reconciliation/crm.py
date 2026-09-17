"""Exact read endpoints and mutation adapter. No automatic mutation retries."""

import os

import httpx

BASE = "https://analyst-assessment-production.up.railway.app/api/v1"


class CRM:
    def __init__(self, token=None, client=None):
        token = token or os.environ.get("CRM_API_TOKEN")
        if not token:
            raise ValueError("Set CRM_API_TOKEN in the environment")
        self._token = token
        self.read_receipts = []
        self.client = client or httpx.Client(
            base_url=BASE + "/",
            headers={"Authorization": "Bearer " + token},
            timeout=25,
            follow_redirects=False,
        )

    def close(self):
        self.client.close()

    def request(self, method, path, **kwargs):
        # Supply Authorization on EVERY call, including injected test clients.
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = "Bearer " + self._token
        r = self.client.request(
            method, path, headers=headers, follow_redirects=False, **kwargs
        )
        r.raise_for_status()
        body = r.json()
        if method == "GET":
            self.read_receipts.append(
                {
                    "method": method,
                    "path": path,
                    "params": kwargs.get("params", {}),
                    "status_code": r.status_code,
                    "authenticated": True,
                    "records": len(body["data"])
                    if isinstance(body, dict) and isinstance(body.get("data"), list)
                    else 1,
                }
            )
        return body

    def accounts(self):
        result = []
        total = None
        for page in range(1, 101):
            body = self.request(
                "GET", "accounts", params={"page": page, "page_size": 100}
            )
            if not isinstance(body.get("data"), list) or not isinstance(
                body.get("total"), int
            ):
                raise ValueError("Invalid CRM list schema")
            if total is not None and total != body["total"]:
                raise ValueError("CRM changed during pagination; rerun")
            total = body["total"]
            rows = body["data"]
            result.extend(rows)
            if len(result) >= total:
                break
            if not rows:
                raise ValueError("CRM pagination incomplete")
        if len(result) != total or len({a["account_id"] for a in result}) != total:
            raise ValueError("CRM pagination inconsistent")
        required = {
            "account_id",
            "name",
            "parent_id",
            "billing_street",
            "billing_city",
            "billing_state",
            "billing_zip",
            "status",
            "lifetime_revenue",
            "outstanding_ar",
        }
        if any(not required.issubset(a) for a in result):
            raise ValueError("CRM account schema incomplete")
        return result

    def get(self, account_id):
        return self.request("GET", f"accounts/{account_id}")

    def create(self, payload):
        return self.request("POST", "accounts", json=payload)

    def patch(self, account_id, payload):
        return self.request("PATCH", f"accounts/{account_id}", json=payload)
