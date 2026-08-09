from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .canonical import sha256 as _sha256
from .fixture_boundaries import is_synthetic_fixture_identity


_PACK_ID = "core-decision-support-conformance"
_FIXTURE_NAMESPACE = "synthetic:core-decision-support-v1:"
_SUPPORTED_FACT_STATES = {"present", "missing", "unresolved"}
_SUPPORTED_LINK_STATES = {"APPROVED", "PROVISIONAL", "REJECTED", "RETIRED"}
_SUPPORTED_OPTION_CODES = (
    "PROTECTED_PRODUCTION_SLOT",
    "QUALIFIED_SOURCE_SPLIT",
    "PREQUALIFIED_ALTERNATE",
    "RELEASE_TIMING_ADJUSTMENT",
    "CAPACITY_BACKED_ACCELERATION",
    "PHASED_DELIVERY",
    "DEPENDENT_WORK_RESEQUENCING",
    "CONTRACTUAL_ESCALATION",
    "ACCEPT_AND_MONITOR",
    "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
)
_OPTION_CONTRACT = {
    "PROTECTED_PRODUCTION_SLOT": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "MILESTONE_ACCELERATION",
    },
    "QUALIFIED_SOURCE_SPLIT": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "EXPOSURE_REDUCTION",
    },
    "PREQUALIFIED_ALTERNATE": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "EXPOSURE_REDUCTION",
    },
    "RELEASE_TIMING_ADJUSTMENT": {
        "allowed_trigger_modes": ["PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "EXPOSURE_REDUCTION",
    },
    "CAPACITY_BACKED_ACCELERATION": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "MILESTONE_ACCELERATION",
    },
    "PHASED_DELIVERY": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "CONSEQUENCE_MITIGATION",
    },
    "DEPENDENT_WORK_RESEQUENCING": {
        "allowed_trigger_modes": ["REACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "CONSEQUENCE_MITIGATION",
    },
    "CONTRACTUAL_ESCALATION": {
        "allowed_trigger_modes": ["REACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "CONSEQUENCE_MITIGATION",
    },
    "ACCEPT_AND_MONITOR": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "ATOMIC",
        "component_codes": [],
        "response_class": "MONITOR_ONLY",
    },
    "PROTECTED_SLOT_WITH_PHASED_DELIVERY": {
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "shape": "COMPOSITE",
        "component_codes": ["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"],
        "response_class": "MILESTONE_ACCELERATION",
    },
}
_OPTION_RULES = {
    "PROTECTED_PRODUCTION_SLOT": (
        "PROTECTED_SLOT_MECHANISM_VERIFIED",
        "PROTECTED_SLOT_SUPPLIER_ACCEPTED",
        "PROTECTED_SLOT_WITHIN_FLOAT",
    ),
    "QUALIFIED_SOURCE_SPLIT": (
        "SPLIT_TWO_QUALIFIED_SOURCES",
        "SPLIT_SPEC_PERMITTED",
        "SPLIT_CONTRACT_PERMITTED",
        "SPLIT_MINIMUM_QUANTITIES_SATISFIED",
        "SPLIT_WITHIN_FLOAT",
    ),
    "PREQUALIFIED_ALTERNATE": (
        "ALTERNATE_CURRENTLY_QUALIFIED",
        "ALTERNATE_SUBSTITUTION_PERMITTED",
        "ALTERNATE_WORK_TRANSFERABLE",
        "ALTERNATE_WITHIN_FLOAT",
    ),
    "RELEASE_TIMING_ADJUSTMENT": (
        "RELEASE_DATE_MOVABLE",
        "RELEASE_MILESTONE_FEASIBLE",
        "RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD",
    ),
    "CAPACITY_BACKED_ACCELERATION": (
        "ACCELERATION_MECHANISM_VERIFIED",
        "ACCELERATION_SUPPLIER_ACCEPTED",
        "ACCELERATION_CONTRACT_PERMITTED",
        "ACCELERATION_WITHIN_FLOAT",
    ),
    "PHASED_DELIVERY": (
        "PHASED_HANDOFF_FEASIBLE",
        "PHASED_DOWNSTREAM_CONSUMABLE",
        "PHASED_CONTRACT_PERMITTED",
    ),
    "DEPENDENT_WORK_RESEQUENCING": (
        "RESEQUENCE_PLAN_REVIEWED",
        "RESEQUENCE_PREREQUISITES_VALID",
        "RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH",
    ),
    "CONTRACTUAL_ESCALATION": (
        "ESCALATION_BASIS_ENFORCEABLE",
        "ESCALATION_NOTICE_WINDOW_OPEN",
        "ESCALATION_RECORDS_COMPLETE",
    ),
    "ACCEPT_AND_MONITOR": (
        "MONITORING_OWNER_ASSIGNED",
        "MONITORING_REVIEW_TIME_VALID",
        "MONITORING_ESCALATION_TRIGGER_REGISTERED",
    ),
    "PROTECTED_SLOT_WITH_PHASED_DELIVERY": ("COMPOSITE_COMPONENTS_COMPATIBLE",),
}
_RULE_PRIORITIES = {
    "PROTECTED_SLOT_MECHANISM_VERIFIED": 100,
    "PROTECTED_SLOT_SUPPLIER_ACCEPTED": 110,
    "PROTECTED_SLOT_WITHIN_FLOAT": 120,
    "SPLIT_TWO_QUALIFIED_SOURCES": 200,
    "SPLIT_SPEC_PERMITTED": 210,
    "SPLIT_CONTRACT_PERMITTED": 220,
    "SPLIT_MINIMUM_QUANTITIES_SATISFIED": 230,
    "SPLIT_WITHIN_FLOAT": 240,
    "ALTERNATE_CURRENTLY_QUALIFIED": 300,
    "ALTERNATE_SUBSTITUTION_PERMITTED": 310,
    "ALTERNATE_WORK_TRANSFERABLE": 320,
    "ALTERNATE_WITHIN_FLOAT": 330,
    "RELEASE_DATE_MOVABLE": 400,
    "RELEASE_MILESTONE_FEASIBLE": 410,
    "RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD": 420,
    "ACCELERATION_MECHANISM_VERIFIED": 500,
    "ACCELERATION_SUPPLIER_ACCEPTED": 510,
    "ACCELERATION_CONTRACT_PERMITTED": 520,
    "ACCELERATION_WITHIN_FLOAT": 530,
    "PHASED_HANDOFF_FEASIBLE": 600,
    "PHASED_DOWNSTREAM_CONSUMABLE": 610,
    "PHASED_CONTRACT_PERMITTED": 620,
    "RESEQUENCE_PLAN_REVIEWED": 700,
    "RESEQUENCE_PREREQUISITES_VALID": 710,
    "RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH": 720,
    "ESCALATION_BASIS_ENFORCEABLE": 800,
    "ESCALATION_NOTICE_WINDOW_OPEN": 810,
    "ESCALATION_RECORDS_COMPLETE": 820,
    "MONITORING_OWNER_ASSIGNED": 900,
    "MONITORING_REVIEW_TIME_VALID": 910,
    "MONITORING_ESCALATION_TRIGGER_REGISTERED": 920,
    "COMPOSITE_COMPONENTS_COMPATIBLE": 1000,
}
_RULE_FACT_CODES = {
    "PROTECTED_SLOT_MECHANISM_VERIFIED": ("PROTECTED_SLOT_MECHANISM_KIND",),
    "PROTECTED_SLOT_SUPPLIER_ACCEPTED": ("PROTECTED_SLOT_SUPPLIER_ACCEPTED",),
    "PROTECTED_SLOT_WITHIN_FLOAT": (
        "TIME_TO_INITIATE_DAYS",
        "AVAILABLE_FLOAT_DAYS",
    ),
    "SPLIT_TWO_QUALIFIED_SOURCES": ("QUALIFIED_SOURCE_COUNT",),
    "SPLIT_SPEC_PERMITTED": ("SPLIT_SPEC_PERMITTED",),
    "SPLIT_CONTRACT_PERMITTED": ("SPLIT_CONTRACT_PERMITTED",),
    "SPLIT_MINIMUM_QUANTITIES_SATISFIED": ("SPLIT_MINIMUM_QUANTITIES_SATISFIED",),
    "SPLIT_WITHIN_FLOAT": ("TIME_TO_INITIATE_DAYS", "AVAILABLE_FLOAT_DAYS"),
    "ALTERNATE_CURRENTLY_QUALIFIED": ("ALTERNATE_CURRENTLY_QUALIFIED",),
    "ALTERNATE_SUBSTITUTION_PERMITTED": ("ALTERNATE_SUBSTITUTION_PERMITTED",),
    "ALTERNATE_WORK_TRANSFERABLE": ("ALTERNATE_WORK_TRANSFERABLE",),
    "ALTERNATE_WITHIN_FLOAT": ("TIME_TO_INITIATE_DAYS", "AVAILABLE_FLOAT_DAYS"),
    "RELEASE_DATE_MOVABLE": ("RELEASE_DATE_MOVABLE",),
    "RELEASE_MILESTONE_FEASIBLE": ("RELEASE_MILESTONE_FEASIBLE",),
    "RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD": ("REVISED_PROVISIONAL_HIGH_LOAD_PREVIEW",),
    "ACCELERATION_MECHANISM_VERIFIED": ("ACCELERATION_MECHANISM_KIND",),
    "ACCELERATION_SUPPLIER_ACCEPTED": ("ACCELERATION_SUPPLIER_ACCEPTED",),
    "ACCELERATION_CONTRACT_PERMITTED": ("ACCELERATION_CONTRACT_PERMITTED",),
    "ACCELERATION_WITHIN_FLOAT": (
        "TIME_TO_INITIATE_DAYS",
        "AVAILABLE_FLOAT_DAYS",
    ),
    "PHASED_HANDOFF_FEASIBLE": ("PHASED_HANDOFF_FEASIBLE",),
    "PHASED_DOWNSTREAM_CONSUMABLE": ("PHASED_DOWNSTREAM_CONSUMABLE",),
    "PHASED_CONTRACT_PERMITTED": ("PHASED_CONTRACT_PERMITTED",),
    "RESEQUENCE_PLAN_REVIEWED": ("RESEQUENCE_PLAN_REVIEWED",),
    "RESEQUENCE_PREREQUISITES_VALID": ("RESEQUENCE_PREREQUISITES_VALID",),
    "RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH": (
        "RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH",
    ),
    "ESCALATION_BASIS_ENFORCEABLE": ("ESCALATION_BASIS_ENFORCEABLE",),
    "ESCALATION_NOTICE_WINDOW_OPEN": ("ESCALATION_NOTICE_WINDOW_OPEN",),
    "ESCALATION_RECORDS_COMPLETE": ("ESCALATION_RECORDS_COMPLETE",),
    "MONITORING_OWNER_ASSIGNED": ("MONITORING_OWNER_REF",),
    "MONITORING_REVIEW_TIME_VALID": ("MONITORING_NEXT_REVIEW_AT",),
    "MONITORING_ESCALATION_TRIGGER_REGISTERED": ("MONITORING_ESCALATION_TRIGGER_REF",),
    "COMPOSITE_COMPONENTS_COMPATIBLE": ("COMPOSITE_COMPATIBILITY_REVIEW_REF",),
}
_KNOWN_FACT_CODES = {
    fact_code for fact_codes in _RULE_FACT_CODES.values() for fact_code in fact_codes
}
_DURATION_FACT_CODES = {"TIME_TO_INITIATE_DAYS", "AVAILABLE_FLOAT_DAYS"}
_BOOLEAN_FACT_CODES = {
    fact_code
    for rule_code, fact_codes in _RULE_FACT_CODES.items()
    if rule_code
    not in {
        "PROTECTED_SLOT_MECHANISM_VERIFIED",
        "PROTECTED_SLOT_WITHIN_FLOAT",
        "SPLIT_TWO_QUALIFIED_SOURCES",
        "SPLIT_WITHIN_FLOAT",
        "ALTERNATE_WITHIN_FLOAT",
        "RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD",
        "ACCELERATION_MECHANISM_VERIFIED",
        "ACCELERATION_WITHIN_FLOAT",
        "MONITORING_OWNER_ASSIGNED",
        "MONITORING_REVIEW_TIME_VALID",
        "MONITORING_ESCALATION_TRIGGER_REGISTERED",
        "COMPOSITE_COMPONENTS_COMPATIBLE",
    }
    for fact_code in fact_codes
}
_EXPECTED_ATTESTATIONS = (
    "COMPONENT_IDENTITIES_ALIGNED",
    "PROTECTED_SLOT_PHASE_PLAN_ALIGNED",
    "PHASE_TOTAL_AND_SEQUENCE_VALID",
    "COMPONENT_OBLIGATIONS_NON_CONFLICTING",
)


def _error(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "reason": reason}


def _allowed_string(value: object, allowed: set[str] | tuple[str, ...]) -> bool:
    return isinstance(value, str) and value in allowed


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _record_identifier(record: Mapping[str, Any]) -> str | None:
    for key in ("record_id", "link_id", "trigger_id", "review_id", "preview_id"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _hash_error(record: Mapping[str, Any], label: str) -> dict[str, str] | None:
    content_hash = record.get("content_hash")
    content = deepcopy(dict(record))
    content.pop("content_hash", None)
    if not isinstance(content_hash, str) or _sha256(content) != content_hash:
        return _error(
            "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            f"The synthetic {label} content binding does not match its record.",
        )
    return None


def _synthetic_record_ref(record: Mapping[str, Any]) -> dict[str, Any]:
    identifier = _record_identifier(record)
    return {
        "reference": identifier,
        "content_hash": record.get("content_hash"),
    }


def _expected_rule_ref(rule_code: str) -> str:
    return f"{_FIXTURE_NAMESPACE}constraint-rules:{rule_code.lower()}:v1"


def _fixture_subject_identity(fixture_case: Mapping[str, Any]) -> str | None:
    identity = fixture_case.get("identity")
    if not isinstance(identity, Mapping):
        return None
    trigger_mode = fixture_case.get("trigger_mode")
    key = "order_line_id" if trigger_mode == "reactive" else "preview_subject_digest"
    value = identity.get(key)
    return value if isinstance(value, str) and value else None


def _validate_fixture(fixture_case: Mapping[str, Any]) -> dict[str, str] | None:
    if not is_synthetic_fixture_identity(fixture_case):
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The fixture case is not bound to the synthetic conformance namespace.",
        )
    hash_error = _hash_error(fixture_case, "fixture case")
    if hash_error is not None:
        return hash_error
    if fixture_case.get("fixture_version") != "v1":
        return _error(
            "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
            "The synthetic fixture version is unsupported.",
        )
    if not _allowed_string(fixture_case.get("trigger_mode"), {"reactive", "proactive"}):
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The synthetic fixture trigger mode is unsupported.",
        )
    subject_identity = _fixture_subject_identity(fixture_case)
    if subject_identity is None:
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The synthetic fixture subject identity is unavailable.",
        )
    identity = fixture_case.get("identity")
    if (
        not isinstance(identity, Mapping)
        or not isinstance(identity.get("dataset_version_id"), str)
        or not isinstance(identity.get("supplier_id"), str)
    ):
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The synthetic fixture dataset and supplier identities are unavailable.",
        )
    driver_state = fixture_case.get("subject_driver_state")
    if not isinstance(driver_state, Mapping) or not isinstance(
        driver_state.get("value"), bool
    ):
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The synthetic fixture Subject Driver State is malformed.",
        )
    if driver_state.get("subject_identity") != subject_identity:
        return _error(
            "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "The synthetic fixture Subject Driver State identity disagrees with the case.",
        )
    evidence = fixture_case.get("evidence")
    subject_verdict = (
        evidence.get("subject_verdict") if isinstance(evidence, Mapping) else None
    )
    if not isinstance(subject_verdict, Mapping):
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The synthetic fixture Subject Verdict is unavailable.",
        )
    for key in (
        "decision_support_role_permitted",
        "decision_support_evaluation_permitted",
    ):
        if not isinstance(subject_verdict.get(key), bool):
            return _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                f"The synthetic fixture Subject Verdict field {key} is malformed.",
            )
    if subject_verdict.get("subject_identity") != subject_identity:
        return _error(
            "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "The synthetic fixture Subject Verdict identity disagrees with the case.",
        )
    return None


def _validate_record_collections(
    governed_records: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]] | None, dict[str, str] | None]:
    if not is_synthetic_fixture_identity(governed_records):
        return None, _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The governed records are not bound to the synthetic conformance namespace.",
        )
    if governed_records.get("fixture_pack_id") != _PACK_ID:
        return None, _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The governed records are bound to an unsupported fixture pack.",
        )
    collections: dict[str, list[dict[str, Any]]] = {}
    for collection_name in (
        "intervention_libraries",
        "driver_action_links",
        "advisory_rubrics",
        "monitoring_triggers",
        "composite_reviews",
    ):
        value = governed_records.get(collection_name)
        if not isinstance(value, list):
            return None, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                f"The governed record collection {collection_name} is malformed.",
            )
        records: list[dict[str, Any]] = []
        for record in value:
            if not isinstance(record, Mapping):
                return None, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The governed record collection {collection_name} contains a malformed record.",
                )
            record_dict = deepcopy(dict(record))
            if _record_identifier(record_dict) is None:
                return None, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The governed record collection {collection_name} contains an unbound record.",
                )
            hash_error = _hash_error(record_dict, collection_name)
            if hash_error is not None:
                return None, hash_error
            if record_dict.get("fixture_pack_id") != _PACK_ID:
                return None, _error(
                    "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                    f"A {collection_name} record is bound to a different fixture pack.",
                )
            records.append(record_dict)
        collections[collection_name] = records
    return collections, None


def _validate_library(
    collections: Mapping[str, list[dict[str, Any]]],
    fixture_case: Mapping[str, Any],
) -> tuple[
    dict[str, Any] | None, dict[str, dict[str, Any]] | None, dict[str, str] | None
]:
    libraries = collections["intervention_libraries"]
    if len(libraries) != 1:
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic intervention library does not have one unique head.",
            ),
        )
    library = libraries[0]
    refs = fixture_case.get("governed_record_refs")
    expected_library_ref = (
        refs.get("intervention_library") if isinstance(refs, Mapping) else None
    )
    if library.get("record_id") != expected_library_ref:
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic fixture library reference does not resolve to the library head.",
            ),
        )
    if (
        library.get("identifier") != "core-intervention-library"
        or library.get("version") != "1"
    ):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
                "The synthetic intervention library version is unsupported.",
            ),
        )
    if (
        library.get("state") != "BUNDLED_CLOSED"
        or library.get("lifecycle_status") != "ACTIVE"
    ):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic intervention library is not an active closed library.",
            ),
        )
    options = library.get("options")
    if not isinstance(options, list) or len(options) != len(_SUPPORTED_OPTION_CODES):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The synthetic intervention library does not expose the closed option set.",
            ),
        )
    option_index: dict[str, dict[str, Any]] = {}
    for expected_order, (option_code, option_record) in enumerate(
        zip(_SUPPORTED_OPTION_CODES, options),
        start=10,
    ):
        if not isinstance(option_record, Mapping):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "The synthetic intervention library contains a malformed option.",
                ),
            )
        option = dict(option_record)
        contract = _OPTION_CONTRACT[option_code]
        if (
            option.get("option_code") != option_code
            or option.get("option_version") != "1"
            or option.get("display_order") != expected_order
            or option.get("lifecycle_status") != "ACTIVE"
            or option.get("status") != "ACTIVE"
            or option.get("allowed_trigger_modes") != contract["allowed_trigger_modes"]
            or option.get("shape") != contract["shape"]
            or option.get("component_codes") != contract["component_codes"]
            or option.get("response_class") != contract["response_class"]
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                    f"The closed option definition for {option_code} is not exact.",
                ),
            )
        expected_refs = [
            {
                "rule_code": rule_code,
                "rule_version": "1",
                "reference": _expected_rule_ref(rule_code),
            }
            for rule_code in _OPTION_RULES[option_code]
        ]
        if option.get("required_constraint_rule_refs") != expected_refs:
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                    f"The closed rule declarations for {option_code} are not exact.",
                ),
            )
        option_index[option_code] = option
    return library, option_index, None


def _validate_links(
    collections: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str] | None]:
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for link in collections["driver_action_links"]:
        option_code = link.get("option_code")
        trigger_mode = link.get("trigger_mode")
        key = (str(option_code), str(trigger_mode))
        if not _allowed_string(
            option_code, set(_OPTION_CONTRACT)
        ) or not _allowed_string(trigger_mode, {"REACTIVE", "PROACTIVE"}):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Driver-Action Link uses an unknown option or trigger mode.",
            )
        contract = _OPTION_CONTRACT[str(option_code)]
        if trigger_mode not in contract["allowed_trigger_modes"]:
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Driver-Action Link is outside its option's trigger scope.",
            )
        if key in links:
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "Multiple synthetic Driver-Action Link heads match one option and trigger mode.",
            )
        if (
            link.get("option_version") != "1"
            or link.get("driver_code") != "SUPPLIER_CONGESTION_HIGH_LOAD"
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Driver-Action Link is not bound to the governed driver and option version.",
            )
        expected_kind = (
            "MONITORING_BASELINE"
            if option_code == "ACCEPT_AND_MONITOR"
            else "ACTION_MECHANISM"
        )
        if link.get("link_kind") != expected_kind:
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Driver-Action Link kind does not match its option.",
            )
        if not _allowed_string(
            link.get("state"), _SUPPORTED_LINK_STATES
        ) or not _allowed_string(link.get("review_status"), _SUPPORTED_LINK_STATES):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Driver-Action Link uses an unsupported lifecycle state.",
            )
        if (
            link.get("intervention_effect_estimated") is not False
            or link.get("action_effect_evidence") != "INTERVENTION_EFFECT_NOT_ESTIMATED"
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Driver-Action Link contains an effect estimate.",
            )
        if (
            not isinstance(link.get("published_at"), str)
            or _parse_time(link.get("published_at")) is None
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Driver-Action Link has no canonical publication time.",
            )
        links[key] = link
    return links, None


def _validate_supporting_registry_records(
    collections: Mapping[str, list[dict[str, Any]]],
) -> dict[str, str] | None:
    trigger_heads: set[tuple[str, str]] = set()
    for trigger in collections["monitoring_triggers"]:
        key = (str(trigger.get("option_code")), str(trigger.get("trigger_mode")))
        if (
            trigger.get("option_code") != "ACCEPT_AND_MONITOR"
            or trigger.get("option_version") != "1"
            or not _allowed_string(
                trigger.get("trigger_mode"), {"REACTIVE", "PROACTIVE"}
            )
            or not _allowed_string(trigger.get("state"), _SUPPORTED_LINK_STATES)
            or not _allowed_string(trigger.get("review_status"), _SUPPORTED_LINK_STATES)
        ):
            return _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Monitoring Escalation Trigger uses an unsupported closed identity.",
            )
        if key in trigger_heads:
            return _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "Multiple synthetic Monitoring Escalation Trigger heads match one option and trigger mode.",
            )
        trigger_heads.add(key)
    for rubric in collections["advisory_rubrics"]:
        option_code = rubric.get("option_code")
        if (
            not _allowed_string(option_code, set(_OPTION_CONTRACT))
            or rubric.get("option_version") != "1"
            or not (
                isinstance(option_code, str)
                and isinstance(rubric.get("trigger_mode"), str)
                and rubric.get("trigger_mode")
                in _OPTION_CONTRACT[option_code]["allowed_trigger_modes"]
            )
            or not _allowed_string(
                rubric.get("dimension"),
                {
                    "CONTRACTUAL_RELATIONSHIP_RISK",
                    "OPERATIONAL_DISRUPTION",
                    "REVERSIBILITY",
                },
            )
            or not _allowed_string(rubric.get("state"), _SUPPORTED_LINK_STATES)
            or not _allowed_string(rubric.get("review_status"), _SUPPORTED_LINK_STATES)
        ):
            return _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric uses an unsupported closed identity.",
            )
    return None


def _validate_snapshot(
    snapshot: Mapping[str, Any],
    fixture_case: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, dict[str, str] | None]:
    hash_error = _hash_error(snapshot, "Case Constraint Snapshot")
    if hash_error is not None:
        return None, None, hash_error
    if (
        snapshot.get("schema_identifier") != "case-constraint-snapshot"
        or snapshot.get("schema_version") != "1"
        or snapshot.get("snapshot_version") != "1"
    ):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
                "The Case Constraint Snapshot schema version is unsupported.",
            ),
        )
    snapshot_id = snapshot.get("snapshot_id")
    if (
        not isinstance(snapshot_id, str)
        or not snapshot_id
        or snapshot.get("record_id") != snapshot_id
    ):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The Case Constraint Snapshot identity is not self-consistent.",
            ),
        )
    subject_identity = _fixture_subject_identity(fixture_case)
    if snapshot.get("subject_identity") != subject_identity:
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The Case Constraint Snapshot subject identity disagrees with the fixture.",
            ),
        )
    causal_decision_at = _parse_time(snapshot.get("causal_decision_at"))
    constraints_as_of = _parse_time(snapshot.get("constraints_as_of"))
    created_at = _parse_time(snapshot.get("created_at"))
    if causal_decision_at is None or constraints_as_of is None or created_at is None:
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Case Constraint Snapshot temporal identity is malformed.",
            ),
        )
    if constraints_as_of < causal_decision_at:
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_TEMPORAL_COMPARISON_UNRESOLVED",
                "The Case Constraint Snapshot cutoff precedes the causal decision time.",
            ),
        )
    if not isinstance(snapshot.get("idempotency_key"), str) or not snapshot.get(
        "idempotency_key"
    ):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Case Constraint Snapshot idempotency key is unavailable.",
            ),
        )
    source = snapshot.get("source")
    provenance = snapshot.get("provenance")
    if (
        not isinstance(source, Mapping)
        or source.get("source_type") != "SYNTHETIC_CONFORMANCE_FIXTURE"
        or source.get("source_kind") != "synthetic_conformance"
        or not isinstance(source.get("provenance_ref"), str)
        or not isinstance(provenance, Mapping)
        or provenance.get("source_kind") != "synthetic_conformance"
    ):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The Case Constraint Snapshot source and provenance binding is not exact.",
            ),
        )
    evidence_refs = snapshot.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Case Constraint Snapshot has no immutable evidence references.",
            ),
        )
    for reference in evidence_refs:
        if (
            not isinstance(reference, Mapping)
            or not isinstance(reference.get("reference"), str)
            or not reference.get("reference")
            or not isinstance(reference.get("content_hash"), str)
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "The Case Constraint Snapshot contains a malformed evidence reference.",
                ),
            )
    facts = snapshot.get("facts")
    if not isinstance(facts, list):
        return (
            None,
            None,
            _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Case Constraint Snapshot fact list is malformed.",
            ),
        )
    normalized_facts: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, Mapping):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "The Case Constraint Snapshot contains a malformed fact.",
                ),
            )
        fact_dict = deepcopy(dict(fact))
        fact_code = fact_dict.get("fact_code")
        if not _allowed_string(fact_code, _KNOWN_FACT_CODES):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot contains unknown fact code {fact_code!r}.",
                ),
            )
        if not _allowed_string(fact_dict.get("state"), _SUPPORTED_FACT_STATES):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot fact {fact_code} has an unsupported state.",
                ),
            )
        required_fields = (
            "source_type",
            "source_record_ref",
            "provenance_ref",
            "known_at",
            "valid_through",
            "recorded_at",
        )
        if any(field not in fact_dict for field in required_fields):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot fact {fact_code} is missing provenance fields.",
                ),
            )
        if not _allowed_string(
            fact_dict.get("source_type"),
            {
                "VERIFIED_UPSTREAM_RECORD",
                "MANAGER_ATTESTATION",
            },
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot fact {fact_code} has an unsupported source type.",
                ),
            )
        if not isinstance(fact_dict.get("source_record_ref"), str) or not isinstance(
            fact_dict.get("provenance_ref"), str
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot fact {fact_code} has malformed provenance references.",
                ),
            )
        if (
            fact_dict.get("valid_through") != "NO_EXPIRY"
            and _parse_time(fact_dict.get("valid_through")) is None
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot fact {fact_code} has an invalid validity horizon.",
                ),
            )
        for temporal_field in ("known_at", "recorded_at"):
            if _parse_time(fact_dict.get(temporal_field)) is None:
                return (
                    None,
                    None,
                    _error(
                        "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                        f"The Case Constraint Snapshot fact {fact_code} has an invalid {temporal_field}.",
                    ),
                )
        if fact_dict.get("source_type") == "VERIFIED_UPSTREAM_RECORD":
            if (
                "source_available_at" not in fact_dict
                or _parse_time(fact_dict.get("source_available_at")) is None
            ):
                return (
                    None,
                    None,
                    _error(
                        "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                        f"The verified fact {fact_code} has no canonical source availability time.",
                    ),
                )
        if "option_code" in fact_dict and not _allowed_string(
            fact_dict.get("option_code"), set(_OPTION_CONTRACT)
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The Case Constraint Snapshot fact {fact_code} uses an unknown option scope.",
                ),
            )
        if "option_code" in fact_dict and fact_dict.get("option_version") != "1":
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
                    f"The Case Constraint Snapshot fact {fact_code} uses an unsupported option version.",
                ),
            )
        if fact_dict.get("state") == "present" and "value" not in fact_dict:
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The present Case Constraint Snapshot fact {fact_code} has no typed value.",
                ),
            )
        if (
            fact_code in _DURATION_FACT_CODES
            and "duration_basis" in fact_dict
            and not isinstance(fact_dict.get("duration_basis"), str)
        ):
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"The duration basis for {fact_code} is malformed.",
                ),
            )
        normalized_facts.append(fact_dict)
    return (
        {
            "snapshot": deepcopy(dict(snapshot)),
            "causal_decision_at": causal_decision_at,
            "constraints_as_of": constraints_as_of,
        },
        normalized_facts,
        None,
    )


def _validate_preview(preview: Mapping[str, Any] | None) -> dict[str, str] | None:
    if preview is None:
        return None
    hash_error = _hash_error(preview, "Release-Timing Preview")
    if hash_error is not None:
        return hash_error
    if (
        preview.get("schema_identifier") != "release-timing-preview"
        or preview.get("schema_version") != "1"
    ):
        return _error(
            "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
            "The Release-Timing Preview schema version is unsupported.",
        )
    if not isinstance(preview.get("preview_id"), str) or preview.get(
        "record_id"
    ) != preview.get("preview_id"):
        return _error(
            "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "The Release-Timing Preview identity is not self-consistent.",
        )
    if not isinstance(preview.get("provisional_high_load_preview"), bool):
        return _error(
            "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "The Release-Timing Preview threshold state is malformed.",
        )
    return None


def _validate_composite_records(
    collections: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str] | None]:
    reviews: dict[tuple[str, str], dict[str, Any]] = {}
    for record in collections["composite_reviews"]:
        option_code = record.get("option_code")
        trigger_mode = record.get("trigger_mode")
        key = (str(option_code), str(trigger_mode))
        if option_code != "PROTECTED_SLOT_WITH_PHASED_DELIVERY" or not _allowed_string(
            trigger_mode, {"REACTIVE", "PROACTIVE"}
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Composite Compatibility Review uses an unknown option or trigger mode.",
            )
        if key in reviews:
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "Multiple synthetic Composite Compatibility Review heads match one option and trigger mode.",
            )
        if (
            record.get("composite_option_code") != option_code
            or record.get("option_version") != "1"
            or record.get("component_codes")
            != ["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"]
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic Composite Compatibility Review component identity is not exact.",
            )
        reviews[key] = record
    return reviews, None


def _evidence_refs(
    facts: list[Mapping[str, Any]], extra: list[Mapping[str, Any]] | None = None
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for fact in facts:
        for key in ("source_record_ref", "provenance_ref"):
            reference = fact.get(key)
            if isinstance(reference, str) and reference:
                entry = {
                    "reference": reference,
                    "content_hash": fact.get("content_hash"),
                }
                if entry not in references:
                    references.append(entry)
    for reference in extra or []:
        if dict(reference) not in references:
            references.append(deepcopy(dict(reference)))
    return references


def _fact_candidates(
    facts: list[Mapping[str, Any]],
    fact_code: str,
    option_scope: str,
) -> list[Mapping[str, Any]]:
    exact = [
        fact
        for fact in facts
        if fact.get("fact_code") == fact_code
        and fact.get("option_code") == option_scope
    ]
    if exact:
        return exact
    if fact_code == "AVAILABLE_FLOAT_DAYS":
        return [
            fact
            for fact in facts
            if fact.get("fact_code") == fact_code and "option_code" not in fact
        ]
    if fact_code == "TIME_TO_INITIATE_DAYS":
        shared = [fact for fact in facts if fact.get("fact_code") == fact_code]
        if len(shared) == 1:
            return shared
    return []


def _eligible_fact(
    candidates: list[Mapping[str, Any]],
    *,
    constraints_as_of: datetime,
) -> tuple[Mapping[str, Any] | None, str]:
    if len(candidates) != 1:
        return None, "UNKNOWN"
    fact = candidates[0]
    if fact.get("state") != "present":
        return fact, "UNKNOWN"
    known_at = _parse_time(fact.get("known_at"))
    recorded_at = _parse_time(fact.get("recorded_at"))
    if known_at is None or recorded_at is None or known_at > constraints_as_of:
        return fact, "UNKNOWN"
    source_type = fact.get("source_type")
    if source_type == "VERIFIED_UPSTREAM_RECORD":
        source_available_at = _parse_time(fact.get("source_available_at"))
        if source_available_at is None or source_available_at > constraints_as_of:
            return fact, "UNKNOWN"
    valid_through = fact.get("valid_through")
    if valid_through != "NO_EXPIRY":
        parsed_valid_through = _parse_time(valid_through)
        if parsed_valid_through is None or constraints_as_of > parsed_valid_through:
            return fact, "UNKNOWN"
    return fact, "ELIGIBLE"


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, str) or not value.startswith("decimal:"):
        return None
    try:
        parsed = Decimal(value.split(":", 1)[1])
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _rule_result(
    *,
    rule_code: str,
    option_scope: str,
    component_scope: str | None,
    status: str,
    observed_facts: list[Mapping[str, Any]],
    explanation_code: str,
    typed_threshold: object = None,
    allowed_values: list[object] | None = None,
    extra_evidence: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rule_id": _expected_rule_ref(rule_code),
        "rule_version": "1",
        "rule_code": rule_code,
        "rule_type": "REQUIRED",
        "priority": _RULE_PRIORITIES[rule_code],
        "option_scope": option_scope,
        "component_scope": component_scope,
        "status": status,
        "observed_facts": deepcopy([dict(fact) for fact in observed_facts]),
        "typed_observed_facts": deepcopy([dict(fact) for fact in observed_facts]),
        "evidence_refs": _evidence_refs(observed_facts, extra_evidence),
        "explanation_code": explanation_code,
    }
    if typed_threshold is not None:
        result["typed_threshold"] = deepcopy(typed_threshold)
    if allowed_values is not None:
        result["allowed_values"] = deepcopy(allowed_values)
    return result


def _rule_facts(
    facts: list[Mapping[str, Any]],
    rule_code: str,
    option_scope: str,
) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    for fact_code in _RULE_FACT_CODES[rule_code]:
        candidates = _fact_candidates(facts, fact_code, option_scope)
        if len(candidates) == 1:
            selected.append(candidates[0])
        elif candidates:
            selected.extend(candidates)
    return selected


def _evaluate_composite_review(
    *,
    facts: list[Mapping[str, Any]],
    option_scope: str,
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    trigger_mode: str,
    subject_identity: str,
    composite_reviews: Mapping[tuple[str, str], dict[str, Any]],
) -> tuple[str, list[Mapping[str, Any]], str, list[Mapping[str, Any]]]:
    candidates = _fact_candidates(
        facts, "COMPOSITE_COMPATIBILITY_REVIEW_REF", option_scope
    )
    fact, eligibility = _eligible_fact(candidates, constraints_as_of=constraints_as_of)
    observed = [fact] if fact is not None else candidates
    if (
        eligibility != "ELIGIBLE"
        or fact is None
        or not isinstance(fact.get("value"), Mapping)
    ):
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_MISSING", []
    reference = fact["value"]
    review_ref = reference.get("reference")
    review_hash = reference.get("content_hash")
    review = composite_reviews.get((option_scope, trigger_mode))
    if review is None or review.get("record_id") != review_ref:
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_MISSING", []
    if review.get("content_hash") != review_hash:
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_REFERENCE_MISMATCH", []
    if (
        review.get("subject_identity") != subject_identity
        or review.get("case_constraint_snapshot_ref") != snapshot.get("snapshot_id")
        or review.get("constraints_as_of") != snapshot.get("constraints_as_of")
        or review.get("option_version") != "1"
        or review.get("trigger_mode") != trigger_mode
    ):
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_IDENTITY_MISMATCH", []
    attestations = review.get("attestations")
    if (
        review.get("criteria_schema_identifier") != "composite-compatibility-criteria"
        or review.get("criteria_schema_version") != "1"
        or not isinstance(attestations, list)
        or [
            item.get("attestation_code")
            for item in attestations
            if isinstance(item, Mapping)
        ]
        != list(_EXPECTED_ATTESTATIONS)
    ):
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_UNDER_SPECIFIED", []
    for attestation in attestations:
        if (
            not isinstance(attestation, Mapping)
            or not _allowed_string(
                attestation.get("outcome"),
                {"ATTESTED_COMPATIBLE", "ATTESTED_INCOMPATIBLE"},
            )
            or attestation.get("review_status") != "APPROVED"
            or not isinstance(attestation.get("evidence_refs"), list)
            or not attestation.get("evidence_refs")
        ):
            return "UNKNOWN", observed, "COMPOSITE_REVIEW_UNDER_SPECIFIED", []
    without_review_fact = [
        fact_item
        for fact_item in snapshot.get("facts", [])
        if fact_item.get("fact_code") != "COMPOSITE_COMPATIBILITY_REVIEW_REF"
    ]
    expected_digest = _sha256(
        {
            "snapshot_id": snapshot.get("snapshot_id"),
            "subject_identity": snapshot.get("subject_identity"),
            "causal_decision_at": snapshot.get("causal_decision_at"),
            "constraints_as_of": snapshot.get("constraints_as_of"),
            "ordered_snapshot_facts_excluding_COMPOSITE_COMPATIBILITY_REVIEW_REF": without_review_fact,
        }
    )
    if review.get("composite_compatibility_input_digest") != expected_digest:
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_REFERENCE_MISMATCH", []
    extra_evidence = [
        {
            "reference": review.get("record_id"),
            "content_hash": review.get("content_hash"),
        }
    ]
    if review.get("state") != "APPROVED" or review.get("review_status") != "APPROVED":
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_NOT_APPROVED", extra_evidence
    if (
        review.get("outcome") == "COMPATIBLE"
        and review.get("compatibility_status") == "SATISFIED"
    ):
        return "SATISFIED", observed, "COMPOSITE_REVIEW_COMPATIBLE", extra_evidence
    if review.get("outcome") == "INCOMPATIBLE":
        return "UNSATISFIED", observed, "COMPOSITE_REVIEW_INCOMPATIBLE", extra_evidence
    return "UNKNOWN", observed, "COMPOSITE_REVIEW_UNDER_SPECIFIED", extra_evidence


def _evaluate_rule(
    *,
    rule_code: str,
    option_scope: str,
    component_scope: str | None,
    facts: list[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    trigger_mode: str,
    subject_identity: str,
    links: Mapping[tuple[str, str], dict[str, Any]],
    monitoring_triggers: Mapping[tuple[str, str], dict[str, Any]],
    composite_reviews: Mapping[tuple[str, str], dict[str, Any]],
    release_preview: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if rule_code == "COMPOSITE_COMPONENTS_COMPATIBLE":
        status, review_facts, explanation, extra = _evaluate_composite_review(
            facts=facts,
            option_scope=option_scope,
            snapshot=snapshot,
            constraints_as_of=constraints_as_of,
            trigger_mode=trigger_mode,
            subject_identity=subject_identity,
            composite_reviews=composite_reviews,
        )
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=review_facts,
            explanation_code=explanation,
            extra_evidence=extra,
        )
    if rule_code in {
        "PROTECTED_SLOT_MECHANISM_VERIFIED",
        "ACCELERATION_MECHANISM_VERIFIED",
    }:
        fact_code = _RULE_FACT_CODES[rule_code][0]
        candidates = _fact_candidates(facts, fact_code, option_scope)
        fact, eligibility = _eligible_fact(
            candidates, constraints_as_of=constraints_as_of
        )
        allowed = (
            ["PROTECTED_SLOT", "CAPACITY_RESERVATION"]
            if rule_code == "PROTECTED_SLOT_MECHANISM_VERIFIED"
            else ["OVERTIME_CAPACITY", "SLOT_SWAP"]
        )
        if (
            eligibility != "ELIGIBLE"
            or fact is None
            or not isinstance(fact.get("value"), str)
        ):
            status = "UNKNOWN"
        elif fact["value"] in allowed:
            status = "SATISFIED"
        else:
            status = "UNSATISFIED"
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=[fact] if fact is not None else candidates,
            allowed_values=allowed,
            explanation_code=f"{rule_code}_{status}",
        )
    if rule_code in {
        "PROTECTED_SLOT_WITHIN_FLOAT",
        "SPLIT_WITHIN_FLOAT",
        "ALTERNATE_WITHIN_FLOAT",
        "ACCELERATION_WITHIN_FLOAT",
    }:
        time_candidates = _fact_candidates(facts, "TIME_TO_INITIATE_DAYS", option_scope)
        float_candidates = _fact_candidates(facts, "AVAILABLE_FLOAT_DAYS", option_scope)
        time_fact, time_state = _eligible_fact(
            time_candidates,
            constraints_as_of=constraints_as_of,
        )
        float_fact, float_state = _eligible_fact(
            float_candidates,
            constraints_as_of=constraints_as_of,
        )
        observed_facts = [fact for fact in (time_fact, float_fact) if fact is not None]
        time_value = _decimal(time_fact.get("value")) if time_fact is not None else None
        float_value = (
            _decimal(float_fact.get("value")) if float_fact is not None else None
        )
        same_basis = (
            time_fact is not None
            and float_fact is not None
            and isinstance(time_fact.get("duration_basis"), str)
            and time_fact.get("duration_basis") == float_fact.get("duration_basis")
        )
        if (
            time_state != "ELIGIBLE"
            or float_state != "ELIGIBLE"
            or time_value is None
            or float_value is None
            or not same_basis
        ):
            status = "UNKNOWN"
        else:
            status = "SATISFIED" if time_value <= float_value else "UNSATISFIED"
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=observed_facts,
            typed_threshold={
                "operator": "LTE",
                "time_to_initiate_days": time_fact.get("value") if time_fact else None,
                "available_float_days": float_fact.get("value") if float_fact else None,
                "duration_basis": time_fact.get("duration_basis")
                if time_fact
                else None,
            },
            explanation_code=f"{rule_code}_{status}",
        )
    if rule_code == "SPLIT_TWO_QUALIFIED_SOURCES":
        fact_code = "QUALIFIED_SOURCE_COUNT"
        candidates = _fact_candidates(facts, fact_code, option_scope)
        fact, eligibility = _eligible_fact(
            candidates, constraints_as_of=constraints_as_of
        )
        value = fact.get("value") if fact is not None else None
        status = (
            "UNKNOWN"
            if eligibility != "ELIGIBLE"
            or isinstance(value, bool)
            or not isinstance(value, int)
            else "SATISFIED"
            if value >= 2
            else "UNSATISFIED"
        )
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=[fact] if fact is not None else candidates,
            typed_threshold={"operator": "GTE", "value": 2, "value_type": "INTEGER"},
            explanation_code=f"{rule_code}_{status}",
        )
    if rule_code == "RELEASE_LOAD_PREVIEW_BELOW_THRESHOLD":
        candidates = _fact_candidates(
            facts,
            "REVISED_PROVISIONAL_HIGH_LOAD_PREVIEW",
            option_scope,
        )
        fact, eligibility = _eligible_fact(
            candidates, constraints_as_of=constraints_as_of
        )
        value = fact.get("value") if fact is not None else None
        preview_valid = False
        if isinstance(value, Mapping) and release_preview is not None:
            preview_valid = (
                value.get("preview_ref") == release_preview.get("preview_id")
                and value.get("preview_hash") == release_preview.get("content_hash")
                and isinstance(value.get("value"), bool)
                and value.get("value")
                == release_preview.get("provisional_high_load_preview")
            )
        status = "UNKNOWN"
        if eligibility == "ELIGIBLE" and preview_valid:
            status = (
                "SATISFIED"
                if release_preview.get("provisional_high_load_preview") is False
                else "UNSATISFIED"
            )
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=[fact] if fact is not None else candidates,
            typed_threshold={
                "operator": "EQ",
                "value": False,
                "preview_ref": release_preview.get("preview_id")
                if release_preview
                else None,
            },
            explanation_code=f"{rule_code}_{status}",
        )
    if rule_code == "MONITORING_OWNER_ASSIGNED":
        candidates = _fact_candidates(facts, "MONITORING_OWNER_REF", option_scope)
        fact, eligibility = _eligible_fact(
            candidates, constraints_as_of=constraints_as_of
        )
        status = (
            "SATISFIED"
            if eligibility == "ELIGIBLE"
            and isinstance(fact.get("value") if fact else None, str)
            and bool(fact.get("value"))
            else "UNKNOWN"
            if eligibility != "ELIGIBLE"
            or fact is None
            or not isinstance(fact.get("value"), str)
            else "UNSATISFIED"
        )
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=[fact] if fact is not None else candidates,
            explanation_code=f"{rule_code}_{status}",
        )
    if rule_code == "MONITORING_REVIEW_TIME_VALID":
        candidates = _fact_candidates(facts, "MONITORING_NEXT_REVIEW_AT", option_scope)
        fact, eligibility = _eligible_fact(
            candidates, constraints_as_of=constraints_as_of
        )
        review_time = _parse_time(fact.get("value") if fact else None)
        status = (
            "UNKNOWN"
            if eligibility != "ELIGIBLE" or review_time is None
            else "SATISFIED"
            if review_time > constraints_as_of
            else "UNSATISFIED"
        )
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=[fact] if fact is not None else candidates,
            typed_threshold={
                "operator": "GT",
                "value": snapshot.get("constraints_as_of"),
            },
            explanation_code=f"{rule_code}_{status}",
        )
    if rule_code == "MONITORING_ESCALATION_TRIGGER_REGISTERED":
        candidates = _fact_candidates(
            facts,
            "MONITORING_ESCALATION_TRIGGER_REF",
            option_scope,
        )
        fact, eligibility = _eligible_fact(
            candidates, constraints_as_of=constraints_as_of
        )
        trigger_ref = fact.get("value") if fact is not None else None
        trigger = None
        if isinstance(trigger_ref, Mapping):
            trigger = monitoring_triggers.get((option_scope, trigger_mode))
            if trigger is None or trigger.get("record_id") != trigger_ref.get(
                "reference"
            ):
                trigger = None
            elif trigger.get("content_hash") != trigger_ref.get("content_hash"):
                trigger = None
        trigger_valid = bool(
            trigger is not None
            and trigger.get("state") == "APPROVED"
            and trigger.get("review_status") == "APPROVED"
            and trigger.get("lifecycle_status") == "ACTIVE"
            and trigger.get("option_code") == "ACCEPT_AND_MONITOR"
            and trigger.get("option_version") == "1"
            and trigger.get("trigger_mode") == trigger_mode
            and trigger.get("response_code") == "REQUEST_MANAGER_REVIEW"
            and isinstance(trigger.get("operator"), str)
            and isinstance(trigger.get("threshold"), Mapping)
            and isinstance(trigger.get("source_refs"), list)
            and bool(trigger.get("source_refs"))
            and _parse_time(trigger.get("published_at")) is not None
            and _parse_time(trigger.get("published_at")) <= constraints_as_of
        )
        status = (
            "SATISFIED" if eligibility == "ELIGIBLE" and trigger_valid else "UNKNOWN"
        )
        return _rule_result(
            rule_code=rule_code,
            option_scope=option_scope,
            component_scope=component_scope,
            status=status,
            observed_facts=[fact] if fact is not None else candidates,
            explanation_code=f"{rule_code}_{status}",
            extra_evidence=[_synthetic_record_ref(trigger)]
            if trigger is not None
            else None,
        )
    candidates = _fact_candidates(
        facts,
        _RULE_FACT_CODES[rule_code][0],
        option_scope,
    )
    fact, eligibility = _eligible_fact(candidates, constraints_as_of=constraints_as_of)
    value = fact.get("value") if fact is not None else None
    if eligibility != "ELIGIBLE" or not isinstance(value, bool):
        status = "UNKNOWN"
    else:
        status = "SATISFIED" if value is True else "UNSATISFIED"
    return _rule_result(
        rule_code=rule_code,
        option_scope=option_scope,
        component_scope=component_scope,
        status=status,
        observed_facts=[fact] if fact is not None else candidates,
        explanation_code=f"{rule_code}_{status}",
    )


def _ordered_rule_scopes(option: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    option_code = str(option["option_code"])
    contract = _OPTION_CONTRACT[option_code]
    if contract["shape"] != "COMPOSITE":
        return [(option_code, None)]
    scopes = [
        (component_code, option_code) for component_code in contract["component_codes"]
    ]
    scopes.append((option_code, None))
    return scopes


def _option_provenance(
    option: Mapping[str, Any],
    link: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    release_preview: Mapping[str, Any] | None,
    rule_registry_ref: str,
) -> dict[str, Any]:
    provenance = {
        "intervention_option": _synthetic_record_ref(option),
        "driver_action_link": _synthetic_record_ref(link),
        "case_constraint_snapshot": _synthetic_record_ref(snapshot),
        "constraint_rule_registry": {"reference": rule_registry_ref},
    }
    if release_preview is not None:
        provenance["release_timing_preview"] = _synthetic_record_ref(release_preview)
    return provenance


def _suppression_reason(
    *,
    code: str,
    reason: str,
    rule_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "category": "CONSTRAINT" if rule_result is not None else "OPTION",
        "priority": 300
        if code == "REQUIRED_CONSTRAINT_UNSATISFIED"
        else 400
        if code == "REQUIRED_CONSTRAINT_UNKNOWN"
        else 100,
        "reason": reason,
    }
    if rule_result is not None:
        result.update(
            {
                "constraint_rule_priority": rule_result["priority"],
                "rule_code": rule_result["rule_code"],
                "option_scope": rule_result["option_scope"],
                "evidence_refs": deepcopy(rule_result["evidence_refs"]),
                "explanation_code": rule_result["explanation_code"],
            }
        )
    return result


def _build_rule_registry() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": _expected_rule_ref(rule_code),
            "rule_version": "1",
            "rule_code": rule_code,
            "rule_type": "REQUIRED",
            "priority": _RULE_PRIORITIES[rule_code],
            "fact_codes": list(_RULE_FACT_CODES[rule_code]),
            "status_set": ["SATISFIED", "UNSATISFIED", "UNKNOWN", "NOT_APPLICABLE"],
        }
        for rule_code in sorted(
            _RULE_PRIORITIES, key=lambda code: _RULE_PRIORITIES[code]
        )
    ]


def _build_registry_inspection(
    *,
    collections: Mapping[str, list[dict[str, Any]]],
    library: Mapping[str, Any],
    fixture_case: Mapping[str, Any],
) -> dict[str, Any]:
    from .decision_support import DECISION_SUPPORT_POLICY

    release_binding = fixture_case.get("release_binding")
    return {
        "inspection_kind": "GOVERNED_RECORD_INSPECTION",
        "effect_bearing": False,
        "consumed_by_evaluation": False,
        "release_binding": deepcopy(dict(release_binding))
        if isinstance(release_binding, Mapping)
        else {
            "state": "TEST_ONLY_NOT_SHIPPED",
            "release_candidate_id": None,
            "runtime_fingerprint_digest": None,
        },
        "policy": deepcopy(DECISION_SUPPORT_POLICY),
        "intervention_library": deepcopy(dict(library)),
        "driver_action_links": deepcopy(collections["driver_action_links"]),
        "advisory_rubrics": deepcopy(collections["advisory_rubrics"]),
        "monitoring_triggers": deepcopy(collections["monitoring_triggers"]),
        "composite_reviews": deepcopy(collections["composite_reviews"]),
        "constraint_rules": _build_rule_registry(),
    }


def _option_result(
    *,
    option: Mapping[str, Any],
    link: Mapping[str, Any] | None,
    trigger_mode: str,
    facts: list[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    subject_identity: str,
    links: Mapping[tuple[str, str], dict[str, Any]],
    monitoring_triggers: Mapping[tuple[str, str], dict[str, Any]],
    composite_reviews: Mapping[tuple[str, str], dict[str, Any]],
    release_preview: Mapping[str, Any] | None,
) -> dict[str, Any]:
    option_code = str(option["option_code"])
    mechanism_tag = (
        "REVIEWED_BASELINE"
        if option_code == "ACCEPT_AND_MONITOR"
        else "REVIEWED_PLAUSIBLE"
    )
    base: dict[str, Any] = {
        "display_order": option["display_order"],
        "option_code": option_code,
        "option_version": option["option_version"],
        "label": option["label"],
        "shape": option["shape"],
        "response_class": option["response_class"],
        "evaluation_state": "SUPPRESSED",
        "recommendation_eligible": False,
        "evidence_tags": {
            "DRIVER_EVIDENCE": "SUPPORTED_UNDER_ASSUMPTIONS",
            "MECHANISTIC_LINK": mechanism_tag,
            "RULE_BASED_ELIGIBILITY": "NOT_EVALUATED",
            "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
        },
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "speculative_disclosure": "ABSENT",
        "constraint_results": [],
        "suppression_reasons": [],
    }
    base["provenance"] = {
        "intervention_option": _synthetic_record_ref(option),
        "case_constraint_snapshot": _synthetic_record_ref(snapshot),
        "constraint_rule_registry": {
            "reference": _FIXTURE_NAMESPACE + "constraint-rules:v1",
        },
    }
    if link is not None:
        base["provenance"].update(
            _option_provenance(
                option,
                link,
                snapshot,
                release_preview,
                _FIXTURE_NAMESPACE + "constraint-rules:v1",
            )
        )
    if option.get("lifecycle_status") != "ACTIVE":
        base["evidence_tags"] = {
            slot: "NOT_EVALUATED"
            for slot in (
                "DRIVER_EVIDENCE",
                "MECHANISTIC_LINK",
                "RULE_BASED_ELIGIBILITY",
                "ASSUMPTION_BASED_BENEFIT",
            )
        }
        base["suppression_reasons"] = [
            _suppression_reason(
                code="OPTION_RETIRED",
                reason="The governed option version is retired at the evaluation cutoff.",
            )
        ]
        return base
    if trigger_mode not in option.get("allowed_trigger_modes", []):
        base["evidence_tags"]["MECHANISTIC_LINK"] = "NOT_EVALUATED"
        base["suppression_reasons"] = [
            _suppression_reason(
                code="TRIGGER_MODE_INCOMPATIBLE",
                reason=(
                    f"This option is not registered for the {trigger_mode.lower()} trigger mode."
                ),
            )
        ]
        return base
    if link is None:
        base["evidence_tags"]["MECHANISTIC_LINK"] = "NOT_EVALUATED"
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_MISSING",
                reason="No exact governed Driver-Action Link is available for this option and trigger mode.",
            )
        ]
        return base
    published_at = _parse_time(link.get("published_at"))
    constraints_time = _parse_time(snapshot.get("constraints_as_of"))
    if (
        published_at is None
        or constraints_time is None
        or published_at > constraints_time
    ):
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_NOT_AVAILABLE_AT_CUTOFF",
                reason="The exact Driver-Action Link is not available by the Case Constraint Snapshot cutoff.",
            )
        ]
        return base
    link_state = link.get("state")
    review_status = link.get("review_status")
    if link_state == "PROVISIONAL" or review_status == "PROVISIONAL":
        base["evidence_tags"]["MECHANISTIC_LINK"] = "PROVISIONAL"
        base["speculative_disclosure"] = "PRESENT"
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_PROVISIONAL",
                reason="The exact Driver-Action Link is provisional and cannot make an option eligible.",
            )
        ]
        return base
    if link_state == "REJECTED" or review_status == "REJECTED":
        base["evidence_tags"]["MECHANISTIC_LINK"] = "REJECTED"
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_REJECTED",
                reason="The exact Driver-Action Link is rejected and cannot make an option eligible.",
            )
        ]
        return base
    if (
        link_state == "RETIRED"
        or review_status == "RETIRED"
        or link.get("supersession_ref")
    ):
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_SUPERSEDED",
                reason="The exact Driver-Action Link has a governed successor at the evaluation cutoff.",
            )
        ]
        return base
    if link_state != "APPROVED" or review_status != "APPROVED":
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_PROVISIONAL",
                reason="The exact Driver-Action Link is not approved for eligibility.",
            )
        ]
        return base
    rule_results: list[dict[str, Any]] = []
    for rule_scope, component_scope in _ordered_rule_scopes(option):
        for rule_code in _OPTION_RULES[rule_scope]:
            rule_results.append(
                _evaluate_rule(
                    rule_code=rule_code,
                    option_scope=rule_scope,
                    component_scope=component_scope,
                    facts=facts,
                    snapshot=snapshot,
                    constraints_as_of=constraints_as_of,
                    trigger_mode=trigger_mode,
                    subject_identity=subject_identity,
                    links=links,
                    monitoring_triggers=monitoring_triggers,
                    composite_reviews=composite_reviews,
                    release_preview=release_preview,
                )
            )
    rule_results.sort(key=lambda item: (int(item["priority"]), str(item["rule_code"])))
    base["constraint_results"] = rule_results
    failing_results = [
        item for item in rule_results if item["status"] in {"UNSATISFIED", "UNKNOWN"}
    ]
    if failing_results:
        base["evaluation_state"] = "SUPPRESSED"
        base["evidence_tags"]["RULE_BASED_ELIGIBILITY"] = (
            "UNKNOWN"
            if any(item["status"] == "UNKNOWN" for item in failing_results)
            else "UNSATISFIED"
        )
        base["suppression_reasons"] = [
            _suppression_reason(
                code=(
                    "REQUIRED_CONSTRAINT_UNSATISFIED"
                    if item["status"] == "UNSATISFIED"
                    else "REQUIRED_CONSTRAINT_UNKNOWN"
                ),
                reason=(
                    f"Required rule {item['rule_code']} evaluated as {item['status']} for {item['option_scope']}."
                ),
                rule_result=item,
            )
            for item in failing_results
        ]
        base["suppression_reasons"].sort(
            key=lambda item: (
                int(item["priority"]),
                int(item["constraint_rule_priority"]),
                str(item["rule_code"]),
            )
        )
        return base
    base["evaluation_state"] = "ACTIVE"
    base["evidence_tags"]["RULE_BASED_ELIGIBILITY"] = "SATISFIED"
    return base


def _active_failure(
    *,
    result: dict[str, Any],
    error: Mapping[str, Any],
    consumed_inputs: list[str],
) -> dict[str, Any]:
    result.update(
        {
            "outcome": "FAILED",
            "state": "unavailable",
            "primary_reason_code": error["code"],
            "reason": error["reason"],
            "next_step": "Restore the closed governed records and retry the conformance evaluation.",
            "options": [],
            "suppression_reasons": [
                {
                    "code": error["code"],
                    "category": "INPUT",
                    "priority": 100,
                    "reason": error["reason"],
                }
            ],
            "consumed_inputs": consumed_inputs,
        }
    )
    return result


def evaluate_active_synthetic_conformance(
    *,
    result: dict[str, Any],
    investigation_request: Mapping[str, Any],
    subject_applicability: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
    population_verdict: Mapping[str, Any] | None,
    driver_state: Mapping[str, Any],
    synthetic_conformance: Mapping[str, Any],
) -> dict[str, Any]:
    del subject_applicability, subject_verdict, population_verdict
    fixture_case = synthetic_conformance.get("fixture_case")
    governed_records = synthetic_conformance.get("governed_records")
    if not isinstance(fixture_case, Mapping) or not isinstance(
        governed_records, Mapping
    ):
        return _active_failure(
            result=result,
            error=_error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The synthetic conformance context is missing its fixture case or governed records.",
            ),
            consumed_inputs=["permission_envelope", "subject_driver_state"],
        )
    fixture_error = _validate_fixture(fixture_case)
    if fixture_error is not None:
        return _active_failure(
            result=result,
            error=fixture_error,
            consumed_inputs=["permission_envelope", "subject_driver_state"],
        )
    collections, records_error = _validate_record_collections(governed_records)
    if records_error is not None or collections is None:
        return _active_failure(
            result=result,
            error=records_error
            or _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The synthetic governed records are unavailable.",
            ),
            consumed_inputs=["permission_envelope", "subject_driver_state"],
        )
    library, option_index, library_error = _validate_library(collections, fixture_case)
    if library_error is not None or library is None or option_index is None:
        return _active_failure(
            result=result,
            error=library_error
            or _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic intervention library is unavailable.",
            ),
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
            ],
        )
    links, links_error = _validate_links(collections)
    if links_error is not None:
        return _active_failure(
            result=result,
            error=links_error,
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
            ],
        )
    supporting_error = _validate_supporting_registry_records(collections)
    if supporting_error is not None:
        return _active_failure(
            result=result,
            error=supporting_error,
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "advisory_rubrics",
                "monitoring_triggers",
            ],
        )
    operational_inputs = fixture_case.get("operational_inputs")
    if not isinstance(operational_inputs, Mapping):
        return _active_failure(
            result=result,
            error=_error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The active synthetic fixture has no operational input envelope.",
            ),
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
            ],
        )
    snapshot_value = operational_inputs.get("case_constraint_snapshot")
    if not isinstance(snapshot_value, Mapping):
        return _active_failure(
            result=result,
            error=_error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The active synthetic fixture has no Case Constraint Snapshot.",
            ),
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "case_constraint_snapshot",
            ],
        )
    snapshot_validation, facts, snapshot_error = _validate_snapshot(
        snapshot_value, fixture_case
    )
    if snapshot_error is not None or snapshot_validation is None or facts is None:
        return _active_failure(
            result=result,
            error=snapshot_error
            or _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Case Constraint Snapshot is unavailable.",
            ),
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "case_constraint_snapshot",
            ],
        )
    snapshot = snapshot_validation["snapshot"]
    constraints_as_of = snapshot_validation["constraints_as_of"]
    preview = operational_inputs.get("release_timing_preview")
    if preview is not None and not isinstance(preview, Mapping):
        return _active_failure(
            result=result,
            error=_error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The Release-Timing Preview input is malformed.",
            ),
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "case_constraint_snapshot",
                "release_timing_preview",
            ],
        )
    preview_error = _validate_preview(preview)
    if preview_error is not None:
        return _active_failure(
            result=result,
            error=preview_error,
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "case_constraint_snapshot",
                "release_timing_preview",
            ],
        )
    trigger_mode = str(driver_state["trigger_mode"])
    subject_identity = str(driver_state["subject_identity"])
    monitoring_triggers = {
        (str(record.get("option_code")), str(record.get("trigger_mode"))): record
        for record in collections["monitoring_triggers"]
    }
    composite_reviews, composite_error = _validate_composite_records(collections)
    if composite_error is not None:
        return _active_failure(
            result=result,
            error=composite_error,
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "constraint_rules",
                "case_constraint_snapshot",
                "composite_reviews",
            ],
        )
    registry_inspection = _build_registry_inspection(
        collections=collections,
        library=library,
        fixture_case=fixture_case,
    )
    options: list[dict[str, Any]] = []
    for option_code in _SUPPORTED_OPTION_CODES:
        option = option_index[option_code]
        link = links.get((option_code, trigger_mode))
        options.append(
            _option_result(
                option=option,
                link=link,
                trigger_mode=trigger_mode,
                facts=facts,
                snapshot=snapshot,
                constraints_as_of=constraints_as_of,
                subject_identity=subject_identity,
                links=links,
                monitoring_triggers=monitoring_triggers,
                composite_reviews=composite_reviews,
                release_preview=preview,
            )
        )
    suppression_reasons: list[dict[str, Any]] = []
    for option in options:
        for reason in option["suppression_reasons"]:
            if reason not in suppression_reasons:
                suppression_reasons.append(deepcopy(reason))
    suppression_reasons.sort(
        key=lambda item: (
            int(item["priority"]),
            int(item.get("constraint_rule_priority", -1)),
            str(item.get("rule_code", item["code"])),
            str(item.get("option_scope", "")),
        )
    )
    evaluation_identity = {
        "fixture_id": fixture_case.get("fixture_id"),
        "investigation_request_id": investigation_request.get(
            "investigation_request_id"
        ),
        "subject_identity": subject_identity,
        "driver_state": deepcopy(dict(driver_state)),
        "library_content_hash": library.get("content_hash"),
        "snapshot_content_hash": snapshot.get("content_hash"),
        "trigger_mode": trigger_mode,
    }
    from .decision_support import _stable_id

    result.update(
        {
            "outcome": "NO_ELIGIBLE_OPTION",
            "state": "constraints_evaluated",
            "primary_reason_code": "CONSTRAINT_EVALUATION_COMPLETE",
            "reason": (
                "Every required constraint for every governed option was evaluated under "
                "the closed synthetic conformance registry. Benefit, value, comparison, "
                "recommendation, drafting, and authorization stages are outside this evaluation."
            ),
            "next_step": "Inspect each option's typed rule outcomes, suppression reasons, and provenance.",
            "decision_support_evaluation_id": _stable_id("dse", evaluation_identity),
            "decision_support_evaluation_series_id": _stable_id(
                "dses",
                {
                    "fixture_id": fixture_case.get("fixture_id"),
                    "subject_identity": subject_identity,
                },
            ),
            "decision_support_driver_state_digest": _sha256(dict(driver_state)),
            "decision_support_input_digest": _sha256(
                {
                    "registry_inspection": registry_inspection,
                    "case_constraint_snapshot": snapshot,
                    "options": options,
                }
            ),
            "options": options,
            "evidence_tags": {
                "DRIVER_EVIDENCE": "SUPPORTED_UNDER_ASSUMPTIONS",
                "MECHANISTIC_LINK": "REVIEWED_GOVERNED_RECORDS",
                "RULE_BASED_ELIGIBILITY": "EVALUATED",
                "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
            },
            "suppression_reasons": suppression_reasons,
            "registry_inspection": registry_inspection,
            "case_constraint_snapshot": deepcopy(snapshot),
            "constraint_rule_registry": _build_rule_registry(),
            "monitoring": {
                "state": "CONSTRAINTS_EVALUATED",
                "option_code": "ACCEPT_AND_MONITOR",
            },
            "action_recommendation": None,
            "tradeoff": None,
            "drafting": {"state": "NOT_PERMITTED"},
            "authorization": {"state": "NOT_PERMITTED"},
            "consumed_inputs": [
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "constraint_rules",
                "case_constraint_snapshot",
                "release_timing_preview",
            ],
        }
    )
    return result


def evaluate_synthetic_fixture(
    *,
    fixture_case: Mapping[str, Any],
    governed_records: Mapping[str, Any],
) -> dict[str, Any]:
    from .decision_support import evaluate_decision_support

    fixture_error = _validate_fixture(fixture_case)
    if fixture_error is not None:
        return {
            "schema_version": "decision-support-boundary.v1",
            "outcome": "FAILED",
            "state": "unavailable",
            "primary_reason_code": fixture_error["code"],
            "reason": fixture_error["reason"],
            "next_step": "Restore the synthetic conformance fixture and retry.",
            "permission": {
                "decision_support_evaluation_permitted": False,
                "denial_reason_code": fixture_error["code"],
                "reason": fixture_error["reason"],
                "next_step": "Restore the synthetic conformance fixture and retry.",
            },
            "options": [],
            "evidence_tags": {
                "DRIVER_EVIDENCE": "NOT_EVALUATED",
                "MECHANISTIC_LINK": "NOT_EVALUATED",
                "RULE_BASED_ELIGIBILITY": "NOT_EVALUATED",
                "ASSUMPTION_BASED_BENEFIT": "NOT_EVALUATED",
            },
            "suppression_reasons": [
                {
                    "code": fixture_error["code"],
                    "category": "INPUT",
                    "priority": 100,
                    "reason": fixture_error["reason"],
                }
            ],
            "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
            "action_recommendation": None,
            "tradeoff": None,
            "monitoring": {"state": "NOT_EVALUATED"},
            "drafting": {"state": "NOT_PERMITTED"},
            "authorization": {"state": "NOT_PERMITTED"},
            "consumed_inputs": [],
            "content_hash": _sha256(
                {
                    "schema_version": "decision-support-boundary.v1",
                    "outcome": "FAILED",
                    "primary_reason_code": fixture_error["code"],
                }
            ),
        }
    identity = fixture_case["identity"]
    trigger_mode = str(fixture_case["trigger_mode"])
    subject_identity = str(_fixture_subject_identity(fixture_case))
    driver = fixture_case["subject_driver_state"]
    evidence = fixture_case["evidence"]
    subject_verdict = deepcopy(dict(evidence["subject_verdict"]))
    permitted = bool(subject_verdict["decision_support_evaluation_permitted"])
    operational_inputs = fixture_case.get("operational_inputs")
    snapshot = (
        operational_inputs.get("case_constraint_snapshot")
        if isinstance(operational_inputs, Mapping)
        else None
    )
    decision_at = (
        snapshot.get("causal_decision_at") if isinstance(snapshot, Mapping) else None
    )
    primary = {
        "state": "present",
        "high_load_exposure": bool(driver["value"])
        if trigger_mode == "reactive"
        else False,
        "provisional_high_load_preview": bool(driver["value"])
        if trigger_mode == "proactive"
        else False,
    }
    request: dict[str, Any] = {
        "investigation_request_id": fixture_case["fixture_id"],
        "trigger_mode": trigger_mode,
        "subject": (
            {"order_line_id": subject_identity}
            if trigger_mode == "reactive"
            else {"preview_subject_digest": subject_identity}
        ),
        "dataset_version_id": identity["dataset_version_id"],
        "decision_cutoff": {"value": decision_at},
        "causal_engine_input": {"supplier_load_exposure": {"primary": primary}},
    }
    subject_applicability = {
        "state": "applicable" if permitted else "abstained",
        "subject_identity": subject_identity,
        "reason_code": evidence.get("permission_reason_code"),
        "reason": (
            "Synthetic conformance permission is present."
            if permitted
            else "Synthetic conformance permission is denied."
        ),
        "next_step": "Inspect the fixture evidence state.",
    }
    population_verdict = {
        "scope": "population",
        "decision_support_role_permitted": permitted,
        "decision_support_evaluation_permitted": permitted,
    }
    release_binding = fixture_case.get("release_binding")
    return evaluate_decision_support(
        investigation_request=request,
        subject_applicability=subject_applicability,
        subject_verdict=subject_verdict,
        population_verdict=population_verdict,
        intended_role="semi_synthetic_hero",
        release_candidate_id=(
            release_binding.get("release_candidate_id")
            if isinstance(release_binding, Mapping)
            else None
        ),
        runtime_fingerprint_digest=(
            release_binding.get("runtime_fingerprint_digest")
            if isinstance(release_binding, Mapping)
            else None
        ),
        synthetic_conformance={
            "fixture_case": deepcopy(dict(fixture_case)),
            "governed_records": deepcopy(dict(governed_records)),
        },
    )
