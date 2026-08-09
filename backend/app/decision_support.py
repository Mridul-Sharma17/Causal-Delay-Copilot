from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .canonical import sha256 as _sha256
from .fixture_boundaries import is_synthetic_fixture_identity


DECISION_SUPPORT_BOUNDARY_SCHEMA_VERSION = "decision-support-boundary.v1"
DECISION_SUPPORT_POLICY = {
    "identifier": "decision-support-policy",
    "version": "1",
    "state": "BUNDLED_RELEASE_BOUND",
}
_NORMALIZED_TRIGGER_MODES = {"reactive": "REACTIVE", "proactive": "PROACTIVE"}
_EVIDENCE_TAG_SLOTS = (
    "DRIVER_EVIDENCE",
    "MECHANISTIC_LINK",
    "RULE_BASED_ELIGIBILITY",
    "ASSUMPTION_BASED_BENEFIT",
)
_DIMENSIONS = (
    "CONTRACTUAL_RELATIONSHIP_RISK",
    "OPERATIONAL_DISRUPTION",
    "REVERSIBILITY",
)
_OPTIONS = (
    {
        "display_order": 10,
        "option_code": "PROTECTED_PRODUCTION_SLOT",
        "option_version": "1",
        "label": "Protected production slot",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "MILESTONE_ACCELERATION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 20,
        "option_code": "QUALIFIED_SOURCE_SPLIT",
        "option_version": "1",
        "label": "Qualified source split",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "EXPOSURE_REDUCTION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 30,
        "option_code": "PREQUALIFIED_ALTERNATE",
        "option_version": "1",
        "label": "Prequalified alternate",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "EXPOSURE_REDUCTION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 40,
        "option_code": "RELEASE_TIMING_ADJUSTMENT",
        "option_version": "1",
        "label": "Release timing adjustment",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["PROACTIVE"],
        "response_class": "EXPOSURE_REDUCTION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 50,
        "option_code": "CAPACITY_BACKED_ACCELERATION",
        "option_version": "1",
        "label": "Capacity-backed acceleration",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "MILESTONE_ACCELERATION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 60,
        "option_code": "PHASED_DELIVERY",
        "option_version": "1",
        "label": "Phased delivery",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "CONSEQUENCE_MITIGATION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 70,
        "option_code": "DEPENDENT_WORK_RESEQUENCING",
        "option_version": "1",
        "label": "Dependent-work resequencing",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE"],
        "response_class": "CONSEQUENCE_MITIGATION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 80,
        "option_code": "CONTRACTUAL_ESCALATION",
        "option_version": "1",
        "label": "Contractual escalation",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE"],
        "response_class": "CONSEQUENCE_MITIGATION",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 90,
        "option_code": "ACCEPT_AND_MONITOR",
        "option_version": "1",
        "label": "Accept and monitor",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "MONITOR_ONLY",
        "shape": "ATOMIC",
        "component_codes": [],
    },
    {
        "display_order": 100,
        "option_code": "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
        "option_version": "1",
        "label": "Protected slot with phased delivery",
        "lifecycle_status": "ACTIVE",
        "allowed_trigger_modes": ["REACTIVE", "PROACTIVE"],
        "response_class": "MILESTONE_ACCELERATION",
        "shape": "COMPOSITE",
        "component_codes": ["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"],
    },
)


def _hashed_record(record: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(record))
    result["content_hash"] = _sha256(result)
    return result


def _link_record(
    option: Mapping[str, Any],
    trigger_mode: str,
    *,
    release_binding: Mapping[str, Any],
) -> dict[str, Any]:
    option_code = str(option["option_code"])
    link_kind = (
        "MONITORING_BASELINE"
        if option_code == "ACCEPT_AND_MONITOR"
        else "ACTION_MECHANISM"
    )
    return _hashed_record({
        "schema_identifier": "driver-action-link",
        "schema_version": "1",
        "link_id": f"dal:{option_code.lower()}:{trigger_mode.lower()}",
        "link_version": "1",
        "registry_identifier": "supplier-congestion-driver-action-links",
        "registry_version": "1",
        "driver_code": "SUPPLIER_CONGESTION_HIGH_LOAD",
        "option_code": option_code,
        "option_version": str(option["option_version"]),
        "trigger_mode": trigger_mode,
        "link_kind": link_kind,
        "state": "PROVISIONAL",
        "review_status": "PROVISIONAL",
        "review_reason_code": "unavailable_pending_review",
        "reviewer_role": "unavailable_pending_review",
        "review_date": "unavailable_pending_review",
        "review_reference": "unavailable_pending_review",
        "predecessor_version_ref": None,
        "supersession_ref": None,
        "release_binding": deepcopy(dict(release_binding)),
        "intervention_effect_estimated": False,
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
    })


def _build_registry_inspection(
    *,
    release_candidate_id: str | None,
    runtime_fingerprint_digest: str | None,
) -> dict[str, Any]:
    release_bound = bool(
        isinstance(release_candidate_id, str)
        and release_candidate_id
        and isinstance(runtime_fingerprint_digest, str)
        and runtime_fingerprint_digest
    )
    release_binding = {
        "state": "BUNDLED_RELEASE_BOUND"
        if release_bound
        else "RELEASE_BINDING_UNAVAILABLE",
        "release_candidate_id": release_candidate_id,
        "runtime_fingerprint_digest": runtime_fingerprint_digest,
    }
    options = []
    for source_option in _OPTIONS:
        option = {
            "schema_identifier": "intervention-option",
            "schema_version": "1",
            **deepcopy(source_option),
            "status": source_option["lifecycle_status"],
            "predecessor_version_ref": None,
            "supersession_ref": None,
            "release_binding": deepcopy(release_binding),
        }
        options.append(_hashed_record(option))
    links = [
        _link_record(option, trigger_mode, release_binding=release_binding)
        for option in _OPTIONS
        for trigger_mode in option["allowed_trigger_modes"]
    ]
    rubrics = [
        _hashed_record({
            "schema_identifier": "advisory-rubric",
            "schema_version": "1",
            "rubric_id": (
                f"advisory-rubric:{str(option['option_code']).lower()}"
                f":{dimension.lower()}"
            ),
            "rubric_version": "1",
            "option_code": option["option_code"],
            "option_version": option["option_version"],
            "dimension": dimension,
            "state": "UNAVAILABLE_PENDING_REVIEW",
            "review_reason_code": "unavailable_pending_review",
            "predecessor_version_ref": None,
            "supersession_ref": None,
            "release_binding": deepcopy(release_binding),
        })
        for option in _OPTIONS
        if option["shape"] == "ATOMIC"
        for dimension in _DIMENSIONS
    ]
    monitoring_triggers = [
        _hashed_record({
            "schema_identifier": "monitoring-escalation-trigger",
            "schema_version": "1",
            "trigger_id": f"monitoring-trigger:accept-and-monitor:{trigger_mode.lower()}",
            "trigger_version": "1",
            "option_code": "ACCEPT_AND_MONITOR",
            "option_version": "1",
            "trigger_mode": trigger_mode,
            "state": "UNAVAILABLE_PENDING_REVIEW",
            "review_reason_code": "unavailable_pending_review",
            "predecessor_version_ref": None,
            "supersession_ref": None,
            "release_binding": deepcopy(release_binding),
        })
        for trigger_mode in ("REACTIVE", "PROACTIVE")
    ]
    library = _hashed_record({
            "schema_identifier": "core-intervention-library",
            "schema_version": "1",
            "identifier": "core-intervention-library",
            "version": "1",
            "state": "BUNDLED_CLOSED",
            "predecessor_version_ref": None,
            "supersession_ref": None,
            "release_binding": deepcopy(release_binding),
            "options": options,
        })
    composite = _hashed_record({
        "schema_identifier": "composite-compatibility-review",
        "schema_version": "1",
        "option_code": "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
        "option_version": "1",
        "state": "UNAVAILABLE_PENDING_REVIEW",
        "review_status": "PROVISIONAL",
        "review_reason_code": "unavailable_pending_review",
        "predecessor_version_ref": None,
        "supersession_ref": None,
        "release_binding": deepcopy(release_binding),
    })
    inspection = {
        "inspection_kind": "GOVERNED_RECORD_INSPECTION",
        "effect_bearing": False,
        "consumed_by_evaluation": False,
        "release_binding": release_binding,
        "policy": _hashed_record({
            **DECISION_SUPPORT_POLICY,
            "schema_identifier": "decision-support-policy",
            "schema_version": "1",
            "release_binding": deepcopy(release_binding),
        }),
        "intervention_library": library,
        "driver_action_links": links,
        "advisory_rubrics": rubrics,
        "monitoring_triggers": monitoring_triggers,
        "composite_reviews": [composite],
    }
    inspection["advice_currentness_dependency_set"] = _registry_currentness_dependencies(
        inspection
    )
    return inspection


def _registry_currentness_dependencies(
    registry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    def dependency(
        kind: str,
        record: Mapping[str, Any],
        *,
        identifier: str,
        version: str,
        disposition: str,
        lifecycle: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields = {
            "dependency_kind": kind,
            "reference": identifier,
            "id": identifier,
            "version": version,
            "content_hash": record["content_hash"],
            "consumed_disposition": disposition,
        }
        if lifecycle is not None:
            fields.update(deepcopy(dict(lifecycle)))
        current = deepcopy(dict(record))
        current.update(
            {
                "id": identifier,
                "version": version,
                "content_hash": record["content_hash"],
                "disposition": disposition,
            }
        )
        if lifecycle is not None:
            current.update(deepcopy(dict(lifecycle)))
        fields["current"] = current
        return fields

    dependencies: list[dict[str, Any]] = []
    policy = _mapping(registry.get("policy"))
    if policy is not None:
        dependencies.append(
            dependency(
                "GOVERNED_VERSION_ENVELOPE",
                policy,
                identifier=str(policy["identifier"]),
                version=str(policy["version"]),
                disposition=str(policy.get("state", "NOT_APPLICABLE")),
            )
        )
    library = _mapping(registry.get("intervention_library"))
    if library is not None:
        dependencies.append(
            dependency(
                "INTERVENTION_LIBRARY_VERSION",
                library,
                identifier=str(library["identifier"]),
                version=str(library["version"]),
                disposition=str(library.get("state", "NOT_APPLICABLE")),
                lifecycle={
                    "unique_unsuperseded_head": True,
                    "supported": True,
                },
            )
        )
    for option in registry.get("intervention_library", {}).get("options", []):
        if not isinstance(option, Mapping):
            continue
        dependencies.append(
            dependency(
                "INTERVENTION_OPTION_VERSION",
                option,
                identifier=str(option["option_code"]),
                version=str(option["option_version"]),
                disposition=str(option.get("status", "NOT_APPLICABLE")),
                lifecycle={
                    "effective": True,
                    "unique_unsuperseded_head": True,
                    "supported_result": option.get("status") == "ACTIVE",
                },
            )
        )
    for record in registry.get("driver_action_links", []):
        if not isinstance(record, Mapping):
            continue
        dependencies.append(
            dependency(
                "DRIVER_ACTION_LINK_VERSION",
                record,
                identifier=str(record["link_id"]),
                version=str(record["link_version"]),
                disposition=str(record.get("review_status", "NOT_APPLICABLE")),
                lifecycle={
                    "effective": True,
                    "unique_unsuperseded_head": True,
                    "supported_result": False,
                },
            )
        )
    for record in registry.get("advisory_rubrics", []):
        if not isinstance(record, Mapping):
            continue
        dependencies.append(
            dependency(
                "ADVISORY_RUBRIC_VERSION",
                record,
                identifier=str(record["rubric_id"]),
                version=str(record["rubric_version"]),
                disposition=str(record.get("state", "NOT_APPLICABLE")),
                lifecycle={
                    "effective": True,
                    "unique_unsuperseded_head": True,
                    "applicable": True,
                    "known_result": False,
                },
            )
        )
    for record in registry.get("monitoring_triggers", []):
        if not isinstance(record, Mapping):
            continue
        dependencies.append(
            dependency(
                "MONITORING_ESCALATION_TRIGGER_VERSION",
                record,
                identifier=str(record["trigger_id"]),
                version=str(record["trigger_version"]),
                disposition=str(record.get("state", "NOT_APPLICABLE")),
                lifecycle={
                    "effective": True,
                    "unique_unsuperseded_head": True,
                    "applicable": True,
                    "supported_result": False,
                },
            )
        )
    for record in registry.get("composite_reviews", []):
        if not isinstance(record, Mapping):
            continue
        dependencies.append(
            dependency(
                "COMPOSITE_COMPATIBILITY_REVIEW_VERSION",
                record,
                identifier=str(record.get("review_id", record.get("option_code"))),
                version=str(record.get("review_version", "1")),
                disposition=str(record.get("review_status", "NOT_APPLICABLE")),
                lifecycle={
                    "effective": True,
                    "unique_unsuperseded_head": True,
                    "satisfied_result": False,
                    "fully_specified": True,
                },
            )
        )
    return dependencies


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _subject_identity(
    investigation_request: Mapping[str, Any],
    subject_applicability: Mapping[str, Any],
) -> str | None:
    identity = subject_applicability.get("subject_identity")
    if isinstance(identity, str) and identity:
        return identity
    subject = _mapping(investigation_request.get("subject"))
    if subject is None:
        return None
    for key in ("order_line_id", "preview_subject_digest"):
        value = subject.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _permission(
    *,
    subject_applicability: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
    population_verdict: Mapping[str, Any] | None,
    intended_role: str,
) -> dict[str, Any]:
    subject_record = subject_verdict if isinstance(subject_verdict, Mapping) else None
    population_record = (
        population_verdict if isinstance(population_verdict, Mapping) else None
    )
    permitted = bool(
        subject_record is not None
        and subject_record.get("decision_support_role_permitted") is True
        and subject_record.get("decision_support_evaluation_permitted") is True
        and subject_applicability.get("state") == "applicable"
        and intended_role == "semi_synthetic_hero"
    )
    denial_reason = None
    if subject_record is not None:
        candidate = subject_record.get("primary_trigger_code")
        if isinstance(candidate, str) and candidate:
            denial_reason = candidate
    if denial_reason is None:
        candidate = subject_applicability.get("reason_code")
        if isinstance(candidate, str) and candidate:
            denial_reason = candidate
    if denial_reason is None and population_record is not None:
        candidate = population_record.get("primary_trigger_code")
        if isinstance(candidate, str) and candidate:
            denial_reason = candidate
    if denial_reason is None and intended_role != "semi_synthetic_hero":
        denial_reason = "SOURCE_SEMANTICS_INELIGIBLE"
    reason = subject_applicability.get("reason")
    next_step = subject_applicability.get("next_step")
    return {
        "decision_support_evaluation_permitted": permitted,
        "denial_reason_code": None if permitted else denial_reason or "DECISION_SUPPORT_PERMISSION_DENIED",
        "reason": (
            reason
            if isinstance(reason, str) and reason
            else "The verified evidence does not permit Decision Support for this subject."
        ),
        "next_step": (
            next_step
            if isinstance(next_step, str) and next_step
            else "Use the registered evidence recovery step before requesting Decision Support."
        ),
    }


def _optional_content_hash_error(
    value: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, str] | None:
    if "content_hash" not in value:
        return None
    content_hash = value.get("content_hash")
    content = deepcopy(dict(value))
    content.pop("content_hash", None)
    if not isinstance(content_hash, str) or _sha256(content) != content_hash:
        return {
            "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "reason": f"The verified {label} content binding does not match its record.",
        }
    return None


def _request_content_hash_error(
    investigation_request: Mapping[str, Any],
) -> dict[str, str] | None:
    if "content_hash" not in investigation_request:
        return None
    content_hash = investigation_request.get("content_hash")
    content = deepcopy(dict(investigation_request))
    content.pop("content_hash", None)
    content.pop("accepted_at", None)
    if not isinstance(content_hash, str) or _sha256(content) != content_hash:
        return {
            "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "reason": "The verified Investigation Request content binding does not match its record.",
        }
    return None


def _permission_integrity_error(
    *,
    investigation_request: Mapping[str, Any],
    subject_applicability: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
    population_verdict: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    request_hash_error = _request_content_hash_error(investigation_request)
    if request_hash_error is not None:
        return request_hash_error
    if subject_verdict is not None:
        if not isinstance(subject_verdict, Mapping):
            return {
                "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "reason": "The verified Subject Verdict is malformed.",
            }
        if "schema_version" in subject_verdict and subject_verdict.get(
            "schema_version"
        ) != "evidence-verdict.v2":
            return {
                "code": "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
                "reason": "The verified Subject Verdict schema is unsupported.",
            }
        hash_error = _optional_content_hash_error(
            subject_verdict,
            label="Subject Verdict",
        )
        if hash_error is not None:
            return hash_error
        if subject_verdict.get("scope") not in {None, "subject"}:
            return {
                "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "reason": "The verified Subject Verdict scope is inconsistent.",
            }
        for key in (
            "decision_support_role_permitted",
            "decision_support_evaluation_permitted",
        ):
            if key in subject_verdict and not isinstance(subject_verdict[key], bool):
                return {
                    "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "reason": f"The verified Subject Verdict field {key} is malformed.",
                }
        if (
            subject_verdict.get("decision_support_evaluation_permitted") is True
            and subject_verdict.get("decision_support_role_permitted") is not True
        ):
            return {
                "code": "DECISION_SUPPORT_VERDICT_PERMISSION_INCONSISTENT",
                "reason": "The verified Subject Verdict permissions are inconsistent.",
            }
        expected_identity = _subject_identity(
            investigation_request,
            subject_applicability,
        )
        if (
            subject_verdict.get("subject_identity") is not None
            and subject_verdict.get("subject_identity") != expected_identity
        ):
            return {
                "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "reason": "The verified Subject Verdict identity disagrees with the subject chain.",
            }
        if subject_verdict.get("decision_support_evaluation_permitted") is True:
            if subject_verdict.get("verdict_code") not in {
                None,
                "SUPPORTED_UNDER_ASSUMPTIONS",
            } or subject_verdict.get("effect_display") not in {
                None,
                "CAUSAL_ESTIMATE",
            }:
                return {
                    "code": "DECISION_SUPPORT_VERDICT_PERMISSION_INCONSISTENT",
                    "reason": "The verified Subject Verdict claim exceeds its Decision Support permission.",
                }

    if population_verdict is not None:
        if not isinstance(population_verdict, Mapping):
            return {
                "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                "reason": "The verified Population Verdict is malformed.",
            }
        if "schema_version" in population_verdict and population_verdict.get(
            "schema_version"
        ) != "evidence-verdict.v2":
            return {
                "code": "DECISION_SUPPORT_POLICY_VERSION_UNSUPPORTED",
                "reason": "The verified Population Verdict schema is unsupported.",
            }
        hash_error = _optional_content_hash_error(
            population_verdict,
            label="Population Verdict",
        )
        if hash_error is not None:
            return hash_error
        if population_verdict.get("scope") not in {None, "population"}:
            return {
                "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
                "reason": "The verified Population Verdict scope is inconsistent.",
            }
    return None


def _permission_provenance(
    *,
    investigation_request: Mapping[str, Any],
    subject_applicability: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
    population_verdict: Mapping[str, Any] | None,
    permission: Mapping[str, Any],
) -> dict[str, Any]:
    upstream_mode = investigation_request.get("trigger_mode")
    subject_id = _subject_identity(investigation_request, subject_applicability)

    def binding(value: Mapping[str, Any] | None, scope: str) -> dict[str, Any] | None:
        if value is None:
            return None
        content_hash = value.get("content_hash")
        return {
            "scope": scope,
            "reference": content_hash,
            "content_hash": content_hash,
        }

    return {
        "subject_verdict_ref_and_hash": binding(subject_verdict, "subject"),
        "population_verdict_ref_and_hash": binding(population_verdict, "population"),
        "subject_identity": subject_id,
        "causal_decision_at": deepcopy(investigation_request.get("decision_cutoff")),
        "upstream_trigger_mode": upstream_mode,
        "trigger_mode": (
            _NORMALIZED_TRIGGER_MODES.get(upstream_mode)
            if isinstance(upstream_mode, str)
            else None
        ),
        "requested_use": "DECISION_SUPPORT",
        "requested_claim_scope": (
            subject_verdict.get("permitted_claim_scope")
            if isinstance(subject_verdict, Mapping)
            else None
        ),
        "permission": deepcopy(dict(permission)),
    }


def _base_result(
    *,
    permission: Mapping[str, Any],
    registry_inspection: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": DECISION_SUPPORT_BOUNDARY_SCHEMA_VERSION,
        "policy": deepcopy(DECISION_SUPPORT_POLICY),
        "outcome": "NOT_PERMITTED",
        "state": "not_permitted",
        "primary_reason_code": None,
        "reason": None,
        "next_step": None,
        "permission": deepcopy(dict(permission)),
        "permission_provenance": None,
        "subject_driver_state": None,
        "decision_support_evaluation_id": None,
        "decision_support_evaluation_series_id": None,
        "decision_support_permission_digest": None,
        "decision_support_driver_state_digest": None,
        "options": [],
        "evidence_tags": {
            slot: "NOT_EVALUATED" for slot in _EVIDENCE_TAG_SLOTS
        },
        "suppression_reasons": [],
        "registry_inspection": deepcopy(dict(registry_inspection)),
        "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
        "action_recommendation": None,
        "tradeoff": None,
        "monitoring": {"state": "NOT_EVALUATED"},
        "drafting": {"state": "NOT_PERMITTED"},
        "authorization": {"state": "NOT_PERMITTED"},
        "consumed_operational_horizons": [],
        "advice_valid_through": "NO_EXPIRY",
        "consumed_inputs": ["permission_envelope"],
    }


def _with_content_hash(result: dict[str, Any]) -> dict[str, Any]:
    result["content_hash"] = _sha256(result)
    return result


def _stable_id(prefix: str, value: Mapping[str, Any]) -> str:
    return f"{prefix}:{_sha256(value).split(':', 1)[1][:32]}"


def _driver_state(
    *,
    investigation_request: Mapping[str, Any],
    subject_applicability: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    upstream_mode = investigation_request.get("trigger_mode")
    if not isinstance(upstream_mode, str):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The verified Investigation Request trigger mode is unavailable.",
        }
    normalized_mode = _NORMALIZED_TRIGGER_MODES.get(upstream_mode)
    if normalized_mode is None:
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The verified Investigation Request trigger mode is unsupported.",
        }
    subject = _mapping(investigation_request.get("subject"))
    subject_identity = _subject_identity(
        investigation_request,
        subject_applicability,
    )
    if not isinstance(subject_identity, str) or not subject_identity:
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The exact Subject identity is unavailable at the causal cutoff.",
        }
    expected_identity_key = (
        "order_line_id" if normalized_mode == "REACTIVE" else "preview_subject_digest"
    )
    if subject is None or not isinstance(subject.get(expected_identity_key), str):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The discriminated Subject identity is unavailable.",
        }
    if subject.get(expected_identity_key) != subject_identity:
        return None, {
            "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "reason": "The verified Subject identity disagrees with the Investigation Request.",
        }
    causal_input = _mapping(investigation_request.get("causal_engine_input"))
    exposure = _mapping(causal_input.get("supplier_load_exposure")) if causal_input else None
    primary = _mapping(exposure.get("primary")) if exposure else None
    field_name = (
        "high_load_exposure"
        if upstream_mode == "reactive"
        else "provisional_high_load_preview"
    )
    value = primary.get(field_name) if primary else None
    if not isinstance(value, bool):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The exact Subject Driver State is unavailable at the causal cutoff.",
        }
    subject_profile_hash = subject_applicability.get("subject_profile_hash")
    if subject_profile_hash is not None and not isinstance(subject_profile_hash, str):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The verified Subject Profile binding is malformed.",
        }
    verdict_profile_hash = (
        subject_verdict.get("subject_profile_hash")
        if isinstance(subject_verdict, Mapping)
        else None
    )
    if (
        isinstance(verdict_profile_hash, str)
        and isinstance(subject_profile_hash, str)
        and verdict_profile_hash != subject_profile_hash
    ):
        return None, {
            "code": "DECISION_SUPPORT_REFERENCE_INTEGRITY_MISMATCH",
            "reason": "The verified Subject Profile hash disagrees across the Subject Verdict chain.",
        }
    dataset_version_id = investigation_request.get("dataset_version_id")
    if dataset_version_id is not None and not isinstance(dataset_version_id, str):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The verified Dataset Version binding is malformed.",
        }
    decision_cutoff = investigation_request.get("decision_cutoff")
    if decision_cutoff is not None and not isinstance(decision_cutoff, Mapping):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The causal decision cutoff binding is malformed.",
        }
    request_content_hash = investigation_request.get("content_hash")
    if request_content_hash is not None and not isinstance(request_content_hash, str):
        return None, {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The Investigation Request content binding is malformed.",
        }
    return {
        "schema_identifier": "subject-driver-state",
        "schema_version": "subject-driver-state.v1",
        "version": "1",
        "kind": field_name,
        "value": value,
        "subject_identity": subject_identity,
        "dataset_version_id": dataset_version_id,
        "causal_decision_at": deepcopy(decision_cutoff),
        "subject_profile_hash": subject_profile_hash,
        "upstream_trigger_mode": upstream_mode,
        "trigger_mode": normalized_mode,
        "derivation_evidence": [
            {
                "record_id": investigation_request.get("investigation_request_id"),
                "content_hash": request_content_hash,
                "field_path": (
                    "causal_engine_input.supplier_load_exposure.primary."
                    f"{field_name}"
                ),
            }
        ],
    }, None


def _inactive_options(reason: str) -> list[dict[str, Any]]:
    tags = {slot: "NOT_EVALUATED" for slot in _EVIDENCE_TAG_SLOTS}
    return [
        {
            "display_order": option["display_order"],
            "option_code": option["option_code"],
            "option_version": option["option_version"],
            "label": option["label"],
            "evaluation_state": "NOT_EVALUATED",
            "evidence_tags": deepcopy(tags),
            "action_effect_evidence": "INTERVENTION_EFFECT_NOT_ESTIMATED",
            "suppression_reasons": [
                {
                    "code": "SUBJECT_DRIVER_NOT_ACTIVE",
                    "category": "DRIVER_STATE",
                    "priority": 0,
                    "reason": reason,
                }
            ],
        }
        for option in _OPTIONS
    ]


def _active_shipped_options(trigger_mode: str) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for option in _OPTIONS:
        allowed = trigger_mode in option["allowed_trigger_modes"]
        if not allowed:
            suppression = {
                "code": "TRIGGER_MODE_INCOMPATIBLE",
                "category": "OPTION",
                "priority": 100,
                "reason": (
                    f"This option is not registered for the {trigger_mode.lower()} "
                    "trigger mode."
                ),
            }
            mechanism_tag = "NOT_EVALUATED"
            speculative_disclosure = "ABSENT"
        else:
            suppression = {
                "code": "DRIVER_ACTION_LINK_PROVISIONAL",
                "category": "OPTION",
                "priority": 210,
                "reason": (
                    "The exact Driver-Action Link is provisional because practitioner "
                    "review is unavailable."
                ),
            }
            mechanism_tag = "PROVISIONAL"
            speculative_disclosure = "PRESENT"
        options.append(
            {
                "display_order": option["display_order"],
                "option_code": option["option_code"],
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
                "speculative_disclosure": speculative_disclosure,
                "suppression_reasons": [suppression],
            }
        )
    return options


def evaluate_decision_support(
    *,
    investigation_request: Mapping[str, Any],
    subject_applicability: Mapping[str, Any],
    subject_verdict: Mapping[str, Any] | None,
    population_verdict: Mapping[str, Any] | None,
    intended_role: str,
    release_candidate_id: str | None = None,
    runtime_fingerprint_digest: str | None = None,
    synthetic_conformance: Mapping[str, Any] | None = None,
    evaluation_occurrence_id: str | None = None,
    evaluation_series_id: str | None = None,
) -> dict[str, Any]:
    """Project the shipped Decision Support boundary without authorizing action."""

    registry_inspection = _build_registry_inspection(
        release_candidate_id=release_candidate_id,
        runtime_fingerprint_digest=runtime_fingerprint_digest,
    )
    identity_envelope = {
        "investigation_request": investigation_request,
        "subject_applicability": subject_applicability,
        "subject_verdict": subject_verdict,
        "population_verdict": population_verdict,
        "intended_role": intended_role,
    }
    synthetic_conformance_allowed = bool(
        isinstance(synthetic_conformance, Mapping)
        and is_synthetic_fixture_identity(synthetic_conformance)
        and is_synthetic_fixture_identity(identity_envelope)
    )
    if is_synthetic_fixture_identity(identity_envelope) and not synthetic_conformance_allowed:
        permission = {
            "decision_support_evaluation_permitted": False,
            "denial_reason_code": "SYNTHETIC_FIXTURE_NOT_SHIPPED",
            "reason": (
                "Synthetic approval-bearing fixtures are reserved for the test "
                "harness and are not shipped evidence."
            ),
            "next_step": (
                "Use the synthetic conformance harness; do not route this fixture "
                "through the shipped demo path."
            ),
        }
    else:
        permission = _permission(
            subject_applicability=subject_applicability,
            subject_verdict=subject_verdict,
            population_verdict=population_verdict,
            intended_role=intended_role,
        )
    result = _base_result(
        permission=permission,
        registry_inspection=registry_inspection,
    )
    permission_error = _permission_integrity_error(
        investigation_request=investigation_request,
        subject_applicability=subject_applicability,
        subject_verdict=subject_verdict,
        population_verdict=population_verdict,
    )
    if permission_error is not None:
        result.update(
            {
                "outcome": "FAILED",
                "state": "unavailable",
                "primary_reason_code": permission_error["code"],
                "reason": permission_error["reason"],
                "next_step": "Restore the verified evidence bindings and retry.",
                "suppression_reasons": [
                    {
                        "code": permission_error["code"],
                        "category": "PERMISSION_ENVELOPE",
                        "priority": 100,
                        "reason": permission_error["reason"],
                    }
                ],
            }
        )
        return _with_content_hash(result)
    permission_provenance = _permission_provenance(
        investigation_request=investigation_request,
        subject_applicability=subject_applicability,
        subject_verdict=subject_verdict,
        population_verdict=population_verdict,
        permission=permission,
    )
    result["permission_provenance"] = permission_provenance
    result["decision_support_permission_digest"] = _sha256(permission_provenance)
    if not permission["decision_support_evaluation_permitted"]:
        reason = str(permission["reason"])
        result["suppression_reasons"] = [
            {
                "code": str(permission["denial_reason_code"]),
                "category": "PERMISSION",
                "priority": 100,
                "reason": reason,
            }
        ]
        return _with_content_hash(result)

    driver_state, driver_error = _driver_state(
        investigation_request=investigation_request,
        subject_applicability=subject_applicability,
        subject_verdict=subject_verdict,
    )
    if driver_error is not None or driver_state is None:
        error = driver_error or {
            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
            "reason": "The exact Subject Driver State is unavailable at the causal cutoff.",
        }
        result.update(
            {
                "outcome": "FAILED",
                "state": "unavailable",
                "primary_reason_code": error["code"],
                "reason": error["reason"],
                "next_step": "Restore the verified Subject Driver State and retry.",
                "suppression_reasons": [
                    {
                        "code": error["code"],
                        "category": "INPUT",
                        "priority": 100,
                        "reason": error["reason"],
                    }
                ],
            }
        )
        return _with_content_hash(result)

    result["subject_driver_state"] = driver_state
    if driver_state["value"] is False:
        if driver_state["trigger_mode"] == "REACTIVE":
            reason = (
                "The verified subject was not in High-Load Exposure at the causal decision "
                "cutoff. No driver-linked option was evaluated. This does not state what "
                "caused any observed or future delay."
            )
        else:
            reason = (
                "The verified proposal's provisional preview did not meet the High-Load "
                "Exposure threshold at the causal decision cutoff. No driver-linked option "
                "was evaluated. This preview is not a canonical exposure fact and does not "
                "state what caused any delay."
            )
        evaluation_identity = {
            "investigation_request_id": investigation_request.get(
                "investigation_request_id"
            ),
            "subject_identity": driver_state["subject_identity"],
            "driver_state": driver_state,
        }
        result.update(
            {
                "outcome": "NO_ELIGIBLE_OPTION",
                "state": "inactive_driver",
                "primary_reason_code": "SUBJECT_DRIVER_NOT_ACTIVE",
                "reason": reason,
                "next_step": (
                    "Continue with evidence-only review; no driver-linked option is "
                    "available from an inactive driver."
                ),
                "decision_support_evaluation_id": evaluation_occurrence_id
                or _stable_id("dse", evaluation_identity),
                "decision_support_evaluation_series_id": evaluation_series_id
                or _stable_id("dses", evaluation_identity),
                "decision_support_driver_state_digest": _sha256(driver_state),
                "options": _inactive_options(reason),
                "suppression_reasons": [
                    {
                        "code": "SUBJECT_DRIVER_NOT_ACTIVE",
                        "category": "DRIVER_STATE",
                        "priority": 0,
                        "reason": reason,
                    }
                ],
                "consumed_inputs": [
                    "permission_envelope",
                    "subject_driver_state",
                ],
            }
        )
        return _with_content_hash(result)

    if synthetic_conformance is not None:
        if not synthetic_conformance_allowed:
            reason = (
                "The synthetic conformance context is missing its test-only identity "
                "binding."
            )
            result.update(
                {
                    "outcome": "FAILED",
                    "state": "unavailable",
                    "primary_reason_code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                    "reason": reason,
                    "next_step": "Use the isolated synthetic conformance harness with its bound fixture pack.",
                    "suppression_reasons": [
                        {
                            "code": "DECISION_SUPPORT_INPUT_SCHEMA_INVALID",
                            "category": "INPUT",
                            "priority": 100,
                            "reason": reason,
                        }
                    ],
                }
            )
            return _with_content_hash(result)
        from .decision_support_constraints import evaluate_active_synthetic_conformance

        result = evaluate_active_synthetic_conformance(
            result=result,
            investigation_request=investigation_request,
            subject_applicability=subject_applicability,
            subject_verdict=subject_verdict,
            population_verdict=population_verdict,
            driver_state=driver_state,
            synthetic_conformance=synthetic_conformance,
        )
        return _with_content_hash(result)

    release_binding = _mapping(registry_inspection.get("release_binding"))
    if release_binding is None or release_binding.get("state") != "BUNDLED_RELEASE_BOUND":
        reason = (
            "The shipped governed Decision Support records are not bound to the "
            "current release identity. No approval-dependent option path was evaluated."
        )
        result.update(
            {
                "outcome": "FAILED",
                "state": "unavailable",
                "primary_reason_code": "DECISION_SUPPORT_RELEASE_BINDING_UNAVAILABLE",
                "reason": reason,
                "next_step": "Restore the release-bound governed records and retry.",
                "decision_support_evaluation_id": None,
                "decision_support_evaluation_series_id": None,
                "decision_support_driver_state_digest": _sha256(driver_state),
                "suppression_reasons": [
                    {
                        "code": "DECISION_SUPPORT_RELEASE_BINDING_UNAVAILABLE",
                        "category": "GOVERNANCE",
                        "priority": 100,
                        "reason": reason,
                    }
                ],
                "consumed_inputs": [
                    "permission_envelope",
                    "subject_driver_state",
                    "release_binding",
                ],
            }
        )
        return _with_content_hash(result)

    evaluation_identity = {
        "investigation_request_id": investigation_request.get(
            "investigation_request_id"
        ),
        "subject_identity": driver_state["subject_identity"],
        "driver_state": driver_state,
        "library": "core-intervention-library:1",
    }
    options = _active_shipped_options(str(driver_state["trigger_mode"]))
    suppression_reasons: list[dict[str, Any]] = []
    for option in options:
        for suppression in option["suppression_reasons"]:
            if suppression not in suppression_reasons:
                suppression_reasons.append(deepcopy(suppression))
    suppression_reasons.sort(
        key=lambda item: (int(item["priority"]), str(item["code"]))
    )
    result.update(
        {
            "outcome": "NO_ELIGIBLE_OPTION",
            "state": "approval_dependent_suppressed",
            "primary_reason_code": "PRACTITIONER_REVIEW_UNAVAILABLE",
            "reason": (
                "Shipped Decision Support records remain provisional or unavailable "
                "because practitioner review is not claimed. Approval-dependent "
                "recommendations, trade-offs, monitoring, drafting, and authorization "
                "are suppressed."
            ),
            "next_step": (
                "Use the inspectable evidence and governed-record states; do not treat "
                "this shipped data as an approved action path."
            ),
            "decision_support_evaluation_id": evaluation_occurrence_id
            or _stable_id("dse", evaluation_identity),
            "decision_support_evaluation_series_id": evaluation_series_id
            or _stable_id("dses", evaluation_identity),
            "decision_support_driver_state_digest": _sha256(driver_state),
            "decision_support_input_digest": _sha256(
                {
                    "driver_state": driver_state,
                    "registry_inspection": registry_inspection,
                    "library": "core-intervention-library:1",
                    "links": [
                        {
                            "option_code": option["option_code"],
                            "state": option["evaluation_state"],
                            "suppression_reasons": option["suppression_reasons"],
                        }
                        for option in options
                    ],
                }
            ),
            "options": options,
            "suppression_reasons": suppression_reasons,
            "monitoring": {
                "state": "SUPPRESSED",
                "reason_code": "MONITORING_TRIGGER_UNDER_SPECIFIED",
            },
            "consumed_inputs": [
                "permission_envelope",
                "subject_driver_state",
                "intervention_library",
                "driver_action_links",
                "release_binding",
            ],
        }
    )
    return _with_content_hash(result)


def evaluate_synthetic_decision_support_fixture(
    *,
    fixture_case: Mapping[str, Any],
    governed_records: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one isolated synthetic conformance fixture through the public seam."""

    from .decision_support_constraints import evaluate_synthetic_fixture

    return evaluate_synthetic_fixture(
        fixture_case=fixture_case,
        governed_records=governed_records,
    )
