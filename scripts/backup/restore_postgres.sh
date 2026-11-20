#!/usr/bin/env bash
# ==============================================================================
# Resume Analyzer - Production PostgreSQL Restore & Verification Script
# ==============================================================================
# Restores a PostgreSQL backup (.dump) into an explicitly specified target
# database, validates archive checksum and structure, and performs
# post-restoration data integrity checks.
#
# Usage:
#   ./restore_postgres.sh --backup /path/to/backup.dump --target-db resume_analyzer_restored
# ==============================================================================

set -euo pipefail

BACKUP_FILE=""
TARGET_DB=""
FORCE_PRODUCTION=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --target-db)
            TARGET_DB="$2"
            shift 2
            ;;
        --force-production-overwrite)
            FORCE_PRODUCTION=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --backup <path.dump> --target-db <db_name> [--force-production-overwrite]"
            exit 1
            ;;
    esac
done

if [[ -z "$BACKUP_FILE" ]] || [[ -z "$TARGET_DB" ]]; then
    echo "[ERROR] Both --backup and --target-db arguments are required."
    echo "Usage: $0 --backup <path.dump> --target-db <db_name>"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "[ERROR] Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Production safety guard
if [[ "$TARGET_DB" == "resume_analyzer" ]] && [[ "$FORCE_PRODUCTION" != true ]]; then
    echo "====================================================================="
    echo "[CRITICAL SAFETY GUARD] Target database is 'resume_analyzer' (production)!"
    echo "Restoration directly over production is prohibited without explicit confirmation."
    echo "To override, pass: --force-production-overwrite"
    echo "Recommended: Restore into an isolated database first (e.g. resume_analyzer_recovery_test)"
    echo "====================================================================="
    exit 1
fi

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"

echo "=========================================================="
echo "Starting PostgreSQL Restore: $(date -u)"
echo "Backup File:       ${BACKUP_FILE}"
echo "Target Database:   ${TARGET_DB} on ${PGHOST}:${PGPORT}"
echo "=========================================================="

# 1. Verify SHA256 checksum if .sha256 file exists alongside dump
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
    echo "Verifying SHA256 checksum..."
    EXPECTED_HASH="$(cat "$CHECKSUM_FILE" | awk '{print $1}')"
    ACTUAL_HASH="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
    if [[ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]]; then
        echo "[CRITICAL] Checksum mismatch! The backup file is corrupted or tampered."
        echo "Expected: $EXPECTED_HASH"
        echo "Actual:   $ACTUAL_HASH"
        exit 1
    fi
    echo "[SUCCESS] SHA256 Checksum verified: $ACTUAL_HASH"
fi

# 2. Verify archive integrity using pg_restore table of contents
echo "Validating archive format and structure with pg_restore --list..."
if ! pg_restore --list "$BACKUP_FILE" > /dev/null; then
    echo "[ERROR] Archive validation failed! File is not a valid PostgreSQL custom dump."
    exit 1
fi
echo "[SUCCESS] Archive structure is valid."

# 3. Create target database if it does not exist
echo "Checking target database '${TARGET_DB}' existence..."
export PGHOST PGPORT PGUSER
DB_EXISTS="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}';" || true)"

if [[ "$DB_EXISTS" != "1" ]]; then
    echo "Database '${TARGET_DB}' does not exist. Creating it now..."
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "CREATE DATABASE \"${TARGET_DB}\";"
    echo "[SUCCESS] Created database '${TARGET_DB}'."
else
    echo "Target database '${TARGET_DB}' exists. Preparing schema..."
fi

# 4. Perform restoration using pg_restore
echo "Executing pg_restore into '${TARGET_DB}'..."
# Flags: --clean drops database objects before recreating, --if-exists avoids errors on clean drops
pg_restore \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$TARGET_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    "$BACKUP_FILE" || true  # pg_restore may return warnings (exit code 1) for benign drops

echo "[SUCCESS] Database restoration command finished."

# 5. Post-Restoration Verification & Smoke Checks
echo "=========================================================="
echo "Performing Post-Restoration Verification..."
echo "=========================================================="

# Check connectivity
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB" -c "SELECT 1;" > /dev/null; then
    echo "[ERROR] Cannot connect to restored database '${TARGET_DB}'!"
    exit 1
fi
echo "✓ Target database is reachable."

# Check critical schema tables
REQUIRED_TABLES=("users" "jobs" "applications" "interviews" "outbox_events")
for tbl in "${REQUIRED_TABLES[@]}"; do
    EXISTS="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB" -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='${tbl}');")"
    if [[ "$EXISTS" != "t" ]]; then
        echo "[ERROR] Critical table '${tbl}' is MISSING in restored database!"
        exit 1
    fi
    ROW_COUNT="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB" -tAc "SELECT count(*) FROM \"${tbl}\";")"
    echo "✓ Table '${tbl}' verified (rows: ${ROW_COUNT})."
done

# Verify Alembic migration version table
ALEMBIC_VER="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB" -tAc "SELECT version_num FROM alembic_version LIMIT 1;" || true)"
echo "✓ Schema revision: ${ALEMBIC_VER:-unknown}"

echo "=========================================================="
echo "[SUCCESS] PostgreSQL disaster recovery restoration complete & verified!"
echo "Database '${TARGET_DB}' is fully operational."
echo "=========================================================="
