from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import sqlite3
from typing import Any, Mapping

from .canonical import sha256 as _sha256
from .tradeoff_selection import (
    GOVERNANCE_SELECTION_REFERENCE_FIELD,
    TRADEOFF_SELECTION_CLAIM_SCHEMA_IDENTIFIER,
    TRADEOFF_SELECTION_SCHEMA_VERSION,
    TradeoffSelectionContractError,
    normalize_selection,
    record_content_hash as _selection_record_content_hash,
    selection_key_for,
)


HISTORICAL_REPLAY_SCHEMA_VERSION = "historical-replay.v1"


class HistoricalReplayUnavailable(Exception):
    """The immutable historical chain cannot be reconstructed safely."""

    def __init__(self, reference: str, message: str) -> None:
        super().__init__(message)
        self.reference = reference


@dataclass(frozen=True, slots=True)
class HistoricalReplayProjection:
    snapshot: dict[str, Any]
    state: dict[str, Any]
    last_verified_event_seq: int


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _json_mapping(value: object, reference: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise HistoricalReplayUnavailable(reference, "stored historical content is not JSON") from error
    if not isinstance(parsed, Mapping):
        raise HistoricalReplayUnavailable(reference, "stored historical content is not an object")
    return dict(parsed)


def _hash_without_content_hash(value: Mapping[str, Any]) -> str:
    content = deepcopy(dict(value))
    content.pop("content_hash", None)
    return _sha256(content)


def _reference(value: object, label: str) -> dict[str, str]:
    record = _mapping(value)
    if (
        record is None
        or not isinstance(record.get("reference"), str)
        or not record.get("reference")
        or not isinstance(record.get("content_hash"), str)
        or not record.get("content_hash")
    ):
        raise HistoricalReplayUnavailable(label, f"{label} is not a content-addressed reference")
    return {
        "reference": str(record["reference"]),
        "content_hash": str(record["content_hash"]),
    }


def _same_reference(left: object, right: object) -> bool:
    try:
        return _reference(left, "left") == _reference(right, "right")
    except HistoricalReplayUnavailable:
        return False


def _audit_row(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    occurrence_id: str,
    reference: str,
    expected_kind: str | None = None,
    expected_outcome: str | None = None,
    expected_hash: str | None = None,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT * FROM audit_events
        WHERE workspace_id = ? AND occurrence_id = ?
        """,
        (workspace_id, occurrence_id),
    ).fetchone()
    if row is None:
        raise HistoricalReplayUnavailable(reference, "historical audit occurrence is missing")
    if (
        (expected_kind is not None and str(row["occurrence_kind"]) != expected_kind)
        or (expected_outcome is not None and str(row["outcome_code"]) != expected_outcome)
        or (expected_hash is not None and str(row["content_hash"]) != expected_hash)
    ):
        raise HistoricalReplayUnavailable(reference, "historical audit binding failed integrity")
    return row


def _visible_audit(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    occurrence_id: str,
    cutoff_event_seq: int,
    reference: str,
    expected_kind: str | None = None,
    expected_outcome: str | None = None,
    expected_hash: str | None = None,
) -> sqlite3.Row | None:
    row = _audit_row(
        connection,
        workspace_id=workspace_id,
        occurrence_id=occurrence_id,
        reference=reference,
        expected_kind=expected_kind,
        expected_outcome=expected_outcome,
        expected_hash=expected_hash,
    )
    return None if int(row["event_seq"]) > cutoff_event_seq else row


def _event_projection(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "occurrence_id": str(row["occurrence_id"]),
        "event_seq": int(row["event_seq"]),
        "occurrence_kind": str(row["occurrence_kind"]),
        "outcome_code": str(row["outcome_code"]),
        "content_hash": str(row["content_hash"]),
        "created_at": str(row["created_at"]),
    }


def _request_binding(snapshot: Mapping[str, Any]) -> dict[str, str]:
    request = _mapping(snapshot.get("investigation_request"))
    if request is None:
        raise HistoricalReplayUnavailable(
            "investigation-request",
            "historical Decision Brief request is unavailable",
        )
    request_id = request.get("investigation_request_id")
    content_hash = request.get("content_hash")
    if not isinstance(request_id, str) or not request_id:
        raise HistoricalReplayUnavailable(
            "investigation-request",
            "historical Investigation Request identity is unavailable",
        )
    if not isinstance(content_hash, str) or not content_hash:
        raise HistoricalReplayUnavailable(
            f"investigation-request:{request_id}",
            "historical Investigation Request hash is unavailable",
        )
    return {"record_id": request_id, "content_hash": content_hash}


def _snapshot_row(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    investigation_request_id: str,
    cutoff_event_seq: int,
    snapshot_loader: Any,
) -> tuple[dict[str, Any], sqlite3.Row]:
    row = connection.execute(
        """
        SELECT * FROM decision_brief_snapshots
        WHERE workspace_id = ?
          AND investigation_request_id = ?
          AND event_seq <= ?
        ORDER BY event_seq DESC
        LIMIT 1
        """,
        (workspace_id, investigation_request_id, cutoff_event_seq),
    ).fetchone()
    reference = f"decision-brief:{investigation_request_id}:{cutoff_event_seq}"
    if row is None:
        raise HistoricalReplayUnavailable(reference, "no Decision Brief Snapshot exists at the cutoff")
    audit = _audit_row(
        connection,
        workspace_id=workspace_id,
        occurrence_id=str(row["occurrence_id"]),
        reference=reference,
        expected_kind="DECISION_BRIEF_SNAPSHOT",
        expected_outcome="DECISION_BRIEF_PUBLISHED",
        expected_hash=str(row["content_hash"]),
    )
    if int(audit["event_seq"]) != int(row["event_seq"]):
        raise HistoricalReplayUnavailable(reference, "Decision Brief Snapshot sequence is not authoritative")
    try:
        snapshot = snapshot_loader(row)
    except Exception as error:
        raise HistoricalReplayUnavailable(reference, "Decision Brief Snapshot failed integrity") from error
    if snapshot.get("investigation_request_id") != investigation_request_id:
        raise HistoricalReplayUnavailable(reference, "Decision Brief Snapshot request binding changed")
    if int(snapshot.get("event_seq", 0)) != int(row["event_seq"]):
        raise HistoricalReplayUnavailable(reference, "Decision Brief Snapshot payload sequence changed")
    return snapshot, audit


def _series_ids(snapshot: Mapping[str, Any]) -> set[str]:
    decision_support = _mapping(snapshot.get("decision_support"))
    if decision_support is None:
        return set()
    values: set[str] = set()
    for key in (
        "decision_support_evaluation_series_id",
        "evaluation_series_id",
    ):
        value = decision_support.get(key)
        if isinstance(value, str) and value:
            values.add(value)
    lifecycle = _mapping(decision_support.get("evaluation_lifecycle"))
    if lifecycle is not None:
        value = lifecycle.get("evaluation_series_id")
        if isinstance(value, str) and value:
            values.add(value)
    return values


def _root_matches(record: Mapping[str, Any], request: Mapping[str, str]) -> bool:
    identity = _mapping(record.get("identity_binding"))
    if identity is None:
        return False
    binding = _mapping(identity.get("investigation_request"))
    return (
        binding is not None
        and binding.get("record_id") == request["record_id"]
        and binding.get("content_hash") == request["content_hash"]
    )


def _validate_series(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    evaluation_series_id: str,
    request: Mapping[str, str],
) -> None:
    row = connection.execute(
        """
        SELECT * FROM decision_support_evaluation_series
        WHERE workspace_id = ? AND evaluation_series_id = ?
        """,
        (workspace_id, evaluation_series_id),
    ).fetchone()
    reference = f"decision-support-series:{evaluation_series_id}"
    if row is None:
        raise HistoricalReplayUnavailable(reference, "Decision Support evaluation series is missing")
    identity = _json_mapping(row["identity_binding_json"], reference)
    if (
        str(row["identity_binding_hash"]) != _hash_without_content_hash(identity)
        or str(row["series_key"]) != _sha256(identity)
    ):
        raise HistoricalReplayUnavailable(reference, "Decision Support evaluation series failed integrity")
    if not _root_matches({"identity_binding": identity}, request):
        raise HistoricalReplayUnavailable(reference, "Decision Support evaluation series is bound to another request")


def _validate_recommendation(value: object, reference: str) -> dict[str, Any] | None:
    if value is None:
        return None
    recommendation = _mapping(value)
    if (
        recommendation is None
        or not isinstance(recommendation.get("occurrence_id"), str)
        or not isinstance(recommendation.get("content_hash"), str)
        or _hash_without_content_hash(recommendation) != recommendation.get("content_hash")
    ):
        raise HistoricalReplayUnavailable(reference, "stored recommendation failed integrity")
    return deepcopy(dict(recommendation))


def _evaluation_projection(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    snapshot: Mapping[str, Any],
    request: Mapping[str, str],
    cutoff_event_seq: int,
    evaluation_loader: Any,
) -> dict[str, Any] | None:
    series_ids = _series_ids(snapshot)
    rows = connection.execute(
        """
        SELECT * FROM decision_support_evaluations
        WHERE workspace_id = ?
        ORDER BY evaluation_series_id, evaluation_occurrence_id
        """,
        (workspace_id,),
    ).fetchall()
    visible: list[tuple[sqlite3.Row, dict[str, Any], sqlite3.Row]] = []
    for row in rows:
        series_id = str(row["evaluation_series_id"])
        explicit_series = series_id in series_ids
        if explicit_series:
            audit_probe = connection.execute(
                """
                SELECT event_seq FROM audit_events
                WHERE workspace_id = ? AND occurrence_id = ?
                """,
                (workspace_id, str(row["evaluation_occurrence_id"])),
            ).fetchone()
            if audit_probe is None:
                raise HistoricalReplayUnavailable(
                    f"decision-support-evaluation:{row['evaluation_occurrence_id']}",
                    "Decision Support evaluation audit occurrence is missing",
                )
            if int(audit_probe["event_seq"]) > cutoff_event_seq:
                continue
        try:
            raw = json.loads(str(row["payload_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            if explicit_series:
                raise HistoricalReplayUnavailable(
                    f"decision-support-evaluation:{row['evaluation_occurrence_id']}",
                    "stored Decision Support evaluation is not JSON",
                )
            continue
        if not isinstance(raw, Mapping):
            if explicit_series:
                raise HistoricalReplayUnavailable(
                    f"decision-support-evaluation:{row['evaluation_occurrence_id']}",
                    "stored Decision Support evaluation is not an object",
                )
            continue
        if not explicit_series and not _root_matches(raw, request):
            continue
        _validate_series(
            connection,
            workspace_id=workspace_id,
            evaluation_series_id=series_id,
            request=request,
        )
        occurrence_id = str(row["evaluation_occurrence_id"])
        audit = _visible_audit(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            cutoff_event_seq=cutoff_event_seq,
            reference=f"decision-support-evaluation:{occurrence_id}",
            expected_kind="DECISION_SUPPORT_EVALUATION",
            expected_hash=str(row["content_hash"]),
        )
        if audit is None:
            continue
        try:
            record = evaluation_loader(row)
        except Exception as error:
            raise HistoricalReplayUnavailable(
                f"decision-support-evaluation:{occurrence_id}",
                "stored Decision Support evaluation failed integrity",
            ) from error
        terminal = _mapping(record.get("terminal_result"))
        if (
            terminal is None
            or record.get("predecessor_occurrence_id")
            != row["predecessor_occurrence_id"]
            or record.get("evaluation_digest") != row["evaluation_digest"]
            or terminal.get("content_hash") != str(row["result_hash"])
            or str(audit["outcome_code"]) != str(terminal.get("outcome"))
        ):
            raise HistoricalReplayUnavailable(
                f"decision-support-evaluation:{occurrence_id}",
                "Decision Support evaluation audit binding failed integrity",
            )
        visible.append((row, record, audit))

    if not visible:
        decision_support = _mapping(snapshot.get("decision_support"))
        permission = None if decision_support is None else _mapping(
            decision_support.get("permission")
        )
        if decision_support is not None and (
            (permission is not None
             and permission.get("decision_support_evaluation_permitted") is True)
            or decision_support.get("decision_support_evaluation_id") is not None
        ):
            raise HistoricalReplayUnavailable(
                "decision-support-evaluation",
                "Decision Support evaluation referenced by the snapshot is unavailable",
            )
        return None

    visible.sort(key=lambda item: int(item[2]["event_seq"]))
    by_occurrence = {str(row["evaluation_occurrence_id"]): item for item in visible for row in [item[0]]}
    for row, record, audit in visible:
        predecessor = record.get("predecessor_occurrence_id")
        if predecessor is None:
            continue
        predecessor_item = by_occurrence.get(str(predecessor))
        if predecessor_item is None:
            predecessor_audit = _audit_row(
                connection,
                workspace_id=workspace_id,
                occurrence_id=str(predecessor),
                reference=f"decision-support-evaluation:{predecessor}",
                expected_kind="DECISION_SUPPORT_EVALUATION",
            )
            if int(predecessor_audit["event_seq"]) <= cutoff_event_seq:
                raise HistoricalReplayUnavailable(
                    f"decision-support-evaluation:{predecessor}",
                    "Decision Support evaluation predecessor is missing",
                )
            raise HistoricalReplayUnavailable(
                f"decision-support-evaluation:{row['evaluation_occurrence_id']}",
                "Decision Support evaluation points to a future predecessor",
            )

    row, record, audit = visible[-1]
    occurrence_id = str(row["evaluation_occurrence_id"])
    terminal = _mapping(record.get("terminal_result"))
    if terminal is None:
        raise HistoricalReplayUnavailable(
            f"decision-support-result:{occurrence_id}",
            "Decision Support terminal result is unavailable",
        )
    terminal_ref = {
        "reference": f"decision-support-result:{occurrence_id}",
        "content_hash": str(row["result_hash"]),
    }
    if not _same_reference(record.get("terminal_result_ref_and_hash"), terminal_ref):
        raise HistoricalReplayUnavailable(
            f"decision-support-result:{occurrence_id}",
            "Decision Support terminal result reference failed integrity",
        )
    recommendation = _validate_recommendation(
        terminal.get("action_recommendation"),
        f"decision-support-result:{occurrence_id}",
    )
    return {
        "series_id": str(row["evaluation_series_id"]),
        "record": deepcopy(record),
        "terminal_result": deepcopy(dict(terminal)),
        "evaluation_ref_and_hash": {
            "reference": f"decision-support-evaluation:{occurrence_id}",
            "content_hash": str(row["content_hash"]),
        },
        "terminal_result_ref_and_hash": terminal_ref,
        "recommendation": recommendation,
        "event": _event_projection(audit),
    }


def _claim_from_row(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    row: sqlite3.Row,
    audit: sqlite3.Row,
    evaluation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    reference = f"tradeoff-selection-claim:{row['selection_claim_occurrence_id']}"
    claim = _json_mapping(row["payload_json"], reference)
    claim_hash = str(row["content_hash"])
    if (
        claim.get("schema_identifier") != TRADEOFF_SELECTION_CLAIM_SCHEMA_IDENTIFIER
        or claim.get("schema_version") != TRADEOFF_SELECTION_SCHEMA_VERSION
        or claim.get("selection_claim_key") != str(row["selection_claim_key"])
        or claim.get("content_hash") != claim_hash
        or _hash_without_content_hash(claim) != claim_hash
        or claim.get("selection_claim_occurrence_id") != str(row["selection_claim_occurrence_id"])
        or claim.get("evaluation_series_id") != evaluation["series_id"]
        or claim.get("evaluation_occurrence_id")
        != evaluation["record"]["evaluation_occurrence_id"]
        or not _same_reference(
            claim.get("terminal_result_ref_and_hash"),
            evaluation["terminal_result_ref_and_hash"],
        )
        or claim.get("evaluation_digest") != evaluation["record"].get("evaluation_digest")
        or str(audit["occurrence_kind"]) != "DECISION_SUPPORT_TRADEOFF_SELECTION_CLAIM"
        or str(audit["outcome_code"]) != "TRADEOFF_SELECTION_ACCEPTED"
        or str(audit["content_hash"]) != claim_hash
    ):
        raise HistoricalReplayUnavailable(reference, "trade-off selection claim failed integrity")
    selection_ref = _reference(claim.get("tradeoff_selection_ref_and_hash"), reference)
    governance_ref = _reference(claim.get(GOVERNANCE_SELECTION_REFERENCE_FIELD), reference)
    selection_occurrence_id = selection_ref["reference"].split(":", 1)[-1]
    if governance_ref != {
        "reference": f"governance-tradeoff-selection:{selection_occurrence_id}",
        "content_hash": selection_ref["content_hash"],
    }:
        raise HistoricalReplayUnavailable(reference, "trade-off selection governance binding changed")
    recommendation = _validate_recommendation(claim.get("action_recommendation"), reference)
    recommendation_ref = _reference(claim.get("action_recommendation_ref_and_hash"), reference)
    if recommendation is None or recommendation_ref != {
        "reference": recommendation.get("occurrence_id") if recommendation else None,
        "content_hash": recommendation.get("content_hash") if recommendation else None,
    }:
        raise HistoricalReplayUnavailable(reference, "trade-off selection recommendation binding changed")
    if claim.get("selection_is_not_authorization") is not True:
        raise HistoricalReplayUnavailable(reference, "trade-off selection claim changed authorization semantics")
    evaluation_recommendation = evaluation.get("recommendation")
    if evaluation_recommendation is not None and not _same_reference(
        recommendation_ref,
        {
            "reference": evaluation_recommendation.get("occurrence_id"),
            "content_hash": evaluation_recommendation.get("content_hash"),
        },
    ):
        raise HistoricalReplayUnavailable(reference, "trade-off selection changed the evaluated recommendation")
    return claim, selection_ref


def _selection_from_claim(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    selection_ref: Mapping[str, str],
    cutoff_event_seq: int,
    claim_event_seq: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    occurrence_id = str(selection_ref["reference"]).split(":", 1)[-1]
    reference = f"governance-tradeoff-selection:{occurrence_id}"
    row = connection.execute(
        """
        SELECT * FROM governance_tradeoff_selections
        WHERE workspace_id = ? AND selection_occurrence_id = ?
        """,
        (workspace_id, occurrence_id),
    ).fetchone()
    if row is None:
        raise HistoricalReplayUnavailable(reference, "Governance trade-off selection is missing")
    try:
        selection = normalize_selection(json.loads(str(row["payload_json"])))
    except (TradeoffSelectionContractError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise HistoricalReplayUnavailable(reference, "Governance trade-off selection is invalid") from error
    if (
        selection.get("content_hash") != str(row["content_hash"])
        or selection.get("content_hash") != selection_ref["content_hash"]
        or _selection_record_content_hash(selection) != selection["content_hash"]
        or selection.get("selection_occurrence_id") != occurrence_id
        or selection_key_for(selection) != str(row["selection_key"])
    ):
        raise HistoricalReplayUnavailable(reference, "Governance trade-off selection failed integrity")
    audit = _visible_audit(
        connection,
        workspace_id=workspace_id,
        occurrence_id=reference,
        cutoff_event_seq=cutoff_event_seq,
        reference=reference,
        expected_kind="GOVERNANCE_TRADEOFF_SELECTION",
        expected_outcome="TRADEOFF_SELECTION_RECORDED",
        expected_hash=str(row["content_hash"]),
    )
    if audit is None or int(audit["event_seq"]) > claim_event_seq:
        raise HistoricalReplayUnavailable(reference, "Governance trade-off selection was not known before its claim")
    return selection, _event_projection(audit)


def _selection_projection(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    evaluation: Mapping[str, Any] | None,
    cutoff_event_seq: int,
) -> dict[str, Any]:
    if evaluation is None:
        return {
            "state": "NOT_PUBLISHED",
            "selection": None,
            "claim": None,
            "selection_ref_and_hash": None,
            "claim_ref_and_hash": None,
            "events": [],
        }
    rows = connection.execute(
        """
        SELECT * FROM decision_support_tradeoff_selection_claims
        WHERE workspace_id = ?
          AND evaluation_series_id = ?
          AND evaluation_occurrence_id = ?
        """,
        (
            workspace_id,
            evaluation["series_id"],
            evaluation["record"]["evaluation_occurrence_id"],
        ),
    ).fetchall()
    visible_claim: tuple[dict[str, Any], dict[str, str], dict[str, Any]] | None = None
    for row in rows:
        occurrence_id = str(row["selection_claim_occurrence_id"])
        audit = _visible_audit(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            cutoff_event_seq=cutoff_event_seq,
            reference=f"tradeoff-selection-claim:{occurrence_id}",
            expected_kind="DECISION_SUPPORT_TRADEOFF_SELECTION_CLAIM",
            expected_outcome="TRADEOFF_SELECTION_ACCEPTED",
            expected_hash=str(row["content_hash"]),
        )
        if audit is None:
            continue
        claim, selection_ref = _claim_from_row(
            connection,
            workspace_id=workspace_id,
            row=row,
            audit=audit,
            evaluation=evaluation,
        )
        visible_claim = (
            claim,
            selection_ref,
            _event_projection(audit),
        )
    if visible_claim is None:
        return {
            "state": "NOT_PUBLISHED",
            "selection": None,
            "claim": None,
            "selection_ref_and_hash": None,
            "claim_ref_and_hash": None,
            "events": [],
        }
    claim, selection_ref, claim_event = visible_claim
    selection, selection_event = _selection_from_claim(
        connection,
        workspace_id=workspace_id,
        selection_ref=selection_ref,
        cutoff_event_seq=cutoff_event_seq,
        claim_event_seq=int(claim_event["event_seq"]),
    )
    return {
        "state": "PUBLISHED",
        "selection": selection,
        "claim": claim,
        "selection_ref_and_hash": deepcopy(selection_ref),
        "claim_ref_and_hash": {
            "reference": f"tradeoff-selection-claim:{claim['selection_claim_occurrence_id']}",
            "content_hash": str(claim["content_hash"]),
        },
        "events": [selection_event, claim_event],
    }


def _manager_candidate(
    payload: Mapping[str, Any],
    *,
    evaluation: Mapping[str, Any] | None,
    request: Mapping[str, str],
) -> bool:
    tokens = {
        request["record_id"],
        request["content_hash"],
    }
    if evaluation is not None:
        tokens.update(
            {
                str(evaluation["record"]["evaluation_occurrence_id"]),
                str(evaluation["terminal_result_ref_and_hash"]["reference"]),
                str(evaluation["terminal_result_ref_and_hash"]["content_hash"]),
            }
        )
        if _same_reference(
            payload.get("terminal_result_ref_and_hash"),
            evaluation["terminal_result_ref_and_hash"],
        ):
            return True
        context = _mapping(payload.get("draft_context"))
        provenance = None if context is None else _mapping(context.get("provenance"))
        if provenance is not None and _same_reference(
            provenance.get("evaluation_result"),
            evaluation["terminal_result_ref_and_hash"],
        ):
            return True
    identity = _mapping(payload.get("evaluation"))
    if identity is not None and _root_matches(identity, request):
        return True
    serialized = json.dumps(payload, sort_keys=True)
    return any(token in serialized for token in tokens)


def _manager_projection(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    request: Mapping[str, str],
    evaluation: Mapping[str, Any] | None,
    cutoff_event_seq: int,
    manager_snapshot_loader: Any,
    manager_decision_loader: Any,
) -> dict[str, Any]:
    snapshots = connection.execute(
        """
        SELECT * FROM governance_manager_decision_snapshots
        WHERE workspace_id = ?
        ORDER BY event_seq
        """,
        (workspace_id,),
    ).fetchall()
    related: list[tuple[dict[str, Any], sqlite3.Row, sqlite3.Row, dict[str, Any]]] = []
    for row in snapshots:
        if int(row["event_seq"]) > cutoff_event_seq:
            continue
        raw = _json_mapping(row["payload_json"], f"manager-decision-snapshot:{row['snapshot_id']}")
        if not _manager_candidate(raw, evaluation=evaluation, request=request):
            continue
        occurrence_id = str(row["occurrence_id"])
        audit = _audit_row(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            reference=f"manager-decision-snapshot:{row['snapshot_id']}",
            expected_kind="MANAGER_DECISION_BRIEF_SNAPSHOT",
            expected_outcome="DECISION_BRIEF_PUBLISHED",
            expected_hash=str(row["content_hash"]),
        )
        if int(audit["event_seq"]) != int(row["event_seq"]):
            raise HistoricalReplayUnavailable(
                f"manager-decision-snapshot:{row['snapshot_id']}",
                "manager decision snapshot audit sequence changed",
            )
        try:
            payload = manager_snapshot_loader(row)
        except Exception as error:
            raise HistoricalReplayUnavailable(
                f"manager-decision-snapshot:{row['snapshot_id']}",
                "manager decision snapshot failed integrity",
            ) from error
        if int(payload.get("event_seq", 0)) != int(row["event_seq"]):
            raise HistoricalReplayUnavailable(
                f"manager-decision-snapshot:{row['snapshot_id']}",
                "manager decision snapshot sequence changed",
            )
        decision_occurrence_id = payload.get("manager_decision_occurrence_id")
        if not isinstance(decision_occurrence_id, str) or not decision_occurrence_id:
            raise HistoricalReplayUnavailable(
                f"manager-decision-snapshot:{row['snapshot_id']}",
                "manager decision occurrence binding is unavailable",
            )
        decision_row = connection.execute(
            """
            SELECT * FROM governance_manager_decisions
            WHERE workspace_id = ? AND occurrence_id = ?
            """,
            (workspace_id, decision_occurrence_id),
        ).fetchone()
        if decision_row is None or int(decision_row["event_seq"]) > cutoff_event_seq:
            raise HistoricalReplayUnavailable(
                f"manager-decision:{decision_occurrence_id}",
                "manager decision is not complete at the requested cutoff",
            )
        decision_audit = _audit_row(
            connection,
            workspace_id=workspace_id,
            occurrence_id=decision_occurrence_id,
            reference=f"manager-decision:{decision_occurrence_id}",
            expected_kind="GOVERNANCE_MANAGER_DECISION",
            expected_outcome="MANAGER_DECISION_RECORDED",
            expected_hash=str(decision_row["content_hash"]),
        )
        if int(decision_audit["event_seq"]) != int(decision_row["event_seq"]):
            raise HistoricalReplayUnavailable(
                f"manager-decision:{decision_occurrence_id}",
                "manager decision audit sequence changed",
            )
        try:
            decision = manager_decision_loader(decision_row)
        except Exception as error:
            raise HistoricalReplayUnavailable(
                f"manager-decision:{decision_occurrence_id}",
                "manager decision failed integrity",
            ) from error
        if int(decision.get("event_seq", 0)) not in {0, int(decision_row["event_seq"])}:
            raise HistoricalReplayUnavailable(
                f"manager-decision:{decision_occurrence_id}",
                "manager decision sequence changed",
            )
        related.append(
            (
                payload,
                audit,
                decision_audit,
                decision,
            )
        )

    if not related:
        return {
            "state": "NOT_RECORDED",
            "snapshot": None,
            "decision": None,
            "events": [],
        }
    related.sort(key=lambda item: int(item[2]["event_seq"]))
    payload, snapshot_audit, decision_audit, decision = related[-1]
    return {
        "state": "RECORDED",
        "snapshot": payload,
        "decision": decision,
        "events": [_event_projection(snapshot_audit), _event_projection(decision_audit)],
    }


def _draft_outcome(disposition: object) -> str:
    return {
        "NOT_DISPOSED": "DRAFT_CREATED",
        "APPROVE_INTENT": "DRAFT_APPROVAL_INTENT_RECORDED",
        "REJECTED": "DRAFT_REJECTED",
        "INVESTIGATE_FURTHER": "DRAFT_INVESTIGATION_REQUESTED",
    }.get(str(disposition), "")


def _draft_projection(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    evaluation: Mapping[str, Any] | None,
    manager: Mapping[str, Any],
    cutoff_event_seq: int,
    draft_loader: Any,
) -> dict[str, Any]:
    manager_snapshot = _mapping(manager.get("snapshot"))
    draft_ids: set[str] = set()
    if manager_snapshot is not None and isinstance(manager_snapshot.get("draft_id"), str):
        draft_ids.add(str(manager_snapshot["draft_id"]))
    evaluation_ref = None if evaluation is None else evaluation["terminal_result_ref_and_hash"]
    rows = connection.execute(
        """
        SELECT * FROM governance_draft_versions
        WHERE workspace_id = ?
        ORDER BY draft_id, version_number
        """,
        (workspace_id,),
    ).fetchall()
    histories: dict[str, list[tuple[dict[str, Any], sqlite3.Row]]] = {}
    for row in rows:
        draft_id = str(row["draft_id"])
        occurrence_id = f"draft-audit:{draft_id}:{row['version_number']}"
        audit_probe = connection.execute(
            """
            SELECT event_seq FROM audit_events
            WHERE workspace_id = ? AND occurrence_id = ?
            """,
            (workspace_id, occurrence_id),
        ).fetchone()
        if audit_probe is None:
            raise HistoricalReplayUnavailable(
                f"draft-version:{draft_id}:{row['version_number']}",
                "draft audit occurrence is missing",
            )
        if int(audit_probe["event_seq"]) > cutoff_event_seq:
            continue
        raw = _json_mapping(row["payload_json"], f"draft-version:{draft_id}:{row['version_number']}")
        candidate = draft_id in draft_ids
        if not candidate and evaluation_ref is not None:
            context = _mapping(raw.get("source_context"))
            provenance = None if context is None else _mapping(context.get("provenance"))
            artifact = _mapping(raw.get("source_artifact"))
            artifact_provenance = None if artifact is None else _mapping(artifact.get("provenance"))
            candidate = _same_reference(
                None if provenance is None else provenance.get("evaluation_result"),
                evaluation_ref,
            ) or _same_reference(
                None if artifact_provenance is None else artifact_provenance.get("evaluation_result"),
                evaluation_ref,
            )
        if not candidate:
            continue
        audit = _audit_row(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            reference=f"draft-version:{draft_id}:{row['version_number']}",
            expected_kind="GOVERNANCE_DRAFT_VERSION",
            expected_outcome=_draft_outcome(raw.get("disposition")),
            expected_hash=_sha256(
                {
                    "occurrence_id": raw.get("occurrence_id"),
                    "outcome_code": _draft_outcome(raw.get("disposition")),
                    "content_hash": raw.get("content_hash"),
                }
            ),
        )
        if audit is None:
            continue
        try:
            draft = draft_loader(row)
        except Exception as error:
            raise HistoricalReplayUnavailable(
                f"draft-version:{draft_id}:{row['version_number']}",
                "draft version failed integrity",
            ) from error
        if evaluation_ref is not None and not _same_reference(
            draft.get("evidence_ref_and_hash"), evaluation_ref
        ):
            raise HistoricalReplayUnavailable(
                f"draft-version:{draft_id}:{row['version_number']}",
                "draft evidence is not the historical evaluation result",
            )
        histories.setdefault(draft_id, []).append((draft, audit))

    if not histories:
        return {
            "state": "NOT_PUBLISHED",
            "draft_id": None,
            "source": None,
            "fallback": None,
            "head": None,
            "history": [],
            "history_refs": [],
            "edits": [],
            "events": [],
        }

    selected_id, history_rows = max(
        histories.items(),
        key=lambda item: max(int(audit["event_seq"]) for _, audit in item[1]),
    )
    history_rows.sort(key=lambda item: int(item[0]["version_number"]))
    history: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for expected_version, (draft, audit) in enumerate(history_rows, start=1):
        if int(draft.get("version_number", 0)) != expected_version:
            raise HistoricalReplayUnavailable(
                f"draft:{selected_id}",
                "historical draft version sequence has a gap",
            )
        predecessor = draft.get("predecessor_ref_and_hash_or_null")
        expected_predecessor = None if not history else {
            "reference": history[-1]["occurrence_id"],
            "content_hash": history[-1]["content_hash"],
        }
        if predecessor != expected_predecessor:
            raise HistoricalReplayUnavailable(
                f"draft-version:{selected_id}:{expected_version}",
                "historical draft predecessor chain failed integrity",
            )
        history.append(deepcopy(draft))
        events.append(_event_projection(audit))
    head = history[-1]
    if manager_snapshot is not None:
        expected_head = {
            "reference": head["occurrence_id"],
            "content_hash": head["content_hash"],
        }
        if (
            not _same_reference(manager_snapshot.get("draft_version_ref_and_hash"), expected_head)
            or manager_snapshot.get("draft_history_ref_and_hashes")
            != [
                {
                    "reference": draft["occurrence_id"],
                    "content_hash": draft["content_hash"],
                }
                for draft in history
            ]
        ):
            raise HistoricalReplayUnavailable(
                f"draft:{selected_id}",
                "manager decision snapshot and historical draft history disagree",
            )
        if evaluation is not None and (
            not _same_reference(
                manager_snapshot.get("terminal_result_ref_and_hash"),
                evaluation["terminal_result_ref_and_hash"],
            )
            or not _same_reference(
                manager_snapshot.get("evidence_ref_and_hash"),
                evaluation["terminal_result_ref_and_hash"],
            )
        ):
            raise HistoricalReplayUnavailable(
                f"manager-decision-snapshot:{manager_snapshot['snapshot_id']}",
                "manager decision snapshot and historical evidence disagree",
            )
    manager_decision = _mapping(manager.get("decision"))
    if manager_decision is not None and (
        not _same_reference(manager_decision.get("draft_version_ref_and_hash"), {
            "reference": head["occurrence_id"],
            "content_hash": head["content_hash"],
        })
        or manager_decision.get("draft_history_ref_and_hashes")
        != [
            {
                "reference": draft["occurrence_id"],
                "content_hash": draft["content_hash"],
            }
            for draft in history
        ]
    ):
        raise HistoricalReplayUnavailable(
            f"draft:{selected_id}",
            "manager decision and historical draft history disagree",
        )
    artifact = _mapping(head.get("source_artifact")) or {}
    artifact_provenance = _mapping(artifact.get("provenance")) or {}
    drafting = _mapping(artifact_provenance.get("drafting"))
    fallback = None if drafting is None else deepcopy(drafting.get("fallback"))
    return {
        "state": "PUBLISHED",
        "draft_id": selected_id,
        "source": head.get("source"),
        "fallback": fallback,
        "drafting": None if drafting is None else deepcopy(dict(drafting)),
        "head": deepcopy(head),
        "history": history,
        "history_refs": [
            {
                "reference": draft["occurrence_id"],
                "content_hash": draft["content_hash"],
            }
            for draft in history
        ],
        "edits": [
            {
                "version_number": int(draft["version_number"]),
                "reference": draft["occurrence_id"],
                "content_hash": draft["content_hash"],
                "changed_fields": deepcopy(
                    (_mapping(draft.get("manager_edits")) or {}).get("changed_fields", [])
                ),
            }
            for draft in history[1:]
        ],
        "events": events,
    }


def _known_projection(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "investigation_request": deepcopy(snapshot.get("investigation_request")),
        "ingress_attempt": deepcopy(snapshot.get("ingress_attempt")),
        "lineage": deepcopy(snapshot.get("lineage")),
        "validated_reference": deepcopy(snapshot.get("reference")),
        "subject_applicability": deepcopy(snapshot.get("subject_applicability")),
        "subject_verdict": deepcopy(snapshot.get("subject_verdict")),
        "rendered_subject_verdict": deepcopy(snapshot.get("rendered_subject_verdict")),
        "decision_brief_snapshot": {
            "reference": f"decision-brief-snapshot:{snapshot['snapshot_id']}",
            "content_hash": str(snapshot["content_hash"]),
        },
    }


def _references_projection(
    snapshot: Mapping[str, Any],
    evaluation: Mapping[str, Any] | None,
    selection: Mapping[str, Any],
    draft: Mapping[str, Any],
    manager: Mapping[str, Any],
) -> dict[str, Any]:
    references: dict[str, Any] = {
        "decision_brief_snapshot": {
            "reference": f"decision-brief-snapshot:{snapshot['snapshot_id']}",
            "content_hash": str(snapshot["content_hash"]),
        },
        "investigation_request": deepcopy(
            (_mapping(snapshot.get("referenced_records")) or {}).get("investigation_request")
        ),
        "ingress_attempt": deepcopy(
            (_mapping(snapshot.get("referenced_records")) or {}).get("ingress_attempt")
        ),
        "lineage": deepcopy(((_mapping(snapshot.get("referenced_records")) or {}).get("lineage"))),
        "validated_reference": deepcopy(
            (_mapping(snapshot.get("referenced_records")) or {}).get("validated_reference")
        ),
    }
    if evaluation is not None:
        references["evaluation"] = deepcopy(evaluation["evaluation_ref_and_hash"])
        references["terminal_result"] = deepcopy(evaluation["terminal_result_ref_and_hash"])
        if evaluation.get("recommendation") is not None:
            recommendation = evaluation["recommendation"]
            references["recommendation"] = {
                "reference": recommendation["occurrence_id"],
                "content_hash": recommendation["content_hash"],
            }
    selection_claim = _mapping(selection.get("claim"))
    if selection_claim is not None and _mapping(selection_claim.get("action_recommendation")) is not None:
        selected_recommendation = _mapping(selection_claim["action_recommendation"])
        references["recommendation"] = {
            "reference": selected_recommendation["occurrence_id"],
            "content_hash": selected_recommendation["content_hash"],
        }
    for key in ("selection_ref_and_hash", "claim_ref_and_hash"):
        if selection.get(key) is not None:
            references[key.removesuffix("_ref_and_hash")] = deepcopy(selection[key])
    if draft.get("history_refs"):
        references["draft_history"] = deepcopy(draft["history_refs"])
        references["draft_head"] = deepcopy(draft["history_refs"][-1])
    manager_snapshot = _mapping(manager.get("snapshot"))
    decision = _mapping(manager.get("decision"))
    if manager_snapshot is not None:
        references["manager_decision_snapshot"] = {
            "reference": f"decision-brief-snapshot:{manager_snapshot['snapshot_id']}",
            "content_hash": manager_snapshot["content_hash"],
        }
    if decision is not None:
        references["manager_decision"] = {
            "reference": f"manager-decision:{decision['occurrence_id']}",
            "content_hash": decision["content_hash"],
        }
    return references


def _validate_embedded_audit_bindings(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    snapshot: Mapping[str, Any],
    cutoff_event_seq: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for container_key in ("ingress_attempt", "lineage"):
        container = _mapping(snapshot.get(container_key))
        binding = None if container is None else _mapping(container.get("audit_binding"))
        if binding is None:
            continue
        occurrence_id = binding.get("occurrence_id")
        event_seq = binding.get("event_seq")
        content_hash = binding.get("content_hash") or container.get("content_hash")
        if (
            not isinstance(occurrence_id, str)
            or not isinstance(event_seq, int)
            or not isinstance(content_hash, str)
        ):
            raise HistoricalReplayUnavailable(
                f"{container_key}-audit",
                "embedded historical audit binding is malformed",
            )
        audit = _audit_row(
            connection,
            workspace_id=workspace_id,
            occurrence_id=occurrence_id,
            reference=f"{container_key}:{occurrence_id}",
            expected_hash=content_hash,
        )
        if int(audit["event_seq"]) != event_seq or event_seq > cutoff_event_seq:
            raise HistoricalReplayUnavailable(
                f"{container_key}:{occurrence_id}",
                "embedded historical audit binding is outside the requested cutoff",
            )
        events.append(_event_projection(audit))
    return events


def project_historical_replay(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    investigation_request_id: str,
    cutoff_event_seq: int,
    snapshot_loader: Any,
    evaluation_loader: Any,
    manager_snapshot_loader: Any,
    manager_decision_loader: Any,
    draft_loader: Any,
) -> HistoricalReplayProjection:
    snapshot, snapshot_audit = _snapshot_row(
        connection,
        workspace_id=workspace_id,
        investigation_request_id=investigation_request_id,
        cutoff_event_seq=cutoff_event_seq,
        snapshot_loader=snapshot_loader,
    )
    request = _request_binding(snapshot)
    embedded_events = _validate_embedded_audit_bindings(
        connection,
        workspace_id=workspace_id,
        snapshot=snapshot,
        cutoff_event_seq=cutoff_event_seq,
    )
    evaluation = _evaluation_projection(
        connection,
        workspace_id=workspace_id,
        snapshot=snapshot,
        request=request,
        cutoff_event_seq=cutoff_event_seq,
        evaluation_loader=evaluation_loader,
    )
    selection = _selection_projection(
        connection,
        workspace_id=workspace_id,
        evaluation=evaluation,
        cutoff_event_seq=cutoff_event_seq,
    )
    manager = _manager_projection(
        connection,
        workspace_id=workspace_id,
        request=request,
        evaluation=evaluation,
        cutoff_event_seq=cutoff_event_seq,
        manager_snapshot_loader=manager_snapshot_loader,
        manager_decision_loader=manager_decision_loader,
    )
    draft = _draft_projection(
        connection,
        workspace_id=workspace_id,
        evaluation=evaluation,
        manager=manager,
        cutoff_event_seq=cutoff_event_seq,
        draft_loader=draft_loader,
    )
    events = [
        _event_projection(snapshot_audit),
        *embedded_events,
        *([] if evaluation is None else [evaluation["event"]]),
        *selection["events"],
        *draft["events"],
        *manager["events"],
    ]
    unique_events = {
        int(event["event_seq"]): event
        for event in events
        if int(event["event_seq"]) <= cutoff_event_seq
    }
    ordered_events = [unique_events[key] for key in sorted(unique_events)]
    evidence = {
        "subject_verdict": deepcopy(snapshot.get("subject_verdict")),
        "population_verdict": deepcopy(
            (_mapping(snapshot.get("reference")) or {}).get("evidence_verdict")
        ),
        "decision_support": deepcopy(snapshot.get("decision_support")),
        "evaluation": None if evaluation is None else deepcopy(evaluation["record"]),
        "terminal_result": None
        if evaluation is None
        else deepcopy(evaluation["terminal_result"]),
    }
    selection_claim = _mapping(selection.get("claim"))
    selected_recommendation = (
        None
        if selection_claim is None
        else _mapping(selection_claim.get("action_recommendation"))
    )
    recommendation_record = selected_recommendation or (
        None if evaluation is None else evaluation.get("recommendation")
    )
    recommendation = {
        "state": "NOT_PUBLISHED" if recommendation_record is None else "PUBLISHED",
        "record": None
        if recommendation_record is None
        else deepcopy(dict(recommendation_record)),
        "reference": None
        if recommendation_record is None
        else {
            "reference": recommendation_record["occurrence_id"],
            "content_hash": recommendation_record["content_hash"],
        },
        "source": (
            "DECISION_SUPPORT_TRADEOFF_SELECTION_CLAIM"
            if selected_recommendation is not None
            else "DECISION_SUPPORT_EVALUATION"
            if evaluation is not None and evaluation.get("recommendation") is not None
            else None
        ),
        "tradeoff": None
        if evaluation is None
        else deepcopy(evaluation["terminal_result"].get("tradeoff")),
    }
    disposition = {
        "state": (
            "NOT_RECORDED"
            if draft["state"] == "NOT_PUBLISHED"
            else str((_mapping(draft["head"]) or {}).get("disposition", "NOT_DISPOSED"))
        ),
        "actor": None
        if draft["state"] == "NOT_PUBLISHED"
        else (_mapping(draft["head"]) or {}).get("manager_actor_ref"),
    }
    state: dict[str, Any] = {
        "schema_version": HISTORICAL_REPLAY_SCHEMA_VERSION,
        "investigation_request_id": investigation_request_id,
        "cutoff_event_seq": cutoff_event_seq,
        "historical": True,
        "read_only": True,
        "known": _known_projection(snapshot),
        "evidence": evidence,
        "recommendation": recommendation,
        "tradeoff_selection": selection,
        "selection": deepcopy(selection),
        "draft": draft,
        "disposition": disposition,
        "decision": {
            "state": manager["state"],
            "record": deepcopy(manager["decision"]),
        },
        "manager_decision": deepcopy(manager["decision"]),
        "references": _references_projection(
            snapshot,
            evaluation,
            selection,
            draft,
            manager,
        ),
        "occurrences": ordered_events,
        "presentation": {
            "mode": "HISTORICAL_READ_ONLY",
            "current_policy_consulted": False,
            "currentness_consulted": False,
            "source_adapter_consulted": False,
            "replay_basis": "IMMUTABLE_PERSISTED_OCCURRENCES_AT_CUTOFF",
        },
    }
    last_verified = max(
        [int(snapshot_audit["event_seq"]), *[int(event["event_seq"]) for event in ordered_events]]
    )
    return HistoricalReplayProjection(
        snapshot=snapshot,
        state=state,
        last_verified_event_seq=last_verified,
    )
