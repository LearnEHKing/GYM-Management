# GYM management system

## PostgreSQL setup

Install the Python dependencies from `requirements.txt`, install the PostgreSQL
client tools so `pg_dump` is available, then set all required variables before
starting the app:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/gym_management"
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
`APP_SECRET_KEY`, `DATABASE_URL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` from
the deployment environment or a secret manager. `DEMO_PASSWORD` is required
only when running `fake_data.py`.

The application creates missing tables and applies the small compatibility
migrations at startup. Existing SQLite databases are not read automatically;
export them with a migration tool before switching the connection string.

Backups are PostgreSQL custom-format files written to `backups/` and can be
restored with `pg_restore`.
