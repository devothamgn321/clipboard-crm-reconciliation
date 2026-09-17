import copy
import json
from pathlib import Path

import pytest

from reconciliation.rules import reconcile
from reconciliation.store import Store

DATA = Path(__file__).parents[1] / "data"


@pytest.fixture
def source():
    return json.loads((DATA / "website-snapshot.json").read_text())


@pytest.fixture
def accounts():
    return json.loads((DATA / "crm-snapshot.json").read_text())["data"]


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.sqlite3")


class FakeCRM:
    def __init__(self, accounts):
        self.rows = {a["account_id"]: copy.deepcopy(a) for a in accounts}
        self.writes = []
        self.fail = None

    def accounts(self):
        return copy.deepcopy(list(self.rows.values()))

    def get(self, aid):
        return copy.deepcopy(self.rows[aid])

    def patch(self, aid, payload):
        self.writes.append(("PATCH", aid, copy.deepcopy(payload)))
        if self.fail == "patch":
            raise TimeoutError("simulated failure")
        self.rows[aid].update(payload)
        return self.get(aid)

    def create(self, payload):
        aid = f"NEW{len(self.rows)}"
        self.writes.append(("POST", aid, copy.deepcopy(payload)))
        self.rows[aid] = {
            "account_id": aid,
            "lifetime_revenue": 0,
            "outstanding_ar": 0,
            "phone": "",
            "chow_current_account": "",
            "duplicate_of_account": "",
            **payload,
        }
        if self.fail == "create":
            raise TimeoutError("response lost after server committed")
        return self.get(aid)

    def close(self):
        pass


@pytest.fixture
def crm(accounts):
    return FakeCRM(accounts)


@pytest.fixture
def report(source, accounts):
    return reconcile(source["facilities"], accounts)


@pytest.fixture
def seeded(store, report):
    store.save_run(report)
    return store
