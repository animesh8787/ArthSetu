# ============================================================
# FILE: backend/app/services/matching_engine.py
# ============================================================

from __future__ import annotations
from uuid import UUID
import json
import enum
from datetime import datetime, date
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.services.scoring import (
    address_similarity,
    normalize_address,
    normalize_email,
    normalize_phone,
    normalize_text,
    normalize_pin,
    pin_matches,
    similarity,
)
from backend.app.services.matching_config_service import (
    MatchingWeights,
    get_weights,
)
from backend.app.services.ubid_service import generate_ubid

from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.audit_log import AuditLog

from backend.app.db.enums import (
    LinkDecisionEnum,
    ReviewCaseStatusEnum,
    AuditActorEnum,
    EntityStatusEnum,
)

# ============================================================
# THRESHOLDS & WEIGHTS
#   GSTIN alone is definitive (unique government id).
#   PAN alone is a strong anchor (same legal entity / proprietor).
#   Name + address + PIN together corroborate enough for human review
#   but never enough for an automatic link without an id anchor.
#
#   These used to be fixed module constants; they now live in the
#   `matching_config` table (single row, defaults match the original
#   values) so an admin can calibrate them from reviewer approve/reject
#   feedback — see matching_config_service.py and GET /matching/calibration.
#   A shared PIN only counts once the names are at least loosely related —
#   a bare PIN covers thousands of businesses.
# ============================================================

# Filler tokens that make a poor blocking key.
_NAME_STOPWORDS = {"M", "S", "MS", "MESSRS", "THE"}


# ============================================================
# RESPONSE DTO
# ============================================================

@dataclass
class MatchResult:
    decision: str
    confidence: float
    business_entity_id: Optional[str]
    reasons: List[str]

##Normalize JSON-ish DB values into a dict.
def _as_dict(value):
    """
    Normalize JSON-ish DB values into a dict.

    Handles:
    - dict -> returned as-is
    - JSON string -> parsed into dict
    - None / invalid / other -> {}
    """
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    return {}
    ##json normaization
def _json_safe(value):
    """
    Recursively convert Python objects into JSON-serializable values.
    Handles UUID, Enum, datetime/date, dict, list, tuple, set.
    """
    if value is None:
        return None

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, enum.Enum):
        return value.value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    return value
# ============================================================
# PUBLIC ENTRYPOINT
# ============================================================

def process_source_record(
    db: Session,
    source_record_id: UUID | str,
) -> Dict[str, Any]:
    """
    Main entrypoint.

    Accepts a new source_record and decides:

    1. AUTO_LINK
    2. REVIEW
    3. NEW_ENTITY
    """

    if not isinstance(source_record_id, UUID):
        try:
            source_record_id = UUID(str(source_record_id))
        except (ValueError, TypeError):
            raise ValueError("Invalid source_record_id")

    source_record = db.get(SourceRecord, source_record_id)
    if not source_record:
        raise ValueError("SourceRecord not found")

    # Idempotent: a record that is already linked or awaiting review keeps its decision.
    settled = _existing_decision(db, source_record.id)
    if settled is not None:
        return _to_dict(settled)

    try:
        weights = get_weights(db)
        candidates = _find_candidates(db, source_record)

        if not candidates:
            result = _create_new_entity(db, source_record)
            db.commit()
            return _to_dict(result)

        best_entity, score, reasons = _best_candidate(source_record, candidates, weights)

        if score >= weights.auto_link_threshold:
            result = _auto_link(
                db=db,
                source_record=source_record,
                entity=best_entity,
                score=score,
                reasons=reasons,
            )

        elif score >= weights.review_threshold:
            result = _create_review_case(
                db=db,
                source_record=source_record,
                entity=best_entity,
                score=score,
                reasons=reasons,
            )

        else:
            result = _create_new_entity(
                db, source_record, best_score=score, best_reasons=reasons
            )

        db.commit()
        return _to_dict(result)

    except Exception:
        db.rollback()
        raise


def _existing_decision(db: Session, source_record_id: UUID) -> Optional[MatchResult]:
    link = (
        db.query(EntityRecordLink)
        .filter(EntityRecordLink.source_record_id == source_record_id)
        .first()
    )
    if link is not None:
        return MatchResult(
            decision=link.decision.name if link.decision else "AUTO_LINK",
            confidence=link.confidence or 0.0,
            business_entity_id=link.business_entity_id,
            reasons=["Already linked"],
        )
    case = (
        db.query(ReviewCase)
        .filter(
            ReviewCase.source_record_id == source_record_id,
            ReviewCase.status == ReviewCaseStatusEnum.OPEN,
        )
        .first()
    )
    if case is not None:
        return MatchResult(
            decision="REVIEW",
            confidence=case.confidence or 0.0,
            business_entity_id=case.candidate_entity_id,
            reasons=["Already in the review queue"],
        )
    return None


# ============================================================
# CANDIDATE BLOCKING
# ============================================================

def _name_block_tokens(name: str) -> List[str]:
    """The most discriminating leading tokens of a name, past filler like 'M/S'."""
    tokens = [t for t in name.split(" ") if t and t not in _NAME_STOPWORDS]
    return tokens[:2]


def _find_candidates(
    db: Session,
    source_record: SourceRecord,
) -> List[BusinessEntity]:
    """Conservative blocking — avoid full-table scans while catching noisy names."""

    name = normalize_text(source_record.extracted_name)
    source_pin = normalize_pin(source_record.extracted_pin)
    src_pan = source_record.extracted_pan or _pan_from_gstin(source_record.extracted_gstin)

    # Exact government ids first, so a crowded PIN or name prefix can never push the
    # true owner of a GSTIN/PAN out of the candidate window.
    exact = []
    if source_record.extracted_gstin:
        exact.append(BusinessEntity.gstin == source_record.extracted_gstin)
    if src_pan:
        exact.append(BusinessEntity.pan == src_pan)
        exact.append(BusinessEntity.gstin.like(f"__{src_pan}%"))
    found: List[BusinessEntity] = (
        db.query(BusinessEntity).filter(or_(*exact)).limit(50).all() if exact else []
    )

    conditions = []
    for token in _name_block_tokens(name):
        conditions.append(BusinessEntity.normalized_name.ilike(f"{token}%"))
        conditions.append(BusinessEntity.normalized_name.ilike(f"% {token}%"))

    if source_pin:
        conditions.append(BusinessEntity.pin_code == source_pin)

    if conditions and len(found) < 50:
        seen = {e.id for e in found}
        fuzzy = (
            db.query(BusinessEntity)
            .filter(or_(*conditions))
            .limit(50)
            .all()
        )
        found.extend(e for e in fuzzy if e.id not in seen)

    return found[:50]


# ============================================================
# SCORING
# ============================================================

def _best_candidate(
    source_record: SourceRecord,
    candidates: List[BusinessEntity],
    weights: MatchingWeights,
) -> Tuple[BusinessEntity, float, List[str]]:

    best_score = -1.0
    best_entity = candidates[0]
    best_reasons: List[str] = []

    for entity in candidates:
        score, reasons = _score_candidate(source_record, entity, weights)

        if score > best_score:
            best_score = score
            best_entity = entity
            best_reasons = reasons

    return best_entity, round(best_score, 4), best_reasons


def _pan_from_gstin(gstin: Optional[str]) -> Optional[str]:
    """An Indian GSTIN embeds the PAN at positions 2..12."""
    if gstin and len(gstin) >= 12:
        return gstin[2:12].upper()
    return None


def _score_candidate(
    source_record: SourceRecord,
    entity: BusinessEntity,
    weights: MatchingWeights,
    ) -> Tuple[float, List[str]]:

    score = 0.0
    reasons: List[str] = []

    sr_payload = _as_dict(source_record.normalized_payload)

    src_gstin = source_record.extracted_gstin
    src_pan = source_record.extracted_pan or _pan_from_gstin(src_gstin)
    src_address = source_record.extracted_address or sr_payload.get("address")
    src_pin = source_record.extracted_pin or sr_payload.get("pin_code")

    # --- Strong identifiers ---------------------------------------------
    if src_gstin and entity.gstin and src_gstin == entity.gstin:
        score += weights.gstin_weight
        reasons.append("GSTIN exact match")

    entity_pan = entity.pan or _pan_from_gstin(entity.gstin)
    if src_pan and entity_pan and src_pan == entity_pan:
        score += weights.pan_weight
        reasons.append("PAN exact match")

    # --- Name --------------------------------------------------------------
    name_score = similarity(source_record.extracted_name, entity.legal_name)
    score += weights.name_weight * name_score
    reasons.append(f"Name similarity {round(name_score, 2)}")

    # --- Address --------------------------------------------------------
    if src_address and entity.address:
        addr_score = address_similarity(src_address, entity.address)
        if addr_score > 0:
            score += weights.address_weight * addr_score
            reasons.append(f"Address similarity {round(addr_score, 2)}")

    # --- PIN code (only meaningful alongside a plausible name) ---------
    if pin_matches(src_pin, entity.pin_code):
        if name_score >= weights.pin_requires_name_sim:
            score += weights.pin_weight
            reasons.append(f"PIN code match ({normalize_pin(src_pin)})")
        else:
            reasons.append("PIN code match (ignored — names unrelated)")

    # --- Contact details (a shared agency number only counts alongside a related name) ---
    if name_score >= weights.pin_requires_name_sim:
        phone = normalize_phone(source_record.extracted_phone)
        email = normalize_email(source_record.extracted_email)
        if phone and phone == normalize_phone(entity.phone):
            score += weights.contact_weight
            reasons.append("Contact match (phone)")
        elif email and email == normalize_email(entity.email):
            score += weights.contact_weight
            reasons.append("Contact match (email)")

    score = min(round(score, 4), 1.0)
    return score, reasons

# ============================================================
# DECISIONS
# ============================================================

def _auto_link(
    db: Session,
    source_record: SourceRecord,
    entity: BusinessEntity,
    score: float,
    reasons: List[str],
) -> MatchResult:

    _fill_contact(entity, source_record)
    link = EntityRecordLink(
        source_record_id=source_record.id,
        business_entity_id=entity.id,
        confidence=score,
        decision=LinkDecisionEnum.AUTO_LINK,
        explanation=reasons,
    )

    db.add(link)

    _audit(
        db,
        entity_type="business_entity",
        entity_id=str(entity.id),
        action="AUTO_LINK",
        after_state=_json_safe(
            {
                "source_record_id": source_record.id,
                "confidence": score,
                "reasons": reasons,
            }
        ),
    )

    return MatchResult(
        decision="AUTO_LINK",
        confidence=score,
        business_entity_id=entity.id,
        reasons=reasons,
    )


def _fill_contact(entity: BusinessEntity, source_record: SourceRecord) -> None:
    """A confirmed link may teach the business a phone/email it did not have."""
    entity.phone = entity.phone or normalize_phone(source_record.extracted_phone) or None
    entity.email = entity.email or normalize_email(source_record.extracted_email) or None


def _create_review_case(
    db: Session,
    source_record: SourceRecord,
    entity: BusinessEntity,
    score: float,
    reasons: List[str],
) -> MatchResult:

    review = ReviewCase(
        source_record_id=source_record.id,
        candidate_entity_id=entity.id,
        status=ReviewCaseStatusEnum.OPEN,
        confidence=score,
        evidence={
            "candidate_entity_id": str(entity.id),
            "candidate_name": entity.legal_name,
            "confidence": score,
            "reasons": reasons,
        },
        notes=f"Confidence {round(score, 2)}. Manual verification required.",
    )

    db.add(review)

    _audit(
        db,
        entity_type="review_case",
        entity_id=str(source_record.id),
        action="REVIEW_CREATED",
        after_state=_json_safe(
            {
                "candidate_entity_id": entity.id,
                "confidence": score,
            }
        ),
    )

    return MatchResult(
        decision="REVIEW",
        confidence=score,
        business_entity_id=entity.id,
        reasons=reasons,
    )


def _create_new_entity(
    db: Session,
    source_record: SourceRecord,
    best_score: Optional[float] = None,
    best_reasons: Optional[List[str]] = None,
) -> MatchResult:

    # PAN is shared by every branch GSTIN of one legal entity, but the column is
    # unique: only the first entity keeps it, the rest still match via their GSTIN.
    pan = source_record.extracted_pan
    if pan and db.query(BusinessEntity.id).filter(BusinessEntity.pan == pan).first():
        pan = None

    explanation = ["No reliable candidate found"]
    if best_reasons:
        explanation = [
            f"Best candidate scored {best_score} (below review threshold)",
            *best_reasons,
        ]

    entity = BusinessEntity(
        ubid_code=generate_ubid(),
        legal_name=source_record.extracted_name or "UNKNOWN",
        normalized_name=normalize_text(source_record.extracted_name),
        pan=pan,
        gstin=source_record.extracted_gstin,
        address=source_record.extracted_address,
        normalized_address=normalize_address(source_record.extracted_address),
        pin_code=normalize_pin(source_record.extracted_pin) or None,
        email=normalize_email(source_record.extracted_email) or None,
        phone=normalize_phone(source_record.extracted_phone) or None,
        status=EntityStatusEnum.UNKNOWN,
    )

    db.add(entity)
    db.flush()

    link = EntityRecordLink(
        source_record_id=source_record.id,
        business_entity_id=entity.id,
        confidence=None,  # founding record: nothing was matched, so no score to report
        decision=LinkDecisionEnum.AUTO_LINK,
        explanation=explanation,
    )

    db.add(link)
    db.flush()

    _audit(
        db,
        entity_type="business_entity",
        entity_id=str(entity.id),
        action="NEW_ENTITY_CREATED",
        after_state=_json_safe(
        {
            "source_record_id": source_record.id,
            "ubid_code": entity.ubid_code,
        },
    ))

    return MatchResult(
        decision="NEW_ENTITY",
        confidence=0.0,
        business_entity_id=entity.id,
        reasons=explanation,
    )


# ============================================================
# AUDIT
# ============================================================

def _audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
) -> None:

    log = AuditLog(
        actor_type=AuditActorEnum.SYSTEM,
        actor_id=None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
    )

    db.add(log)


# ============================================================
# SERIALIZER
# ============================================================

def _to_dict(result: MatchResult) -> Dict[str, Any]:
    return {
        "decision": result.decision,
        "confidence": round(result.confidence, 4),
        "business_entity_id": (
            str(result.business_entity_id)
            if result.business_entity_id is not None
            else None
        ),
        "reasons": result.reasons,
    }