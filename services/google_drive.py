"""Google Drive backup uploads using a service-account credential from the environment."""

import json
import os
from pathlib import Path


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def _enabled():
    return os.environ.get("GOOGLE_DRIVE_UPLOAD_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _settings():
    folder_id = os.environ.get("GOOGLE_DRIVE_BACKUP_FOLDER_ID", "").strip()
    credentials_json = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if not folder_id or not credentials_json:
        raise RuntimeError(
            "GOOGLE_DRIVE_BACKUP_FOLDER_ID and GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON "
            "must be set when Google Drive uploads are enabled."
        )
    try:
        return folder_id, json.loads(credentials_json)
    except json.JSONDecodeError as error:
        raise RuntimeError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON must contain valid JSON.") from error


def upload_backup_bundle(backup_file):
    """Upload the encrypted dump and its integrity sidecars to Google Drive.

    Set GOOGLE_DRIVE_UPLOAD_ENABLED=true only after the destination folder has
    been shared with the service-account email as a Contributor.
    """
    if not _enabled():
        return []
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as error:
        raise RuntimeError(
            "Google Drive uploads require google-api-python-client and google-auth."
        ) from error

    folder_id, credentials_info = _settings()
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=[DRIVE_SCOPE]
    )
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    paths = [
        Path(backup_file),
        Path(backup_file).with_suffix(Path(backup_file).suffix + ".sha256"),
        Path(backup_file).with_suffix(Path(backup_file).suffix + ".json"),
    ]
    uploaded_ids = []
    try:
        for path in paths:
            if not path.is_file():
                raise RuntimeError(f"Backup upload input is missing: {path.name}")
            media = MediaFileUpload(
                str(path), mimetype="application/octet-stream", resumable=True,
                chunksize=5 * 1024 * 1024,
            )
            result = drive.files().create(
                body={"name": path.name, "parents": [folder_id]},
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            uploaded_ids.append(result["id"])
    except Exception as error:
        raise RuntimeError("Google Drive backup upload failed.") from error
    return uploaded_ids
