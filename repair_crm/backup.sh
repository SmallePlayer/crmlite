#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_FILE="$SCRIPT_DIR/repair_crm.db"
BACKUP_DIR="$SCRIPT_DIR/backups"
MAX_BACKUPS=7

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: Database file not found: $DB_FILE"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/repair_crm_${TIMESTAMP}.db"

cp "$DB_FILE" "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"

cd "$BACKUP_DIR"
ls -t repair_crm_*.db 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm --
echo "Old backups cleaned. Remaining: $(ls repair_crm_*.db 2>/dev/null | wc -l)"
