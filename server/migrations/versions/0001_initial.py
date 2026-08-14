"""Initial ingestion and versioned telemetry schema.

Revision ID: 0001_initial
Revises: None
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


METRICS = [
    ("mode_code", "Operating mode code", None, "operating", "confirmed", "number", 10),
    ("mode", "Operating mode", None, "operating", "confirmed", "text", 20),
    ("compressor_set_hz", "Compressor set frequency", "Hz", "operating", "confirmed", "number", 30),
    ("outdoor_coil_t3_f", "Outdoor coil temperature (T3)", "°F", "temperature", "confirmed", "number", 100),
    ("outdoor_ambient_t4_f", "Outdoor ambient temperature (T4)", "°F", "temperature", "confirmed", "number", 110),
    ("compressor_discharge_t5_f", "Compressor discharge temperature (T5)", "°F", "temperature", "confirmed", "number", 120),
    ("compressor_suction_th_f", "Compressor suction temperature (Th)", "°F", "temperature", "confirmed", "number", 130),
    ("outdoor_coil_outlet_t3l_f", "Outdoor coil outlet temperature (T3L)", "°F", "temperature", "confirmed", "number", 140),
    ("compressor_ipm_temp_f", "Compressor IPM temperature", "°F", "temperature", "confirmed", "number", 150),
    ("target_evaporating_temp_tes_f", "Target evaporating temperature (Tes)", "°F", "temperature", "confirmed", "number", 160),
    ("evaporating_temp_te_f", "Evaporating temperature (Te)", "°F", "temperature", "confirmed", "number", 170),
    ("target_condensing_temp_tcs_f", "Target condensing temperature (Tcs)", "°F", "temperature", "confirmed", "number", 180),
    ("condensing_temp_tc_f", "Condensing temperature (Tc)", "°F", "temperature", "confirmed", "number", 190),
    ("target_discharge_superheat_f", "Target discharge superheat", "°F", "temperature", "confirmed", "number", 200),
    ("compressor_discharge_superheat_f", "Compressor discharge superheat", "°F", "temperature", "confirmed", "number", 210),
    ("evaporating_pressure_pe_psig", "Evaporating pressure (Pe)", "psig", "pressure", "confirmed", "number", 300),
    ("condensing_pressure_pc_psig", "Condensing pressure (Pc)", "psig", "pressure", "confirmed", "number", 310),
    ("pressure_lift_psid", "Pressure lift", "psi", "pressure", "derived", "number", 320),
    ("estimated_absolute_compression_ratio", "Estimated absolute compression ratio", None, "pressure", "derived", "number", 330),
    ("candidate_compressor_current_a", "Candidate compressor current", "A", "electrical", "candidate", "number", 400),
    ("candidate_actuator_or_load_value", "Candidate actuator/load value", None, "actuator", "candidate", "number", 410),
    ("candidate_continuous_run_seconds", "Candidate continuous runtime", "s", "operating", "candidate", "number", 420),
    ("candidate_ac_input_voltage_v", "Candidate AC input voltage", "V", "electrical", "candidate", "number", 430),
    ("candidate_dc_bus_voltage_v", "Candidate DC bus voltage", "V", "electrical", "candidate", "number", 440),
    ("candidate_software_version_raw", "Candidate software version", None, "diagnostic", "candidate", "number", 450),
]


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(64), primary_key=True),
        sa.Column("friendly_name", sa.String(128)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "ingest_batches",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("device_id", sa.String(64), sa.ForeignKey("devices.device_id"), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("collector_version", sa.String(32), nullable=False),
        sa.Column("decoder_versions", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.String(128), nullable=False),
        sa.Column("edge_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.CheckConstraint("sample_count > 0", name="ingest_batch_sample_count_positive"),
    )
    op.create_index("ingest_batches_device_received_idx", "ingest_batches", ["device_id", "received_at"])
    op.create_table(
        "telemetry_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("event_digest", sa.String(64), nullable=False),
        sa.Column("device_id", sa.String(64), sa.ForeignKey("devices.device_id"), nullable=False),
        sa.Column("first_batch_id", sa.String(64), sa.ForeignKey("ingest_batches.batch_id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edge_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decoder_version", sa.Integer(), nullable=False),
        sa.Column("urgent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("urgent_reason", sa.Text()),
        sa.Column("edge_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("raw_frame", postgresql.BYTEA(), nullable=False),
        sa.Column("raw_frame_digest", sa.String(64), nullable=False),
        sa.CheckConstraint("octet_length(raw_frame) = 167", name="telemetry_raw_frame_167_bytes"),
    )
    op.create_index("telemetry_device_captured_idx", "telemetry_events", ["device_id", "captured_at"])
    op.create_index("telemetry_captured_brin_idx", "telemetry_events", ["captured_at"], postgresql_using="brin")
    op.create_index(
        "telemetry_urgent_captured_idx",
        "telemetry_events",
        ["device_id", "captured_at"],
        postgresql_where=sa.text("urgent IS TRUE"),
    )
    op.create_table(
        "batch_events",
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("ingest_batches.batch_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("telemetry_events.event_id"), primary_key=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("batch_id", "ordinal", name="batch_events_batch_ordinal_key"),
    )
    op.create_table(
        "metric_catalog",
        sa.Column("metric_key", sa.String(128), primary_key=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("unit", sa.String(32)),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("value_type", sa.String(16), nullable=False, server_default="number"),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("introduced_decoder_version", sa.Integer(), nullable=False),
    )
    metric_table = sa.table(
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
    op.bulk_insert(
        metric_table,
        [
            {
                "metric_key": key,
                "label": label,
                "unit": unit,
                "category": category,
                "confidence": confidence,
                "value_type": value_type,
                "display_order": order,
                "introduced_decoder_version": 1,
            }
            for key, label, unit, category, confidence, value_type, order in METRICS
        ],
    )
    op.create_table(
        "decoded_projections",
        sa.Column("event_id", sa.String(64), sa.ForeignKey("telemetry_events.event_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("decoder_version", sa.Integer(), primary_key=True),
        sa.Column("decoded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decoder_build", sa.String(64), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", postgresql.JSONB(), nullable=False),
        sa.Column("decode_error", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("decoded_projections")
    op.drop_table("metric_catalog")
    op.drop_table("batch_events")
    op.drop_index("telemetry_urgent_captured_idx", table_name="telemetry_events")
    op.drop_index("telemetry_captured_brin_idx", table_name="telemetry_events")
    op.drop_index("telemetry_device_captured_idx", table_name="telemetry_events")
    op.drop_table("telemetry_events")
    op.drop_index("ingest_batches_device_received_idx", table_name="ingest_batches")
    op.drop_table("ingest_batches")
    op.drop_table("devices")
