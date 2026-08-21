"""Run a development command with local environment defaults.

Examples:
    python dev_env.py main.py
    python dev_env.py create_admin.py
    python dev_env.py fake_data.py

Production should provide these variables through its process manager or secret
store instead of using this helper.
"""

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