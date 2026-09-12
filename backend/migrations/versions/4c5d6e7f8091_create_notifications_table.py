"""create_notifications_table

Revision ID: 4c5d6e7f8091
Revises: 3b4c5d6e7f80
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4c5d6e7f8091"
down_revision: Union[str, Sequence[str], None] = "3b4c5d6e7f80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("escalation_id", sa.Integer(), nullable=True),
        sa.Column("recipient_role", sa.String(length=50), nullable=False),
        sa.Column("recipient_name", sa.String(length=120), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["escalation_id"],
            ["escalations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_notifications_escalation_id"),
        "notifications",
        ["escalation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_recipient_role"),
        "notifications",
        ["recipient_role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_status"),
        "notifications",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notifications_status"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_recipient_role"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_escalation_id"),
        table_name="notifications",
    )
    op.drop_table("notifications")
