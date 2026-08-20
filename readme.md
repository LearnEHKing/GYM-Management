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

Backups are SQLite files written to `backups/`.
