"""add is_email_verified to users

Revision ID: e7b4c9d1a2f8
Revises: d4e8a1b2c3f4
Create Date: 2026-11-18 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7b4c9d1a2f8"
down_revision: Union[str, Sequence[str], None] = "d4e8a1b2c3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_email_verified column to users (backfilling existing users as verified)."""
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    # New rows going forward default to false until OTP verification completes
    op.alter_column(
        "users",
        "is_email_verified",
        server_default=sa.text("false"),
    )


def downgrade() -> None:
    """Remove is_email_verified column from users."""
    op.drop_column("users", "is_email_verified")
