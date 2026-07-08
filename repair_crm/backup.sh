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

cd "$SCRIPT_DIR"
python3 -c "
import sqlite3
import sys

try:
    source = sqlite3.connect('repair_crm.db')
    dest = sqlite3.connect('$BACKUP_FILE')
    source.backup(dest)
    dest.close()
    source.close()
    print('Backup created safely using SQLite backup API: $BACKUP_FILE')
except Exception as e:
    print(f'ERROR: Backup failed: {e}', file=sys.stderr)
    sys.exit(1)
"

cd "$BACKUP_DIR"
ls -t repair_crm_*.db 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm --
echo "Old backups cleaned. Remaining: $(ls repair_crm_*.db 2>/dev/null | wc -l)"
