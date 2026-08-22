# GYM-Management

GYM-Management is a multi-tenant Flask application for gym owners. It manages
members, attendance, memberships, payments, reminders, reports, encrypted
PostgreSQL backups, and platform administration.

## Contents

- [Requirements](#requirements)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Database migrations](#database-migrations)
- [Users and demo data](#users-and-demo-data)
- [Backups and Google Drive](#backups-and-google-drive)
- [WhatsApp reminders](#whatsapp-reminders)
- [Scheduled jobs](#scheduled-jobs)
- [Production deployment](#production-deployment)
- [Operational endpoints](#operational-endpoints)
- [Troubleshooting](#troubleshooting)

## Requirements

- Python 3.10+
- PostgreSQL 14+
- PostgreSQL utilities: `pg_dump` and `pg_restore` (for backups and restore drills)
- Optional: Google Cloud service account and Drive folder for off-site backups
- Optional: Meta WhatsApp Cloud API account for automatic reminders

Install the application dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass`
for the current shell only, then activate the environment again.

## Local development

1. Create a local PostgreSQL database.
2. Install dependencies.
3. Apply migrations.
4. Create the platform-admin account.
5. Start the app.

`dev_env.py` supplies local defaults only to the child command. It is not a
production secret store and must not contain production credentials.

```powershell
# Create the database tables from committed migrations.
python dev_env.py -m flask --app main db upgrade

# Create the configured platform administrator once.
python dev_env.py create_admin.py

# Start the local development server.
python dev_env.py main.py
```

Then open `http://127.0.0.1:5000`. The helper's local defaults are `admin` /
`12345678`; change them before any shared use.

Useful development commands:

```powershell
python dev_env.py -m flask --app main db current
python dev_env.py -m flask --app main db history
python dev_env.py -m flask --app main db migrate -m "describe the change"
python dev_env.py fake_data.py
```

Never run `fake_data.py` against production.

## Configuration

Set production configuration through a process manager or secret manager. Never
commit passwords, service-account JSON, API tokens, or a Flask secret key.

### Required application settings

| Variable | Description |
| --- | --- |
| `APP_SECRET_KEY` | Long random Flask session-signing secret. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL, e.g. `postgresql+psycopg://user:password@host:5432/gym_management`. |
| `ADMIN_USERNAME` | Login name of the platform administrator. |
| `ADMIN_PASSWORD` | Used by `create_admin.py` to create the initial administrator. |

### HTTP and monitoring settings

| Variable | Default | Description |
| --- | --- | --- |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` in HTTPS production. |
| `TRUSTED_PROXY_HOPS` | `0` | Exact number of trusted proxies in front of the app. Never set this from client input. |
| `SENTRY_DSN` | unset | Optional Sentry DSN for unexpected-error reporting. |

### Backup settings

| Variable | Default | Description |
| --- | --- | --- |
| `BACKUP_ENCRYPTION_KEY` | required | Fernet key used to encrypt dumps. Keep it separate from backups. |
| `BACKUP_DIR` | project `backups` directory | Local encrypted backup location. |
| `BACKUP_MAX_STORAGE_BYTES` | `0` | Local backup storage limit; `0` disables it. |
| `BACKUP_COMMAND_TIMEOUT_SECONDS` | `1800` | Timeout for `pg_dump` and `pg_restore`. |
| `BACKUP_RESTORE_DATABASE_URL` | required for drills | Isolated database used only for restore verification. **Never use the production database.** |

## Database migrations

The application does not create or upgrade tables at startup. Apply migrations
before starting each release:

```powershell
flask --app main db current
flask --app main db upgrade
flask --app main db current
```

Startup checks the Alembic revision and refuses to serve if the database is not
at the repository head. Review generated migrations before applying them:

```powershell
flask --app main db migrate -m "describe the schema change"
flask --app main db upgrade
```

Do not run `db stamp head` on an empty database: it marks migrations as applied
without creating tables.

## Users and demo data

Create the platform administrator after migrations:

```powershell
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "use-a-long-unique-password"
python create_admin.py
```

For local visual testing only:

```powershell
$env:DEMO_PASSWORD = "local-demo-password"
python fake_data.py
```

## Backups and Google Drive

Backups are encrypted PostgreSQL custom-format dumps. Each backup produces:

- `*.dump.enc` — encrypted database dump
- `*.dump.enc.sha256` — SHA-256 integrity checksum
- `*.dump.enc.json` — creation metadata

The app retains local backups for 30 days and keeps one backup per older month.
Local retention is not an off-site backup strategy.

### Configure Google Drive uploads

1. Create a dedicated Google Cloud service account and enable the Google Drive API.
2. Create a dedicated Google Drive backup folder.
3. Share only that folder with the service-account email as **Contributor**.
4. Put the entire downloaded JSON credential in your secret manager.
5. Set the following variables:

```powershell
$env:GOOGLE_DRIVE_UPLOAD_ENABLED = "true"
$env:GOOGLE_DRIVE_BACKUP_FOLDER_ID = "your-drive-folder-id"
$env:GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON = '{"type":"service_account",...}'
```

When enabled, every completed backup uploads its encrypted dump, checksum, and
metadata. An upload failure is reported as a backup failure; it is not silently
ignored.

### Restore drill safety

The scheduled restore drill runs `pg_restore --clean`, which deletes objects in
the target database. Use a separate restore database and least-privileged
credentials. Setting `BACKUP_RESTORE_DATABASE_URL` to production can destroy
production data.

## WhatsApp reminders

Automatic reminders are queued in the database and sent through the Meta
WhatsApp Cloud API up to the configured daily message limit.

### Configure Meta Cloud API

Create a Meta system-user access token with `whatsapp_business_messaging`, then
configure:

```powershell
$env:WHATSAPP_ACCESS_TOKEN = "meta-system-user-access-token"
$env:WHATSAPP_PHONE_NUMBER_ID = "meta-phone-number-id"
$env:WHATSAPP_TEMPLATE_NAME = "approved_reminder_template"
$env:WHATSAPP_TEMPLATE_LANGUAGE = "en_US"
```

Template mode is the default because business-initiated messages generally need
a Meta-approved template. Create a template with one text body variable:

```text
{{1}}
```

The application inserts its rendered reminder into that variable. Configure
`WHATSAPP_MESSAGE_MODE=text` only for recipients inside an active
customer-service window; outside that window Meta can reject free-form text.

| Variable | Default | Description |
| --- | --- | --- |
| `WHATSAPP_GRAPH_API_VERSION` | `v25.0` | Meta Graph API version. Update through config when retired. |
| `WHATSAPP_MESSAGE_MODE` | `template` | `template` or `text`. |
| `WHATSAPP_TEMPLATE_NAME` | required in template mode | Approved Meta template name. |
| `WHATSAPP_TEMPLATE_LANGUAGE` | `en_US` | Template language code. |
| `WHATSAPP_TIMEOUT_SECONDS` | `15` | Provider request timeout. |

Test first with Meta's test number and test recipients—never with production
member data.

## Scheduled jobs

Jobs run in Asia/Kolkata time:

| Time | Job |
| --- | --- |
| 00:30 | Remove inactive members according to each gym's settings |
| 01:00 | Create encrypted backup and optional Google Drive upload |
| 01:30 | Reconcile active-member counters |
| 02:00 Sunday | Restore newest backup into the isolated restore database |
| 08:00 | Queue/send member membership-expiry reminders |
| 09:00 | Queue/send owner subscription-expiry reminders |

Run exactly one scheduler in production. Multiple schedulers can duplicate
messages, backups, and membership-removal actions.

## Production deployment

Do not deploy with `python main.py`; it enables Flask debug mode. Use a
production WSGI server such as Gunicorn or Waitress behind HTTPS and a reverse
proxy.

Release checklist:

1. Install pinned dependencies.
2. Load all secrets through the deployment environment.
3. Run `flask --app main db upgrade` once.
4. Confirm the migration revision is current.
5. Start web workers without debug mode.
6. Start exactly one scheduler process.
7. Verify backup, Drive upload, WhatsApp test message, and isolated restore.
8. Alert on database, scheduler, backup, Drive, WhatsApp, and application failures.

[`deploy/nginx.conf.example`](deploy/nginx.conf.example) contains a basic
reverse-proxy and login rate-limit example. Adapt it for TLS certificates,
request/body limits, static-file delivery, proxy timeouts, and your process
manager. Set `TRUSTED_PROXY_HOPS=1` only when that Nginx instance is the sole
trusted proxy directly in front of the app.

## Operational endpoints

These endpoints require an authenticated platform-admin session:

| Endpoint | Purpose |
| --- | --- |
| `/health` | Confirms the app process is running. |
| `/ready` | Confirms database access and scheduler availability. |
| `/metrics` | Returns in-process request and latency counters. |

Expose them only to authenticated or private monitoring infrastructure.

## Troubleshooting

### Server will not start

Run `flask --app main db current` and `flask --app main db upgrade`. Confirm
`DATABASE_URL` points to the intended PostgreSQL database and all required
variables are present.

### Drive upload fails

Confirm that the Drive API is enabled, the folder ID is correct, the JSON is
valid, and the service account has access to the folder. Never log or paste the
service-account JSON while troubleshooting.

### WhatsApp messages remain pending

Verify the access token, phone-number ID, API version, approved template,
recipient opt-in, and Meta account status. Check the automatic-message error
record and application logs.

### Restore drill fails

Confirm `pg_dump` and `pg_restore` are installed, the encryption key matches
the backup, and the isolated restore database is reachable and safe to erase.
