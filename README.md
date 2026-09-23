# Airport Fuel Management

This repository is being built module by module.

## Module 1: foundation

- FastAPI backend with PostgreSQL configuration
- Admin login using JWT bearer tokens
- React + Vite frontend with a login screen

## Start the backend

```powershell
Copy-Item backend/.env.example backend/.env
docker compose up -d db
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

The startup task creates the database tables and the initial admin from `.env`.

## Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and sign in with the values from `backend/.env`.
