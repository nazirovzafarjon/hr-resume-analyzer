# Production Incident Response Guide

## Incident Severity Matrix

| Severity | Definition | Response Target | Example |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Core service completely unavailable; data loss risk | < 15 minutes | PostgreSQL down, API returning 5xx to all users |
| **SEV-2 (High)** | Major feature unavailable with no workaround | < 1 hour | Celery workers crashed; AI resume evaluations stalled |
| **SEV-3 (Medium)** | Degraded service or external provider failure | < 4 hours | Resend email outage; non-critical export timeout |
| **SEV-4 (Low)** | Minor bug or cosmetic issue | Next business day | Single user report visual glitch |

---

## Playbook 1: API Outage (502 / 503 / 500 Spike)

### Symptoms
- Nginx returning HTTP 502 Bad Gateway.
- Uptime robot / Prometheus alert `APIInstanceDown` or `HighHTTP5xxErrorRate`.
- Users report connection timeouts.

### Diagnostic Steps
```bash
# 1. Check container status
docker compose -f docker-compose.prod.yml ps api

# 2. Inspect latest API container logs
docker compose -f docker-compose.prod.yml logs --tail 100 api

# 3. Check memory & CPU utilization
docker stats --no-stream resume-analyzer-api

# 4. Check readiness probe
curl -v http://localhost:8000/health/readiness
```

### Safe Recovery Steps
```bash
# If container exited with OOM (exit code 137) or crashed:
docker compose -f docker-compose.prod.yml restart api

# If database connectivity failed:
docker compose -f docker-compose.prod.yml restart postgres
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres -d resume_analyzer
```

### Verification Steps
```bash
# Confirm readiness returns HTTP 200
curl -s http://localhost:8000/health/readiness | jq .
```

---

## Playbook 2: PostgreSQL Database Outage

### Symptoms
- API logs show `SQLAlchemyError` or `OperationalError: could not connect to server`.
- Readiness probe returns 503 with `"checks": {"database": "unhealthy"}`.

### Diagnostic Steps
```bash
# 1. Check PostgreSQL container status and exit code
docker compose -f docker-compose.prod.yml ps postgres

# 2. View PostgreSQL error logs
docker compose -f docker-compose.prod.yml logs --tail 100 postgres

# 3. Check host disk space
df -h
```

### Safe Recovery Steps
```bash
# 1. Check if database volume disk is full
# If disk is 100% full, free up disk space first before restarting PostgreSQL (see Playbook 7)

# 2. Restart container safely
docker compose -f docker-compose.prod.yml restart postgres

# 3. Verify PostgreSQL is accepting connections
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres -d resume_analyzer
```

### Verification Steps
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d resume_analyzer -c "SELECT count(*) FROM users;"
```

---

## Playbook 3: Redis Broker Outage

### Symptoms
- Celery workers logging `kombu.exceptions.OperationalError: Error while reading from socket`.
- API asynchronous dispatch fails or hangs.
- Readiness check reports `"broker": "unhealthy"`.

### Diagnostic Steps
```bash
docker compose -f docker-compose.prod.yml ps redis
docker compose -f docker-compose.prod.yml logs --tail 100 redis
```

### Safe Recovery Steps
```bash
# 1. Ping Redis directly
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# 2. If unresponsive, restart Redis container
docker compose -f docker-compose.prod.yml restart redis

# 3. Restart Celery workers so connections re-establish cleanly
docker compose -f docker-compose.prod.yml restart worker-ai worker-batch worker-notifications worker-exports worker-default
```

### Verification Steps
```bash
# Run Celery broker health check from backend
docker compose -f docker-compose.prod.yml exec api python -c "from app.core.celery_app import check_celery_broker_health; print(check_celery_broker_health())"
```

---

## Playbook 4: Celery Workers Stalled or Outbox Backlog

### Symptoms
- Resumes uploaded by candidates remain in "Queued" or "Processing" indefinitely.
- Flower dashboard shows 0 active workers or high queue depth.
- `outbox_events` table contains growing rows with `status = 'pending'`.

### Diagnostic Steps
```bash
# 1. Inspect worker states via Celery inspect ping
docker compose -f docker-compose.prod.yml exec api celery -A app.core.celery_app inspect ping

# 2. Check pending outbox events in PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d resume_analyzer -c \
  "SELECT status, count(*) FROM outbox_events GROUP BY status;"

# 3. Check Flower task dashboard
# Open http://<server-ip>:5555
```

### Safe Recovery Steps
```bash
# 1. Restart Celery beat (the scheduler and outbox recovery runner)
docker compose -f docker-compose.prod.yml restart celery-beat

# 2. Restart workers with graceful timeout (60s)
docker compose -f docker-compose.prod.yml restart worker-ai worker-batch worker-notifications worker-exports worker-default

# 3. Trigger manual outbox recovery sweep
docker compose -f docker-compose.prod.yml exec api python -c \
  "from app.core.database import SessionLocal; from app.services.outbox import process_pending_outbox_events; db = SessionLocal(); print('Recovered events:', process_pending_outbox_events(db, limit=100)); db.close()"
```

### Verification Steps
```bash
# Verify pending outbox count drops towards 0
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d resume_analyzer -c \
  "SELECT count(*) FROM outbox_events WHERE status='pending';"
```

---

## Playbook 5: Failed Database Backups

### Symptoms
- Backup cron job sends alert or returns non-zero exit code.
- Latest `.dump` file in `/backups/postgres` is older than 25 hours.

### Diagnostic Steps
```bash
# 1. Check disk space on the backup volume
df -h /backups

# 2. Inspect latest backup script log
tail -n 100 /var/log/resume_analyzer_backup.log

# 3. Check PostgreSQL dump permissions
ls -ld /backups/postgres
```

### Safe Recovery Steps
```bash
# 1. Execute manual backup run to test failure cause
./scripts/backup/backup_postgres.sh

# 2. If pg_dump failed due to locks or query timeout, check active transactions
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d resume_analyzer -c \
  "SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;"
```

### Verification Steps
```bash
# Verify new dump and sha256 checksum exists
ls -lht /backups/postgres | head -n 5
sha256sum -c $(ls -t /backups/postgres/*.dump.sha256 | head -1)
```

---

## Playbook 6: Host Disk Space Exhaustion

### Symptoms
- Docker reports `No space left on device`.
- PostgreSQL shuts down in read-only panic.
- Celery tasks fail with `IOError` during file parsing.

### Diagnostic Steps
```bash
# 1. Find disk consumption by mount
df -h

# 2. Find large Docker directories
docker system df
du -sh /var/lib/docker/*
du -sh /app/uploads/* /backups/*
```

### Safe Recovery Steps
```bash
# 1. Prune dangling Docker images, build caches, and stopped containers (NEVER remove named volumes!)
docker system prune -f

# 2. Clean temporary files in upload folder
find /app/uploads -type f -name ".health_probe_tmp*" -delete

# 3. Compress older log files in /var/log/
journalctl --vacuum-time=3d
```

### Verification Steps
```bash
# Ensure root and volume filesystems have at least 15% free headroom
df -h
```

---

## Playbook 7: External AI Provider Outage

### Symptoms
- Resume evaluations fail or return `AIProviderError`.
- Sentry alerts indicate HTTP 429 Too Many Requests or 503 Provider Unavailable.
- Latency on AI analysis spikes beyond 45 seconds.

### Diagnostic Steps
```bash
# 1. Check configured AI provider status page (OpenRouter, Groq, Gemini)
# 2. Inspect backend AI error logs
docker compose -f docker-compose.prod.yml logs --tail 50 worker-ai
```

### Safe Recovery Steps
```bash
# 1. If provider is experiencing a sustained outage:
# Temporarily switch AI_PROVIDER in .env to a standby provider (e.g., from openrouter to groq or gemini)
# Example:
#   AI_PROVIDER=groq
#   AI_MODEL=llama-3.3-70b-versatile
#   AI_API_KEY=gsk_xxxxxxxxxxxx

# 2. Restart worker-ai container
docker compose -f docker-compose.prod.yml up -d --no-deps worker-ai
```

### Verification Steps
```bash
# Test single application analysis from admin or via Celery task
```

---

## Playbook 8: Transactional Email Provider Failure (Resend)

### Symptoms
- Candidate verification codes or HR password reset links are not received.
- Worker logs report `HTTP 403 (sandbox sender)` or `HTTP 429 rate limit`.

### Diagnostic Steps
```bash
docker compose -f docker-compose.prod.yml logs --tail 50 worker-notifications
```

### Safe Recovery Steps
```bash
# 1. If EMAIL_FROM still uses onboarding@resend.dev:
# Verify a custom domain in Resend Dashboard and update EMAIL_FROM to an authorized domain address.

# 2. If RESEND_API_KEY was revoked or reached quota:
# Generate a new API key in Resend and update RESEND_API_KEY in .env

# 3. Restart notification worker
docker compose -f docker-compose.prod.yml up -d --no-deps worker-notifications
```

### Verification Steps
```bash
# Request password reset code from login page and confirm receipt in inbox
```
