"""Record immutable invoice payment entries."""

import sqlalchemy as sa
from alembic import op

revision = "0003_invoice_payments"
down_revision = "0002_rate_period_exclusion"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_invoice_payment_amount_positive"),
        sa.ForeignKeyConstraint(["admin_id"], ["administrators.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invoice_payment_invoice_date",
        "invoice_payments",
        ["invoice_id", "payment_date", "id"],
    )


def downgrade():
    op.drop_index("ix_invoice_payment_invoice_date", table_name="invoice_payments")
    op.drop_table("invoice_payments")
