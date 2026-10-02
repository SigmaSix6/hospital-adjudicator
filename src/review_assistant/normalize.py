"""Deterministic normalisers for dates, identifiers, names, and free text."""

from __future__ import annotations

import re
import string
from datetime import date, datetime

_BLANK_PLACEHOLDERS = {"", "-", "--", "—", "n/a", "na", "tbd", "pending", "null"}
_NAME_TITLES = {"mr", "mrs", "ms", "miss", "dr", "tn", "ny", "nn", "sdr", "prof"}
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%Y/%m/%d")


def is_blank(value: str | None) -> bool:
    return value is None or value.strip().lower() in _BLANK_PLACEHOLDERS


def parse_date(value: str | None) -> date | None:
    if is_blank(value):
        return None
    raw = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def norm_id(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "")).upper()


def norm_name(value: str | None) -> str:
    text = (value or "").lower().translate(str.maketrans(string.punctuation, " " * len(string.punctuation)))
    tokens = [t for t in text.split() if t not in _NAME_TITLES]
    return " ".join(tokens)


def norm_text(value: str | None) -> str:
    """Lower-case, unify dashes/quotes, collapse whitespace. Used for quote verification."""
    text = (value or "").lower()
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"[\u2018\u2019\u201c\u201d\"']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;,")


UNCERTAINTY_MARKERS = (
    "suspected", "possible", "probable", "rule out", "rule-out", "r/o", "not confirmed",
    "not definitive", "unconfirmed", "query", "differential",
)


def has_uncertainty_marker(text: str | None) -> bool:
    low = (text or "").lower()
    return any(m in low for m in UNCERTAINTY_MARKERS)


def find_iso_dates(text: str | None) -> list[date]:
    out: list[date] = []
    for m in re.finditer(r"\b(\d{4}-\d{2}-\d{2})\b", text or ""):
        parsed = parse_date(m.group(1))
        if parsed:
            out.append(parsed)
    return out
