"""add_escalation_action_fields

Revision ID: 5d6e7f8091a2
Revises: 4c5d6e7f8091
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5d6e7f8091a2"
down_revision: Union[str, Sequence[str], None] = "4c5d6e7f8091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "escalations",
        sa.Column("acknowledged_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "escalations",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "escalations",
        sa.Column("resolved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "escalations",
        sa.Column("resolution_notes", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_escalations_acknowledged_by_users",
        "escalations",
        "users",
        ["acknowledged_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        "fk_escalations_resolved_by_users",
        "escalations",
        "users",
        ["resolved_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        op.f("ix_escalations_acknowledged_by"),
        "escalations",
        ["acknowledged_by"],
        unique=False,
    )

    op.create_index(
        op.f("ix_escalations_resolved_by"),
        "escalations",
        ["resolved_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_escalations_resolved_by"),
        table_name="escalations",
    )
    op.drop_index(
        op.f("ix_escalations_acknowledged_by"),
        table_name="escalations",
    )

    op.drop_constraint(
        "fk_escalations_resolved_by_users",
        "escalations",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_escalations_acknowledged_by_users",
        "escalations",
        type_="foreignkey",
    )

    op.drop_column("escalations", "resolution_notes")
    op.drop_column("escalations", "resolved_by")
    op.drop_column("escalations", "acknowledged_at")
    op.drop_column("escalations", "acknowledged_by")
