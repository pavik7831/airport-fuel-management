from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.auth import router as auth_router
from app.api.routes.fuel_rates import router as fuel_rates_router
from app.api.routes.invoices import router as invoices_router
from app.api.routes.parties import router as parties_router
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User


def create_initial_admin() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        exists = db.query(User).filter(User.email == settings.admin_email).first()
        if exists is None:
            db.add(
                User(
                    email=settings.admin_email,
                    password_hash=hash_password(settings.admin_password),
                    is_admin=True,
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    create_initial_admin()
    yield


settings = get_settings()
app = FastAPI(title="Airport Fuel Management API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(fuel_rates_router, prefix="/api/v1")
app.include_router(parties_router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
