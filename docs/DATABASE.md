# PG OS — Database Design

Status: Phase 2 (Database) implemented, plus additions from Phase 3a (`users.token_version`, §4.1) and Phase 6 (`complaints.suggested_action` §4.9; `rag_document_chunks` §4.12). Four migrations exist under `backend/alembic/versions/`: the initial schema, `token_version`, `rag_document_chunks` (+ `pgvector` extension), and `suggested_action`. This document has been updated to match; see the "implementation notes" callouts below for anything that changed from the original Phase 1 design.

## 1. Overview

- Engine: PostgreSQL (developed/tested against 16)
- ORM: SQLAlchemy 2.0 (`backend/app/models/`)
- Migrations: Alembic (`backend/alembic/`) — schema changes only ever happen through a migration, never a manual `ALTER TABLE` against a live database
- Extensions: none required for the core schema — `gen_random_uuid()` has been a core PostgreSQL 13+ function since PG13, not a `pgcrypto`-only function as originally assumed in Phase 1 (verified directly: it works on a fresh database with zero extensions installed). `pgvector` **is** required for `rag_document_chunks` (§4.12, Phase 6) — genuinely installed and enabled in this environment (the `postgresql-16-pgvector` apt package, unlike Ollama itself, isn't network-blocked); see §8's Phase 6 note for the one gotcha (enabling it needs a one-time privileged step, separate from the app's own migration role).

## 2. Conventions

| Convention | Decision | Rationale |
|---|---|---|
| Primary keys | `UUID` (v4), default `gen_random_uuid()` | Non-enumerable in tenant-facing APIs (no IDOR-by-guessing); avoids ID collisions if multiple PG properties' data is ever merged under the future SaaS model. At this scale (~100 rows/table) the minor index-size cost vs. `BIGSERIAL` is irrelevant. |
| Table names | Plural, `snake_case` (`tenants`, `rent_ledger`) | Standard SQLAlchemy/Postgres convention; a table is a collection of rows. |
| Column names | `snake_case` | Postgres convention; avoids quoting. |
| Money | `NUMERIC(10,2)` | Exact decimal arithmetic — never `FLOAT`/`DOUBLE` for currency. |
| Timestamps | `TIMESTAMPTZ` | Always store in UTC; convert at the presentation layer. |
| Audit fields | `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ`, `created_by UUID NULL REFERENCES users(id)`, `updated_by UUID NULL REFERENCES users(id)` | Applied to every table. `created_by`/`updated_by` are nullable to allow system/scheduler-originated rows. |
| Soft delete | `is_deleted BOOLEAN NOT NULL DEFAULT false`, `deleted_at TIMESTAMPTZ NULL` | Applied to **master/reference data** the business can "remove" from active use: `buildings`, `rooms`, `beds`, `tenants`, `documents`, `users`. **Not** applied to append-only financial/audit records — `rent_ledger`, `security_deposits`, `complaints`, `expenses`, `allocations` are never deleted, only status-transitioned, so history is always reconstructable. |
| Enums | Native Postgres `ENUM` types via SQLAlchemy `Enum` | Enforced at the database level, not just application level. |

## 3. Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o| TENANTS : "linked account (optional)"
    BUILDINGS ||--o{ ROOMS : has
    ROOMS ||--o{ BEDS : has
    TENANTS ||--o{ ALLOCATIONS : has
    ROOMS ||--o{ ALLOCATIONS : "allocated in"
    BEDS ||--o{ ALLOCATIONS : "allocated in"
    TENANTS ||--o{ RENT_LEDGER : owes
    TENANTS ||--o{ SECURITY_DEPOSITS : pays
    TENANTS ||--o{ COMPLAINTS : files
    ROOMS ||--o{ COMPLAINTS : "concerns (optional)"
    TENANTS ||--o{ DOCUMENTS : uploads
    BUILDINGS ||--o{ EXPENSES : "incurred at (optional)"

    USERS {
        uuid id PK
        string email
        string phone
        string password_hash
        enum role
        string discord_id
        bool is_active
    }
    BUILDINGS {
        uuid id PK
        string name
        text address
    }
    ROOMS {
        uuid id PK
        uuid building_id FK
        string room_number
        int floor
        int capacity
        enum status
    }
    BEDS {
        uuid id PK
        uuid room_id FK
        string bed_number
        enum status
    }
    TENANTS {
        uuid id PK
        uuid user_id FK
        string name
        string phone
        string email
        string emergency_contact
        date joining_date
        date exit_date
        enum status
    }
    ALLOCATIONS {
        uuid id PK
        uuid tenant_id FK
        uuid room_id FK
        uuid bed_id FK
        date start_date
        date end_date
    }
    RENT_LEDGER {
        uuid id PK
        uuid tenant_id FK
        date month
        numeric rent_amount
        numeric paid_amount
        numeric balance
        date due_date
        enum payment_status
    }
    SECURITY_DEPOSITS {
        uuid id PK
        uuid tenant_id FK
        numeric amount
        date received_date
        enum refund_status
    }
    COMPLAINTS {
        uuid id PK
        uuid tenant_id FK
        uuid room_id FK
        enum category
        text description
        enum priority
        enum status
        timestamptz resolved_at
    }
    EXPENSES {
        uuid id PK
        uuid building_id FK
        enum category
        numeric amount
        date date
        string vendor
        text notes
    }
    DOCUMENTS {
        uuid id PK
        uuid tenant_id FK
        enum document_type
        text storage_url
        enum verification_status
    }
```

## 4. Entities

Audit columns (`created_at`, `updated_at`, `created_by`, `updated_by`) and, where applicable, soft-delete columns (`is_deleted`, `deleted_at`) are omitted from the tables below to avoid repetition — assume every entity has the audit columns, and every entity marked **soft-delete: yes** in its heading also has `is_deleted`/`deleted_at`.

### 4.1 `users` (soft-delete: yes)

Added beyond CLAUDE.md's explicit entity list — required to back JWT auth + RBAC (see [ARCHITECTURE.md](ARCHITECTURE.md) §12).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier for staff/owner. |
| phone | VARCHAR(20) | UNIQUE, NULL | |
| password_hash | VARCHAR(255) | NOT NULL | Argon2id (`argon2-cffi`) — decided in Phase 3a, OWASP's current recommended default; a 97-character encoded hash comfortably fits `VARCHAR(255)`. |
| role | ENUM `user_role` | NOT NULL | `OWNER`, `MANAGER`, `STAFF`, `TENANT`. |
| discord_id | VARCHAR(32) | UNIQUE, NULL | Links a Discord account to a PG OS user for bot commands. |
| is_active | BOOLEAN | NOT NULL DEFAULT true | Deactivate without deleting. |
| token_version | INTEGER | NOT NULL DEFAULT 0 | **Added in Phase 3a**, beyond the original Phase 1 design — not requested by CLAUDE.md or planned in this document before implementation. `POST /api/v1/auth/logout` requires *some* server-side state to actually invalidate a refresh token (a bare JWT can't be revoked by itself); bumping this column invalidates every refresh token issued for that user before the bump. See [ARCHITECTURE.md](ARCHITECTURE.md) §7 and `backend/app/security/jwt.py`. |

### 4.2 `buildings` (soft-delete: yes)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| name | VARCHAR(255) | NOT NULL | |
| address | TEXT | NULL | |

### 4.3 `rooms` (soft-delete: yes)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| building_id | UUID | FK → `buildings.id`, NOT NULL | |
| room_number | VARCHAR(20) | NOT NULL | |
| floor | INTEGER | NULL | |
| capacity | INTEGER | NOT NULL, CHECK (capacity > 0) | Max beds in the room. |
| status | ENUM `room_status` | NOT NULL DEFAULT `AVAILABLE` | `AVAILABLE`, `FULL`, `MAINTENANCE`, `INACTIVE`. |

Constraint: `UNIQUE (building_id, room_number)`.

### 4.4 `beds` (soft-delete: yes)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| room_id | UUID | FK → `rooms.id`, NOT NULL | |
| bed_number | VARCHAR(10) | NOT NULL | |
| status | ENUM `bed_status` | NOT NULL DEFAULT `VACANT` | `VACANT`, `OCCUPIED`, `MAINTENANCE`. |

Constraint: `UNIQUE (room_id, bed_number)`.

### 4.5 `tenants` (soft-delete: yes)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → `users.id`, UNIQUE, NULL | Set only if the tenant has portal/bot login access. |
| name | VARCHAR(255) | NOT NULL | |
| phone | VARCHAR(20) | NOT NULL, UNIQUE | |
| email | VARCHAR(255) | UNIQUE, NULL | |
| emergency_contact | VARCHAR(20) | NULL | |
| joining_date | DATE | NOT NULL | |
| exit_date | DATE | NULL | |
| status | ENUM `tenant_status` | NOT NULL DEFAULT `ACTIVE` | `ACTIVE`, `NOTICE_PERIOD`, `EXITED`, `BLACKLISTED`. |

### 4.6 `allocations` (soft-delete: no — append-only)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | FK → `tenants.id`, NOT NULL | |
| room_id | UUID | FK → `rooms.id`, NOT NULL | Denormalized alongside `bed_id` for query convenience (a bed's room shouldn't change, but this avoids a join for room-level occupancy checks). |
| bed_id | UUID | FK → `beds.id`, NOT NULL | |
| start_date | DATE | NOT NULL | |
| end_date | DATE | NULL | `NULL` = currently active allocation. |

Constraint: partial unique index ensuring a bed has at most one active allocation at a time: `UNIQUE (bed_id) WHERE end_date IS NULL`.

### 4.7 `rent_ledger` (soft-delete: no — append-only)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | FK → `tenants.id`, NOT NULL | |
| month | DATE | NOT NULL | First-of-month convention, e.g. `2026-08-01`, for one row per tenant per month. |
| rent_amount | NUMERIC(10,2) | NOT NULL, CHECK (rent_amount >= 0) | |
| paid_amount | NUMERIC(10,2) | NOT NULL DEFAULT 0, CHECK (paid_amount >= 0) | |
| balance | NUMERIC(10,2) | NOT NULL | Maintained as `rent_amount - paid_amount` by the service layer (application-computed, not a generated column, so partial payments can be recorded with an audit trail). |
| due_date | DATE | NOT NULL | |
| payment_status | ENUM `payment_status` | NOT NULL DEFAULT `PENDING` | `PENDING`, `PARTIAL`, `PAID`, `OVERDUE`. |

Constraint: `UNIQUE (tenant_id, month)`.

### 4.8 `security_deposits` (soft-delete: no — append-only)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | FK → `tenants.id`, NOT NULL | |
| amount | NUMERIC(10,2) | NOT NULL, CHECK (amount >= 0) | |
| received_date | DATE | NOT NULL | |
| refund_status | ENUM `refund_status` | NOT NULL DEFAULT `HELD` | `HELD`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FORFEITED`. |

### 4.9 `complaints` (soft-delete: no — append-only)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | FK → `tenants.id`, NOT NULL | |
| room_id | UUID | FK → `rooms.id`, NULL | A complaint may not be room-specific (e.g., billing question). |
| category | ENUM `complaint_category` | NOT NULL | `PLUMBING`, `ELECTRICAL`, `CLEANING`, `WIFI`, `FOOD`, `SECURITY`, `OTHER`. Assigned by the AI classifier, validated by the service layer against this enum before persisting. |
| description | TEXT | NOT NULL | |
| priority | ENUM `priority` | NOT NULL DEFAULT `MEDIUM` | `LOW`, `MEDIUM`, `HIGH`, `URGENT`. |
| status | ENUM `complaint_status` | NOT NULL DEFAULT `OPEN` | `OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`, `REOPENED`. |
| suggested_action | TEXT | NULL | **Added in Phase 6** — the AI classifier's advisory next-step text, shown to staff as context; nothing automated reads it. `NULL` if the classifier was unreachable when the complaint was filed. See [AI_DESIGN.md](AI_DESIGN.md) §2. |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | (Listed explicitly here — same column as the standard audit field.) |
| resolved_at | TIMESTAMPTZ | NULL | Set when `status` transitions to `RESOLVED`. |

### 4.10 `expenses` (soft-delete: no — append-only)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| building_id | UUID | FK → `buildings.id`, NULL | Added beyond CLAUDE.md's field list so multi-building expense reporting works once a second building exists; nullable so general/company-level expenses are still valid. |
| category | ENUM `expense_category` | NOT NULL | `MAINTENANCE`, `UTILITIES`, `SALARY`, `SUPPLIES`, `OTHER`. |
| amount | NUMERIC(10,2) | NOT NULL, CHECK (amount >= 0) | |
| date | DATE | NOT NULL | |
| vendor | VARCHAR(255) | NULL | |
| notes | TEXT | NULL | |

### 4.11 `documents` (soft-delete: yes)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenant_id | UUID | FK → `tenants.id`, NOT NULL | |
| document_type | ENUM `document_type` | NOT NULL | `ID_PROOF`, `ADDRESS_PROOF`, `AGREEMENT`, `PHOTO`, `OTHER`. |
| storage_url | TEXT | NOT NULL | Object key/URL in R2/S3, not a public link — resolved to a pre-signed download URL at request time. |
| verification_status | ENUM `verification_status` | NOT NULL DEFAULT `PENDING` | `PENDING`, `VERIFIED`, `REJECTED`. |

### 4.12 `rag_document_chunks` (soft-delete: no — regenerated by re-ingestion)

Added in Phase 6 ([AI_DESIGN.md](AI_DESIGN.md) §3) — the RAG knowledge base backing the tenant FAQ. Not in CLAUDE.md's original Database Design section (which predates the AI phase); needed once RAG needed somewhere to actually store embeddings.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| source | TEXT | NOT NULL, indexed | Source filename, e.g. `pg_rules.md`. Ingestion deletes all rows for a `source` before re-inserting its current chunks — see [AI_DESIGN.md](AI_DESIGN.md) §3. |
| chunk_index | INTEGER | NOT NULL | Position within `source`, for stable ordering. |
| content | TEXT | NOT NULL | The chunk's raw text — what gets sent to the AI service as retrieved context. |
| embedding | `vector(768)` | NOT NULL | pgvector. 768 = `nomic-embed-text`'s output size (§8's Phase 6 note); change requires a new migration if the embedding model changes. |

No `created_by`/`updated_by` in practice (still present as columns, per the standard mixins) — ingestion is a script/service action, not a user action, so these are `NULL`.

## 5. Enumerations

| Enum | Values |
|---|---|
| `user_role` | `OWNER`, `MANAGER`, `STAFF`, `TENANT` |
| `room_status` | `AVAILABLE`, `FULL`, `MAINTENANCE`, `INACTIVE` |
| `bed_status` | `VACANT`, `OCCUPIED`, `MAINTENANCE` |
| `tenant_status` | `ACTIVE`, `NOTICE_PERIOD`, `EXITED`, `BLACKLISTED` |
| `payment_status` | `PENDING`, `PARTIAL`, `PAID`, `OVERDUE` |
| `refund_status` | `HELD`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FORFEITED` |
| `complaint_category` | `PLUMBING`, `ELECTRICAL`, `CLEANING`, `WIFI`, `FOOD`, `SECURITY`, `OTHER` |
| `priority` | `LOW`, `MEDIUM`, `HIGH`, `URGENT` |
| `complaint_status` | `OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`, `REOPENED` |
| `expense_category` | `MAINTENANCE`, `UTILITIES`, `SALARY`, `SUPPLIES`, `OTHER` |
| `document_type` | `ID_PROOF`, `ADDRESS_PROOF`, `AGREEMENT`, `PHOTO`, `OTHER` |
| `verification_status` | `PENDING`, `VERIFIED`, `REJECTED` |

These are proposed defaults, not fixed by CLAUDE.md (which named the `status` fields but not their values). Confirm before Phase 2, particularly `complaint_category`, since the AI classifier's output vocabulary (Phase 6) must match this enum exactly.

## 6. Relationships Summary

| Parent | Child | Cardinality | FK column | On delete |
|---|---|---|---|---|
| buildings | rooms | 1–N | rooms.building_id | RESTRICT (must reassign/remove rooms first) |
| rooms | beds | 1–N | beds.room_id | RESTRICT |
| users | tenants | 1–0/1 | tenants.user_id | SET NULL |
| tenants | allocations | 1–N | allocations.tenant_id | RESTRICT |
| rooms | allocations | 1–N | allocations.room_id | RESTRICT |
| beds | allocations | 1–N | allocations.bed_id | RESTRICT |
| tenants | rent_ledger | 1–N | rent_ledger.tenant_id | RESTRICT |
| tenants | security_deposits | 1–N | security_deposits.tenant_id | RESTRICT |
| tenants | complaints | 1–N | complaints.tenant_id | RESTRICT |
| rooms | complaints | 1–0/N | complaints.room_id | SET NULL |
| buildings | expenses | 1–0/N | expenses.building_id | SET NULL |
| tenants | documents | 1–N | documents.tenant_id | RESTRICT |

`RESTRICT` is the default because these are financial/audit records — a hard delete of a parent (e.g. a tenant) must not silently cascade-delete their rent history. Removing a tenant from active use goes through `is_deleted`/`status`, not `DELETE FROM tenants`.

## 7. Indexing Strategy

- All primary keys and unique constraints listed above are indexed automatically.
- Foreign keys get explicit indexes (Postgres does not auto-index FK columns): `rooms.building_id`, `beds.room_id`, `allocations.tenant_id`, `allocations.room_id`, `allocations.bed_id`, `rent_ledger.tenant_id`, `security_deposits.tenant_id`, `complaints.tenant_id`, `complaints.room_id`, `expenses.building_id`, `documents.tenant_id`.
- `tenants.phone` and `tenants.email` — already unique-indexed; also the primary lookup path for login/support.
- `complaints (status, priority)` — composite index to serve the staff "open queue sorted by priority" view.
- `rent_ledger (payment_status, due_date)` — composite index to serve the daily pending-rent job (§9 in ARCHITECTURE.md).
- `allocations (bed_id) WHERE end_date IS NULL` — partial unique index, doubles as the fast "is this bed currently occupied" lookup.

## 8. Migration Strategy (Alembic)

- One migration per logical schema change; autogenerate from models (`uv run alembic revision --autogenerate -m "..."` from `backend/`), then hand-review before committing.
- Migration file names: `<revision>_<snake_case_description>.py` (Alembic default).
- Seed/reference data (e.g., a default `OWNER` user) is applied via a separate seed script, not baked into migrations — migrations define structure, seeding defines starting data, and the two run independently.
- No migration is ever edited after it has been applied to a shared environment; a mistake gets a new corrective migration.

**Phase 2 implementation notes — things autogenerate gets wrong, confirmed by actually running the upgrade/downgrade cycle against Postgres 16:**

- **Partial unique indexes** (e.g. `uq_allocations_active_bed` on `allocations (bed_id) WHERE end_date IS NULL`) *are* picked up correctly by autogenerate — confirmed via `pg_indexes` after running the migration — but verify this by hand for every migration that touches one; it's dialect-specific behavior, not something to assume holds in general.
- **Enum types are not dropped when their table is dropped.** `op.drop_table()` has no knowledge of the `sa.Enum` columns the table used, so a generated `downgrade()` leaves every Postgres `ENUM` type orphaned — confirmed by running `upgrade` → `downgrade` → inspecting `\dT`, which showed all 12 enum types still present with no tables referencing them. A second `upgrade` then fails with `type already exists`. The fix (applied by hand in the initial migration) is an explicit loop of `op.execute(f"DROP TYPE IF EXISTS {enum_name}")` for every enum, placed after the `drop_table` calls in `downgrade()`. Every future migration that adds a new enum type needs the same treatment in its `downgrade()`.

**Phase 6 implementation note — extensions and the app's migration role:** the `544a1f8f92c8` migration (`rag_document_chunks`, §4.12) needs `CREATE EXTENSION vector`. Confirmed by actually running it as the app's normal `pgos` role (not a superuser, matching production): `CREATE EXTENSION IF NOT EXISTS vector` **succeeds** for a non-superuser role as long as the extension already exists (Postgres skips the privilege check once there's nothing to do) but **fails with `InsufficientPrivilege`** if it doesn't yet exist, and `DROP EXTENSION` fails outright either way (`must be owner of extension`). So: enabling `vector` for the first time on a fresh database is a one-time step a superuser (or a managed provider's privileged setup — e.g. Supabase's own "Extensions" UI) runs once, same category of manual provisioning as creating the `pgos` role/database itself; `alembic upgrade head` afterward works fine for everyone since the extension already exists by then. The migration's `downgrade()` deliberately does not drop the extension — both because the app role can't, and because a shared, cluster-level extension shouldn't be unilaterally removed by one table's migration (`CASCADE` could take out other objects depending on it).

## 9. Seed Data Plan

Implemented at `backend/app/database/seed.py` (run via `uv run python -m app.database.seed` from `backend/`) — **not** at a top-level `database/seed.py` as originally planned in Phase 1. That path would have needed `backend/` on `PYTHONPATH` for a script outside the `backend/` package to import `app.models`/`app.database.connection`, which is unnecessary friction for no benefit; keeping the seed script inside the `backend` package it seeds means it shares the same environment, dependencies, and import root as everything else. See the corresponding correction in [ARCHITECTURE.md](ARCHITECTURE.md) §13.

Covers, for local/dev environments only:

- One `buildings` row.
- 5 `rooms` (12 `beds` total) to exercise capacity/occupancy logic without needing all 30/70.
- 6 `tenants`, 5 with `allocations` (one left unallocated to exercise that state too) — including `rent_ledger` history that covers all four `payment_status` values (`PAID`, `PARTIAL`, `PENDING`, `OVERDUE`), plus a `security_deposit` per allocated tenant.
- A few `complaints` (`OPEN`, `IN_PROGRESS`, `RESOLVED`) and `expenses`, so every dashboard view (Phase 4) has something to render, not just rent.
- One `users` row per role (`OWNER`, `MANAGER`, `STAFF`, `TENANT`) for auth testing, with the `TENANT`-role user linked to a seeded tenant via `user_id`.
- Safe to re-run: no-ops if a `Building` already exists rather than duplicating rows.

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, layering rules
- [API.md](API.md) — how these entities are exposed over HTTP
- [ROADMAP.md](ROADMAP.md) — phased delivery plan
