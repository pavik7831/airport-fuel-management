"""Prevent concurrent overlapping active fuel-rate periods.

PostgreSQL's btree_gist operator class allows provider/fuel equality and date
range overlap to be enforced atomically by a single exclusion constraint.
"""

from alembic import op

revision = "0002_rate_period_exclusion"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    # Existing installations must resolve any current overlaps before upgrading.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE fuel_rates
        ADD CONSTRAINT ex_rate_active_period_no_overlap
        EXCLUDE USING gist (
            provider_id WITH =,
            fuel_type WITH =,
            daterange(effective_from, effective_to, '[]') WITH &&
        ) WHERE (active)
        """
    )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint("ex_rate_active_period_no_overlap", "fuel_rates", type_="exclude")
    # Do not remove btree_gist: another application object may depend on it.
