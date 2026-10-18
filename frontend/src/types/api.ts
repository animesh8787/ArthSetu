// Mirrors Docs/API_CONTRACT.md — keep in sync with the backend.

export type Role = "admin" | "reviewer" | "viewer";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  is_bootstrap: boolean;
  created_at: string | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
}

export interface DashboardResponse {
  total_businesses: number;
  active: number;
  dormant: number;
  closed: number;
  unknown: number;
  pending_reviews: number;
  total_links: number;
  auto_match_rate: number;
}

export interface AnalyticsSummary {
  total_businesses: number;
  active: number;
  dormant: number;
  closed: number;
  unknown: number;
}

export interface TrendPoint {
  month: string;
  events: number;
}

export interface DistrictRow {
  district: string;
  total: number;
  active: number;
  dormant: number;
  closed: number;
  unknown: number;
}

export interface Page<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface BusinessSearchItem {
  ubid: string;
  business_name: string;
  status: string;
  district: string | null;
  pin_code: string | null;
  pan: string | null;
  gstin: string | null;
}

export interface LinkedRecord {
  link_id: string;
  source_record_id: string;
  source_system: string | null;
  department: string | null;
  external_id: string | null;
  extracted_name: string | null;
  extracted_address: string | null;
  extracted_pin: string | null;
  confidence: number | null;
  decision: string | null;
}

export interface MatchingEvidence {
  signal: string;
  value: string;
}

export interface TimelineEvent {
  id: string;
  date: string | null;
  event: string;
  score: number | null;
}

export interface StatusHistoryPoint {
  date: string;
  status: string;
  confidence: number | null;
}

export interface BusinessProfile {
  id: string;
  ubid: string;
  business_name: string;
  status: string;
  status_locked: boolean;
  status_override_reason: string | null;
  pan: string | null;
  gstin: string | null;
  address: string | null;
  pin_code: string | null;
  district: string | null;
  sector: string | null;
  linked_records_count: number;
  linked_records: LinkedRecord[];
  matching_evidence: MatchingEvidence[];
  timeline: TimelineEvent[];
  status_history: StatusHistoryPoint[];
}

export interface ReviewEvidence {
  candidate_entity_id?: string;
  candidate_name?: string;
  confidence?: number;
  reasons?: string[];
}

export interface ReviewCaseItem {
  review_id: string;
  source_record_id: string;
  candidate_entity_id: string | null;
  candidate_name: string | null;
  candidate_ubid: string | null;
  source_system: string | null;
  extracted_name: string | null;
  status: string;
  confidence: number | null;
  evidence: ReviewEvidence | null;
  notes: string | null;
  reviewer_id: string | null;
  created_at: string | null;
  decided_at: string | null;
}

export interface ReviewDecisionResponse {
  message: string;
  review_id: string;
  status: string;
  linked_entity_id: string | null;
  link_id: string | null;
}

export interface StatusResult {
  business_entity_id: string;
  ubid_code: string;
  status: string;
  engine_status: string | null;
  locked: boolean;
  confidence: number;
  reasons: string[];
}

export interface CorrectionEntry {
  audit_id: string;
  action: string;
  actor_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  summary: string;
  reason: string | null;
  created_at: string | null;
  undone: boolean;
  reversible: boolean;
}

export interface CorrectionResult {
  message: string;
  audit_id: string;
  detail: unknown;
}

export interface AuditEntry {
  id: string;
  actor_type: string;
  actor_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  action: string | null;
  before_state: unknown;
  after_state: unknown;
  created_at: string | null;
}

// --- Ingestion ---------------------------------------------------------

export interface SourceSystem {
  code: string;
  name: string;
  department: string;
  record_count: number;
  /** Only admins receive the URL; it can carry an access key. */
  pull_url: string | null;
  pull_kind: "records" | "events" | null;
  last_pull_at: string | null;
  last_pull_status: string | null;
}

export interface EventsReport {
  rows_read: number;
  created: number;
  skipped_duplicates: number;
  unresolved: number;
  errors: { row: number; error: string }[];
  recomputed: number;
}

export interface LearnedSignal {
  field: string;
  label: string;
  coefficient: number;
  approved_avg: number;
  rejected_avg: number;
  current_weight: number;
  suggested_weight: number;
  learned: boolean;
}

export interface CalibrationSuggestion {
  ready: boolean;
  message: string | null;
  decided: number;
  approved: number;
  rejected: number;
  accuracy: number | null;
  signals: LearnedSignal[];
}

export interface MatchingTally {
  auto_link: number;
  review: number;
  new_entity: number;
  failed: number;
}

export interface IngestionReport {
  source_system: string;
  rows_read: number;
  created: number;
  skipped_duplicates: number;
  errors: { row: number; error: string }[];
  matching: MatchingTally | null;
  job_id: string | null;
}

// --- Background jobs ----------------------------------------------------

export type JobType = "status_run_all" | "process_pending" | "csv_match" | "sync_connectors";
export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  payload: unknown;
  result: unknown;
  error: string | null;
  created_by: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

// --- Matching configuration ---------------------------------------------

export interface MatchingWeights {
  gstin_weight: number;
  pan_weight: number;
  name_weight: number;
  address_weight: number;
  pin_weight: number;
  contact_weight: number;
  pin_requires_name_sim: number;
  auto_link_threshold: number;
  review_threshold: number;
  updated_by: string | null;
  updated_at: string | null;
}

export interface ConfidenceBucket {
  label: string;
  total: number;
  approved: number;
  rejected: number;
  pending: number;
  approve_rate: number | null;
}

export interface SignalBreakdownRow {
  signal: string;
  approved: number;
  rejected: number;
}

export interface MatchingCalibration {
  weights: MatchingWeights;
  buckets: ConfidenceBucket[];
  signals: SignalBreakdownRow[];
  sample_size: number;
}
