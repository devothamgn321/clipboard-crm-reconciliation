import copy

import pytest

from reconciliation.normalize import chow_required, street
from reconciliation.rules import material, reconcile


@pytest.mark.parametrize(
    "a,b",
    [
        ("1120 West Main Street", "1120 W Main St."),
        ("1250 Northwest Franklin St", "1250 NW Franklin Street"),
        ("3313 Wilmington Pk", "3313 Wilmington Pike"),
        ("199 Barks Road West", "199 Barks Rd W"),
    ],
)
def test_normalization(a, b):
    assert street(a) == street(b)


def test_units_not_erased():
    assert street("12 Main St Suite 2") != street("12 Main St Suite 3")


@pytest.mark.parametrize(
    "rev,ar,result", [(1, 1, True), (100, 0, False), (0, 20, False), (0, 0, False)]
)
def test_chow_boolean(rev, ar, result):
    assert chow_required({"lifetime_revenue": rev, "outstanding_ar": ar}) == result


@pytest.mark.parametrize("value", [None, "bad", "NaN", "Infinity", -1])
def test_invalid_billing_fails_closed(value):
    with pytest.raises(ValueError):
        chow_required({"lifetime_revenue": value, "outstanding_ar": 0})


def test_live_snapshot_counts(report):
    assert report["website_facilities"] == 35
    assert report["current_bellhaven_children"] == 29
    assert report["classification_counts"] == {
        "missing_account": 4,
        "direct_reparent": 4,
        "duplicate": 7,
        "field_update": 8,
        "ambiguous": 1,
        "chow_required": 2,
        "stale_needs_review": 3,
    }
    assert report["facility_classification_counts"]["unchanged"] == 16
    assert all(p["status"] == "pending_review" for p in report["proposals"])


def test_exact_address_matches_renamed_facility(report):
    p = next(
        p
        for p in report["proposals"]
        if p["current"] and p["current"]["name"] == "Riverbend Manor Care Center"
    )
    assert p["changes"] == {"name": "Bellhaven of Chagrin Falls"}


def test_wrong_parent_zero_ar_direct(report):
    p = next(
        p
        for p in report["proposals"]
        if (p["facility"] or {}).get("name") == "Bellhaven Crossings of Lima"
    )
    assert p["classification"] == "direct_reparent" and p["changes"] == {
        "parent_id": report["parent_id"]
    }


def test_chow_cases(report):
    ps = [p for p in report["proposals"] if p["classification"] == "chow_required"]
    assert {p["facility"]["name"] for p in ps} == {
        "Bellhaven of Marietta",
        "Bellhaven of Tiffin",
    }
    assert all(chow_required(p["current"]) for p in ps)


def test_duplicates(report):
    ps = [p for p in report["proposals"] if p["classification"] == "duplicate"]
    assert len(ps) == 7
    assert len({p["facility"]["name"] for p in ps}) == 5
    assert all(
        p["changes"]["status"] == "Inactive"
        and p["changes"]["duplicate_of_account"] == p["survivor_id"]
        and "parent_id" not in p["changes"]
        for p in ps
    )


def test_stale_and_ambiguous(report):
    ps = [
        p
        for p in report["proposals"]
        if p["classification"] in ("stale_needs_review", "ambiguous")
    ]
    assert {p["current"]["billing_city"] for p in ps} == {
        "Alliance",
        "Coldwater",
        "Sandusky",
        "Ashtabula",
    }
    assert all(
        p["changes"]["status"] == "Needs Review" and "parent_id" not in p["changes"]
        for p in ps
    )


def test_decoys_do_not_match(report):
    ps = [p for p in report["proposals"] if p["classification"] == "missing_account"]
    assert {p["facility"]["name"] for p in ps} == {
        "Amberly Manor",
        "Bellhaven at Union Square",
        "Bellhaven of Batavia",
        "Bellhaven of Carlisle",
    }


def test_zip_correction(report):
    p = next(
        p
        for p in report["proposals"]
        if p["current"] and p["current"]["billing_city"] == "Portsmouth"
    )
    assert p["changes"] == {"billing_zip": "45662"}


def test_both_duplicate_histories_ambiguous(source, accounts):
    for a in accounts:
        if a["billing_city"] == "Owosso":
            a["lifetime_revenue"] = 100
    ps = reconcile(source["facilities"], accounts)["proposals"]
    assert all(
        p["classification"] == "ambiguous"
        for p in ps
        if p["current"] and p["current"]["billing_city"] == "Owosso"
    )


def test_timestamp_not_material(accounts):
    a = copy.deepcopy(accounts[0])
    before = material(a)
    a["updated_at"] = "tomorrow"
    assert material(a) == before


def test_every_one_of_121_accounts_has_a_disposition(report, accounts):
    coverage = report["account_coverage"]
    assert report["accounts_considered"] == 121
    assert len(coverage) == len({a["account_id"] for a in coverage}) == 121
    assert {a["account_id"] for a in coverage} == {a["account_id"] for a in accounts}
    assert all(a["considered"] and a["reason"] for a in coverage)
    assert sum(report["coverage_counts"].values()) == 121
    assert any(
        a["name"] == "Amberly Manor" and a["disposition"] == "unrelated"
        for a in coverage
    )
