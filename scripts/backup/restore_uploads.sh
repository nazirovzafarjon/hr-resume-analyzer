#!/usr/bin/env bash
# ==============================================================================
# Resume Analyzer - Upload Storage Restore Script
# ==============================================================================
# Restores uploaded candidate resumes and profiles from a backup archive (.tar.gz)
# after verifying its cryptographic checksum.
#
# Usage:
#   ./restore_uploads.sh --archive /path/to/uploads_backup.tar.gz --target-dir uploads
# ==============================================================================

set -euo pipefail

ARCHIVE_PATH=""
TARGET_DIR="${UPLOAD_DIR:-uploads}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --archive)
            ARCHIVE_PATH="$2"
            shift 2
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --archive <archive.tar.gz> [--target-dir <uploads_dir>]"
            exit 1
            ;;
    esac
done

if [[ -z "$ARCHIVE_PATH" ]]; then
    echo "[ERROR] Missing required --archive argument."
    echo "Usage: $0 --archive <archive.tar.gz> [--target-dir <uploads_dir>]"
    exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
    echo "[ERROR] Archive file not found: $ARCHIVE_PATH"
    exit 1
fi

echo "=========================================================="
echo "Starting Upload Storage Restore: $(date -u)"
echo "Archive File:     ${ARCHIVE_PATH}"
echo "Target Directory: ${TARGET_DIR}"
echo "=========================================================="

# Verify checksum if present
CHECKSUM_FILE="${ARCHIVE_PATH}.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
    echo "Verifying SHA256 checksum..."
    EXPECTED_HASH="$(cat "$CHECKSUM_FILE" | awk '{print $1}')"
    ACTUAL_HASH="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
    if [[ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]]; then
        echo "[CRITICAL] Checksum mismatch! Archive is corrupted."
        exit 1
    fi
    echo "[SUCCESS] SHA256 Checksum verified: $ACTUAL_HASH"
fi

# Create target directory
mkdir -p "$TARGET_DIR"

# Extract archive
echo "Extracting archive to ${TARGET_DIR}..."
tar -xzf "$ARCHIVE_PATH" -C "$(dirname "$TARGET_DIR")"

echo "=========================================================="
echo "[SUCCESS] Upload storage restored successfully at: $(date -u)"
echo "Target Directory: ${TARGET_DIR}"
echo "=========================================================="
