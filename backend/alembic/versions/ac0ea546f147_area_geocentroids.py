"""area geocentroids

Revision ID: ac0ea546f147
Revises: 9621a8fea164
Create Date: 2026-08-24 21:45:40.597185

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac0ea546f147'
down_revision: Union[str, Sequence[str], None] = '9621a8fea164'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also emitted spurious drop_constraint lines for the enum
    # CHECK constraints on users/orders/order_tracking/agent_profiles (naming-compare
    # false positive) — stripped, see AGENTS.md.
    op.add_column('areas', sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('areas', sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('areas', 'longitude')
    op.drop_column('areas', 'latitude')
