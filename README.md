# Resume Analyzer

A modern, full-stack recruitment platform and applicant tracking system (ATS) powered by multi-provider AI analysis, granular role-based access control, and dedicated workspaces for HR recruiters, platform administrators, and job applicants.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [User Roles & Permissions](#user-roles--permissions)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Backend Architecture](#backend-architecture)
- [Background Processing Architecture (Celery + Redis)](#background-processing-architecture-celery--redis)
- [CRM Frontend Architecture](#crm-frontend-architecture)
- [Landing Website](#landing-website)
- [Core Business Workflows](#core-business-workflows)
- [AI Integration & Analysis Engine](#ai-integration--analysis-engine)
- [Database Schema & Migrations](#database-schema--migrations)
- [API Reference Catalog](#api-reference-catalog)
- [Authentication & Security](#authentication--security)
- [External Integrations](#external-integrations)
- [Environment Variables](#environment-variables)
- [Prerequisites](#prerequisites)
- [Installation & Local Setup](#installation--local-setup)
- [Running the Applications](#running-the-applications)
- [Database Migrations](#database-migrations)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Production Build Instructions](#production-build-instructions)
- [Phase 1 Production Operations & Disaster Recovery](#phase-1-production-operations--disaster-recovery)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Deployment Status & Known Limitations](#deployment-status--known-limitations)

---

## Overview

**Resume Analyzer** is an enterprise-ready recruitment management platform consisting of three tightly integrated applications:

1. **Backend REST API (`backend/`)**: A high-performance FastAPI service backed by PostgreSQL and SQLAlchemy, featuring multi-provider LLM integrations (OpenRouter, Groq, Google Gemini, Anthropic, OpenAI, DeepSeek, and SSRF-safe custom endpoints), zero-dependency resume document text extraction (PDF, DOCX, TXT), automated background batch processing, document export generation (PDF, Excel, Word), and cryptographic security.
2. **HR & Admin CRM (`crm/`)**: A responsive single-page application built with React 19, TypeScript, Vite, and React Router v7. It features dedicated workspaces for HR recruiters, a superuser admin console, a candidate application portal, and dynamic public application forms.
3. **Public Landing Website (`landing/`)**: A marketing and lead generation application built with React 19, TypeScript, and Vite. It offers 4-language localization (`en`, `ru`, `uz`, `kiril`), theme synchronization, direct integration with the backend public contact service, and automatic CRM session detection.

---

## System Architecture

```mermaid
graph TB
    subgraph Clients["Client Layer (Browsers)"]
        Visitor["Public Visitor / Applicant"]
        HRUser["HR Recruiter"]
        AdminUser["Platform Administrator"]
        CandidateUser["Job Candidate"]
    end

    subgraph FrontendApps["Frontend Applications"]
        Landing["Landing Website (landing/)<br/>React 19 + TypeScript + Vite<br/>Port 5174"]
        CRM["HR CRM & Portal (crm/)<br/>React 19 + TypeScript + Vite<br/>Port 5173"]
    end

    subgraph BackendApp["API & Business Logic (backend/)"]
        FastAPI["FastAPI REST Service<br/>Uvicorn | Port 8000 (/api)"]
        AuthModule["Auth & Security<br/>JWT Purpose Claims | Fernet | Bcrypt"]
        DocParser["Zero-Dependency Resume Parser<br/>PDF FlateDecode | DOCX XML | TXT"]
        AIEngine["AI Orchestration Layer<br/>Provider Routing | Retries | SSRF Guard"]
        ExportEngine["Export Engine<br/>ReportLab | OpenPyXL | python-docx"]
        BatchEngine["Auto Analyze Engine<br/>Async Background Worker"]
    end

    subgraph Persistence["Data Layer"]
        Postgres[("PostgreSQL Database<br/>19 Tables | Alembic Migrations")]
        Storage[("Local File Storage (uploads/)<br/>Profile Avatars | Candidate Resumes")]
    end

    subgraph ExternalServices["External Services"]
        OpenRouter["OpenRouter API"]
        Groq["Groq API"]
        Gemini["Google Gemini API"]
        Anthropic["Anthropic Messages API"]
        OpenAICompatible["OpenAI / DeepSeek / Custom AI"]
        Resend["Resend REST API (Transactional Email)"]
        GoogleOAuth["Google Cloud OAuth 2.0"]
    end

    Visitor -->|Views pages / Contact inquiry| Landing
    Visitor -->|Submits public application /apply/:token| CRM
    HRUser -->|Recruitment pipeline & AI scoring| CRM
    AdminUser -->|System console & user moderation| CRM
    CandidateUser -->|Follows applications & interviews| CRM

    Landing -.->|Checks resumeAnalyzer.signedIn cookie| CRM
    Landing -->|POST /api/public/contact| FastAPI
    CRM -->|REST API Requests with Bearer JWT| FastAPI

    FastAPI --> AuthModule
    FastAPI --> DocParser
    FastAPI --> AIEngine
    FastAPI --> ExportEngine
    FastAPI --> BatchEngine

    FastAPI -->|SQLAlchemy ORM + Advisory Locks| Postgres
    FastAPI -->|Direct File I/O| Storage

    AIEngine --> OpenRouter
    AIEngine --> Groq
    AIEngine --> Gemini
    AIEngine --> Anthropic
    AIEngine --> OpenAICompatible
    AuthModule --> Resend
    AuthModule --> GoogleOAuth
```

---

## Key Features

### Recruitment & Vacancy Management
- **Vacancy Creation & AI Parser**: HR can create jobs manually or paste unstructured job posting text to let AI automatically extract the title, company name, requirements, skills, experience, and generate customized application questions.
- **Customizable Public Application Forms**: Every job can configure tailored application form questions (text, email, phone, single choice, and file uploads). Forms are published with a cryptographically secure token (`/apply/:token`) that can be regenerated or revoked at any time.
- **Application Tracking Pipeline**: Complete hiring lifecycle tracking from `new` to `screening`, `interviewing`, `offered`, `hired`, or `rejected`.
- **Zero-Dependency Resume Text Extraction**: Built-in parsers read plain text directly from uploaded `.pdf` (decompressed via zlib FlateDecode and PDF font operators `Tj`/`TJ`), `.docx` (ZIP XML extraction), and `.txt` files without requiring heavy third-party OCR runtimes.
- **AI Resume Match & Candidate Scoring**: Analyzes applicant resumes against job requirements and custom form answers, outputting an objective match score (0–100%), structured strengths, missing requirements, risk factors, and advisory recommendations (`strong_hire`, `hire`, `weak_hire`, `do_not_hire`).
- **Auto Analyze Background Batches**: Bulk screen up to 1,000 new, unanalyzed applications asynchronously in the background with real-time progress tracking and cancellation controls.
- **Comparative Candidate Analysis**: Generates relative percentile rankings and pool statistics comparing candidates within the same job vacancy based on completed AI evaluations.
- **Interview Scheduling & Management**: Schedule interviews with date/time, duration, interviewer assignment, video meeting links, and status workflows (`upcoming`, `completed`, `cancelled`).
- **Universal Multi-Format Export**: Export filtered tables of jobs, applications, candidates, and interviews to publication-ready PDF, Excel (`.xlsx`), or Word (`.docx`) documents.

### Candidate Portal
- **Independent Candidate Identity**: Job seekers maintain dedicated candidate accounts (`candidate_accounts`) completely separated from staff identities.
- **Application Status & Timeline**: Real-time tracking of candidate application progress, stages, and candidate-safe evaluation feedback (never leaking internal HR notes or recruiter rankings).
- **Interview Calendar**: Direct visibility into scheduled interview times, interviewers, and meeting URLs.
- **Profile Management**: Profile image upload, password management, and seamless account linking via Google OAuth.

### Platform Administration & Monitoring
- **User Directory & Lifecycle Controls**: Platform-wide user management to inspect activity, activate/deactivate accounts, promote or demote administrators, and delete users (with built-in safeguards preventing self-demotion or removing the last active administrator).
- **Cross-Organization Governance**: Global directory of all jobs, applications, candidates, and interviews across all recruiters, with moderation controls to remove inappropriate job postings.
- **AI Performance & Usage Monitoring**: Real-time tracking of AI provider health, latency, request volume, error classifications, and detailed inspection of individual analysis runs.
- **Audit Logs & Security Trail**: Immutable, searchable audit logs tracking all sensitive actions (auth events, user mutations, job deletions, batch starts) enriched with actor ID, IP address, user agent, and unique request IDs.
- **System Errors & Diagnostics**: Centralized logging of server-side 5xx errors with automated request-ID tracing and zero sensitive-data leakage.
- **Runtime Feature Toggles & Health Checks**: Runtime toggles for public user registration and live health reports checking API status, PostgreSQL connectivity, AI providers, email delivery, and disk storage.

---

## User Roles & Permissions

| Role | Scope | Data Access | Available Workspaces | Key Capabilities |
|---|---|---|---|---|
| **HR Recruiter** | Tenant-isolated (`users` table, `is_superuser=False`) | Own data only (`owner_id = user.id`) | HR Workspace (`/dashboard`, `/jobs`, `/applications`, `/candidates`, `/interviews`, `/analytics`, `/settings`) | Create and manage vacancies, publish application forms, review applications, trigger AI evaluations, schedule interviews, export reports, configure custom AI provider keys. |
| **Platform Admin** | Global superuser (`users` table, `is_superuser=True`) | All platform data (`owner_id = None`) | Admin Console (`/admin/*`) & HR Workspace | Full HR capabilities across all recruiter data, user management (activate/deactivate/promote/delete), job moderation, AI performance monitoring, audit log inspection, error tracking, runtime settings. |
| **Candidate** | Dedicated portal (`candidate_accounts` table) | Own applications and interviews only | Candidate Portal (`/candidate/*`) | Track application statuses, view interview dates and meeting links, receive candidate-safe feedback, manage personal profile. Isolated from HR/admin endpoints. |
| **Anonymous Visitor** | Public unauthenticated | Public endpoints only | Landing Page (`landing/`) & Apply Form (`/apply/:token`) | Browse landing marketing content, submit contact messages, apply for published job openings via secure token. |

---

## Technology Stack

### Backend Application (`backend/`)
- **Runtime**: Python 3.14+
- **Framework**: FastAPI, Uvicorn
- **ORM & Database**: SQLAlchemy 2.x, PostgreSQL 14+, Alembic (database migrations)
- **Validation & Settings**: Pydantic v2, Pydantic Settings, email-validator
- **Security & Cryptography**: Python-Jose (JWT generation and verification), Passlib & Bcrypt (password hashing), Cryptography / Fernet (symmetric encryption for user AI API keys), Python-Multipart
- **HTTP Client**: HTTPX (asynchronous client for AI provider APIs, Google OAuth 2.0 exchange, and Resend transactional email)
- **Document Exporting**: ReportLab (PDF generation), OpenPyXL (Excel `.xlsx` generation), python-docx (Word `.docx` generation)
- **Document Parsing**: Python standard library (`zlib`, `re`, `zipfile`, `html`) for dependency-free text extraction from PDF, DOCX, and TXT files
- **Background Processing & Message Broker**: Celery 5.x, Redis 7+ (distributed task execution, dedicated queues)
- **Reliability & Data Consistency**: Transactional Outbox pattern, idempotent execution, bounded exponential backoff
- **Testing**: Pytest, FastAPI TestClient

### CRM Frontend Application (`crm/`)
- **Runtime**: Node.js 20+
- **Framework**: React 19, TypeScript ~5.7
- **Bundler & Dev Server**: Vite 6
- **Routing**: React Router v7 (code-splitting with React `lazy` and `Suspense`)
- **UI Components & Icons**: Custom token-based design system, Lucide React
- **Data Visualization**: Recharts (trend charts, breakdown charts, pipeline funnels)
- **Authentication**: Native JWT token storage with silent refresh interceptors, `@react-oauth/google`
- **Testing**: Vitest, React Testing Library, JSDOM

### Landing Website (`landing/`)
- **Runtime**: Node.js 20+
- **Framework**: React 19, TypeScript ~5.7
- **Bundler & Dev Server**: Vite 6
- **Internationalization (i18n)**: Fully typed multi-language system (`en`, `ru`, `uz`, `kiril`)
- **Theme Engine**: Light / Dark / System themes with CSS custom properties synced via `localStorage`
- **Integration**: CRM session detection via shared cookie, direct Contact form submission to FastAPI

---

## Repository Structure

```text
resume_analyzer/
├── README.md                      # Primary technical documentation and onboarding guide
├── docker-compose.yml             # Multi-worker background processing orchestration (API, Redis, Postgres, Workers)
├── .gitignore                     # Repository-wide Git ignore rules
│
├── backend/                       # FastAPI REST API & Database Service
│   ├── Dockerfile                 # Production multi-stage Dockerfile for API & Celery workers
│   ├── alembic.ini                # Alembic migration configuration
│   ├── pytest.ini                 # Pytest configuration
│   ├── requirements.txt           # Python dependency specifications
│   ├── .env.example               # Backend environment variable template
│   ├── alembic/                   # Database migration scripts
│   │   ├── env.py                 # Alembic migration environment
│   │   └── versions/              # 23 incremental schema migration versions
│   ├── app/
│   │   ├── main.py                # FastAPI initialization, middleware, lifecycle, static mounts
│   │   ├── core/                  # Core infrastructure (config, database, security, celery_app, redis)
│   │   ├── crud/                  # Database access layer (SQLAlchemy query models)
│   │   ├── dependencies/          # Dependency injection (HR auth, admin scope, candidate auth)
│   │   ├── models/                # 21 SQLAlchemy database models (including batch items & outbox)
│   │   ├── routers/               # 10 API route groups (auth, jobs, applications, admin, etc.)
│   │   ├── schemas/               # Pydantic validation and serialization schemas
│   │   ├── services/              # Business logic (AI pipelines, exports, auth, email, parsing, outbox)
│   │   └── tasks/                 # Celery background tasks (ai_analysis, notifications, exports)
│   ├── tests/                     # 975+ automated tests covering all backend domains & background queues
│   └── uploads/                   # Shared file storage (profile avatars, uploaded resumes, exports)
│
├── crm/                           # HR & Admin CRM Single Page Application
│   ├── package.json               # Frontend dependencies and scripts
│   ├── vite.config.ts             # Vite configuration
│   ├── tsconfig.json              # TypeScript compiler configuration
│   ├── eslint.config.js           # ESLint configuration
│   ├── .env.example               # CRM environment variable template
│   ├── index.html                 # CRM HTML entry point
│   └── src/
│       ├── main.tsx               # React application entry point
│       ├── App.tsx                # Context providers and root routing gate
│       ├── config.ts              # Cross-application URL configuration
│       ├── auth/                  # Token storage, Google OAuth helper, session roles
│       ├── components/            # Reusable UI components, modals, guards, layouts
│       ├── context/               # AuthContext, CandidateAuthContext
│       ├── contexts/              # ThemeContext, LanguageContext, ToastContext
│       ├── hooks/                 # Custom React hooks (URL filters, debounce, media queries)
│       ├── pages/                 # CRM view pages (HR workspace, Admin, Candidate, Public forms)
│       ├── routes/                # Central route definitions and authorization guards
│       ├── services/              # API clients and HTTP interceptors
│       ├── translations/          # UI translation bundles
│       └── types/                 # TypeScript type and interface definitions
│
└── landing/                       # Public Marketing & Lead Generation Website
    ├── package.json               # Landing dependencies and scripts
    ├── vite.config.ts             # Vite configuration
    ├── tsconfig.json              # TypeScript compiler configuration
    ├── .env.example               # Landing environment variable template
    ├── index.html                 # Landing HTML entry point
    ├── README.md                  # Landing site documentation
    └── src/
        ├── main.tsx               # React application entry point
        ├── App.tsx                # Router-free page switcher
        ├── components/            # Section components (Hero, Features, Pricing, Contact, etc.)
        ├── hooks/                 # Document metadata and section reveal hooks
        ├── i18n/                  # Typed translation catalogs (EN, RU, UZ, Kiril)
        ├── lib/                   # API clients, theme utilities, configuration
        ├── pages/                 # LandingPage, SimplePage (Terms, Privacy, 404)
        └── styles/                # CSS tokens, base styles, landing page layouts
```

---

## Backend Architecture

### Request Processing Lifecycle

```text
HTTP Request
  │
  ▼
RequestContextMiddleware  ────────► Injects unique X-Request-ID header & catches unhandled 5xx
  │
  ▼
CORSMiddleware           ────────► Validates Origins (CRM :5173, Landing :5174)
  │
  ▼
FastAPI APIRouter        ────────► Dispatches route (/api/auth, /api/jobs, /api/applications, etc.)
  │
  ▼
Dependency Injection     ────────► get_db (Session), get_current_session, get_access_scope
  │
  ▼
Service Layer            ────────► Domain business logic, AI orchestration, file processing
  │
  ▼
CRUD Layer               ────────► Scoped database queries (enforcing multi-tenant owner_id)
  │
  ▼
SQLAlchemy ORM           ────────► PostgreSQL database transactions
```

### Application Lifecycle & Startup Automation
During startup (`lifespan` in `backend/app/main.py`), the backend automatically:
1. **Validates Security Configuration**: Warns if default development `SECRET_KEY` or sandbox Resend email configurations are active.
2. **Auto-Bootstraps the Database**: Verifies PostgreSQL connectivity. If the target database does not exist, it connects to PostgreSQL's maintenance database and creates it automatically.
3. **Applies Schema Migrations Safely**: Acquires a dedicated PostgreSQL advisory lock (`0x52_41_53_43`) to prevent race conditions across multi-worker environments, verifies the current Alembic revision against the codebase head revision, applies pending migrations automatically (if `DB_AUTO_MIGRATE=true`), and stamps the database.
4. **Seeds the Configured Superuser**: Automatically ensures that the credentials specified in `SUPERUSER_EMAIL` exist, have superuser privileges, and are marked active and email-verified.
5. **Performs Housekeeping**: Automatically cleans up expired and consumed pending registrations from `pending_registrations`.
6. **Graceful Shutdown**: Shuts down the shared asynchronous HTTP client releasing all persistent AI connections.

### Zero-Dependency Resume Text Extraction (`resume_text.py`)
To prevent the overhead and vulnerability footprint of heavyweight third-party document parsing daemons, the backend features custom, zero-dependency extractors:
- **`.txt`**: Decoded using UTF-8-SIG, Windows-1252, or Latin-1 fallbacks.
- **`.docx`**: Unzipped in memory using `zipfile`; extracts paragraph runs directly from `word/document.xml`.
- **`.pdf`**: Inspects stream blocks, decompresses data using Python's standard `zlib.decompress` (FlateDecode), and parses text-showing operands (`Tj` and `TJ`) while handling octal and hex character escapes.
- **Scanned / Image PDFs**: Safely identified and handled without crashing; returns an explanation indicating that the resume contained no text layer so analysis can proceed on form answers.

---

## Background Processing Architecture (Celery + Redis)

### 1. Overview
The Resume Analyzer background processing system decouples long-running, compute-intensive, and I/O-bound tasks from the synchronous FastAPI HTTP request cycle. It uses **Celery** as the distributed task execution framework, **Redis** as the high-throughput message broker, **PostgreSQL** as the authoritative source of truth for business data and task states, and a **Transactional Outbox** pattern to guarantee at-least-once task delivery without dual-write race conditions.

Key architectural benefits:
- **Zero Request Thread Blocking**: Fast response times for recruiters (< 100ms) while AI models take 5–30 seconds to parse and score candidate resumes.
- **Resilience Against Crashes**: Worker termination or server restarts do not lose tasks; late acknowledgments (`acks_late=True`) cause unacknowledged tasks to be automatically requeued.
- **Independent Elastic Scaling**: Workloads are isolated across dedicated queues, allowing AI workers, batch workers, and email notifications to scale independently based on queue depth.
- **Granular Batch Observability**: Each batch of up to 1,000 applications tracks item-level execution states (`pending`, `running`, `completed`, `failed`, `skipped`, `cancelled`) in PostgreSQL.

---

### 2. System Architecture Diagram

```mermaid
graph TB
    subgraph Clients["Client Layer"]
        CRMApp["React CRM (Port 5173)"]
        LandingApp["Landing Website (Port 5174)"]
    end

    subgraph API["FastAPI Application"]
        Router["HTTP Endpoints (/api/*)"]
        AuthService["Auth & Recruiter Scoping"]
        OutboxWriter["Transactional Outbox Writer"]
    end

    subgraph Database["PostgreSQL (Source of Truth)"]
        AppTable[("applications & analysis_batches")]
        BatchItems[("analysis_batch_items")]
        OutboxTable[("outbox_events")]
    end

    subgraph Broker["Redis Message Broker (Port 6379)"]
        QueueAI["Queue: ai_analysis"]
        QueueBatch["Queue: batch_analysis"]
        QueueNotify["Queue: notifications"]
        QueueExport["Queue: exports"]
        QueueDefault["Queue: default"]
    end

    subgraph Workers["Dedicated Celery Worker Pool"]
        WorkerAI["AI Worker (c=2)<br/>analyze_single_application_task"]
        WorkerBatch["Batch Worker (c=4)<br/>analyze_batch_item_task<br/>dispatch_batch_analysis_task"]
        WorkerNotify["Notifications Worker (c=2)<br/>send_email_task"]
        WorkerExport["Exports Worker (c=2)<br/>generate_export_task"]
        WorkerDefault["Default Worker (c=1)<br/>General Housekeeping"]
    end

    subgraph External["External Integrations"]
        LLMProviders["AI Providers<br/>(OpenRouter, Groq, Gemini)"]
        ResendAPI["Resend Email API"]
        SharedStorage[("Shared Storage Volume<br/>/app/uploads/")]
    end

    CRMApp -->|REST Requests| Router
    LandingApp -->|Contact Inquiries| Router
    Router --> AuthService
    Router --> OutboxWriter

    OutboxWriter -->|Atomic SQL Commit| AppTable
    OutboxWriter -->|Atomic SQL Commit| BatchItems
    OutboxWriter -->|Atomic SQL Commit| OutboxTable

    OutboxWriter -->|Publish Event| QueueAI
    OutboxWriter -->|Publish Event| QueueBatch
    OutboxWriter -->|Publish Event| QueueNotify
    OutboxWriter -->|Publish Event| QueueExport

    QueueAI --> WorkerAI
    QueueBatch --> WorkerBatch
    QueueNotify --> WorkerNotify
    QueueExport --> WorkerExport
    QueueDefault --> WorkerDefault

    WorkerAI -->|Decrypt API Keys & Read Resumes| Database
    WorkerAI -->|Inference Call| LLMProviders
    WorkerAI -->|Persist Results & ai_score| AppTable

    WorkerBatch -->|Atomic SQL Counter Increments| Database
    WorkerBatch -->|Inference Call| LLMProviders
    WorkerBatch -->|Update Item Status| BatchItems

    WorkerNotify -->|Send Transactional Emails| ResendAPI
    WorkerExport -->|Write Generated PDF/XLSX/DOCX| SharedStorage
    WorkerAI -->|Read Resume Files| SharedStorage
```

---

### 3. Queue Topology and Worker Responsibilities

Tasks are strictly partitioned into dedicated Kombu queues to prevent noisy-neighbor starvation:

| Queue Name | Routing Key Pattern | Dedicated Tasks | Concurrency Recommendation | Description |
|---|---|---|---|---|
| `ai_analysis` | `ai.#` | `app.tasks.ai_analysis.analyze_single_application_task` | 2 processes | Executes single-resume AI scoring. Limited concurrency respects provider rate limits. |
| `batch_analysis` | `batch.#` | `app.tasks.ai_analysis.analyze_batch_item_task`, `dispatch_batch_analysis_task` | 4 processes | High-throughput batch processing for bulk candidate evaluations (up to 1,000 items). |
| `notifications` | `notify.#` | `app.tasks.notifications.send_email_task` | 2 processes | Transactional email delivery via Resend (verification codes, password reset). Completely isolated so notifications are never delayed by LLM queues. |
| `exports` | `export.#` | `app.tasks.exports.generate_export_task` | 2 processes | Generates Excel, PDF, and Word export files and persists them to shared volume. |
| `default` | `default.#` | Unrouted tasks, outbox maintenance, periodic cleanup | 1 process | Fallback queue for general asynchronous tasks. |

---

### 4. Detailed Execution Workflows

#### A. Single Resume Analysis Workflow
1. **Trigger**: Recruiter clicks "Analyze" or sends `POST /api/applications/{id}/analyze`.
2. **Validation**: API validates recruiter ownership (`owner_id = user.id`), checks that the application is not already analyzed (`force=false`), and pre-verifies that the job owner has connected an AI provider.
3. **Transactional Outbox Record**: An event `analyze_single_application` is written to `outbox_events` and committed atomically with the application state.
4. **Task Dispatch**: Celery routes the task to the `ai_analysis` queue in Redis.
5. **Immediate API Response**: FastAPI returns HTTP 200 with the `ApplicationDetailResponse` showing `analysis_status="analyzing"`.
6. **Worker Processing**:
   - `worker-ai` pulls task from Redis.
   - Worker opens an isolated SQLAlchemy session (`with SessionLocal() as db:`).
   - Verifies idempotency guard (skips if already completed and `force=false`).
   - Resolves and decrypts the job owner's AI provider credentials from PostgreSQL using Fernet key (keys are never exposed in task messages).
   - Extracts resume text from shared storage volume (`/app/uploads/`).
   - Calls the LLM provider API with built-in retry and schema validation.
   - Updates `applications` table: `analysis_status="completed"`, `ai_score=88.0`, `ai_analysis_details={...}`.
   - Writes monitoring diagnostic entry to `ai_analysis_runs` and audit log entry.
   - Commits transaction and late-acknowledges the Celery task.

#### B. Batch Resume Analysis Workflow
1. **Batch Creation**: Recruiter submits `POST /api/applications/auto-analyze` with target count (1–1,000) and filters.
2. **Atomic Persistence**:
   - PostgreSQL inserts `analysis_batches` (status `queued`, total items count).
   - PostgreSQL inserts individual `analysis_batch_items` for every selected application (status `pending`).
   - Outbox event `dispatch_batch_analysis` is recorded and transaction commits.
3. **Batch Dispatching**:
   - `dispatch_batch_analysis_task` runs on `worker-batch`.
   - Transitions batch status to `running`.
   - Dispatches individual `analyze_batch_item_task` jobs for each item in the batch.
4. **Parallel Worker Execution**:
   - `worker-batch` processes items concurrently across workers with `worker_prefetch_multiplier=1`.
   - **Cooperative Cancellation Guard**: Before calling the AI provider, the worker checks if `batch.status == "cancelled"`. If cancelled, the item transitions to `cancelled` and terminates immediately with zero LLM API costs.
   - **Atomic SQL Counter Increments**: When an item completes, fails, or is skipped, counters are updated via PostgreSQL SQL expressions (`successful_count = AnalysisBatch.successful_count + 1`), preventing race conditions.
   - **Item State Tracking**: Detailed item row in `analysis_batch_items` records `started_at`, `completed_at`, `celery_task_id`, and exact error messages on failure.
   - **Batch Completion**: The last item to finish automatically transitions the parent batch to `status="completed"` and records `finished_at`.

#### C. Document Export Generation Workflow
1. **Trigger**: Recruiter requests filtered table export (`POST /api/exports`).
2. **Dispatch**: API dispatches `generate_export_task` to the `exports` queue with resource name, column definitions, and format (`pdf`, `xlsx`, `docx`).
3. **Execution**:
   - `worker-exports` opens a DB session and applies recruiter data scoping.
   - Invokes `ExportService.export()` to stream records from PostgreSQL and compile document binary.
   - Writes generated document to `/app/uploads/exports/{filename}` in the shared volume.
   - Returns structured metadata (`status="completed"`, `filename`, `file_size`, `record_count`).

#### D. Transactional Email Dispatch Workflow
1. **Trigger**: User registers or requests verification code resend (`POST /api/auth/resend-verification-code`).
2. **Dispatch**: Task `send_email_task` is dispatched to the `notifications` queue.
3. **Delivery**:
   - `worker-notifications` calls Resend REST API via `httpx`.
   - Permanent rejections (e.g., sandbox 403, bad email format) fail fast without retrying.
   - Transient errors (HTTP 429, 500, 502, 503, 504) trigger Celery exponential backoff retries (countdown 5s, 10s, 20s up to 3 attempts).

---

### 5. Worker Concurrency Guidelines and Allocation

| Worker Container / Process | Assigned Queues | Recommended Concurrency (`-c`) | Memory Allocation | Scalability Strategy |
|---|---|---|---|---|
| `worker-ai` | `ai_analysis` | 2 processes | 512 MB – 1 GB | Kept low to avoid exceeding per-minute rate limits (RPM/TPM) of third-party AI provider tiers. |
| `worker-batch` | `batch_analysis` | 4 processes | 1 GB – 2 GB | High throughput for processing 1,000 resumes. Scale out horizontally with additional nodes if batch volume increases. |
| `worker-notifications` | `notifications` | 2 processes | 256 MB – 512 MB | Fast I/O workers. Processes hundreds of emails per minute with low CPU overhead. |
| `worker-exports` | `exports` | 2 processes | 1 GB – 2 GB | High memory headroom for generating large PDFs and Excel workbooks with ReportLab and OpenPyXL. |
| `worker-default` | `default` | 1 process | 256 MB | Single-process housekeeping worker. |

---

### 6. Configuration and Environment Variables

Add these variables to your `backend/.env` file:

```ini
# Redis & Celery Message Broker Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Default queue for tasks without an explicit route
CELERY_TASK_DEFAULT_QUEUE=default

# Worker process concurrency per node
CELERY_WORKER_CONCURRENCY=4

# Task execution reliability:
# acks_late ensures tasks are acknowledged only after completion (prevents loss on worker crash)
CELERY_TASK_ACKS_LATE=true

# prefetch_multiplier=1 disables greedy allocation, ensuring fair distribution across workers
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# reject_on_worker_lost requeues tasks if a worker process is terminated abruptly (SIGKILL/OOM)
CELERY_TASK_REJECT_ON_WORKER_LOST=true

# Execution timeouts in seconds (soft raises SoftTimeLimitExceeded, hard kills worker)
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=360
```

---

### 7. Local Development Setup Instructions

#### Running with Docker Compose (Recommended)
The fastest way to start the complete stack (API, Redis, PostgreSQL, and all 5 workers) is via Docker Compose:

```bash
# 1. Clone repository and navigate to root
cd hr-resume-analyzer

# 2. Copy environment file
cp backend/.env.example backend/.env

# 3. Start all services in the background
docker-compose up -d

# 4. Follow logs
docker-compose logs -f
```

#### Running Locally without Docker
To run workers natively on your host machine:

1. **Start Redis Server**:
   ```bash
   # Linux / Ubuntu / WSL:
   sudo service redis-server start

   # Verify Redis is listening:
   redis-cli ping
   # Expected output: PONG
   ```

2. **Activate Backend Virtual Environment**:
   ```bash
   cd backend
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Run Schema Migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start the FastAPI API Server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

### 8. Running Celery Workers in Development

In development, you can run all queues within a single combined worker, or run dedicated workers matching production:

#### Option A: Combined Development Worker (All Queues)
```bash
celery -A app.core.celery_app worker -Q ai_analysis,batch_analysis,notifications,exports,default -c 4 -l info
```

#### Option B: Dedicated Workers (Production Parity)
Run each command in a separate terminal:

```bash
# 1. AI Analysis Worker
celery -A app.core.celery_app worker -Q ai_analysis -c 2 -l info -n worker_ai@%h

# 2. Batch Analysis Worker
celery -A app.core.celery_app worker -Q batch_analysis -c 4 -l info -n worker_batch@%h

# 3. Notifications Worker
celery -A app.core.celery_app worker -Q notifications -c 2 -l info -n worker_notifications@%h

# 4. Exports Worker
celery -A app.core.celery_app worker -Q exports -c 2 -l info -n worker_exports@%h

# 5. Default Queue Worker
celery -A app.core.celery_app worker -Q default -c 1 -l info -n worker_default@%h
```

---

### 9. Docker Compose Multi-Worker Stack

The root `docker-compose.yml` provides production-grade orchestration:

- **`postgres`**: PostgreSQL 16 with health checks (`pg_isready`).
- **`redis`**: Redis 7 Alpine with persistent volume and health check (`redis-cli ping`).
- **`api`**: FastAPI application with auto-migration and live reload.
- **`worker-ai`**: Dedicated container for `ai_analysis` queue (concurrency: 2).
- **`worker-batch`**: Dedicated container for `batch_analysis` queue (concurrency: 4).
- **`worker-notifications`**: Dedicated container for `notifications` queue (concurrency: 2).
- **`worker-exports`**: Dedicated container for `exports` queue (concurrency: 2).
- **`worker-default`**: Dedicated container for `default` queue (concurrency: 1).
- **`celery-beat`**: Celery Beat scheduler executing periodic jobs (outbox recovery scan every 30s).
- **`flower`**: Real-time Celery task monitoring dashboard on port `5555`.
- **Shared Volume (`uploads-data`)**: Mounted at `/app/uploads` across `api`, `worker-ai`, `worker-batch`, and `worker-exports`.

---

### 10. Database Migration Instructions

The background architecture introduces two new tables:
1. `analysis_batch_items`: Individual batch item tracking for Celery workers.
2. `outbox_events`: Transactional outbox table for reliable at-least-once task dispatching.

To apply migrations:
```bash
cd backend
alembic upgrade head
```

To roll back the background migrations:
```bash
alembic downgrade -2
```

---

### 11. Monitoring and Operations

#### Worker Status Inspection
```bash
# Check if workers are running and responding
celery -A app.core.celery_app inspect ping

# View active running tasks
celery -A app.core.celery_app inspect active

# View reserved/prefetched tasks
celery -A app.core.celery_app inspect reserved

# View registered tasks
celery -A app.core.celery_app inspect registered
```

#### Queue Depth Monitoring via Redis CLI
```bash
# Check queue length (pending tasks)
redis-cli llen ai_analysis
redis-cli llen batch_analysis
redis-cli llen notifications
redis-cli llen exports
```

#### Flower Web Monitoring (Optional)
Run the Flower real-time dashboard to monitor task execution, worker loads, and latencies in your browser:
```bash
pip install flower
celery -A app.core.celery_app flower --port=5555
# Open http://localhost:5555 in your browser
```

---

### 12. Failure Modes, Retry Policies, and Dead-Letter Handling

1. **Transient Provider Failures (Retryable)**:
   - Status codes: HTTP 429 (Rate Limit), 502 (Bad Gateway), 503 (Service Unavailable), 504 (Gateway Timeout), and network disconnects.
   - Behavior: Retried with exponential backoff (`countdown = 5 * 2^retries`). Maximum 2 retries at Celery task level to prevent multiplying internal HTTP client retries.
2. **Permanent / Business Failures (Non-Retryable)**:
   - Status codes: HTTP 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 422 (Unprocessable Entity), missing AI provider configuration (`AIConfigurationRequiredError`).
   - Behavior: Fails immediately without Celery retries. Updates PostgreSQL application row: `analysis_status="failed"` with sanitized error message for recruiter retry in the UI.
3. **Dead-Letter Handling & Outbox Recovery**:
   - Outbox events that fail to publish are retried up to 5 times.
   - Events exceeding 5 retries transition to `status="failed"` in `outbox_events` for administrator inspection.
   - `process_pending_outbox_events(db)` automatically recovers orphaned pending events.

---

### 13. Security and Multi-Tenant Isolation Model

- **Zero Secrets Over Message Broker**: Task payloads strictly pass database primary keys (`application_id: int`, `batch_id: int`). No API keys, passwords, bearer tokens, or resume raw contents are passed over Redis.
- **Worker-Side Credential Resolution**: The Celery worker loads the application, queries the owning recruiter (`application.job.owner_id`), and decrypts their API key in-process using the application's Fernet encryption key (`AI_CREDENTIAL_ENCRYPTION_KEY`).
- **Tenant Data Isolation**: Database queries inside workers strictly enforce `owner_filter(Job.owner_id, owner_id)`. Recruiters can never access or analyze candidates outside their workspace.

---

### 14. Shared Storage Architecture

Uploaded documents (resumes in `.pdf`, `.docx`, `.txt`) and generated exports (`.xlsx`, `.pdf`, `.docx`) are stored on the filesystem under the path specified by `UPLOAD_DIR` (default: `uploads/`).

In containerized deployments, `docker-compose.yml` mounts a shared named volume `uploads-data` to `/app/uploads` across the API and all worker services:
- **API Container**: Saves incoming resume files uploaded via public application forms (`/app/uploads/resumes/`).
- **AI Workers**: Read resume text from `/app/uploads/resumes/` to generate prompt inputs.
- **Export Workers**: Write compiled documents to `/app/uploads/exports/`.

---

### 15. Testing Instructions

#### Running Celery Tests in Eager Mode
During automated testing, Celery is configured in eager mode (`task_always_eager=True`, `task_eager_propagates=False`) in `tests/conftest.py`. This executes task logic synchronously in the test process without requiring a running Celery daemon:

```bash
# Run Celery configuration and queue tests
pytest tests/test_celery_config.py

# Run Celery single resume analysis tests
pytest tests/test_celery_single_analysis.py

# Run Celery batch analysis tests
pytest tests/test_celery_batch.py

# Run Celery notification and export task tests
pytest tests/test_celery_notifications_and_exports.py

# Run Transactional Outbox tests
pytest tests/test_outbox.py
```

#### Running the Full Test Suite
```bash
pytest
```

---

### 16. Production Deployment Recommendations

1. **Process Supervision**: Run Celery workers under **systemd**, **Docker Compose**, or **Kubernetes** with `restart: unless-stopped`.
2. **Resource Limits**: Set memory limits (`--max-memory-per-child=500000` in kilobytes) to recycle worker processes and prevent Python memory leaks from document parsing.
3. **Connection Pooling**: Use Redis connection pooling with appropriate socket timeouts (`socket_timeout=5.0`).
4. **Log Aggregation**: Collect worker logs in JSON format via fluentd or Promtail/Loki.

---

### 17. Troubleshooting Guide

#### Issue: `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.`
- **Cause**: Redis server is not running or port 6379 is blocked.
- **Fix**: Start Redis with `sudo service redis-server start` (Linux/WSL) or verify `docker-compose up -d redis`.

#### Issue: Celery tasks stay in `PENDING` state and never run
- **Cause**: No Celery worker is listening to the designated queue.
- **Fix**: Check that workers are running with the matching queue flag: `-Q ai_analysis`, `-Q batch_analysis`, `-Q notifications`, `-Q exports`.

#### Issue: Tasks fail with `Application not found in database`
- **Cause**: Database transaction did not commit before the task was dispatched (dual-write race condition).
- **Fix**: Always dispatch tasks through `outbox_service.record_and_dispatch(db, ...)`, which commits the database transaction before enqueueing the task.

#### Issue: Worker OOM (Out of Memory) during large PDF export
- **Cause**: ReportLab drawing huge tables with 10,000+ rows into memory.
- **Fix**: The export service enforces pagination and column limits; ensure worker containers have at least 1 GB RAM allocated.

---

---

## CRM Frontend Architecture

### Routing and Layout Matrix

The CRM uses React Router v7 with fine-grained route guards:

```text
/ (RootRedirect)
  │
  ├──► Public / Auth Routes (No Shell)
  │     ├── /login, /register, /forgot-password, /reset-password, /verify-email
  │     ├── /select-role (Workspace selector for superusers)
  │     ├── /oauth/callback (Google OAuth redirect handler)
  │     └── /apply/:token (Public token-based applicant form)
  │
  ├──► HR Recruiter Workspace (RequireAuth -> AppLayout)
  │     ├── /dashboard (Overview metrics, recent leads & vacancies)
  │     ├── /jobs, /jobs/create, /jobs/:id, /jobs/:id/edit
  │     ├── /applications, /applications/:id (AI analysis, CV viewer, status update)
  │     ├── /candidates, /candidates/:id (Candidate pipeline details)
  │     ├── /interviews, /interviews/:id (Scheduling calendar)
  │     ├── /analytics (Trend charts, funnel analysis)
  │     └── /settings (Profile, password, custom AI provider keys)
  │
  ├──► Admin Console (RequireAdmin -> AppLayout[variant="admin"])
  │     ├── /admin/dashboard (Platform KPIs, 30-day activity)
  │     ├── /admin/users, /admin/users/:id (User management)
  │     ├── /admin/jobs (Moderation)
  │     ├── /admin/applications, /admin/candidates
  │     ├── /admin/interviews
  │     ├── /admin/ai-analysis (Run logs, error distribution)
  │     ├── /admin/analytics (Platform-wide metrics)
  │     ├── /admin/audit-logs (Searchable audit trail)
  │     ├── /admin/system-errors (5xx error inspector)
  │     ├── /admin/settings (Runtime registration toggles)
  │     └── /admin/system-health (Live subsystem checks)
  │
  └──► Candidate Portal (RequireCandidate -> CandidateLayout)
        ├── /candidate (Dashboard summary)
        ├── /candidate/applications, /candidate/applications/:id
        ├── /candidate/interviews
        └── /candidate/profile
```

### State Management & HTTP Layer
- **Centralized Authentication Contexts**: `AuthContext` manages HR/Admin tokens, active workspace roles, and automatic token refresh upon encountering 401 responses. `CandidateAuthContext` independently manages candidate portal sessions.
- **Silent JWT Refresh Interceptor**: The Axios/fetch client detects expired access tokens and seamlessly invokes `POST /api/auth/refresh` or `POST /api/candidate/auth/refresh` using the single-use refresh token, replaying the original request without disrupting the user.
- **URL-Driven Filtering (`useUrlFilters`)**: Data tables across jobs, applications, candidates, interviews, and admin directories synchronize search queries, status filters, sort columns, and pagination directly into browser URL search parameters for shareable states.

---

## Landing Website

The landing site (`landing/`) is an optimized, standalone presentation application:
- **Zero-Dependency Routing**: Because the site consists of a primary landing page and lightweight legal documents (`/privacy`, `/terms`), it implements a lightweight, router-free page switcher that reads the window pathname directly.
- **Internationalization (i18n)**: Features typed translation files (`src/i18n/en.ts`, `ru.ts`, `uz.ts`, `kiril.ts`). Adding a key to the English catalog enforces compilation-time type safety across all languages.
- **Theme & Design Tokens**: Design tokens (`tokens.css`) mirror the CRM's visual language. Theme preferences (`light`, `dark`, `system`) and language selections persist in `localStorage` under identical keys (`resume-analyzer-theme`, `resume-analyzer-language`), ensuring seamless continuity when switching between applications.
- **Cross-App Session Awareness**: Reads the `resumeAnalyzer.signedIn=1` cookie set by the CRM to dynamically swap the navigation call-to-action between "Log in" / "Get started" and "Open workspace" (`/dashboard`).
- **Contact Form**: Directly communicates with `POST /api/public/contact`, with built-in client-side IP-based rate limiting on the backend.

---

## Core Business Workflows

### 1. Job Creation to Applicant Submission

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR Recruiter
    participant CRM as CRM Frontend
    participant API as FastAPI Backend
    participant AI as AI Provider
    participant DB as PostgreSQL
    actor Candidate as Job Candidate

    HR->>CRM: Paste vacancy text
    CRM->>API: POST /api/jobs/analyze
    API->>AI: Analyze vacancy & extract requirements
    AI-->>API: Structured JSON (skills, description, questions)
    API-->>CRM: Formatted vacancy payload
    HR->>CRM: Review & save job
    CRM->>API: POST /api/jobs
    API->>DB: Store Job record
    HR->>CRM: Configure & publish application form
    CRM->>API: POST /api/jobs/:id/application-form/publish
    API->>DB: Generate public_token & store ApplicationForm
    API-->>CRM: Public URL (/apply/:token)

    Candidate->>CRM: Open /apply/:token
    CRM->>API: GET /api/public/applications/:token
    API-->>CRM: Public form fields & company info
    Candidate->>CRM: Upload resume + answers
    CRM->>API: POST /api/public/applications/:token/submit
    API->>DB: Save Application & ApplicationResponses
    API->>DB: Increment Job leads_count
    API-->>Candidate: 201 Created Confirmation
```

### 2. AI Screening to Hiring Decision

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR Recruiter
    participant CRM as CRM Frontend
    participant API as FastAPI Backend
    participant Parser as Zero-Dep Resume Parser
    participant AI as AI Provider
    participant DB as PostgreSQL
    actor Candidate as Job Candidate

    HR->>CRM: Trigger analysis (or launch Auto Analyze batch)
    CRM->>API: POST /api/applications/:id/analyze
    API->>DB: Fetch Application, Job & Responses
    API->>Parser: Extract text from resume file (PDF/DOCX/TXT)
    Parser-->>API: Extracted plain text
    API->>AI: Send prompt (Requirements + Answers + Resume text)
    AI-->>API: Structured evaluation (Score, Strengths, Risks, Recommendation)
    API->>DB: Persist ai_score & ai_analysis_details
    API-->>CRM: Updated Application details

    HR->>CRM: View Comparative Ranking
    CRM->>API: GET /api/applications/:id/comparison
    API->>DB: Calculate percentile rank within same job pool
    API-->>CRM: Relative percentile & rank

    HR->>CRM: Move to Candidate Pipeline
    CRM->>API: POST /api/applications/:id/convert-to-candidate
    API->>DB: Set candidate_at timestamp

    HR->>CRM: Schedule Interview
    CRM->>API: POST /api/interviews
    API->>DB: Store Interview (date, interviewer, link)

    Candidate->>CRM: Logs into Candidate Portal (/candidate)
    CRM->>API: GET /api/candidate/applications & /interviews
    API-->>CRM: Candidate-safe status, timeline & interview link
```

---

## AI Integration & Analysis Engine

### Supported AI Providers
The platform implements a provider-agnostic architecture supporting both proprietary and open-source models:

| Provider ID | Implementation Type | Default / Recommended Models | Base URL Configuration |
|---|---|---|---|
| `openrouter` | OpenAI-compatible | `google/gemma-4-26b-a4b-it:free` | `https://openrouter.ai/api/v1` |
| `groq` | OpenAI-compatible | `llama-3.3-70b-versatile` | `https://api.groq.com/openai/v1` |
| `gemini` | Native Gemini REST API | `gemini-2.0-flash`, `gemini-1.5-pro` | `https://generativelanguage.googleapis.com/v1beta/models` |
| `anthropic` | Native Messages API | `claude-3-5-sonnet-20241022` | `https://api.anthropic.com/v1/messages` |
| `openai` | OpenAI-compatible | `gpt-4o`, `gpt-4o-mini` | `https://api.openai.com/v1` |
| `deepseek` | OpenAI-compatible | `deepseek-chat` | `https://api.deepseek.com/v1` |
| `generic` | OpenAI-compatible | Any compliant model ID | User-supplied custom base URL (SSRF validated) |

### Credential Resolution & Multi-Tenant Encryption
1. **Custom Provider Configuration**: HR recruiters can save their own AI provider, API key, model ID, and custom base URL in **Settings -> AI Provider**.
2. **Fernet Encryption**: User API keys are symmetrically encrypted before persistence in `user_ai_provider_configs.api_key_encrypted` using the server's `AI_CREDENTIAL_ENCRYPTION_KEY`. Plaintext keys are never logged and never returned to the frontend.
3. **Resolution Hierarchy (`resolve_for_user`)**:
   - If the user has an active custom AI configuration, it is always used.
   - If no custom configuration exists and `REQUIRE_USER_AI_CONFIG=true` (default), the API rejects the analysis request with a clear 400 error directing the user to configure their credentials in Settings.
   - If `REQUIRE_USER_AI_CONFIG=false`, the system falls back to platform environment variables (`AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`).
4. **SSRF Guard for Generic Providers (`url_security.py`)**: Custom base URLs provided by users undergo strict validation: HTTPS is required (HTTP only allowed on localhost in debug mode), ports are restricted to 443 and 8443, credentials and fragments are rejected, and DNS resolution blocks private, loopback, link-local, multicast, or cloud-metadata IP addresses (e.g., `169.254.169.254`).

### Resilience, Rate Limiting & Backoff
- **Transient Error Retries**: Automatically retries HTTP 429, 502, 503, and 504 errors using exponential backoff (`AI_RETRY_BASE_DELAY`).
- **Upstream Rate Limit Headers**: Explicitly inspects and obeys `Retry-After` (seconds or RFC 9110 HTTP date) and `X-RateLimit-Reset` (Unix timestamp) headers from providers.
- **Budget Caps**: Enforces a per-wait limit (`AI_MAX_RETRY_WAIT = 30s`) and a cumulative retry budget (`AI_RETRY_BUDGET = 45s`).

### Structured Prompt Contracts
AI prompts enforce strict rules:
- Candidate input and resume content are treated as untrusted data to protect against prompt injection.
- Hallucinations are strictly forbidden: missing requirements must be explicitly labelled as "not found in provided information".
- Returns strict JSON conforming to `ApplicationAnalysis`:
  - `match_percentage`: Number (0–100)
  - `summary`: Concise recruiter summary
  - `matched_requirements` & `missing_requirements`: Array of strings
  - `matched_skills` & `missing_skills`: Array of strings
  - `strengths`, `weaknesses`, `risks`: Array of strings
  - `experience_analysis` & `education_analysis`: Narrative strings
  - `relevant_experience` & `relevant_projects`: Array of strings
  - `ai_recommendation`: `"strong_hire" | "hire" | "weak_hire" | "do_not_hire"`

---

## Database Schema & Migrations

The database is built on PostgreSQL and managed using SQLAlchemy models and Alembic.

```mermaid
erDiagram
    users ||--o{ jobs : "owns"
    users ||--o{ interviews : "conducts"
    users ||--o{ analysis_batches : "launches"
    users ||--o{ user_ai_provider_configs : "configures"
    users ||--o{ audit_logs : "actor"
    users ||--o{ system_error_logs : "user"

    jobs ||--|| application_forms : "has"
    jobs ||--o{ applications : "receives"

    candidate_accounts ||--o{ applications : "submits"

    applications ||--o{ application_responses : "contains"
    applications ||--o{ application_status_history : "tracks"
    applications ||--o{ interviews : "scheduled_for"
    applications ||--o{ ai_analysis_runs : "evaluated_in"

    users {
        int id PK
        string email UK
        string hashed_password
        string full_name
        string profile_image_url
        boolean is_active
        boolean is_superuser
        boolean is_email_verified
        string google_id UK
        datetime last_login_at
        datetime created_at
    }

    candidate_accounts {
        int id PK
        string email UK
        string hashed_password
        string full_name
        string profile_image_url
        boolean is_active
        boolean is_email_verified
        string google_id UK
        datetime created_at
    }

    jobs {
        int id PK
        uuid public_id UK
        int owner_id FK
        string company_name
        string position
        text description
        text required_skills
        text required_experience
        int leads_count
        datetime created_at
    }

    application_forms {
        int id PK
        int job_id FK,UK
        string public_token UK
        string title
        text description
        json fields
        boolean is_active
    }

    applications {
        int id PK
        int job_id FK
        int candidate_account_id FK
        string name
        string email
        string phone
        string resume_path
        string application_status
        string hiring_status
        string interview_status
        float ai_score
        json ai_analysis_details
        string analysis_status
        datetime candidate_at
        datetime submitted_at
    }

    application_responses {
        int id PK
        int application_id FK
        string field_id
        string field_label
        string field_type
        text value
        string file_path
    }

    interviews {
        int id PK
        int candidate_id FK
        int hr_id FK
        string interviewer
        datetime scheduled_at
        int duration_minutes
        string status
        string meeting_link
        text notes
    }

    analysis_batches {
        int id PK
        int owner_id FK
        int total
        int processed
        int successful_count
        int failed_count
        int skipped_count
        string status
        json application_ids
        int current_application_id
    }

    user_ai_provider_configs {
        int id PK
        int user_id FK,UK
        string provider
        string model_id
        string api_key_encrypted
        string base_url
        boolean is_active
    }

    audit_logs {
        int id PK
        int actor_user_id FK
        string action
        string resource_type
        int resource_id
        json details
        string ip_address
        string user_agent
        string request_id
        datetime created_at
    }
```

### Additional Relational & Support Tables
- `pending_registrations`: Stores unconfirmed user accounts during the 2-phase verification process (`email`, `hashed_password`, `full_name`, `token_hash`, `code_hash`, `expires_at`, `attempts`).
- `email_verifications`: Tracks verification attempt counters and cooldown windows.
- `application_status_history`: Historical log of candidate pipeline status transitions.
- `ai_analysis_runs`: Detailed logs of AI provider invocations (`latency_ms`, `error_type`, `error_message`, `status`).
- `system_error_logs`: 5xx server exceptions recorded with request IDs and user associations.
- `platform_settings`: Key-value runtime platform configuration (e.g. `registration_enabled`).
- `revoked_tokens`: JTI blacklist tracking revoked access tokens upon logout or role change.
- `session_cutoffs`: Tracks user password reset timestamps to invalidate all previously issued tokens.
- `contact_messages`: Inquiries submitted via the public landing page contact form.

---

## API Reference Catalog

The API is served with the `/api` prefix.

### 1. Authentication & Profile (`/api/auth`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | None | Initiates 2-phase registration; sends 6-digit OTP code or link via email |
| `POST` | `/api/auth/verify-email` | None | Verifies OTP code or link token and creates the permanent account |
| `POST` | `/api/auth/resend-verification-code` | None | Resends a 6-digit verification code subject to cooldown limits |
| `POST` | `/api/auth/login` | None | Authenticates with email and password; returns JWT access/refresh tokens |
| `POST` | `/api/auth/google` | None | Exchanges Google OAuth authorization code for session tokens |
| `POST` | `/api/auth/logout` | Bearer | Revokes current token in token registry |
| `POST` | `/api/auth/refresh` | None | Exchanges valid refresh token for a fresh token pair (rotation) |
| `POST` | `/api/auth/forgot-password` | None | Generates and emails password reset token |
| `POST` | `/api/auth/verify-reset-token` | None | Checks validity and expiration of password reset token |
| `POST` | `/api/auth/reset-password` | None | Resets password using valid token and revokes earlier sessions |
| `POST` | `/api/auth/select-role` | Optional | Switches session workspace between HR and Admin |
| `GET` | `/api/auth/me` | Bearer | Retrieves authenticated user profile |
| `PATCH` | `/api/auth/me` | Bearer | Updates authenticated user's name or email |
| `PATCH` | `/api/auth/me/password` | Bearer | Changes password; revokes all earlier sessions |
| `POST` | `/api/auth/me/profile-image` | Bearer | Uploads profile picture (JPEG/PNG/WebP, max 5MB) |
| `DELETE` | `/api/auth/me/profile-image` | Bearer | Removes profile picture |
| `GET` | `/api/auth/me/ai-provider` | Bearer | Gets user's custom AI provider configuration |
| `PUT` | `/api/auth/me/ai-provider` | Bearer | Saves encrypted custom AI provider credentials |
| `DELETE` | `/api/auth/me/ai-provider` | Bearer | Deactivates custom AI provider configuration |
| `POST` | `/api/auth/me/ai-provider/test` | Bearer | Tests live connection to configured AI provider |

### 2. Jobs & Vacancies (`/api/jobs`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/jobs` | Bearer | Lists vacancies owned by the authenticated HR (or all for Admin) |
| `POST` | `/api/jobs` | Bearer | Creates a new job vacancy |
| `POST` | `/api/jobs/analyze` | Bearer | Uses AI to parse unstructured vacancy text into structured fields |
| `GET` | `/api/jobs/{id}` | Bearer | Retrieves vacancy details by ID |
| `PUT` | `/api/jobs/{id}` | Bearer | Updates vacancy details |
| `DELETE` | `/api/jobs/{id}` | Bearer | Deletes vacancy and cascade-removes its applications |
| `GET` | `/api/jobs/{id}/application-form` | Bearer | Retrieves custom application form configuration |
| `PUT` | `/api/jobs/{id}/application-form` | Bearer | Updates custom application form fields |
| `POST` | `/api/jobs/{id}/application-form/publish` | Bearer | Generates or regenerates public form submission token |
| `DELETE` | `/api/jobs/{id}/application-form` | Bearer | Resets custom application form |

### 3. Applications & Candidates (`/api/applications`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/applications` | Bearer | Lists applications with status, candidate, search, and sort filters |
| `POST` | `/api/applications` | Bearer | Manually records an application and increments job leads count |
| `GET` | `/api/applications/{id}` | Bearer | Retrieves detailed application record and responses |
| `PATCH` | `/api/applications/{id}` | Bearer | Updates application, hiring, or interview status |
| `DELETE` | `/api/applications/{id}` | Bearer | Deletes application record |
| `POST` | `/api/applications/{id}/analyze` | Bearer | Triggers AI resume analysis against job requirements |
| `GET` | `/api/applications/{id}/analysis` | Bearer | Retrieves structured AI analysis results |
| `GET` | `/api/applications/{id}/resume` | Bearer | Downloads original applicant resume file |
| `POST` | `/api/applications/{id}/convert-to-candidate` | Bearer | Moves application into Candidate pipeline (`candidate_at`) |
| `GET` | `/api/applications/auto-analyze/available` | Bearer | Counts eligible applications matching auto-analyze filters |
| `POST` | `/api/applications/auto-analyze` | Bearer | Starts asynchronous background auto-analyze batch |
| `GET` | `/api/applications/auto-analyze/{batch_id}` | Bearer | Polls batch progress (processed, failed, remaining) |
| `POST` | `/api/applications/auto-analyze/{batch_id}/cancel` | Bearer | Cancels running auto-analyze batch |
| `GET` | `/api/applications/{id}/comparison` | Bearer | Retrieves relative percentile ranking within job pool |
| `GET` | `/api/applications/jobs/{job_id}/comparisons` | Bearer | Retrieves comparative rankings for all candidates in a job |

### 4. Candidate Portal (`/api/candidate`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/candidate/auth/register` | None | Registers candidate account with email verification |
| `POST` | `/api/candidate/auth/login` | None | Authenticates candidate account |
| `POST` | `/api/candidate/auth/google` | None | Google OAuth login for candidates |
| `POST` | `/api/candidate/auth/verify-email` | None | Verifies candidate email address |
| `POST` | `/api/candidate/auth/refresh` | None | Refreshes candidate access token |
| `POST` | `/api/candidate/auth/logout` | Bearer | Revokes candidate session token |
| `POST` | `/api/candidate/auth/forgot-password` | None | Sends candidate password reset link |
| `POST` | `/api/candidate/auth/reset-password` | None | Resets candidate password |
| `GET` | `/api/candidate/profile` | Bearer | Retrieves candidate profile |
| `PATCH` | `/api/candidate/profile` | Bearer | Updates candidate profile |
| `PATCH` | `/api/candidate/profile/password` | Bearer | Changes candidate password |
| `POST` | `/api/candidate/profile/image` | Bearer | Uploads candidate profile photo |
| `DELETE` | `/api/candidate/profile/image` | Bearer | Deletes candidate profile photo |
| `GET` | `/api/candidate/dashboard` | Bearer | Retrieves dashboard counts and next interview |
| `GET` | `/api/candidate/applications` | Bearer | Lists candidate's submitted applications |
| `GET` | `/api/candidate/applications/{id}` | Bearer | Gets candidate-safe application details & timeline |
| `GET` | `/api/candidate/applications/{id}/resume` | Bearer | Downloads candidate's own submitted resume |
| `GET` | `/api/candidate/interviews` | Bearer | Lists candidate's scheduled interviews |
| `GET` | `/api/candidate/interviews/{id}` | Bearer | Retrieves specific interview details |

### 5. Interviews (`/api/interviews`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/interviews` | Bearer | Lists interviews with status, search, and date filters |
| `GET` | `/api/interviews/stats` | Bearer | Retrieves interview metrics by status |
| `POST` | `/api/interviews` | Bearer | Schedules an interview for a candidate |
| `GET` | `/api/interviews/{id}` | Bearer | Retrieves single interview details |
| `PATCH` | `/api/interviews/{id}` | Bearer | Updates interview status, notes, meeting link, or time |
| `DELETE` | `/api/interviews/{id}` | Bearer | Deletes scheduled interview |

### 6. Dashboard & Analytics (`/api/dashboard`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/dashboard/overview` | Bearer | Hiring pipeline analytics grouped by company/position |
| `GET` | `/api/dashboard/recent-leads` | Bearer | Most recent candidate submissions in caller's scope |
| `GET` | `/api/dashboard/recent-jobs` | Bearer | Most recent job vacancies in caller's scope |
| `GET` | `/api/dashboard/analytics` | Bearer | Comprehensive analytics for 7d, 30d, or 90d periods |

### 7. Universal Data Exports (`/api/exports`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/exports` | Bearer | Generates and streams PDF, XLSX, or DOCX exports of jobs, applications, candidates, or interviews |

### 8. Admin Console (`/api/admin`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/admin/dashboard` | Superuser | Platform KPIs, 30-day trends, and activity overview |
| `GET` | `/api/admin/analytics` | Superuser | Platform analytics over 7d, 30d, 90d, or 12m |
| `GET` | `/api/admin/filters` | Superuser | Filter options for recruiter owners and companies |
| `GET` | `/api/admin/users` | Superuser | Paginated list of registered users with activity stats |
| `GET` | `/api/admin/users/{id}` | Superuser | User details, usage statistics, and recent activity |
| `GET` | `/api/admin/jobs` | Superuser | Platform-wide job listing |
| `GET` | `/api/admin/jobs/{id}` | Superuser | Job details with application breakdown |
| `DELETE` | `/api/admin/jobs/{id}` | Superuser | Moderation delete of a job and its applications |
| `GET` | `/api/admin/applications` | Superuser | Platform-wide application listing |
| `GET` | `/api/admin/candidates` | Superuser | Platform-wide candidate pipeline listing |
| `GET` | `/api/admin/applications/{id}` | Superuser | Application details and stored AI evaluation |
| `GET` | `/api/admin/interviews` | Superuser | Platform-wide scheduled interview directory |
| `GET` | `/api/admin/ai-analysis` | Superuser | AI health metrics, volume, and error categories |
| `GET` | `/api/admin/ai-analysis/runs` | Superuser | Detailed historical AI provider execution logs |
| `GET` | `/api/admin/audit-logs/meta` | Superuser | Available audit action and resource type filters |
| `GET` | `/api/admin/audit-logs` | Superuser | Searchable, immutable platform audit trail |
| `GET` | `/api/admin/system-errors` | Superuser | Log of 5xx server exceptions |
| `GET` | `/api/admin/settings` | Superuser | Runtime settings and configuration presence |
| `PATCH` | `/api/admin/settings` | Superuser | Updates runtime switches (e.g., registration) |
| `GET` | `/api/admin/system-health` | Superuser | Real-time health checks of DB, API, AI, Email, Storage |

### 9. User Administration (`/api/users`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/users` | Superuser | Lists all users with pagination |
| `GET` | `/api/users/{id}` | Superuser | Retrieves user by ID |
| `PUT` | `/api/users/{id}` | Superuser | Updates name, active status, or superuser privileges |
| `DELETE` | `/api/users/{id}` | Superuser | Deletes user and cascades to owned jobs/applications |

### 10. Public Endpoints (`/api/public` & System)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/public/jobs/{job_id}` | None | Public job presentation summary |
| `POST` | `/api/public/apply/{job_id}` | None | Legacy public application submission |
| `GET` | `/api/public/applications/{token}` | None | Gets public application form schema by token |
| `POST` | `/api/public/applications/{token}/submit` | Optional | Submits candidate form answers and resume |
| `POST` | `/api/public/contact` | None | Submits Contact Us inquiry from landing site |
| `GET` | `/health` | None | Basic API liveness probe (`{"status": "ok"}`) |
| `GET` | `/uploads/profile/{filename}` | None | Static file mount for user profile avatars |

---

## Authentication & Security

### Token Lifecycle & Purpose Claims
The platform issues HMAC-SHA256 JWT tokens containing dedicated `typ` purpose claims to enforce cryptographic separation:
- `access`: Standard HR access token (default lifetime: 60 minutes).
- `refresh`: Long-lived single-use refresh token (default lifetime: 7 days).
- `password_reset`: Short-lived single-use password reset token (default lifetime: 30 minutes).
- `candidate_access`: Access token scoped exclusively to the Candidate Portal.
- `candidate_refresh`: Refresh token scoped exclusively to candidate sessions.
- `candidate_password_reset`: Password reset token for candidate accounts.

Neither token type can be used on the other party's endpoints: the HR dependency rejects candidate tokens, and the candidate dependency rejects HR tokens.

### Token Revocation Registry
- **JTI Blacklist (`revoked_tokens`)**: Tokens invalidated by explicit logout are recorded in the database and rejected immediately.
- **Monotonic Session Cutoffs (`session_cutoffs`)**: When a user changes their password, a cutoff timestamp is recorded. All tokens issued before that cutoff timestamp are invalidated instantly.

### Two-Phase Email Verification
New HR and candidate registrations undergo two-phase verification:
1. Registration payload is validated and staged in `pending_registrations` (no active user is created in `users`).
2. A 6-digit OTP code and a secure verification link are dispatched via Resend.
3. Verification (`POST /api/auth/verify-email`) verifies the hash, moves the user into `users`, marks `is_email_verified = True`, and issues session tokens.
4. Resend requests enforce cooldowns (`EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60s`) and hourly limits (`EMAIL_VERIFICATION_MAX_PER_HOUR = 5`).

---

## External Integrations

1. **Google OAuth 2.0**:
   - Enables "Sign in with Google" for both HR recruiters and candidates.
   - Handles Google authorization codes issued via frontend redirects or Google popup flows (`postmessage` redirect URI).
   - Enforces that Google's `email_verified` claim is `true` before linking accounts.
2. **Resend Transactional Email API**:
   - Dispatches email verification codes and password reset links via direct HTTPS calls to `https://api.resend.com/emails`.
   - Uses bounded exponential backoff retries for transient HTTP 429/5xx errors.
   - Development fallback: When `RESEND_API_KEY` is not provided, email links and codes are logged directly to the server console.
3. **AI LLM Providers**:
   - Direct asynchronous HTTP integration with OpenRouter, Groq, Google Gemini, Anthropic, OpenAI, DeepSeek, and custom OpenAI-compatible endpoints.
4. **Telegram Bot** (optional, `backend/app/bot/`, aiogram 3):
   - HR users link Telegram in **Settings → Telegram**, candidates in **Profile → Telegram**. The page issues a single-use deep link (`https://t.me/<bot>?start=<token>`, valid `TELEGRAM_LINK_TOKEN_EXPIRE_MINUTES`); the bot consumes the token from `/start` and stores a `telegram_links` row. Only a SHA-256 digest of the token is kept, and accounts are never matched by phone number or username.
   - Bot commands: `/start`, `/status`, `/applications`, `/new`, `/settings`, `/unlink`, `/help` (private chats only; replies in Uzbek, Russian or English from the Telegram language).
   - Candidate notifications: when an application submitted from a signed-in candidate account is received or its candidate-facing status changes, a `send_telegram` outbox event is written in the same transaction and delivered by `send_telegram_task` on the `notifications` queue. Internal HR moves (e.g. `reviewing -> shortlisted`) send nothing; a blocked bot (HTTP 403) deactivates the link, 429/5xx are retried.
   - `/applications` lists the candidate's applications (5 per page) with the same status wording as the Candidate Portal; each card shows the status, the next interview and the progress timeline. Dates use `TELEGRAM_TIMEZONE` (default `Asia/Tashkent`).
   - HR notifications: an application that arrives through the public apply form or the public apply endpoint notifies the job's owner (only that HR user) with the applicant's name, the job and the time, plus a **Details** button and, on a public host, an **Open in CRM** link. Applications HR enters by hand are not announced.
   - `/new` (HR) lists unreviewed (`new`) applications to the HR user's own jobs, 5 per page; each card shows the applicant's name and email, the HR status (CRM wording) and the AI match score once analysed. The bot always uses the HR workspace scope, also for admins.
   - HR actions: the card has buttons to move the application to Reviewing, Shortlisted, Interview, Hired or Rejected (the current status and withdrawn applications get none). Hiring and rejecting ask for confirmation first. A change goes through the same CRUD call as `PATCH /api/applications/{id}`, so the status history and the candidate's Telegram notification follow, and it is audited as `UPDATE_APPLICATION` with the HR user as actor and `via: telegram`.
   - Interview scheduling: the HR card has a **Schedule interview** button. HR picks a day (the next 7 days), a start time (every 30 minutes from 09:00 to 18:30 in `TELEGRAM_TIMEZONE`, at least 15 minutes ahead) and a duration (30/45/60/90 minutes), then confirms. The interview is created like `POST /api/interviews` with the HR user as interviewer, audited as `CREATE_INTERVIEW` with `via: telegram`, and gets the usual reminders. A meeting link can be added afterwards by sending it as a message (`/cancel` stops waiting). Withdrawn, hired and rejected applications cannot be scheduled, and scheduling does not change the application status.
   - Rescheduling and cancelling: when the application has an upcoming interview, the HR card also shows **Reschedule** (the same day/time/duration pickers, keeping the current length) and **Cancel interview** (asks first). Both go through the same CRUD call as `PATCH /api/interviews/{id}` and are audited as `UPDATE_INTERVIEW` with `via: telegram`. A cancelled interview is kept with status `cancelled`; the application status does not change.
   - Interview changes for candidates: when an interview that is still ahead is scheduled, moved, cancelled (or deleted) or gets a meeting link — from the CRM or from the bot — a linked candidate gets a Telegram message (the new time, the previous one when moved, the duration and the link). Notes, interviewer and duration edits, completed and past interviews send nothing, and the HR user is not told about their own change. A message that went stale before delivery (moved again, reinstated) is dropped. The candidate's **Interviews: changes and reminders** switch in `/settings` covers these messages and the reminders.
   - Setup: create a bot with @BotFather, set `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME` in `backend/.env`, then start the opt-in service with `docker compose --profile telegram up -d`. With the bot disabled the API answers `503` for new links and the candidate card stays hidden.
   - Interview reminders: a Celery beat task (`send_interview_reminders_task`, every 5 minutes) reminds the candidate and the HR user 24 hours and 1 hour before an upcoming interview (an interview booked less than an hour ahead only gets the 1-hour one). `telegram_interview_reminders` remembers what was sent per interview time, so a reminder is never duplicated and moving the interview arms it again; cancelled or moved interviews drop already-queued reminders. A web meeting link is included.
   - `/settings`: each linked account has its own switches (candidate: status changes, reminders; HR: new applications, reminders), stored on `telegram_links` and checked both when a notification is queued and when it is sent.
   - Webhook mode: set `TELEGRAM_WEBHOOK_URL` (public `https://…/telegram/webhook`) and `TELEGRAM_WEBHOOK_SECRET`; the bot then serves updates on port 8081, nginx forwards `/telegram/webhook` to it, and updates without the secret header are rejected. With the URL empty the bot uses long polling.

---

## Environment Variables

### Backend Configuration (`backend/.env`)

| Variable | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `APP_NAME` | string | `Resume Analyzer API` | No | Application display name |
| `DEBUG` | boolean | `false` | No | Enables verbose logging and localhost HTTP for Generic AI |
| `API_PREFIX` | string | `/api` | No | Global URL routing prefix |
| `SECRET_KEY` | string | `change-me-in-production` | **Yes** | Cryptographic key for signing JWT tokens (min 32 chars) |
| `ALGORITHM` | string | `HS256` | No | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `60` | No | Access token expiration duration |
| `REFRESH_TOKEN_EXPIRE_DAYS` | integer | `7` | No | Refresh token expiration duration |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | integer | `30` | No | Expiration for password reset tokens |
| `EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES` | integer | `10` | No | Expiration for 6-digit email OTP codes |
| `EMAIL_VERIFICATION_MAX_ATTEMPTS` | integer | `5` | No | Max invalid OTP attempts before invalidation |
| `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` | integer | `60` | No | Cooldown period between code resend requests |
| `EMAIL_VERIFICATION_MAX_PER_HOUR` | integer | `5` | No | Max verification codes issued per email per hour |
| `FRONTEND_BASE_URL` | string | `http://localhost:5173` | **Yes** | CRM origin used to build absolute email action links |
| `RESEND_API_KEY` | string | `""` | No (Dev) / **Yes** (Prod) | Resend API key; logs to console if empty |
| `EMAIL_FROM` | string | `onboarding@resend.dev` | **Yes** | Sender email address (use verified custom domain in prod) |
| `EMAIL_FROM_NAME` | string | `""` | No | Friendly display name for outgoing emails |
| `EMAIL_REPLY_TO` | string | `""` | No | Reply-To address for outgoing emails |
| `EMAIL_MAX_RETRIES` | integer | `2` | No | Max delivery retry attempts for transient email errors |
| `EMAIL_RETRY_BASE_DELAY` | float | `1.0` | No | Base backoff delay for email retries |
| `EMAIL_MAX_RETRY_WAIT` | float | `10.0` | No | Max retry delay cap for email requests |
| `EMAIL_REQUEST_TIMEOUT` | integer | `10` | No | HTTP timeout (seconds) for Resend API calls |
| `GOOGLE_CLIENT_ID` | string | `""` | Optional | Google OAuth 2.0 Web Client ID |
| `GOOGLE_CLIENT_SECRET` | string | `""` | Optional | Google OAuth 2.0 Client Secret |
| `GOOGLE_REDIRECT_URI` | string | `http://localhost:5173/oauth/callback` | Optional | Authorized redirect URI for Google OAuth |
| `DATABASE_URL` | string | `postgresql://postgres:postgres@localhost:5432/resume_analyzer` | **Yes** | PostgreSQL connection connection URI |
| `DB_AUTO_MIGRATE` | boolean | `true` | No | Automatically applies pending Alembic migrations at startup |
| `BACKEND_CORS_ORIGINS` | string | `http://localhost:5173,http://localhost:5174` | **Yes** | Comma-separated list of allowed browser origins |
| `AI_CREDENTIAL_ENCRYPTION_KEY` | string | `""` | Optional | 32-byte url-safe base64 Fernet key to encrypt user AI keys |
| `REQUIRE_USER_AI_CONFIG` | boolean | `true` | No | When true, recruiters must configure their own AI keys |
| `AI_PROVIDER` | string | `openrouter` | No | Platform fallback AI provider |
| `AI_MODEL` | string | `""` | No | Platform fallback model identifier |
| `AI_API_KEY` | string | `""` | No | Platform fallback AI API key |
| `AI_BASE_URL` | string | `""` | No | Custom base URL for fallback AI provider |
| `AI_MAX_RETRIES` | integer | `3` | No | Max retry attempts for transient AI errors |
| `AI_RETRY_BASE_DELAY` | integer | `2` | No | Base delay for AI exponential backoff |
| `AI_MAX_RETRY_WAIT` | integer | `30` | No | Max single delay cap honored for AI retries |
| `AI_RETRY_BUDGET` | integer | `45` | No | Cumulative timeout budget across all AI retries |
| `AI_REQUEST_TIMEOUT` | integer | `60` | No | HTTP timeout (seconds) for AI requests |
| `AI_HTTP_REFERER` | string | `""` | No | HTTP-Referer header passed for provider attribution |
| `AI_APP_TITLE` | string | `Resume Analyzer` | No | X-Title header passed for provider attribution |
| `OPENROUTER_API_KEY` | string | `""` | Optional | Legacy OpenRouter API key |
| `OPENROUTER_MODEL` | string | `google/gemma-4-26b-a4b-it:free` | No | Legacy OpenRouter model identifier |
| `OPENROUTER_REFERER` | string | `http://localhost:8000` | No | Legacy OpenRouter HTTP-Referer |
| `OPENROUTER_APP_TITLE` | string | `Resume Analyzer` | No | Legacy OpenRouter X-Title |
| `OPENROUTER_MAX_CONTENT_LENGTH` | integer | `50000` | No | Max characters allowed in vacancy text |
| `APPLICATION_RESUME_MAX_CHARS` | integer | `20000` | No | Max resume text characters sent to LLM prompt |
| `UPLOAD_DIR` | string | `uploads` | No | Relative or absolute directory for uploaded files |
| `PROFILE_IMAGE_MAX_SIZE_MB` | integer | `5` | No | Max allowed size for profile picture uploads (MB) |
| `SUPERUSER_EMAIL` | string | `""` | Optional | Email for initial administrator auto-seeding |
| `SUPERUSER_PASSWORD` | string | `""` | Optional | Initial password for seeded administrator (min 8 chars) |
| `SUPERUSER_FULL_NAME` | string | `Administrator` | No | Full name for seeded administrator |

### CRM Frontend Configuration (`crm/.env` or `crm/.env.local`)

| Variable | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | string | `http://localhost:8000/api` | **Yes** | Base URL of the FastAPI backend |
| `VITE_GOOGLE_CLIENT_ID` | string | `""` | Optional | Google OAuth Web Client ID |
| `VITE_GOOGLE_REDIRECT_URI` | string | `http://localhost:5173/oauth/callback` | Optional | Google OAuth callback redirect URL |
| `VITE_LANDING_URL` | string | `http://localhost:5174` | No | Origin of the marketing landing website |
| `VITE_SESSION_COOKIE_DOMAIN` | string | `""` | No | Shared cookie domain for landing session hint (e.g. `.example.com`) |

### Landing Website Configuration (`landing/.env` or `landing/.env.local`)

| Variable | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `VITE_APP_URL` | string | `http://localhost:5173` | **Yes** | Origin of the CRM application |
| `VITE_API_BASE_URL` | string | `http://localhost:8000/api` | **Yes** | Base URL of the FastAPI backend (for Contact form) |
| `VITE_SITE_URL` | string | `""` | No | Canonical public URL used for Open Graph metadata |
| `VITE_CONTACT_EMAIL` | string | `""` | No | Optional contact email address displayed as a `mailto:` link |

---

## Prerequisites

Ensure the following tools are installed on your host system:

- **Python**: Version 3.14 or higher (supports Python 3.12+ as well)
- **Node.js**: Version 20.0.0 or higher
- **Package Manager**: `npm` (version 9 or higher)
- **PostgreSQL**: Version 14 or higher running locally or accessible via network

---

## Installation & Local Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd resume_analyzer
```

### 2. Configure the Backend
```bash
cd backend

# Create and activate a Python virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env
# Open .env and adjust DATABASE_URL, SECRET_KEY, and optional credentials
```

Generate a secure encryption key for `AI_CREDENTIAL_ENCRYPTION_KEY`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Configure the CRM Frontend
```bash
cd ../crm

# Install dependencies
npm install

# Create environment configuration
cp .env.example .env.local
```

### 4. Configure the Landing Website
```bash
cd ../landing

# Install dependencies
npm install

# Create environment configuration
cp .env.example .env.local
```

---

## Running the Applications

### 1. Start the Backend API
```bash
cd backend
source env/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Base URL: `http://localhost:8000/api`
- Interactive Swagger Documentation: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`
- Health Check: `http://localhost:8000/health`

### 2. Start the HR CRM Frontend
In a separate terminal:
```bash
cd crm
npm run dev
```
- CRM Application URL: `http://localhost:5173`

### 3. Start the Landing Website
In a separate terminal:
```bash
cd landing
npm run dev
```
- Landing Page URL: `http://localhost:5174`

---

## Database Migrations

Database migrations are managed using Alembic inside `backend/`.

### Automatic Startup Migrations
By default, `DB_AUTO_MIGRATE=true` is enabled in `backend/.env`. When the FastAPI server starts, it acquires a PostgreSQL advisory lock, checks the schema version against the Alembic head, and applies all pending migrations automatically.

### Manual Migration Commands
If you prefer to run migrations manually:

```bash
cd backend
source env/bin/activate

# Apply all migrations to latest revision
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1

# Inspect current database revision
alembic current

# Generate a new auto-detected migration after model changes
alembic revision --autogenerate -m "describe_schema_changes"
```

---

## Testing & Quality Assurance

### Backend Test Suite (Pytest)
The backend features 960 automated test cases covering authentication, security, AI rate limiting, application forms, candidate portal flows, role authorization, and data exports.

The test suite runs against a dedicated test database (`resume_analyzer_test`) configured in `backend/tests/conftest.py`, ensuring real development data is never altered:

```bash
cd backend
source env/bin/activate

# Run the complete test suite
pytest

# Run tests with short traceback
pytest -q

# Run specific domain test suites
pytest tests/test_security.py
pytest tests/test_services.py
pytest tests/test_auth.py
pytest tests/test_candidate_portal.py
pytest tests/test_ai_provider.py
```

### CRM Frontend Test Suite (Vitest)
The CRM includes 87 tests across 14 test suites covering role selection, URL filter state synchronizers, authentication guards, user dialogs, and candidate portal views:

```bash
cd crm

# Run all frontend tests once
npm run test

# Run tests in watch mode
npm run test:watch
```

---

## Production Build Instructions

### Building the CRM Frontend
```bash
cd crm
npm run build
```
Produces an optimized static bundle in `crm/dist/` ready to be served by Nginx, Caddy, or Cloudflare Pages.

### Building the Landing Website
```bash
cd landing
npm run build
```
Produces an optimized static bundle in `landing/dist/`.

### Production Backend Execution
For production environments, run Uvicorn with multiple worker processes behind a reverse proxy (e.g., Nginx):
```bash
cd backend
source env/bin/activate
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Phase 1 Production Operations & Disaster Recovery

Phase 1 provides an enterprise-grade production foundation with comprehensive operational documentation, backup/disaster recovery tooling, monitoring, container hardening, and automated CI/CD workflows:

- **[Production Deployment Guide](docs/operations/PRODUCTION_DEPLOYMENT.md)**: Host infrastructure prerequisites, environment provisioning, SSL/TLS, database migrations, and zero-downtime rolling update instructions.
- **[Database Backup & Disaster Recovery](docs/operations/DATABASE_BACKUP_AND_RECOVERY.md)**: Automated PostgreSQL logical backups (`-Fc`), cryptographic SHA256 integrity verification, configurable retention policies (7d daily, 4w weekly, 3m monthly), resume storage backups, and verified isolated restoration procedures.
- **[Monitoring & Observability Guide](docs/operations/MONITORING_AND_ALERTING.md)**: Sentry error tracking with PII scrubbing, Prometheus metrics (`/metrics`), Grafana dashboard provisioning, distinct `/health/liveness` vs `/health/readiness` probes, structured JSON logging, and alert rule catalog.
- **[Incident Response Guide](docs/operations/INCIDENT_RESPONSE.md)**: Step-by-step diagnostic and safe recovery playbooks for SEV-1 to SEV-4 incidents (API outages, database outages, Redis broker disconnects, Celery worker stalls, backup failures, disk exhaustion, and external provider issues).
- **[Environment Configuration Reference](docs/operations/ENVIRONMENT_CONFIGURATION.md)**: Complete security-classified audit of all configuration settings across Backend, CRM, and Landing.
- **[Production Readiness Checklist](docs/operations/PRODUCTION_READINESS_CHECKLIST.md)**: Transparent status breakdown of implemented and verified controls vs external setup requirements.

---

## Security Considerations

1. **Secret Keys**: Always generate a high-entropy string of at least 32 characters for `SECRET_KEY`. Running with default keys in non-debug mode logs a prominent startup warning.
2. **Encrypted AI Keys**: Always configure `AI_CREDENTIAL_ENCRYPTION_KEY`. If this key is lost, previously saved user AI API keys cannot be decrypted and must be re-entered.
3. **SSRF Mitigation**: Custom base URLs configured for generic OpenAI-compatible providers are validated against private IP ranges and loopback interfaces. Never disable this validation.
4. **Resend Email Domain**: The default `onboarding@resend.dev` sender is restricted to delivering messages to the account owner's email address. Configure a verified custom domain before deploying to production.
5. **CORS Configuration**: Restrict `BACKEND_CORS_ORIGINS` to the exact production domains of the CRM and Landing frontend deployments.
6. **File Storage Permissions**: Ensure `uploads/` permissions restrict direct script execution. The `/uploads/profile` path only serves static images; resume files in `uploads/resumes/` are served strictly via authenticated API endpoints (`GET /api/applications/{id}/resume`).

---

## Troubleshooting

### Database Connectivity Error (503 Service Unavailable)
- **Symptom**: Requests fail with HTTP 503 and `detail: "The service is temporarily unavailable"`.
- **Cause**: PostgreSQL is stopped, unreachable, or credentials in `DATABASE_URL` are incorrect.
- **Solution**: Ensure PostgreSQL is running (`sudo systemctl status postgresql`) and verify connection credentials using `psql <DATABASE_URL>`.

### AI Analysis Fails with "AI is not set up for your account" (400 Bad Request)
- **Symptom**: Triggering an AI analysis returns HTTP 400.
- **Cause**: `REQUIRE_USER_AI_CONFIG=true` is set, and the HR user has not yet configured their AI provider credentials.
- **Solution**: Navigate to **Settings -> AI Provider** in the CRM, choose an AI provider (e.g. OpenRouter, Groq, or Gemini), enter an API key, select a model, test the connection, and save.

### Email Verification Codes Not Received
- **Symptom**: Registering a new account does not send an email.
- **Cause**: `RESEND_API_KEY` is empty, or `EMAIL_FROM` is using the sandbox sender (`onboarding@resend.dev`) to send to an unverified recipient.
- **Solution**: In local development, check the backend console terminal output where verification codes and links are printed directly. In production, configure a verified Resend domain.

### Google Sign-In Fails or Displays Error Popup
- **Symptom**: Clicking "Sign in with Google" fails or displays an OAuth configuration error.
- **Cause**: `GOOGLE_CLIENT_ID` or redirect URIs are mismatched between `backend/.env`, `crm/.env.local`, and the Google Cloud Console.
- **Solution**: Ensure `VITE_GOOGLE_CLIENT_ID` in `crm/` matches `GOOGLE_CLIENT_ID` in `backend/`, and verify that `http://localhost:5173/oauth/callback` is added to "Authorized redirect URIs" in the Google Cloud Console.

---

## Deployment Status & Known Limitations

- **Containerization**: Full Docker containerization is supported via `backend/Dockerfile` and root `docker-compose.yml` for multi-worker background processing with Celery, Redis, PostgreSQL, and Flower. The application can also run natively on Node.js and Python runtimes for local development.
- **Document Text Extraction**: The zero-dependency PDF parser extracts text from searchable PDF text streams (`Tj`/`TJ`). Scanned, image-only PDFs without an embedded OCR text layer will yield no text; for such files, the analysis engine automatically evaluates the applicant based on submitted form questions.
- **Legacy Word Files (`.doc`)**: Word 97-2003 binary formats are unsupported by the built-in parser. Applicants should upload modern `.docx` or searchable `.pdf` documents.
