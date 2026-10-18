# ArthSetu
#### A platform which provides Unified Business Intelligence Infrastructure for Indian Government

 
### *One Business. One Identity. One Truth Layer for Government.*

<p align="center">
  <img src="https://img.shields.io/badge/Status-Prototype%20Operational-success?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/PostgreSQL-Ready-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Explainable-Scoring-orange?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Human--in--Loop-GovTech-important?style=for-the-badge"/>
</p>

---

# Executive Summary

ArthSetu is a government-grade **Business Identity & Activity Intelligence Platform** designed to solve one of the most critical administrative problems in public governance:

> The absence of a trusted, unified business identity across fragmented departmental systems.

Today, the same business often exists separately in:

- Labour Department databases  
- Factory Registries  
- Municipal Licensing Systems  
- Pollution Control Boards  
- Utility Records  
- Compliance Portals  

Each department stores business data differently, resulting in:

- Duplicate records  
- Fragmented identities  
- Manual reconciliation effort  
- Poor compliance targeting  
- Delayed closure detection  
- Weak inter-department coordination  
- Inaccurate policy intelligence  

ArthSetu creates a **Unique Business Identifier (UBID)** for every real-world business and continuously determines whether the business is:

- **Active**
- **Dormant**
- **Closed**

—all while ensuring every decision remains:

- Explainable  
- Reviewable  
- Reversible  
- Government-feasible  

---

# Why ArthSetu Matters

## The Real Problem Is Not Just Duplicate Data

The actual problem is:

- No shared identity layer
- No operational truth
- No cross-department visibility
- No trustworthy business lifecycle intelligence

### Example

The same factory may appear as:

| Department | Record |
|---|---|
| Labour | Punjab Steel Works Pvt Ltd |
| Municipal | Punjab Steel Wrks Pvt. Ltd. |
| Pollution | PUNJAB STEEL INDUSTRIES |
| Utility | Punjab Steel Works |

No officer can instantly confirm:

> “Are these the same business?”

ArthSetu solves this.

---

# Vision

ArthSetu acts as a **Digital Coordination Layer** above existing government systems without replacing them.

It enables governments to answer queries like:

```sql
SELECT *
FROM factories
WHERE status = 'ACTIVE'
AND last_inspection > 18 months;
```

within seconds instead of weeks.

---

# Core System Capabilities

# 1. UBID Identity Resolution Engine

ArthSetu intelligently links fragmented business records across multiple systems into a single trusted identity.

## Supported Matching Signals

### Strong Anchors

- GSTIN
- PAN

### Similarity Signals

- Business name similarity (token-set + fuzzy, filler words like "M/S" ignored)
- Address similarity
- PIN code (counted only beside a loosely related name - a bare PIN covers thousands of businesses)
- Contact details: phone / email (also only beside a related name, so a shared agency number cannot link strangers)

---

## Explainable Matching

Every linkage stores:

- Confidence score
- Evidence signals (the reasons shown below)
- Timestamp

Reviewer actions and what is needed to reverse them live in the audit log, one entry per decision.

### Example Decision

```json
{
  "decision": "AUTO_LINK",
  "confidence": 0.94,
  "reasons": [
    "GSTIN exact match",
    "Name similarity 0.96",
    "PIN code match"
  ]
}
```

---

# 2. Human-in-the-Loop Governance

ArthSetu never silently merges uncertain records.

Instead:

| Confidence | Action |
|---|---|
| High (>= auto-link threshold, default 0.92) | Auto-Link |
| Medium (>= review threshold, default 0.70) | Send to Review Queue |
| Low | Keep Separate - the record opens its own business identity |

Rejecting a review case works the same way: the record gets its own UBID (reversible via Undo) and is not
queued again.

---

## Reviewer Workflow

Reviewers can:

- Approve merges
- Reject merges
- Split wrongly linked entities
- Override classifications
- Reassign activity events

Every approve / reject becomes training data for **calibration**. A small logistic regression (plain numpy)
is fitted on the evidence of decided cases and *suggests* new matching weights, with the per-signal numbers
that explain why. It never scores a record itself - matching stays the transparent weighted sum - and nothing
changes until an admin presses **Apply** on the Matching Tuning page. Suggestions are bounded to 0.25x-2.5x of the
current weights and need at least 20 decided cases (5+ of each outcome).

---

# 3. Business Activity Intelligence Engine

A registered business is not necessarily an operational business.

ArthSetu evaluates the activity events departments send it:

- Inspections
- GST filings
- Licence renewals / cancellations
- Utility (power) usage
- Complaints and document updates
- Suspension and closure notices

Events arrive through the **activity-event import** (CSV, or `POST /api/v1/ingest/events`) or a scheduled
**connector**, and the affected businesses are re-evaluated immediately. A business with no events at all is
**Unclassified**, not Closed.

to infer:

## ACTIVE

Recent operational signals detected.

## DORMANT

Historical existence but weak recent activity.

## CLOSED

Explicit closure or prolonged inactivity.

---

## Explainable Status Decisions

### Example

```yaml
Status: Dormant (confidence 0.31)

Reasons:
  - GST_FILED: base=0.95, age=410d, decay=0.1, score=0.09
  - POWER_USAGE: base=0.82, age=212d, decay=0.3, score=0.25
  - INSPECTION: base=0.75, age=520d, decay=0.1, score=0.07
```

---

# 4. Government Interoperability Layer

ArthSetu was specifically designed around real-world government constraints.

## No Source System Changes Required

Departments continue using existing systems.

ArthSetu integrates using:

- JSON APIs (`/ingest/records`, `/ingest/events`)
- CSV exports (records and activity events, department column names matched loosely)
- Read-only connectors: a system publishes a CSV / JSON export at a public `https` URL and ArthSetu pulls it
  (SSRF-guarded: no private addresses, no redirects, 8 MB cap). Nothing is written back to the department.
- Scheduled syncs: `POST /api/v1/cron/tick` (shared-secret) pulls every connector, matches new records and
  refreshes statuses. [`scheduled-sync.yml`](.github/workflows/scheduled-sync.yml) calls it every 6 hours once
  the `CRON_SECRET` secret and `BACKEND_URL` variable are set.

This makes deployment realistic.

---

# System Architecture
Docs/

<p align="center">
  <img src="Docs/architecture/ArthSetu_System_Architecture.png" width="950"/>
</p>

```text
┌─────────────────────────────────────────────┐
│         Government Department Systems       │
│ Labour │ Municipal │ Pollution │ Utilities │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│              Ingestion Layer                │
│ APIs │ CSV Imports │ Connectors │ Sync Jobs │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│            Normalization Engine             │
│ Name Cleaning │ Address Standardization     │
└─────────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌───────────────────┐   ┌────────────────────┐
│ Identity Engine   │   │ Activity Engine    │
│ UBID Matching     │   │ Status Inference   │
└───────────────────┘   └────────────────────┘
          │                       │
          └───────────┬───────────┘
                      ▼
┌─────────────────────────────────────────────┐
│             Unified UBID Registry           │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ Dashboard │ Search │ Review Queue │ APIs    │
└─────────────────────────────────────────────┘
```

---

# Technology Stack

## Backend

- Python
- FastAPI
- SQLAlchemy 2.0
- Alembic
- Pydantic

## Database

- SQLite (development)
- PostgreSQL-ready architecture

## Matching & Intelligence

- RapidFuzz
- Weighted Rule Engine
- Explainable Confidence Scoring (every decision lists its reasons)
- Reviewer-Feedback Calibration (logistic regression over decided reviews, numpy)

## Frontend

- React
- Vite
- TailwindCSS

## Infrastructure

- Docker + docker-compose (Postgres, API, nginx-served frontend)
- In-process background job runner for batch/bulk operations
- Modular backend services
- REST APIs

---

# Database Design

ArthSetu uses a normalized relational architecture.

## Core Tables

| Table | Purpose |
|---|---|
| source_system | Department registry metadata |
| source_record | Raw fragmented business records |
| business_entity | Canonical UBID entity |
| entity_record_link | Mapping source records to UBID |
| review_case | Human review queue |
| activity_event | Operational activity signals |
| status_snapshot | Business lifecycle classifications |
| audit_log | Explainability and governance tracking |

---

### ER DIAGRAM

<p align="center">
  <img src="Docs/architecture/Er_diagram_ArthSetu.png" width="950"/>
</p>

# Current Prototype Status

## Backend Platform

### Completed

- FastAPI backend
- Database schema
- Alembic migrations
- Identity engine
- Explainable matching
- Activity inference
- Review APIs
- Synthetic ecosystem
- Analytics endpoints

---

## Frontend

React + TypeScript console (Vite + Tailwind, TanStack Query). Complete:

- **Authentication** — Firebase sign-in, route guards, role-gated UI, admin user management
- **Data ingestion** (admin) — CSV import with loose header matching, records run through
  the matching engine on upload, "process pending" for unresolved records, activity-event
  import, and per-system read-only connectors with "Sync now"
- **Executive dashboard** — KPIs, activity-trend chart, status breakdown, live audit feed
- **Business search** — substring search over UBID, name, PAN, GSTIN and address, plus status,
  district and "no inspection in N months" filters; URL-synced, paginated
- **Business profile** — identity, linked departmental records, matching evidence,
  activity timeline, explainable status inference, per-business audit trail (links, review
  decisions, events and corrections)
- **Review queue** — human-in-the-loop approve / reject with real link confirmation,
  reviewer attribution
- **Corrections** — split a wrongly-linked record, pin a lifecycle status, reassign an
  activity event; every correction is reversible from a history view
- **District analytics** — stacked bars + sortable table with drill-down into search
- **Background jobs** (admin) — batch status recompute and bulk matching now run off the
  request thread on a worker pool; a Jobs page tracks pending/running/succeeded/failed
- **Matching tuning** (admin) — the scoring weights and decision thresholds are live-editable
  (no longer fixed constants), a reviewer-feedback calibration view that buckets review-case
  confidence against actual approve/reject outcomes, and learned-weight suggestions you can apply

---

# Synthetic Sandbox Ecosystem

To simulate real government environments, ArthSetu includes a realistic synthetic ecosystem.

## Current Dataset

Produced by `python -m backend.seed_dev --reset` (fixed random seed, so it is reproducible):

| Component | Count |
|---|---|
| Source Systems | 4 |
| Businesses | 146 |
| Source Records | 376 |
| Linked Records | 192 |
| Open Review Cases | 184 |
| Activity Events | 1227 |
| Status Snapshots | 146 |
| Audit Logs | 522 |

About half of the departmental records carry no strong id, so name + address + PIN alone can only
reach the review band; that is by design - it is why the review queue is so full on demo data.

---

## Synthetic Realism Included

- Spelling variations
- Missing PAN/GSTIN
- Noisy addresses and phone formats
- Intra-department duplicates (about 1 in 8 departments holds a business twice)
- Ambiguous identities
- Synthetic activity histories

---

# APIs

<p align="center">
  <img src="Docs/architecture/Backend_routes_1.png" width="950"/>
</p>


<p align="center">
  <img src="Docs/architecture/Backend_routes_2.png" width="950"/>
</p>


## Matching Engine

<p align="center">
  <img src="Docs/architecture/Matching_Workflow_ArthSetu.png" width="950"/>
</p>

```http
POST /api/v1/matching/process/{id}
```

Processes incoming records.

---

## Review Queue

```http
GET /api/v1/reviews
```

Returns pending review cases.

---

## Approve / Reject Review

```http
POST /api/v1/reviews/{id}/approve
POST /api/v1/reviews/{id}/reject
```

A case that is already decided answers `409`.

---

## Business Search

```http
GET /api/v1/business/search?q=&status=&district=&no_inspection_months=18
```

`q` is a substring match over UBID, GSTIN, PAN, business name and address;
`no_inspection_months` keeps businesses with no inspection in that window (or ever).

---

## Status Engine

```http
GET /api/v1/status/{ubid}      # reviewer role; recomputes and stores a snapshot
```

Returns operational status for a UBID.



# Design Targets (not measured results)

These are the improvements the design aims for. They have not been measured on real departmental data.

| Capability | Target |
|---|---|
| Manual reconciliation reduction | 70–85% |
| Duplicate record reduction | 60–75% |
| Faster closure detection | 90–180 days |
| Reviewer workload reduction | 65–80% |
| Compliance targeting efficiency | 40–60% |

---

# Why ArthSetu Is Different

Most solutions solve only one layer:

- Matching tool
- Dashboard
- Analytics engine
- Integration middleware

ArthSetu combines:

- Identity Resolution  
- Explainable, rule-based scoring with learned calibration  
- Human Governance  
- Activity Intelligence  
- Interoperability  

into one deployable ecosystem.

---

# Security & Governance

ArthSetu was designed with government trust requirements in mind.

## Principles

- Explainable decisions
- Audit trails
- Reversible merges
- No silent automation
- Sandbox compatibility
- No hosted LLM dependency on raw PII

---

# Scalability Vision

ArthSetu can evolve into:

- Statewide business intelligence infrastructure
- Compliance targeting engine
- Fraud detection layer
- MSME operational intelligence network
- National interoperable business identity layer

---

# Repository Structure

```bash
ArthSetu/
│
├── backend/
│   ├── app/            # FastAPI app: api / services / db / schemas
│   └── seed_dev.py     # self-contained synthetic-data seeder
├── frontend/           # React + TypeScript + Vite console
├── migrations/         # Alembic migrations
├── Docs/
│   ├── API_CONTRACT.md # the v1 REST contract the frontend targets
│   └── architecture/
└── README.md
```

---

# Setup Instructions

Run everything from the repository root.

## Backend

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate elsewhere)
pip install -r backend/requirements.txt

python -m backend.seed_dev --reset          # build a local SQLite dataset
python -m uvicorn backend.app.main:app --reload
```

- API: `http://localhost:8000`  ·  Swagger: `http://localhost:8000/docs`
- DB defaults to `sqlite:///./arthsetu_dev.db`; set `DATABASE_URL` (e.g. Postgres)
  in `backend/.env` to override. Schema is managed by Alembic (`alembic upgrade head`).
- **Sign-in needs a Firebase Auth target.** For local dev, run the
  [Firebase Auth Emulator](https://firebase.google.com/docs/emulator-suite)
  (`npm install -g firebase-tools`, then `firebase emulators:start --only auth`)
  and set `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` in `backend/.env` —
  see `backend/.env.example` (the file is found from any working directory). **For any non-local run, set
  `FIREBASE_CREDENTIALS_JSON`** to a real Firebase service-account JSON.

## Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

The dev server proxies `/api` to the backend, so start the API first. See
[`frontend/README.md`](frontend/README.md) for details.

## Docker

```bash
docker compose up --build
docker compose exec backend python -m backend.seed_dev --reset   # optional: synthetic demo data
```
Runs Postgres + the API (`:8000`, migrations applied on start) + the
frontend behind nginx (`:8080`). Sign-in needs a Firebase target even for a
trial: put your web-app config in `.env` as `VITE_FIREBASE_*` (they are baked
into the frontend image, so rebuild after changing them), or run the Auth
Emulator on your host and set `FIREBASE_AUTH_EMULATOR_HOST=host.docker.internal:9099`
(backend) and `VITE_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` (browser); start it with `--host 0.0.0.0`.
A fresh container bootstraps one admin login (`admin@arthsetu.local` / `arthsetu-admin` by
default; if that email already exists in your Firebase project it is adopted). For a real deployment, copy `.env.docker.example` to `.env` and
set `APP_ENV=production` plus real secrets; the backend refuses to start in
production without a real Firebase project configured or with the default
bootstrap password.
See [`Docs/API_CONTRACT.md`](Docs/API_CONTRACT.md#running-with-docker) for
the full hardening notes (non-root containers, health checks, resource
limits, nginx security headers).

## Deploying: Vercel + Render

Frontend on Vercel, backend + Postgres on Render — [`render.yaml`](render.yaml)
and [`frontend/vercel.json`](frontend/vercel.json) are ready for it. Full
step-by-step in
[`Docs/API_CONTRACT.md`](Docs/API_CONTRACT.md#deploying-to-vercel--render).

## Auth

Sign-in happens client-side via **Firebase Authentication** (email +
password) — every API call except `/health` needs a
`Bearer <firebase-id-token>` header. Roles: **admin** > **reviewer** >
**viewer** (see [`Docs/API_CONTRACT.md`](Docs/API_CONTRACT.md)). The dev
seeder (`backend/seed_dev.py`) creates these demo accounts in Firebase:

| Email | Password | Role |
|---|---|---|
| `admin@arthsetu.local` | `arthsetu-admin` | admin |
| `reviewer@arthsetu.local` | `arthsetu-review` | reviewer |
| `officer@arthsetu.local` | `arthsetu-view` | viewer |

## Tests

```bash
python -m pytest                    # backend — from the repo root
cd frontend && npm run test         # frontend (Vitest)
```

Backend covers the scoring, status and matching engines, review decisions and undo, activity-event
feeds, connectors, the scheduler endpoint, learned calibration, and the authenticated API (roles,
endpoint contracts). Frontend covers the formatters, audit descriptions, and the auth context / route guard.

GitHub Actions (`.github/workflows/ci.yml`) runs both suites on every push and pull request, against
SQLite and against a real PostgreSQL service (migrations, `alembic check`, tests), plus `tsc --noEmit`,
`vite build` and a Docker build of both images.

---

# Evaluation Criteria Alignment

| Evaluation Area | ArthSetu Strength |
|---|---|
| Problem Understanding | Deep real-world government fragmentation analysis |
| Technical Innovation | Explainable matching + activity intelligence |
| Government Feasibility | No source system replacement needed |
| Demo Quality | Reviewer workflow + live matching engine |
| Scalability | Modular statewide interoperability platform |

---

# Future Roadmap

## Phase 1

- Frontend completion
- Dashboard polish
- Deployment hardening

## Phase 2

- District heatmaps
- Anomaly detection
- Per-district calibration (the learned-weights suggestion today is global)

## Phase 3

- Statewide onboarding
- Distributed ingestion
- Compliance intelligence layer

---

# Final Statement

ArthSetu is not merely a registry.

It is a trusted intelligence layer that helps governments understand:

- Which businesses are truly the same
- Which are operational
- Where intervention is required
- Why the system reached that conclusion

---

# Team ArthSetu
###| Member | Role |
|---|---|
|AYUSH | AI & Backend Systems Engineer |
| PRANAY GUPTA | Platform & Data Infrastructure Engineer |
|ANIMESH | Product & Governance Workflow Engineer |

Building trustworthy digital public infrastructure for modern governance.
