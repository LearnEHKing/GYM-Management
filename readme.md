# GYM management system

## Development setup

Install the Python dependencies from `requirements.txt`, then set the sensitive
values before starting the app:

```powershell
$env:APP_SECRET_KEY = "a-long-random-production-secret"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "use-a-secret-manager-value"
$env:DATABASE_URL = "postgresql+psycopg://user:password@db-host/gym"
$env:TRUSTED_PROXY_HOPS = "1"
$env:BACKUP_ENCRYPTION_KEY = "generate-a-Fernet-key-and-store-it-in-a-secret-manager"
$env:BACKUP_RESTORE_DATABASE_URL = "postgresql://restore_user:password@restore-db/gym_restore"
$env:BACKUP_MAX_STORAGE_BYTES = "10737418240"
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

The application reads `DATABASE_URL` from the environment and creates missing
tables at startup. Production should run behind HTTPS. Set `TRUSTED_PROXY_HOPS`
to the exact number of trusted reverse proxies in front of the app; leave it at
`0` when accessing the app directly. Never set it based on untrusted client
input.

The in-process login limiter protects each app process. For shared protection
across workers, apply the Nginx configuration in `deploy/nginx.conf.example`,
which limits `/login` to five requests per minute per client IP with a small
burst allowance.

Backups require the PostgreSQL `pg_dump` and `pg_restore` utilities. They are
written as encrypted custom-format dumps with SHA-256 sidecars. The scheduler
runs a weekly restore drill against the isolated `BACKUP_RESTORE_DATABASE_URL`;
never point that value at the production database. Set `SENTRY_DSN` to report
unexpected application failures to Sentry.

Backups are SQLite files written to `backups/`.
