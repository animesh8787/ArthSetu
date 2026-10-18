"""Review decisions: reject gives the record its own UBID, decisions are final, undo is ordered."""

import pytest

from backend.app.db.enums import ReviewCaseStatusEnum
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.audit_log import AuditLog
from backend.app.db.models.review_case import ReviewCase
from backend.app.services import corrections_service as corrections
from backend.app.services.ingestion import pending_count, process_pending
from backend.app.services.matching_engine import process_source_record
from backend.app.services.review_service import (
    ReviewConflict,
    approve_review_case,
    reject_review_case,
)


def _reject(db, seed):
    return reject_review_case(db, str(seed["review_id"]), "rev@test.local")


def test_reject_creates_own_business_and_stops_the_loop(db, seed):
    before = db.query(BusinessEntity).count()
    _reject(db, seed)

    case = db.get(ReviewCase, seed["review_id"])
    assert case.status is ReviewCaseStatusEnum.REJECTED
    assert db.query(BusinessEntity).count() == before + 1
    link = db.query(EntityRecordLink).filter_by(source_record_id=case.source_record_id).one()
    assert link.confidence is None  # founding record carries no match score

    assert pending_count(db) == 0
    assert process_pending(db)["processed"] == 0  # no new review case appears


def test_decided_case_cannot_be_decided_again(db, seed):
    _reject(db, seed)
    with pytest.raises(ReviewConflict):
        _reject(db, seed)
    with pytest.raises(ReviewConflict):
        approve_review_case(db, str(seed["review_id"]), "rev@test.local")


def test_approve_closes_sibling_cases(db, seed):
    case = db.get(ReviewCase, seed["review_id"])
    twin = ReviewCase(
        source_record_id=case.source_record_id,
        candidate_entity_id=case.candidate_entity_id,
        status=ReviewCaseStatusEnum.OPEN,
        confidence=0.6,
    )
    db.add(twin)
    db.commit()

    approve_review_case(db, str(case.id), "rev@test.local")
    db.refresh(twin)
    assert twin.status is ReviewCaseStatusEnum.CLOSED


def test_process_source_record_is_idempotent(db, seed):
    sr_id = seed["sr_match_id"]  # already linked in the seed
    links = db.query(EntityRecordLink).count()
    result = process_source_record(db, sr_id)
    assert result["reasons"] == ["Already linked"]
    assert db.query(EntityRecordLink).count() == links


def test_undo_reject_removes_the_new_business(db, seed):
    before = db.query(BusinessEntity).count()
    _reject(db, seed)
    audit = db.query(AuditLog).filter_by(action="REVIEW_REJECTED").one()

    corrections.undo(db, str(audit.id), "rev@test.local")

    assert db.query(BusinessEntity).count() == before
    assert db.get(ReviewCase, seed["review_id"]).status is ReviewCaseStatusEnum.OPEN


def test_undo_reject_refused_after_business_gained_a_link(db, seed):
    _reject(db, seed)
    audit = db.query(AuditLog).filter_by(action="REVIEW_REJECTED").one()
    link = db.query(EntityRecordLink).filter_by(source_record_id=seed["sr_new_id"]).one()
    from backend.app.db.models.source_record import SourceRecord

    other = SourceRecord(
        source_system_id=db.get(SourceRecord, seed["sr_new_id"]).source_system_id,
        external_id="second", raw_payload={}, normalized_payload={},
        extracted_name="Zephyr Logistics Pvt",
    )
    db.add(other)
    db.flush()
    db.add(EntityRecordLink(
        source_record_id=other.id, business_entity_id=link.business_entity_id, confidence=0.9,
    ))
    db.commit()

    with pytest.raises(ValueError, match="gained links"):
        corrections.undo(db, str(audit.id), "rev@test.local")


def test_exact_gstin_found_even_in_a_crowded_pin(db, seed):
    for i in range(60):
        db.add(BusinessEntity(
            ubid_code=f"UBIDX{i:05d}", legal_name=f"Noise {i}", normalized_name=f"acme noise {i}",
            pin_code="141001",
        ))
    db.commit()

    from backend.app.db.models.source_record import SourceRecord
    from backend.app.services.matching_engine import _find_candidates

    sr = SourceRecord(
        source_system_id=db.query(SourceRecord).first().source_system_id,
        external_id="crowd", raw_payload={}, normalized_payload={},
        extracted_name="Acme Steel Works", extracted_gstin="03ABCDE1234F1Z5",
        extracted_pin="141001",
    )
    db.add(sr)
    db.commit()
    assert seed["acme_id"] in {e.id for e in _find_candidates(db, sr)}
