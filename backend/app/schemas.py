# ============================================================
# FILE: backend/app/schemas.py
# Pydantic response/request models for the public API contract.
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------
# Auth
# ------------------------------------------------------------

Role = Literal["admin", "reviewer", "viewer"]


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: Role
    is_active: bool
    is_bootstrap: bool = False
    created_at: Optional[datetime] = None


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=120)
    role: Role = "viewer"
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# ------------------------------------------------------------
# Health
# ------------------------------------------------------------


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------

class DashboardResponse(BaseModel):
    total_businesses: int
    active: int
    dormant: int
    closed: int
    unknown: int
    pending_reviews: int
    total_links: int
    auto_match_rate: float


# ------------------------------------------------------------
# Analytics
# ------------------------------------------------------------

class AnalyticsSummaryResponse(BaseModel):
    total_businesses: int
    active: int
    dormant: int
    closed: int
    unknown: int


class TrendPoint(BaseModel):
    month: str
    events: int


class DistrictRow(BaseModel):
    district: str
    total: int
    active: int
    dormant: int
    closed: int
    unknown: int


# ------------------------------------------------------------
# Business
# ------------------------------------------------------------

class BusinessSearchItem(BaseModel):
    ubid: str
    business_name: str
    status: str
    district: Optional[str] = None
    pin_code: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None


class BusinessSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[BusinessSearchItem]


class TimelineEvent(BaseModel):
    id: str
    date: Optional[datetime] = None
    event: str
    score: Optional[float] = None


class LinkedRecord(BaseModel):
    link_id: str
    source_record_id: str
    source_system: Optional[str] = None
    department: Optional[str] = None
    external_id: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_address: Optional[str] = None
    extracted_pin: Optional[str] = None
    confidence: Optional[float] = None
    decision: Optional[str] = None


class MatchingEvidence(BaseModel):
    signal: str
    value: str


class StatusHistoryPoint(BaseModel):
    date: datetime
    status: str
    confidence: Optional[float] = None


class BusinessProfileResponse(BaseModel):
    id: str
    ubid: str
    business_name: str
    status: str
    status_locked: bool = False
    status_override_reason: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    pin_code: Optional[str] = None
    district: Optional[str] = None
    sector: Optional[str] = None
    linked_records_count: int
    linked_records: List[LinkedRecord]
    matching_evidence: List[MatchingEvidence]
    timeline: List[TimelineEvent]
    status_history: List[StatusHistoryPoint]


# ------------------------------------------------------------
# Review
# ------------------------------------------------------------

class ReviewCaseItem(BaseModel):
    review_id: str
    source_record_id: str
    candidate_entity_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_ubid: Optional[str] = None
    source_system: Optional[str] = None
    extracted_name: Optional[str] = None
    status: str
    confidence: Optional[float] = None
    evidence: Optional[Any] = None
    notes: Optional[str] = None
    reviewer_id: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None


class ReviewListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ReviewCaseItem]


class ReviewDecisionResponse(BaseModel):
    message: str
    review_id: str
    status: str
    linked_entity_id: Optional[str] = None
    link_id: Optional[str] = None


# ------------------------------------------------------------
# Status engine
# ------------------------------------------------------------

class StatusResultResponse(BaseModel):
    business_entity_id: str
    ubid_code: str
    status: str
    engine_status: Optional[str] = None
    locked: bool = False
    confidence: float
    reasons: List[str]


# ------------------------------------------------------------
# Matching
# ------------------------------------------------------------

class MatchingResultResponse(BaseModel):
    decision: str
    confidence: float
    business_entity_id: Optional[str] = None
    reasons: List[str]


# ------------------------------------------------------------
# Audit
# ------------------------------------------------------------

class AuditEntry(BaseModel):
    id: str
    actor_type: str
    actor_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action: Optional[str] = None
    before_state: Optional[Any] = None
    after_state: Optional[Any] = None
    created_at: Optional[datetime] = None


class AuditListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[AuditEntry]


# ------------------------------------------------------------
# Ingestion
# ------------------------------------------------------------

class SourceSystemOut(BaseModel):
    code: str
    name: str
    department: str
    record_count: int
    pull_url: Optional[str] = None
    pull_kind: Optional[str] = None
    last_pull_at: Optional[datetime] = None
    last_pull_status: Optional[str] = None


class IngestRecord(BaseModel):
    external_id: Optional[str] = None
    name: str
    pan: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    pin: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class IngestRequest(BaseModel):
    source_system_code: str
    records: List[IngestRecord]
    process: bool = True


class RowError(BaseModel):
    row: int
    error: str


class MatchingTallyOut(BaseModel):
    auto_link: int
    review: int
    new_entity: int
    failed: int


class IngestionReportOut(BaseModel):
    source_system: str
    rows_read: int
    created: int
    skipped_duplicates: int
    errors: List[RowError]
    matching: Optional[MatchingTallyOut] = None
    job_id: Optional[str] = None


class PendingCountResponse(BaseModel):
    pending: int


# ------------------------------------------------------------
# Corrections (reviewer graph edits)
# ------------------------------------------------------------

class SplitLinkRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    mode: Literal["new_entity", "reopen_review"] = "reopen_review"


class StatusOverrideRequest(BaseModel):
    status: Literal["active", "dormant", "closed", "unknown"]
    reason: str = Field(min_length=1, max_length=500)


class ReassignEventRequest(BaseModel):
    target_ubid: str
    reason: str = Field(min_length=1, max_length=500)


class CorrectionResult(BaseModel):
    message: str
    audit_id: str
    detail: Optional[Any] = None


class CorrectionEntry(BaseModel):
    audit_id: str
    action: str
    actor_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    summary: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    undone: bool = False
    reversible: bool = False


class CorrectionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[CorrectionEntry]


# ------------------------------------------------------------
# Background jobs
# ------------------------------------------------------------

JobStatus = Literal["pending", "running", "succeeded", "failed"]
JobType = Literal["status_run_all", "process_pending", "csv_match", "sync_connectors"]


class JobOut(BaseModel):
    id: str
    job_type: JobType
    status: JobStatus
    payload: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[JobOut]


# ------------------------------------------------------------
# Matching configuration (reviewer-feedback calibration)
# ------------------------------------------------------------

class MatchingWeightsOut(BaseModel):
    gstin_weight: float
    pan_weight: float
    name_weight: float
    address_weight: float
    pin_weight: float
    contact_weight: float
    pin_requires_name_sim: float
    auto_link_threshold: float
    review_threshold: float
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class MatchingWeightsUpdate(BaseModel):
    gstin_weight: Optional[float] = Field(default=None, ge=0, le=1)
    pan_weight: Optional[float] = Field(default=None, ge=0, le=1)
    name_weight: Optional[float] = Field(default=None, ge=0, le=1)
    address_weight: Optional[float] = Field(default=None, ge=0, le=1)
    pin_weight: Optional[float] = Field(default=None, ge=0, le=1)
    contact_weight: Optional[float] = Field(default=None, ge=0, le=1)
    pin_requires_name_sim: Optional[float] = Field(default=None, ge=0, le=1)
    auto_link_threshold: Optional[float] = Field(default=None, ge=0, le=1)
    review_threshold: Optional[float] = Field(default=None, ge=0, le=1)


class ConfidenceBucket(BaseModel):
    label: str
    total: int
    approved: int
    rejected: int
    pending: int
    approve_rate: Optional[float] = None


class SignalBreakdownRow(BaseModel):
    signal: str
    approved: int
    rejected: int


class MatchingCalibrationResponse(BaseModel):
    weights: MatchingWeightsOut
    buckets: List[ConfidenceBucket]
    signals: List[SignalBreakdownRow]
    sample_size: int


# ---------- Connectors, activity events, learned calibration ----------

class ConnectorUpdate(BaseModel):
    pull_url: Optional[str] = Field(default=None, max_length=1000)
    pull_kind: Literal["records", "events"] = "records"


class EventRecord(BaseModel):
    ubid: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    external_id: Optional[str] = None
    event_type: str
    occurred_at: str


class EventsIngestRequest(BaseModel):
    source_system_code: Optional[str] = None
    events: List[EventRecord] = Field(max_length=5000)


class EventsReportOut(BaseModel):
    rows_read: int
    created: int
    skipped_duplicates: int
    unresolved: int
    errors: List[RowError]
    recomputed: int


class LearnedSignal(BaseModel):
    field: str
    label: str
    coefficient: float
    approved_avg: float
    rejected_avg: float
    current_weight: float
    suggested_weight: float
    learned: bool


class CalibrationSuggestion(BaseModel):
    ready: bool
    message: Optional[str] = None
    decided: int
    approved: int
    rejected: int
    accuracy: Optional[float] = None
    signals: List[LearnedSignal]
