from __future__ import annotations

import pytest

from backend.app.canonical import normalise_temporal
from backend.app.risk import resolve_frozen_promise
from backend.app.risk import resolve_supplier_milestone_slippage


def temporal_field(
    value: str,
    *,
    kind: str = "date",
    precision: str | None = None,
) -> dict:
    return {
        "state": "present",
        "value": {
            "value": value,
            "kind": kind,
            "precision": precision or ("date" if kind == "date" else "minute"),
            "timezone_status": "not_applicable" if kind == "date" else "known",
            "source_timezone": None if kind == "date" else "Asia/Kolkata",
        },
    }


def missing_field() -> dict:
    return {"state": "missing"}


def event(
    event_id: str,
    kind: str,
    occurred_at: str,
    known_at: str,
    *,
    milestone_kind: str | None = None,
    promised_for: dict | None = None,
    revises_promise_event_id: str | None = None,
    supersedes_event_id: str | None = None,
    temporal_kind: str = "date",
) -> dict:
    return {
        "event_id": event_id,
        "order_line_id": "line-1",
        "kind": kind,
        "milestone_kind": (
            {"state": "present", "value": milestone_kind}
            if milestone_kind is not None
            else {"state": "not_applicable"}
        ),
        "clocks": {
            "occurred_at": temporal_field(occurred_at, kind=temporal_kind),
            "known_at": temporal_field(known_at, kind=temporal_kind),
        },
        "promised_for": promised_for or {"state": "not_applicable"},
        "revises_promise_event_id": (
            {"state": "present", "value": revises_promise_event_id}
            if revises_promise_event_id is not None
            else {"state": "not_applicable" if kind != "promise_revised" else "unresolved"}
        ),
        "supersedes_event_id": (
            {"state": "present", "value": supersedes_event_id}
            if supersedes_event_id is not None
            else missing_field()
        ),
    }


def cutoff(value: str, *, kind: str = "date"):
    return normalise_temporal(
        {
            "value": value,
            "kind": kind,
            "precision": "date" if kind == "date" else "minute",
            "timezone_status": "not_applicable" if kind == "date" else "known",
            "source_timezone": None if kind == "date" else "Asia/Kolkata",
        }
    )


def promise_event(
    event_id: str,
    occurred_at: str,
    promised_for: str,
    *,
    known_at: str | None = None,
    revises_promise_event_id: str | None = None,
    temporal_kind: str = "date",
) -> dict:
    return event(
        event_id,
        "promise_revised" if revises_promise_event_id else "promise_recorded",
        occurred_at,
        known_at or occurred_at,
        milestone_kind="supplier_handoff",
        promised_for=temporal_field(promised_for, kind=temporal_kind),
        revises_promise_event_id=revises_promise_event_id,
        temporal_kind=temporal_kind,
    )


def test_frozen_promise_selects_the_latest_known_revision_with_provenance() -> None:
    commitment = cutoff("2026-01-10")
    first = promise_event("promise-1", "2026-01-05", "2026-02-15")
    revised = promise_event(
        "promise-2",
        "2026-01-08",
        "2026-02-20",
        revises_promise_event_id="promise-1",
    )
    later = promise_event(
        "promise-3",
        "2026-01-12",
        "2026-02-25",
        revises_promise_event_id="promise-2",
    )

    resolved = resolve_frozen_promise(
        [first, revised, later],
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=commitment,
    )

    assert resolved.code is None
    assert resolved.value is not None
    assert resolved.value.field["value"]["source_value"] == "2026-02-20"
    assert resolved.event_id == "promise-2"
    assert resolved.event_ids == ("promise-1", "promise-2")


def test_signed_calendar_day_slippage_preserves_early_completion() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-22"),
        event(
            "actual",
            "milestone_reached",
            "2026-01-20",
            "2026-01-20",
            milestone_kind="supplier_handoff",
        ),
    ]

    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-25"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
        follow_up_horizon_days=0,
    )

    assert outcome["state"] == "present"
    assert outcome["supplier_milestone_slippage_days"] == -2
    assert outcome["supplier_milestone_late"] is False
    assert outcome["supplier_milestone_slippage_duration_basis"] == "CALENDAR_DAY"
    assert outcome["provenance"]["selected_promise_event_id"] == "promise"
    assert outcome["provenance"]["selected_actual_event_id"] == "actual"


def test_elapsed_day_slippage_preserves_fractional_days() -> None:
    events = [
        event(
            "commitment",
            "committed",
            "2026-01-01T09:00:00+05:30",
            "2026-01-01T09:01:00+05:30",
            temporal_kind="instant",
        ),
        promise_event(
            "promise",
            "2026-01-02T09:00:00+05:30",
            "2026-01-20T09:00:00+05:30",
            known_at="2026-01-02T09:01:00+05:30",
            temporal_kind="instant",
        ),
        event(
            "actual",
            "milestone_reached",
            "2026-01-21T21:00:00+05:30",
            "2026-01-21T21:01:00+05:30",
            milestone_kind="supplier_handoff",
            temporal_kind="instant",
        ),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03T09:00:00+05:30", kind="instant"),
        observation_cutoff=cutoff("2026-01-22T00:00:00+05:30", kind="instant"),
        canonical_slippage_duration_basis="ELAPSED_86400_SECOND_DAY",
        follow_up_horizon_days=0,
    )

    assert outcome["state"] == "present"
    assert outcome["supplier_milestone_slippage_days"] == pytest.approx(1.5)
    assert outcome["supplier_milestone_late"] is True
    assert outcome["supplier_milestone_slippage_duration_basis"] == (
        "ELAPSED_86400_SECOND_DAY"
    )


@pytest.mark.parametrize(
    ("events", "expected_code", "observation"),
    [
        (
            [
                event("commitment", "committed", "2026-01-01", "2026-01-01"),
                promise_event("promise", "2026-01-02", "2026-01-10"),
                event(
                    "actual",
                    "milestone_reached",
                    "2026-01-19",
                    "2026-01-19",
                    milestone_kind="supplier_handoff",
                ),
                event(
                    "cancel",
                    "cancelled",
                    "2026-01-18",
                    "2026-01-18",
                ),
            ],
                "CANCELLED_BEFORE_MILESTONE",
                "2026-01-20",
        ),
        (
            [
                event("commitment", "committed", "2026-01-01", "2026-01-01"),
                promise_event("promise", "2026-01-02", "2026-01-20"),
                event(
                    "actual",
                    "milestone_reached",
                    "2026-01-19",
                    "2026-01-19",
                    milestone_kind="supplier_handoff",
                ),
                event("cancel", "cancelled", "2026-01-19", "2026-01-19"),
            ],
                "OUTCOME_TEMPORALLY_INVALID",
                "2026-01-20",
        ),
        (
            [
                event("commitment", "committed", "2026-01-01", "2026-01-01"),
                promise_event("promise", "2026-01-02", "2026-01-10"),
                event(
                    "actual",
                    "milestone_reached",
                    "2026-01-19",
                    "2026-01-19",
                    milestone_kind="supplier_handoff",
                ),
            ],
                "OUTCOME_UNOBSERVED",
                "2026-01-18",
        ),
    ],
)
def test_outcome_failure_precedence_is_fail_closed(
    events: list[dict], expected_code: str, observation: str
) -> None:
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff(observation),
        canonical_slippage_duration_basis="CALENDAR_DAY",
        follow_up_horizon_days=0,
    )

    assert outcome["state"] == "unresolved"
    assert outcome["outcome_code"] == expected_code
    assert outcome["supplier_milestone_slippage_days"] is None


def test_immaturity_precedes_an_early_observed_actual() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
        event(
            "actual",
            "milestone_reached",
            "2026-01-21",
            "2026-01-21",
            milestone_kind="supplier_handoff",
        ),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-25"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
        follow_up_horizon_days=10,
    )

    assert outcome["outcome_code"] == "FOLLOW_UP_IMMATURE"
    assert outcome["supplier_milestone_slippage_days"] is None


def test_mixed_temporal_bases_are_not_converted() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
        event(
            "actual",
            "milestone_reached",
            "2026-01-21T12:00:00+05:30",
            "2026-01-21T12:01:00+05:30",
            milestone_kind="supplier_handoff",
            temporal_kind="instant",
        ),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-25"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
        follow_up_horizon_days=0,
    )

    assert outcome["outcome_code"] == "OUTCOME_TEMPORALLY_INVALID"
    assert outcome["supplier_milestone_slippage_days"] is None


def test_subject_profile_reports_basis_and_reason_without_an_estimate() -> None:
    promise = normalise_temporal(
        {
            "value": "2026-02-20",
            "kind": "date",
            "precision": "date",
            "timezone_status": "not_applicable",
            "source_timezone": None,
        }
    )
    outcome = resolve_supplier_milestone_slippage(
        [],
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-01"),
        observation_cutoff=cutoff("2026-01-10"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
        role="SUBJECT_LINE",
        frozen_promise=promise,
    )

    assert outcome["state"] == "not_applicable"
    assert outcome["role"] == "SUBJECT_LINE"
    assert outcome["canonical_slippage_duration_basis"] == "CALENDAR_DAY"
    assert outcome["outcome_code"] == "OUTCOME_NOT_REQUIRED_FOR_SUBJECT"
    assert outcome["supplier_milestone_slippage_days"] is None
    assert "actual_target_milestone" not in outcome


def test_cancellation_after_a_valid_actual_does_not_change_the_outcome() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
        event(
            "actual",
            "milestone_reached",
            "2026-01-19",
            "2026-01-19",
            milestone_kind="supplier_handoff",
        ),
        event("cancel", "cancelled", "2026-01-20", "2026-01-20"),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-21"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
    )

    assert outcome["state"] == "present"
    assert outcome["supplier_milestone_slippage_days"] == -1
    assert outcome["provenance"]["selected_actual_event_id"] == "actual"


def test_bad_foreknowledge_is_temporally_invalid_even_before_observation() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
        event(
            "actual",
            "milestone_reached",
            "2026-01-19",
            "2026-01-18",
            milestone_kind="supplier_handoff",
        ),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-21"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
    )

    assert outcome["outcome_code"] == "OUTCOME_TEMPORALLY_INVALID"


def test_unresolvable_follow_up_is_not_mislabelled_as_immature() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-21T00:00:00+05:30", kind="instant"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
        follow_up_horizon_days=0,
    )

    assert outcome["outcome_code"] == "FOLLOW_UP_UNRESOLVABLE"


def test_line_basis_mismatch_is_abstained_without_conversion() -> None:
    events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
        event(
            "actual",
            "milestone_reached",
            "2026-01-21",
            "2026-01-21",
            milestone_kind="supplier_handoff",
        ),
    ]
    outcome = resolve_supplier_milestone_slippage(
        events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-25"),
        canonical_slippage_duration_basis="ELAPSED_86400_SECOND_DAY",
    )

    assert outcome["outcome_code"] == "SLIPPAGE_DURATION_BASIS_MIXED"
    assert outcome["supplier_milestone_slippage_days"] is None


def test_supersession_cycle_and_unsupported_target_fail_closed() -> None:
    cycle_events = [
        event("commitment", "committed", "2026-01-01", "2026-01-01"),
        promise_event("promise", "2026-01-02", "2026-01-20"),
        event(
            "actual-a",
            "milestone_reached",
            "2026-01-21",
            "2026-01-21",
            milestone_kind="supplier_handoff",
            supersedes_event_id="actual-b",
        ),
        event(
            "actual-b",
            "milestone_reached",
            "2026-01-22",
            "2026-01-22",
            milestone_kind="supplier_handoff",
            supersedes_event_id="actual-a",
        ),
    ]
    cycle = resolve_supplier_milestone_slippage(
        cycle_events,
        target_milestone_kind="supplier_handoff",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-25"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
    )
    unsupported = resolve_supplier_milestone_slippage(
        [],
        target_milestone_kind="customer_delivery",
        commitment_cutoff=cutoff("2026-01-03"),
        observation_cutoff=cutoff("2026-01-25"),
        canonical_slippage_duration_basis="CALENDAR_DAY",
    )

    assert cycle["outcome_code"] == "OUTCOME_TEMPORALLY_INVALID"
    assert unsupported["outcome_code"] == "TARGET_MILESTONE_UNSUPPORTED"
