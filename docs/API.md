# PG OS — API Specification

Status: Phase 1 (Architecture) deliverable. Defines the contract Phase 3 (Backend) will implement. No endpoints exist yet — once FastAPI is running, this document should stay in sync with (or be superseded by) its auto-generated OpenAPI schema.

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

`C`=Create, `R`=Read, `U`=Update, `D`=Delete (soft-delete where applicable, per [DATABASE.md](DATABASE.md) §2).

## 4. Tenant Self-Service APIs

All endpoints under `/api/v1/tenant/*` implicitly scope to the authenticated `TENANT`'s own `tenant_id` — no tenant can pass another tenant's ID and read their data.

| Method | Path | CLAUDE.md source | Description |
|---|---|---|---|
| GET | `/api/v1/tenant/profile` | `GET /tenant/profile` | Own profile. |
| PATCH | `/api/v1/tenant/profile` | *(added)* | Update own contact info (phone, email, emergency contact). |
| GET | `/api/v1/tenant/rent` | `GET /tenant/rent` | Own rent ledger history. |
| GET | `/api/v1/tenant/rent/{rent_id}` | *(added)* | Single rent ledger entry. |
| POST | `/api/v1/tenant/complaints` | `POST /tenant/complaint` | File a complaint. |
| GET | `/api/v1/tenant/complaints` | *(added)* | List own complaints + status. |
| GET | `/api/v1/tenant/documents` | *(added)* | List own documents. |
| POST | `/api/v1/tenant/documents` | *(added)* | Register an uploaded document (after pre-signed upload — see [ARCHITECTURE.md](ARCHITECTURE.md) §4.6). |

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
  "created_at": "2026-08-02T14:30:00Z"
}
```

`category` and `priority` are filled in by the AI classifier server-side (see [ARCHITECTURE.md](ARCHITECTURE.md) §6.1) — the tenant never supplies them.

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
{ "tenant_id": "...", "room_id": "...", "bed_id": "...", "start_date": "2026-08-05" }
```

The service layer rejects this if the bed already has an active allocation (see [DATABASE.md](DATABASE.md) §4.6 partial unique index) — that check is a database constraint backstopped by a friendly `409 Conflict` from the service layer, not just a raw constraint-violation error.

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
| DELETE | `/api/v1/expenses/{id}` | OWNER | *(added)* |

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
| PATCH | `/api/v1/documents/{id}/verify` | OWNER, MANAGER | *(added — set verification_status)* |

### 5.12 Dashboard & Reports

| Method | Path | Roles | CLAUDE.md source |
|---|---|---|---|
| GET | `/api/v1/dashboard` | OWNER, MANAGER, STAFF (partial) | `GET /dashboard` |
| GET | `/api/v1/reports/income` | OWNER, MANAGER | `GET /reports` |
| GET | `/api/v1/reports/occupancy` | OWNER, MANAGER | `GET /reports` |
| GET | `/api/v1/reports/complaints` | OWNER, MANAGER | `GET /reports` |

`GET /api/v1/dashboard` response shape (feeds the Streamlit dashboard's four views — occupancy, rent, complaints, expenses):

```json
{
  "occupancy": { "total_beds": 70, "occupied_beds": 63, "vacant_beds": 7 },
  "rent": { "collected_this_month": 189000.00, "pending_this_month": 21000.00, "overdue_count": 3 },
  "complaints": { "open": 5, "in_progress": 2, "urgent": 1 },
  "expenses": { "this_month": 42500.00 }
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

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, request flow examples
- [DATABASE.md](DATABASE.md) — underlying schema and enums
- [ROADMAP.md](ROADMAP.md) — when each endpoint group gets built
