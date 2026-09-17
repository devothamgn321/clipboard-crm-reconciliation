import pytest

from reconciliation import service
from reconciliation.store import Conflict


def pick(store, kind):
    return next(p for p in store.proposals() if p["classification"] == kind)


def test_pipeline_never_writes(store, crm, source):
    report = service.run(store, crm, lambda: source)
    assert report["new_proposals"] == 29 and crm.writes == []
    report = service.run(store, crm, lambda: source)
    assert report["new_proposals"] == 0 and len(store.proposals()) == 29


def test_rejection_idempotent(seeded, crm, source):
    p = pick(seeded, "missing_account")
    service.reject(seeded, p["id"], "Analyst", "Not enough evidence")
    assert service.run(seeded, crm, lambda: source)["new_proposals"] == 0
    assert seeded.get(p["id"])["status"] == "rejected" and crm.writes == []
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)


def test_direct_reparent_and_repeated_approval(seeded, crm, source):
    p = pick(seeded, "direct_reparent")
    service.apply(seeded, p["id"], "Analyst", "Verified website", crm, lambda: source)
    assert crm.get(p["current"]["account_id"])["parent_id"] == p["parent_id"]
    assert seeded.get(p["id"])["status"] == "applied"
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "Analyst", "Again", crm, lambda: source)
    assert len(crm.writes) == 1
    assert service.run(seeded, crm, lambda: source)["new_proposals"] == 0


def test_chow_preserves_entire_old_account(seeded, crm, source):
    p = pick(seeded, "chow_required")
    old = crm.get(p["current"]["account_id"])
    service.apply(seeded, p["id"], "Analyst", "Billing SOP", crm, lambda: source)
    after = crm.get(old["account_id"])
    newid = after.pop("chow_current_account")
    old.pop("chow_current_account")
    assert after == old
    assert crm.get(newid)["parent_id"] == p["parent_id"]
    assert [w[0] for w in crm.writes] == ["POST", "PATCH"]
    assert crm.writes[1][2] == {"chow_current_account": newid}
    assert service.run(seeded, crm, lambda: source)["new_proposals"] == 0


def test_recheck_billing_prevents_wrong_parent_write(seeded, crm, source):
    p = pick(seeded, "direct_reparent")
    crm.rows[p["current"]["account_id"]]["outstanding_ar"] = 100
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "Analyst", "Read evidence", crm, lambda: source)
    assert not crm.writes
    report = service.run(seeded, crm, lambda: source)
    assert seeded.get(p["id"])["status"] == "superseded"
    assert any(
        x["classification"] == "chow_required" and x["entity"] == p["entity"]
        for x in report["proposals"]
    )


def test_changed_website_blocks(seeded, crm, source):
    p = pick(seeded, "missing_account")
    for f in source["facilities"]:
        if f["url"] == p["facility"]["url"]:
            f["address"] = "999 Changed St"
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)
    assert not crm.writes


def test_new_matching_account_blocks_create(seeded, crm, source):
    p = pick(seeded, "missing_account")
    crm.rows["external"] = {
        "account_id": "external",
        "lifetime_revenue": 0,
        "outstanding_ar": 0,
        **p["changes"],
    }
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)
    assert not crm.writes


def test_partial_chow_stops_and_journals(seeded, crm, source):
    p = pick(seeded, "chow_required")
    crm.fail = "patch"
    with pytest.raises(TimeoutError):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)
    assert seeded.get(p["id"])["status"] == "recovery_required"
    assert seeded.operations(p["id"])["create"]["state"] == "verified"
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "Retry", crm, lambda: source)
    assert len(crm.writes) == 2


def test_create_timeout_never_retried(seeded, crm, source):
    p = pick(seeded, "missing_account")
    crm.fail = "create"
    with pytest.raises(TimeoutError):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)
    assert seeded.get(p["id"])["status"] == "recovery_required"
    assert seeded.operations(p["id"])["create"]["state"] == "intent"
    assert p["id"] in crm.writes[0][2]["note"]
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "Again", crm, lambda: source)
    assert len(crm.writes) == 1


def test_duplicate_requires_corrected_survivor(seeded, crm, source):
    p = next(
        p
        for p in seeded.proposals()
        if p["classification"] == "duplicate" and p["facility"]["city"] == "Kettering"
    )
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)
    assert not crm.writes


def test_missing_reviewer_no_write(seeded, crm, source):
    with pytest.raises(ValueError):
        service.apply(
            seeded, pick(seeded, "direct_reparent")["id"], " ", "R", crm, lambda: source
        )
    assert not crm.writes


def test_failed_crawl_preserves_queue(seeded, crm):
    def bad():
        raise ValueError("incomplete crawl")

    before = seeded.proposals()
    with pytest.raises(ValueError):
        service.run(seeded, crm, bad)
    assert seeded.proposals() == before and not crm.writes


def test_all_29_mock_approvals_end_state(seeded, crm, source):
    # Explicit simulated reviewer approvals; never a production batch-approve path.
    ps = sorted(seeded.proposals(), key=lambda p: p["classification"] == "duplicate")
    for p in ps:
        service.apply(
            seeded,
            p["id"],
            "Test reviewer",
            "Verified snapshot evidence",
            crm,
            lambda: source,
        )
    assert all(p["status"] == "applied" for p in seeded.proposals())
    assert len(crm.writes) == 31  # two CHOW proposals each require two calls
    report = service.run(seeded, crm, lambda: source)
    assert report["new_proposals"] == 0 and report["proposals"] == []
    assert report["current_bellhaven_children"] == 39
    assert (
        sum(
            a["parent_id"] == report["parent_id"] and a["status"] == "Active"
            for a in crm.accounts()
        )
        == 34
    )
    assert len([a for a in crm.accounts() if a.get("duplicate_of_account")]) == 7
    assert len([a for a in crm.accounts() if a.get("chow_current_account")]) == 2


def test_concurrent_claim_blocks_second_approval(seeded, crm, source):
    first = pick(seeded, "chow_required")
    second = pick(seeded, "direct_reparent")
    seeded.transition(
        first["id"], {"pending_review"}, "applying", "test_claim", {"reviewer": "A"}
    )
    with pytest.raises(Conflict):
        service.apply(seeded, second["id"], "B", "Review", crm, lambda: source)
    assert not crm.writes
    assert seeded.get(second["id"])["status"] == "pending_review"


def test_corrupt_write_response_fails_verification(seeded, crm, source):
    p = pick(seeded, "direct_reparent")
    original = crm.patch

    def bad(aid, changes):
        original(aid, changes)
        # CRM persists a wrong value: the GET read-back must catch it
        return original(aid, {"parent_id": "wrong"})

    crm.patch = bad
    with pytest.raises(Conflict):
        service.apply(seeded, p["id"], "A", "R", crm, lambda: source)
    assert seeded.get(p["id"])["status"] == "recovery_required"
