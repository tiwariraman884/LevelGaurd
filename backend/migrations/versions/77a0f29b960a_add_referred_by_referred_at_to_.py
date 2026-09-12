"""add_referred_by_referred_at_to_escalations

Revision ID: 77a0f29b960a
Revises: 5d6e7f8091a2
Create Date: 2026-09-12 18:04:10.124343
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '77a0f29b960a'
down_revision: Union[str, Sequence[str], None] = '5d6e7f8091a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("escalations", sa.Column("referred_by", sa.Integer(), nullable=True))
    op.add_column("escalations", sa.Column("referred_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_escalations_referred_by_users",
        "escalations",
        "users",
        ["referred_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_escalations_referred_by"),
        "escalations",
        ["referred_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_escalations_referred_by"),
        table_name="escalations",
    )
    op.drop_constraint(
        "fk_escalations_referred_by_users",
        "escalations",
        type_="foreignkey",
    )
    op.drop_column("escalations", "referred_at")
    op.drop_column("escalations", "referred_by")
