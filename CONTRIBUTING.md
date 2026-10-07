# Contributing

Thanks for helping improve Airport Fuel Management. Keep changes focused, preserve invoice and audit history, and avoid weakening database-enforced financial invariants.

## Development setup

Follow the Windows PowerShell setup in [README.md](./README.md). Install the pinned Python dependencies with `pip install -r requirements.lock` and the frontend dependencies with `npm ci` from `frontend/`.

## Checks before opening a pull request

Run the relevant checks locally:

```powershell
ruff check backend
ruff format --check backend
pytest
```

From `frontend/`, run:

```powershell
npm audit --audit-level=moderate
npm run lint
npm run typecheck
npm run format:check
npm test
npm run build
```

Backend CI runs against PostgreSQL on Python 3.12 and 3.13. The browser journey uses a disposable PostgreSQL database and dedicated test credentials; never point it at production data.

## Pull request checklist

- Explain the user-visible or operational change and any relevant context.
- Add or update tests for changed behavior, including validation and failure cases.
- For schema changes, include a reviewed Alembic migration; do not rely on application startup to create or alter tables.
- Preserve server-side financial calculations, immutable finalized/cancelled invoice behavior, and audit events.
- Update relevant documentation and configuration examples.
- Do not include secrets, local databases, generated build output, or unrelated formatting changes.
- Confirm the applicable local checks pass and call out checks that could not be run.
