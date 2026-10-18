# ============================================================
# FILE: backend/app/services/scoring.py
# ============================================================

from __future__ import annotations

import re
from typing import Optional
from rapidfuzz import fuzz


def normalize_text(value: Optional[str]) -> str:
    """
    Normalize text for matching:
    - handles None safely
    - uppercase
    - remove punctuation
    - collapse spaces
    """
    if not value:
        return ""

    value = value.upper().strip()
    value = re.sub(r"[^A-Z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def similarity(a: Optional[str], b: Optional[str]) -> float:
    """
    Token-sort similarity score from 0.0 to 1.0
    """
    na = normalize_text(a)
    nb = normalize_text(b)

    if not na or not nb:
        return 0.0

    return fuzz.token_sort_ratio(na, nb) / 100.0


def exact_match(a: Optional[str], b: Optional[str]) -> bool:
    """
    Safe exact comparison after normalization.
    """
    return bool(normalize_text(a) and normalize_text(a) == normalize_text(b))


def normalized_contains(a: Optional[str], b: Optional[str]) -> bool:
    """
    Returns True if one normalized string contains another.
    """
    na = normalize_text(a)
    nb = normalize_text(b)

    if not na or not nb:
        return False

    return na in nb or nb in na


# ------------------------------------------------------------
# Address / PIN
# ------------------------------------------------------------

# Words that carry no discriminating signal in an Indian address.
_ADDRESS_STOPWORDS = {
    "SHOP", "NO", "PLOT", "HOUSE", "FLAT", "ROAD", "RD", "STREET", "ST",
    "NEAR", "OPP", "OPPOSITE", "BEHIND", "MAIN", "GALI", "MARKET", "MKT",
    "NAGAR", "COLONY", "SECTOR", "PHASE", "BLOCK", "WARD", "PO", "PS",
    "DIST", "DISTRICT", "TEH", "TEHSIL", "PIN", "PUNJAB", "INDIA",
}


def normalize_address(value: Optional[str]) -> str:
    """Normalize an address to its discriminating tokens (drops filler words)."""
    norm = normalize_text(value)
    if not norm:
        return ""
    tokens = [t for t in norm.split(" ") if t and t not in _ADDRESS_STOPWORDS]
    return " ".join(tokens)


def address_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Token-set similarity of two addresses, 0.0–1.0 (filler words removed)."""
    na = normalize_address(a)
    nb = normalize_address(b)
    if not na or not nb:
        return 0.0
    return fuzz.token_set_ratio(na, nb) / 100.0


def normalize_pin(value: Optional[str]) -> str:
    """Return a 6-digit Indian PIN, or '' if the input has no clean 6-digit code."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 6 else ""


def pin_matches(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = normalize_pin(a), normalize_pin(b)
    return bool(na) and na == nb


# ------------------------------------------------------------
# Contact details
# ------------------------------------------------------------

def normalize_phone(value: Optional[str]) -> str:
    """Last 10 digits of an Indian phone number (drops +91 / 0 prefixes), or ''."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) >= 10 else ""


def normalize_email(value: Optional[str]) -> str:
    email = str(value or "").strip().lower()
    return email if "@" in email and "." in email.rsplit("@", 1)[-1] else ""
