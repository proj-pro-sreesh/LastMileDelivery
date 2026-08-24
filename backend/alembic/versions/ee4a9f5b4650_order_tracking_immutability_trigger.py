"""order tracking immutability trigger

Revision ID: ee4a9f5b4650
Revises: 0a99c4073293
Create Date: 2026-08-24 21:04:43.674033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee4a9f5b4650'
down_revision: Union[str, Sequence[str], None] = '0a99c4073293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


IMMUTABILITY_FUNCTION = """
CREATE OR REPLACE FUNCTION prevent_order_tracking_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'order_tracking records are immutable';
END;
$$ LANGUAGE plpgsql;
"""

DROP_FUNCTION = "DROP FUNCTION IF EXISTS prevent_order_tracking_mutation();"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(IMMUTABILITY_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER trg_order_tracking_immutable
        BEFORE UPDATE OR DELETE ON order_tracking
        FOR EACH ROW EXECUTE FUNCTION prevent_order_tracking_mutation();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_order_tracking_immutable ON order_tracking;")
    op.execute(DROP_FUNCTION)
