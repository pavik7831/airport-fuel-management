"""Create the initial AFM schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "administrators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_administrators_username", "administrators", ["username"], unique=True)

    for table in ("providers", "airlines"):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=24), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("contact_person", sa.String(length=120), nullable=True),
            sa.Column("email", sa.String(length=254), nullable=True),
            sa.Column("phone", sa.String(length=32), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{table}_code", table, ["code"], unique=True)

    op.create_table(
        "fuel_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("fuel_type", sa.String(length=40), nullable=False),
        sa.Column("rate_per_unit", sa.Numeric(precision=14, scale=5), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rate_per_unit > 0", name="ck_rate_positive"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_rate_dates"
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_rates_provider_id", "fuel_rates", ["provider_id"])
    op.create_index(
        "ix_rate_lookup",
        "fuel_rates",
        ["provider_id", "fuel_type", "effective_from", "effective_to"],
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("airline_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("rate_id", sa.Integer(), nullable=False),
        sa.Column("airline_code", sa.String(length=24), nullable=False),
        sa.Column("airline_name", sa.String(length=160), nullable=False),
        sa.Column("provider_code", sa.String(length=24), nullable=False),
        sa.Column("provider_name", sa.String(length=160), nullable=False),
        sa.Column("billing_month", sa.Date(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("fuel_type", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("rate_per_unit", sa.Numeric(precision=14, scale=5), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_quantity_positive"),
        sa.CheckConstraint("rate_per_unit > 0", name="ck_invoice_rate_positive"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'FINALIZED', 'CANCELLED')", name="ck_invoice_status"
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0", name="ck_invoice_amounts"
        ),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rate_id"], ["fuel_rates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", name="uq_invoice_reference"),
    )
    op.create_index("ix_invoices_airline_id", "invoices", ["airline_id"])
    op.create_index("ix_invoices_provider_id", "invoices", ["provider_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoice_billing_month", "invoices", ["billing_month"])
    op.create_index("ix_invoice_status_date", "invoices", ["status", "invoice_date"])

    op.create_table(
        "invoice_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["administrators.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_audit_events_invoice_id", "invoice_audit_events", ["invoice_id"])


def downgrade():
    op.drop_index("ix_invoice_audit_events_invoice_id", table_name="invoice_audit_events")
    op.drop_table("invoice_audit_events")
    op.drop_index("ix_invoice_status_date", table_name="invoices")
    op.drop_index("ix_invoice_billing_month", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_provider_id", table_name="invoices")
    op.drop_index("ix_invoices_airline_id", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_rate_lookup", table_name="fuel_rates")
    op.drop_index("ix_fuel_rates_provider_id", table_name="fuel_rates")
    op.drop_table("fuel_rates")
    for table in ("airlines", "providers"):
        op.drop_index(f"ix_{table}_code", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_administrators_username", table_name="administrators")
    op.drop_table("administrators")
