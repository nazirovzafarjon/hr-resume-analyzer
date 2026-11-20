# Production Deployment Guide

## 1. Overview & Architecture

Resume Analyzer is designed for deployment on modern Linux servers (Ubuntu 22.04/24.04 LTS or Debian 12) using Docker and Docker Compose with an edge Nginx reverse proxy.

```
Internet (HTTPS 443 / HTTP 80)
            |
            v
   [ Nginx Reverse Proxy ]
     (Edge SSL Termination & Static Assets)
     |               |               |
     v               v               v
  [ API ]         [ CRM ]        [ Landing ]
 (FastAPI)     (React SPA)     (React Static)
     |
     +------------+------------+
     |                         |
     v                         v
[ PostgreSQL 16 ]        [ Redis 7 (AOF) ]
     ^                         |
     |                         v
     +----------------- [ Celery Workers ]
                          - worker-ai (2 concurrency)
                          - worker-batch (4 concurrency)
                          - worker-notifications (2 concurrency)
                          - worker-exports (2 concurrency)
                          - worker-default (1 concurrency)
                          - celery-beat (outbox recovery scanner)
```

---

## 2. Infrastructure Prerequisites

### Minimum Production Host Requirements
- **CPU:** 4 vCPUs (recommended: 8 vCPUs for heavy concurrent AI resume batching)
- **RAM:** 8 GB RAM (recommended: 16 GB RAM)
- **Storage:** 80 GB SSD/NVMe (PostgreSQL data, Docker images, and resume uploads)
- **Operating System:** Ubuntu 22.04 LTS / 24.04 LTS x86_64
- **Network Ports:**
  - `80/tcp` (HTTP -> Redirected to HTTPS, ACME challenge)
  - `443/tcp` (HTTPS - Public Web Traffic)
  - `22/tcp` (SSH - Restricted to admin IPs / VPN)
  - All internal ports (`5432`, `6379`, `8000`, `5555`) must remain closed to the public internet!

### Installed Host Software
```bash
# Docker Engine and Compose Plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Verify
docker --version
docker compose version
```

---

## 3. Environment & Secrets Provisioning

Create the production environment file on the server at `/opt/resume-analyzer/.env`:

> [!CAUTION]
> Never commit `.env` or production credentials into source control. Generate cryptographically strong random keys for production.

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Generate AI_CREDENTIAL_ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Production `.env` Specification
```ini
# Application
APP_NAME=Resume Analyzer
DEBUG=false
API_PREFIX=/api
LOG_FORMAT=json

# Security Keys
SECRET_KEY=replace_with_48_char_random_token_generated_above
AI_CREDENTIAL_ENCRYPTION_KEY=replace_with_fernet_key_generated_above

# Database Credentials
POSTGRES_USER=app_prod_user
POSTGRES_PASSWORD=replace_with_strong_database_password
POSTGRES_DB=resume_analyzer
DATABASE_URL=postgresql://app_prod_user:replace_with_strong_database_password@postgres:5432/resume_analyzer
DB_AUTO_MIGRATE=false

# Redis & Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# CORS & Base URLs
FRONTEND_BASE_URL=https://app.yourcompany.com
BACKEND_CORS_ORIGINS=https://app.yourcompany.com,https://yourcompany.com

# Email (Resend) - Must use verified custom domain
RESEND_API_KEY=re_prod_xxxxxxxxxxxx
EMAIL_FROM=noreply@yourcompany.com
EMAIL_FROM_NAME=YourCompany Careers
EMAIL_REPLY_TO=support@yourcompany.com

# Super Administrator Seed
SUPERUSER_EMAIL=admin@yourcompany.com
SUPERUSER_PASSWORD=replace_with_strong_admin_password
SUPERUSER_FULL_NAME=Production System Administrator

# Storage & Uploads
UPLOAD_DIR=/app/uploads
PROFILE_IMAGE_MAX_SIZE_MB=5

# Observability
SENTRY_DSN=https://your-key@o000000.ingest.sentry.io/0000000
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=0.1.0
PROMETHEUS_METRICS_ENABLED=true
```

---

## 4. TLS & HTTPS Setup with Certbot

```bash
# Install Certbot
sudo apt-get update && sudo apt-get install -y certbot

# Issue certificates for primary domain and app subdomain
sudo certbot certonly --standalone \
    -d yourcompany.com \
    -d app.yourcompany.com \
    --email admin@yourcompany.com \
    --agree-tos --no-eff-email

# Symlink or mount certificates to docker compose volume:
sudo mkdir -p /var/docker-volumes/certs-data/live
sudo cp -L /etc/letsencrypt/live/yourcompany.com/fullchain.pem /var/docker-volumes/certs-data/live/
sudo cp -L /etc/letsencrypt/live/yourcompany.com/privkey.pem /var/docker-volumes/certs-data/live/
sudo chmod 600 /var/docker-volumes/certs-data/live/*.pem
```

---

## 5. Deployment & Database Initialization

### 5.1 Clone Repository
```bash
sudo git clone https://github.com/your-org/hr-resume-analyzer.git /opt/resume-analyzer
cd /opt/resume-analyzer
```

### 5.2 Build Images
```bash
docker compose -f docker-compose.prod.yml build
```

### 5.3 Database Migration Procedure

> [!IMPORTANT]
> In production, `DB_AUTO_MIGRATE=false` is enforced. Migrations must be run explicitly as a pre-deployment step so failures abort the release before any user-facing containers are updated.

```bash
# 1. Start database and cache first
docker compose -f docker-compose.prod.yml up -d postgres redis

# 2. Wait for healthy status
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U app_prod_user -d resume_analyzer

# 3. Execute Alembic migration
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

### 5.4 Launch Services
```bash
docker compose -f docker-compose.prod.yml up -d
```

### 5.5 Verify Service Health
```bash
# Check Docker container states
docker compose -f docker-compose.prod.yml ps

# Check API health probes
curl -f http://localhost:8000/health/liveness
curl -f http://localhost:8000/health/readiness

# Check edge reverse proxy HTTPS response
curl -I https://app.yourcompany.com/health/liveness
```

---

## 6. Upgrade & Zero-Downtime Rolling Update

```bash
# 1. Pull latest code
cd /opt/resume-analyzer
git pull origin main

# 2. Build updated images
docker compose -f docker-compose.prod.yml build

# 3. Apply any additive database migrations
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 4. Gracefully restart workers (waiting for in-flight tasks to acknowledge)
docker compose -f docker-compose.prod.yml up -d --no-deps worker-ai worker-batch worker-notifications worker-exports worker-default celery-beat

# 5. Update API container
docker compose -f docker-compose.prod.yml up -d --no-deps api

# 6. Update Frontends & Nginx
docker compose -f docker-compose.prod.yml up -d --no-deps crm landing nginx
```

---

## 7. Migration Safety & Rollback Considerations

### Why Database Migrations Cannot Always Be Rolled Back
- Destructive column removals or column renames destroy data that cannot be recovered by running `alembic downgrade`.
- When an updated schema has already recorded new rows from production traffic, running a downgrade can corrupt or reject active records.

### The Expand/Contract Pattern (Mandatory for Production)
1. **Expand (Phase 1):** Add new columns as nullable or with defaults. Code writes to both old and new columns, but reads from old.
2. **Backfill:** Populate new columns in background batches.
3. **Switch:** Code starts reading from new columns.
4. **Contract (Phase 2):** Drop old columns in a subsequent release only after verifying zero remaining dependencies.
