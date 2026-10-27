# Resume Analyzer — Backend

## Overview

The **Resume Analyzer** backend is a REST API built with **FastAPI** that helps
HR users manage the hiring pipeline for job vacancies:

* HR users create accountsand authenticate with **JWT** tokens.
* They create **jobs** (vacancies) describing the company, position, required
  skillsand experience.
* They record **applications/candidates** (leads) who applied for those jobs,
  track their **hiring status** (strong hire / hire / weak hire / do not hire)and
  **interview status** (in process / completed / not completed).
* A **dashboard** gives them analytics (total jobs/candidates/leads, breakdown
  by company/position/experience)and recent activity (recent jobs and leads).
* A keyword-based **resume analysis** utility scores a resume against a job's
  required skillsand suggests a hiring recommendation. It is currently a local
  heuristic (see “Resume analysis” below)so the MVP needs no external AI service.

**Who uses it:**

| Role | Can do |
|---|---|
| **HR user** | Manage their own account, jobs, applications/candidates, interviews and dashboard. Never sees another HR user's data or any admin feature. |
| **Candidate** (Candidate Portal) | Their own account, the applications they submitted while signed in, each application's status and timeline, candidate-safe resume feedback, and their interviews. Never sees HR data, other candidates or any HR/admin feature. |
| **Admin (superuser)** | **Every HR permission, on every HR user's data**, **plus** the admin console: manage user accounts (activate/deactivate, promote/demote, delete), organisation-wide dashboards and analytics, job moderation, and monitoring of AI usage, audit logs, errors, health and runtime settings. |

Admin access needs two things, both checked server-side on every request: an
account with `is_superuser=True` **and** a session opened in the *admin
workspace* (see “Sessions and workspaces” under Authorization). The frontend
only mirrors these rules for a better UX.



## Features

### Authentication
* Register a new HR account (POST /api/auth/register)
* Login with email + password (POST /api/auth/login)
* Logout endpoint for clients to discard their token (POST /api/auth/logout)
* Forgot / reset password with a short-lived JWT reset token]
* Password hashing with **bcrypt** (passwords are never stored in plain text)
* JWT access tokens]** with configurable expiry

### Own-account settings (Settings page)
* Read the signed-in user's own profile (GET /api/auth/me)
* Update own full name and/or email (PATCH /api/auth/me)
* Upload/replace/remove own profile image (POST/DELETE /api/auth/me/profile-image)
* Change own password with re-authentication (PATCH /api/auth/me/password);
  every session issued before the change is revoked
* Profile images are validated by content (JPG/PNG/WEBP, size limit), stored on
  disk under a generated name and served from the `/uploads` static mount
* Ownership is guaranteed by design: the user is always resolved from the JWT,
  so these endpoints can never touch another user's account

### User management (admin only)
* List, read, update, delete registered users (`/api/users`)
* Edit a user's full name, account status (`is_active`) and role (`is_superuser`)
* Deactivate / reactivate accounts (deactivated accounts cannot log in and
  their existing tokens stop working immediately)
* Promote users to admin / demote other admins to HR
* Guardrails: an admin cannot demote/deactivate/delete their own account, and
  the last active admin can never be removed (400)
* Deleting a user cascade-deletes their jobs, applications and interviews
* Every change is written to the audit log

### Admin console (admin only, `/api/admin/*`)
Platform-wide views that support user management and operations. The console
itself only lists and inspects; to *act* on a job, application, candidate or
interview, its **Manage** button opens the regular HR screen, where an admin
session has the same permissions as the owning HR user (see “Authorization”).

* Dashboard and analytics across all HR users
* Users directory with search/filter/sort/pagination and a per-user detail view
  (usage stats, recent jobs/applications, recent audit activity)
* Jobs, applications, candidates and interviews across all HR users, linking to
  the HR screens to manage them, plus `DELETE /api/admin/jobs/{id}` for moderation
* AI analysis monitoring, audit logs, system errors and system health
* Runtime settings (e.g. whether public registration is open), audited

### Candidate Portal (`/candidate`, `/api/candidate/*`)
The second side of the platform: job seekers follow their applications.

* **Separate identity.** Candidates live in `candidate_accounts`, not `users`,
  and their tokens carry candidate-only purposes (`candidate_access`,
  `candidate_refresh`, `candidate_password_reset`). The HR guard accepts only
  `access` tokens and the candidate guard only `candidate_access`, so neither
  token works on the other side. Hashing and JWT signing are shared.
* **Email/password and Google.** Candidates can register/sign in with a local
  password or with the same Google OAuth code exchange HR uses. Only a
  *verified* Google email is accepted; an existing candidate account is linked
  by email, while an HR account with the same address stays a separate
  identity (candidates can never take over an HR/admin account). A Google-only
  candidate has `hashed_password = NULL`: password login is rejected (the
  profile reports `has_password: false` and the UI hides the change-password
  form), and the reset flow can set a first local password without unlinking
  Google.
* **Applying.** The existing public form (`/apply/:token`) is reused. Sent with
  a candidate token (optional), the new application is linked to the account
  (`applications.candidate_account_id`); guests can still apply. Applications
  are **never linked by matching email** (emails are not verified).
* **What a candidate sees**, all scoped to the signed-in account (another
  candidate's records answer 404):
  * a dashboard (total / active / upcoming interviews / completed, next
    interview, recent applications) computed by the backend;
  * each application with a friendly **candidate status** derived from the HR
    pipeline (`submitted`, `ai_review`, `hr_review`, `interview_invited`,
    `interview_scheduled`, `decision_pending`, `accepted`, `rejected`,
    `withdrawn`) — separate from the AI result and the interview status;
  * a five-step **timeline** built from stored facts (`application_status_history`,
    the analysis time, interviews); unknown dates are left empty, never guessed;
  * **candidate-safe AI feedback**: match percentage and skill/requirement lists
    only. The HR recommendation, recruiter-oriented AI text, internal
    `ai_score`, provider errors and interviewer notes are never exposed;
  * interviews (date, time, duration, online/in-person, http(s) meeting link for
    upcoming ones);
  * profile (name, email, phone, photo, password, password reset by email).
* HR gets one new application status, `hired` (the candidate sees "Application
  accepted").

| Endpoint | Purpose |
|---|---|
| `POST /api/candidate/auth/register` · `login` · `google` · `refresh` · `logout` | Candidate session (refresh tokens are single-use). `google` uses the same Google OAuth code exchange as HR sign-in and links an existing candidate account by verified email. |
| `POST /api/candidate/auth/forgot-password` · `reset-password` | Password reset by emailed link (`/candidate/reset-password`) |
| `GET/PATCH /api/candidate/profile`, `PATCH …/profile/password`, `POST/DELETE …/profile/image` | Own profile |
| `GET /api/candidate/dashboard` | Counts, next interview, recent applications |
| `GET /api/candidate/applications`, `GET …/applications/{id}` | Own applications; detail includes job, answers, safe AI feedback, timeline, interviews |
| `GET /api/candidate/applications/{id}/resume` | Download own submitted CV |
| `GET /api/candidate/interviews`, `GET …/interviews/{id}` | Own interviews |
* Future phases (not built): candidate ↔ HR messaging, an AI assistant,
  interview confirmation/rescheduling, notifications, job discovery. See the
  `TODO(CANDIDATE-PORTAL)` / `TODO(FUTURE)` notes in
  `app/models/candidate_account.py` and `app/services/candidate_portal.py`.

### Job management
* Create, list, read, update, delete jobs
* Jobs store: company name, position, description, required skills,
  required experience,and a running lead count
* Jobs are scoped to their owner: HR users only ever see/manage their own jobs;
  an admin session sees and manages every HR user's jobs

### Application / candidate management
* Create, list, read, update, delete applications/candidates
* Each application belongs to a job; creating an application increments the job's lead count
* Update hiring statusand interview status (validated enums; invalid values → 422)

### Dashboard / analytics
* Overview with exact counts: total jobs, total candidates, total leads,
  anda breakdown grouped by company, position, or required experience
* Recent jobsand recent leads (paginated via a limit query param)

### Resume analysis
* Keyword-based scoring of a resume against required skills (case-insensitive,
  substring matching), producing a percentage score, matched/missing skills,
  a summary, anda hiring recommendation (strong hire / hire / weak hire / do not hire)

### AI-powered job analysis
* The backend can analyze vacancy descriptions using an AI provider to extract
  structured job information (company name, position, description, required skills,
  required experience).
* The AI provider is configurable via environment variables.
* Supported providers: **OpenRouter**, **Groq**, **Google Gemini**.
* Provider switching is configuration-driven — no source-code changes required.
* Rate limits (HTTP 429) and service unavailability (HTTP 503) are handled with
  exponential backoff retries.
* The application never logs API keys, authorization headers, or sensitive prompts.

### Validation & security
* Pydantic request validation (validation errors → 422)
* JWT-protected endpoints(401 without/invalid/expired token)
* Ownership checks: other users' resources behave as “not found” (404) for
  regular HR users, returning no information about whether they exist; an
  admin session bypasses ownership (never user management, which stays admin-only)
* SQLAlchemy ORM queries(parameterized — not vulnerable to SQL injection)

---

## Tech Stack

* **Python 3.12+** (developed against 3.14)
* **FastAPI** — web framework
* **Uvicorn** — ASGI server
* **PostgreSQL** — database
* **SQLAlchemy 2.x** — ORM
* **Pydantic v2** + **pydantic-settings** — validation and configuration
* **email-validator** — email format validation
* **python-jose** — JWT encode/decode
* **bcrypt** — password hashing
* **Alembic** — migrations, applied automatically at startup (see “Migrations”
  below)
* **pytest** + **FastAPI TestClient** — testing
## Project Structure

```text
backend/
├── app/
│   ├── main.py              # FastAPI app factory: routers, health, startup bootstrap
│   ├── core/
│   │   ├── config.py        # Settings read from environment / .env
│   │   ├── database.py      # Engine, session factory, declarative Base, get_db
│   │   └── security.py      # Password hashing, JWT create/validate
│   ├── models/              # SQLAlchemy models: User, Job, Application
│   ├── schemas/             # Pydantic request/response models (auth, user, job,
│   │                        #   application, dashboard, analysis)
│   ├── crud/                # Plain database operations (no business logic)
│   │   ├── user.py
│   │   ├── job.py
│   │   └── application.py
│   ├── services/            # Business logic
│   │   ├── auth.py          # register, authenticate, tokens, password reset
│   │   ├── profile.py       # own-account settings (name/email, profile image)
│   │   ├── job.py           # lead counting, analytics aggregation
│   │   ├── application_analysis.py  # analyze one application, convert to candidate
│   │   ├── ai/              # AI integration
│   │   │   ├── provider.py      # which provider/key/model a user's AI calls use
│   │   │   ├── job_analyzer.py  # AI job-vacancy analysis
│   │   │   ├── application_analyzer.py  # AI application analysis
│   │   │   ├── batch.py         # auto-analyze batches
│   │   │   ├── monitoring.py    # records AI runs for the admin console
│   │   │   └── heuristic.py     # keyword resume scoring heuristics
│   │   └── admin/           # Admin console
│   │       ├── users.py         # user management rules (self/last-admin guards)
│   │       ├── directory.py     # platform-wide read views
│   │       ├── stats.py         # dashboard + analytics
│   │       ├── health.py        # system health checks
│   │       └── errors.py        # persists 5xx errors
│   ├── routers/             # API endpoints
│   │   ├── auth.py          # /api/auth/*
│   │   ├── users.py         # /api/users/* (superuser only)
│   │   ├── jobs.py          # /api/jobs/*
│   │   ├── applications.py  # /api/applications/*
│   │   └── dashboard.py     # /api/dashboard/*
│   └── dependencies/
│       └── auth.py          # get_current_user / get_current_superuser / get_access_scope
├── alembic/                 # Alembic migration scaffolding
├── alembic.ini
├── tests/                   # pytest suite (see “Running tests”)
│   ├── conftest.py          # fixtures + test-database setup
│   ├── payloads.py          # shared deterministic test payloads
│   ├── test_security.py     # hashing + JWT unit tests
│   ├── test_auth.py         # register/login/logout/reset + auth service
│   ├── test_password_reset.py # forgot/reset/skip/refresh + token purposes
│   ├── test_users.py        # superuser user management + user CRUD
│   ├── test_jobs.py         # job endpoints + job CRUD
│   ├── test_applications.py # application endpoints + application CRUD
│   ├── test_dashboard.py    # analytics + recent activity endpoints
│   └── test_services.py     # resume analysis + job service units
├── pytest.ini
├── .env.example             # Template for environment variables
├── .env                     # Local configuration(never commit real secrets)
├── requirements.txt
└── README.md
```

### Where code belongs
* **`app/models/`** — only SQLAlchemy table definitionsand relationships.
* **`app/schemas/`** — only Pydantic models (request bodies, response shapes).
* **`app/crud/`** — only database queries. No business rules, no raises (except
  `create_user` raising `ValueError` on duplicate email,and void `HTTPException`). Keep
  each function a single query or so.
* **`app/services/`** — business rules that span more than a simple CRUD call:
  password reset, token issuing, analytics aggregation, resume scoring.
* **`app/routers/`** — HTTP layer: declare routes, depend on `get_db`and
  `get_current_user`, translate service `ValueError`s into HTTP responses.,

  Must not contain SQL or business rules.,
* **`app/dependencies/`** — reusable FastAPI dependencies (auth resolution.,
* **`app/core/`** — infrastructure: config, database engine, security utilities.,

---

## Request flow

```text
Router (app/routers/)             # HTTP entry point, validation, status codes
   ↓
Service (app/services/)           # business logic, only when logic > simple CRUD
   ↓
CRUD (app/crud/)                 # plain database operations
   ↓
Database (PostgreSQL)
```

Simple operations go Router → CRUD → Database directly (e.g. job update), which
keeps the code shortand junior-friendly. More complex operations (register,
reset password, analytics, resume analysis) route through a service layer first.,
---

## Environment setup

### 1. Prerequisites
* Python 3.12+
* PostgreSQL running locally (default URL expects user `postgres` /
  password `postgres` on `localhost:5432`)

### 2. Clone and configure
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set DATABASE_URL, SECRET_KEY,and optionally SUPERUSER_*
```

### 3. Start the server
The first startup automatically: creates the target database if missing, creates
all tables,and seeds a superuser if `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD`
are set. No manual migration step is required for the MVP.

```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs (Swagger UI) or
http://localhost:8000/redoc (ReDoc).

### 4. Database schema and migrations
Nothing to run by hand: at startup the API brings the schema to the revision
the code expects (`app/core/migrations.py`), under a PostgreSQL advisory lock
so several API processes cannot race:

| Database state | What startup does |
|---|---|
| Empty (fresh install) | Creates every table from the models and stamps the Alembic head |
| Behind the code's revision | Applies the pending migrations (`alembic upgrade head`) |
| At the code's revision | Nothing to migrate |
| Has tables but no Alembic revision | Refuses to start and explains how to stamp it |

Set `DB_AUTO_MIGRATE=false` to apply migrations yourself (e.g. as a separate
deploy step); the API then refuses to start on an out-of-date schema and names
the command to run. Changing the schema means adding a migration:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

> **Why not just `create_all()`?** It only creates *missing* tables and never
> renames or alters existing ones. Before startup ran migrations, starting new
> code on an unmigrated database created an empty `applications` table next to
> `workers` and split the data. Revision `2cb0c8660dbf` also repairs that state
> (stray rows are copied over and the stray table is kept as
> `applications_orphaned`).

---

## Environment variables

All settings are read from real environment variables or the `.env` file
(`app/core/config.py`). None are secrets; never commit real secrets.,

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Resume Analyzer API` | Display name used in the FastAPI app. |
| `DEBUG` | `false` | Enables FastAPI debug mode. Accepts `true/false`, `dev/development`, `prod/production`. |
| `API_PREFIX` | `/api` | Prefix prepended to all router URLs. |
| `SECRET_KEY` | `change-me-in-production` | HMAC signing key for JWT. **Must be overridden** with a strong random value in production. |
| `ALGORITHM` | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access-token lifetimein minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh-token lifetime (days); only accepted by `POST /api/auth/refresh`. |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | `30` | Lifetime of the token carried by an emailed password-reset link. |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | Origin used to build the reset link sent to the user. |
| `RESEND_API_KEY` | *(empty)* | Resend API key (https://resend.com/api-keys). When empty, verification/reset links are written to the server log in DEBUG builds instead of being emailed. |
| `EMAIL_FROM` | `onboarding@resend.dev` | From-address. Must be on a Resend-verified domain for real recipients; the sandbox `onboarding@resend.dev` sender only delivers to your own Resend account address. |
| `EMAIL_FROM_NAME` | *(empty)* | Optional display name, rendered as `Name <EMAIL_FROM>`. |
| `EMAIL_REPLY_TO` | *(empty)* | Optional Reply-To address; omitted when empty. |
| `EMAIL_REQUEST_TIMEOUT` | `10` | Seconds to wait for the Resend API (registration sends synchronously). |
| `EMAIL_MAX_RETRIES` | `2` | Max retries for transient Resend failures (HTTP 429/5xx, network). Permanent 4xx are never retried. |
| `EMAIL_RETRY_BASE_DELAY` | `1` | Base seconds for the bounded exponential backoff between email retries. |
| `EMAIL_MAX_RETRY_WAIT` | `10` | Longest single backoff wait between email retries, in seconds. |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/resume_analyzer` | SQLAlchemy database URL. |
| `DB_AUTO_MIGRATE` | `true` | Apply pending Alembic migrations at startup. `false`: refuse to start on an out-of-date schema and ask for `alembic upgrade head`. |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174` | Comma-separated browser origins allowed to call the API: the CRM (`crm/`) and the landing site (`landing/`, for its Contact form). |
| `SUPERUSER_EMAIL` | *(empty)* | If set, a superuser is seeded at startup when no superuser exists yet. Needed to use the admin `/api/users` endpoints. |
| `SUPERUSER_PASSWORD` | *(empty)* | Password for the seeded superuser. |
| `SUPERUSER_FULL_NAME` | `Administrator` | Display name for the seeded superuser. |

### AI Provider Configuration

#### Per-user AI credentials (who pays for which call)

Each HR user can save their own **provider, API key and model ID** in
**Settings → AI provider** (`GET/PUT/DELETE /api/auth/me/ai-provider`, plus
`POST .../test` to check them). Every AI feature resolves credentials for the
user who owns the data through one gateway, `resolve_for_user` in
`app/services/ai/provider.py`:

| User's state | `REQUIRE_USER_AI_CONFIG=true` (default) | `REQUIRE_USER_AI_CONFIG=false` |
|---|---|---|
| Saved own provider | Their provider + key + model, never mixed with `.env` | Same |
| Nothing saved | 400 "AI is not set up for your account…" (nothing attempted, nothing marked failed) | The platform provider below |
| Saved key can't be decrypted | Clear error, no fallback | Same |

* **Features covered:** vacancy analysis (`POST /api/jobs/analyze`), manual
  application analysis, background analysis of public submissions, and Auto
  Analyze batches. The analyzers take the resolved config as a *required*
  argument, so a new feature cannot skip the gateway.
* **Changes apply to the next call:** configurations are read from the
  database on every AI call and nothing is cached across users; there is no
  restart. Batches resolve the owner's configuration per application at run
  time and only ever carry ids; removing the configuration mid-batch stops the
  batch and leaves the remaining applications untouched.
* **Secrets:** keys are encrypted at rest with Fernet using
  `AI_CREDENTIAL_ENCRYPTION_KEY` (server environment only; saving is refused
  without it), decrypted only for the call, never returned (the UI shows the
  last four characters), never logged, and never kept in browser storage.

#### Platform (environment) settings

All settings are read from real environment variables or the `.env` file
(`app/core/config.py`). The `AI_*` variables take precedence over provider-specific
legacy variables. The provider, key and model here are used for HR work only
when `REQUIRE_USER_AI_CONFIG=false`; the retry and timeout settings apply to
every AI call.

| Variable | Default | Purpose |
| --- | --- | --- |
| `REQUIRE_USER_AI_CONFIG` | `true` | `true`: every HR must save their own provider, key and model before AI features run for them. `false`: HRs without one use the platform provider below. |
| `AI_CREDENTIAL_ENCRYPTION_KEY` | *(empty)* | Fernet key that encrypts users' saved API keys. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |
| `AI_PROVIDER` | `openrouter` | AI provider: `openrouter`, `groq`, or `gemini`. |
| `AI_MODEL` | *(empty)* | Model identifier. Falls back to `OPENROUTER_MODEL` for OpenRouter. |
| `AI_API_KEY` | *(empty)* | API key for the configured provider. Falls back to `OPENROUTER_API_KEY`. |
| `AI_BASE_URL` | *(provider default)* | Base URL for the provider's API. |
| `AI_MAX_RETRIES` | `3` | Maximum retry attempts for transient failures (429, 503, network). |
| `AI_RETRY_BASE_DELAY` | `2` | Base delay in seconds for exponential backoff. |
| `AI_MAX_RETRY_WAIT` | `30` | Longest single wait (seconds) honoured when the provider says how long to back off; a longer request ends the retries at once. |
| `AI_RETRY_BUDGET` | `45` | Total seconds one AI call may spend waiting between retries. |
| `AI_REQUEST_TIMEOUT` | `60` | Request timeout in seconds. |
| `AI_HTTP_REFERER` | *(empty)* | HTTP-Referer header for provider attribution. Falls back to `OPENROUTER_REFERER`. |
| `AI_APP_TITLE` | `Resume Analyzer` | X-Title header for provider attribution. Falls back to `OPENROUTER_APP_TITLE`. |

#### Provider-specific notes

**OpenRouter** (`AI_PROVIDER=openrouter`):
- Base URL: `https://openrouter.ai/api/v1`
- Model format: `provider/model:free` (e.g., `google/gemma-2-9b-it:free`)
- Attribution headers (`HTTP-Referer`, `X-Title`) are sent automatically.
- Legacy variables `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` are used as fallback.

**Groq** (`AI_PROVIDER=groq`):
- Base URL: `https://api.groq.com/openai/v1`
- Uses OpenAI-compatible API format.
- Attribution headers are sent automatically.

**Google Gemini** (`AI_PROVIDER=gemini`):
- Base URL: `https://generativelanguage.googleapis.com/v1beta/models`
- Uses Gemini's native REST API (not OpenAI-compatible).
- Model format: `gemini-2.0-flash` etc.
- No attribution headers are sent.

#### Provider switching

To switch providers, change only the environment variables:

```env
# Switch from OpenRouter to Groq
AI_PROVIDER=groq
AI_MODEL=llama-3.3-70b-versatile
AI_API_KEY=your-groq-api-key
```

No source-code changes are required.

#### Rate limiting

Changing the model name does **not** eliminate rate limits. Rate limits are
enforced by the provider's infrastructure and account quota. On a 429 the
application:

* waits as long as the provider asks (`Retry-After`, or OpenRouter's
  `X-RateLimit-Reset` for account limits) up to `AI_MAX_RETRY_WAIT`, otherwise
  backs off exponentially (`AI_RETRY_BASE_DELAY`, up to `AI_MAX_RETRIES`);
* stops early, without sending requests that are bound to fail, when the
  provider asks for a longer wait or the call's `AI_RETRY_BUDGET` is spent;
* reports a specific message: for OpenRouter `:free` models it names the
  model, explains that free models share one rate limit with everyone using
  them, and suggests choosing a paid model in **Settings → AI provider**. The
  job-analysis endpoint also returns the wait as a `Retry-After` header.

Attribution headers (`HTTP-Referer`, `X-Title`) are for application
identification only and do not guarantee rate-limit avoidance.

---

## Database

## Database

### PostgreSQL setup
The app expects a running PostgreSQL server. The default connection URL is
`postgresql://postgres:postgres@localhost:5432/resume_analyzer` — create
user `postgres` with password `postgres` locally, or set `DATABASE_URL` to match
your environment.,

### Database connection
`app/core/database.py` creates:

* `engine` — the SQLAlchemy engine (URL from settings, `pool_pre_ping=True`).
* `Base` — the declarative base every model inherits.
* `SessionLocal` — a session factory; `get_db()` yields one session per request
  and closes it in a `finally` block.,

### Models and relationships
| Model | Table | Key fields | Relationships |
| --- | --- | --- | --- |
| `User` | `users` | id, email (unique, indexed), hashed_password, full_name, is_active, is_superuser | has many `jobs` (cascade delete via DB) |
| `Job` | `jobs` | id, owner_id (FK users.id, indexed), company_name, position, description, required_skills, required_experience, leads_count, created_at | belongs to `User`; has many `applications` (cascade delete via DB) |
| `Application` | `applications` | id,, job_id,, name,, email,, resume_path,, hiring_status,, interview_status,, created_at | belongs to `Job` |

Enum columns use SQLAlchemy `Enum` with Python `enum.Enum` values:

* `HiringStatus`: `strong_hire`, `hire`, `weak_hire`, `do_not_hire` (default `hire`)
* `InterviewStatus`: `in_process`, `completed`, `not_completed` (default `not_completed`)

### Migrations
At startup the app calls `_ensure_database()` (creates the database if
missing), then `prepare_schema()` (creates a fresh schema or applies pending
Alembic migrations; see “Database schema and migrations” above) and optionally
seeds the first superuser.

### Test database strategy
Tests never touch the development/production database. `tests/conftest.py` sets
`DATABASE_URL` to `.../resume_analyzer_test` **before** any app module is imported,
creates the test database once per session,, creates tables,, and truncates all tables
before every test. That keeps tests isolated, deterministic,and repeatable.,

---

## Authentication

### How passwords are stored
`app/core/security.py::hash_password()` hashes with `bcrypt` (72-byte truncation
guard)and `verify_password()` compares. Raw passwords are never stored or returned.,

### JWT
`_create_token()` builds a signed JWT (HS256) with:
* `sub` — the user id (as string)`,
* `exp` — expiry,
* `iat` — issue time (second granularity), which is what makes "revoke every
  session that predates this password change" possible,
* `typ` — the token's purpose,
* `jti` — a unique id, so a single token can be consumed (refresh rotation).

Purposes are not interchangeable:

| `typ` | Minted by | Accepted by |
| --- | --- | --- |
| `access` | login, register, Google, reset/skip, refresh | the `get_current_user` bearer guard |
| `refresh` | the same sign-in paths | `POST /api/auth/refresh` only |
| `password_reset` | `POST /api/auth/forgot-password` | `/verify-reset-token`, `/reset-password`, `/skip-reset` |

A reset token therefore cannot be replayed as a session even though it arrives
in a URL that may be logged, shared or opened on another machine. Tokens with no
`typ` claim (issued before this scheme existed) are treated as access tokens, so
sessions that predate the upgrade keep working.

`decode_access_token()` validates signature and expiry and raises `JWTError` otherwise;
`decode_token_for_purpose()` / `decode_reset_token()` additionally enforce the table
above. Revocation state lives in `app/core/token_registry.py` (in-process; swap for
Redis or a `users.token_version` column when running more than one worker).

### Authentication flow

```text
Client → POST /api/auth/register
   → validate payload (Pydantic)
   → check duplicate email (bcrypt hash is never exposed)
   → hash password with bcrypt
   → save user in users table
   → issue JWT
   ↓
Client → POST /api/auth/login (email + password)
   → find user by email
   → verify bcrypt password hash
   → (deactivated accounts are rejected)
   → issue JWT
   ↓
Client sends: Authorization: Bearer <token>
   → get_current_user dependency decodes the token
   → loads the user (rejects stale/deleted/inactive users)
   → request proceeds on owned resources only
```

### HR email verification & Two-Phase Registration

To prevent spam, unverified accounts, and orphaned records, HR registration follows a **secure two-phase architecture**:
1. When an HR user registers, an unverified record is stored in `pending_registrations`. **No user row is inserted into `users` and zero JWT tokens are issued.**
2. A cryptographically secure random token (sha256 hash) and a 6-digit OTP code (bcrypt/hash) are generated and stored with a 10-minute expiry.
3. Resend delivers an email containing both a secure activation link (`/verify-email?token=<token>`) and a 6-digit verification code.
4. The pending record is persisted **before** the email is attempted, so a rejected delivery never discards the recoverable state. If delivery fails (e.g. Resend HTTP 403 sandbox restriction or an unverified sender), `POST /api/auth/register` still returns **HTTP 201 Created** with `verification_email_sent: false` and a safe, actionable `email_delivery_error`. The user can then request a fresh code with `POST /api/auth/resend-verification-code`. (A hard 502 is deliberately *not* returned: the registration itself was accepted, and the account can still be completed.)
5. Once the user clicks the link and confirms ("It's me" POST action) or enters the 6-digit code, the pending registration is atomically consumed: the permanent user is created in `users` with `is_email_verified = True`, and session JWT tokens are minted.

```text
POST /api/auth/register
   → pending record created in pending_registrations (NO user in `users`, zero JWT tokens)
   → cryptographically random token (sha256) and 6-digit code generated
   → email dispatched via Resend (delivery failure is reported via verification_email_sent=false, never a 502)
   → response: { message: "...", email: "...", requires_verification: true,
                 verification_email_sent: true, email_delivery_error: null }
        ↓
Option A: Click verification link in email (GET /verify-email?token=...)
   → Frontend displays "Confirm Your Email" with "It's me — Complete Registration" button
   → User clicks confirmation button (POST /api/auth/verify-email { token })
        ↓
Option B: Enter 6-digit OTP code (POST /api/auth/verify-email { email, code })
        ↓
Atomically in DB transaction:
   → Pending registration consumed and verified
   → Permanent account created in `users` (is_email_verified = true)
   → Legitimate JWT session tokens issued
        ↓
HR panel accessible
```

* **Model.** `pending_registrations` (separate table with email, full name, hashed password, token hash, code hash, attempt counter, last sent timestamp, expiration timestamp).
* **Security.** Link scanner protection: link verification uses an explicit confirmation button submitting a POST request to ensure security bots following GET links do not consume the pending registration.
* **Concurrency.** The pending row is claimed with a conditional `UPDATE … WHERE consumed_at IS NULL`, so two simultaneous confirmations (double-click, retried request) can never both create a user; the loser gets a clean `400`. The user insert and the claim share one transaction, and the unique email constraint is the final backstop.
* **Background dispatch.** Registration email is sent synchronously (bounded by `EMAIL_REQUEST_TIMEOUT`) so the client can be told whether delivery was accepted; `POST /api/auth/resend-verification-code` regenerates the credentials synchronously but dispatches the message through `BackgroundTasks`, so its response never waits on the provider.
* **Resend Configuration & Sandbox Restrictions:**
  - `RESEND_API_KEY`: API key from [Resend](https://resend.com/api-keys).
  - `EMAIL_FROM` / `EMAIL_FROM_NAME`: the from-address (and optional display name). By default `onboarding@resend.dev`, but that sandbox sender **only permits delivery to the specific email address used to register the Resend account** — any other recipient yields HTTP 403.
  - For staging/production, verify a custom domain in the Resend dashboard (e.g. `edubaselearning.uz`) and set `EMAIL_FROM=noreply@edubaselearning.uz` (optionally `EMAIL_FROM_NAME=EduBase`, `EMAIL_REPLY_TO=support@edubaselearning.uz`). The API logs a startup warning while `@resend.dev` is still configured.
  - Delivery retries only transient failures: HTTP 429/5xx and network errors are retried with bounded exponential backoff (`EMAIL_MAX_RETRIES`, `EMAIL_RETRY_BASE_DELAY`, `EMAIL_MAX_RETRY_WAIT`); permanent 4xx rejections (the sandbox 403, an invalid key) fail immediately. Provider error bodies are sanitized (addresses redacted) before being logged.
* **Rate Limiting & Cooldowns:** 60-second cooldown between resend requests per address; max 5 codes per hour.
* **Candidate Portal:** Maintains separate identity and independent candidate verification table.

### Forgot / reset password

```text
Client → POST /api/auth/forgot-password { email }
   → look the account up (password account or Google-only one)
   → mint a 30-minute `password_reset` JWT
   → email the reset link via Resend (app/services/email.py)
     → no RESEND_API_KEY, or Resend down/error: log the link instead
   → reply is always "If that email exists, a reset link has been sent"
   ↓
Browser → GET /reset-password?token=<jwt>
   → POST /api/auth/verify-reset-token  → whose account is this? does it have a password?
   ↓
   ├── "Skip"            → POST /api/auth/skip-reset
   │      → validate the token, leave the hash alone, return a fresh pair
   │
   └── "Change password" → POST /api/auth/reset-password { token, new_password }
          → bcrypt the new password
          → revoke every session issued before the change
          → return a fresh access/refresh pair
   ↓
Either branch: the client stores both tokens and navigates to /dashboard signed in.
```

A Google-only account is never dead-ended: **Skip** signs it straight in, and
**Change password** simply gives it its first local password while keeping the
Google link intact. Because `hashed_password` is nullable, no schema change was
needed.

Email delivery happens in `app/services/email.py::send_reset_password_email()`
through the Resend REST API (`httpx`, subject **"Reset Your Password"**, from
`EMAIL_FROM`, with a `<FRONTEND_BASE_URL>/reset-password?token=...>` action
link). When `RESEND_API_KEY` is empty — or Resend rejects/errors — the link is
written to the server log instead, and the endpoint still answers identically
for every address, so local development keeps working and account existence is
never revealed.

### Authorization
* `get_current_user` — requires a valid Bearer JWT for an active account
  (401 without/invalid/expired token or a deactivated account).
* `get_current_superuser` — requires `is_superuser=True` **and** an admin
  session (403 `"Admin privileges required"` for HR accounts, 403 `"Switch to
  the admin workspace to use this."` for an admin account in an HR session).
  Guards `/api/users/*` and every `/api/admin/*` route.
* `get_access_scope` — used by the HR endpoints (jobs, applications/candidates,
  AI analysis and Auto Analyze, interviews, dashboard). Returns an
  `AccessScope`:
  * HR user (or an admin account in an HR session): its own id, so reading or
    modifying another user's resource returns 404, never revealing that it exists;
  * admin account in an admin session: `owner_id=None`, meaning every HR
    user's data. The admin then runs the **same** HR actions through the same
    endpoints and business logic — there is no separate read-only admin path.

  Routers call `scope.can_access(resource.owner_id)` for single resources and
  pass `scope.owner_id` to CRUD listings (`None` adds no owner filter, via
  `crud.query_utils.owner_filter`).

**Permission model — admin = HR permissions + admin-only permissions:**

| Capability | HR | Admin session |
|---|:-:|:-:|
| Own profile, settings, AI provider | ✅ | ✅ |
| Jobs: create / read / update / delete, application form | own | all |
| Applications & candidates: read, update statuses, convert, delete, CV | own | all |
| AI analysis, Auto Analyze | own | all |
| Interviews: schedule, edit, change status, delete | own | all |
| Dashboard & analytics | own data | organisation-wide |
| Admin console, user management (view, activate/deactivate, promote/demote, delete) | ❌ | ✅ |

Notes:
* An interview always belongs to the HR user who owns the candidate's job,
  also when an admin scheduled it, so that HR user keeps seeing it; the audit
  log records the admin as the actor.
* AI analysis always uses the **job owner's** AI configuration, also when an
  admin triggers it. An admin Auto Analyze batch spans every HR user and skips
  applications whose owner has no AI configured.

### Sessions and workspaces
Every session is signed with a workspace (`role` claim): `user` (HR) or
`admin`. HR-only accounts always get `user`. An admin account chooses at
sign-in (the login returns `requires_role_selection` and a short-lived
selection token for `POST /api/auth/select-role`) and can switch later by
calling `POST /api/auth/select-role` with its current session; the old access
token is revoked. The server grants `admin` only to accounts that really have
it, so a client cannot upgrade itself by editing a token, storage or the URL.

---

## API Documentation

All endpoints (except `/health` and the unauthenticated auth routes) require

```text
Authorization: Bearer <access_token>
```

Responses use FastAPI's standard error shape:`{"detail": "..."}`.

---

### POST /api/auth/register
**Purpose:** Initiate a two-phase HR registration and email a verification link + code. No account is created and no token is issued until the email is verified.,

**Authentication:** Not required.,

**Request body:**

```json
{
    "email": "hr@example.com",
    "full_name": "Jane Doe",
    "password": "StrongPassword123"
}
```

**Success (201 Created):**

```json
{
    "message": "Please check your email to complete registration.",
    "email": "hr@example.com",
    "requires_verification": true,
    "verification_email_sent": true,
    "email_delivery_error": null
}
```

When the email provider rejects the message, the pending registration is still
persisted and the same `201` is returned with `verification_email_sent: false`
and a safe `email_delivery_error` (never a false success and never a `502`). The
user completes registration through `POST /api/auth/resend-verification-code`.

**Possible errors:**
* `400` — email already registered (`"A user with this email already exists"`)
* `403` — an administrator has switched registration off
* `422` — invalid email, empty `full_name`, missing fields.,

---

### POST /api/auth/login
**Purpose:** Exchange email + password for a JWT.,

**Authentication:** Not required.,

**Request body:**
```json
{
    "email": "hr@example.com",
    "password": "StrongPassword123"
}
```

**Success (200):** same `Token` shape as register.,

**Possible errors:**
* `401` — incorrect email or password (incl. deactivated accounts)
* `422` — invalid email format.,

---

### POST /api/auth/logout
**Purpose:** Client-side logout signal (JWTs are stateless;the client discards its token).

**Authentication:** Required.,

**Success (204 No Content).**

**Errors:** `401` — missing/invalid token.,

---

### POST /api/auth/verify-email
**Purpose:** Confirm the HR email with the emailed 6-digit code and sign in.

**Authentication:** Not required (the code is the credential).

**Request body:**
```json
{ "email": "hr@example.com", "code": "483921" }
```

**Success (200):** a `Token`/role-selection result — the account is signed in as
part of the verification (`is_email_verified: true`).

**Errors:**
* `400` — `"Invalid or expired verification code"` for a wrong, expired, used or
  unknown-account code (one generic message)
* `400` — `"Email is already verified"`
* `422` — missing/malformed email or a code that is not exactly 6 digits

### POST /api/auth/resend-verification-code
**Purpose:** Email a fresh 6-digit verification code.

**Authentication:** Not required.

**Request body:** `{ "email": "hr@example.com" }`

**Success (200):** `{ "message": "If that email needs verification, a verification code has been sent." }` — generic for unknown/unverified addresses.

**Errors:** `400` — `"Email is already verified"`; `429` — too soon or too many requests.

### POST /api/auth/forgot-password
**Purpose:** Request a password-reset token for an email.,

**Authentication:** Not required.,

**Request body:**
```json
{ "email": "hr@example.com" }
```

**Success (200):**
```json
{ "message": "If that email exists, a reset link has been sent" }
```

The same message is returned whether or not the email exists, and whether the
account is a password account or a Google-only one (no account enumeration).
When `RESEND_API_KEY` is set, the link — `<FRONTEND_BASE_URL>/reset-password?token=<jwt>` —
is emailed from `EMAIL_FROM` via Resend (`app/services/email.py`, subject
"Reset Your Password"); without a key it is written to the server logs so
local development stays usable.

The reset token is a short-lived (`PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`,
default 30) JWT tagged `typ: "password_reset"`. It is only accepted by
`/verify-reset-token`, `/reset-password` and `/skip-reset`; the API's bearer
guard rejects it, so a leaked link can never be replayed as a session.

---

### POST /api/auth/verify-reset-token
**Purpose:** Report which account a reset link belongs to, so the reset page can
word itself correctly ("add a password" for Google-only accounts).

**Authentication:** Not required (the reset token is the credential).

**Request body:**
```json
{ "token": "<reset jwt>" }
```

**Success (200):**
```json
{
    "email": "hr@example.com",
    "full_name": "HR User",
    "has_password": true,
    "is_google_account": false
}
```

**Errors:** `400` — invalid or expired token; `422` — missing token.

---

### POST /api/auth/reset-password
**Purpose:** Set a new password using the reset token.

**Authentication:** Not required.

**Request body:**
```json
{
    "token": "<30-minute reset jwt>",
    "new_password": "BrandNewPassword123"
}
```

**Success (200):** a fresh `Token` pair (`access_token`, `token_type`,
`refresh_token`) — the user is signed in as part of the reset, so the client
stores the tokens and goes straight to the dashboard instead of returning to
`/login`. Every session issued *before* the change is invalidated. For a
Google-only account this sets its first local password without unlinking Google
sign-in.

**Errors:**
* `400` — invalid or expired token.,

---

### POST /api/auth/skip-reset
**Purpose:** The "Skip" option on the reset page — keep the current password and
turn the reset link into a live session.

**Authentication:** Not required (the reset token is the credential).

**Request body:**
```json
{ "token": "<reset jwt>" }
```

**Success (200):** a fresh `Token` pair. The stored hash is untouched and other
devices stay signed in (nothing about the credentials changed), which is what
distinguishes this from `/reset-password`.

**Errors:**
* `400` — invalid, expired or deactivated-account token
* `422` — missing token

---

### POST /api/auth/refresh
**Purpose:** Exchange a refresh token for a new access/refresh pair.

**Authentication:** Not required (the refresh token is the credential).

**Request body:**
```json
{ "refresh_token": "<jwt>" }
```

**Success (200):** a fresh `Token` pair. Refresh tokens rotate: the presented
token is consumed and replaying it returns `401`.

**Errors:**
* `401` — invalid, expired, already-consumed or wrong-purpose token (an access
  token is rejected here), or a deactivated account
* `422` — missing `refresh_token`

The frontend API client calls this transparently: a protected request that
returns `401` triggers one shared (single-flight) refresh and is replayed once
before the user is signed out.

---

### GET /api/auth/me
**Purpose:** Return the authenticated user's own profile (the Settings page).

**Authentication:** Required.

**Success (200):**
```json
{
    "id": 1,
    "email": "hr@example.com",
    "full_name": "Jane Doe",
    "profile_image": "/uploads/profile/9f2c….png",
    "has_password": true
}
```

`profile_image` is `null` until the user uploads one (Google account pictures
are not copied here). `has_password` is `false` for Google-only accounts, which
is how the Settings page knows to hide the password form.

The response never includes `hashed_password` or any token/security data.

**Errors:** `401` — missing/invalid/expired token.

---

### PATCH /api/auth/me
**Purpose:** Update the authenticated user's own full name and/or email.

**Authentication:** Required.

**Request body (any subset):**
```json
{
    "full_name": "John Smith",
    "email": "john.smith@example.com"
}
```

Both fields are optional, so `{"full_name": "John Smith"}` alone is valid. The
name is trimmed and must not be empty; the email is normalized with the same
`EmailStr` rule the auth endpoints use and must not belong to another account.
There is **no** `user_id` field — the account comes from the JWT, so a caller
can never target another user.

**Success (200):** updated profile (same shape as `GET /api/auth/me`).

**Possible errors:**
* `400` — the new email is already registered by another account
* `422` — empty/whitespace-only `full_name`, invalid email format

The JWT stays valid after an email change (it carries the user id, not the
email), so the client does not need to re-authenticate. The password is never
touched by this endpoint.

---

### PATCH /api/auth/me/password
**Purpose:** Change the authenticated user's own password (requires the
current one).

**Authentication:** Required.

**Request body:**
```json
{
    "current_password": "OldPassword123",
    "new_password": "NewPassword123"
}
```

On success the new password is bcrypt-hashed, **every session issued before
the change is revoked** (same mechanism as `/reset-password`) and a fresh
access/refresh pair is returned, so the client stays signed in. The current
password is verified against the stored hash; a Google-only account (no local
password) cannot use this endpoint.

**Success (200):** fresh `Token` pair (same shape as `/login`).

**Possible errors:**
* `400` — wrong current password, or a Google-only account without a password
* `422` — missing/empty `current_password`, empty or over-72-character
  `new_password` (bcrypt only hashes the first 72 bytes)

---

### POST /api/auth/me/profile-image
**Purpose:** Upload or replace the authenticated user's own profile image.

**Authentication:** Required.

**Request:** `multipart/form-data` with a `file` field (JPG/JPEG, PNG or WEBP,
at most `PROFILE_IMAGE_MAX_SIZE_MB` MB — default 5). The file is validated by
its **content** (magic bytes), not by filename or declared type alone; a
mismatch or an unsupported type is rejected, so a renamed executable cannot
pass. The stored filename is a fresh UUID under `UPLOAD_DIR/profile/`, which
also rules out path traversal, and a previously uploaded image is deleted when
replaced.

**Success (200):** updated profile with the new server-relative
`profile_image` URL, served from the `/uploads` static mount.

**Possible errors:**
* `400` — unsupported type, content/type mismatch, or oversized upload
* `401`
* `422` — missing `file` field

---

### DELETE /api/auth/me/profile-image
**Purpose:** Remove the authenticated user's own profile image.

**Authentication:** Required.

The stored file is deleted and `profile_image` is set back to `null`. Calling
it when no image is set still succeeds (nothing to remove).

**Success (200):** updated profile with `profile_image: null`.

**Errors:** `401`.

---

### GET /api/users
**Purpose:** List registered users (paginated). Superuser only.,

**Authentication:** Superuser.,

**Query parameters:** `skip` (default 0, ≥0), `limit` (default 100, 1–200).

**Success (200):**
```json
[
    {
        "id": 1,
        "email": "hr@example.com",
        "full_name": "Jane Doe",
        "is_active": true,
        "is_superuser": false
    }
]
```

**Errors:** `401` anonymous,, `403` regular HR user,, `422` bad pagination.,

---

### GET /api/users/{user_id}
**Purpose:** Read a single user. Superuser only.,

**Success (200):** `UserResponse` shape (above).,

**Errors:** `404` user not found.,

---

### PUT /api/users/{user_id}
**Purpose:** Update `full_name`, `is_active`, `is_superuser`.,

**Authentication:** Superuser.,

**Request body (any subset):**
```json
{
    "full_name": "New Name",
    "is_active": false,
    "is_superuser": false
}
```

**Success (200):** updated `UserResponse`.,

**Errors:**
* `400` — cannot demote/deactivate your own account
* `404` — user not found.,

---

### DELETE /api/users/{user_id}
**Purpose:** Delete a user (their jobs and applications cascade-delete). Superuser only.,

**Success (204 No Content).,

**Errors:**
* `400` — cannot delete your own account
* `404` — user not found.,
---

### GET /api/jobs
**Purpose:** List the current user's jobs (newest first).,

**Authentication:** Required.,

**Success (200):**
```json
[
    {
        "id": 1,
        "company_name": "Acme Corp",
        "position": "Backend Developer",
        "description": "Build and maintain REST APIs.",
        "required_skills": "Python, FastAPI, PostgreSQL",
        "required_experience": "2+ years",
        "leads_count": 0,
        "created_at": "2026-09-04T12:00:00Z"
    }
]
```

**Errors:** `401`.,

---

### POST /api/jobs
**Purpose:** Create a job owned by the current user.,

**Authentication:** Required.,

**Request body:**
```json
{
    "company_name": "Acme Corp",
    "position": "Backend Developer",
    "description": "Build and maintain REST APIs.",
    "required_skills": "Python, FastAPI, PostgreSQL",
    "required_experience": "2+ years"
}
```

`description`, `required_skills`, `required_experience` are optional (default empty;).

**Success (201 Created):** `JobResponse` (above), with `leads_count: 0`.,

**Errors:**
* `401`
* `422` — missing/empty `company_name` or `position`.,

---

### GET /api/jobs/{job_id}
**Purpose:** Read one of the current user's jobs.,

**Authentication:** Required.,

**Success (200):** `JobResponse`.,

**Errors:**
* `401`
* `404` — not found (or belongs to another user.,

---

### PUT /api/jobs/{job_id}
**Purpose:** Update job fields.,

**Authentication:** Required.,

**Request body (any subset):**
```json
{
    "position": "Senior Backend Developer"
}
```

**Success (200):** updated `JobResponse`.,

**Errors:**
* `401`
* `404` — not found (or not owned)
* `422` — empty `company_name` / `position`.,

---

### DELETE /api/jobs/{job_id}
**Purpose:** Delete a job (its applications cascade-delete)..,

**Authentication:** Required.,

**Success (204 No Content)..,

**Errors:** `401`, `404`.,

---

### GET /api/applications?job_id={job_id}
**Purpose:** List applications/candidates for one of the user's jobs.,

**Authentication:** Required.,

**Query parameters:** `job_id` (required.,

**Success (200):**
```json
[
    {
        "id": 1,
        "job_id": 1,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "resume_path": "/resumes/jane-doe.pdf",
        "hiring_status": "hire",
        "interview_status": "not_completed",
        "created_at": "2026-09-04T12:00:00Z"
    }
]
```

**Errors:** `401`, `404` (job not found/not owned), `422` (missing job_id.,

---

### POST /api/applications?job_id={job_id}
**Purpose:** Record a new application by hand and increment the job's `leads_count`.,

**Authentication:** Required.,

**Query parameters:** `job_id` (required.,

**Request body:**
```json
{
    "name": "Jane Doe",
    "email": "jane@example.com",
    "resume_path": "/resumes/jane-doe.pdf"
}
```

`resume_path` is optional.,

**Success (201 Created):** `ApplicationItemResponse` with default `hiring_status:"hire"`, `interview_status:"not_completed"`.,

**Errors:** `401`, `404`, `422` (missing/empty name.,

---

### GET /api/applications/{application_id}
**Purpose:** Read a single application.,

**Authentication:** Required.,

**Success (200):** `ApplicationItemResponse`.,

**Errors:** `401`, `404`.,

---

### PATCH /api/applications/{application_id}
**Purpose:** Update application fields (typically hiring/interview status).,

**Authentication:** Required.,

**Request body (any subset):**
```json
{
    "hiring_status": "strong_hire",
    "interview_status": "completed"
}
```

**Success (200):** updated `ApplicationItemResponse`.,

**Errors:**
* `401`
* `404`
* `422` — invalid enum value (`hiring_status` must be one of `strong_hire|hire|weak_hire|do_not_hire`; `interview_status` one of `in_process|completed|not_completed`.,

---

### DELETE /api/applications/{application_id}
**Purpose:** Delete an application.,

**Authentication:** Required.,

**Success (204 No Content).,

**Errors:** `401`, `404`.,

---

### GET /api/dashboard/overview?category={category}
**Purpose:** Hiring analytics for the current user.,

**Authentication:** Required.,

**Query parameters:** `category` (default `company`; one of `company`, `position`, `required_experience`.,

**Success (200):**
```json
{
    "total_jobs": 3,
    "total_candidates":  3,
    "total_leads": 3,
    "group_by": "company",
    "breakdown": [
        {"category": "Acme Corp", "jobs": 2, "candidates": 2},
        {"category": "Globex", "jobs": 1, "candidates": 1}
    ]
}
```

`total_candidates` counts actual application rows; `total_leads` sums the per-job
`leads_count` counter.,

**Errors:** `400` — invalid category,, `401`.,

---

### GET /api/dashboard/recent-leads?limit={limit}
**Purpose:** Most recent candidate applications across the user's jobs.,

**Authentication:** Required.,

**Query parameters:** `limit` (default 5, 1–50.,

**Success (200):**
```json
[
    {
        "id": 2,
        "name": "Newest",
        "email": "jane@example.com",
        "company_name": "Acme Corp",
        "position": "Backend Developer",
        "hiring_status": "hire",
        "created_at": "2026-09-04T12:00:00Z"
    }
]
```

**Errors:** `401`, `422`.,

---

### GET /api/dashboard/recent-jobs?limit={limit}
**Purpose:** Most recent jobs created by the current user.,

**Authentication:** Required.,

**Query parameters:** `limit` (default 5, 1–50.,

**Success (200):**
```json
[
    {
        "id": 2,
        "company_name": "Acme Corp",
        "position": "Backend Developer",
        "leads_count": 1,
        "created_at": "2026-09-04T12:00:00Z"
    }
]
```

**Errors:** `401`, `422`.,

---

### POST /api/public/contact
**Purpose:** Store a message from the landing page's Contact Us form.

**Authentication:** Not required (a bearer token, if sent, is ignored).

**Request body:**
```json
{
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "message": "Hello! I'd like a demo."
}
```
All fields are required. Names are trimmed and 1–100 characters, `message` is
trimmed and 1–5000 characters, `email` must be a valid address. The message is
saved to the `contact_messages` table; `email` is the address the team replies to.

**Success (201):** `{ "message": "Thanks for reaching out! We'll get back to you soon." }`

**Errors:** `422` (validation — nothing is stored), `429` (more than 5 messages
from one client within 10 minutes; in-process limit), `503` (database unavailable).

---

### GET /health
**Purpose:** Liveness probe.,

**Authentication:** Not required.,

**Success (200):** `{ "status": "ok" }`.,
---

## Key functions

### Security (`app/core/security.py`)
* `hash_password(password) -> str` — bcrypt-hash a plain password (72-byte
  truncation guard). Returns the salted digest.
* `verify_password(plain_password, hashed_password) -> bool` — compare a plain
  password against a stored hash;; returns `False` for malformed hashes instead of crashing.

* `create_access_token(subject, expires_delta=None) -> str` — mint a signed JWT
  with `sub` = user id and `exp` (configurable lifetime,, default 60 min).
* `decode_access_token(token) -> dict` — validate signature/expiry and return payload;
  raises `JWTError` when invalid.,

### Auth service (`app/services/auth.py`)
* `register_user(db,, payload) -> User` — validates duplicate email (raises
  `ValueError`), hashes the password,, creates the user.,
* `authenticate_user(db,, email,, password,) -> User | None` — find by email,, verify
  hash,, reject inactive accounts,, return `None` on any failure..
* `issue_token(user,) -> Token` — build the `Token` response for a user..
* `send_reset_email(db,, email,) -> None` — mint a 30-min reset JWT for the user
  and logs it ((no SMTP yet)); silently returns when the email is unknown..
* `reset_password(db,, token,, new_password,) -> None` — decode the reset token,
  load the user,, replace the stored hash;; raises `ValueError` on invalid/expired token.,

### Job service (`app/services/job.py`)
* `increment_leads_count(db,, job_id,) -> Job | None` — `leads_count += 1` and
  return the refreshed job ((or `None` when missing).
* `job_analytics(db,, owner_id,, category="company") -> dict` — compute total jobs,,
  candidates,, leads,and a grouped breakdown by `company`, `position`, or
  `required_experience`;; raises `ValueError` for unsupported categories.,

### Resume analysis (`app/services/ai/heuristic.py`)
* `analyze_resume(resume_text,, job_requirements,) -> AnalysisResult` — case-insensitive,,
  substring matching of required skills against the resume;; returns `score` ((0–100,
  percent of required skills found), matched/missing skills,, per-skill matches,, and a summary..
* `score_candidate(match_details,) -> HiringStatus` — map a score to a recommendation::
  score ≥80 → `STRONG_HIRE`, ≥60 → `HIRE`, ≥40 → `WEAK_HIRE`, else → `DO_NOT_HIRE`.,

### CRUD — users (`app/crud/user.py`)
* `create_user(db,, payload,, is_superuser=False,) -> User` — hash the password,, insert,,,
  commit;; raises `ValueError` on duplicate email..
* `list_users(db,, skip=0,, limit=100,) -> list[User]`, `get_user_by_id(db,, user_id,)`,
  `get_user_by_email(db,, email,)`, `count_users(db,)`, `has_superuser(db,)`,
  `update_user(db,, user,, payload,) -> User`, `delete_user(db,, user,) -> None`.

### CRUD — jobs (`app/crud/job.py`)
`create_job(db,, owner_id,, payload,)`, `get_job(db,, job_id,)`,
`get_jobs_for_user(db,, owner_id,)`, `get_recent_jobs(db,, owner_id,, limit=5,)`,
`update_job(db,, job,, payload,)`, `delete_job(db,, job_id,)`.

### CRUD — applications (`app/crud/application.py`)
`create_application(db,, job_id,, payload,)`, `get_application(db,, application_id,)`,
`get_applications_for_job(db,, job_id,)`, `get_recent_applications(db,, owner_id,, limit=5,)`
((uses `contains_eager` to avoid N+1 for dashboard recent leads),,
`update_application(db,, application,, payload,)`, `delete_application(db,, application_id,)`.

---

## API flows

### Registration flow
```text
Client → POST /api/auth/register
  → Pydantic validates payload ((422 on bad input)
  → service checks duplicate email ((400 on duplicates)
  → password hashed ((bcrypt)
  → user inserted into users
  → JWT issued
  → 201 + {access_token,, token_type}
```

### Login flow
```text
Client → POST /api/auth/login
  → find user by email
  → verify bcrypt password
  → reject if inactive / wrong credentials ((401)
  → issue JWT
  → 200 + {access_token,, token_type}
```

### Job creation flow
```text
HR → Authorization: Bearer <jwt>
  → get_current_user verifies token ((401 on missing/invalid/expired)
  → Pydantic validates JobCreate ((422 on missing/empty fields)
  → crud.create_job inserts row ((owner_id = current user)
  → 201 + JobResponse
```

### Application creation flow
```text
HR → POST /api/applications?job_id=...
  → get_current_user ((401)
  → ownership check:: job must belong to current user, or admin session ((404 otherwise)
  → crud.create_application inserts row
  → service.increment_leads_count bumps job.leads_count
  → 201 + ApplicationItemResponse
```

### Protected endpoint flow
```text
Request + Authorization header
  → HTTPBearer extracts credentials ((401 when missing)
  → decode JWT ((401 invalid/expired signature)
  → load user by id ((401 user deleted)
  → require is_active ((401 deactivated)
  → optional superuser check ((403 non-admin)
  → handler runs ((resources further scoped to the owner; an admin session sees all)
```
---

## Error handling

| Situation | Status | Body |
| --- | --- | --- |
| Validation failure (bad email,, empty name,, missing field,, bad enum,, bad query) | `422` | FastAPI validation detail |
| Missing / invalid / expired token,, deleted/inactive user | `401` | `{"detail": "Not authenticated"}` or `"Invalid or expired token"` |
| Authenticated non-superuser hits admin route | `403` | `{"detail": "Admin privileges required"}` |
| Resource not found (or not owned) | `404` | `"User/Job/Application not found"` |
| Duplicate email at registration | `400` | `"A user with this email already exists"` |
| Email change to an address another account uses | `400` | `"A user with this email already exists"` |
| Wrong current password at `PATCH /api/auth/me/password` | `400` | `"Current password is incorrect"` |
| Password change on a Google-only account | `400` | `"This account does not have a password to change."` |
| Unsupported / mismatched / oversized profile image | `400` | `"Unsupported file type…"` / `"…does not match its declared type"` / `"Profile image must be at most 5 MB"` |
| Admin self-demote / self-deactivate / self-delete | `400` | dedicated message |
| Unsupported analytics category | `400` | `"Unsupported analytics category: ..."` |
| Invalid/expired reset token | `400` | `"Invalid or expired reset token"` |
| Database connectivity/operational failure | `503` | `"The service is temporarily unavailable. Try again later."`(full traceback logged server-side) |
| Unexpected server error | `500` | standard FastAPI internal error |

---

## Running tests

The test suite runs against a dedicated `resume_analyzer_test` database — it never
touches the dev/production data. It requires a running PostgreSQL (same credentials
as `DATABASE_URL`),but the test DB is created automatically.,

```bash
cd backend
pytest                        # run everything
pytest -v                    # verbose output
pytest tests/test_auth.py    # run a single test file
pytest tests/test_jobs.py -k "update"   # filter tests by name
```

Expected result:

```text
346 passed, 1 warning
```

The single warning is a Starlette deprecation raised inside FastAPI's routing
(`HTTP_422_UNPROCESSABLE_ENTITY`), not from the application's own code.

> Note: the exact count grows as endpoints are added (e.g. the Settings/profile
> tests in `tests/test_settings.py`). What matters is that the run is green.

---

## Interactive API docs

FastAPI ships automatic OpenAPI documentation:

* **Swagger UI:** http://localhost:8000/docs
* **ReDoc:** http://localhost:8000/redoc
* **OpenAPI JSON:** http://localhost:8000/openapi.json

Both docs let you try every endpoint directly from the browser.,

---

## Resume analysis (current heuristics)

`app/services/ai/heuristic.py` implements deterministic, keyword-based logic:

* required skills are split on commas/semicolons/newlines,
* matching is case-insensitiveand substring based (`"SQL"` matches `"PostgreSQL"`),
* `score` = matched required skills / total required skills × 100,
* `score_candidate` maps the score to a hiring recommendation.,

No external AI provider is required today; swap the function bodies for real LLM
calls later without changing the schemas or approvals.,

---

## Notes for contributors

* Keep the layering: Router → Service (only if needed) → CRUD → DB..
* Tests must not rely on execution order; each test starts with empty tables..
* Never commit real secrets (`.env` is git-ignored;; only commit `.env.example` with placeholders.,
* SQL injection is mitigated by always using SQLAlchemy ORM/parameterized queries—
  never concatenate user input into raw SQL.,

---
