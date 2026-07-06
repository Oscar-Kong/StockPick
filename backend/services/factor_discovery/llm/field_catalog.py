"""Field catalog helpers for LLM context minimization."""
from __future__ import annotations

from engines.factor.discovery.field_registry import build_default_field_registry


def available_fields_for_llm() -> list[dict]:
    registry = build_default_field_registry()
    out = []
    for fid, spec in sorted(registry.fields.items()):
        if not spec.factor_input_allowed or spec.is_outcome_label:
            continue
        if spec.availability.value == "unavailable":
            continue
        out.append(
            {
                "field_id": fid,
                "data_class": spec.data_class.value,
                "description": spec.description[:120],
                "requires_pit": spec.requires_point_in_time,
            }
        )
    return out


def unavailable_fields_for_llm() -> list[dict]:
    registry = build_default_field_registry()
    return [
        {"field_id": fid, "reason": spec.availability.value}
        for fid, spec in sorted(registry.fields.items())
        if spec.availability.value == "unavailable" or spec.is_outcome_label
    ]


def forbidden_outcome_fields() -> frozenset[str]:
    registry = build_default_field_registry()
    return frozenset(
        fid for fid, spec in registry.fields.items() if spec.is_outcome_label or not spec.factor_input_allowed
    )
