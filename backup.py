import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

def create_backup():
    project_dir = Path(__file__).resolve().parent
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to create a PostgreSQL backup.")

    backup_dir = project_dir / "backups"
    backup_dir.mkdir(exist_ok=True)

    pg_dump_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    
    # --------------------------
    # Create backup
    # --------------------------
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = backup_dir / f"gym_backup_{timestamp}.dump"
    subprocess.run(
        ["pg_dump", "--format=custom", "--file", str(backup_file), pg_dump_url],
        check=True,
    )
    
    print(f"Created backup: {backup_file}")
    
    # --------------------------
    # Cleanup old backups
    # --------------------------
    cutoff = datetime.now() - timedelta(days=30)
    
    backups = sorted(
        backup_dir.glob("gym_backup_*.dump"),
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
