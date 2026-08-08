from __future__ import annotations

from backend.app.canonical import normalise_temporal
from backend.app.eligibility import (
    evaluate_pre_estimation_eligibility,
    evaluate_propensity_overlap,
    evaluate_subject_distribution_support,
)


def temporal_field(value: str, *, kind: str = "instant") -> dict:
    return {
        "state": "present",
        "value": {
            "value": value,
            "kind": kind,
            "precision": "minute" if kind == "instant" else "date",
            "timezone_status": "known" if kind == "instant" else "not_applicable",
            "source_timezone": "Asia/Kolkata" if kind == "instant" else None,
        },
    }


def event(
    event_id: str,
    order_line_id: str,
    kind: str,
    occurred_at: str,
    known_at: str,
    *,
    milestone_kind: str | None = None,
    promised_for: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "order_line_id": order_line_id,
        "kind": kind,
        "milestone_kind": (
            {"state": "present", "value": milestone_kind}
            if milestone_kind is not None
            else {"state": "not_applicable"}
        ),
        "clocks": {
            "occurred_at": temporal_field(occurred_at),
            "known_at": temporal_field(known_at),
        },
        "promised_for": promised_for or {"state": "not_applicable"},
        "revises_promise_event_id": {"state": "not_applicable"},
        "supersedes_event_id": {"state": "missing"},
    }


def line(line_id: str, fields: dict) -> dict:
    return {
        "order_line_id": line_id,
        "order_group_id": f"group-{line_id}",
        "supplier_id": "supplier-1",
        "fields": fields,
    }


def observation(line_id: str, field_path: str, known_at: str) -> dict:
    return {
        "source_observation_id": f"observation-{line_id}-{field_path}",
        "target_record_id": line_id,
        "target_field_path": field_path,
        "known_at": temporal_field(known_at),
        "source_value_fingerprint": {"state": "present", "value": "stable"},
        "evidence_refs": [f"evidence-{line_id}-{field_path}"],
    }


def test_pre_estimation_pipeline_preserves_only_registered_pre_treatment_inputs() -> None:
    subject_fields = {
        "material_class": {"state": "present", "value": "switchgear"},
        "complexity_class": {"state": "missing"},
        "quantity": {"state": "present", "value": 4},
        "value": {"state": "invalid", "source_value": "bad"},
        "project_id": {"state": "present", "value": "project-1"},
        "production_progress": {"state": "present", "value": 0.8},
    }
    historical_fields = {
        "material_class": {"state": "present", "value": "fabrication"},
        "complexity_class": {"state": "present", "value": "medium"},
        "quantity": {"state": "present", "value": 3},
        "value": {"state": "present", "value": 20},
        "project_id": {"state": "present", "value": "project-1"},
    }
    subject_id = "subject"
    lineage = {
        "dataset_version": {
            "dataset_version_id": "dataset-v1",
            "intended_role": "semi_synthetic_hero",
        },
        "mapping_manifest": {
            "intended_role": "semi_synthetic_hero",
            "mapping_manifest_id": "mapping-v1",
        },
        "order_lines": [line(subject_id, subject_fields), line("history", historical_fields)],
        "order_line_events": [
            event("subject-commit", subject_id, "committed", "2026-01-10T09:00:00+05:30", "2026-01-10T08:59:00+05:30"),
            event("history-commit", "history", "committed", "2026-01-09T09:00:00+05:30", "2026-01-09T08:59:00+05:30"),
        ],
        "source_observations": [
            observation(subject_id, "supplier_id", "2026-01-10T08:59:00+05:30"),
            observation("history", "supplier_id", "2026-01-09T08:59:00+05:30"),
            observation(subject_id, "fields.material_class", "2026-01-10T08:59:00+05:30"),
            observation(subject_id, "fields.complexity_class", "2026-01-10T08:59:00+05:30"),
            observation(subject_id, "fields.quantity", "2026-01-10T08:59:00+05:30"),
            observation(subject_id, "fields.value", "2026-01-10T08:59:00+05:30"),
            observation(subject_id, "fields.project_id", "2026-01-10T08:59:00+05:30"),
        ],
    }

    result = evaluate_pre_estimation_eligibility(
        lineage,
        subject_id=subject_id,
        subject_supplier_id="supplier-1",
        decision_cutoff=normalise_temporal(
            temporal_field("2026-01-10T09:00:00+05:30")["value"]
        ),
        observation_cutoff=normalise_temporal(
            temporal_field("2026-01-10T09:00:00+05:30")["value"]
        ),
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
        trigger_mode="reactive",
    )

    assert result["adjustment_set"]["fields"] == [
        "material_class",
        "complexity_class",
        "quantity",
        "value",
        "project_id",
        "project_phase",
        "urgency_class",
        "geography_code",
        "contract_form",
    ]
    assert result["subject"]["inputs"]["complexity_class"]["state"] == "missing"
    assert result["subject"]["inputs"]["value"]["state"] == "invalid"
    assert "production_progress" not in result["subject"]["inputs"]
    assert "production_progress" not in str(result)
    assert result["stage_order"] == [
        "H0_HISTORY_SOURCE",
        "H1_HISTORY_COMMITMENT",
        "S0_SOURCE",
        "S1_COMMITMENT",
        "S2_WARMED",
        "S2_SNAPSHOT_OK",
        "S3_EXPOSURE",
        "S4_DESIGN",
        "S5_PROMISE",
        "S6_MATURE",
        "S7_COVARIATE",
        "S8_OUTCOME",
        "S9_OVERLAP",
    ]


def test_propensity_common_support_is_inclusive_and_trim_rates_are_deterministic() -> None:
    rows = [
        {"id": "lower", "exposure": False, "propensity": 0.10},
        {"id": "upper", "exposure": True, "propensity": 0.90},
        {"id": "trim-low", "exposure": False, "propensity": 0.09},
        {"id": "trim-high", "exposure": True, "propensity": 0.91},
    ]

    result = evaluate_propensity_overlap(rows)

    assert result["support_interval"]["lower"] == 0.10
    assert result["support_interval"]["upper"] == 0.90
    assert result["retained_ids"] == ["lower", "upper"]
    assert result["trimmed_ids"] == ["trim-high", "trim-low"]
    assert result["overall_trim_rate"] == 0.5
    assert result["eligibility_codes"] == ["OVERLAP_COHORT_INSUFFICIENT"]


def test_subject_distribution_support_requires_twenty_neighbors_per_arm() -> None:
    subject = {
        "material_class": {"state": "present", "value": "switchgear"},
        "complexity_class": {"state": "missing"},
        "quantity": {"state": "present", "value": 10},
    }
    rows = [
        {
            "id": f"line-{arm}-{index:02d}",
            "exposure": arm == "exposed",
            "inputs": {
                "material_class": {"state": "present", "value": "switchgear"},
                "complexity_class": {"state": "missing"},
                "quantity": {"state": "present", "value": 10},
            },
        }
        for arm, count in (("unexposed", 20), ("exposed", 19))
        for index in range(count)
    ]

    result = evaluate_subject_distribution_support(subject, rows)

    assert result["state"] == "unsupported"
    assert result["eligibility_codes"] == ["SUBJECT_DISTRIBUTION_UNSUPPORTED"]
    assert result["support"]["categorical_levels"]["material_class"]["switchgear"] == {
        "unexposed": 20,
        "exposed": 19,
    }


def test_frozen_selectors_keep_reactive_subject_in_history_but_remove_it_from_s0() -> None:
    cutoff = normalise_temporal(
        temporal_field("2026-01-10T09:00:00+05:30")["value"]
    )
    lineage = {
        "dataset_version": {
            "dataset_version_id": "dataset-v1",
            "intended_role": "semi_synthetic_hero",
        },
        "mapping_manifest": {"intended_role": "semi_synthetic_hero"},
        "order_lines": [
            line("subject", {}),
            line("history", {}),
            line("future", {}),
        ],
        "order_line_events": [
            event(
                "subject-commit",
                "subject",
                "committed",
                "2026-01-10T09:00:00+05:30",
                "2026-01-10T08:59:00+05:30",
            ),
            event(
                "history-commit",
                "history",
                "committed",
                "2026-01-09T09:00:00+05:30",
                "2026-01-09T08:59:00+05:30",
            ),
            event(
                "future-commit",
                "future",
                "committed",
                "2026-01-11T09:00:00+05:30",
                "2026-01-11T08:59:00+05:30",
            ),
        ],
    }

    result = evaluate_pre_estimation_eligibility(
        lineage,
        subject_id="subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=cutoff,
        observation_cutoff=cutoff,
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
        trigger_mode="reactive",
    )

    assert result["stages"]["H0_HISTORY_SOURCE"]["selected_ids"] == [
        "history",
        "subject",
    ]
    assert result["stages"]["S0_SOURCE"]["selected_ids"] == ["history"]
    assert result["selectors"]["history_lookback"]["selected_count"] == 2
    assert result["selectors"]["estimator_window"][
        "subject_removed_before_denominators"
    ] is True
    assert "late_risk" in result["variants"]


def test_required_zero_denominators_fail_with_recovery_reasons() -> None:
    result = evaluate_pre_estimation_eligibility(
        {"order_lines": []},
        subject_id="subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=normalise_temporal(
            temporal_field("2026-01-10T09:00:00+05:30")["value"]
        ),
        observation_cutoff=normalise_temporal(
            temporal_field("2026-01-10T09:00:00+05:30")["value"]
        ),
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
        trigger_mode="reactive",
    )

    primary = result["variants"]["primary"]
    assert "COHORT_SUPPORT_INSUFFICIENT" in primary["eligibility_codes"]
    assert primary["stages"]["S0_SOURCE"]["reason_code"] == (
        "COHORT_SUPPORT_INSUFFICIENT"
    )
    assert primary["stages"]["S0_SOURCE"]["next_step"]
