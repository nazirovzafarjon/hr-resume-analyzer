#!/usr/bin/env bash
# ==============================================================================
# Resume Analyzer - Upload Storage Backup Script
# ==============================================================================
# Archives persistent uploaded candidate resumes and profiles, generates
# cryptographic SHA256 checksums, and applies a configurable retention policy.
# ==============================================================================

set -euo pipefail

UPLOAD_DIR="${UPLOAD_DIR:-uploads}"
BACKUP_DIR="${BACKUP_DIR:-/backups/uploads}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [[ ! -d "$UPLOAD_DIR" ]]; then
    echo "[WARNING] Upload directory '${UPLOAD_DIR}' does not exist. Creating empty directory."
    mkdir -p "$UPLOAD_DIR"
fi

TIMESTAMP="$(date -u +"%Y%m%d_%H%M%S")"
ARCHIVE_NAME="uploads_backup_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"
CHECKSUM_PATH="${ARCHIVE_PATH}.sha256"

echo "=========================================================="
echo "Starting Upload Storage Backup: $(date -u)"
echo "Source Directory: ${UPLOAD_DIR}"
echo "Destination:      ${ARCHIVE_PATH}"
echo "=========================================================="

# Create compressed tarball
tar -czf "$ARCHIVE_PATH" -C "$(dirname "$UPLOAD_DIR")" "$(basename "$UPLOAD_DIR")"
chmod 600 "$ARCHIVE_PATH"

ARCHIVE_SIZE="$(du -h "$ARCHIVE_PATH" | cut -f1)"
echo "[SUCCESS] Uploads archive created (${ARCHIVE_SIZE})"

# Generate SHA256 checksum
echo "Generating SHA256 checksum..."
sha256sum "$ARCHIVE_PATH" | awk '{print $1}' > "$CHECKSUM_PATH"
chmod 600 "$CHECKSUM_PATH"
echo "[SUCCESS] SHA256: $(cat "$CHECKSUM_PATH")"

# Apply retention policy
TOTAL_BACKUPS="$(find "$BACKUP_DIR" -maxdepth 1 -name "uploads_backup_*.tar.gz" | wc -l)"
if [[ "$TOTAL_BACKUPS" -gt 1 ]]; then
    echo "Enforcing upload backup retention (Days: ${RETENTION_DAYS})..."
    find "$BACKUP_DIR" -maxdepth 1 -name "uploads_backup_*.tar.gz" -mtime +"$RETENTION_DAYS" -exec rm -f {} \;
    find "$BACKUP_DIR" -maxdepth 1 -name "uploads_backup_*.tar.gz.sha256" -mtime +"$RETENTION_DAYS" -exec rm -f {} \;
    echo "[SUCCESS] Uploads retention complete."
else
    echo "Single existing upload archive; retention pruning skipped for data safety."
fi

echo "=========================================================="
echo "Upload storage backup finished at: $(date -u)"
echo "Archive File: ${ARCHIVE_PATH}"
echo "=========================================================="
