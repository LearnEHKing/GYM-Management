from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

def create_backup():
    DB_FILE = Path("instance/gym.db")   # Change this if needed
    BACKUP_DIR = Path("backups")
    
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # --------------------------
    # Create backup
    # --------------------------
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = BACKUP_DIR / f"gym_backup_{timestamp}.db"
    
    with sqlite3.connect(DB_FILE) as source:
        with sqlite3.connect(backup_file) as destination:
            source.backup(destination)
    
    print(f"Created backup: {backup_file}")
    
    # --------------------------
    # Cleanup old backups
    # --------------------------
    cutoff = datetime.now() - timedelta(days=30)
    
    backups = sorted(
        BACKUP_DIR.glob("gym_backup_*.db"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    
    monthly_kept = set()
    
    for backup in backups:
        modified = datetime.fromtimestamp(backup.stat().st_mtime)
    
        # Keep all backups from last 30 days
        if modified >= cutoff:
            continue
    
        month_key = (modified.year, modified.month)
    
        # Keep only the newest backup of each older month
        if month_key not in monthly_kept:
            monthly_kept.add(month_key)
        else:
            backup.unlink()
            print(f"Deleted: {backup.name}")