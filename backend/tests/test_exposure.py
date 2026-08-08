from __future__ import annotations

import json

import pytest

from backend.app.canonical import normalise_temporal
from backend.app.risk import evaluate_supplier_load_exposure
from backend.app.risk import derive_supplier_load_exposure
from backend.app.risk import resolve_supplier_load_snapshot


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
        "supersedes_event_id": {"state": "missing"},
    }


def line(line_id: str, supplier_id: str = "supplier-1") -> dict:
    return {"order_line_id": line_id, "supplier_id": supplier_id, "fields": {}}


def supplier_observation(line_id: str, known_at: str) -> dict:
    return {
        "source_observation_id": f"observation-{line_id}",
        "target_record_id": line_id,
        "target_field_path": "supplier_id",
        "known_at": temporal_field(known_at),
        "source_value_fingerprint": {
            "state": "present",
            "value": "supplier-1",
        },
        "evidence_refs": [f"evidence-{line_id}"],
    }


def test_primary_exposure_uses_nearest_rank_and_strict_greater_than() -> None:
    history = [0, 1, 1, 2, 2, 3, 3, 4, 5, 7]

    unexposed = evaluate_supplier_load_exposure(
        current_load_count=3,
        history_load_counts=history,
        duration_basis="CALENDAR_DAY",
    )
    exposed = evaluate_supplier_load_exposure(
        current_load_count=4,
        history_load_counts=history,
        duration_basis="CALENDAR_DAY",
    )

    assert unexposed["primary"]["threshold"] == 3
    assert unexposed["primary"]["threshold_rank"] == 7
    assert unexposed["primary"]["high_load_exposure"] is False
    assert exposed["primary"]["high_load_exposure"] is True
    assert exposed["primary"]["load_percentile"] == pytest.approx(0.75)
    assert exposed["duration_basis"] == "CALENDAR_DAY"


def test_history_minimums_are_variant_specific_and_do_not_rescue_primary() -> None:
    result = evaluate_supplier_load_exposure(
        current_load_count=4,
        history_load_counts=[0] * 9,
        duration_basis="CALENDAR_DAY",
    )

    assert result["primary"]["state"] == "ineligible"
    assert result["primary"]["eligibility_codes"] == [
        "SUPPLIER_HISTORY_INSUFFICIENT"
    ]
    assert result["variants"]["short_history"]["state"] == "present"
    assert result["variants"]["long_history"]["state"] == "ineligible"
    assert result["variants"]["short_history"]["replaces_primary"] is False


def test_supplier_load_snapshot_is_point_in_time_and_half_open() -> None:
    cutoff = normalise_temporal(
        {
            "value": "2026-01-10T10:00:00+05:30",
            "kind": "instant",
            "precision": "minute",
            "timezone_status": "known",
            "source_timezone": "Asia/Kolkata",
        }
    )
    lines = [
        line("subject"),
        line("open"),
        line("closed-at-cutoff"),
        line("late-known-closure"),
        line("wrong-milestone"),
        line("cancelled"),
        line("same-time"),
    ]
    events = [
        event("subject-commit", "subject", "committed", "2026-01-10T10:00:00+05:30", "2026-01-10T09:59:00+05:30"),
        event("open-commit", "open", "committed", "2026-01-10T09:00:00+05:30", "2026-01-10T08:59:00+05:30"),
        event("closed-commit", "closed-at-cutoff", "committed", "2026-01-10T09:00:00+05:30", "2026-01-10T08:59:00+05:30"),
        event("closed-reached", "closed-at-cutoff", "milestone_reached", "2026-01-10T10:00:00+05:30", "2026-01-10T10:00:00+05:30", milestone_kind="supplier_handoff"),
        event("late-commit", "late-known-closure", "committed", "2026-01-10T09:00:00+05:30", "2026-01-10T08:59:00+05:30"),
        event("late-reached", "late-known-closure", "milestone_reached", "2026-01-10T09:30:00+05:30", "2026-01-10T10:01:00+05:30", milestone_kind="supplier_handoff"),
        event("wrong-commit", "wrong-milestone", "committed", "2026-01-10T09:00:00+05:30", "2026-01-10T08:59:00+05:30"),
        event("wrong-reached", "wrong-milestone", "milestone_reached", "2026-01-10T09:30:00+05:30", "2026-01-10T09:31:00+05:30", milestone_kind="customer_delivery"),
        event("cancel-commit", "cancelled", "committed", "2026-01-10T09:00:00+05:30", "2026-01-10T08:59:00+05:30"),
        event("cancelled-event", "cancelled", "cancelled", "2026-01-10T09:45:00+05:30", "2026-01-10T09:46:00+05:30"),
        event("same-time-commit", "same-time", "committed", "2026-01-10T10:00:00+05:30", "2026-01-10T09:59:00+05:30"),
    ]
    lineage = {
        "order_lines": lines,
        "order_line_events": events,
        "source_observations": [
            supplier_observation(item["order_line_id"], "2026-01-10T09:00:00+05:30")
            for item in lines
        ],
    }

    snapshot = resolve_supplier_load_snapshot(
        lineage,
        subject_id="subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=cutoff,
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
    )

    assert snapshot["state"] == "present"
    assert snapshot["concurrent_load_count"] == 3
    assert snapshot["contributing_order_line_ids"] == [
        "late-known-closure",
        "open",
        "wrong-milestone",
    ]
    assert snapshot["snapshot_hash"].startswith("sha256:")


def test_supplier_load_exposure_uses_expanding_history_and_keeps_variants_separate() -> None:
    lines = [line("subject")]
    events = [
        event(
            "subject-commit",
            "subject",
            "committed",
            "2026-01-11T09:00:00+05:30",
            "2026-01-11T08:59:00+05:30",
        )
    ]
    observations = [supplier_observation("subject", "2026-01-11T08:59:00+05:30")]
    for day in range(1, 11):
        line_id = f"history-{day:02d}"
        lines.append(line(line_id))
        events.append(
            event(
                f"{line_id}-commit",
                line_id,
                "committed",
                f"2026-01-{day:02d}T09:00:00+05:30",
                f"2026-01-{day:02d}T08:59:00+05:30",
            )
        )
        observations.append(
            supplier_observation(line_id, f"2026-01-{day:02d}T08:59:00+05:30")
        )

    lineage = {
        "order_lines": lines,
        "order_line_events": events,
        "source_observations": observations,
    }
    result = derive_supplier_load_exposure(
        lineage,
        subject_id="subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=normalise_temporal(
            {
                "value": "2026-01-11T09:00:00+05:30",
                "kind": "instant",
                "precision": "minute",
                "timezone_status": "known",
                "source_timezone": "Asia/Kolkata",
            }
        ),
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
        trigger_mode="reactive",
    )

    assert result["state"] == "present"
    assert result["load_snapshot"]["concurrent_load_count"] == 10
    assert result["history"]["valid_history_count"] == 10
    assert result["history"]["load_counts"] == list(range(10))
    assert result["primary"]["threshold"] == 6
    assert result["primary"]["high_load_exposure"] is True
    assert result["variants"]["stricter_threshold"]["threshold"] == 7
    assert result["variants"]["short_history"]["state"] == "present"
    assert result["variants"]["long_history"]["state"] == "ineligible"
    assert result["variants"]["continuous_load"]["state"] == "present"
    assert result["variants"]["placebo_treatment_within_supplier"]["state"] == (
        "not_run"
    )
    assert result["history"]["identity_hash"].startswith("sha256:")
    assert result["derivation_hash"].startswith("sha256:")


def test_unresolved_supplier_lineage_is_not_inferred() -> None:
    cutoff = normalise_temporal(
        {
            "value": "2026-01-10T10:00:00+05:30",
            "kind": "instant",
            "precision": "minute",
            "timezone_status": "known",
            "source_timezone": "Asia/Kolkata",
        }
    )
    lineage = {
        "order_lines": [line("subject"), line("candidate")],
        "order_line_events": [
            event(
                "subject-commit",
                "subject",
                "committed",
                "2026-01-10T10:00:00+05:30",
                "2026-01-10T09:59:00+05:30",
            ),
            event(
                "candidate-commit",
                "candidate",
                "committed",
                "2026-01-10T09:00:00+05:30",
                "2026-01-10T08:59:00+05:30",
            ),
        ],
        "source_observations": [supplier_observation("subject", "2026-01-10T09:59:00+05:30")],
    }

    snapshot = resolve_supplier_load_snapshot(
        lineage,
        subject_id="subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=cutoff,
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
    )

    assert snapshot["state"] == "unresolved"
    assert snapshot["eligibility_codes"] == ["LOAD_SNAPSHOT_UNRESOLVABLE"]
    assert snapshot["concurrent_load_count"] is None


def test_later_known_commitment_correction_cannot_rewrite_the_cutoff() -> None:
    cutoff = normalise_temporal(
        {
            "value": "2026-01-10T10:00:00+05:30",
            "kind": "instant",
            "precision": "minute",
            "timezone_status": "known",
            "source_timezone": "Asia/Kolkata",
        }
    )
    corrected = event(
        "candidate-correction",
        "candidate",
        "committed",
        "2026-01-02T09:00:00+05:30",
        "2026-01-11T09:01:00+05:30",
    )
    corrected["supersedes_event_id"] = {
        "state": "present",
        "value": "candidate-commit",
    }
    lineage = {
        "order_lines": [line("subject"), line("candidate")],
        "order_line_events": [
            event(
                "subject-commit",
                "subject",
                "committed",
                "2026-01-10T10:00:00+05:30",
                "2026-01-10T09:59:00+05:30",
            ),
            event(
                "candidate-commit",
                "candidate",
                "committed",
                "2026-01-01T09:00:00+05:30",
                "2026-01-01T08:59:00+05:30",
            ),
            corrected,
        ],
        "source_observations": [
            supplier_observation("subject", "2026-01-10T09:59:00+05:30"),
            supplier_observation("candidate", "2026-01-01T08:59:00+05:30"),
        ],
    }

    snapshot = resolve_supplier_load_snapshot(
        lineage,
        subject_id="subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=cutoff,
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
    )

    assert snapshot["state"] == "unresolved"
    assert snapshot["eligibility_codes"] == ["COMMITMENT_CUTOFF_UNUSABLE"]


def test_proactive_derivation_exposes_only_preview_fields() -> None:
    lines = [line(f"history-{day:02d}") for day in range(1, 11)]
    events = [
        event(
            f"history-{day:02d}-commit",
            f"history-{day:02d}",
            "committed",
            f"2026-01-{day:02d}T09:00:00+05:30",
            f"2026-01-{day:02d}T08:59:00+05:30",
        )
        for day in range(1, 11)
    ]
    lineage = {
        "order_lines": lines,
        "order_line_events": events,
        "source_observations": [
            supplier_observation(
                f"history-{day:02d}",
                f"2026-01-{day:02d}T08:59:00+05:30",
            )
            for day in range(1, 11)
        ],
    }
    result = derive_supplier_load_exposure(
        lineage,
        subject_id="preview-subject",
        subject_supplier_id="supplier-1",
        decision_cutoff=normalise_temporal(
            {
                "value": "2026-01-11T09:00:00+05:30",
                "kind": "instant",
                "precision": "minute",
                "timezone_status": "known",
                "source_timezone": "Asia/Kolkata",
            }
        ),
        target_milestone_kind="supplier_handoff",
        duration_basis="CALENDAR_DAY",
        trigger_mode="proactive",
    )

    serialized = json.dumps(result)
    assert result["provisional_concurrent_load_count"] == 10
    assert result["provisional_high_load_preview"] is True
    assert result["provisional_load_percentile"] == pytest.approx(1.0)
    assert "load_snapshot" not in result
    assert "high_load_exposure" not in serialized
    assert "order_line_id" not in serialized
