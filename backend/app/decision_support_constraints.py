from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .canonical import sha256 as _sha256
from .decision_support_value import (
    ValueContext,
    canonical_value_inputs,
    prepare_value_inputs,
    project_option_value,
)
from .decision_support_comparison import (
    compare_and_publish,
    comparison_dimensions_for_option,
)
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
_ADVISORY_DIMENSIONS = (
    "CONTRACTUAL_RELATIONSHIP_RISK",
    "OPERATIONAL_DISRUPTION",
    "REVERSIBILITY",
)
_ADVISORY_OUTPUTS = {
    "CONTRACTUAL_RELATIONSHIP_RISK": ("LOW", "MEDIUM", "HIGH"),
    "OPERATIONAL_DISRUPTION": ("LOW", "MEDIUM", "HIGH"),
    "REVERSIBILITY": (
        "EASILY_REVERSIBLE",
        "PARTIALLY_REVERSIBLE",
        "DIFFICULT_TO_REVERSE",
    ),
}
_ADVISORY_DIRECTIONS = {
    "CONTRACTUAL_RELATIONSHIP_RISK": "LOWER_IS_MORE_FAVORABLE",
    "OPERATIONAL_DISRUPTION": "LOWER_IS_MORE_FAVORABLE",
    "REVERSIBILITY": "MORE_REVERSIBLE_IS_MORE_FAVORABLE",
}
_ADVISORY_REASON_PRIORITIES = {
    "RUBRIC_UNAVAILABLE": 100,
    "RUBRIC_NOT_APPROVED": 110,
    "RUBRIC_NOT_APPLICABLE": 120,
    "RUBRIC_INPUT_MISSING": 200,
    "RUBRIC_INPUT_INVALID": 210,
    "RUBRIC_INPUT_CONFLICT": 220,
    "RUBRIC_RULE_NO_MATCH": 300,
    "RUBRIC_RULE_AMBIGUOUS": 310,
    "RUBRIC_COMPONENT_RESULT_UNKNOWN": 320,
}
_ADVISORY_VALUE_TYPES = {"BOOLEAN", "INTEGER", "DECIMAL", "STRING"}
_ADVISORY_OPERATORS = {"EQ", "GTE", "LTE"}


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
        expected_advisory_declarations = (
            [
                {
                    "dimension": dimension,
                    "trigger_mode": trigger_mode,
                    "rubric_reference": (
                        f"{_FIXTURE_NAMESPACE}advisory-rubrics:"
                        f"{option_code.lower()}:{trigger_mode.lower()}:"
                        f"{dimension.lower()}:v1"
                    ),
                }
                for trigger_mode in contract["allowed_trigger_modes"]
                for dimension in _ADVISORY_DIMENSIONS
            ]
            if contract["shape"] == "ATOMIC"
            else []
        )
        expected_advisory_derivation = (
            None
            if contract["shape"] == "ATOMIC"
            else {"kind": "LEAST_FAVORABLE_COMPONENT_RESULTS.v1"}
        )
        declarations = option.get("advisory_rubric_declarations")
        declarations_match = (
            declarations == []
            if contract["shape"] != "ATOMIC"
            else isinstance(declarations, list)
            and len(declarations) == len(expected_advisory_declarations)
            and all(
                isinstance(actual, Mapping)
                and actual.get("dimension") == expected["dimension"]
                and actual.get("trigger_mode") == expected["trigger_mode"]
                and actual.get("rubric_reference")
                in {expected["rubric_reference"], "UNAVAILABLE_PENDING_REVIEW"}
                for actual, expected in zip(
                    declarations, expected_advisory_declarations
                )
            )
        )
        if not declarations_match or option.get("advisory_derivation") != expected_advisory_derivation:
            return (
                None,
                None,
                _error(
                    "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                    f"The advisory declarations for {option_code} are not exact.",
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


def _valid_evidence_refs(value: object) -> bool:
    return bool(
        isinstance(value, list)
        and value
        and all(
            isinstance(reference, Mapping)
            and isinstance(reference.get("reference"), str)
            and bool(reference.get("reference"))
            and isinstance(reference.get("content_hash"), str)
            and bool(reference.get("content_hash"))
            for reference in value
        )
    )


def _validate_advisory_rubric_records(
    collections: Mapping[str, list[dict[str, Any]]],
    option_index: Mapping[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str] | None]:
    rubrics_by_reference: dict[str, dict[str, Any]] = {}
    rubric_keys: set[tuple[str, str, str, str]] = set()
    for rubric in collections["advisory_rubrics"]:
        record_id = rubric.get("record_id")
        option_code = rubric.get("option_code")
        trigger_mode = rubric.get("trigger_mode")
        dimension = rubric.get("dimension")
        key = (str(option_code), str(rubric.get("option_version")), str(trigger_mode), str(dimension))
        expected_reference = (
            f"{_FIXTURE_NAMESPACE}advisory-rubrics:"
            f"{str(option_code).lower()}:{str(trigger_mode).lower()}:"
            f"{str(dimension).lower()}:v1"
        )
        if (
            not isinstance(record_id, str)
            or rubric.get("rubric_id") != record_id
            or record_id != expected_reference
            or rubric.get("rubric_version") != "1"
            or rubric.get("schema_identifier") != "advisory-rubric"
            or rubric.get("schema_version") != "1"
            or rubric.get("registry_identifier") != "decision-support-advisory-rubrics"
            or rubric.get("registry_version", "1") != "1"
            or not _allowed_string(option_code, set(option_index))
            or rubric.get("option_version") != "1"
            or not isinstance(trigger_mode, str)
            or trigger_mode not in _OPTION_CONTRACT[str(option_code)]["allowed_trigger_modes"]
            or not _allowed_string(dimension, _ADVISORY_DIMENSIONS)
            or key in rubric_keys
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Advisory Rubric uses a duplicate or unsupported identity.",
            )
        applicability = rubric.get("applicability")
        if applicability != {
            "option_code": option_code,
            "option_version": "1",
            "trigger_mode": trigger_mode,
        }:
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Advisory Rubric applicability declaration is not exact.",
            )
        if not _allowed_string(rubric.get("lifecycle_status"), {"ACTIVE", "RETIRED"}):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric uses an unsupported lifecycle status.",
            )
        if not _allowed_string(rubric.get("state"), _SUPPORTED_LINK_STATES) or not _allowed_string(
            rubric.get("review_status"), _SUPPORTED_LINK_STATES
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric uses an unsupported approval status.",
            )
        for field in ("published_at", "review_available_at"):
            if _parse_time(rubric.get(field)) is None:
                return {}, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"A synthetic Advisory Rubric has an invalid {field}.",
                )
        for field in ("review_date", "reviewed_at"):
            if _parse_time(rubric.get(field)) is None:
                return {}, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    f"A synthetic Advisory Rubric has an invalid {field}.",
                )
        published_at = _parse_time(rubric.get("published_at"))
        review_date = _parse_time(rubric.get("review_date"))
        review_available_at = _parse_time(rubric.get("review_available_at"))
        if (
            published_at is not None
            and review_date is not None
            and review_date > published_at
        ) or (
            published_at is not None
            and review_available_at is not None
            and review_available_at > published_at
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Advisory Rubric review is published before its review evidence is available.",
            )
        if not isinstance(rubric.get("review_reference"), str) or not rubric.get(
            "review_reference"
        ) or not isinstance(rubric.get("review_reason_code"), str) or not rubric.get(
            "review_reason_code"
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric has incomplete review provenance.",
            )
        if (
            rubric.get("approval_scope") != "SYNTHETIC_CONFORMANCE_ONLY"
            or rubric.get("contract_status") != "SYNTHETIC_CONFORMANCE_ONLY"
            or rubric.get("reviewer_role") != "SYNTHETIC_CONFORMANCE_REVIEW"
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Advisory Rubric has an ungoverned approval scope.",
            )
        provenance = rubric.get("provenance")
        if (
            not isinstance(provenance, Mapping)
            or provenance.get("source_kind") != "synthetic_conformance"
            or provenance.get("source_namespace") != "synthetic://core-decision-support/v1"
            or provenance.get("production_authority") != "PROHIBITED"
            or provenance.get("external_evaluation_eligibility") != "PROHIBITED"
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Advisory Rubric has incomplete provenance binding.",
            )
        if not _valid_evidence_refs(rubric.get("source_refs")):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric has no ordered evidence references.",
            )
        result_contract = rubric.get("result_contract")
        if (
            not isinstance(result_contract, Mapping)
            or result_contract.get("unknown_code") != "UNKNOWN"
            or result_contract.get("allowed_values")
            != list(_ADVISORY_OUTPUTS[str(dimension)])
            or result_contract.get("direction")
            != (
                "lower_is_more_favorable"
                if dimension != "REVERSIBILITY"
                else "more_reversible_is_more_favorable"
            )
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Advisory Rubric result contract is not exact.",
            )
        declarations = rubric.get("typed_input_declarations")
        if not isinstance(declarations, list) or not declarations:
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric has no typed input declarations.",
            )
        declared_fact_codes: list[str] = []
        declarations_by_fact: dict[str, Mapping[str, Any]] = {}
        for declaration in declarations:
            if not isinstance(declaration, Mapping):
                return {}, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "A synthetic Advisory Rubric contains a malformed input declaration.",
                )
            fact_code = declaration.get("fact_code")
            if (
                not _allowed_string(fact_code, _KNOWN_FACT_CODES)
                or fact_code in declared_fact_codes
                or not _allowed_string(declaration.get("value_type"), _ADVISORY_VALUE_TYPES)
                or not isinstance(declaration.get("unit"), str)
                or not isinstance(declaration.get("required"), bool)
            ):
                return {}, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "A synthetic Advisory Rubric typed input declaration is invalid.",
                )
            declared_fact_codes.append(str(fact_code))
            declarations_by_fact[str(fact_code)] = declaration
        rules = rubric.get("rules")
        precedence = rubric.get("rule_precedence")
        if (
            not isinstance(rules, list)
            or not rules
            or not isinstance(precedence, Mapping)
            or precedence.get("order") != "ascending_priority"
            or precedence.get("complete_for_declared_input") is not True
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric rule registry is incomplete.",
            )
        priorities: set[int] = set()
        ordered_priorities: list[int] = []
        predicate_fact_codes: set[str] = set()
        for rule in rules:
            predicate = rule.get("predicate") if isinstance(rule, Mapping) else None
            priority = rule.get("priority") if isinstance(rule, Mapping) else None
            output = rule.get("output") if isinstance(rule, Mapping) else None
            predicate_fact_code = (
                predicate.get("fact_code") if isinstance(predicate, Mapping) else None
            )
            predicate_declaration = declarations_by_fact.get(str(predicate_fact_code))
            predicate_operator = (
                predicate.get("operator") if isinstance(predicate, Mapping) else None
            )
            predicate_value = (
                predicate.get("value") if isinstance(predicate, Mapping) else None
            )
            predicate_value_valid = (
                isinstance(predicate_declaration, Mapping)
                and "value" in predicate
                and (
                    (
                        predicate_operator == "EQ"
                        and _advisory_value_is_valid(
                            predicate_value,
                            str(predicate_declaration["value_type"]),
                        )
                    )
                    or (
                        predicate_operator in {"GTE", "LTE"}
                        and predicate_declaration["value_type"]
                        in {"INTEGER", "DECIMAL"}
                        and _decimal(predicate_value) is not None
                    )
                )
            )
            if (
                not isinstance(rule, Mapping)
                or not isinstance(rule.get("rule_id"), str)
                or not isinstance(priority, int)
                or isinstance(priority, bool)
                or priority in priorities
                or not isinstance(predicate, Mapping)
                or predicate_fact_code not in declared_fact_codes
                or not _allowed_string(predicate_operator, _ADVISORY_OPERATORS)
                or not predicate_value_valid
                or output not in _ADVISORY_OUTPUTS[str(dimension)]
                or (
                    predicate.get("output") is not None
                    and predicate.get("output") != output
                )
            ):
                return {}, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "A synthetic Advisory Rubric contains an invalid rule.",
                )
            priorities.add(priority)
            ordered_priorities.append(priority)
            predicate_fact_codes.add(str(predicate["fact_code"]))
        if (
            ordered_priorities != sorted(ordered_priorities)
            or predicate_fact_codes != set(declared_fact_codes)
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "A synthetic Advisory Rubric does not completely and deterministically cover its typed inputs.",
            )
        rubric_key = (str(option_code), "1", str(trigger_mode), str(dimension))
        rubric_copy = deepcopy(rubric)
        rubrics_by_reference[record_id] = rubric_copy
        rubric_keys.add(rubric_key)

    for option_code, option in option_index.items():
        if option.get("shape") != "ATOMIC":
            continue
        declarations = option.get("advisory_rubric_declarations")
        if not isinstance(declarations, list):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                f"The advisory declarations for {option_code} are malformed.",
            )
        for declaration in declarations:
            reference = declaration.get("rubric_reference") if isinstance(declaration, Mapping) else None
            if reference == "UNAVAILABLE_PENDING_REVIEW":
                continue
            if not isinstance(reference, str) or reference not in rubrics_by_reference:
                return {}, _error(
                    "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                    f"The advisory rubric declaration for {option_code} does not resolve exactly.",
                )
            rubric = rubrics_by_reference[reference]
            if (
                rubric.get("option_code") != option_code
                or rubric.get("option_version") != option.get("option_version")
                or rubric.get("trigger_mode") != declaration.get("trigger_mode")
                or rubric.get("dimension") != declaration.get("dimension")
            ):
                return {}, _error(
                    "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                    f"The advisory rubric declaration for {option_code} is bound to the wrong rubric.",
                )
    return rubrics_by_reference, None


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
    links: Mapping[tuple[str, str], dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str] | None]:
    reviews: dict[tuple[str, str], dict[str, Any]] = {}
    for record in collections["composite_reviews"]:
        option_code = record.get("option_code")
        trigger_mode = record.get("trigger_mode")
        key = (str(option_code), str(trigger_mode))
        expected_record_id = (
            f"{_FIXTURE_NAMESPACE}composite-reviews:"
            f"protected-slot-with-phased-delivery:{str(trigger_mode).lower()}:v1"
        )
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
            record.get("schema_identifier") != "composite-compatibility-review"
            or record.get("schema_version") != "1"
            or record.get("registry_identifier")
            != "decision-support-composite-compatibility-reviews"
            or record.get("registry_version") != "1"
            or not isinstance(record.get("record_id"), str)
            or record.get("record_id") != expected_record_id
            or record.get("review_id") != record.get("record_id")
            or record.get("result_version") != "1"
            or record.get("composite_option_code") != option_code
            or record.get("option_version") != "1"
            or record.get("component_codes")
            != ["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"]
            or record.get("component_option_refs")
            != [
                f"{_FIXTURE_NAMESPACE}options:protected_production_slot:v1",
                f"{_FIXTURE_NAMESPACE}options:phased_delivery:v1",
            ]
            or record.get("composite_driver_action_link_ref")
            != (
                f"{_FIXTURE_NAMESPACE}driver-action-links:"
                f"protected_slot_with_phased_delivery:{str(trigger_mode).lower()}:v1"
            )
            or not isinstance(links.get(key), Mapping)
            or links[key].get("record_id")
            != record.get("composite_driver_action_link_ref")
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic Composite Compatibility Review identity is not exact.",
            )
        if (
            record.get("criteria_schema_identifier")
            != "composite-compatibility-criteria"
            or record.get("criteria_schema_version") != "1"
            or not isinstance(record.get("subject_identity"), str)
            or not isinstance(record.get("case_constraint_snapshot_ref"), str)
            or not record.get("case_constraint_snapshot_ref")
            or _parse_time(record.get("constraints_as_of")) is None
            or not isinstance(record.get("published_at"), str)
            or _parse_time(record.get("published_at")) is None
            or not isinstance(record.get("review_available_at"), str)
            or _parse_time(record.get("review_available_at")) is None
            or _parse_time(record.get("review_date")) is None
            or _parse_time(record.get("reviewed_at")) is None
            or record.get("reviewer_role") != "SYNTHETIC_CONFORMANCE_REVIEW"
            or not isinstance(record.get("review_reference"), str)
            or not record.get("review_reference")
            or not isinstance(record.get("review_reason_code"), str)
            or not record.get("review_reason_code")
            or not _allowed_string(record.get("lifecycle_status"), {"ACTIVE", "RETIRED"})
            or not _allowed_string(record.get("state"), _SUPPORTED_LINK_STATES)
            or not _allowed_string(record.get("review_status"), _SUPPORTED_LINK_STATES)
            or not _valid_evidence_refs(record.get("source_refs"))
            or not isinstance(record.get("provenance"), Mapping)
            or record["provenance"].get("source_kind") != "synthetic_conformance"
            or record["provenance"].get("source_namespace")
            != "synthetic://core-decision-support/v1"
            or record["provenance"].get("production_authority") != "PROHIBITED"
            or record["provenance"].get("external_evaluation_eligibility")
            != "PROHIBITED"
            or record.get("approval_scope") != "SYNTHETIC_CONFORMANCE_ONLY"
            or record.get("contract_status") != "SYNTHETIC_CONFORMANCE_ONLY"
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The synthetic Composite Compatibility Review metadata is malformed.",
            )
        published_at = _parse_time(record.get("published_at"))
        review_date = _parse_time(record.get("review_date"))
        review_available_at = _parse_time(record.get("review_available_at"))
        reviewed_at = _parse_time(record.get("reviewed_at"))
        if (
            published_at is not None
            and review_date is not None
            and review_date > published_at
        ) or (
            published_at is not None
            and review_available_at is not None
            and review_available_at > published_at
        ) or (
            published_at is not None
            and reviewed_at is not None
            and reviewed_at > published_at
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "A synthetic Composite Compatibility Review is published before its review evidence is available.",
            )
        attestations = record.get("attestations")
        if not isinstance(attestations, list) or [
            item.get("attestation_code")
            if isinstance(item, Mapping)
            else None
            for item in attestations
        ] != list(_EXPECTED_ATTESTATIONS):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The synthetic Composite Compatibility Review attestations are not the exact ordered set.",
            )
        for attestation in attestations:
            if (
                not isinstance(attestation, Mapping)
                or not _allowed_string(
                    attestation.get("outcome"),
                    {"ATTESTED_COMPATIBLE", "ATTESTED_INCOMPATIBLE"},
                )
                or attestation.get("review_status") != "APPROVED"
                or _parse_time(attestation.get("review_date")) is None
                or not isinstance(attestation.get("reviewer_reference"), str)
                or not attestation.get("reviewer_reference")
                or attestation.get("reviewer_role")
                != "SYNTHETIC_CONFORMANCE_REVIEW"
                or not isinstance(attestation.get("review_reference"), str)
                or not attestation.get("review_reference")
                or not isinstance(attestation.get("review_reason_code"), str)
                or not attestation.get("review_reason_code")
                or not _valid_evidence_refs(attestation.get("evidence_refs"))
            ):
                return {}, _error(
                    "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "A synthetic Composite Compatibility Review attestation is not fully evidenced and approved.",
                )
        expected_outcome = (
            "INCOMPATIBLE"
            if any(
                attestation["outcome"] == "ATTESTED_INCOMPATIBLE"
                for attestation in attestations
            )
            else "COMPATIBLE"
        )
        expected_status = (
            "UNSATISFIED" if expected_outcome == "INCOMPATIBLE" else "SATISFIED"
        )
        if (
            record.get("outcome") != expected_outcome
            or record.get("compatibility_status") != expected_status
        ):
            return {}, _error(
                "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "The synthetic Composite Compatibility Review outcome does not match its attestations.",
            )
        if record.get("supersession_ref") is not None and not isinstance(
            record.get("supersession_ref"), str
        ):
            return {}, _error(
                "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "The synthetic Composite Compatibility Review supersession reference is malformed.",
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


def _advisory_reason(
    code: str,
    *,
    reason: str,
    evidence_refs: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "priority": _ADVISORY_REASON_PRIORITIES[code],
        "reason": reason,
        "evidence_refs": _evidence_refs([], evidence_refs),
    }


def _ordered_reasons(reasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    unique.sort(key=lambda item: (int(item["priority"]), str(item["code"])))
    return unique


def _advisory_value_is_valid(value: object, value_type: str) -> bool:
    if value_type == "BOOLEAN":
        return isinstance(value, bool)
    if value_type == "INTEGER":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if value_type == "DECIMAL":
        return _decimal(value) is not None
    if value_type == "STRING":
        return isinstance(value, str) and bool(value)
    return False


def _advisory_predicate_matches(predicate: Mapping[str, Any], value: object) -> bool:
    operator = predicate.get("operator")
    expected = predicate.get("value")
    if operator == "EQ":
        return value == expected
    if operator in {"GTE", "LTE"}:
        try:
            left = Decimal(str(value))
            right = Decimal(str(expected))
        except (InvalidOperation, ValueError):
            return False
        return left >= right if operator == "GTE" else left <= right
    return False


def _advisory_result_base(
    *,
    option_code: str,
    option_version: str,
    trigger_mode: str,
    dimension: str,
    subject_identity: str,
    snapshot: Mapping[str, Any],
    rubric: Mapping[str, Any] | None,
) -> dict[str, Any]:
    rubric_ref = (
        {
            "reference": rubric.get("rubric_id"),
            "rubric_version": rubric.get("rubric_version"),
            "content_hash": rubric.get("content_hash"),
        }
        if rubric is not None
        else None
    )
    result: dict[str, Any] = {
        "schema_identifier": "advisory-result",
        "schema_version": "1",
        "option_code": option_code,
        "option_version": option_version,
        "trigger_mode": trigger_mode,
        "dimension": dimension,
        "subject_identity": subject_identity,
        "case_constraint_snapshot": _synthetic_record_ref(snapshot),
        "constraints_as_of": snapshot.get("constraints_as_of"),
        "rubric": rubric_ref,
        "status": "UNKNOWN",
        "value": "UNKNOWN",
        "ordinal": "UNKNOWN",
        "result": "UNKNOWN",
        "input_values": [],
        "typed_inputs": [],
        "observed_facts": [],
        "matched_rule": None,
        "reasons": [],
        "evidence_refs": [],
        "provenance": {
            "advisory_rubric": rubric_ref,
            "case_constraint_snapshot": _synthetic_record_ref(snapshot),
        },
    }
    return result


def _evaluate_advisory_rubric(
    *,
    option_code: str,
    option_version: str,
    trigger_mode: str,
    dimension: str,
    declaration: Mapping[str, Any],
    rubric: Mapping[str, Any] | None,
    facts: list[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    subject_identity: str,
) -> dict[str, Any]:
    result = _advisory_result_base(
        option_code=option_code,
        option_version=option_version,
        trigger_mode=trigger_mode,
        dimension=dimension,
        subject_identity=subject_identity,
        snapshot=snapshot,
        rubric=rubric,
    )
    rubric_evidence = (
        rubric.get("source_refs") if isinstance(rubric, Mapping) else []
    )
    result["evidence_refs"] = _evidence_refs([], rubric_evidence)
    result["provenance"]["rubric_source_refs"] = deepcopy(list(rubric_evidence))
    if declaration.get("rubric_reference") == "UNAVAILABLE_PENDING_REVIEW":
        result["reasons"] = [
            _advisory_reason(
                "RUBRIC_UNAVAILABLE",
                reason="The exact Advisory Rubric is unavailable pending review.",
                evidence_refs=rubric_evidence,
            )
        ]
        return result
    if rubric is None:
        result["reasons"] = [
            _advisory_reason(
                "RUBRIC_UNAVAILABLE",
                reason="The exact Advisory Rubric is unavailable.",
            )
        ]
        return result
    if (
        rubric.get("option_code") != option_code
        or rubric.get("option_version") != option_version
        or rubric.get("trigger_mode") != trigger_mode
        or rubric.get("dimension") != dimension
    ):
        result["reasons"] = [
            _advisory_reason(
                "RUBRIC_NOT_APPLICABLE",
                reason="The approved Advisory Rubric does not apply to this exact option and trigger mode.",
                evidence_refs=rubric_evidence,
            )
        ]
        return result
    published_at = _parse_time(rubric.get("published_at"))
    review_available_at = _parse_time(rubric.get("review_available_at"))
    if (
        rubric.get("lifecycle_status") != "ACTIVE"
        or rubric.get("state") != "APPROVED"
        or rubric.get("review_status") != "APPROVED"
        or published_at is None
        or review_available_at is None
        or published_at > constraints_as_of
        or review_available_at > constraints_as_of
        or rubric.get("supersession_ref") is not None
    ):
        result["reasons"] = [
            _advisory_reason(
                "RUBRIC_NOT_APPROVED",
                reason="The exact Advisory Rubric is not approved and available at the Case Constraint Snapshot cutoff.",
                evidence_refs=rubric_evidence,
            )
        ]
        return result

    input_values: list[dict[str, Any]] = []
    typed_inputs: list[dict[str, Any]] = []
    observed_facts: list[Mapping[str, Any]] = []
    reasons: list[dict[str, Any]] = []
    resolved_by_fact: dict[str, object] = {}
    declarations = rubric.get("typed_input_declarations", [])
    for declaration_item in declarations:
        fact_code = str(declaration_item["fact_code"])
        candidates = _fact_candidates(facts, fact_code, option_code)
        if not candidates:
            if declaration_item.get("required") is True:
                reasons.append(
                    _advisory_reason(
                        "RUBRIC_INPUT_MISSING",
                        reason=f"Required Advisory Rubric input {fact_code} has no eligible evidence.",
                        evidence_refs=rubric_evidence,
                    )
                )
            continue
        observed_facts.extend(candidates)
        if len(candidates) != 1:
            reasons.append(
                _advisory_reason(
                    "RUBRIC_INPUT_CONFLICT",
                    reason=f"Advisory Rubric input {fact_code} does not establish one value.",
                    evidence_refs=_evidence_refs(candidates),
                )
            )
            continue
        fact, eligibility = _eligible_fact(
            candidates,
            constraints_as_of=constraints_as_of,
        )
        if eligibility != "ELIGIBLE" or fact is None:
            if declaration_item.get("required") is True:
                reasons.append(
                    _advisory_reason(
                        "RUBRIC_INPUT_MISSING",
                        reason=f"Required Advisory Rubric input {fact_code} is unavailable at the cutoff.",
                        evidence_refs=_evidence_refs(candidates),
                    )
                )
            continue
        value = fact.get("value")
        if not _advisory_value_is_valid(value, str(declaration_item["value_type"])):
            reasons.append(
                _advisory_reason(
                    "RUBRIC_INPUT_INVALID",
                    reason=f"Advisory Rubric input {fact_code} has the wrong typed value.",
                    evidence_refs=_evidence_refs([fact]),
                )
            )
            continue
        declared_unit = declaration_item.get("unit")
        fact_unit = fact.get("unit")
        if (
            declared_unit == "NOT_APPLICABLE"
            and fact_unit not in {None, "NOT_APPLICABLE"}
        ) or (
            declared_unit != "NOT_APPLICABLE" and fact_unit != declared_unit
        ):
            reasons.append(
                _advisory_reason(
                    "RUBRIC_INPUT_INVALID",
                    reason=f"Advisory Rubric input {fact_code} has an incompatible unit.",
                    evidence_refs=_evidence_refs([fact]),
                )
            )
            continue
        resolved_by_fact[fact_code] = value
        input_values.append({"fact_code": fact_code, "value": deepcopy(value)})
        typed_inputs.append(
            {
                "fact_code": fact_code,
                "value": deepcopy(value),
                "value_type": declaration_item["value_type"],
                "unit": declaration_item["unit"],
                "evidence_refs": _evidence_refs([fact]),
            }
        )
    result["input_values"] = input_values
    result["typed_inputs"] = typed_inputs
    result["observed_facts"] = deepcopy([dict(fact) for fact in observed_facts])
    evidence_refs = _evidence_refs(observed_facts, rubric_evidence)
    result["evidence_refs"] = evidence_refs
    result["provenance"]["rubric_source_refs"] = deepcopy(list(rubric_evidence))
    if reasons:
        result["reasons"] = _ordered_reasons(reasons)
        return result
    matches: list[Mapping[str, Any]] = []
    for rule in sorted(rubric["rules"], key=lambda item: int(item["priority"])):
        predicate = rule["predicate"]
        fact_code = str(predicate["fact_code"])
        if fact_code in resolved_by_fact and _advisory_predicate_matches(
            predicate, resolved_by_fact[fact_code]
        ):
            matches.append(rule)
    if not matches:
        result["reasons"] = [
            _advisory_reason(
                "RUBRIC_RULE_NO_MATCH",
                reason="Complete typed Advisory Rubric inputs matched no rule.",
                evidence_refs=evidence_refs,
            )
        ]
        return result
    if len(matches) > 1:
        result["reasons"] = [
            _advisory_reason(
                "RUBRIC_RULE_AMBIGUOUS",
                reason="Complete typed Advisory Rubric inputs matched multiple rules.",
                evidence_refs=evidence_refs,
            )
        ]
        return result
    matched = matches[0]
    value = matched["output"]
    result.update(
        {
            "status": "KNOWN",
            "value": value,
            "ordinal": value,
            "result": value,
            "matched_rule": {
                "rule_id": matched["rule_id"],
                "priority": matched["priority"],
                "output": value,
            },
        }
    )
    return result


def _advisory_declaration(
    option: Mapping[str, Any],
    *,
    trigger_mode: str,
    dimension: str,
) -> Mapping[str, Any] | None:
    declarations = option.get("advisory_rubric_declarations")
    if not isinstance(declarations, list):
        return None
    matches = [
        declaration
        for declaration in declarations
        if isinstance(declaration, Mapping)
        and declaration.get("trigger_mode") == trigger_mode
        and declaration.get("dimension") == dimension
    ]
    return matches[0] if len(matches) == 1 else None


def _advisory_result_reasons(result: Mapping[str, Any]) -> list[str]:
    reasons = result.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [
        str(reason["code"])
        for reason in reasons
        if isinstance(reason, Mapping) and isinstance(reason.get("code"), str)
    ]


def _atomic_advisory_results(
    *,
    option: Mapping[str, Any],
    trigger_mode: str,
    facts: list[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    subject_identity: str,
    rubrics_by_reference: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    option_code = str(option["option_code"])
    option_version = str(option["option_version"])
    for dimension in _ADVISORY_DIMENSIONS:
        declaration = _advisory_declaration(
            option,
            trigger_mode=trigger_mode,
            dimension=dimension,
        )
        if declaration is None:
            declaration = {
                "dimension": dimension,
                "trigger_mode": trigger_mode,
                "rubric_reference": "UNAVAILABLE_PENDING_REVIEW",
            }
        reference = declaration.get("rubric_reference")
        rubric = (
            rubrics_by_reference.get(reference)
            if isinstance(reference, str)
            else None
        )
        results.append(
            _evaluate_advisory_rubric(
                option_code=option_code,
                option_version=option_version,
                trigger_mode=trigger_mode,
                dimension=dimension,
                declaration=declaration,
                rubric=rubric,
                facts=facts,
                snapshot=snapshot,
                constraints_as_of=constraints_as_of,
                subject_identity=subject_identity,
            )
        )
    return results


def _composite_advisory_result(
    *,
    dimension: str,
    option: Mapping[str, Any],
    trigger_mode: str,
    component_results: list[dict[str, Any]],
    snapshot: Mapping[str, Any],
    subject_identity: str,
) -> dict[str, Any]:
    result = _advisory_result_base(
        option_code=str(option["option_code"]),
        option_version=str(option["option_version"]),
        trigger_mode=trigger_mode,
        dimension=dimension,
        subject_identity=subject_identity,
        snapshot=snapshot,
        rubric=None,
    )
    result["derivation"] = {
        "kind": "LEAST_FAVORABLE_COMPONENT_RESULTS.v1",
        "version": "1",
    }
    result["component_results"] = deepcopy(component_results)
    result["evidence_refs"] = _evidence_refs(
        [],
        [
            reference
            for component in component_results
            for reference in component.get("evidence_refs", [])
            if isinstance(reference, Mapping)
        ],
    )
    result["provenance"]["component_results"] = [
        {
            "option_code": component.get("option_code"),
            "dimension": component.get("dimension"),
            "rubric": deepcopy(component.get("rubric")),
        }
        for component in component_results
    ]
    unknown_components = [
        component
        for component in component_results
        if component.get("status") == "UNKNOWN"
    ]
    if unknown_components:
        reasons = [
            _advisory_reason(
                "RUBRIC_COMPONENT_RESULT_UNKNOWN",
                reason="A composite component Advisory Result is UNKNOWN; no component value was selected.",
                evidence_refs=[
                    reference
                    for component in unknown_components
                    for reference in component.get("evidence_refs", [])
                    if isinstance(reference, Mapping)
                ],
            )
        ]
        for component in unknown_components:
            for reason in component.get("reasons", []):
                if isinstance(reason, Mapping) and isinstance(reason.get("code"), str):
                    reasons.append(deepcopy(dict(reason)))
        result["reasons"] = _ordered_reasons(reasons)
        return result
    values = [str(component["value"]) for component in component_results]
    if dimension in {"CONTRACTUAL_RELATIONSHIP_RISK", "OPERATIONAL_DISRUPTION"}:
        value = max(
            values,
            key=lambda item: _ADVISORY_OUTPUTS[dimension].index(item),
        )
    else:
        value = max(
            values,
            key=lambda item: _ADVISORY_OUTPUTS[dimension].index(item),
        )
    result.update(
        {
            "status": "KNOWN",
            "value": value,
            "ordinal": value,
            "result": value,
        }
    )
    return result


def _option_advisory_results(
    *,
    option: Mapping[str, Any],
    option_index: Mapping[str, dict[str, Any]],
    trigger_mode: str,
    facts: list[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    subject_identity: str,
    rubrics_by_reference: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if option.get("shape") != "COMPOSITE":
        return _atomic_advisory_results(
            option=option,
            trigger_mode=trigger_mode,
            facts=facts,
            snapshot=snapshot,
            constraints_as_of=constraints_as_of,
            subject_identity=subject_identity,
            rubrics_by_reference=rubrics_by_reference,
        )
    component_results_by_dimension: dict[str, list[dict[str, Any]]] = {
        dimension: [] for dimension in _ADVISORY_DIMENSIONS
    }
    for component_code in option.get("component_codes", []):
        component = option_index.get(str(component_code))
        if component is None:
            continue
        component_results = _atomic_advisory_results(
            option=component,
            trigger_mode=trigger_mode,
            facts=facts,
            snapshot=snapshot,
            constraints_as_of=constraints_as_of,
            subject_identity=subject_identity,
            rubrics_by_reference=rubrics_by_reference,
        )
        for component_result in component_results:
            component_results_by_dimension[str(component_result["dimension"])].append(
                component_result
            )
    return [
        _composite_advisory_result(
            dimension=dimension,
            option=option,
            trigger_mode=trigger_mode,
            component_results=component_results_by_dimension[dimension],
            snapshot=snapshot,
            subject_identity=subject_identity,
        )
        for dimension in _ADVISORY_DIMENSIONS
    ]


def _time_comparison_dimension(
    *,
    option_code: str,
    facts: list[Mapping[str, Any]],
    constraints_as_of: datetime,
) -> dict[str, Any]:
    if option_code == "PROTECTED_SLOT_WITH_PHASED_DELIVERY":
        return {
            "applicability": "INCOMPARABLE",
            "value": "UNKNOWN",
            "direction": "LOWER_IS_MORE_FAVORABLE",
            "source": "COMPOSITION_DECLARATION",
            "reason_codes": ["TIME_COMPOSITION_RULE_UNAVAILABLE"],
        }
    candidates = _fact_candidates(facts, "TIME_TO_INITIATE_DAYS", option_code)
    fact, eligibility = _eligible_fact(candidates, constraints_as_of=constraints_as_of)
    reason_codes: list[str] = []
    if not candidates or eligibility != "ELIGIBLE" or fact is None:
        reason_codes.append("TIME_TO_INITIATE_INPUT_UNAVAILABLE")
        value: object = "UNKNOWN"
        applicability = "INCOMPARABLE"
    elif _decimal(fact.get("value")) is None or not isinstance(
        fact.get("duration_basis"), str
    ):
        reason_codes.append("TIME_TO_INITIATE_INPUT_INVALID")
        value = "UNKNOWN"
        applicability = "INCOMPARABLE"
    else:
        value = fact.get("value")
        applicability = "APPLICABLE"
    result: dict[str, Any] = {
        "applicability": applicability,
        "value": value,
        "direction": "LOWER_IS_MORE_FAVORABLE",
        "source": "CONSTRAINT_FACT",
    }
    if fact is not None:
        result["duration_basis"] = fact.get("duration_basis")
        result["evidence_refs"] = _evidence_refs([fact])
    if reason_codes:
        result["reason_codes"] = reason_codes
    return result


def _comparison_dimensions(
    *,
    option_code: str,
    advisory_results: list[Mapping[str, Any]],
    facts: list[Mapping[str, Any]],
    constraints_as_of: datetime,
) -> tuple[dict[str, dict[str, Any]], str]:
    dimensions: dict[str, dict[str, Any]] = {
        "TIME_TO_INITIATE": _time_comparison_dimension(
            option_code=option_code,
            facts=facts,
            constraints_as_of=constraints_as_of,
        )
    }
    for advisory in advisory_results:
        dimension = str(advisory["dimension"])
        if advisory.get("status") == "KNOWN":
            dimensions[dimension] = {
                "applicability": "APPLICABLE",
                "value": advisory["value"],
                "direction": _ADVISORY_DIRECTIONS[dimension],
                "source": "ADVISORY_RESULT",
            }
        else:
            dimensions[dimension] = {
                "applicability": "INCOMPARABLE",
                "value": "UNKNOWN",
                "direction": _ADVISORY_DIRECTIONS[dimension],
                "source": "ADVISORY_RESULT",
                "reason_codes": _advisory_result_reasons(advisory),
            }
    state = (
        "INCOMPARABLE_EVIDENCE"
        if any(
            dimension.get("applicability") == "INCOMPARABLE"
            for dimension in dimensions.values()
        )
        else "COMPARABLE"
    )
    return dimensions, state


def _not_evaluated_comparison_dimensions(
    *, reason_code: str
) -> tuple[dict[str, dict[str, Any]], str]:
    dimensions = {
        "TIME_TO_INITIATE": {
            "applicability": "NOT_EVALUATED",
            "value": "NOT_EVALUATED",
            "direction": "LOWER_IS_MORE_FAVORABLE",
            "source": "NOT_EVALUATED",
            "reason_codes": [reason_code],
        }
    }
    dimensions.update(
        {
            dimension: {
                "applicability": "NOT_EVALUATED",
                "value": "NOT_EVALUATED",
                "direction": _ADVISORY_DIRECTIONS[dimension],
                "source": "NOT_EVALUATED",
                "reason_codes": [reason_code],
            }
            for dimension in _ADVISORY_DIMENSIONS
        }
    )
    return dimensions, "NOT_EVALUATED"


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
    published_at = _parse_time(review.get("published_at"))
    review_available_at = _parse_time(review.get("review_available_at"))
    if (
        published_at is None
        or review_available_at is None
        or published_at > constraints_as_of
        or review_available_at > constraints_as_of
    ):
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_NOT_AVAILABLE_AT_CUTOFF", extra_evidence
    if review.get("supersession_ref") is not None:
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_SUPERSEDED", extra_evidence
    if review.get("lifecycle_status") == "RETIRED" or review.get("state") == "RETIRED" or review.get(
        "review_status"
    ) == "RETIRED":
        return "UNKNOWN", observed, "COMPOSITE_REVIEW_RETIRED", extra_evidence
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
    option_index: Mapping[str, dict[str, Any]],
    link: Mapping[str, Any] | None,
    trigger_mode: str,
    facts: list[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    constraints_as_of: datetime,
    subject_identity: str,
    links: Mapping[tuple[str, str], dict[str, Any]],
    monitoring_triggers: Mapping[tuple[str, str], dict[str, Any]],
    composite_reviews: Mapping[tuple[str, str], dict[str, Any]],
    rubrics_by_reference: Mapping[str, dict[str, Any]],
    release_preview: Mapping[str, Any] | None,
    value_context: ValueContext,
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
        "advisory_results": [],
        "comparison_state": "NOT_EVALUATED",
    }
    base["comparison_dimensions"], base["comparison_state"] = (
        _not_evaluated_comparison_dimensions(reason_code="NOT_EVALUATED")
    )
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
    if option_code == "ACCEPT_AND_MONITOR":
        monitoring_trigger = monitoring_triggers.get((option_code, trigger_mode))
        base["monitoring_escalation_trigger_ref_and_hash"] = (
            _synthetic_record_ref(monitoring_trigger)
            if monitoring_trigger is not None
            else None
        )
        base["monitoring_trigger_ref_and_hash"] = deepcopy(
            base["monitoring_escalation_trigger_ref_and_hash"]
        )

    def mark_advisories_not_evaluated(reason_code: str) -> None:
        base["advisory_results"] = []
        base["comparison_dimensions"], base["comparison_state"] = (
            _not_evaluated_comparison_dimensions(reason_code=reason_code)
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
        mark_advisories_not_evaluated("OPTION_RETIRED")
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
        mark_advisories_not_evaluated("TRIGGER_MODE_INCOMPATIBLE")
        return base
    if link is None:
        base["evidence_tags"]["MECHANISTIC_LINK"] = "NOT_EVALUATED"
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_MISSING",
                reason="No exact governed Driver-Action Link is available for this option and trigger mode.",
            )
        ]
        mark_advisories_not_evaluated("DRIVER_ACTION_LINK_MISSING")
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
        mark_advisories_not_evaluated("DRIVER_ACTION_LINK_NOT_AVAILABLE_AT_CUTOFF")
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
        mark_advisories_not_evaluated("DRIVER_ACTION_LINK_PROVISIONAL")
        return base
    if link_state == "REJECTED" or review_status == "REJECTED":
        base["evidence_tags"]["MECHANISTIC_LINK"] = "REJECTED"
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_REJECTED",
                reason="The exact Driver-Action Link is rejected and cannot make an option eligible.",
            )
        ]
        mark_advisories_not_evaluated("DRIVER_ACTION_LINK_REJECTED")
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
        mark_advisories_not_evaluated("DRIVER_ACTION_LINK_SUPERSEDED")
        return base
    if link_state != "APPROVED" or review_status != "APPROVED":
        base["suppression_reasons"] = [
            _suppression_reason(
                code="DRIVER_ACTION_LINK_PROVISIONAL",
                reason="The exact Driver-Action Link is not approved for eligibility.",
            )
        ]
        mark_advisories_not_evaluated("DRIVER_ACTION_LINK_PROVISIONAL")
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
    advisory_results = _option_advisory_results(
        option=option,
        option_index=option_index,
        trigger_mode=trigger_mode,
        facts=facts,
        snapshot=snapshot,
        constraints_as_of=constraints_as_of,
        subject_identity=subject_identity,
        rubrics_by_reference=rubrics_by_reference,
    )
    comparison_dimensions, comparison_state = _comparison_dimensions(
        option_code=option_code,
        advisory_results=advisory_results,
        facts=facts,
        constraints_as_of=constraints_as_of,
    )
    base["advisory_results"] = advisory_results
    base["comparison_dimensions"] = comparison_dimensions
    base["comparison_state"] = comparison_state
    failing_results = [
        item for item in rule_results if item["status"] in {"UNSATISFIED", "UNKNOWN"}
    ]
    value_projection = project_option_value(
        option=option,
        link=link,
        trigger_mode=trigger_mode,
        subject_identity=subject_identity,
        snapshot=snapshot,
        constraints_as_of=constraints_as_of,
        required_constraints_pass=not failing_results,
        value_context=value_context,
    )
    projection_fields = deepcopy(value_projection.fields)
    tag_updates = projection_fields.pop("evidence_tags", {})
    base.update(projection_fields)
    base["evidence_tags"].update(tag_updates)
    base["comparison_dimensions"] = comparison_dimensions_for_option(base)
    base["comparison_state"] = (
        "INCOMPARABLE_EVIDENCE"
        if any(
            dimension.get("applicability") == "INCOMPARABLE"
            for dimension in base["comparison_dimensions"].values()
        )
        else "COMPARABLE"
    )
    if option_code == "ACCEPT_AND_MONITOR":
        base["evidence_tags"]["ASSUMPTION_BASED_BENEFIT"] = "NO_BENEFIT_CLAIM"
    elif value_context.present:
        base["evidence_tags"]["ASSUMPTION_BASED_BENEFIT"] = (
            "EXPOSURE_TRANSLATION_ASSUMPTION"
            if value_projection.fields.get("benefit_projection") is not None
            and option.get("response_class")
            in {"EXPOSURE_REDUCTION", "MILESTONE_ACCELERATION"}
            else "OPERATIONAL_ASSUMPTION_ONLY"
            if value_projection.fields.get("benefit_projection") is not None
            else "UNAVAILABLE"
        )
    base["suppression_reasons"].extend(value_projection.suppression_reasons)
    base["suppression_reasons"] = sorted(
        base["suppression_reasons"],
        key=lambda item: (
            int(item["priority"]),
            int(item.get("constraint_rule_priority", -1)),
            str(item.get("rule_code", item["code"])),
        ),
    )
    if failing_results:
        base["evaluation_state"] = "SUPPRESSED"
        base["evidence_tags"]["RULE_BASED_ELIGIBILITY"] = (
            "UNKNOWN"
            if any(item["status"] == "UNKNOWN" for item in failing_results)
            else "UNSATISFIED"
        )
        constraint_suppression_reasons = [
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
        base["suppression_reasons"] = [
            *constraint_suppression_reasons,
            *value_projection.suppression_reasons,
        ]
        base["suppression_reasons"].sort(
            key=lambda item: (
                int(item["priority"]),
                int(item["constraint_rule_priority"]),
                str(item["rule_code"]),
            )
        )
        return base
    if value_projection.suppression_reasons:
        base["evaluation_state"] = "SUPPRESSED"
        base["evidence_tags"]["RULE_BASED_ELIGIBILITY"] = "SATISFIED"
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
    del subject_applicability, population_verdict
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
    rubrics_by_reference, rubric_error = _validate_advisory_rubric_records(
        collections,
        option_index,
    )
    if rubric_error is not None:
        return _active_failure(
            result=result,
            error=rubric_error,
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "advisory_rubrics",
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
    composite_reviews, composite_error = _validate_composite_records(collections, links)
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
    value_preparation = prepare_value_inputs(
        fixture_case=fixture_case,
        subject_verdict=subject_verdict,
    )
    if value_preparation.error is not None:
        return _active_failure(
            result=result,
            error=value_preparation.error,
            consumed_inputs=[
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "constraint_rules",
                "case_constraint_snapshot",
                "decision_support_value_inputs",
            ],
        )
    value_context = value_preparation.context
    canonical_value_input_payload = canonical_value_inputs(value_context)
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
                option_index=option_index,
                link=link,
                trigger_mode=trigger_mode,
                facts=facts,
                snapshot=snapshot,
                constraints_as_of=constraints_as_of,
                subject_identity=subject_identity,
                links=links,
                monitoring_triggers=monitoring_triggers,
                composite_reviews=composite_reviews,
                rubrics_by_reference=rubrics_by_reference,
                release_preview=preview,
                value_context=value_context,
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
        "decision_support_value_inputs": canonical_value_input_payload,
    }
    from .decision_support import _stable_id

    evaluation_id = _stable_id("dse", evaluation_identity)
    evaluation_series_id = _stable_id(
        "dses",
        {
            "fixture_id": fixture_case.get("fixture_id"),
            "subject_identity": subject_identity,
        },
    )
    input_digest = _sha256(
        {
            "registry_inspection": registry_inspection,
            "case_constraint_snapshot": snapshot,
            "decision_support_value_inputs": canonical_value_input_payload,
            "options": options,
        }
    )
    comparison_result = compare_and_publish(
        options=options,
        evaluation_occurrence_id=evaluation_id,
        evaluation_series_id=evaluation_series_id,
        input_digest=input_digest,
        provenance={
            "case_constraint_snapshot": _synthetic_record_ref(snapshot),
            "intervention_library": _synthetic_record_ref(library),
            "driver_action_links": [
                _synthetic_record_ref(link)
                for link in links.values()
                if link is not None
            ],
            "decision_support_value_inputs": canonical_value_input_payload,
        },
    )

    result.update(
        {
            "outcome": "NO_ELIGIBLE_OPTION",
            "state": "constraints_evaluated",
            "primary_reason_code": "CONSTRAINT_EVALUATION_COMPLETE",
            "reason": (
                "Every required constraint for every governed option was evaluated under "
                "the closed synthetic conformance registry. Benefit, value, comparison, "
                "and assumption-based projection values were evaluated when their exact "
                "inputs passed. Comparison, recommendation, drafting, and authorization "
                "stages are outside this evaluation."
            ),
            "next_step": "Inspect each option's typed rule outcomes, suppression reasons, and provenance.",
            "decision_support_evaluation_id": evaluation_id,
            "decision_support_evaluation_series_id": evaluation_series_id,
            "decision_support_driver_state_digest": _sha256(dict(driver_state)),
            "decision_support_input_digest": input_digest,
            "decision_support_value_inputs": canonical_value_input_payload,
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
                "decision_support_value_inputs",
            ],
        }
    )
    result.update(comparison_result)
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
