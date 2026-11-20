# Production Environment Configuration Reference

This document provides a comprehensive audit of all configuration variables across the Backend, CRM, and Landing applications, categorizing them by security classification and production requirements.

---

## 1. Security Classification Legend

- 🔴 **SECRET:** High-risk credentials (passwords, encryption keys, signing secrets). **Must never be logged, committed to source control, or exposed to clients.**
- 🟡 **CONFIDENTIAL:** Internal service URLs, operational parameters, and private addresses.
- 🟢 **PUBLIC:** Client-facing URLs and non-sensitive identifiers safe for frontend code.

---

## 2. Backend Environment Variables (`backend/.env`)

### 2.1 Core Security & Authentication

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `SECRET_KEY` | 🔴 | **Mandatory** | Strong random string (min 32 chars) | Signs JWT access, refresh, and reset tokens. If weak, startup logs a warning. |
| `AI_CREDENTIAL_ENCRYPTION_KEY` | 🔴 | **Mandatory for custom keys** | Fernet 32-byte URL-safe base64 key | Encrypts tenant AI API keys in PostgreSQL. Generate with `cryptography.fernet`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 🟡 | Optional | `60` | JWT bearer token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 🟡 | Optional | `7` | Single-use refresh token rotation lifetime. |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | 🟡 | Optional | `30` | Emailed password-reset link token expiry. |
| `EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES`| 🟡 | Optional | `10` | 6-digit email confirmation code lifetime. |
| `SUPERUSER_EMAIL` | 🟡 | Recommended on init | `admin@yourcompany.com` | Automatically created/promoted to admin on startup if configured. |
| `SUPERUSER_PASSWORD` | 🔴 | **Mandatory if seed set** | Min 8 chars, high entropy | Initial password for the superuser account. |

### 2.2 Database & Background Broker

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `DATABASE_URL` | 🔴 | **Mandatory** | `postgresql://user:pass@postgres:5432/resume_analyzer` | Connection string for SQLAlchemy connection pool. |
| `DB_AUTO_MIGRATE` | 🟡 | **Set `false` in Prod** | `false` | When `false`, migrations must be run explicitly as a pre-deploy gate. |
| `REDIS_URL` | 🟡 | **Mandatory** | `redis://redis:6379/0` | Message broker and caching backend. |
| `CELERY_BROKER_URL` | 🟡 | Optional | Falls back to `REDIS_URL` | Explicit Celery broker override. |
| `CELERY_RESULT_BACKEND` | 🟡 | Optional | `redis://redis:6379/1` | Celery task result persistence backend. |
| `CELERY_TASK_ACKS_LATE` | 🟡 | **True** | `true` | Tasks only acknowledged after completion (prevents loss on crash). |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | 🟡 | **1** | `1` | Disables greedy task prefetching for fair task distribution. |

### 2.3 Network, CORS & URLs

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `BACKEND_CORS_ORIGINS` | 🟡 | **Mandatory** | `https://app.yourcompany.com,https://yourcompany.com` | Comma-separated browser origins permitted to invoke the API. |
| `FRONTEND_BASE_URL` | 🟢 | **Mandatory** | `https://app.yourcompany.com` | Used to construct absolute email confirmation and password reset links. |
| `DEBUG` | 🟡 | **False** | `false` | Must be `false` in production. Disables debug tracebacks in responses. |
| `LOG_FORMAT` | 🟡 | **json** | `json` | Structured single-line JSON log formatting. |

### 2.4 Transactional Email (Resend)

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `RESEND_API_KEY` | 🔴 | **Mandatory** | `re_prod_xxxxxxxxxxxx` | API key from https://resend.com. |
| `EMAIL_FROM` | 🟡 | **Verified Domain** | `noreply@yourcompany.com` | Must belong to a verified domain in Resend with SPF/DKIM configured. |
| `EMAIL_FROM_NAME` | 🟢 | Optional | `Resume Analyzer Careers` | Display name in recipient inboxes. |

### 2.5 Observability

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `SENTRY_DSN` | 🔴 | Optional | `https://key@o0.ingest.sentry.io/0` | Sentry error tracking endpoint. Empty string disables Sentry. |
| `SENTRY_ENVIRONMENT` | 🟡 | Recommended | `production` | Tag for grouping Sentry issues. |
| `PROMETHEUS_METRICS_ENABLED` | 🟡 | Recommended | `true` | Exposes `/metrics` endpoint for Prometheus. |

---

## 3. CRM Frontend Environment Variables (`crm/.env`)

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | 🟢 | **Mandatory** | `https://app.yourcompany.com/api` | Base URL of the API. |
| `VITE_GOOGLE_CLIENT_ID` | 🟢 | Optional | `52314646701-xxxx.apps.googleusercontent.com` | Google OAuth Client ID for web clients. |
| `VITE_GOOGLE_REDIRECT_URI` | 🟢 | Optional | `https://app.yourcompany.com/oauth/callback` | Callback URL matching Google Cloud Console. |
| `VITE_LANDING_URL` | 🟢 | Optional | `https://yourcompany.com` | Link back to the public landing page. |
| `VITE_SENTRY_DSN` | 🟢 | Optional | `https://key@o0.ingest.sentry.io/1` | Sentry DSN for frontend browser error reporting. |

---

## 4. Landing Frontend Environment Variables (`landing/.env`)

| Variable | Class | Production Requirement | Default / Example | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `VITE_APP_URL` | 🟢 | **Mandatory** | `https://app.yourcompany.com` | Destination URL for "Log in" and "Get started" buttons. |
| `VITE_API_BASE_URL` | 🟢 | **Mandatory** | `https://app.yourcompany.com/api` | API endpoint for public contact inquiries. |
| `VITE_SITE_URL` | 🟢 | Recommended | `https://yourcompany.com` | Canonical OpenGraph / SEO root URL. |
