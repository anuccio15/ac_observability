"""Persist edge health state transitions.

Revision ID: 0002_edge_status
Revises: 0001_initial
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_edge_status"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edge_status",
        sa.Column("edge_id", sa.String(64), primary_key=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pi_reachable", sa.Boolean(), nullable=False),
        sa.Column("bluetooth_connected", sa.Boolean()),
        sa.Column("last_frame_at", sa.DateTime(timezone=True)),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "edge_status_transitions",
        sa.Column("transition_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("edge_id", sa.String(64), nullable=False),
        sa.Column("from_state", sa.String(32)),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "edge_status_transitions_changed_idx",
        "edge_status_transitions",
        ["edge_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("edge_status_transitions_changed_idx", table_name="edge_status_transitions")
    op.drop_table("edge_status_transitions")
    op.drop_table("edge_status")
