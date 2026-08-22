import hashlib
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.engine import make_url
from models import local_now


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


def _command_timeout():
    try:
        timeout = int(os.environ.get("BACKUP_COMMAND_TIMEOUT_SECONDS", "1800"))
    except ValueError as error:
        raise RuntimeError("BACKUP_COMMAND_TIMEOUT_SECONDS must be a positive integer.") from error
    if timeout <= 0:
        raise RuntimeError("BACKUP_COMMAND_TIMEOUT_SECONDS must be a positive integer.")
    return timeout


def _run(command):
    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True,
            timeout=_command_timeout(),
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"Required PostgreSQL utility is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"{command[0]} failed: {detail[-500:]}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{command[0]} exceeded the backup command timeout.") from error


def _encrypt_file(encryptor, source, destination, chunk_size=4 * 1024 * 1024):
    """Encrypt a dump in independent Fernet chunks without loading it into RAM."""
    with source.open("rb") as input_file, destination.open("wb") as output_file:
        while chunk := input_file.read(chunk_size):
            output_file.write(encryptor.encrypt(chunk))
            output_file.write(b"\n")


def _decrypt_file(encryptor, source, destination):
    """Decrypt both new chunked backups and legacy single-token backups."""
    try:
        with source.open("rb") as input_file, destination.open("wb") as output_file:
            for token in input_file:
                token = token.strip()
                if token:
                    output_file.write(encryptor.decrypt(token))
    except (InvalidToken, TypeError, ValueError, OSError) as error:
        raise RuntimeError(f"Backup decryption failed for {source.name}.") from error


def _sha256_file(path, chunk_size=4 * 1024 * 1024):
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        while chunk := input_file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksum(path):
    digest = _sha256_file(path)
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
    timestamp = local_now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = backup_dir / f"gym_backup_{timestamp}.dump.enc"
    encryptor = _encryption_key()

    with tempfile.TemporaryDirectory() as temporary_dir:
        dump_file = Path(temporary_dir) / "gym.dump"
        _run(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump_file), _database_url()])
        _encrypt_file(encryptor, dump_file, backup_file)

    digest = _write_checksum(backup_file)
    metadata = {
        "created_at": local_now().isoformat(),
        "format": "postgresql-custom-dump",
        "encryption_format": "fernet-chunked-v1",
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
    cutoff = local_now() - timedelta(days=30)
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
    checksum = _sha256_file(backup_file)
    try:
        expected = backup_file.with_suffix(backup_file.suffix + ".sha256").read_text(encoding="ascii").split()[0]
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected.lower()):
            raise ValueError("checksum is not SHA-256")
    except (OSError, IndexError, UnicodeDecodeError, ValueError) as error:
        raise RuntimeError(f"Backup checksum file is invalid for {backup_file.name}.") from error
    if checksum != expected:
        raise RuntimeError(f"Checksum verification failed for {backup_file.name}.")
    with tempfile.TemporaryDirectory() as temporary_dir:
        dump_file = Path(temporary_dir) / "restore-check.dump"
        _decrypt_file(_encryption_key(), backup_file, dump_file)
        _run(["pg_restore", "--clean", "--if-exists", "--exit-on-error", "--no-owner", "--dbname", restore_url, str(dump_file)])
    logger.info("Completed PostgreSQL backup restore drill", extra={"backup": str(backup_file)})
