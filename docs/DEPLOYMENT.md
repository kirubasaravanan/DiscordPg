# PG OS — Deployment

Phase 7. Local/dev parity (`docker compose up`, docs/ROADMAP.md Phase 7) is covered by the root [`docker-compose.yml`](../docker-compose.yml) and [`.env.example`](../.env.example) — this document is about the production topology CLAUDE.md names: backend on Railway or a VPS, database on Supabase Postgres, storage on Cloudflare R2, AI on a self-hosted Ollama server.

Not verified end-to-end against real Railway/Supabase/R2/Ollama accounts from this environment — see §6.

## 1. Topology

```
                    ┌─────────────┐
   Discord ────────▶│ discord_bot │───┐
                    └─────────────┘   │
                                      ▼
   Browser ───────▶ ┌───────────┐  ┌─────────┐      ┌──────────────┐
                    │ dashboard │─▶│ backend │─────▶│ Supabase     │
                    └───────────┘  └────┬────┘      │ PostgreSQL   │
                                        │            │ (+ pgvector) │
                            ┌───────────┼───────┐    └──────────────┘
                            ▼                   ▼
                    ┌───────────────┐   ┌────────────────┐
                    │ Cloudflare R2 │   │ ai_engine ─────▶│ Ollama (self-hosted)
                    └───────────────┘   └────────────────┘
```

Four independently deployable processes (`backend/`, `dashboard/`, `discord_bot/`, `ai_engine/`), each its own `uv` project with its own Dockerfile (`docker/*.Dockerfile`) — see docs/ARCHITECTURE.md §3-4 for why they're split this way (no service holds credentials it doesn't need; `ai_engine/` in particular never gets database access).

## 2. Database — Supabase PostgreSQL

1. Create a Supabase project (free tier is enough to start; CLAUDE.md's 30-room/70-bed target is small).
2. **Enable `pgvector`**: Supabase's dashboard → Database → Extensions → search "vector" → Enable. This is the managed-provider equivalent of the privileged `CREATE EXTENSION` step documented in docs/DATABASE.md §8's Phase 6 note — Supabase's own UI runs it with the necessary privileges, so the app's own connection role never needs them.
3. Supabase gives you **two** connection strings — use the right one for the right job:
   - **Direct connection** (port 5432) — use this for running `alembic upgrade head` (migrations use session-level features that don't always play well with connection poolers).
   - **Pooled connection** (via Supavisor, port 6543, `?pgbouncer=true`) — use this for the running backend's `DATABASE_URL`, since it's built to handle many short-lived connections well, which is what a typical web backend does.
4. Adapt the connection string to this project's driver: `postgresql+psycopg://...` (SQLAlchemy needs the `+psycopg` dialect suffix; Supabase's copy-paste string is plain `postgresql://`).
5. Run migrations once from a machine that can reach Supabase (a laptop, or a one-off CI/Railway job) — from `backend/`, with `DATABASE_URL` pointed at the **direct** connection string:
   ```
   uv run alembic upgrade head
   ```
6. Optionally seed reference data the same way CLAUDE.md's dev workflow does (`uv run python -m app.database.seed`) — but review `backend/app/database/seed.py` first; it creates obviously-labeled dev accounts with known passwords, meant for local development, not a real production PG's actual staff/tenant accounts.

## 3. Backend — Railway or a VPS

**Railway** (simplest):
1. New service → deploy from this repo → set the Dockerfile path to `docker/backend.Dockerfile` and the build context to `backend/`.
2. Set every environment variable from the root [`.env.example`](../.env.example) in Railway's dashboard, with real values: the Supabase pooled `DATABASE_URL`, a real `JWT_SECRET_KEY`, the R2 `STORAGE_S3_*` keys (§4), `AI_ENGINE_URL` pointing at wherever `ai_engine/` ends up running (§4), `DISCORD_BOT_TOKEN` (§5).
3. Railway assigns a public HTTPS domain and handles TLS — no reverse proxy needed.
4. The container's own `CMD` already runs `alembic upgrade head` before starting the server (see `docker/backend.Dockerfile`) — no separate migration step needed in Railway itself, though running it once by hand first (§2 step 5) means the very first deploy doesn't do it under deploy-time pressure.

**VPS** (more control, more setup):
1. Install Docker + Docker Compose on the VPS.
2. Use `docker-compose.yml` as a starting point, but drop the `postgres` service (using Supabase instead) and point `DATABASE_URL` at Supabase.
3. Put a reverse proxy in front of `backend` (and `dashboard`, if also hosted here) for TLS — Caddy is the least configuration for a first deployment (automatic Let's Encrypt certificates from just a domain name in a `Caddyfile`); nginx + certbot is the more common alternative if you're already familiar with it.
4. Same environment variables as the Railway path, set via the VPS's own `.env` or secrets mechanism.

Dashboard and Discord bot deploy the same way — each is its own Dockerfile/Railway service (or VPS container), never bundled into the backend's container. Both are long-running processes (the bot holds a persistent Discord gateway connection; Streamlit serves a long-lived session), so neither belongs on a serverless/function platform that expects short-lived invocations.

## 4. Storage — Cloudflare R2

Already built (Phase 3c, docs/ARCHITECTURE.md §4.6, §12 item 15) — production just means flipping the config, not new code:
1. Create an R2 bucket in the Cloudflare dashboard.
2. Create an R2 API token (Account → R2 → Manage API Tokens) scoped to that bucket — gives you an Access Key ID and Secret Access Key.
3. Set on the backend: `STORAGE_BACKEND=s3`, `STORAGE_S3_BUCKET=<bucket name>`, `STORAGE_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com`, `STORAGE_S3_REGION=auto`, `STORAGE_S3_ACCESS_KEY_ID`/`STORAGE_S3_SECRET_ACCESS_KEY` from step 2.
4. This backend's presigned URLs were verified with `moto` (an in-process AWS mock) as far as this environment allows, but never against a live R2 bucket — see docs/ARCHITECTURE.md §12 item 15 for exactly what that does and doesn't cover. Test a real upload/download round-trip against the real bucket before relying on it.

## 5. AI — Self-hosted Ollama

No managed option here — CLAUDE.md calls for a local Ollama server, and that's a real machine (or a container) somewhere you control:
1. A machine with enough RAM to run Qwen3 8B comfortably (16 GB+ recommended for CPU-only inference; a GPU makes a meaningful latency difference but isn't required to function). This can be the same VPS as the backend for a small deployment, or separate if you want to scale it independently.
2. Run Ollama itself — either natively (`https://ollama.com/download`) or via the `ollama/ollama` Docker image (same one `docker-compose.yml` uses for local dev).
3. Pull the two models this project uses: `ollama pull qwen3:8b` (chat/classification/summaries) and `ollama pull nomic-embed-text` (RAG embeddings — docs/AI_DESIGN.md §3 explains why a separate embedding model).
4. **Do not expose Ollama's API to the public internet** — it has no authentication of its own. Put it on a private network/VPC with `ai_engine/` (the only thing that should ever reach it — docs/AI_DESIGN.md §1), or firewall it to that host's IP specifically.
5. Point `ai_engine/`'s `OLLAMA_HOST` at wherever this ends up (e.g. `http://<private-ip>:11434`).
6. **None of this — Ollama, `ai_engine/`'s live calls to it, `qwen3:8b`'s or `nomic-embed-text`'s actual output quality — has been verified against a real model in this project so far.** The sandboxed environment every phase of this project was built in blocks outbound access to both `ollama.com` and `huggingface.co` at the network policy level (docs/ARCHITECTURE.md §12 item 27); every line of code that calls Ollama is real and tested against a hand-rolled stand-in server, but a real model has never actually generated a real classification, embedding, or answer for this project. Run docs/AI_DESIGN.md §6's planned evaluation once this is stood up for real.

## 6. What's Verified vs. Not (this phase)

Consistent with every prior phase's documented infrastructure gaps (S3 credentials in Phase 3c, a Discord bot token in Phase 5, a live Ollama server in Phase 6) — this environment hit a **fourth**, related gap: the same egress policy that blocks `ollama.com`/`huggingface.co` also blocks Docker Hub's blob storage (`production.cloudfront.docker.com`), confirmed the same way (the proxy's own connection log, not assumed) rather than by attempting to route around it. Unlike the earlier gaps, this one is specific to *this* sandboxed environment, not to production use — Docker Hub is about as universally reachable as a registry gets, so a real user or CI runner will not hit this.

What **is** verified for real in this environment:
- The Docker daemon runs here, and `docker compose config` fully resolves `docker-compose.yml` — every service definition, environment variable interpolation (`DATABASE_URL`/`AI_ENGINE_URL`/`API_BASE_URL` correctly resolve to container-network hostnames), healthcheck, volume, and `depends_on` condition, exactly as designed.
- Required-variable enforcement works: clearing `POSTGRES_PASSWORD` from `.env` and re-running `docker compose config` fails with the intended, actionable error rather than silently proceeding with an empty password.
- Each Dockerfile's syntax is valid — `docker compose build` parses every instruction correctly and reaches the first `FROM` before failing on the (policy-blocked) image pull; the failure is confirmed to be exactly and only that pull, not a syntax or build-logic error, by reading the actual error output.

What is **not** verified here, and needs a real `docker compose up` (on a machine with normal Docker Hub access — i.e., basically anywhere else) to confirm: that the built images actually start correctly, that the `postgres`→`backend` and `backend`→`dashboard`/`discord_bot` startup ordering behaves as the `depends_on: condition:` blocks intend, and that `alembic upgrade head` actually runs cleanly against a freshly-initialized `pgvector/pgvector:pg16` container.

## 7. Backup Strategy

**Postgres:**
- On Supabase: automatic daily backups with point-in-time recovery are included on paid plans — this is the primary safety net, and requires no setup beyond picking a plan that includes it.
- Independent of Supabase's own backups (defense against a platform-level or account-level problem, not just a bad migration): a scheduled `pg_dump` — e.g. a daily cron job wherever the backend runs — piped to a file, uploaded to the same R2 bucket documents live in (a separate prefix, e.g. `backups/postgres/`). Retain a rolling window (e.g. 7 daily + 4 weekly) rather than keeping every dump forever.
- If self-hosting Postgres on a VPS instead of Supabase, this second point becomes the *only* backup mechanism, not a supplement — set it up before relying on the deployment for real data.

**Document storage (R2):** object storage is already durable by design; the main additional consideration is **accidental deletion/overwrite**, not disk failure. Cloudflare R2 supports bucket versioning — enabling it means an accidental overwrite or delete is recoverable, at the cost of extra storage for old versions. Whether to eventually expire very old tenant documents (a retention policy) is a business/legal decision for whoever runs the PG, not something to hardcode a number for here.

**Ollama models:** not data — `qwen3:8b`/`nomic-embed-text` are re-downloadable from Ollama's library at any time, so there's nothing to back up beyond the two `ollama pull` commands in §5.

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, §8 configuration & secrets, §12 open questions (including this phase's items)
- [AI_DESIGN.md](AI_DESIGN.md) — what's and isn't verified about the AI layer specifically
- [ROADMAP.md](ROADMAP.md) — Phase 7 deliverables and definition of done
- Root [`docker-compose.yml`](../docker-compose.yml) and [`.env.example`](../.env.example) — local/dev parity, not this document's production topology
