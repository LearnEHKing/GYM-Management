import hashlib
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url


logger = logging.getLogger(__name__)


def _database_url():
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL must be set before creating a backup.")
    url = make_url(value)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Backups require a PostgreSQL DATABASE_URL.")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _encryption_key():
    value = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
    if not value:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY must be set for encrypted backups.")
    try:
        return Fernet(value.encode())
    except (ValueError, TypeError) as error:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY must be a valid Fernet key.") from error


def _run(command):
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError(f"Required PostgreSQL utility is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"{command[0]} failed: {detail[-500:]}") from error


def _write_checksum(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="ascii"
    )
    return digest


def _check_storage(backup_dir):
    limit = int(os.environ.get("BACKUP_MAX_STORAGE_BYTES", "0"))
    if limit <= 0:
        return
    used = sum(path.stat().st_size for path in backup_dir.glob("*") if path.is_file())
    if used > limit:
        raise RuntimeError("Backup storage limit exceeded; cleanup or expand storage before continuing.")


def create_backup():
    backup_dir = Path(os.environ.get("BACKUP_DIR", Path(__file__).resolve().parent / "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = backup_dir / f"gym_backup_{timestamp}.dump.enc"
    encryptor = _encryption_key()

    with tempfile.TemporaryDirectory() as temporary_dir:
        dump_file = Path(temporary_dir) / "gym.dump"
        _run(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump_file), _database_url()])
        backup_file.write_bytes(encryptor.encrypt(dump_file.read_bytes()))

    digest = _write_checksum(backup_file)
    metadata = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "format": "postgresql-custom-dump",
        "encrypted": True,
        "sha256": digest,
        "size_bytes": backup_file.stat().st_size,
    }
    backup_file.with_suffix(backup_file.suffix + ".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    _cleanup_old_backups(backup_dir)
    _check_storage(backup_dir)
    logger.info("Created encrypted PostgreSQL backup", extra={"backup": str(backup_file), "sha256": digest})
    return backup_file


def _cleanup_old_backups(backup_dir):
    cutoff = datetime.utcnow() - timedelta(days=30)
    backups = sorted(backup_dir.glob("gym_backup_*.dump.enc"), key=lambda path: path.stat().st_mtime, reverse=True)
    monthly_kept = set()
    for backup in backups:
        modified = datetime.utcfromtimestamp(backup.stat().st_mtime)
        if modified >= cutoff:
            continue
        month_key = (modified.year, modified.month)
        if month_key in monthly_kept:
            for companion in (backup, backup.with_suffix(backup.suffix + ".sha256"), backup.with_suffix(backup.suffix + ".json")):
                companion.unlink(missing_ok=True)
        else:
            monthly_kept.add(month_key)


def restore_drill():
    """Restore the newest backup into the isolated restore database."""
    restore_url = os.environ.get("BACKUP_RESTORE_DATABASE_URL", "").strip()
    if not restore_url:
        raise RuntimeError("BACKUP_RESTORE_DATABASE_URL must be set for restore drills.")
    backup_dir = Path(os.environ.get("BACKUP_DIR", Path(__file__).resolve().parent / "backups"))
    backups = sorted(backup_dir.glob("gym_backup_*.dump.enc"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not backups:
        raise RuntimeError("No encrypted backup is available for the restore drill.")
    backup_file = backups[0]
    checksum = hashlib.sha256(backup_file.read_bytes()).hexdigest()
    expected = backup_file.with_suffix(backup_file.suffix + ".sha256").read_text(encoding="ascii").split()[0]
    if checksum != expected:
        raise RuntimeError(f"Checksum verification failed for {backup_file.name}.")
    with tempfile.TemporaryDirectory() as temporary_dir:
        dump_file = Path(temporary_dir) / "restore-check.dump"
        dump_file.write_bytes(_encryption_key().decrypt(backup_file.read_bytes()))
        _run(["pg_restore", "--clean", "--if-exists", "--exit-on-error", "--no-owner", "--dbname", restore_url, str(dump_file)])
    logger.info("Completed PostgreSQL backup restore drill", extra={"backup": str(backup_file)})
