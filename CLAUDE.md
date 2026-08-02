# PG OS (PG Management Operating System)

This file is the master instruction set for Claude Code in this repository. Read it before making any changes.

## Role

You are the lead software architect, senior backend engineer, database architect, DevOps engineer, and AI engineer for this project.

You are responsible for designing and developing a production-grade PG Management Operating System.

- Do not write random code.
- Follow clean architecture.
- Understand requirements before implementation.
- Create documentation before major coding changes.

## Project Vision

Build a complete digital operating system for managing a Paying Guest (PG) accommodation business.

**Initial target:**

- 30 rooms
- 70 beds
- Multiple tenants
- Rent collection
- Complaints
- Maintenance
- Documents
- Expenses
- Reports
- AI assistant

**Future goal:** convert this into a multi-PG SaaS platform.

## Core Technology Stack

### Backend

- **Language:** Python 3.12+
- **Framework:** FastAPI
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Validation:** Pydantic
- **Authentication:** JWT based authentication

### Database

PostgreSQL. Use:

- Proper normalization
- Foreign keys
- Indexing
- Audit fields
- Soft delete where required

### Frontend

- **Admin dashboard:** Streamlit initially
- **Future:** React

### Communication

- **Discord Bot** — library: `discord.py`

### AI Engine

- **Local LLM:** Ollama
- **Recommended model:** Qwen3 8B
- **AI capabilities:** complaint classification, tenant FAQ, report generation, document search, management insights

### Storage

Documents: Cloudflare R2 / AWS S3-compatible storage

## Architecture Rules

```
User
  |
  v
Discord Bot / Dashboard
  |
  v
FastAPI
  |
  v
Services Layer
  |
  v
Database Layer
  |
  v
PostgreSQL
```

The AI layer is separate:

```
FastAPI
  |
  v
AI Service
  |
  v
Ollama
  |
  v
Qwen Model
```

**Never allow AI to directly modify the database.**

AI can:

- Analyze
- Summarize
- Classify

The backend decides actions.

## Repository Structure

Maintain this layout:

```
pg-os/
├── backend/
│   └── app/
│       ├── api/
│       ├── models/
│       ├── schemas/
│       ├── services/
│       ├── database/
│       ├── security/
│       ├── utils/
│       └── main.py
├── discord_bot/
├── dashboard/
├── ai_engine/
├── database/
├── docs/
├── tests/
├── docker/
├── CLAUDE.md
├── README.md
└── docker-compose.yml
```

## Database Design

### Building

- id
- name
- address
- created_at

### Room

- id
- building_id
- room_number
- floor
- capacity
- status

### Bed

- id
- room_id
- bed_number
- status

### Tenant

- id
- name
- phone
- email
- emergency_contact
- joining_date
- exit_date
- status

### Allocation

Tracks: tenant, room, bed, start_date, end_date

### Rent Ledger

- tenant_id
- month
- rent_amount
- paid_amount
- balance
- due_date
- payment_status

### Security Deposit

- tenant_id
- amount
- received_date
- refund_status

### Complaint

- tenant_id
- room_id
- category
- description
- priority
- status
- created_at
- resolved_at

### Expense

- category
- amount
- date
- vendor
- notes

### Documents

- tenant_id
- document_type
- storage_url
- verification_status

## Development Rules

Before coding:

1. Explain approach
2. Create/update documentation
3. Show file changes
4. Implement
5. Add tests

Never:

- Change unrelated files
- Delete existing functionality
- Hardcode credentials
- Commit secrets

## Security Requirements

Implement:

- Environment variables / `.env` support
- JWT authentication
- Password hashing
- Role-based access control

**Roles:** OWNER, MANAGER, STAFF, TENANT

## API Requirements

### Tenant APIs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tenant/profile` | Tenant profile |
| GET | `/tenant/rent` | Tenant rent status |
| POST | `/tenant/complaint` | File a complaint |

### Admin APIs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/dashboard` | Dashboard summary |
| POST | `/tenant` | Create tenant |
| POST | `/room` | Create room |
| POST | `/allocation` | Allocate bed |
| GET | `/reports` | Generate reports |

## Discord Bot Requirements

Create a PG Management Discord Server.

**Roles:** Owner, Manager, Maintenance, Tenant

**Commands:**

| Command | Description |
|---|---|
| `/rent` | Shows pending rent |
| `/complaint` | Creates a complaint ticket |
| `/rules` | Shows PG rules |
| `/status` | Shows complaint status |

## Automation

Use APScheduler.

**Jobs:**

- Daily 8 AM — check pending rent
- Daily 9 PM — generate management report
- Monthly — generate income report

## AI Requirements

Use the Ollama API.

### Complaint Classification

Input:

```
"My bathroom tap is leaking"
```

Output:

```json
{
  "category": "",
  "priority": "",
  "suggested_action": ""
}
```

### Management Summary

- Input: database statistics
- Output: human-readable report

### FAQ (RAG)

Knowledge base:

- PG rules
- Rent policy
- Maintenance instructions

Use `pgvector` for retrieval.

## Testing Requirements

Every module requires:

- Unit tests
- API tests
- Database tests

Use `pytest`.

## Deployment

**Development:** Docker Compose

**Production:**

- Backend: Railway / VPS
- Database: Supabase PostgreSQL
- Storage: Cloudflare R2
- AI: local Ollama server

## Documentation

Maintain under `docs/`:

- `ARCHITECTURE.md`
- `DATABASE.md`
- `API.md`
- `AI_DESIGN.md`
- `DEPLOYMENT.md`
- `CHANGELOG.md`

## Coding Style

- PEP8
- Type hints
- Docstrings
- Clean naming
- Small functions
- Reusable services

## Current Task Behavior

Before implementing any feature, ask:

1. What problem does this solve?
2. Which database entities are affected?
3. Which APIs are required?
4. How will testing be done?
5. Does documentation need updating?

You are building a production system, not a demo.

## Development Roadmap (Phase Prompts)

Work proceeds in phases. Run one phase per Claude Code session, in order, and do not skip ahead.

1. **Architecture** — Read `CLAUDE.md`. Create `ARCHITECTURE.md`, `DATABASE.md`, an API specification, and a development roadmap. Do not write application code yet.
2. **Database** — Implement the PostgreSQL layer: SQLAlchemy models, Alembic migrations, database connection, seed data. Add tests. Update documentation.
3. **Backend** — Implement the FastAPI backend: authentication, tenant management, room management, bed allocation, rent ledger. Follow the existing architecture. Add API documentation and pytest tests.
4. **Dashboard** — Create the Streamlit admin dashboard, connected via the FastAPI APIs: occupancy dashboard, rent dashboard, complaint dashboard, expense dashboard.
5. **Discord** — Implement the Discord bot, integrated with the backend APIs: tenant commands, complaint workflow, rent status, notifications. Follow security rules.
6. **AI** — Implement the AI service, integrating Ollama + Qwen3: complaint classifier, FAQ assistant, daily summary generator, RAG document search using `pgvector`.
7. **Production** — Prepare production deployment: Docker files, `docker-compose`, environment configuration, deployment documentation, backup strategy.
