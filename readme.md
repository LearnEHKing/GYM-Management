# GYM management system

## Development setup

Install the Python dependencies from `requirements.txt`, then set the sensitive
values before starting the app:

```powershell
$env:APP_SECRET_KEY = "a-long-random-production-secret"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "use-a-secret-manager-value"
python main.py
```

For development, use the helper to launch a command with local defaults:

```powershell
python dev_env.py main.py
python dev_env.py create_admin.py
python dev_env.py fake_data.py
```

The helper sets variables only for the child process. Production must provide
`APP_SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` from the deployment
environment or a secret manager. `DEMO_PASSWORD` is required only when running
`fake_data.py`.

The application uses SQLite at `instance/gym.db`, creates missing tables, and
applies the small compatibility migrations at startup.

Backups are SQLite files written to `backups/`.
