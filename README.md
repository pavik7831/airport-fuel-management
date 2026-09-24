# Airport Fuel Management (AFM)

AFM is a connected internal operations console for managing aviation fuel rates, providers, airlines, and monthly airline settlements. The browser client talks to FastAPI, which persists all business data in PostgreSQL.

## Features

- JWT-protected administrator login with bcrypt password hashing
- Database-driven dashboard totals and recent invoice activity
- CRUD for fuel rates, fuel providers, and airlines
- Provider and airline activation controls
- Monthly invoices with rate x quantity calculation before saving
- Duplicate invoice prevention for provider + airline + billing month at both API and database levels
- Search, empty states, validation feedback, responsive layout, and destructive-safe workflows

## Technology

- React 19 + Vite + Lucide React
- FastAPI + SQLAlchemy 2 + Pydantic Settings
- PostgreSQL 16
- JWT via `python-jose`, bcrypt via `passlib`

## Structure

```text
backend/app/       FastAPI configuration, models, schemas, auth, and routes
frontend/src/      React application, API client, pages, forms, and styles
docker-compose.yml Local PostgreSQL service
```

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- Docker Desktop, or a PostgreSQL 14+ server

## Setup

1. Start PostgreSQL with `docker compose up -d postgres`.
2. Copy `backend/.env.example` to `backend/.env` and update the values. The defaults match the included Docker service.
3. Install backend dependencies and start FastAPI:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

4. In a second terminal, install and start the React client:

```powershell
cd frontend
npm install
npm run dev
```

The client is available at http://localhost:5173 and API documentation is available at http://localhost:8000/docs. The API health endpoint is http://localhost:8000/health.

## Database and first login

Tables are created automatically on the first successful API startup. The first administrator is seeded from `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `backend/.env`; change both values before using the application beyond local development. Never commit `.env` or production credentials.

## Environment

Backend settings are documented in `backend/.env.example`. The frontend can override the API origin with `frontend/.env`:

```text
VITE_API_URL=http://localhost:8000/api
```

## Troubleshooting

- A database connection error means PostgreSQL is not running or `DATABASE_URL` does not match its credentials.
- A CORS error means the browser origin is missing from `CORS_ORIGINS`.
- If the seeded password was changed after the first startup, update the existing administrator row or recreate the local database volume.
- FastAPI exposes validation and duplicate-record messages as JSON `detail` values; the client surfaces them as toast errors.
