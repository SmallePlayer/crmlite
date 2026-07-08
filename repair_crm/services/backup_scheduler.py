import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from config import BASE_DIR


class DatabaseBackupScheduler:
    def __init__(self, backup_hour: int = 3, backup_minute: int = 0, max_backups: int = 7):
        self.backup_hour = backup_hour
        self.backup_minute = backup_minute
        self.max_backups = max_backups
        self.backup_dir = BASE_DIR / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = BASE_DIR / "repair_crm.db"
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[BackupScheduler] Started. Daily backup at {self.backup_hour:02d}:{self.backup_minute:02d}")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        print("[BackupScheduler] Stopped")

    def _run(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            next_backup = now.replace(
                hour=self.backup_hour,
                minute=self.backup_minute,
                second=0,
                microsecond=0
            )
            if next_backup <= now:
                next_backup = next_backup.replace(day=next_backup.day + 1)
            
            wait_seconds = (next_backup - now).total_seconds()
            if self._stop_event.wait(timeout=wait_seconds):
                break
            
            self._do_backup()
            
            self._stop_event.wait(timeout=60)

    def _do_backup(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"repair_crm_{timestamp}.db"
            
            source = sqlite3.connect(str(self.db_path))
            dest = sqlite3.connect(str(backup_file))
            source.backup(dest)
            dest.close()
            source.close()
            
            print(f"[BackupScheduler] Backup created: {backup_file}")
            
            self._cleanup_old_backups()
            
        except Exception as e:
            print(f"[BackupScheduler] ERROR: Backup failed: {e}")

    def _cleanup_old_backups(self):
        try:
            backups = sorted(self.backup_dir.glob("repair_crm_*.db"), reverse=True)
            for old_backup in backups[self.max_backups:]:
                old_backup.unlink()
                print(f"[BackupScheduler] Removed old backup: {old_backup}")
        except Exception as e:
            print(f"[BackupScheduler] ERROR: Cleanup failed: {e}")

    def backup_now(self):
        self._do_backup()


backup_scheduler = DatabaseBackupScheduler()
