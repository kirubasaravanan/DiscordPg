# PG OS — AI Design

Phase 6. No live Ollama server is reachable from the environment this phase was built in — see [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 27 for exactly what that means for verification. This document describes what was built and why; it is written before the model-quality evaluation it describes has actually been run.

## 1. Architecture

```
FastAPI (services layer)
  |  structured request (text/JSON in)
  v
ai_engine/  (own process, own uv project)
  |  Ollama's documented REST API
  v
Ollama
  |
  v
Qwen3 8B (chat) / nomic-embed-text (embeddings)
```

- **`ai_engine/` has no database credentials in its runtime config** — not "doesn't use them," its `Settings` class has no `database_url` field at all, so this is verifiable by reading `ai_engine/config.py`, not just documented. It knows nothing about PostgreSQL, tenants, or complaints; it receives plain text/JSON and returns plain text/JSON.
- **`ai_engine/` never touches the database, including for RAG.** This is the one place CLAUDE.md's "AI can Analyze, Summarize, Classify — the backend decides actions" rule has a subtlety worth spelling out: RAG *needs* a vector similarity search against stored document embeddings, which sounds like "AI reading the database." The split: the **backend** (which already holds DB credentials and does pgvector's `ORDER BY embedding <=> query_vector` query itself) does retrieval; `ai_engine/` only ever receives the already-retrieved text chunks as part of a request and generates an answer *over provided context* — it never runs a query. Retrieval and generation are different steps, and only generation is delegated.
- **The backend calls `ai_engine/` over HTTP, never Ollama directly.** `backend/app/services/ai_client.py` is the only thing in the backend that knows `ai_engine/`'s base URL; nothing in `backend/` holds an Ollama host/model name.
- **Every AI output is a suggestion the service layer validates before persisting or acting on it** (docs/ARCHITECTURE.md §5 item 5). Concretely: `ai_engine/` does not know PG OS's enum values and doesn't try to — it returns whatever the model produces (best-effort JSON), and `backend/app/services/complaint_service.py` is what actually checks the returned `category`/`priority` against `ComplaintCategory`/`Priority` ([DATABASE.md](DATABASE.md) §5) before ever calling `db.add()`.
- **AI is an enhancement, not a hard dependency for core flows.** If `ai_engine/` is unreachable or returns something unparseable, complaint filing still succeeds — it falls back to exactly the Phase 3b placeholder behavior (tenant's own suggested category, or `OTHER`; priority `MEDIUM`) rather than failing the request. A tenant filing a complaint should never get a 500 because a local LLM server is down.

## 2. Complaint Classification

**Input:** the complaint description text (plus the tenant's own optional category suggestion, still honored as a fallback).

**Output contract** (`ai_engine/`'s `POST /classify`):

```json
{ "category": "PLUMBING", "priority": "HIGH", "suggested_action": "Dispatch a plumber to check the tap washer." }
```

**Prompt** (`ai_engine/prompts.py`): a single chat completion instructing the model to return *only* JSON matching this shape, with the exact allowed values for `category` (`PLUMBING`, `ELECTRICAL`, `CLEANING`, `WIFI`, `FOOD`, `SECURITY`, `OTHER`) and `priority` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`) spelled out in the prompt itself, plus 2-3 worked examples (few-shot) — the enum values are listed in the prompt precisely so the model's output vocabulary has the best chance of matching [DATABASE.md](DATABASE.md) §5 exactly, per that section's own note that this must line up.

**Validation (`complaint_service.py`, not `ai_engine/`):**
1. Call `ai_client.classify_complaint(description)`. Any exception (unreachable, timeout, malformed JSON) → fall back immediately, log a warning, continue.
2. `category`: must exactly match a `ComplaintCategory` member (case-sensitive, matching the enum's own values). If not, fall back to the tenant's suggested category, then `OTHER`.
3. `priority`: must exactly match a `Priority` member. If not, fall back to `MEDIUM`.
4. `suggested_action`: free text, stored as-is if present and a non-empty string, else `NULL`. It's advisory — nothing reads it to take an automated action; staff see it as context on the ticket. New nullable `complaints.suggested_action` column (migration in this phase).

This is a **clamp, not a reject** — an invalid or missing field degrades that one field to its safe default rather than failing the whole classification (or the complaint creation) outright.

## 3. Tenant FAQ (RAG)

**Knowledge base:** `backend/app/content/*.md` — `pg_rules.md` (Phase 5), plus `rent_policy.md` and `maintenance_instructions.md` (this phase). Same static-file, owner-editable pattern as Phase 5's rules content; no admin UI to edit the knowledge base in v1.

**Chunking** (`rag_service.py`): split each file on Markdown `##` headings — one chunk per section, not a fixed-token sliding window. These files are short, hand-written, and already organized into coherent sections (Rent due dates, Late fees, etc.); splitting on headings keeps each chunk topically self-contained, which matters more for retrieval quality than hitting a specific token count at this content size. Revisit with token-based chunking (with overlap) if the knowledge base grows to longer, less-structured documents.

**Embedding model:** `nomic-embed-text` via Ollama, **not** Qwen3 8B, configured separately from the chat model (`ai_engine/config.py`: `OLLAMA_CHAT_MODEL` vs `OLLAMA_EMBED_MODEL`). CLAUDE.md names Qwen3 8B as "the" model without distinguishing chat vs. embedding use, but Ollama supports pulling multiple models, and a dedicated embedding model is standard RAG practice — smaller, faster, and trained specifically to produce embeddings that cluster well for similarity search, vs. asking a general chat model to double as one. See [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 28 for the full rationale.

**Embedding dimension: 768**, matching `nomic-embed-text`'s documented output size — hardcoded into the `rag_document_chunks.embedding` column (`vector(768)`) because pgvector requires a fixed dimension at table-creation time. **This is not verified against a live model in this environment** — if a different embedding model ends up used in production, this needs a new migration to alter the column's dimension before ingestion. Flagged prominently, not buried: see [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 27.

**Retrieval:** cosine distance (`<=>`, pgvector's operator for `vector_cosine_ops`), top 4 chunks.

**Answering:** the retrieved chunks (with their source filename) are sent to `ai_engine/`'s `POST /answer` as context; the model is prompted to answer *only* from the provided context and say it doesn't know rather than guess if the context doesn't cover the question.

**Citations come from retrieval, not the model's self-report.** `rag_service.answer_faq()` already knows exactly which chunks (and therefore which source files) were retrieved before it ever calls `ai_engine/` — the response's `cited_sources` field is built from that list directly, not parsed out of the LLM's generated text. This satisfies ROADMAP.md Phase 6's "RAG answers cite which knowledge-base document they drew from" in a way that's true by construction rather than dependent on the model accurately citing itself.

**Entry points:** `POST /api/v1/tenant/faq` (backend) and `/ask` (`discord_bot/`) — CLAUDE.md's Discord Bot Requirements table doesn't list a FAQ command (only `/rent`, `/complaint`, `/rules`, `/status`), but the AI Requirements section describes tenant FAQ as a real feature, and the dashboard is staff-only, so without a bot command there'd be no way for a tenant to actually use it. Added consistent with how Phase 5 added `/link` beyond the original four.

## 4. Management Summary

**Input:** the same aggregate stats `dashboard_service.get_dashboard_summary()` already computes (occupancy, rent, complaints, expenses) — reused, not recomputed. `ai_engine/`'s `POST /summarize` receives this as plain JSON and has no idea where it came from.

**Output:** a short natural-language paragraph, written for a PG owner/manager skimming a Discord message, not a data dump — the numbers are already in the input JSON if someone wants exact figures; the summary's job is calling out what needs attention (e.g. overdue rent, urgent complaints).

**Consumers:** `GET /api/v1/reports/summary` (OWNER/MANAGER, on-demand) and the daily 21:00 APScheduler job (`scheduled_jobs.generate_management_report`), which posts the same generated text to the management Discord channel via `notification_service.send_channel_message`. One function, two callers — the job doesn't duplicate the on-demand endpoint's logic.

## 5. Scheduled Jobs (APScheduler)

Wired in this phase, per [ROADMAP.md](ROADMAP.md) Phase 6 (deferred from Phase 5 specifically because two of the three need this phase's summary generator):

| Job | Schedule | Calls |
|---|---|---|
| Pending rent check | Daily 08:00 | `scheduled_jobs.check_pending_rent` — no AI involved, DMs each affected linked tenant + a management-channel summary via `notification_service`. |
| Management report | Daily 21:00 | `scheduled_jobs.generate_management_report` — dashboard stats → `ai_client.generate_summary` → management channel. |
| Income report | Monthly (1st, 09:00) | `scheduled_jobs.generate_income_report` — prior month's rent/expenses → management channel. |

Every job function opens and closes its own DB session (`SessionLocal()`, not the request-scoped `get_db` dependency — jobs run outside any request) and catches its own exceptions, logging rather than propagating — one bad run (AI down, Discord down, whatever) must not crash the scheduler or block the next job. **Unverified against a live Discord/Ollama in this environment**, same as the mechanisms they call (docs/ARCHITECTURE.md §12 items 25, 27).

## 6. Evaluation Approach (planned, not yet run)

No live model to evaluate against in this environment. The intended approach, to run once real Ollama access exists:

1. **Classification accuracy**: a hand-labeled set of ~30-50 example complaint descriptions (varied category/priority, including ambiguous ones) run through `POST /classify`; category exact-match accuracy and priority exact-match accuracy tracked separately, since priority is inherently more subjective than category. A confusion matrix per category surfaces which categories the model conflates (e.g. `PLUMBING` vs `MAINTENANCE`-adjacent `OTHER`).
2. **RAG answer quality**: a hand-written set of ~15-20 questions with known-correct answers drawn from the three knowledge-base documents, checked for (a) citing the correct source document, (b) not hallucinating content absent from the retrieved context, (c) correctly saying "I don't know" for out-of-scope questions (e.g. "what's the wifi password" isn't in any of the three documents).
3. **Summary quality**: qualitative review only (a management summary doesn't have a single correct answer) — check it doesn't state numbers absent from the input stats and does surface the stats that actually need attention (overdue rent, urgent complaints) rather than an evenly-weighted list of everything.

## 7. What's Verified vs. Not

See [ARCHITECTURE.md](ARCHITECTURE.md) §12 item 27 for the full breakdown. Summary: every line of code in `ai_engine/` is tested against a real (if hand-rolled, Ollama-API-shaped) test server standing in for Ollama itself (`tests/ai_engine/fake_ollama.py`); the backend's `ai_client.py` is tested against a genuinely running `ai_engine/` subprocess pointed at that same fake server (`tests/backend/test_ai_client.py`) — so the whole chain is real except the last hop; and `complaint_service.py`'s validation/fallback, `rag_service.py`'s chunking/retrieval/citation-assembly, and the scheduled jobs' orchestration are all tested against real Postgres. What isn't verified: that Qwen3 8B or `nomic-embed-text` specifically, running for real, produce good classifications, good embeddings, or good answers — that's the one thing genuinely impossible to check without a reachable Ollama server.

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, §9 background jobs, §12 open questions
- [DATABASE.md](DATABASE.md) — `rag_document_chunks` schema (§4.12), enums (§5)
- [API.md](API.md) — `/tenant/faq`, `/reports/summary` request/response shapes
- [ROADMAP.md](ROADMAP.md) — Phase 6 deliverables and definition of done
