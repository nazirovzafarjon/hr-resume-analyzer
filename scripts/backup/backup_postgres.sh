#!/usr/bin/env bash
# ==============================================================================
# Resume Analyzer - Production PostgreSQL Backup Script
# ==============================================================================
# Performs transactional logical backups using pg_dump custom format (-Fc),
# validates archive integrity, generates SHA256 checksums, and applies a
# configurable retention policy.
# ==============================================================================

set -euo pipefail

# Configuration with sensible defaults
BACKUP_DIR="${BACKUP_DIR:-/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"
RETENTION_MONTHS="${RETENTION_MONTHS:-3}"

# Parse DB connection from DATABASE_URL if individual PG* variables are not set
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-resume_analyzer}"

if [[ -n "${DATABASE_URL:-}" ]]; then
    # Format: postgresql://user:password@host:port/dbname
    PROTO="$(echo "$DATABASE_URL" | grep :// | sed -e's,^\(.*://\).*,\1,g')"
    URL_WITHOUT_PROTO="${DATABASE_URL#"$PROTO"}"
    USERPASS="$(echo "$URL_WITHOUT_PROTO" | grep @ | cut -d@ -f1 || true)"
    HOSTPORT_DB="$(echo "$URL_WITHOUT_PROTO" | sed -e "s,^$USERPASS@,,")"
    HOSTPORT="$(echo "$HOSTPORT_DB" | cut -d/ -f1)"
    
    if [[ -n "$USERPASS" ]]; then
        PGUSER="$(echo "$USERPASS" | cut -d: -f1)"
        if [[ "$USERPASS" == *:* ]]; then
            export PGPASSWORD="$(echo "$USERPASS" | cut -d: -f2)"
        fi
    fi
    if [[ "$HOSTPORT" == *:* ]]; then
        PGHOST="$(echo "$HOSTPORT" | cut -d: -f1)"
        PGPORT="$(echo "$HOSTPORT" | cut -d: -f2)"
    else
        PGHOST="$HOSTPORT"
    fi
    PGDATABASE="$(echo "$HOSTPORT_DB" | cut -d/ -f2 | cut -d? -f1)"
fi

TIMESTAMP="$(date -u +"%Y%m%d_%H%M%S")"
BACKUP_FILENAME="${PGDATABASE}_backup_${TIMESTAMP}.dump"
BACKUP_FILEPATH="${BACKUP_DIR}/${BACKUP_FILENAME}"
CHECKSUM_FILEPATH="${BACKUP_FILEPATH}.sha256"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

echo "=========================================================="
echo "Starting PostgreSQL backup: $(date -u)"
echo "Target Database: ${PGDATABASE} on ${PGHOST}:${PGPORT}"
echo "Output File:     ${BACKUP_FILEPATH}"
echo "=========================================================="

# 1. Execute pg_dump with custom format, compression, and blob inclusion
export PGHOST PGPORT PGUSER PGDATABASE
pg_dump \
    --format=custom \
    --compress=6 \
    --blobs \
    --no-owner \
    --no-privileges \
    --file="$BACKUP_FILEPATH"

chmod 600 "$BACKUP_FILEPATH"
BACKUP_SIZE="$(du -h "$BACKUP_FILEPATH" | cut -f1)"
echo "[SUCCESS] Dump created successfully (${BACKUP_SIZE})"

# 2. Verify archive integrity using pg_restore table-of-contents list
echo "Verifying archive integrity with pg_restore --list..."
if ! pg_restore --list "$BACKUP_FILEPATH" > /dev/null; then
    echo "[ERROR] Backup integrity verification FAILED! Removing corrupted file."
    rm -f "$BACKUP_FILEPATH"
    exit 1
fi
echo "[SUCCESS] Archive integrity verified (valid PostgreSQL custom format)."

# 3. Generate SHA256 checksum for cryptographic verification
echo "Generating SHA256 checksum..."
sha256sum "$BACKUP_FILEPATH" | awk '{print $1}' > "$CHECKSUM_FILEPATH"
chmod 600 "$CHECKSUM_FILEPATH"
echo "[SUCCESS] SHA256: $(cat "$CHECKSUM_FILEPATH")"

# 4. Optional Encryption (if BACKUP_ENCRYPTION_PASSPHRASE is provided)
if [[ -n "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]]; then
    echo "Encrypting backup with OpenSSL AES-256-CBC..."
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -in "$BACKUP_FILEPATH" \
        -out "${BACKUP_FILEPATH}.enc" \
        -pass env:BACKUP_ENCRYPTION_PASSPHRASE
    chmod 600 "${BACKUP_FILEPATH}.enc"
    sha256sum "${BACKUP_FILEPATH}.enc" | awk '{print $1}' > "${BACKUP_FILEPATH}.enc.sha256"
    echo "[SUCCESS] Encrypted backup created: ${BACKUP_FILEPATH}.enc"
fi

# 5. Apply Retention Policy
# Rule: Never delete old backups if total valid backups <= 1
TOTAL_BACKUPS="$(find "$BACKUP_DIR" -maxdepth 1 -name "${PGDATABASE}_backup_*.dump" | wc -l)"
if [[ "$TOTAL_BACKUPS" -gt 1 ]]; then
    echo "Enforcing backup retention policy (Days: ${RETENTION_DAYS})..."
    find "$BACKUP_DIR" -maxdepth 1 -name "${PGDATABASE}_backup_*.dump" -mtime +"$RETENTION_DAYS" -exec rm -f {} \;
    find "$BACKUP_DIR" -maxdepth 1 -name "${PGDATABASE}_backup_*.dump.sha256" -mtime +"$RETENTION_DAYS" -exec rm -f {} \;
    find "$BACKUP_DIR" -maxdepth 1 -name "${PGDATABASE}_backup_*.dump.enc*" -mtime +"$RETENTION_DAYS" -exec rm -f {} \;
    echo "[SUCCESS] Retention pruning complete."
else
    echo "Single existing backup detected; retention pruning skipped for data safety."
fi

echo "=========================================================="
echo "PostgreSQL backup successfully completed at: $(date -u)"
echo "Backup File: ${BACKUP_FILEPATH}"
echo "=========================================================="
