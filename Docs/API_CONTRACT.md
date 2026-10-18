# ArthSetu API Contract (v1)

Base URL: `http://localhost:8000`
Prefix: `/api/v1`
Interactive docs: `http://localhost:8000/docs`

Stored enum values (business status, review status, link decision, job type/status, event type) are
**lower_snake_case** strings (`active`, `dormant`, `closed`, `unknown`, `open`, `approved`, `rejected`,
`auto_link`, `review`, `manual`). Two engine results are the exception and come back **UPPER_CASE**:
`status` from `GET /status/{ubid}` (`ACTIVE`, `DORMANT`, `CLOSED`, `UNKNOWN`) and `decision` from
`POST /matching/process/{id}` (`AUTO_LINK`, `REVIEW`, `NEW_ENTITY`). Invalid enum filters return `422`.

## Authentication

Sign-in happens client-side against **Firebase Authentication** (email +
password) — the backend never sees a password, only a Firebase ID token.
Every endpoint **except `GET /health`** requires an
`Authorization: Bearer <firebase-id-token>` header. Missing/invalid/expired
token → `401`; a verified token with no matching ArthSetu profile, or
insufficient role, or a disabled account → `403`.

Roles (each includes the ones below it): **admin** > **reviewer** > **viewer**.

| Capability | Minimum role |
|---|---|
| Read dashboard / search / profiles / analytics / audit | viewer |
| Recompute a business status (`GET /status/{ubid}`) | reviewer |
| Approve / reject a review case | reviewer |
| Corrections (split / status override / reassign / undo) | reviewer |
| Batch status recompute (`POST /status/run-all`) | admin |
| Trigger matching (`POST /matching/process/...`) | admin |
| Import records and events (`POST /ingest/csv`, `/ingest/records`, `/ingest/events`, `/ingest/events/csv`, `/ingest/process-pending`) | admin |
| Configure / run a connector (`PUT /ingest/source-systems/{code}/connector`, `POST .../sync`) | admin |
| List source systems / pending count / templates (connector URLs are shown to admins only) | viewer |
| Scheduled sync (`POST /cron/tick`) | shared secret (`X-Cron-Secret`), no user token |
| Background jobs (`/jobs*`) | admin |
| Matching weights & calibration (`/matching/weights`, `/matching/calibration*`) | admin |
| User management (`/auth/users*`) | admin |

`GET /api/v1/auth/me` → the local ArthSetu profile for the verified Firebase user:
```json
{ "id": "...", "full_name": "System Administrator", "email": "admin@example.com",
  "role": "admin", "is_active": true, "is_bootstrap": true, "created_at": "..." }
```

There is no backend login or change-password endpoint — sign-in, sign-out,
and a user changing their own password all go through the Firebase client
SDK directly. Forgotten passwords use Firebase's `sendPasswordResetEmail`.

**Admin only** (these still go through the backend, which uses the Firebase
Admin SDK server-side so an admin can set a colleague's password directly):
`GET /api/v1/auth/users` → `[UserOut, ...]`
`POST /api/v1/auth/users` → `{ email, full_name, role, password }` → `201 UserOut`
`PATCH /api/v1/auth/users/{id}` → `{ full_name?, email?, role?, is_active? }` → `UserOut`
`POST /api/v1/auth/users/{id}/reset-password` → `{ "new_password": "..." }` → `UserOut`

The API ships no hard-coded accounts: the bootstrap admin
(`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`) is created in Firebase on first boot
(an existing Firebase account with that email is adopted), and the development seeder
`backend/seed_dev.py` creates four publicly documented demo users - never run it against production.
Changing a user's email through `PATCH /auth/users/{id}` also changes the Firebase login (`409` if the
address is taken).

---

## Health

`GET /api/v1/health`  (public)
```json
{ "status": "ok", "service": "ArthSetu", "version": "1.0.0",
  "environment": "development", "database": "connected" }
```

## Dashboard

`GET /api/v1/dashboard`
```json
{ "total_businesses": 140, "active": 90, "dormant": 20, "closed": 30,
  "unknown": 0, "pending_reviews": 151, "total_links": 346,
  "auto_match_rate": 56.36 }
```

## Analytics

`GET /api/v1/analytics/summary` → `{ total_businesses, active, dormant, closed, unknown }`

`GET /api/v1/analytics/trends` → `[{ "month": "2026-07", "events": 212 }, ...]`

`GET /api/v1/analytics/districts` →
```json
[{ "district": "Ludhiana", "total": 25, "active": 19,
   "dormant": 3, "closed": 3, "unknown": 0 }, ...]
```

## Business

`GET /api/v1/business/search?q=&status=&district=&pin=&no_inspection_months=&limit=25&offset=0`
(`q` is a case-insensitive substring match over UBID, name, PAN, GSTIN and address; `pin` is an exact
6-digit filter; `district=Unknown` selects businesses with no district; `no_inspection_months=18` keeps
businesses with no inspection in the last 18 months, including never-inspected ones)
```json
{ "total": 12, "limit": 25, "offset": 0,
  "items": [{ "ubid": "UBID-1A2B3C4D5E", "business_name": "Singh Auto Works",
              "status": "active", "district": "Mandi Gobindgarh",
              "pin_code": "147301", "pan": "FKBJZ2744X", "gstin": null }] }
```

`GET /api/v1/business/{ubid}`  (404 if unknown)
```json
{ "ubid": "UBID-1A2B3C4D5E", "business_name": "Singh Auto Works",
  "status": "active", "pan": "...", "gstin": null,
  "address": "Plot 42, Focal Point 3, Ludhiana, Punjab", "pin_code": "141001",
  "district": "Mandi Gobindgarh", "sector": "Restaurant",
  "linked_records_count": 4,
  "linked_records": [{ "link_id": "...", "source_record_id": "...",
    "source_system": "Commercial Consumer Ledger", "department": "Electricity Board",
    "external_id": "85c45579-303", "extracted_name": "Singh Auto Wrks",
    "extracted_address": "SINGH AUTO WRKS FOCAL POINT LUDHIANA", "extracted_pin": "141001",
    "confidence": 0.84, "decision": "review" }],
  "matching_evidence": [{ "signal": "Address similarity 0.9", "value": "Address similarity 0.9" }],
  "timeline": [{ "date": "2026-08-22T08:29:15Z", "event": "power_usage", "score": 0.85 }],
  "status_history": [{ "date": "2026-09-04T08:29:16Z", "status": "active", "confidence": 0.735 }] }
```

## Review Queue

`GET /api/v1/reviews?status=open&limit=25&offset=0`
```json
{ "total": 151, "limit": 25, "offset": 0,
  "items": [{ "review_id": "...", "source_record_id": "...",
    "candidate_entity_id": "...", "candidate_name": "Gupta Traders",
    "status": "open", "confidence": 0.56,
    "evidence": { "candidate_name": "Gupta Traders", "confidence": 0.56,
                  "reasons": ["Name similarity 0.82", "Address similarity 0.6", "PIN code match (141001)"] },
    "notes": "Confidence 0.56. Manual verification required.",
    "reviewer_id": null, "created_at": "2026-09-04T08:29:16Z", "decided_at": null }] }
```

`POST /api/v1/reviews/{review_id}/approve`  (reviewer role)
`POST /api/v1/reviews/{review_id}/reject`  (reviewer role)
- No body. The reviewer is taken from the bearer token and recorded in the audit trail.
- Approve confirms the proposed link (creates/promotes an `entity_record_link`,
  decision `manual`), closes any other open case for the same record, and writes an audit row.
- Reject gives the record its **own** business identity (a new UBID with a founding link) and
  writes an audit row; undo removes that identity again while it is still unused.
- A case that is already decided answers `409`; approving a record that is already linked to a
  different business answers `409`.

## Corrections  (reviewer role — reversible graph edits)

`GET  /api/v1/corrections?limit=30&offset=0` → paged history of every correction,
each with `reversible` / `undone` flags and a `summary`.

`POST /api/v1/corrections/links/{link_id}/split`
`{ "reason": "...", "mode": "reopen_review" | "new_entity" }` — unlinks a source
record from a business: back to the review queue, or into its own identity.

`POST /api/v1/corrections/entities/{ubid}/status-override`
`{ "status": "active|dormant|closed", "reason": "..." }` — pins the lifecycle
status. The engine keeps recording its opinion in snapshots but stops changing
`status` until the pin is cleared.
`POST /api/v1/corrections/entities/{ubid}/status-override/clear` — unpin + recompute.

`POST /api/v1/corrections/events/{event_id}/reassign`
`{ "target_ubid": "UBID000123", "reason": "..." }` — moves an activity event to a
different business; both entities' statuses are recomputed.

`POST /api/v1/corrections/undo/{audit_id}` — reverses any of the above (and
approve/reject). It refuses a second undo of the same action, and refuses while a later,
still-active correction depends on the same link, record or business (undo that one first).
```json
{ "message": "Approval undone - link reverted, case reopened",
  "audit_id": "...", "detail": null }
```

## Status Engine

`GET /api/v1/status/{ubid}`  (reviewer) — recomputes + persists a snapshot, returns the
upper-case `status`. A business with no activity events is `UNKNOWN` (confidence 0), not `CLOSED`:
```json
{ "business_entity_id": "...", "ubid_code": "UBID-1A2B3C4D5E", "status": "ACTIVE",
  "confidence": 0.735, "reasons": ["POWER_USAGE: base=0.82, age=13d, decay=1.0, score=0.82", ...] }
```
`POST /api/v1/status/run-all`  (admin) — queues a batch recompute as a
background job (see **Background Jobs** below) instead of blocking the
request → `202` + a `Job`. Poll `GET /jobs/{id}`; its `result` has the same
`processed/failed/active/dormant/closed` shape the old synchronous response
used to return directly.

## Matching

`POST /api/v1/matching/process/{source_record_id}`  (404 on bad id)
```json
{ "decision": "REVIEW", "confidence": 0.73, "business_entity_id": "...",
  "reasons": ["Name similarity 0.98", "Address similarity 0.9", "PIN code match (141001)"] }
```

Signals & weights (score is capped at 1.0) — **admin-tunable**, no longer
fixed constants (defaults shown):

| Signal | Weight | Notes |
|---|---|---|
| GSTIN exact | 0.60 | unique government id — definitive on its own |
| PAN exact | 0.55 | derived from GSTIN when the PAN field is blank |
| Name similarity | 0.42 × score | token-sort fuzzy ratio |
| Address similarity | 0.28 × score | token-set ratio, filler words removed |
| PIN code exact | 0.12 | only counts when name similarity ≥ 0.35 |
| Contact (phone or email exact) | 0.06 | phone compared on its last 10 digits; only counts when name similarity ≥ 0.35 |

`decision` is `AUTO_LINK` at ≥ `auto_link_threshold` (0.92), `REVIEW` at ≥
`review_threshold` (0.70), otherwise `NEW_ENTITY` (the best candidate's score and reasons are kept in the
link's explanation). With the default weights, name + address + PIN + contact tops out at 0.88, so it
reaches `REVIEW` but never `AUTO_LINK` without an id anchor - an admin who retunes the weights can change
that. Processing is idempotent: a record that is already linked or in review keeps its decision.

`GET /api/v1/matching/weights`  (admin) → the nine tunable values above
plus `updated_by` / `updated_at`.
`PUT /api/v1/matching/weights`  (admin) — partial update, e.g.
`{ "review_threshold": 0.65 }`; each field is `0..1`, and `review_threshold` must not exceed
`auto_link_threshold` (`422` otherwise).

`GET /api/v1/matching/calibration`  (admin) — reviewer-feedback calibration:
buckets review cases by confidence range and shows the approve/reject split
in each, plus which evidence signals appear most in decided cases. Decision
support for tuning the weights above, not auto-tuning.
```json
{ "weights": { "...": "..." },
  "buckets": [{ "label": "0.80 - 0.89", "total": 109, "approved": 1,
                "rejected": 0, "pending": 108, "approve_rate": 1.0 }],
  "signals": [{ "signal": "Name", "approved": 1, "rejected": 0 }],
  "sample_size": 157 }
```
Bucket edges follow the live thresholds: three equal bands across the review range, then the auto-link range.

`GET /api/v1/matching/calibration/suggestion`  (admin) — **learned weights**. A small L2-regularised
logistic regression (numpy) is fitted on the evidence of approved / rejected review cases and its
coefficients become *suggested* weights. Needs 20+ decided cases with 5+ of each outcome (`ready: false`
and a `message` otherwise). A signal that never varies in the review band (typically GSTIN) is left alone;
every suggestion is clamped to 0.25x-2.5x of the current weight.
```json
{ "ready": true, "message": null, "decided": 62, "approved": 40, "rejected": 22, "accuracy": 0.9,
  "signals": [{ "field": "name_weight", "label": "Name similarity", "coefficient": 3.1,
                "approved_avg": 0.93, "rejected_avg": 0.61, "current_weight": 0.42,
                "suggested_weight": 0.55, "learned": true }] }
```
`POST /api/v1/matching/calibration/apply`  (admin) — recomputes the suggestion server-side and applies it
(`422` if not ready). Nothing is ever applied automatically.

## Ingestion

`GET /api/v1/ingest/source-systems` → `[{ code, name, department, record_count, pull_url, pull_kind,
last_pull_at, last_pull_status }]` (`pull_url` is `null` unless you are an admin)
`GET /api/v1/ingest/pending` → `{ "pending": 157 }` (records not linked and not in review)
`GET /api/v1/ingest/template` → a sample CSV (`text/csv`)

`POST /api/v1/ingest/csv`  (admin, `multipart/form-data`)
- `file` — the CSV; `source_system_code` — e.g. `LABOUR`; `process` — bool (default true)
- Headers are matched loosely: `name` / `firm_name` / `trade_name` / `consumer_name`…,
  `pan`, `gstin`, `address`, `pin` / `pincode`, `external_id` / `registration_no`…
  Unrecognised columns are kept in `raw_payload`. Missing `external_id` → a content hash
  (so re-imports dedupe).
- Row creation is synchronous; if `process` is true, matching those rows is
  queued as a `csv_match` background job (see below) instead of blocking the
  upload — a large batch no longer holds the request open.

`POST /api/v1/ingest/records`  (admin, JSON) — same shape, same job behaviour.
```json
{ "source_system_code": "LABOUR", "process": true,
  "records": [{ "name": "Punjab Steel Works", "pan": "ABCDE1234F",
                "address": "Focal Point, Ludhiana", "pin": "141001" }] }
```

Both return an ingestion report:
```json
{ "source_system": "LABOUR", "rows_read": 120, "created": 118,
  "skipped_duplicates": 2, "errors": [{ "row": 44, "error": "missing business name" }],
  "matching": null, "job_id": "..." }
```
`matching` is populated inline only if the job already finished by response
time (small batches, or `JOBS_SYNC=1`); otherwise poll `GET /jobs/{job_id}`.

### Activity events

Departments' filings, renewals, inspections and power readings. `event_type` is one of `gst_filed`,
`license_renewed`, `inspection`, `power_usage`, `employee_filing`, `payment_received`, `complaint`,
`document_update`, `zero_power_usage`, `suspension_notice`, `closure_notice`, `license_cancelled`.

`POST /api/v1/ingest/events`  (admin, JSON)
```json
{ "source_system_code": "LABOUR",
  "events": [{ "ubid": "UBID-1A2B3C4D5E", "event_type": "gst_filed", "occurred_at": "2026-09-30" },
             { "gstin": "03ABCDE1234F1Z5", "event_type": "inspection", "occurred_at": "2026-08-14" },
             { "external_id": "L-1001", "event_type": "license_renewed", "occurred_at": "2026-07-01" }] }
```
`POST /api/v1/ingest/events/csv`  (admin, `multipart/form-data`: `file`, optional `source_system_code`) —
same rows as CSV (`ubid`, `gstin`, `pan`, `external_id`, `event_type`, `occurred_at`; `GET /ingest/events/template`).

A row names its business by `ubid`, else `gstin`, else `pan`, else the department's own `external_id`
(needs `source_system_code`). Dates accept `YYYY-MM-DD` and `DD-MM-YYYY`. Re-sending a feed is harmless
(same business + type + date is skipped). Affected statuses are recomputed immediately (up to 200 businesses
per request; larger feeds wait for the next scheduled recompute).
```json
{ "rows_read": 3, "created": 3, "skipped_duplicates": 0, "unresolved": 0,
  "errors": [], "recomputed": 2 }
```

### Connectors and the scheduler

`PUT /api/v1/ingest/source-systems/{code}/connector`  (admin)
`{ "pull_url": "https://dept.example/export.csv", "pull_kind": "records" | "events" }` (`pull_url: null`
removes it). The URL must be `https` and resolve to a public address (`422` otherwise); redirects are not
followed; an export is capped at 8 MB; CSV and JSON (`[...]` or `{"records": [...]}` / `{"events": [...]}`)
are both accepted and use the same loose column matching as the CSV import.
`POST /api/v1/ingest/source-systems/{code}/sync`  (admin) — pulls it now → `202` + a `sync_connectors` job.
The outcome is also stored on the system (`last_pull_at`, `last_pull_status`).

`POST /api/v1/cron/tick`  (header `X-Cron-Secret: <CRON_SECRET>`; `404` while `CRON_SECRET` is unset,
`401` on a wrong secret) → `202` + a `sync_connectors` job with `full_cycle`: pull every connector, match
pending records, recompute every status. Jobs left `pending`/`running` by a restart are marked `failed` on
the next boot.

`POST /api/v1/ingest/process-pending?limit=1000`  (admin) — queues a
`process_pending` job over every unresolved source record → `202` + a `Job`.
Its `result` is `{ processed, auto_link, review, new_entity, failed }`.

---

## Background Jobs  (admin — see job_runner.py)

Batch status recompute and bulk matching run off the request thread on a
small in-process worker pool — no external queue/broker, just a DB-tracked
`Job` row so callers get a pollable status and an audit trail. Endpoints
that queue one return `202` with the `Job` below immediately; poll it.

`GET  /api/v1/jobs?job_type=&status=&limit=25&offset=0` → paged job history.
`GET  /api/v1/jobs/{id}` → one job (404 if unknown).
```json
{ "id": "...", "job_type": "status_run_all", "status": "succeeded",
  "payload": {}, "result": { "processed": 148, "failed": 0, "active": 65,
  "dormant": 25, "closed": 58, "errors": [] }, "error": null,
  "created_by": "admin", "created_at": "...", "started_at": "...",
  "finished_at": "..." }
```
`status` is `pending` → `running` → `succeeded` / `failed`. `job_type` is
one of `status_run_all`, `process_pending`, `csv_match`, `sync_connectors`.

---

## Audit

`GET /api/v1/audit?entity_type=&entity_id=&action=&business_id=&limit=50&offset=0`
(`business_id` returns everything that happened to one business: its own changes, its links, review
cases about it, its events and corrections; `404` for an unknown id)
```json
{ "total": 486, "limit": 50, "offset": 0,
  "items": [{ "id": "...", "actor_type": "system", "actor_id": null,
    "entity_type": "business_entity", "entity_id": "...", "action": "STATUS_UPDATED",
    "before_state": null, "after_state": { "status": "active", "confidence": 0.72, "reasons": [...] },
    "created_at": "2026-09-04T08:29:16Z" }] }
```

---

## Running the backend

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r backend/requirements.txt

python -m backend.seed_dev --reset   # build a local SQLite dataset
python -m uvicorn backend.app.main:app --reload
```

DB defaults to `sqlite:///./arthsetu_dev.db`. Override with `DATABASE_URL`
(e.g. Postgres) in `backend/.env`. Schema is managed by Alembic
(`alembic upgrade head`); the dev seeder also creates tables directly.

Sign-in needs a Firebase Auth target: run the Firebase Auth Emulator
(`npm install -g firebase-tools`, then `firebase emulators:start --only auth`)
and set `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` in `backend/.env` — see
`backend/.env.example`.

## Running with Docker

```bash
docker compose up --build
```
Brings up Postgres, the API (`alembic upgrade head` runs on container start)
on `:8000`, and the frontend behind nginx on `:8080` (nginx proxies `/api/`
to the backend container, so the SPA needs no CORS config). With no `.env`
file this runs in `APP_ENV=development` with insecure demo defaults, but
sign-in still needs a Firebase Auth target: the web-app config as `VITE_FIREBASE_*` in `.env` (baked into
the frontend image - rebuild after changing it), or an Auth Emulator on the host
(`FIREBASE_AUTH_EMULATOR_HOST=host.docker.internal:9099` for the backend,
`VITE_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` for the browser). There is no local-only auth bypass. On
first boot, if the `user_account` table is empty, the API creates one admin
account — in Firebase and locally — from `BOOTSTRAP_ADMIN_EMAIL` /
`BOOTSTRAP_ADMIN_PASSWORD` (default `admin@arthsetu.local` /
`arthsetu-admin`) — that's the login for a fresh container. Load the
synthetic demo dataset on top of it if you want one:
```bash
docker compose exec backend python -m backend.seed_dev --reset
```

**For a real deployment**, copy `.env.docker.example` to `.env` (repo root)
and fill in `FIREBASE_CREDENTIALS_JSON`, `FIREBASE_PROJECT_ID`,
`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, and `POSTGRES_PASSWORD`,
then set `APP_ENV=production`. The backend refuses to start in production
without a real Firebase project configured or with the default bootstrap
password still in place — a deliberate fail-fast guard
(`backend/app/core/config.py`), not a bug, so double-check
`docker compose logs backend` if the container exits immediately. Hardening
baked into the images:
- backend and frontend containers run as non-root users
- both have `HEALTHCHECK`s wired into compose's `depends_on: condition: service_healthy`
- Postgres isn't published to the host — only reachable from the backend over the compose network
- CPU/memory limits and `restart: unless-stopped` on every service
- nginx: security headers (`X-Frame-Options`, `X-Content-Type-Options`, etc.), gzip, `server_tokens off`, immutable caching on hashed assets, `no-cache` on `index.html`

## Deploying to Vercel + Render

An alternative to self-hosting the compose stack: static frontend on Vercel,
containerized backend on Render, Postgres from a free external provider.
The backend image listens on `$PORT` when it's set (Render assigns this
dynamically; falls back to 8000 otherwise), so the same `backend/Dockerfile`
works on both paths unmodified.

Render's own Postgres — even the free tier — requires a card on file
(anti-abuse policy, applies to every database regardless of plan).
[`render.yaml`](../render.yaml) sides around it: the web service is on
`plan: free` (genuinely free, no card) and `DATABASE_URL` isn't provisioned
by Render at all — you bring a free Postgres from
[Neon](https://neon.tech) or [Supabase](https://supabase.com) instead,
neither of which asks for a card on their free tier.

There's a chicken-and-egg between the platforms too — the backend's CORS
list needs the frontend's URL, the frontend's build needs the backend's URL
— so deploy in this order:

1. **Database.** Sign up at [neon.tech](https://neon.tech) (or Supabase),
   create a project, copy its connection string — looks like
   `postgresql://user:password@host/dbname?sslmode=require`. That works
   as-is for `DATABASE_URL`; SQLAlchemy defaults to the psycopg2 driver
   already in `backend/requirements.txt`, no `+psycopg2` suffix needed
   (a `postgres://` scheme is rewritten to `postgresql://` automatically).

1a. **Firebase setup.** Create a project at
   [console.firebase.google.com](https://console.firebase.google.com),
   enable the **Email/Password** sign-in provider (Authentication → Sign-in
   method). Generate a service-account key (Project settings → Service
   accounts → Generate new private key) — its JSON becomes
   `FIREBASE_CREDENTIALS_JSON` in step 2. Register a Web app (Project
   settings → Your apps) to get the `apiKey`/`authDomain`/`projectId`/`appId`
   values needed for `VITE_FIREBASE_*` in step 3.

2. **Backend on Render.** Dashboard → New → Blueprint → point it at this
   repo. Render reads `render.yaml` and, because `DATABASE_URL` has no
   `value`/`generateValue`, prompts you to paste it in — use the Neon
   connection string from step 1. `BOOTSTRAP_ADMIN_PASSWORD` is
   auto-generated (read the actual value off the service's Environment tab
   after it deploys — you'll need it to log in); `FIREBASE_CREDENTIALS_JSON`,
   `FIREBASE_PROJECT_ID`, and `BOOTSTRAP_ADMIN_EMAIL` need a Firebase
   project to exist first (see **Firebase setup** below) and are pasted in
   by hand. `CORS_ORIGINS` in the blueprint already names the project's own
   Vercel URL - change it in step 4 if yours differs. Note the service's
   `https://arthsetu-backend.onrender.com`-style URL once it's live and
   healthy. (Free plan: spins down after ~15 min idle, ~50s cold start on
   the next request — fine for a demo.)

3. **Frontend on Vercel.** Import the repo, set **Root Directory** to
   `frontend`. Framework preset (Vite) and build command are
   auto-detected. Add environment variables before the first build:
   `VITE_API_BASE_URL=https://<your-render-url>/api/v1` plus
   `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`,
   `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` from step 1a — Vite
   bakes these into the JS bundle at build time, so they can't be changed
   later without a rebuild. [`frontend/vercel.json`](../frontend/vercel.json)
   adds the SPA rewrite (client-side routes 404 on refresh without it) and
   the same security headers nginx sets in the Docker path. Note the
   resulting `https://<project>.vercel.app` URL.

4. **Close the loop.** Back on Render, update `CORS_ORIGINS` on
   `arthsetu-backend` to the real Vercel URL from step 3 (changing an env
   var triggers a redeploy automatically). Preview-deployment URLs
   (`<project>-<hash>.vercel.app`) won't match unless added too —
   `CORS_ORIGINS` is an exact comma-separated list, no wildcards.

5. **Log in** with `BOOTSTRAP_ADMIN_EMAIL` (set in step 2) / the generated
   `BOOTSTRAP_ADMIN_PASSWORD` from step 2. `backend/seed_dev.py` (drops
   tables, installs the publicly-known demo accounts below) refuses to run
   at all while `APP_ENV=production` — exactly the case here — so it can't
   be run by habit against a real deployment:
   ```bash
   $ python -m backend.seed_dev --reset
   Refusing to run against APP_ENV=production: this seeder drops tables
   and/or installs publicly-known demo credentials.
   Pass --force-production-seed if you genuinely mean it.
   ```
   That's the correct outcome for a real deployment — leave it there and
   keep the generated bootstrap credentials. For a throwaway showcase
   deployment where you *do* want the synthetic dataset, opt in explicitly:
   ```bash
   python -m backend.seed_dev --reset --force-production-seed
   ```
   which wipes and recreates every table, including `user_account` —
   replacing the bootstrap admin with the seeder's own demo accounts (see
   `DEMO_USERS` in `backend/seed_dev.py`; edit the placeholder emails there
   first if seeding a real Firebase project rather than the emulator).

6. **Optional: scheduled sync.** To pull connectors, match new records and refresh statuses
   automatically, set `CRON_SECRET` on the Render service (any long random string), then in the GitHub
   repo add the same value as the Actions secret `CRON_SECRET` and the repository variable `BACKEND_URL`
   (e.g. `https://arthsetu-backend.onrender.com`). [`scheduled-sync.yml`](../.github/workflows/scheduled-sync.yml)
   calls `POST /api/v1/cron/tick` every 6 hours and does nothing while those are unset. On the free
   plan the first call also wakes the service (~50 s), which the workflow allows for.
