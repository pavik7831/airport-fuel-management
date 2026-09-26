# Airport Fuel Management System

AFM is a full-stack, administrator-operated aviation fuel billing application. It manages fuel providers, airlines, effective dated fuel prices and monthly invoice records with server-calculated amounts and immutable historical rate snapshots.

## Features and architecture

- React 19 + Vite interface with responsive operations navigation, live dashboard, master data, effective dated rate records, invoice creation/details/printing, and CSV export.
- FastAPI REST API under `/api/v1`, async SQLAlchemy 2, PostgreSQL 16, Pydantic validation and Alembic migrations.
- Argon2id password hashes, short-lived JWTs in HttpOnly cookies, readable CSRF token paired with a required mutation header, active-admin checks and login throttling.
- Financial invoice lifecycle: DRAFT → FINALIZED or CANCELLED. Terminal invoices cannot be changed. Cancellation requires a reason and creates an audit event. Invoices snapshot the selected rate and names/codes. Totals use Decimal and ROUND_HALF_UP at two decimal places.
- Invoice references are globally unique. This allows multiple invoices per airline/provider/month while preventing duplicate references. PostgreSQL uniqueness is the concurrency authority.
- Active provider/rate/airline checks, soft deactivation and FK restrictions preserve financial history. Active rate periods are protected both by API validation and a PostgreSQL GiST exclusion constraint, including concurrent writes. Dashboard excludes cancelled amounts and groups by currency to avoid combining unlike currencies.
- Invoice CSV exports neutralize spreadsheet formula prefixes; dashboard monthly/provider/airline summaries use the selected 3–36 month billing window.

## Technology and supported versions

Python 3.12 (3.12–3.13 supported), Node.js 22 LTS (22+), PostgreSQL 16 (16+). Python dependency pins are in `requirements.lock`; JavaScript exact resolution is in `frontend/package-lock.json`. Docker uses Python 3.12, Node 22 and PostgreSQL 16.

## Project structure

```text
backend/app/       configuration, database, models, schemas, security, services, REST API, CLI
backend/migrations/ Alembic environment and initial schema migration
backend/tests/     backend business tests
frontend/src/      React shell, API client, shared UI, page modules, styles and unit tests
frontend/e2e/      Playwright browser journeys
.github/workflows/ CI pipeline
Dockerfile.backend frontend/Dockerfile docker-compose.yml
```

## Windows PowerShell development

Install Python 3.12, Node 22, PostgreSQL 16, then create an empty `afm` database and local role. In PowerShell:

```powershell
Copy-Item .env.example .env
# Edit .env with a random JWT_SECRET, CSRF_SECRET and your local PostgreSQL credentials.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.lock
$env:DATABASE_URL = "postgresql+asyncpg://afm:your-password@localhost:5432/afm"
alembic upgrade head
python -m backend.app.cli create-admin --username admin
uvicorn backend.app.main:app --reload
```

In a second PowerShell terminal:

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
npm run dev
```

Open <http://localhost:5173>. The API Swagger UI is at <http://localhost:8000/api/docs>. Do not use the sample values as production secrets. Omitting `--password` prompts for it without echoing the value.

To reset a local administrator password, run `python -m backend.app.cli reset-password --username admin`; the CLI prompts for a new password and requires at least 12 characters. This is an operator command, not a public API.

## Configuration

See `.env.example`. Required values include `DATABASE_URL`, a unique random `JWT_SECRET` and `CSRF_SECRET` of at least 32 characters, `FRONTEND_ORIGINS`, `COOKIE_SECURE=true` in production, `DEFAULT_CURRENCY`, and `DEFAULT_QUANTITY_UNIT`. The application rejects shorter signing secrets. It explicitly defaults to USD and US gallons. Tax is entered as an explicit amount per invoice and defaults to zero; no tax rate is inferred. Set origins to exact trusted scheme/host values. Do not commit `.env`.

Access tokens expire after `ACCESS_TOKEN_MINUTES` (default 30). Authentication is cookie-based: access cookie is HttpOnly; CSRF cookie is readable by the UI and must be returned as `X-CSRF-Token` on writes. Use HTTPS in production. Lax same-site cookies are the default; deployments across sites require careful cookie and CSRF review.

## Database and migrations

Create the schema with `alembic upgrade head`. Inspect migration state with `alembic current` and `alembic history`. Create reviewed revisions with `alembic revision --autogenerate -m "description"`; check generated DDL before deploying. Rollback one revision with `alembic downgrade -1` only after a backup and review. Migration `0001_initial` downgrade removes the initial schema and is suitable only for an empty/new installation, never as a routine production rollback. App startup never creates or resets tables. Revision `0002_rate_period_exclusion` enables PostgreSQL's `btree_gist` extension and rejects overlapping active periods per provider and fuel type at the database level. Before upgrading an existing database, resolve any conflicts returned by:

```sql
SELECT a.id, b.id, a.provider_id, a.fuel_type
FROM fuel_rates a JOIN fuel_rates b
  ON a.id < b.id
 AND a.provider_id = b.provider_id
 AND a.fuel_type = b.fuel_type
 AND a.active AND b.active
 AND daterange(a.effective_from, a.effective_to, '[]')
     && daterange(b.effective_from, b.effective_to, '[]');
```

## Tests, lint and build

From repo root:

```powershell
ruff check backend
ruff format --check backend
pytest --cov=backend/app --cov-report=term-missing
```

Frontend:

```powershell
cd frontend
npm ci
npm run lint
npm test
npm run build
```

Playwright requires a dedicated running API and disposable database, plus `E2E_USERNAME` / `E2E_PASSWORD`. Its browser journey exercises administrator login, provider and airline creation, rate creation, invoice creation and total verification, then logout. Install Chromium using `npx playwright install chromium`, then run `npm run test:e2e`.

The latest verification in this workspace passed 31 backend tests (80% total line coverage; 99% for invoice services; 95% for the admin CLI), 9 frontend tests, ESLint, Prettier checks, Ruff, an Alembic SQLite upgrade/check/downgrade cycle, PostgreSQL DDL compilation for the exclusion constraint, and a Vite production build. The Playwright journey assertions passed against a disposable local SQLite database, though the runner did not exit cleanly during Windows teardown. The GitHub Actions journey now also races overlapping rate requests against PostgreSQL and expects exactly one creation to succeed. CI has not been run from this workspace; Docker is unavailable here, so the PostgreSQL migration and race check still require CI execution.

The measured Vite output is about 324 kB initial JavaScript (106 kB gzip) and 328 kB CSS (49 kB gzip), plus Bootstrap icon fonts. Management pages load as separate route chunks; consider trimming unused Bootstrap CSS if the interface grows substantially.

## Docker and deployment

Set `.env` including a strong `POSTGRES_PASSWORD`, DB URL (compose overrides host to `db`), JWT/CSRF secrets, and origins. `docker compose up --build -d` starts PostgreSQL with persistent volume, migrates before API start, and serves the UI on `127.0.0.1:8080`; PostgreSQL is not published. Nginx proxies `/api` and `/health` internally. Put a TLS reverse proxy/load balancer in front, restrict inbound access, set the exact public `FRONTEND_ORIGINS`, `COOKIE_SECURE=true`, and keep the database volume private. Do not bake secrets into images.

For database backup: `docker compose exec -T db pg_dump -U afm afm > afm-backup.sql`. Restore to an empty or separately provisioned DB with `docker compose exec -T db psql -U afm afm < afm-backup.sql`; validate backups and recovery regularly. Use managed secret storage and PostgreSQL point-in-time recovery for production. This repository is not deployed and makes no HTTPS claim.

## Operations and security

Liveness is `/health/live`; readiness verifies database connectivity at `/health/ready`. API errors are deliberately brief; request correlation IDs are echoed as `X-Request-ID`. Provider/airline deletion is deactivation. Rate periods cannot overlap through application validation and referenced rates are immutable. Financial identifiers use database uniqueness. ORM statements are parameterized. Nginx adds baseline browser headers; terminate TLS at a trusted proxy and set HSTS there. Review dependencies regularly. The current UI loads Google Fonts via CSS; remove that import for environments requiring zero third-party requests.

`npm audit --omit=dev` reported no production dependency vulnerabilities. Full `npm audit` reports two moderate advisories in the Vitest mocker dependency with no npm fix available at the time of the run. Review again when upgrading the test toolchain.

## CI

GitHub Actions runs Ruff, Alembic migration, pytest with coverage artifact, npm lockfile install, ESLint, Vitest, production build, and a Playwright journey against an ephemeral PostgreSQL-backed API. CI uses test-only credentials and database state.

## Limitations to address before a regulated production launch

- Expand endpoint, security and failure-path tests; current backend total coverage is 80% even though invoice service coverage is 99%.
- Run Playwright against its dedicated test database and verify the PostgreSQL migration and simultaneous rate-write protection in CI before production use.
- Add payment tracking before presenting outstanding receivables; dashboard intentionally omits it.
- Perform a formal threat model, external dependency scan, accessibility audit, backup restore drill and load test before handling live financial records.
