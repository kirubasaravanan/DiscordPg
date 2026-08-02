# PG OS — System Architecture

Status: Phase 2 (Database) implemented under `backend/`. This was originally a Phase 1 (Architecture-only) document; §12 and §13 below now also record where implementation confirmed or corrected the original design — see [DATABASE.md](DATABASE.md) for the full implementation notes.

## 1. Overview

PG OS is a backend-first operating system for running a Paying Guest (PG) accommodation business. A single FastAPI backend is the source of truth for all data and business rules. Three surfaces sit on top of it — a Discord bot, an admin dashboard, and a local AI service — and none of them are permitted to bypass it.

Initial scale: 1 building, 30 rooms, 70 beds, multiple tenants. The design must not block the stated future goal of becoming a multi-PG SaaS platform, but it should not be over-built for that goal today (see [§10](#10-multi-tenancy--future-saas-path)).

## 2. Architectural Style

Layered / clean architecture, single writer of record:

- **One backend, one database.** The Discord bot, the dashboard, and the AI service are all clients of the FastAPI backend. None of them holds a database connection.
- **Unidirectional dependency flow.** API → Services → Database. A layer may only call the layer directly below it.
- **AI is advisory, not authoritative.** The AI service can read text and return structured suggestions. It cannot write to PostgreSQL and has no database credentials. The backend service layer decides what, if anything, gets persisted.

## 3. System Diagram

```mermaid
flowchart TB
    subgraph Clients
        DC[Discord Bot<br/>discord.py]
        DASH[Admin Dashboard<br/>Streamlit]
    end

    subgraph Backend["FastAPI Backend"]
        API[API Layer<br/>routers, auth, validation]
        SVC[Services Layer<br/>business logic]
        DBL[Database Layer<br/>SQLAlchemy models/repositories]
        SCHED[APScheduler<br/>background jobs]
    end

    PG[(PostgreSQL)]
    STORE[(Object Storage<br/>Cloudflare R2 / S3)]

    subgraph AI["AI Layer (isolated)"]
        AISVC[AI Service]
        OLLAMA[Ollama]
        QWEN[Qwen3 8B]
    end

    DC --> API
    DASH --> API
    API --> SVC
    SVC --> DBL
    DBL --> PG
    SVC --> STORE
    SCHED --> SVC
    SVC -- "structured request<br/>(text in)" --> AISVC
    AISVC -- "structured suggestion<br/>(JSON out)" --> SVC
    AISVC --> OLLAMA --> QWEN

    style AISVC fill:#2b2b2b,color:#fff
    style OLLAMA fill:#2b2b2b,color:#fff
    style QWEN fill:#2b2b2b,color:#fff
```

The AI box has no arrow into PostgreSQL. That is intentional and non-negotiable (see [§5](#5-layering--dependency-rules)).

## 4. Components

### 4.1 Discord Bot (`discord_bot/`)

- Library: `discord.py`.
- Presents tenant- and staff-facing slash commands (`/rent`, `/complaint`, `/rules`, `/status`).
- Holds no business logic and no direct database access. Every command call is a call to a FastAPI endpoint using a service-level credential or the invoking user's linked account.
- Maps Discord users to PG OS accounts via a `discord_id` on the `users` table (see [DATABASE.md](DATABASE.md)).

### 4.2 Admin Dashboard (`dashboard/`)

- Streamlit initially; React is the documented future replacement.
- Renders occupancy, rent, complaint, and expense views by calling the same FastAPI APIs the bot and any future clients use — no separate read path, no direct SQL.

### 4.3 FastAPI Backend (`backend/app/`)

The backend is internally layered:

| Layer | Directory | Responsibility |
|---|---|---|
| API | `api/` | HTTP routing, request/response schemas (Pydantic), auth dependency injection. No business logic. |
| Services | `services/` | Business rules, orchestration, transactions. Only layer allowed to call the AI service. |
| Database | `database/`, `models/` | SQLAlchemy models, session management, repository-style queries. |
| Security | `security/` | JWT issuing/verification, password hashing, RBAC checks. |
| Schemas | `schemas/` | Pydantic request/response contracts, shared across API and services. |
| Utils | `utils/` | Cross-cutting helpers with no business meaning of their own. |

Background jobs (APScheduler) live in the backend process and call the services layer exactly like an API request would — they do not touch the database layer directly, so a scheduled job and an HTTP request that trigger the same action run the same code path.

### 4.4 PostgreSQL

Single relational store for all operational data. See [DATABASE.md](DATABASE.md) for schema. Reachable only from the Database layer inside the backend.

### 4.5 AI Service (`ai_engine/`)

- Calls a local Ollama server running Qwen3 8B.
- Stateless with respect to PG OS data: every call receives exactly the text/context it needs as input and returns a structured JSON suggestion. It does not query the database itself and is not issued database credentials.
- Capabilities: complaint classification, tenant FAQ (RAG), report summarization, management insights. Full design deferred to Phase 6 ([AI_DESIGN.md](AI_DESIGN.md), not yet created).

### 4.6 Object Storage (Cloudflare R2 / S3-compatible)

- Holds tenant documents (ID proofs, agreements, photos).
- Backend issues short-lived pre-signed upload/download URLs; clients (dashboard, bot-driven flows) upload directly to storage, then confirm completion to the backend, which records `storage_url` and `verification_status`. The backend never proxies file bytes through itself.

## 5. Layering & Dependency Rules

1. API routers depend only on services. They never import SQLAlchemy models or open a DB session directly.
2. Services own transactions. A service method either fully succeeds or rolls back — no partial writes leaked to callers.
3. The database layer has no awareness of HTTP, Discord, or AI concepts — it only knows about persistence.
4. The AI service is called only from the services layer, never from an API router and never from the Discord bot or dashboard directly. This keeps the "AI never touches the database" rule enforceable in one place instead of scattered across every client.
5. The AI service's output is a suggestion. The service layer validates it against real constraints (e.g., an AI-suggested `priority` must be one of the enum values in [DATABASE.md](DATABASE.md); if not, the service falls back to a default) before persisting anything.

## 6. Request Flow Examples

### 6.1 Tenant files a complaint (Discord → AI classification → DB)

```mermaid
sequenceDiagram
    participant T as Tenant
    participant Bot as Discord Bot
    participant API as FastAPI
    participant SVC as Complaint Service
    participant AI as AI Service
    participant OL as Ollama (Qwen3)
    participant DB as PostgreSQL

    T->>Bot: /complaint "bathroom tap is leaking"
    Bot->>API: POST /api/v1/tenant/complaint (JWT)
    API->>SVC: create_complaint(tenant_id, description)
    SVC->>AI: classify(description)
    AI->>OL: prompt(description)
    OL-->>AI: {category, priority, suggested_action}
    AI-->>SVC: classification JSON
    SVC->>SVC: validate classification against enums
    SVC->>DB: INSERT complaint (status=OPEN)
    DB-->>SVC: complaint row
    SVC-->>API: complaint response
    API-->>Bot: 201 Created
    Bot-->>T: "Ticket #123 created — priority: HIGH"
```

### 6.2 Scheduled job: daily pending-rent check

```mermaid
sequenceDiagram
    participant SCHED as APScheduler
    participant SVC as Rent Service
    participant DB as PostgreSQL
    participant Bot as Discord Bot

    SCHED->>SVC: check_pending_rent()
    SVC->>DB: SELECT rent_ledger WHERE payment_status IN (PENDING, OVERDUE)
    DB-->>SVC: rows
    SVC->>Bot: notify(tenant, room, amount_due)
    Bot-->>SVC: delivery ack
```

## 7. Authentication & Authorization

- **AuthN:** JWT access tokens (short-lived) + refresh tokens (longer-lived), issued by `security/`. Passwords hashed with a modern algorithm (bcrypt/argon2 — finalized in Phase 3).
- **AuthZ:** Role-based access control with four roles: `OWNER`, `MANAGER`, `STAFF`, `TENANT`. Every API router declares the minimum role required per endpoint; the security layer enforces it as a FastAPI dependency, not as ad-hoc checks inside handlers. Full permission matrix in [API.md](API.md).
- A `TENANT`-role token is additionally scoped to that tenant's own `tenant_id` — tenant self-service endpoints filter by the authenticated tenant, never by a client-supplied ID.

## 8. Configuration & Secrets

- All configuration (database URL, JWT secret, Ollama host, storage credentials, Discord bot token) is read from environment variables via `.env` in development, real environment variables in production.
- No secret is ever committed. `.env.example` documents required keys with placeholder values.
- Config is loaded once at startup through a typed settings object (Pydantic `BaseSettings`), not read ad hoc via `os.environ` scattered through the codebase.

## 9. Background Jobs (APScheduler)

| Job | Schedule | Action |
|---|---|---|
| Pending rent check | Daily, 08:00 | Query `rent_ledger` for `PENDING`/`OVERDUE` entries; notify affected tenants and management via the Discord bot. |
| Management report | Daily, 21:00 | Summarize the day's occupancy, rent, complaints, expenses; post to a management Discord channel. |
| Income report | Monthly (1st, 09:00) | Aggregate the prior month's rent and expenses into an income report. |

Jobs call the services layer only — see [§4.3](#43-fastapi-backend-backendapp).

## 10. Multi-Tenancy / Future SaaS Path

The schema already models `Building` as a first-class entity, and `Room` (and optionally `Expense`) scope to `building_id`, even though v1 operates a single building. This is deliberate: it means the step from "one PG" to "multiple PGs under one owner" is a data change (add another `building` row), not a schema change.

Becoming a true multi-tenant SaaS (multiple unrelated PG *businesses* on shared infrastructure) is explicitly a **future goal**, not a v1 requirement, and is **not** implemented now: there is no `organization`/`account` boundary above `Building`, and rows are not partitioned by tenant-of-the-SaaS. When that becomes a real requirement, the natural extension is an `organization_id` above `Building`, propagated through row-level security or query scoping — but building that now would be speculative for a 30-room, single-owner deployment.

## 11. Non-Functional Requirements

- **Security:** JWT auth, RBAC on every endpoint, hashed passwords, no direct AI-to-DB path, secrets only via environment variables, pre-signed URLs for document storage instead of proxying files.
- **Reliability:** Service-layer transactions (no partial writes); Alembic migrations are the only way schema changes reach the database (no manual `ALTER TABLE`).
- **Observability:** Structured logging from the API and services layers (request id, user id, action) at minimum; deferred to Phase 3/7 for concrete tooling choice.
- **Performance:** At 30 rooms / 70 beds and a handful of admin users, there is no scale problem to solve. Indexing (see [DATABASE.md](DATABASE.md) §7) is chosen for query correctness and common access patterns, not premature optimization.
- **Portability:** Everything runs via Docker Compose in development; production targets a VPS/Railway (backend), Supabase (Postgres), Cloudflare R2 (storage), and a self-hosted Ollama instance — no component requires a proprietary managed service it can't be swapped out of.

## 12. Open Questions / Assumptions Made in This Phase

These are architectural decisions made to keep the spec complete and buildable. Flagging them here so they can be corrected before Phase 2 turns them into schema/code:

1. **Rent collection is tracked, not processed.** CLAUDE.md's stack has no payment gateway. This design assumes rent is collected offline (cash/UPI/bank transfer) and recorded into `rent_ledger` by staff or the tenant reporting it — PG OS does not move money. If online payment collection is actually required, that's a new component (payment gateway integration) not currently in scope. *(Still open — unaffected by Phase 2.)*
2. **A `User`/auth entity is added.** CLAUDE.md's Database Design section doesn't list a users table, but JWT auth + RBAC requires one. `users` is added with a nullable link from `tenants.user_id` (a tenant may or may not have portal/bot login access) — see [DATABASE.md](DATABASE.md). *(Implemented in Phase 2 as designed.)*
3. **Primary keys are UUIDs, not auto-increment integers** — chosen for non-enumerable tenant-facing IDs and to avoid ID collisions if multiple PGs' data is ever merged under the future SaaS model. See [DATABASE.md](DATABASE.md) §2 for the full rationale. *(Implemented in Phase 2 as designed.)*
4. **API paths are pluralized and versioned** (`/api/v1/tenants`, not `/tenant`) to follow REST convention, formalizing the illustrative endpoints listed in CLAUDE.md. See [API.md](API.md) for the mapping. *(Still open — not yet implemented; Phase 3.)*
5. **Document uploads use pre-signed URLs** rather than the backend proxying file bytes. *(Still open — not yet implemented; Phase 3.)*
6. **No `pgcrypto` extension needed, contrary to what Phase 1 assumed.** [DATABASE.md](DATABASE.md) §1 originally said UUID generation required the `pgcrypto` extension. Verified empirically against Postgres 16: `gen_random_uuid()` is a core built-in function since PostgreSQL 13, present with zero extensions installed. Corrected in [DATABASE.md](DATABASE.md) §1 — the initial migration does not create any extension.
7. **The seed script lives at `backend/app/database/seed.py`, not top-level `database/seed.py`.** The original Phase 1 mapping (§13 below) put it outside the `backend` package, which would have required cross-package `PYTHONPATH` tricks for no real benefit. Corrected in [DATABASE.md](DATABASE.md) §9.

## 13. Repository-to-Architecture Mapping

| Folder | Architectural layer |
|---|---|
| `backend/app/api/` | API layer |
| `backend/app/services/` | Services layer |
| `backend/app/models/`, `backend/app/database/` | Database layer |
| `backend/app/security/` | AuthN/AuthZ |
| `backend/app/schemas/` | Request/response contracts |
| `discord_bot/` | Client — Discord surface |
| `dashboard/` | Client — admin surface |
| `ai_engine/` | AI layer (isolated, no DB access) |
| `database/` | Reserved for raw SQL / reference artifacts (e.g. a schema dump) if a future phase needs one — not used by Phase 2. The seed script lives at `backend/app/database/seed.py` instead (see [DATABASE.md](DATABASE.md) §9); this folder does not exist yet. |
| `docs/` | This documentation set |
| `tests/` | Unit, API, and database tests |
| `docker/` | Container definitions |

## See Also

- [DATABASE.md](DATABASE.md) — schema, relationships, indexing, enums
- [API.md](API.md) — endpoint specification, permission matrix
- [ROADMAP.md](ROADMAP.md) — phased delivery plan
