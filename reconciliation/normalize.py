import re
import unicodedata
from decimal import Decimal, InvalidOperation

WORDS = {
    "street": "st",
    "avenue": "ave",
    "road": "rd",
    "drive": "dr",
    "lane": "ln",
    "boulevard": "blvd",
    "court": "ct",
    "circle": "cir",
    "parkway": "pkwy",
    "pike": "pike",
    "pk": "pike",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northwest": "nw",
    "northeast": "ne",
    "southwest": "sw",
    "southeast": "se",
}


def text(value):
    value = (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    return " ".join(re.findall(r"[a-z0-9]+", value.replace("&", " and ")))


def street(value):
    return " ".join(WORDS.get(w, w) for w in text(value).split())


def address(record):
    return (
        street(record.get("billing_street", record.get("address"))),
        text(record.get("billing_city", record.get("city"))),
        text(record.get("billing_state", record.get("state"))),
        str(record.get("billing_zip", record.get("zip", "")))[:5],
    )


def money(value):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0:
            raise ValueError("Invalid billing value")
        return n
    except (InvalidOperation, TypeError):
        raise ValueError("Missing or invalid billing value; ownership change blocked")


def chow_required(account):
    # Both fields must be present and valid, even if one is zero.
    revenue, ar = (
        money(account.get("lifetime_revenue")),
        money(account.get("outstanding_ar")),
    )
    return revenue > 0 and ar > 0
