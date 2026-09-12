"""add_officer_final_decision_fields

Revision ID: 6a7b8c9d0e1f
Revises: c2553b8e24fe
Create Date: 2026-09-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a7b8c9d0e1f"
down_revision: Union[str, Sequence[str], None] = "c2553b8e24fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inspections",
        sa.Column("final_decision", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "inspections",
        sa.Column("final_decision_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "inspections",
        sa.Column(
            "final_decision_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "inspections",
        sa.Column("officer_remarks", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_inspections_final_decision_by_users",
        "inspections",
        "users",
        ["final_decision_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        op.f("ix_inspections_final_decision"),
        "inspections",
        ["final_decision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_inspections_final_decision"),
        table_name="inspections",
    )
    op.drop_constraint(
        "fk_inspections_final_decision_by_users",
        "inspections",
        type_="foreignkey",
    )
    op.drop_column("inspections", "officer_remarks")
    op.drop_column("inspections", "final_decision_at")
    op.drop_column("inspections", "final_decision_by")
    op.drop_column("inspections", "final_decision")
