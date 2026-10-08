"""Add invoice due dates for collections aging."""

import sqlalchemy as sa
from alembic import op

revision = "0004_invoice_due_dates"
down_revision = "0003_invoice_payments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("due_date", sa.Date(), nullable=True))
    op.execute("UPDATE invoices SET due_date = invoice_date + 30")
    op.alter_column("invoices", "due_date", nullable=False)
    op.create_check_constraint(
        "ck_invoice_due_date_after_invoice_date",
        "invoices",
        "due_date >= invoice_date",
    )
    op.create_index("ix_invoice_status_due_date", "invoices", ["status", "due_date"])


def downgrade():
    op.drop_index("ix_invoice_status_due_date", table_name="invoices")
    op.drop_constraint("ck_invoice_due_date_after_invoice_date", "invoices", type_="check")
    op.drop_column("invoices", "due_date")
