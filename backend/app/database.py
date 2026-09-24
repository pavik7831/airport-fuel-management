from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_compatibility_migrations():
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE fuel_providers ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255)"))
        connection.execute(text("ALTER TABLE fuel_providers ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50)"))
        connection.execute(text("ALTER TABLE fuel_providers ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
        connection.execute(text("ALTER TABLE fuel_providers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        connection.execute(text("ALTER TABLE airlines ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255)"))
        connection.execute(text("ALTER TABLE airlines ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50)"))
        connection.execute(text("ALTER TABLE airlines ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
        connection.execute(text("ALTER TABLE airlines ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        connection.execute(text("ALTER TABLE fuel_rates ADD COLUMN IF NOT EXISTS rate NUMERIC(12, 4)"))
        connection.execute(text("ALTER TABLE fuel_rates ADD COLUMN IF NOT EXISTS effective_date DATE"))
        connection.execute(text("ALTER TABLE fuel_rates ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS reference_number VARCHAR(50)"))
        connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS provider_id INTEGER"))
        connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS fuel_quantity NUMERIC(14, 3)"))
        connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS fuel_rate NUMERIC(12, 4)"))
        connection.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))

        columns = {row[0] for row in connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'fuel_providers'"))}
        if "email" in columns:
            connection.execute(text("UPDATE fuel_providers SET contact_email = email WHERE contact_email IS NULL"))
        if "phone" in columns:
            connection.execute(text("UPDATE fuel_providers SET contact_phone = phone WHERE contact_phone IS NULL"))
        columns = {row[0] for row in connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'airlines'"))}
        if "email" in columns:
            connection.execute(text("UPDATE airlines SET contact_email = email WHERE contact_email IS NULL"))
        if "phone" in columns:
            connection.execute(text("UPDATE airlines SET contact_phone = phone WHERE contact_phone IS NULL"))
        columns = {row[0] for row in connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'fuel_rates'"))}
        if "rate_per_litre" in columns:
            connection.execute(text("UPDATE fuel_rates SET rate = rate_per_litre WHERE rate IS NULL"))
        if "effective_from" in columns:
            connection.execute(text("UPDATE fuel_rates SET effective_date = effective_from WHERE effective_date IS NULL"))
        columns = {row[0] for row in connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'invoices'"))}
        if "invoice_number" in columns:
            connection.execute(text("UPDATE invoices SET reference_number = invoice_number WHERE reference_number IS NULL"))
        if "fuel_provider_id" in columns:
            connection.execute(text("UPDATE invoices SET provider_id = fuel_provider_id WHERE provider_id IS NULL"))
        if "fuel_quantity_litres" in columns:
            connection.execute(text("UPDATE invoices SET fuel_quantity = fuel_quantity_litres WHERE fuel_quantity IS NULL"))
        if "rate_per_litre" in columns:
            connection.execute(text("UPDATE invoices SET fuel_rate = rate_per_litre WHERE fuel_rate IS NULL"))
