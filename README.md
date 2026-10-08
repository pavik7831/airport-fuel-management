# Airport Fuel Management System

[![CI](https://github.com/pavik7831/airport-fuel-management/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pavik7831/airport-fuel-management/actions/workflows/ci.yml)
[![CodeQL](https://github.com/pavik7831/airport-fuel-management/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/pavik7831/airport-fuel-management/actions/workflows/codeql.yml)

AFM is a full-stack, administrator-operated aviation fuel billing application. It manages fuel providers, airlines, effective dated fuel prices and monthly invoice records with server-calculated amounts and immutable historical rate snapshots.

## Project quality and operational status

| Area | Evidence |
| --- | --- |
| Automated checks | GitHub Actions runs backend, frontend, and PostgreSQL-backed browser checks on pushes and pull requests. Browser checks include axe-core WCAG 2.1 A/AA scans of sign-in, dashboard, and invoice-payment screens, a bounded authenticated API concurrency smoke against disposable PostgreSQL data, then a restore check comparing application table rows and sequence states. |
| Main branch safeguards | `main` requires pull requests and passing Python 3.12/3.13 backend, frontend, PostgreSQL browser, and both CodeQL checks; approvals are optional, and bypass, force-push, and deletion are disabled. |
| Backend coverage | Pytest enforces a 100% coverage threshold; CI retains an XML coverage artifact for each tested Python version. This is a backend threshold, not a claim about frontend coverage. |
| Security and maintenance | CodeQL scans Python and JavaScript/TypeScript on pushes, pull requests, and weekly; Dependabot checks Python, npm, and GitHub Actions dependencies weekly. CI also runs the npm advisory audit. [The threat model](./docs/THREAT_MODEL.md) documents controls and deployment-specific residual risks; it is not an independent security audit. |
| Deployment | Docker Compose deployment and operational guidance are documented below. This repository is not deployed to production. |
| Documentation | Setup, configuration, migrations, backups, security, testing, and deployment instructions are maintained in this README. |

## Features and architecture

- React 19 + Vite interface with responsive operations navigation, live dashboard, master data, effective dated rate records, invoice creation/details/printing, and CSV export.
- FastAPI REST API under `/api/v1`, async SQLAlchemy 2, PostgreSQL 16, Pydantic validation and Alembic migrations.
- Argon2id password hashes, short-lived JWTs in HttpOnly cookies, readable CSRF token paired with a required mutation header, active-admin checks and login throttling.
- Financial invoice lifecycle: DRAFT → FINALIZED or CANCELLED. Terminal invoices cannot be changed. Cancellation requires a reason and creates an audit event. Invoices snapshot the selected rate and names/codes. Totals use Decimal and ROUND_HALF_UP at two decimal places.
- Invoice references are globally unique. This allows multiple invoices per airline/provider/month while preventing duplicate references. PostgreSQL uniqueness is the concurrency authority.
- Active provider/rate/airline checks, soft deactivation and FK restrictions preserve financial history. Active rate periods are protected both by API validation and a PostgreSQL GiST exclusion constraint, including concurrent writes. Dashboard excludes cancelled amounts and groups by currency to avoid combining unlike currencies.
- Finalized invoices accept immutable, dated partial-payment entries with optional references and notes. The API computes paid totals and balances from the ledger, rejects overpayments, and records payment events in the invoice audit history.
- The operations dashboard summarizes open finalized-invoice balances per currency, excluding drafts, fully paid invoices, and cancellations.
- Invoice CSV exports neutralize spreadsheet formula prefixes; dashboard monthly/provider/airline summaries use the selected 3–36 month billing window.

## Technology and supported versions

Python 3.12 and 3.13 are tested in CI. Node.js 22 LTS (22+), PostgreSQL 16 (16+). Python dependency pins are in `requirements.lock`; JavaScript exact resolution is in `frontend/package-lock.json`. Docker uses Python 3.12, Node 22 and PostgreSQL 16.

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

Create the schema with `alembic upgrade head`. Inspect migration state with `alembic current` and `alembic history`. Create reviewed revisions with `alembic revision --autogenerate -m "description"`; check generated DDL before deploying. Rollback one revision with `alembic downgrade -1` only after a backup and review. Migration `0001_initial` downgrade removes the initial schema and is suitable only for an empty/new installation, never as a routine production rollback. App startup never creates or resets tables. Revision `0002_rate_period_exclusion` enables PostgreSQL's `btree_gist` extension and rejects overlapping active periods per provider and fuel type at the database level. Revision `0003_invoice_payments` adds the immutable invoice payment ledger. Before upgrading an existing database to `0002_rate_period_exclusion`, resolve any conflicts returned by:

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
npm run typecheck
npm test
npm run build
```

Pull requests and pushes to `main`/`master` are configured to run backend checks on Python 3.12 and 3.13, frontend checks including a moderate-or-higher npm advisory audit, CodeQL analysis for Python and JavaScript/TypeScript, and a PostgreSQL-backed Playwright journey. Dependabot checks Python, npm, and GitHub Actions dependencies weekly. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the local workflow and pull request checklist. Report security issues privately as described in [SECURITY.md](./SECURITY.md).

Playwright requires a dedicated API and disposable database, plus `E2E_USERNAME` / `E2E_PASSWORD`. Its browser journey exercises administrator login, provider and airline creation, rate creation, concurrent rate-overlap and payment-overpayment checks, invoice creation, finalization, partial payment recording and balance verification, then logout. Install Chromium using `npx playwright install --with-deps chromium`, then run `npm run test:e2e` from `frontend`. CI provisions PostgreSQL and runs this journey with isolated test credentials.

After that journey, CI runs a read-only API concurrency smoke against its loopback-only disposable server: 10 workers for 15 seconds exercise dashboard, provider, airline, rate, and invoice list endpoints using the test administrator session. The check requires successful responses and aggregate p95 latency no higher than 2 seconds; CI retains a JSON report artifact. To run it locally, start the API against a disposable database, set `E2E_USERNAME` and `E2E_PASSWORD`, and run `python scripts/api_load_smoke.py`. The script refuses non-loopback targets, is bounded to at most 100 workers and 120 seconds, and does not mutate application records. It is a small CI regression smoke, not a capacity benchmark, realistic production-data test, or production SLO guarantee.

Local checks are run with the commands below; GitHub Actions runs backend checks on Python 3.12 and 3.13, the frontend suite, and the PostgreSQL browser journey. Unit tests use isolated SQLite databases, while CI validates PostgreSQL behavior against PostgreSQL 16.

The measured Vite output is about 324 kB initial JavaScript (106 kB gzip) and 328 kB CSS (49 kB gzip), plus Bootstrap icon fonts. Management pages load as separate route chunks; consider trimming unused Bootstrap CSS if the interface grows substantially.

## Docker and deployment

Set `.env` including a strong `POSTGRES_PASSWORD`, DB URL (compose overrides host to `db`), JWT/CSRF secrets, and origins. `docker compose up --build -d` starts PostgreSQL with a persistent volume, applies migrations before API start, and serves the UI on `127.0.0.1:8080`; PostgreSQL is not published. Compose waits for PostgreSQL and the API readiness check before starting the frontend. Nginx proxies `/api` and `/health` internally. Put a TLS reverse proxy/load balancer in front, restrict inbound access, set the exact public `FRONTEND_ORIGINS`, `COOKIE_SECURE=true`, and keep the database volume private. Do not bake secrets into images.

Create a logical database backup with `docker compose exec -T db pg_dump -U afm -Fc afm > afm-backup.dump`. To rehearse a restore without touching the application database, create a separate empty database with `docker compose exec -T db createdb -U afm afm_restore`, then restore with `docker compose exec -T db pg_restore -U afm --exit-on-error --no-owner --no-privileges -d afm_restore < afm-backup.dump`. Verify the restored application and data before routing traffic to it; remove the rehearsal database with `docker compose exec -T db dropdb -U afm afm_restore` when finished. After the PostgreSQL browser journey creates invoice, payment, and audit data, CI takes a custom-format dump, restores it into a separate empty database, and compares every non-system table's rows and PostgreSQL sequence definitions and values. The check also requires the journey's invoice, payment, and audit tables to contain data. This verifies logical dump/restore integrity for generated test data; it is not a production backup, encrypted off-site backup, disaster-recovery, or recovery-time test. Use encrypted off-site backups, managed secret storage, and PostgreSQL point-in-time recovery for production. This repository is not deployed and makes no HTTPS claim.

## Operations and security

Liveness is `/health/live`; readiness verifies database connectivity at `/health/ready`. API errors are deliberately brief; request correlation IDs are echoed as `X-Request-ID`. Provider/airline deletion is deactivation. Rate periods cannot overlap through application validation and referenced rates are immutable. Financial identifiers use database uniqueness. ORM statements are parameterized. Nginx adds baseline browser headers; terminate TLS at a trusted proxy and set HSTS there. Review dependencies regularly. The current UI loads Google Fonts via CSS; remove that import for environments requiring zero third-party requests.

The current frontend lockfile passes `npm audit --audit-level=moderate`; CI repeats this check on every run. Re-run the audit when dependencies change. See [docs/THREAT_MODEL.md](./docs/THREAT_MODEL.md) for the internal threat model, residual risks, and production readiness gates.

## CI

GitHub Actions validates the Docker Compose configuration, runs Ruff lint/format checks, Alembic migrations against PostgreSQL 16, pytest with a coverage artifact, npm lockfile install, ESLint, TypeScript, Prettier formatting checks, Vitest, a production build, and the Playwright browser journey against an ephemeral PostgreSQL-backed API. Playwright runs axe-core WCAG 2.1 A/AA checks against the sign-in page, authenticated dashboard, and invoice-payment detail screen. Automated axe checks are a regression guard, not a substitute for manual keyboard, screen-reader, zoom, and assistive-technology review. After the journey, CI runs a bounded read-only API concurrency smoke and restores a custom-format PostgreSQL dump into a second disposable database, verifying exact application-table row and sequence-state equality. The load smoke report is retained as a CI artifact. API unit tests use isolated SQLite databases. CI uses test-only credentials and database state. The restore verifier can also be run with `python scripts/verify_postgres_restore.py --source afm --restored afm_restore` when both disposable databases are available.

## Limitations to address before a regulated production launch

- Maintain the 100% backend coverage gate as routes and services change.
- Confirm the hosted Playwright run passes against PostgreSQL and retain its result before production use.
- Add receivables aging and payment reconciliation before using the payment ledger for collections operations.
- Perform a formal threat model, manual accessibility audit, representative load/capacity test, and recovery-time-tested restore from the intended encrypted production backups before handling live financial records. The CI concurrency smoke is not a substitute for these production-readiness exercises.
