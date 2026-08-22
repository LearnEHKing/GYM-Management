"""Run a development command with local environment defaults.

Examples:
    python dev_env.py main.py
    python dev_env.py create_admin.py
    python dev_env.py fake_data.py
    python dev_env.py -m flask --app main db current
    python dev_env.py -m flask --app main db upgrade

Production should provide these variables through its process manager or secret
store instead of using this helper.
"""

import base64
import os
import secrets
import subprocess
import sys


DEFAULTS = {
    "APP_SECRET_KEY": secrets.token_urlsafe(32),
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "12345678",  #will be changed in production
    "DEMO_PASSWORD": "demo12345",
    "DATABASE_URL": "postgresql+psycopg://postgres:12345678@localhost:5432/repvaroDB", #will be changed in production
    "SESSION_COOKIE_SECURE": "false",
    "BACKUP_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
    "GOOGLE_DRIVE_UPLOAD_ENABLED": "false",
    "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON": "",
    "GOOGLE_DRIVE_BACKUP_FOLDER_ID": "",
    "WHATSAPP_ACCESS_TOKEN": "",
    "WHATSAPP_PHONE_NUMBER_ID": "",
    "WHATSAPP_GRAPH_API_VERSION": "v25.0",
    "WHATSAPP_MESSAGE_MODE": "template",
    "WHATSAPP_TEMPLATE_NAME": "",
    "WHATSAPP_TEMPLATE_LANGUAGE": "en_US",
    "WHATSAPP_TIMEOUT_SECONDS": "15",
}


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python dev_env.py <script.py> [args...]")

    environment = os.environ.copy()
    for name, default in DEFAULTS.items():
        environment.setdefault(name, default)

    completed = subprocess.run([sys.executable, *sys.argv[1:]], env=environment)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
