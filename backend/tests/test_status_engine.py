"""Regression tests for the activity-status inference.

Guards the indentation bug where only the last event was ever scored.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.db.enums import EntityStatusEnum
from backend.app.services.status_engine import _infer_from_events

NOW = datetime.now(timezone.utc)


def ev(event_type: str, days_ago: int, score: float = 0.0):
    when = NOW - timedelta(days=days_ago)
    return SimpleNamespace(
        event_type=event_type, score=score, occurred_at=when,
        created_at=when, event_date=when,
    )


def test_no_events_is_unknown_not_closed():
    result = _infer_from_events([])
    assert result["status"] == "UNKNOWN"
    assert result["status_enum"] is EntityStatusEnum.UNKNOWN
    assert result["confidence"] == 0.0


def test_hard_closure_signal_wins():
    events = [
        ev("gst_filed", 3),
        ev("gst_filed", 10),
        ev("closure_notice", 40),
    ]
    result = _infer_from_events(events)
    assert result["status"] == "CLOSED"
    assert result["confidence"] >= 0.95
    assert "closure" in result["reasons"][0].lower()


def test_many_recent_positive_events_is_active():
    events = [ev("gst_filed", d) for d in (2, 8, 20, 35, 50)]
    result = _infer_from_events(events)
    assert result["status"] == "ACTIVE"
    assert result["confidence"] >= 0.45


def test_old_sparse_activity_is_not_active():
    events = [ev("inspection", 400), ev("inspection", 600)]
    result = _infer_from_events(events)
    assert result["status"] in {"DORMANT", "CLOSED"}


def test_every_event_is_scored_not_just_the_last():
    """The bug: scoring loop de-indented so only events[-1] counted."""
    strong = [ev("gst_filed", d) for d in range(5, 60, 10)]  # 6 strong recent
    # If only the last event were scored, adding 20 more strong recent events
    # would not change the outcome. It should stay ACTIVE and the reason list
    # must reflect multiple events.
    result = _infer_from_events(strong)
    assert result["status"] == "ACTIVE"
    assert len(result["reasons"]) > 1

    # A single weak old event alone must NOT read as active.
    lone = _infer_from_events([ev("document_update", 500)])
    assert lone["status"] != "ACTIVE"


def test_recent_density_bonus_applies():
    events = [ev("gst_filed", d) for d in (2, 5, 9, 15)]  # >= 3 recent
    result = _infer_from_events(events)
    assert any("density bonus" in r.lower() for r in result["reasons"])
