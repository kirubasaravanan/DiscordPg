# PG OS — Development Roadmap

Status: Phase 3a and 3b complete — every backend resource except Documents (Phase 3c). Expands CLAUDE.md's "Development Roadmap (Phase Prompts)" into concrete deliverables, dependencies, and definitions of done. No calendar estimates are given here — this project has no tracked velocity yet to base one on; size phases relatively instead (S/M/L) if planning is needed.

## Guiding Principles

From CLAUDE.md:

- Documentation before major coding changes.
- Clean architecture: API → Services → Database, no layer skipping.
- AI never writes to the database — it only classifies/summarizes; the backend decides.
- No hardcoded credentials, no committed secrets.
- Every module gets unit, API, and database tests.

## Phase 0 — Instruction Pack (done)

**Deliverable:** `CLAUDE.md` at repo root.
**Status:** Complete.

## Phase 1 — Architecture (done)

**Deliverables:**
- `docs/ARCHITECTURE.md`
- `docs/DATABASE.md`
- `docs/API.md`
- `docs/ROADMAP.md` (this file)

**Definition of done:** every entity in CLAUDE.md's Database Design section is fully typed with constraints; every API surface CLAUDE.md names has a path and role; layering rules are explicit enough that Phase 2/3 don't need to re-derive them; open assumptions are flagged for confirmation (see [ARCHITECTURE.md](ARCHITECTURE.md) §12) rather than silently baked in.

**Explicitly out of scope for this phase:** any application code, migrations, or dependency files (`requirements.txt`, `pyproject.toml`, `docker-compose.yml`). CLAUDE.md's Prompt 1 is documentation-only.

**Depends on:** Phase 0.

## Phase 2 — Database (done)

**Deliverables:**
- SQLAlchemy models for every entity in [DATABASE.md](DATABASE.md) §4, including the added `users` table — `backend/app/models/`.
- Alembic setup + initial migration matching the schema, constraints, and indexes documented there — `backend/alembic/`.
- Database connection/session management — `backend/app/database/connection.py`, `backend/app/config.py`.
- Seed data script per [DATABASE.md](DATABASE.md) §9 — `backend/app/database/seed.py` (path corrected from the original top-level `database/seed.py` plan; see [ARCHITECTURE.md](ARCHITECTURE.md) §12).
- 21 unit/database tests (`pytest`, top-level `tests/backend/`) covering relationships, every unique/check constraint, the partial-unique active-allocation index, native-enum enforcement at the DB level, and seed script correctness + idempotency. All passing against a real PostgreSQL 16 instance.
- `docs/DATABASE.md` and `docs/ARCHITECTURE.md` updated for what implementation corrected: no `pgcrypto` extension needed (core PG13+ `gen_random_uuid()`), the seed script path, and an Alembic gotcha (enum types orphaned on downgrade unless dropped explicitly) documented for future migrations to follow.

**Definition of done:** `alembic upgrade head` produces a schema matching `docs/DATABASE.md` exactly (confirmed via `alembic check`); `alembic downgrade base` cleanly reverses it with no orphaned objects (confirmed via `\dT`) and a subsequent `upgrade head` succeeds; seed script runs cleanly against an empty database and no-ops on a second run; all tests pass locally against PostgreSQL 16. Docker Compose parity (running the same against the Phase 7 `docker-compose.yml` Postgres service) is deferred to Phase 7 — no docker-compose.yml exists yet.

**Depends on:** Phase 1 (schema must be settled, especially the flagged assumptions — UUID PKs, `users` table, enum values).

## Phase 3 — Backend

Scope is split into three, as this entry's original wording allowed for. **Phase 3a** covers everything needed for the core tenant lifecycle — sign in, house someone, bill them — end to end with real RBAC. **Phase 3b** covers everything else that's pure database CRUD/aggregation with no external dependency. **Phase 3c** is Documents alone, split out separately because it's the one piece that genuinely needs infrastructure (object storage credentials) this environment doesn't have.

### Phase 3a — Auth, core resources, allocation, rent (done)

**Deliverables:**
- FastAPI app skeleton (`backend/app/main.py`) wired to the database layer from Phase 2, with a consistent error envelope (matching [API.md](API.md) §6) via exception handlers rather than per-route try/except — including a generic `IntegrityError` → `409` safety net.
- Auth: JWT issuing/verification (access + refresh), Argon2id password hashing, RBAC as a FastAPI dependency per [API.md](API.md) §3 — `POST /api/v1/auth/{login,refresh,logout}`. Logout required adding `users.token_version` beyond the Phase 2 schema (see [DATABASE.md](DATABASE.md) §4.1, [ARCHITECTURE.md](ARCHITECTURE.md) §7) — a second Alembic migration, round-trip verified the same way as the initial one.
- Buildings, Rooms, Beds, Tenants (admin), Allocations, Rent Ledger — full CRUD per [API.md](API.md) §5.1–5.6, including the derived-status rule for `Room.status`/`Bed.status` and the active-children delete guards ([ARCHITECTURE.md](ARCHITECTURE.md) §12 items 8–9).
- Tenant self-service read endpoints (`GET /api/v1/tenant/profile`, `GET /api/v1/tenant/rent`) from [API.md](API.md) §4 — added in this phase (ahead of the rest of §4) specifically so RBAC tests exercise all four roles, not just the three admin-side ones.
- Seed data (Phase 2) updated to use real Argon2id password hashes instead of the placeholder string, so the seeded accounts are actually usable for login (dev-only credentials, printed by the seed script).
- 93 tests total (`pytest` + FastAPI `TestClient`, run against real PostgreSQL like the Phase 2 suite) covering auth, RBAC enforcement per role, and each endpoint's happy path plus at least one failure path (401/403/404/409/422 as applicable).
- OpenAPI docs auto-generated by FastAPI kept as the live reference; `docs/API.md` updated for what changed during implementation (allocation request shape, derived-status rule, IntegrityError safety net).

**Definition of done:** every endpoint implemented in this phase matches its [API.md](API.md) entry (path, roles, request/response shape) or `docs/API.md` is updated to match reality — confirmed; RBAC is enforced as a dependency, not ad hoc per-handler checks — confirmed, `require_roles(...)` in `app/api/deps.py`; allocating/ending an allocation keeps `beds.status`/`rooms.status` consistent with actual occupancy — confirmed by test and by hand against the live seeded server. Also fixed along the way: `SessionLocal` had `autoflush=False` since Phase 2, which silently produced stale reads for exactly this kind of "modify then query in the same transaction" logic — changed to the default (`True`).

**Explicitly deferred:** Security Deposits, Complaints, Expenses, full Users CRUD, Dashboard/Reports, and the rest of tenant self-service to Phase 3b; Documents (both admin and tenant-facing) to Phase 3c.

### Phase 3b — Remaining resources except Documents (done)

Scope narrowed again on entry, same reasoning as the 3a/3b split: Documents specifically needs real Cloudflare R2/S3 credentials to build a pre-signed-upload flow that's actually been proven to work, not just written — this environment has none. Splitting it out rather than stubbing it keeps everything else in 3b honestly tested. See [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 12.

**Deliverables:**
- Security Deposits — full CRUD per [API.md](API.md) §5.7 (OWNER/MANAGER only, no STAFF read — narrower than every other resource so far).
- Expenses — CRUD per [API.md](API.md) §5.9, **minus** the `DELETE` endpoint that table originally listed (see [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 10 — it contradicted `expenses`' own append-only rule in [DATABASE.md](DATABASE.md) §2).
- Users — full CRUD per [API.md](API.md) §5.10, OWNER-only, reusing the Phase 3a password-hashing module. Added a guard (§12 item 13) so the last active `OWNER` account can't be demoted or deactivated via the API.
- Complaints — admin list/get/patch per [API.md](API.md) §5.8, plus the tenant-facing `POST`/`GET /api/v1/tenant/complaints` from §4. No AI classifier yet (Phase 6) — interim placeholder design, see [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 11.
- `PATCH /api/v1/tenant/profile` — the one remaining piece of tenant self-service with no external dependency.
- Dashboard (`GET /api/v1/dashboard`) and Reports (`GET /api/v1/reports/{income,occupancy,complaints}`) per [API.md](API.md) §5.12 — the first endpoints that read across multiple resource types at once; their response shapes were designed during this phase (§12 item 14) and are now documented in [API.md](API.md) §5.12.
- 138 tests total, same coverage bar as 3a: happy path + at least one failure path per endpoint, RBAC per role, run against real PostgreSQL. Dashboard/report aggregation math verified against a hand-built exact scenario, then against the real Phase 2 seed data by hand (every number checked out).

**Bug found by smoke-testing against the real seeded server, not just the test suite:** the seed script's `owner@pgos.local`/`manager@pgos.local`/`staff@pgos.local` addresses (Phase 2) fail `EmailStr` validation — `.local` is a reserved TLD — so creating a similarly-shaped new user through the real `POST /api/v1/users` correctly got rejected. The automated tests never caught this because they generate throwaway emails on `@example.com`. The seed data only "worked" because it's inserted directly through the ORM, bypassing Pydantic entirely. Fixed by switching the seed script's staff emails to `@example.com`, matching what the tenant seed data already used.

**Depends on:** Phase 3a (reuses its auth/RBAC/error-envelope scaffolding directly).

### Phase 3c — Documents (not started)

**Deliverables:** `documents` CRUD per [API.md](API.md) §5.11 and the tenant-facing document endpoints from §4, backed by real pre-signed upload/download URLs against Cloudflare R2 (or S3-compatible storage) per [ARCHITECTURE.md](ARCHITECTURE.md) §4.6 — not a stub.

**Depends on:** Phase 3a. Blocked on real object-storage credentials being available to develop and test against (may end up sequenced alongside or after Phase 7's storage configuration work, whichever comes first).

**Depends on:** Phase 2.

## Phase 4 — Dashboard

**Deliverables:**
- Streamlit app (`dashboard/`) authenticating against the Phase 3 API (no direct DB access — per [ARCHITECTURE.md](ARCHITECTURE.md) §4.2).
- Occupancy, rent, complaint, and expense views, each backed by the corresponding `/api/v1/...` endpoints.

**Definition of done:** all four views render live data from a running backend; no view queries Postgres directly.

**Depends on:** Phase 3 (needs the dashboard/reports and resource-listing endpoints).

## Phase 5 — Discord Bot

**Deliverables:**
- `discord_bot/` using `discord.py`.
- `/rent`, `/complaint`, `/rules`, `/status` commands, each calling the Phase 3 API.
- Discord-to-PG-OS account linking via `users.discord_id` ([DATABASE.md](DATABASE.md) §4.1).
- Notification delivery path used by the scheduled jobs ([ARCHITECTURE.md](ARCHITECTURE.md) §9).

**Definition of done:** all four commands work end-to-end against the real API for a linked test account; unlinked Discord users get a clear "link your account" response rather than an error.

**Depends on:** Phase 3 (tenant + complaint + rent endpoints).

## Phase 6 — AI

**Deliverables:**
- `ai_engine/` service calling Ollama (Qwen3 8B), reachable only from the backend services layer.
- Complaint classifier (text → `{category, priority, suggested_action}`, validated against the enums in [DATABASE.md](DATABASE.md) §5 before the service layer persists anything).
- Tenant FAQ via RAG over PG rules / rent policy / maintenance instructions, using `pgvector`.
- Daily/management summary generator.
- `docs/AI_DESIGN.md` (new — prompt design, RAG chunking/embedding strategy, evaluation approach for classification accuracy).
- APScheduler jobs from [ARCHITECTURE.md](ARCHITECTURE.md) §9 wired to call the summary generator.

**Definition of done:** AI service has no database credentials in its runtime config (verifiable, not just documented); classifier output is always validated/clamped by the service layer; RAG answers cite which knowledge-base document they drew from.

**Depends on:** Phase 3 (complaint creation flow to hook the classifier into) and Phase 2 (pgvector-backed table for RAG documents, added as a migration in this phase).

## Phase 7 — Production

**Deliverables:**
- `docker/` Dockerfiles for backend, dashboard, bot, AI service.
- Root `docker-compose.yml` wiring all services + Postgres for local/dev parity.
- Environment configuration reference (`.env.example` with every key from [ARCHITECTURE.md](ARCHITECTURE.md) §8, no real values).
- `docs/DEPLOYMENT.md` (new — backend on Railway/VPS, database on Supabase Postgres, storage on Cloudflare R2, Ollama self-hosted).
- Backup strategy for Postgres (and document storage retention).

**Definition of done:** `docker compose up` runs the full stack locally from a clean checkout with only `.env` filled in; deployment doc is specific enough to follow without re-deriving decisions.

**Depends on:** Phases 2–6 (packages what they built).

## Out of Scope for v1

Per CLAUDE.md's "Future goal" — not built now, but the design should not actively block them later:

- Multi-tenant SaaS (multiple unrelated PG businesses on shared infrastructure) — see [ARCHITECTURE.md](ARCHITECTURE.md) §10.
- React frontend (Streamlit is the v1 dashboard).
- Online rent payment processing (v1 tracks rent, it doesn't move money — see [ARCHITECTURE.md](ARCHITECTURE.md) §12).

## Open Decisions

Carried forward from [ARCHITECTURE.md](ARCHITECTURE.md) §12. Items 2 and 3 are now locked in by the Phase 2 schema/migration — changing them after this point means a new migration against real data, not a documentation edit. Items 1, 4, and 5 are still genuinely open and should be confirmed before Phase 3 code makes them harder to change:

1. Rent collection stays a tracking ledger, not a payment gateway integration — **still open**, confirm before Phase 3.
2. `users` table addition and its relationship to `tenants` — **implemented** (Phase 2: `backend/app/models/user.py`, `tenant.py`).
3. UUID primary keys over auto-increment integers — **implemented** (Phase 2, all 11 tables).
4. Pluralized/versioned API paths that expand on CLAUDE.md's literal endpoint list — **still open**, confirm before Phase 3 locks them into code and Discord/dashboard clients.
5. Pre-signed URL upload pattern for documents — **still open**, confirm Cloudflare R2 is the actual target (affects whether this pattern needs adjustment). Not touched by Phase 2 — `documents.storage_url` is just a `TEXT` column regardless of how it gets populated.

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DATABASE.md](DATABASE.md)
- [API.md](API.md)
