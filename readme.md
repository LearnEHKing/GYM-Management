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
$env:BACKUP_COMMAND_TIMEOUT_SECONDS = "1800"
$env:GOOGLE_DRIVE_UPLOAD_ENABLED = "true"
$env:GOOGLE_DRIVE_BACKUP_FOLDER_ID = "your-drive-folder-id"
$env:GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON = '{"type":"service_account",...}'
$env:WHATSAPP_ACCESS_TOKEN = "meta-system-user-access-token"
$env:WHATSAPP_PHONE_NUMBER_ID = "meta-phone-number-id"
$env:WHATSAPP_TEMPLATE_NAME = "approved_reminder_template"
$env:WHATSAPP_TEMPLATE_LANGUAGE = "en_US"
$env:SESSION_COOKIE_SECURE = "true"
python main.py
```

## Google Drive backups

Set `GOOGLE_DRIVE_UPLOAD_ENABLED=true` to upload each encrypted backup, its
checksum, and metadata sidecar to Drive. Create a dedicated service account,
enable the Drive API, and share only the target backup folder with that service
account as a Contributor. Store the entire downloaded service-account JSON in
`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`; do not commit it or write it to disk.

## WhatsApp reminders

Automatic reminders use the Meta WhatsApp Cloud API. Set
`WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` from a Meta system user
with `whatsapp_business_messaging` permission. The default
`WHATSAPP_MESSAGE_MODE=template` requires an approved template whose body has
one text variable (`{{1}}`); the application puts the rendered reminder in
that variable. Use `WHATSAPP_MESSAGE_MODE=text` only for recipients inside an
active customer-service window. `WHATSAPP_GRAPH_API_VERSION` defaults to
`v25.0` and can be changed without code changes when Meta retires it.

For development, use the helper to launch a command with local defaults:

```powershell
python dev_env.py main.py
python dev_env.py create_admin.py
python dev_env.py fake_data.py
```

Use the same helper for Flask-Migrate commands. The `-m flask` tells Python to
run the Flask CLI as a module, while `dev_env.py` supplies the local database
and application environment:

```powershell
python dev_env.py -m flask --app main db current
python dev_env.py -m flask --app main db history
python dev_env.py -m flask --app main db migrate -m "describe the schema change"
python dev_env.py -m flask --app main db upgrade
```

For a database that already existed before Flask-Migrate was added, initialize
the migration repository once, generate the baseline, review it, and then mark
the existing schema as current:

```powershell
python dev_env.py -m flask --app main db init
python dev_env.py -m flask --app main db migrate -m "baseline existing schema"
python dev_env.py -m flask --app main db stamp head
```

Do not run `stamp head` on a new empty database. For a new database, use
`db upgrade` to create the schema from migrations.

The helper sets variables only for the child process. Production must provide
`APP_SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` from the deployment
environment or a secret manager. `DEMO_PASSWORD` is required only when running
`fake_data.py`.

The application requires `DATABASE_URL`. It does **not** create or upgrade
tables at startup: production releases must run `flask --app main db upgrade`
before starting application workers. Startup refuses to serve a database whose
Alembic revision is not at the repository head.

Database migrations use Flask-Migrate. After installing dependencies, initialize
the migration repository once with `flask --app main db init`, then generate and
apply schema changes with:

```powershell
flask --app main db migrate -m "describe the schema change"
flask --app main db upgrade
```

For an existing database that was created by the startup bootstrap, review the
generated initial migration and run `flask --app main db stamp head` instead of
replaying the initial table creation.
Use a PostgreSQL URL such as `postgresql+psycopg://user:password@db-host/gym`.
Production should run behind HTTPS. Set `TRUSTED_PROXY_HOPS`
to the exact number of trusted reverse proxies in front of the app; leave it at
`0` when accessing the app directly. Never set it based on untrusted client
input.

For local HTTP development, keep `SESSION_COOKIE_SECURE=false` (the default
provided by `dev_env.py`). Set it to `true` in HTTPS production; otherwise the
browser will not send the session cookie and CSRF validation will fail.

The in-process login limiter protects each app process. For shared protection
across workers, apply the Nginx configuration in `deploy/nginx.conf.example`,
which limits `/login` to five requests per minute per client IP with a small
burst allowance.

Backups require the PostgreSQL `pg_dump` and `pg_restore` utilities. They are
written as encrypted custom-format dumps with SHA-256 sidecars. The scheduler
runs a weekly restore drill against the isolated `BACKUP_RESTORE_DATABASE_URL`;
never point that value at the production database. Set `SENTRY_DSN` to report
unexpected application failures to Sentry.

