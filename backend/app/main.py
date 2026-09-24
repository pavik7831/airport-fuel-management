from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_password_hash
from .config import settings
from .database import Base, SessionLocal, engine, run_compatibility_migrations
from .models import AdminUser
from .routes_auth import router as auth_router
from .routes_resources import router as resources_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_compatibility_migrations()
    db = SessionLocal()
    try:
        if not db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first():
            db.add(AdminUser(email=settings.admin_email, password_hash=get_password_hash(settings.admin_password)))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="Airport Fuel Management API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(resources_router)


@app.get("/health")
def health(): return {"status": "ok"}
