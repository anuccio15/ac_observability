"""Add decoder-v2 candidate effort and electrical metrics.

Revision ID: 0003_effort_metrics
Revises: 0002_edge_status
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_effort_metrics"
down_revision = "0002_edge_status"
branch_labels = None
depends_on = None


METRICS = [
    ("candidate_outdoor_unit_power_w", "Candidate outdoor-unit input power", "W", "electrical", 460),
    ("candidate_input_current_a", "Candidate outdoor-unit input current", "A", "electrical", 470),
    ("candidate_power_factor", "Candidate outdoor-unit power factor", None, "electrical", 480),
    ("candidate_outdoor_fan_current_a", "Candidate outdoor-fan current", "A", "electrical", 490),
    ("candidate_outdoor_fan_stage", "Candidate outdoor-fan stage", None, "operating", 500),
    ("candidate_eev_opening", "Candidate EEV opening", None, "actuator", 510),
]


def upgrade() -> None:
    table = sa.table(
        "metric_catalog",
        sa.column("metric_key", sa.String),
        sa.column("label", sa.String),
        sa.column("unit", sa.String),
        sa.column("category", sa.String),
        sa.column("confidence", sa.String),
        sa.column("value_type", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("introduced_decoder_version", sa.Integer),
    )
    op.bulk_insert(table, [
        {
            "metric_key": key,
            "label": label,
            "unit": unit,
            "category": category,
            "confidence": "candidate",
            "value_type": "number",
            "display_order": order,
            "introduced_decoder_version": 2,
        }
        for key, label, unit, category, order in METRICS
    ])


def downgrade() -> None:
    keys = ",".join(f"'{key}'" for key, *_ in METRICS)
    op.execute(sa.text(f"DELETE FROM metric_catalog WHERE metric_key IN ({keys})"))
