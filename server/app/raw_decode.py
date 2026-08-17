"""Decoder-v2 candidate metrics recovered from immutable Bosch frames."""

from __future__ import annotations

from typing import Any


RAW_NUMERIC_METRICS: dict[str, tuple[int, float]] = {
    "candidate_outdoor_fan_current_a": (23, 0.1),
    "candidate_eev_opening": (24, 1.0),
    "candidate_outdoor_unit_power_w": (54, 1.0),
    "candidate_input_current_a": (69, 0.1),
    "candidate_outdoor_fan_stage": (70, 1.0),
}


def raw_word(raw: bytes, index: int) -> int:
    offset = 2 + index * 2
    return int.from_bytes(raw[offset : offset + 2], "little")


def decode_candidate_metrics(raw: bytes) -> dict[str, Any]:
    metrics = {
        key: raw_word(raw, index) * scale
        for key, (index, scale) in RAW_NUMERIC_METRICS.items()
    }
    voltage = raw_word(raw, 31)
    current = metrics["candidate_input_current_a"]
    power = metrics["candidate_outdoor_unit_power_w"]
    metrics["candidate_power_factor"] = (
        round(power / (voltage * current), 3) if voltage and current else None
    )
    return metrics


def raw_metric_sql(metric_key: str, *, table: str = "telemetry_events") -> str | None:
    if metric_key == "candidate_power_factor":
        power = raw_metric_sql("candidate_outdoor_unit_power_w", table=table)
        current = raw_metric_sql("candidate_input_current_a", table=table)
        voltage = f"(get_byte({table}.raw_frame, 64) + 256 * get_byte({table}.raw_frame, 65))"
        return f"CASE WHEN {voltage} * {current} > 0 THEN {power} / ({voltage} * {current}) END"
    definition = RAW_NUMERIC_METRICS.get(metric_key)
    if definition is None:
        return None
    index, scale = definition
    offset = 2 + index * 2
    base = f"(get_byte({table}.raw_frame, {offset}) + 256 * get_byte({table}.raw_frame, {offset + 1}))"
    return base if scale == 1 else f"({base} * {scale})"
