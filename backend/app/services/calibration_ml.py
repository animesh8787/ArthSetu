# ============================================================
# FILE: backend/app/services/calibration_ml.py
# Learns from reviewer decisions. A small L2-regularised logistic regression
# (plain numpy) is fitted on the evidence each decided review case carried,
# and its coefficients are turned into *suggested* matching weights. The model
# never scores a record itself: matching stays the transparent weighted sum,
# and an admin reads the per-signal explanation before applying anything.
# ============================================================

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from backend.app.db.enums import ReviewCaseStatusEnum
from backend.app.db.models.review_case import ReviewCase
from backend.app.services.matching_config_service import (
    get_weights,
    update_weights,
)

# (weight field, label, regex over the reason text, numeric?)
SIGNALS: List[Tuple[str, str, re.Pattern, bool]] = [
    ("gstin_weight", "GSTIN exact match", re.compile(r"^GSTIN exact match"), False),
    ("pan_weight", "PAN exact match", re.compile(r"^PAN exact match"), False),
    ("name_weight", "Name similarity", re.compile(r"^Name similarity ([0-9.]+)"), True),
    ("address_weight", "Address similarity", re.compile(r"^Address similarity ([0-9.]+)"), True),
    ("pin_weight", "PIN code match", re.compile(r"^PIN code match \((?!ignored)"), False),
    ("contact_weight", "Contact match", re.compile(r"^Contact match"), False),
]

MIN_DECIDED = 20
MIN_PER_CLASS = 5
# Suggestions stay within this band of the current weight so one noisy batch of
# decisions cannot swing the engine to an extreme.
CLAMP_LOW, CLAMP_HIGH = 0.25, 2.5


def _vector(reasons: List[str]) -> List[float]:
    out = []
    for _, _, pattern, numeric in SIGNALS:
        value = 0.0
        for reason in reasons:
            m = pattern.search(str(reason))
            if m:
                value = float(m.group(1)) if numeric else 1.0
                break
        out.append(value)
    return out


def _dataset(db: Session) -> Tuple[np.ndarray, np.ndarray]:
    cases = (
        db.query(ReviewCase)
        .filter(
            ReviewCase.status.in_(
                [ReviewCaseStatusEnum.APPROVED, ReviewCaseStatusEnum.REJECTED]
            )
        )
        .all()
    )
    rows, labels = [], []
    for case in cases:
        reasons = (case.evidence or {}).get("reasons") or []
        if not reasons:
            continue
        rows.append(_vector(reasons))
        labels.append(1.0 if case.status == ReviewCaseStatusEnum.APPROVED else 0.0)
    return np.array(rows, dtype=float).reshape(-1, len(SIGNALS)), np.array(labels, dtype=float)


def fit_logistic(
    X: np.ndarray, y: np.ndarray, l2: float = 0.05, iters: int = 4000, lr: float = 0.5
) -> Tuple[np.ndarray, float]:
    """Batch gradient descent on the L2-regularised log loss."""
    w = np.zeros(X.shape[1])
    b = 0.0
    n = len(y)
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w + b, -30, 30)))
        err = p - y
        w -= lr * (X.T @ err / n + l2 * w)
        b -= lr * float(err.mean())
    return w, b


def suggestion(db: Session) -> Dict[str, Any]:
    X, y = _dataset(db)
    decided = len(y)
    approved = int(y.sum())
    rejected = decided - approved

    base: Dict[str, Any] = {
        "decided": decided,
        "approved": approved,
        "rejected": rejected,
        "ready": False,
        "message": None,
        "accuracy": None,
        "signals": [],
    }
    if decided < MIN_DECIDED or min(approved, rejected) < MIN_PER_CLASS:
        base["message"] = (
            f"Needs at least {MIN_DECIDED} decided reviews with {MIN_PER_CLASS}+ approvals and "
            f"{MIN_PER_CLASS}+ rejections (have {approved} approved, {rejected} rejected)."
        )
        return base

    weights = get_weights(db)
    current = {field: getattr(weights, field) for field, *_ in SIGNALS}
    coef, intercept = fit_logistic(X, y)
    probs = 1.0 / (1.0 + np.exp(-(X @ coef + intercept)))
    base["accuracy"] = round(float(((probs >= 0.5) == (y == 1)).mean()), 4)

    # A signal that never varies in the review band (e.g. GSTIN: it is already
    # decisive) teaches nothing, so its weight is left alone.
    varies = X.std(axis=0) > 1e-9
    positive = np.where(varies, np.maximum(coef, 0.0), 0.0)
    pool = sum(current[f] for (f, *_), v in zip(SIGNALS, varies) if v)
    if positive.sum() <= 0:
        base["message"] = "No signal separates approved from rejected cases yet."
        return base

    signals = []
    for i, (field, label, _, _) in enumerate(SIGNALS):
        suggested = current[field]
        if varies[i]:
            share = float(pool * positive[i] / positive.sum())  # plain float: numpy types break SQL binds
            suggested = min(1.0, max(current[field] * CLAMP_LOW, min(share, current[field] * CLAMP_HIGH)))
        approved_mean = float(X[y == 1, i].mean())
        rejected_mean = float(X[y == 0, i].mean())
        signals.append(
            {
                "field": field,
                "label": label,
                "coefficient": round(float(coef[i]), 3),
                "approved_avg": round(approved_mean, 3),
                "rejected_avg": round(rejected_mean, 3),
                "current_weight": round(current[field], 3),
                "suggested_weight": round(suggested, 3),
                "learned": bool(varies[i]),
            }
        )
    base.update(ready=True, signals=signals, message=None)
    return base


def apply_suggestion(db: Session, updated_by: str) -> Dict[str, Any]:
    """Recomputed server-side at apply time, so a stale or edited client copy is never trusted."""
    result = suggestion(db)
    if not result["ready"]:
        raise ValueError(result["message"] or "No suggestion available")
    updates: Dict[str, Optional[float]] = {
        s["field"]: s["suggested_weight"] for s in result["signals"] if s["learned"]
    }
    return update_weights(db, updates, f"{updated_by} (learned from {result['decided']} reviews)"[:100])
