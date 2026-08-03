# PG OS — API Specification

Status: Phases 3a, 3b, 3c, 5, and 6 all implemented — every backend endpoint in this document is live under `backend/`, with one gap noted inline (§4: `GET /api/v1/tenant/rent/{rent_id}` was never built). Documents (§5.11 and the documents portion of §4) ship with a local-filesystem storage backend by default and an R2/S3-compatible backend available via configuration — see [ARCHITECTURE.md](ARCHITECTURE.md) §4.6 and §12. §4.1's two endpoints back `discord_bot/` (Phase 5). `POST /api/v1/tenant/faq` (§4) and `GET /api/v1/reports/summary` (§5.12) are Phase 6 — see [AI_DESIGN.md](AI_DESIGN.md). The live OpenAPI schema (`/openapi.json` on a running server) is the definitive reference for what's implemented; this document is curated for readability and rationale.

## Deviations from CLAUDE.md's literal endpoint list

CLAUDE.md's API Requirements section lists 8 illustrative endpoints (`GET /tenant/profile`, `POST /room`, etc.). This spec formalizes them into a complete, production-shaped API rather than implementing only those 8 verbatim:

- Paths are **pluralized and versioned**: `POST /room` → `POST /api/v1/rooms`. Plural collection names and a version prefix are standard REST practice and CLAUDE.md's own Role/Coding Style sections call for production-grade, clean design.
- **Full CRUD is specified** for entities that only had a `POST` listed (e.g. Buildings and Beds had no endpoints at all in CLAUDE.md but need at least create/list to be usable, since Rooms depend on Buildings and Allocations depend on Beds).
- Endpoints needed to make listed features actually work end-to-end are added (e.g. recording a rent *payment*, updating a complaint's *status*) — CLAUDE.md lists `POST /tenant/complaint` (create) but a complaint workflow is not usable without a way for staff to update it.

Everything CLAUDE.md explicitly named is preserved below (see the "CLAUDE.md source" column) — nothing was removed, only expanded and made consistent.

## 1. Conventions

- **Base path:** `/api/v1`
- **Auth:** `Authorization: Bearer <JWT>` on every endpoint except `POST /api/v1/auth/login` and `POST /api/v1/auth/refresh`.
- **Content type:** `application/json` for all request/response bodies; file bytes never pass through the API (see [ARCHITECTURE.md](ARCHITECTURE.md) §4.6 — pre-signed URLs).
- **Timestamps:** ISO 8601, UTC (`2026-08-02T14:30:00Z`).
- **IDs:** UUIDv4 strings in paths and bodies (see [DATABASE.md](DATABASE.md) §2).
- **Pagination:** list endpoints accept `?page=1&page_size=20` (default `page_size=20`, max `100`) and respond with:

```json
{
  "items": [ /* ... */ ],
  "page": 1,
  "page_size": 20,
  "total": 137
}
```

- **Errors:** see [§7](#7-standard-error-format).

## 2. Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login` | none | Email/phone + password → access + refresh token. |
| POST | `/api/v1/auth/refresh` | refresh token | Exchange a valid refresh token for a new access token. |
| POST | `/api/v1/auth/logout` | access token | Invalidate the current refresh token. |
| POST | `/api/v1/auth/link-discord` | access token | *(added — Phase 5)* Set the caller's own `discord_id`. Any role. See [§4.1](#41-shared-endpoints-any-authenticated-role). |

`POST /api/v1/auth/login` request/response:

```json
// Request
{ "identifier": "owner@example.com", "password": "..." }

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "role": "OWNER"
}
```

User creation is an admin action (`POST /api/v1/users`, [§5.9](#59-users-owner-only)), not public self-registration — this is an operator-run PG, not an open sign-up product.

## 3. Role Permission Matrix

Proposed default; adjust before Phase 3 if the business rules differ.

| Resource | OWNER | MANAGER | STAFF | TENANT |
|---|---|---|---|---|
| Buildings | CRUD | R | R | – |
| Rooms | CRUD | CRU | R | – |
| Beds | CRUD | CRU | R | – |
| Tenants | CRUD | CRU | R | own profile only (R/U) |
| Allocations | CRUD | CRU | R | own (R) |
| Rent ledger | CRUD | CRU | R | own (R) |
| Security deposits | CRUD | CRU | – | own (R) |
| Complaints | CRUD | CRUD | RU (status/priority) | own (CR) |
| Expenses | CRUD | CRU | – | – |
| Documents | CRUD | CRU (verify) | R | own (CR) |
| Users | CRUD | – | – | – |
| Dashboard / Reports | R | R | limited (complaints only) | – |
| Rules | R | R | R | R |
| FAQ (RAG) | – | – | – | own (R via question) |

`C`=Create, `R`=Read, `U`=Update, `D`=Delete (soft-delete where applicable, per [DATABASE.md](DATABASE.md) §2).

## 4. Tenant Self-Service APIs

All endpoints under `/api/v1/tenant/*` implicitly scope to the authenticated `TENANT`'s own `tenant_id` — no tenant can pass another tenant's ID and read their data.

| Method | Path | CLAUDE.md source | Description |
|---|---|---|---|
| GET | `/api/v1/tenant/profile` | `GET /tenant/profile` | Own profile. |
| PATCH | `/api/v1/tenant/profile` | *(added)* | Update own contact info (phone, email, emergency contact). |
| GET | `/api/v1/tenant/rent` | `GET /tenant/rent` | Own rent ledger history. |
| GET | ~~`/api/v1/tenant/rent/{rent_id}`~~ | *(added, not implemented)* | Single rent ledger entry — noticed missing while documenting Phase 3c; low-priority since the list endpoint already returns every field. Not built. |
| POST | `/api/v1/tenant/complaints` | `POST /tenant/complaint` | File a complaint. |
| GET | `/api/v1/tenant/complaints` | *(added)* | List own complaints + status. |
| POST | `/api/v1/tenant/documents/upload-url` | *(added — Phase 3c)* | Get a pre-signed upload URL + `storage_key` for a new document. |
| POST | `/api/v1/tenant/documents` | *(added)* | Confirm/register a document after uploading to the URL above. |
| GET | `/api/v1/tenant/documents` | *(added)* | List own documents (metadata only — no `storage_url`). |
| GET | `/api/v1/tenant/documents/{id}/download-url` | *(added — Phase 3c)* | Get a fresh pre-signed download URL for one of your own documents. |
| POST | `/api/v1/tenant/faq` | *(added — Phase 6)* | Ask a question; answered via RAG over the PG rules/rent policy/maintenance knowledge base. |

`POST /api/v1/tenant/complaints` request/response:

```json
// Request
{ "description": "My bathroom tap is leaking", "room_id": "..." }

// Response 201
{
  "id": "9c3e...",
  "category": "PLUMBING",
  "priority": "HIGH",
  "status": "OPEN",
  "description": "My bathroom tap is leaking",
  "suggested_action": "Send a plumber to replace the tap washer.",
  "created_at": "2026-08-02T14:30:00Z"
}
```

`category`, `priority`, and `suggested_action` are filled in by the AI classifier server-side (see [ARCHITECTURE.md](ARCHITECTURE.md) §6.1, [AI_DESIGN.md](AI_DESIGN.md) §2) — the tenant never supplies them directly (`category` may be *suggested*, per the request shape above). **Implemented as of Phase 6** — but every field is still validated/clamped by the service layer before persisting, and degrades to Phase 3b's original placeholder behavior (tenant's suggestion or `OTHER`, `MEDIUM` priority, no `suggested_action`) if the AI service is unreachable or returns something invalid; see [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 11 and [AI_DESIGN.md](AI_DESIGN.md) §2.

`POST /api/v1/tenant/faq` request/response:

```json
// Request
{ "question": "When is rent due?" }

// Response 200
{
  "answer": "Rent is due on the 5th of each month.",
  "cited_sources": ["rent_policy.md"]
}

// Response 503 if the AI service is unavailable — no fallback answer is
// fabricated; the error is honest rather than silently wrong.
{ "error": { "code": "SERVICE_UNAVAILABLE", "message": "The FAQ assistant is temporarily unavailable. Please try again later.", "field": null } }
```

`cited_sources` lists which knowledge-base file(s) ([AI_DESIGN.md](AI_DESIGN.md) §3) the retrieved context actually came from — built from the retrieval step itself, not parsed out of the model's answer text.

**Document upload flow** (Phase 3c), matching the pre-signed URL pattern from [ARCHITECTURE.md](ARCHITECTURE.md) §4.6:

```json
// 1. POST /api/v1/tenant/documents/upload-url — request: empty body. Response:
{
  "storage_key": "tenants/<tenant_id>/<uuid>",
  "upload_url": "https://...",
  "method": "PUT",
  "expires_in": 900
}

// 2. Client PUTs the file's raw bytes directly to upload_url. No further API call needed for that step.

// 3. POST /api/v1/tenant/documents — request:
{ "document_type": "ID_PROOF", "storage_key": "tenants/<tenant_id>/<uuid>" }
// Response 201: a DocumentRead (below). 400 if nothing was actually uploaded to that key yet.

// GET /api/v1/tenant/documents/{id}/download-url — response:
{ "download_url": "https://...", "expires_in": 900 }
```

`DocumentRead` shape (admin `GET /api/v1/documents` returns the same shape):

```json
{
  "id": "...",
  "tenant_id": "...",
  "document_type": "ID_PROOF",
  "verification_status": "PENDING",
  "created_at": "2026-08-02T14:30:00Z",
  "updated_at": null
}
```

`storage_url`/`storage_key` is deliberately never returned in a document's own read shape — it's an internal key, not something a client uses directly. Get a fresh, time-limited download URL from the dedicated endpoint instead.

## 4.1 Shared Endpoints (any authenticated role)

Added in Phase 5 for `discord_bot/`. Unlike §4, these aren't scoped to a tenant — any authenticated role can call them (see the Role Permission Matrix above).

| Method | Path | CLAUDE.md source | Description |
|---|---|---|---|
| POST | `/api/v1/auth/link-discord` | *(added)* | Set the caller's own `discord_id` (`users.discord_id`, [DATABASE.md](DATABASE.md) §4.1). Idempotent for the same account; `409` if that Discord ID is already linked to a *different* account. |
| GET | `/api/v1/rules` | `/rules` (Discord command) | Static PG house rules content. |

`POST /api/v1/auth/link-discord` request/response:

```json
// Request
{ "discord_id": "111122223333" }

// Response 200
{ "discord_id": "111122223333" }
```

`GET /api/v1/rules` response:

```json
{ "content": "# Sunrise PG — House Rules\n\n## Check-in / check-out\n..." }
```

Content is a single markdown string sourced from `backend/app/content/pg_rules.md` (edit the file directly — no migration or redeploy needed beyond a process restart; see `app/services/rules_service.py`). Phase 6 replaces the *source* of this content with `pgvector`-backed RAG over the same file, not the endpoint's contract.

Every endpoint in this document requires Bearer auth except login/refresh (§1) — `/rules` follows that same rule rather than being a carve-out, even though its content isn't sensitive, so a Discord user must `/link` before any of the bot's four commands work, `/rules` included.

## 5. Admin APIs

### 5.1 Buildings

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/buildings` | OWNER, MANAGER, STAFF | *(added — needed to list before creating rooms)* |
| POST | `/api/v1/buildings` | OWNER | *(added)* |
| GET | `/api/v1/buildings/{id}` | OWNER, MANAGER, STAFF | *(added)* |
| PATCH | `/api/v1/buildings/{id}` | OWNER | *(added)* |
| DELETE | `/api/v1/buildings/{id}` | OWNER | *(added, soft-delete)* |

### 5.2 Rooms

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/rooms` | OWNER, MANAGER, STAFF | *(added)* |
| POST | `/api/v1/rooms` | OWNER, MANAGER | `POST /room` |
| GET | `/api/v1/rooms/{id}` | OWNER, MANAGER, STAFF | *(added)* |
| PATCH | `/api/v1/rooms/{id}` | OWNER, MANAGER | *(added)* |
| DELETE | `/api/v1/rooms/{id}` | OWNER | *(added, soft-delete)* |

### 5.3 Beds

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/beds` | OWNER, MANAGER, STAFF | *(added)* |
| POST | `/api/v1/beds` | OWNER, MANAGER | *(added — Bed is a modeled entity with no endpoint in CLAUDE.md)* |
| GET | `/api/v1/beds/{id}` | OWNER, MANAGER, STAFF | *(added)* |
| PATCH | `/api/v1/beds/{id}` | OWNER, MANAGER | *(added)* |
| DELETE | `/api/v1/beds/{id}` | OWNER | *(added, soft-delete)* |

### 5.4 Tenants

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/tenants` | OWNER, MANAGER, STAFF | *(added)* |
| POST | `/api/v1/tenants` | OWNER, MANAGER | `POST /tenant` |
| GET | `/api/v1/tenants/{id}` | OWNER, MANAGER, STAFF | *(added)* |
| PATCH | `/api/v1/tenants/{id}` | OWNER, MANAGER | *(added)* |
| DELETE | `/api/v1/tenants/{id}` | OWNER | *(added, soft-delete — records exit)* |

### 5.5 Allocations

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/allocations` | OWNER, MANAGER, STAFF | *(added)* |
| POST | `/api/v1/allocations` | OWNER, MANAGER | `POST /allocation` |
| PATCH | `/api/v1/allocations/{id}/end` | OWNER, MANAGER | *(added — checkout / end an active allocation, sets `end_date` and frees the bed)* |

`POST /api/v1/allocations` request:

```json
{ "tenant_id": "...", "bed_id": "...", "start_date": "2026-08-05" }
```

**Implemented in Phase 3a without `room_id` in the request body**, unlike the shape shown here in earlier drafts of this document — `room_id` is derived server-side from `bed.room_id` instead. Requiring the client to also supply `room_id` only created a way to send a value that disagrees with the bed's actual room, for no benefit; the response body still includes `room_id` (read from the bed) so clients don't lose the information.

The service layer rejects the request with `409 Conflict` if the target bed's `status` is not `VACANT` — covering both "already has an active allocation" (backed by the [DATABASE.md](DATABASE.md) §4.6 partial unique index) and "bed is under `MAINTENANCE`" in one check, with a friendlier message than a raw constraint-violation error.

`PATCH /api/v1/allocations/{id}/end` request (both fields optional — an empty body ends the allocation as of today):

```json
{ "end_date": "2026-08-05" }
```

Ending an allocation also flips the bed back to `VACANT` and, if the room had been `FULL`, the room back to `AVAILABLE`. Creating an allocation does the reverse (bed → `OCCUPIED`, room → `FULL` once its last vacant bed is taken). This is why `PATCH /api/v1/rooms/{id}` and `PATCH /api/v1/beds/{id}` reject `FULL`/`OCCUPIED` respectively when set directly (`400`) — those two specific values are derived from allocation state, not staff-editable; every other status value on both resources is still a normal manual edit.

### 5.6 Rent Ledger

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/rent` | OWNER, MANAGER, STAFF | *(added — admin view across tenants)* |
| POST | `/api/v1/rent` | OWNER, MANAGER | *(added — generate a month's ledger entries)* |
| PATCH | `/api/v1/rent/{id}/payment` | OWNER, MANAGER | *(added — record a payment against an entry)* |

### 5.7 Security Deposits

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/deposits` | OWNER, MANAGER | *(added)* |
| POST | `/api/v1/deposits` | OWNER, MANAGER | *(added)* |
| PATCH | `/api/v1/deposits/{id}` | OWNER, MANAGER | *(added — update refund_status)* |

### 5.8 Complaints

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/complaints` | OWNER, MANAGER, STAFF | *(added — the queue staff work from)* |
| GET | `/api/v1/complaints/{id}` | OWNER, MANAGER, STAFF | *(added)* |
| PATCH | `/api/v1/complaints/{id}` | OWNER, MANAGER, STAFF | *(added — update status/priority; sets `resolved_at` on `RESOLVED`)* |

### 5.9 Expenses

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/expenses` | OWNER, MANAGER | *(added)* |
| POST | `/api/v1/expenses` | OWNER, MANAGER | *(added — Expense is a modeled entity with no endpoint in CLAUDE.md)* |
| PATCH | `/api/v1/expenses/{id}` | OWNER, MANAGER | *(added)* |

**No `DELETE` endpoint** — corrected in Phase 3b. An earlier draft of this table had one, but that directly contradicted [DATABASE.md](DATABASE.md) §2's own append-only rule ("`rent_ledger`, `security_deposits`, `complaints`, `expenses`, `allocations` are never deleted, only status-transitioned, so history is always reconstructable"), which `expenses` is explicitly listed under. A mis-entered expense is corrected via `PATCH`, not removed.

### 5.10 Users (OWNER only)

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/users` | OWNER | *(added — required by Security Requirements' RBAC, not explicit in CLAUDE.md's API list)* |
| POST | `/api/v1/users` | OWNER | *(added)* |
| PATCH | `/api/v1/users/{id}` | OWNER | *(added — role changes, deactivation)* |

### 5.11 Documents

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/documents` | OWNER, MANAGER, STAFF (read) | *(added)* |
| GET | `/api/v1/documents/{id}/download-url` | OWNER, MANAGER, STAFF | *(added — Phase 3c; staff can't verify a document they have no way to actually view)* |
| PATCH | `/api/v1/documents/{id}/verify` | OWNER, MANAGER | *(added — set verification_status)* |

Response shapes match the tenant-facing ones in §4 (`DocumentRead`, `DownloadURLResponse`) — this is the same `documents` table, just an admin-wide view instead of scoped to one tenant.

### 5.12 Dashboard & Reports

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/dashboard` | OWNER, MANAGER, STAFF (partial) | `GET /dashboard` |
| GET | `/api/v1/reports/income` | OWNER, MANAGER | `GET /reports` |
| GET | `/api/v1/reports/occupancy` | OWNER, MANAGER | `GET /reports` |
| GET | `/api/v1/reports/complaints` | OWNER, MANAGER | `GET /reports` |
| GET | `/api/v1/reports/summary` | OWNER, MANAGER | *(added — Phase 6)* AI-generated management summary; on-demand version of the daily 21:00 job. |

`GET /api/v1/dashboard` response shape (feeds the Streamlit dashboard's four views — occupancy, rent, complaints, expenses):

```json
{
  "occupancy": { "total_beds": 70, "occupied_beds": 63, "vacant_beds": 7 },
  "rent": { "collected_this_month": 189000.00, "pending_this_month": 21000.00, "overdue_count": 3 },
  "complaints": { "open": 5, "in_progress": 2, "urgent": 1 },
  "expenses": { "this_month": 42500.00 }
}
```

`rent.collected_this_month`/`pending_this_month` are scoped to the current calendar month's `rent_ledger` rows; `rent.overdue_count` deliberately is not — it counts every `OVERDUE` row regardless of month, since a stale unpaid balance from any prior month still belongs on a "needs attention" dashboard. `complaints.urgent` counts `priority=URGENT` rows that are not `RESOLVED`/`CLOSED` — an urgent complaint that's already handled shouldn't show up as needing attention.

**The three report response shapes below were designed during Phase 3b implementation** — this document originally specified only their paths and roles, not a body:

`GET /api/v1/reports/income?months=6` (query param `months`, default 6, max 24) — trailing months oldest-first, each a net of rent collected vs. expenses recorded in that month:

```json
{
  "rows": [
    { "month": "2026-06-01", "rent_collected": 47500.00, "expenses": 0.00, "net": 47500.00 },
    { "month": "2026-07-01", "rent_collected": 38000.00, "expenses": 21700.00, "net": 16300.00 }
  ]
}
```

`GET /api/v1/reports/occupancy` — one row per active room, complementing the dashboard's single aggregate number with a per-room breakdown:

```json
{
  "rows": [
    { "room_id": "...", "building_id": "...", "room_number": "101", "capacity": 2, "occupied_beds": 2, "status": "FULL" }
  ]
}
```

`GET /api/v1/reports/complaints` — category breakdown, sorted by total volume descending; `open_count` includes `OPEN`, `IN_PROGRESS`, and `REOPENED`:

```json
{
  "by_category": [
    { "category": "PLUMBING", "open_count": 2, "total_count": 5 }
  ]
}
```

`GET /api/v1/reports/summary` (Phase 6, [AI_DESIGN.md](AI_DESIGN.md) §4) — AI-narrated version of `GET /api/v1/dashboard`'s stats; falls back to a plain-text stats readout (not an error) if the AI service is unavailable, since the underlying numbers are always available regardless:

```json
{
  "summary": "Occupancy is steady at 90%. Two rent entries are overdue and should be followed up on. One urgent complaint (WIFI) needs attention; everything else is on track."
}
```

## 6. Standard Error Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "rent_amount must be greater than or equal to 0",
    "field": "rent_amount"
  }
}
```

## 7. Status Codes

| Code | Meaning |
|---|---|
| 200 | Success (read/update) |
| 201 | Created |
| 204 | Success, no body (e.g. logout) |
| 400 | Validation error |
| 401 | Missing/invalid/expired token |
| 403 | Authenticated but not authorized for this resource/role |
| 404 | Resource not found (or soft-deleted) |
| 409 | Conflict (e.g. bed already occupied, duplicate rent_ledger month) |
| 422 | Semantically invalid request body (FastAPI/Pydantic default) |
| 500 | Unhandled server error |

**Phase 3a implementation note:** most 409s are raised deliberately by a service with a specific message (e.g. "Cannot delete a building that still has active rooms."). As a safety net, any database constraint violation a service *didn't* pre-check also becomes a 409 automatically (a generic "The request conflicts with existing data." message) rather than surfacing as a 500 — see `backend/app/main.py`'s handler for `sqlalchemy.exc.IntegrityError`.

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, request flow examples
- [DATABASE.md](DATABASE.md) — underlying schema and enums
- [ROADMAP.md](ROADMAP.md) — when each endpoint group gets built
