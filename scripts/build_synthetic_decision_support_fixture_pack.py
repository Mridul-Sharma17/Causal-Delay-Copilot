"""Build the checked-in test-only Decision Support conformance fixture pack.

The generated snapshots are consumed by tests and future conformance harnesses;
the application never imports this builder or the resulting ``tests`` tree.
Synthetic approval states describe fixture authority only. They do not claim
practitioner review, production approval, or external evaluation evidence.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.canonical import sha256 as _sha256  # noqa: E402
from backend.app.settings import DeliveryProfile, RuntimeFingerprint  # noqa: E402


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "decision_support" / "v1"
PACK_ID = "core-decision-support-conformance"
NAMESPACE = "synthetic:core-decision-support-v1:"
STORAGE_NAMESPACE = "synthetic://core-decision-support/v1"
RELEASE_BINDING = {
    "state": "TEST_ONLY_NOT_SHIPPED",
    "release_candidate_id": "synthetic-conformance-release-v1",
    "build_manifest_id": "synthetic-conformance-build-v1",
    "runtime_fingerprint_digest": "sha256:synthetic-conformance-runtime-v1",
}
PUBLISHED_AT = "2026-08-01T00:00:00+00:00"
DELIVERY_BINDING = {
    "schema_version": "synthetic-fixture-delivery-binding.v1",
    "profiles": [profile.value for profile in DeliveryProfile],
    "runtime_fingerprints": [
        RuntimeFingerprint(
            profile=profile,
            release_candidate_id=RELEASE_BINDING["release_candidate_id"],
            build_manifest_id=RELEASE_BINDING["build_manifest_id"],
        ).model_dump(mode="json")
        for profile in DeliveryProfile
    ],
    "demo_workspace": {
        "contract": "DemoWorkspaceResponse.v1",
        "ownership": "NONE",
        "selection": "PROHIBITED",
        "route": None,
        "reason": "Synthetic conformance fixtures are test-harness inputs only.",
    },
}
PROVENANCE = {
    "source_kind": "synthetic_conformance",
    "source_namespace": STORAGE_NAMESPACE,
    "generator_id": "core-decision-support-fixtures",
    "generator_version": "v1",
    "ground_truth": "SYNTHETIC_ONLY",
    "practitioner_validation": "NOT_PERFORMED",
    "production_authority": "PROHIBITED",
    "external_evaluation_eligibility": "PROHIBITED",
}
LABELS = ["SYNTHETIC", "TEST_ONLY", "NO_PRACTITIONER_VALIDATION", "NOT_SHIPPED"]
RELEASE_METADATA = {
    "release_binding_state": "TEST_ONLY_NOT_SHIPPED",
    "shipped_selection": "PROHIBITED",
    "reference_promotion": "PROHIBITED",
    "external_evaluation": "PROHIBITED",
    "release_copy": "PROHIBITED",
    "production_recommendation": "PROHIBITED",
}
PRESENTATION = {
    "test_only": True,
    "display_in_shipped_demo": False,
    "production_route": None,
    "test_route": "decision-support-fixture-harness",
    "badge": "Synthetic conformance fixture",
    "banner": "SYNTHETIC TEST DATA — not a shipped demo record",
    "evidence_disclosure": (
        "Approval states are fixture-only conformance inputs. No practitioner or "
        "production validation is claimed."
    ),
}
DIMENSIONS = (
    "CONTRACTUAL_RELATIONSHIP_RISK",
    "OPERATIONAL_DISRUPTION",
    "REVERSIBILITY",
)
OPTIONS = (
    (
        "PROTECTED_PRODUCTION_SLOT",
        "Protected production slot",
        ("REACTIVE", "PROACTIVE"),
        "ATOMIC",
    ),
    (
        "QUALIFIED_SOURCE_SPLIT",
        "Qualified source split",
        ("REACTIVE", "PROACTIVE"),
        "ATOMIC",
    ),
    (
        "PREQUALIFIED_ALTERNATE",
        "Prequalified alternate",
        ("REACTIVE", "PROACTIVE"),
        "ATOMIC",
    ),
    (
        "RELEASE_TIMING_ADJUSTMENT",
        "Release timing adjustment",
        ("PROACTIVE",),
        "ATOMIC",
    ),
    (
        "CAPACITY_BACKED_ACCELERATION",
        "Capacity-backed acceleration",
        ("REACTIVE", "PROACTIVE"),
        "ATOMIC",
    ),
    ("PHASED_DELIVERY", "Phased delivery", ("REACTIVE", "PROACTIVE"), "ATOMIC"),
    (
        "DEPENDENT_WORK_RESEQUENCING",
        "Dependent-work resequencing",
        ("REACTIVE",),
        "ATOMIC",
    ),
    ("CONTRACTUAL_ESCALATION", "Contractual escalation", ("REACTIVE",), "ATOMIC"),
    ("ACCEPT_AND_MONITOR", "Accept and monitor", ("REACTIVE", "PROACTIVE"), "ATOMIC"),
    (
        "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
        "Protected slot with phased delivery",
        ("REACTIVE", "PROACTIVE"),
        "COMPOSITE",
    ),
)
OPTION_RULES = {
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
RUBRIC_INPUT_FACTS = {
    "CONTRACTUAL_RELATIONSHIP_RISK": "PROTECTED_SLOT_SUPPLIER_ACCEPTED",
    "OPERATIONAL_DISRUPTION": "PHASED_HANDOFF_FEASIBLE",
    "REVERSIBILITY": "RELEASE_DATE_MOVABLE",
}
RUBRIC_OUTPUTS = {
    "CONTRACTUAL_RELATIONSHIP_RISK": ("LOW", "MEDIUM", "HIGH"),
    "OPERATIONAL_DISRUPTION": ("LOW", "MEDIUM", "HIGH"),
    "REVERSIBILITY": (
        "EASILY_REVERSIBLE",
        "PARTIALLY_REVERSIBLE",
        "DIFFICULT_TO_REVERSE",
    ),
}


def _identity(suffix: str) -> str:
    return f"{NAMESPACE}{suffix.replace('/', ':')}"


def _digest(value: object) -> str:
    return _sha256(value)


def _evidence_ref(suffix: str) -> dict[str, str]:
    reference = _identity(suffix)
    return {
        "reference": reference,
        "content_hash": _digest({"fixture_pack_id": PACK_ID, "reference": reference}),
    }


def _response_class(option_code: str) -> str:
    if option_code == "ACCEPT_AND_MONITOR":
        return "MONITOR_ONLY"
    if option_code in {
        "PROTECTED_PRODUCTION_SLOT",
        "CAPACITY_BACKED_ACCELERATION",
        "PROTECTED_SLOT_WITH_PHASED_DELIVERY",
    }:
        return "MILESTONE_ACCELERATION"
    if option_code in {
        "QUALIFIED_SOURCE_SPLIT",
        "PREQUALIFIED_ALTERNATE",
        "RELEASE_TIMING_ADJUSTMENT",
    }:
        return "EXPOSURE_REDUCTION"
    return "CONSEQUENCE_MITIGATION"


def _record(
    record_id: str,
    schema_identifier: str,
    **fields: object,
) -> dict[str, object]:
    record: dict[str, object] = {
        "record_id": record_id,
        "schema_identifier": schema_identifier,
        "schema_version": "1",
        "fixture_pack_id": PACK_ID,
        "labels": list(LABELS),
        "provenance": deepcopy(PROVENANCE),
        "release_binding": deepcopy(RELEASE_BINDING),
        "delivery_binding": deepcopy(DELIVERY_BINDING),
        "contract_status": "SYNTHETIC_CONFORMANCE_ONLY",
        "published_at": PUBLISHED_AT,
        "reviewer_role": "SYNTHETIC_CONFORMANCE_REVIEW",
        "review_reason_code": "synthetic_fixture_conformance",
        "review_date": PUBLISHED_AT,
        **fields,
    }
    record["content_hash"] = _digest(record)
    return record


def _option(
    display_order: int,
    option_code: str,
    label: str,
    trigger_modes: tuple[str, ...],
    shape: str,
) -> dict[str, object]:
    response_class = _response_class(option_code)
    option = {
        "record_id": _identity(f"options/{option_code.lower()}/v1"),
        "schema_identifier": "intervention-option",
        "schema_version": "1",
        "fixture_pack_id": PACK_ID,
        "labels": list(LABELS),
        "provenance": deepcopy(PROVENANCE),
        "release_binding": deepcopy(RELEASE_BINDING),
        "option_code": option_code,
        "option_version": "1",
        "display_order": display_order,
        "label": label,
        "lifecycle_status": "ACTIVE",
        "status": "ACTIVE",
        "allowed_trigger_modes": list(trigger_modes),
        "shape": shape,
        "component_codes": (
            ["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"]
            if shape == "COMPOSITE"
            else []
        ),
        "response_class": response_class,
        "required_constraint_rule_refs": [
            {
                "rule_code": rule_code,
                "rule_version": "1",
                "reference": _identity(f"constraint-rules/{rule_code.lower()}/v1"),
            }
            for rule_code in OPTION_RULES[option_code]
        ],
        "advisory_rubric_declarations": (
            [
                {
                    "dimension": dimension,
                    "trigger_mode": trigger_mode,
                    "rubric_reference": _identity(
                        f"advisory-rubrics/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}/v1"
                    ),
                }
                for trigger_mode in trigger_modes
                for dimension in DIMENSIONS
            ]
            if shape == "ATOMIC"
            else []
        ),
        "advisory_derivation": (
            None
            if shape == "ATOMIC"
            else {"kind": "LEAST_FAVORABLE_COMPONENT_RESULTS.v1"}
        ),
        "action_cost_formula_identifier": "declared-case-action-cost",
        "required_assumption_kind": (
            "NOT_APPLICABLE"
            if response_class == "MONITOR_ONLY"
            else "EXPOSURE_TRANSLATION"
            if response_class in {"EXPOSURE_REDUCTION", "MILESTONE_ACCELERATION"}
            else "CONSEQUENCE_BENEFIT"
        ),
        "benefit_policy": (
            "NO_BENEFIT_CLAIM"
            if response_class == "MONITOR_ONLY"
            else "ASSUMPTION_BASED_BENEFIT"
        ),
        "initiation_time_declaration": (
            "DECLARED_CASE_INITIATION_TIME.v1" if shape == "ATOMIC" else "PARALLEL"
        ),
        "explanation_template_identifier": _identity(
            f"explanation-templates/{option_code.lower()}/v1"
        ),
        "synthetic_approval_scope": "SYNTHETIC_CONFORMANCE_ONLY",
        "production_authority": "PROHIBITED",
    }
    option["content_hash"] = _digest(option)
    return option


def _build_records() -> dict[str, list[dict[str, object]]]:
    options = [
        _option(order, code, label, modes, shape)
        for order, (code, label, modes, shape) in enumerate(OPTIONS, start=10)
    ]
    libraries = [
        _record(
            _identity("intervention-libraries/core/v1"),
            "core-intervention-library",
            identifier="core-intervention-library",
            version="1",
            state="BUNDLED_CLOSED",
            lifecycle_status="ACTIVE",
            published_at="2026-08-01T00:00:00+00:00",
            predecessor_version_ref=None,
            supersession_ref=None,
            options=options,
            synthetic_approval_scope="SYNTHETIC_CONFORMANCE_ONLY",
        )
    ]

    links: list[dict[str, object]] = []
    for option_code, _, trigger_modes, shape in OPTIONS:
        for trigger_mode in trigger_modes:
            links.append(
                _record(
                    _identity(
                        f"driver-action-links/{option_code.lower()}/{trigger_mode.lower()}/v1"
                    ),
                    "driver-action-link",
                    link_id=_identity(
                        f"driver-action-links/{option_code.lower()}/{trigger_mode.lower()}/v1"
                    ),
                    link_version="1",
                    registry_identifier="supplier-congestion-driver-action-links",
                    registry_version="1",
                    driver_code="SUPPLIER_CONGESTION_HIGH_LOAD",
                    causal_question_ref=_identity("causal-questions/primary/v1"),
                    subject_verdict_claim_scope_ref=_identity(
                        "claim-scopes/supplier-high-load/v1"
                    ),
                    option_code=option_code,
                    option_version="1",
                    trigger_mode=trigger_mode,
                    link_kind=(
                        "MONITORING_BASELINE"
                        if option_code == "ACCEPT_AND_MONITOR"
                        else "ACTION_MECHANISM"
                    ),
                    mechanism_class=(
                        "NOT_APPLICABLE"
                        if option_code == "ACCEPT_AND_MONITOR"
                        else _response_class(option_code)
                    ),
                    mechanism_explanation_template=(
                        "NOT_APPLICABLE"
                        if option_code == "ACCEPT_AND_MONITOR"
                        else _identity(
                            f"mechanism-explanations/{option_code.lower()}/v1"
                        )
                    ),
                    baseline_rationale_template=(
                        _identity(
                            f"baseline-rationales/{option_code.lower()}/{trigger_mode.lower()}/v1"
                        )
                        if option_code == "ACCEPT_AND_MONITOR"
                        else "NOT_APPLICABLE"
                    ),
                    default_assumption_ref=(
                        "NOT_APPLICABLE"
                        if option_code == "ACCEPT_AND_MONITOR"
                        else _identity(
                            f"assumptions/{option_code.lower()}/{trigger_mode.lower()}/v1"
                        )
                    ),
                    source_refs=[
                        _evidence_ref(
                            f"sources/driver-action-link/{option_code.lower()}/{trigger_mode.lower()}"
                        )
                    ],
                    review_evidence_refs=[
                        _evidence_ref(
                            f"reviews/driver-action-link/{option_code.lower()}/{trigger_mode.lower()}/evidence"
                        )
                    ],
                    shape=shape,
                    state="APPROVED",
                    lifecycle_status="ACTIVE",
                    review_status="APPROVED",
                    approval_scope="SYNTHETIC_CONFORMANCE_ONLY",
                    reviewer_role="SYNTHETIC_CONFORMANCE_REVIEW",
                    review_reason_code="synthetic_fixture_approval",
                    review_reference=_identity(
                        f"reviews/driver-action-link/{option_code.lower()}/{trigger_mode.lower()}/v1"
                    ),
                    reviewed_at="2026-08-01T00:00:00+00:00",
                    review_date="2026-08-01T00:00:00+00:00",
                    review_available_at="2026-08-01T00:00:00+00:00",
                    predecessor_version_ref=None,
                    supersession_ref=None,
                    intervention_effect_estimated=False,
                    action_effect_evidence="INTERVENTION_EFFECT_NOT_ESTIMATED",
                )
            )

    rubrics: list[dict[str, object]] = []
    for option_code, _, trigger_modes, shape in OPTIONS:
        if shape != "ATOMIC":
            continue
        for trigger_mode in trigger_modes:
            for dimension in DIMENSIONS:
                input_fact_code = RUBRIC_INPUT_FACTS[dimension]
                output_values = RUBRIC_OUTPUTS[dimension]
                rubrics.append(
                    _record(
                        _identity(
                            f"advisory-rubrics/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}/v1"
                        ),
                        "advisory-rubric",
                        rubric_id=_identity(
                            f"advisory-rubrics/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}/v1"
                        ),
                        rubric_version="1",
                        registry_identifier="decision-support-advisory-rubrics",
                        option_code=option_code,
                        option_version="1",
                        trigger_mode=trigger_mode,
                        dimension=dimension,
                        applicability={
                            "option_code": option_code,
                            "option_version": "1",
                            "trigger_mode": trigger_mode,
                        },
                        typed_input_declarations=[
                            {
                                "fact_code": input_fact_code,
                                "value_type": "BOOLEAN",
                                "unit": "NOT_APPLICABLE",
                                "required": True,
                            }
                        ],
                        rules=[
                            {
                                "rule_id": _identity(
                                    f"rubric-rules/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}/true"
                                ),
                                "priority": 10,
                                "predicate": {
                                    "fact_code": input_fact_code,
                                    "operator": "EQ",
                                    "value": True,
                                },
                                "output": output_values[0],
                            },
                            {
                                "rule_id": _identity(
                                    f"rubric-rules/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}/false"
                                ),
                                "priority": 20,
                                "predicate": {
                                    "fact_code": input_fact_code,
                                    "operator": "EQ",
                                    "value": False,
                                },
                                "output": output_values[-1],
                            },
                        ],
                        rule_precedence={
                            "order": "ascending_priority",
                            "complete_for_declared_input": True,
                        },
                        state="APPROVED",
                        lifecycle_status="ACTIVE",
                        review_status="APPROVED",
                        approval_scope="SYNTHETIC_CONFORMANCE_ONLY",
                        reviewer_role="SYNTHETIC_CONFORMANCE_REVIEW",
                        review_reference=_identity(
                            f"reviews/advisory-rubric/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}/v1"
                        ),
                        review_date=PUBLISHED_AT,
                        reviewed_at="2026-08-01T00:00:00+00:00",
                        review_available_at="2026-08-01T00:00:00+00:00",
                        source_refs=[
                            _evidence_ref(
                                f"sources/advisory-rubric/{option_code.lower()}/{trigger_mode.lower()}/{dimension.lower()}"
                            )
                        ],
                        result_contract={
                            "unknown_code": "UNKNOWN",
                            "allowed_values": list(output_values),
                            "direction": "lower_is_more_favorable"
                            if dimension != "REVERSIBILITY"
                            else "more_reversible_is_more_favorable",
                        },
                        predecessor_version_ref=None,
                        supersession_ref=None,
                    )
                )

    triggers = [
        _record(
            _identity(f"monitoring-triggers/accept-and-monitor/{mode.lower()}/v1"),
            "monitoring-escalation-trigger",
            trigger_id=_identity(
                f"monitoring-triggers/accept-and-monitor/{mode.lower()}/v1"
            ),
            trigger_version="1",
            registry_identifier="decision-support-monitoring-escalation-triggers",
            registry_version="1",
            option_code="ACCEPT_AND_MONITOR",
            option_version="1",
            trigger_mode=mode,
            state="APPROVED",
            lifecycle_status="ACTIVE",
            review_status="APPROVED",
            approval_scope="SYNTHETIC_CONFORMANCE_ONLY",
            reviewer_role="SYNTHETIC_CONFORMANCE_REVIEW",
            review_reference=_identity(
                f"reviews/monitoring-trigger/accept-and-monitor/{mode.lower()}/v1"
            ),
            review_date=PUBLISHED_AT,
            reviewed_at="2026-08-01T00:00:00+00:00",
            review_available_at="2026-08-01T00:00:00+00:00",
            observation_registry={
                "registry_identifier": "decision-support-monitoring-observations",
                "registry_version": "1",
                "observation_code": "SUPPLIER_HIGH_LOAD_EXPOSURE",
                "value_type": "DECIMAL",
                "unit": "RATIO",
                "source_schema": {
                    "identifier": "subject-driver-state",
                    "version": "1",
                    "content_hash": _digest(
                        {
                            "schema_identifier": "subject-driver-state",
                            "schema_version": "1",
                        }
                    ),
                },
                "mapping_manifest_ref": _identity("mappings/monitoring-observation/v1"),
                "mapping_manifest_hash": _digest(
                    {
                        "mapping_manifest_ref": _identity(
                            "mappings/monitoring-observation/v1"
                        )
                    }
                ),
                "mapping_entry_code": "SUPPLIER_HIGH_LOAD_EXPOSURE",
            },
            operator="GTE",
            threshold={
                "state": "present",
                "value": "decimal:0.80",
                "value_type": "DECIMAL",
                "unit": "RATIO",
            },
            response_code="REQUEST_MANAGER_REVIEW",
            response="REQUEST_MANAGER_REVIEW",
            source_refs=[
                _evidence_ref(
                    f"sources/monitoring-trigger/accept-and-monitor/{mode.lower()}"
                )
            ],
            predecessor_version_ref=None,
            supersession_ref=None,
        )
        for mode in ("REACTIVE", "PROACTIVE")
    ]

    composites = [
        _record(
            _identity(
                f"composite-reviews/protected-slot-with-phased-delivery/{mode.lower()}/v1"
            ),
            "composite-compatibility-review",
            review_id=_identity(
                f"composite-reviews/protected-slot-with-phased-delivery/{mode.lower()}/v1"
            ),
            registry_identifier="decision-support-composite-compatibility-reviews",
            registry_version="1",
            result_version="1",
            composite_option_code="PROTECTED_SLOT_WITH_PHASED_DELIVERY",
            option_code="PROTECTED_SLOT_WITH_PHASED_DELIVERY",
            option_version="1",
            trigger_mode=mode,
            component_codes=["PROTECTED_PRODUCTION_SLOT", "PHASED_DELIVERY"],
            component_option_refs=[
                _identity("options/protected_production_slot/v1"),
                _identity("options/phased_delivery/v1"),
            ],
            composite_driver_action_link_ref=_identity(
                f"driver-action-links/protected_slot_with_phased_delivery/{mode.lower()}/v1"
            ),
            subject_identity=_identity(
                "subjects/approved-proactive"
                if mode == "PROACTIVE"
                else "subjects/approved-reactive"
            ),
            case_constraint_snapshot_ref=_identity(
                "constraints/approved-proactive/v1"
                if mode == "PROACTIVE"
                else "constraints/approved-reactive/v1"
            ),
            constraints_as_of=PUBLISHED_AT,
            composite_compatibility_input_digest=_digest(
                {
                    "fixture_pack_id": PACK_ID,
                    "mode": mode,
                    "subject_identity": _identity(
                        "subjects/approved-proactive"
                        if mode == "PROACTIVE"
                        else "subjects/approved-reactive"
                    ),
                }
            ),
            criteria_schema_identifier="composite-compatibility-criteria",
            criteria_schema_version="1",
            attestations=[
                {
                    "attestation_code": code,
                    "outcome": "ATTESTED_COMPATIBLE",
                    "review_status": "APPROVED",
                    "reviewer_role": "SYNTHETIC_CONFORMANCE_REVIEW",
                    "reviewer_reference": _identity(
                        f"reviews/composite/{mode.lower()}/{code.lower()}"
                    ),
                    "review_date": PUBLISHED_AT,
                    "review_reason_code": "synthetic_fixture_compatibility",
                    "review_reference": _identity(
                        f"reviews/composite/{mode.lower()}/{code.lower()}"
                    ),
                    "evidence_refs": [
                        _evidence_ref(
                            f"sources/composite/{mode.lower()}/{code.lower()}"
                        )
                    ],
                }
                for code in (
                    "COMPONENT_IDENTITIES_ALIGNED",
                    "PROTECTED_SLOT_PHASE_PLAN_ALIGNED",
                    "PHASE_TOTAL_AND_SEQUENCE_VALID",
                    "COMPONENT_OBLIGATIONS_NON_CONFLICTING",
                )
            ],
            outcome="COMPATIBLE",
            state="APPROVED",
            lifecycle_status="ACTIVE",
            review_status="APPROVED",
            approval_scope="SYNTHETIC_CONFORMANCE_ONLY",
            reviewer_role="SYNTHETIC_CONFORMANCE_REVIEW",
            review_reference=_identity(
                f"reviews/composite/protected-slot-with-phased-delivery/{mode.lower()}/v1"
            ),
            review_date=PUBLISHED_AT,
            reviewed_at="2026-08-01T00:00:00+00:00",
            review_available_at="2026-08-01T00:00:00+00:00",
            source_refs=[_evidence_ref(f"sources/composite/{mode.lower()}")],
            compatibility_status="SATISFIED",
            predecessor_version_ref=None,
            supersession_ref=None,
        )
        for mode in ("REACTIVE", "PROACTIVE")
    ]

    lifecycle_variants = [
        _record(
            _identity("lifecycle/approved-link-v1"),
            "driver-action-link",
            variant_kind="DRIVER_ACTION_LINK",
            lifecycle_state="APPROVED",
            record_version="1",
            predecessor_version_ref=None,
            supersession_ref=None,
            expected_currentness="CURRENT_AND_SUPPORTED",
        ),
        _record(
            _identity("lifecycle/rejected-link-v1"),
            "driver-action-link",
            variant_kind="DRIVER_ACTION_LINK",
            lifecycle_state="REJECTED",
            record_version="1",
            predecessor_version_ref=None,
            supersession_ref=None,
            expected_currentness="NOT_ELIGIBLE",
        ),
        _record(
            _identity("lifecycle/retired-trigger-v1"),
            "monitoring-escalation-trigger",
            variant_kind="MONITORING_ESCALATION_TRIGGER",
            lifecycle_state="RETIRED",
            record_version="1",
            predecessor_version_ref=None,
            supersession_ref=_identity("lifecycle/active-trigger-v2"),
            expected_currentness="NOT_CURRENT",
        ),
        _record(
            _identity("lifecycle/active-trigger-v2"),
            "monitoring-escalation-trigger",
            variant_kind="MONITORING_ESCALATION_TRIGGER",
            lifecycle_state="APPROVED",
            record_version="2",
            predecessor_version_ref=_identity("lifecycle/retired-trigger-v1"),
            supersession_ref=None,
            expected_currentness="CURRENT_AND_SUPPORTED",
        ),
        _record(
            _identity("lifecycle/superseded-library-v1"),
            "core-intervention-library",
            variant_kind="INTERVENTION_LIBRARY",
            lifecycle_state="SUPERSEDED",
            record_version="1",
            predecessor_version_ref=None,
            supersession_ref=_identity("lifecycle/active-library-v2"),
            expected_currentness="NOT_CURRENT",
        ),
        _record(
            _identity("lifecycle/active-library-v2"),
            "core-intervention-library",
            variant_kind="INTERVENTION_LIBRARY",
            lifecycle_state="APPROVED",
            record_version="2",
            predecessor_version_ref=_identity("lifecycle/superseded-library-v1"),
            supersession_ref=None,
            expected_currentness="CURRENT_AND_SUPPORTED",
        ),
        _record(
            _identity("lifecycle/expired-operational-input-v1"),
            "case-constraint-snapshot",
            variant_kind="OPERATIONAL_INPUT",
            lifecycle_state="EXPIRED",
            record_version="1",
            predecessor_version_ref=None,
            supersession_ref=None,
            valid_through="2026-07-31T23:59:59+00:00",
            expected_currentness="OPERATIONAL_FACT_EXPIRED",
        ),
    ]
    return {
        "intervention_libraries": libraries,
        "driver_action_links": links,
        "advisory_rubrics": rubrics,
        "monitoring_triggers": triggers,
        "composite_reviews": composites,
        "lifecycle_variants": lifecycle_variants,
    }


def _fact(
    case_name: str,
    fact_code: str,
    value: object,
    *,
    option_code: str | None = None,
    duration_basis: str | None = None,
    valid_through: str = "2026-08-08T00:00:00+00:00",
) -> dict[str, object]:
    suffix = f"facts/{case_name}/{fact_code.lower()}"
    if option_code is not None:
        suffix += f"/{option_code.lower()}"
    source_ref = _identity(suffix)
    fact: dict[str, object] = {
        "fact_code": fact_code,
        "state": "present",
        "value": value,
        "source_type": "VERIFIED_UPSTREAM_RECORD",
        "source_record_ref": source_ref,
        "provenance_ref": source_ref,
        "known_at": PUBLISHED_AT,
        "valid_through": valid_through,
        "source_available_at": PUBLISHED_AT,
        "recorded_at": PUBLISHED_AT,
    }
    if option_code is not None:
        fact["option_code"] = option_code
        fact["option_version"] = "1"
    if duration_basis is not None:
        fact["duration_basis"] = duration_basis
    return fact


def _build_release_timing_preview(case_name: str, subject_id: str) -> dict[str, object]:
    preview = {
        "preview_id": _identity(f"release-previews/{case_name}/v1"),
        "record_id": _identity(f"release-previews/{case_name}/v1"),
        "schema_identifier": "release-timing-preview",
        "schema_version": "1",
        "created_at": PUBLISHED_AT,
        "base_subject_profile_ref_and_hash": _evidence_ref(
            f"subject-profiles/{case_name}/v1"
        ),
        "base_investigation_request_ref_and_hash": _evidence_ref(
            f"investigation-requests/{case_name}/v1"
        ),
        "base_analysis_run_bundle_ref_and_hash": _evidence_ref(
            f"analysis-runs/{case_name}/bundle/v1"
        ),
        "scientific_request_digest": _digest(
            {"fixture_pack_id": PACK_ID, "case_name": case_name}
        ),
        "base_proactive_proposal_identity": {
            "source_system": "synthetic-conformance",
            "proposal_id": _identity(f"proposals/{case_name}/v1"),
            "proposal_revision": "1",
            "dataset_version_id": _identity(f"datasets/{case_name}"),
        },
        "supplier": _identity(f"suppliers/{case_name}"),
        "target_milestone_kind": "PROMISED_DELIVERY",
        "dataset_version_id": _identity(f"datasets/{case_name}"),
        "base_causal_decision_at": PUBLISHED_AT,
        "constraints_as_of": PUBLISHED_AT,
        "selector_refs": [_identity(f"selectors/{case_name}/primary/v1")],
        "threshold_rule_ref": _identity("threshold-rules/high-load/v1"),
        "candidate_release_at": "2026-08-03T00:00:00+00:00",
        "candidate_promised_target_milestone": "2026-08-10T00:00:00+00:00",
        "alternate_decision_at": "2026-08-03T00:00:00+00:00",
        "provisional_concurrent_load_count": 7,
        "provisional_load_percentile": "decimal:0.90",
        "provisional_high_load_preview": True,
        "calculation_inputs": [
            {
                "input_code": "CONCURRENT_LOAD_COUNT",
                "value": 7,
                "known_at": PUBLISHED_AT,
                "provenance_ref": _identity(f"preview-inputs/{case_name}/load"),
                "content_hash": _digest(
                    {"case_name": case_name, "input_code": "CONCURRENT_LOAD_COUNT"}
                ),
            }
        ],
        "preview_subject_identity": subject_id,
        "valid_through": "2026-08-08T00:00:00+00:00",
        "provenance": deepcopy(PROVENANCE),
    }
    preview["content_hash"] = _digest(preview)
    return preview


def _build_case_constraint_snapshot(
    case_name: str,
    subject_id: str,
    *,
    release_preview: dict[str, object] | None,
) -> dict[str, object]:
    facts: list[dict[str, object]] = [
        _fact(
            case_name,
            "AVAILABLE_FLOAT_DAYS",
            "decimal:5",
            duration_basis="CALENDAR_DAY",
        ),
        _fact(
            case_name,
            "TIME_TO_INITIATE_DAYS",
            "decimal:2",
            option_code="PROTECTED_PRODUCTION_SLOT",
            duration_basis="CALENDAR_DAY",
        ),
        _fact(
            case_name,
            "PROTECTED_SLOT_MECHANISM_KIND",
            "PROTECTED_SLOT",
            option_code="PROTECTED_PRODUCTION_SLOT",
        ),
        _fact(
            case_name,
            "PROTECTED_SLOT_SUPPLIER_ACCEPTED",
            True,
            option_code="PROTECTED_PRODUCTION_SLOT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "QUALIFIED_SOURCE_COUNT",
            2,
            option_code="QUALIFIED_SOURCE_SPLIT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "SPLIT_SPEC_PERMITTED",
            True,
            option_code="QUALIFIED_SOURCE_SPLIT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "SPLIT_CONTRACT_PERMITTED",
            True,
            option_code="QUALIFIED_SOURCE_SPLIT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "SPLIT_MINIMUM_QUANTITIES_SATISFIED",
            True,
            option_code="QUALIFIED_SOURCE_SPLIT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ALTERNATE_CURRENTLY_QUALIFIED",
            True,
            option_code="PREQUALIFIED_ALTERNATE",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ALTERNATE_SUBSTITUTION_PERMITTED",
            True,
            option_code="PREQUALIFIED_ALTERNATE",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ALTERNATE_WORK_TRANSFERABLE",
            True,
            option_code="PREQUALIFIED_ALTERNATE",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "RELEASE_DATE_MOVABLE",
            True,
            option_code="RELEASE_TIMING_ADJUSTMENT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "RELEASE_MILESTONE_FEASIBLE",
            True,
            option_code="RELEASE_TIMING_ADJUSTMENT",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ACCELERATION_MECHANISM_KIND",
            "OVERTIME_CAPACITY",
            option_code="CAPACITY_BACKED_ACCELERATION",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ACCELERATION_SUPPLIER_ACCEPTED",
            True,
            option_code="CAPACITY_BACKED_ACCELERATION",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ACCELERATION_CONTRACT_PERMITTED",
            True,
            option_code="CAPACITY_BACKED_ACCELERATION",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "PHASED_HANDOFF_FEASIBLE",
            True,
            option_code="PHASED_DELIVERY",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "PHASED_DOWNSTREAM_CONSUMABLE",
            True,
            option_code="PHASED_DELIVERY",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "PHASED_CONTRACT_PERMITTED",
            True,
            option_code="PHASED_DELIVERY",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "RESEQUENCE_PLAN_REVIEWED",
            True,
            option_code="DEPENDENT_WORK_RESEQUENCING",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "RESEQUENCE_PREREQUISITES_VALID",
            True,
            option_code="DEPENDENT_WORK_RESEQUENCING",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "RESEQUENCE_NO_NEW_CRITICAL_PATH_BREACH",
            True,
            option_code="DEPENDENT_WORK_RESEQUENCING",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ESCALATION_BASIS_ENFORCEABLE",
            True,
            option_code="CONTRACTUAL_ESCALATION",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ESCALATION_NOTICE_WINDOW_OPEN",
            True,
            option_code="CONTRACTUAL_ESCALATION",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "ESCALATION_RECORDS_COMPLETE",
            True,
            option_code="CONTRACTUAL_ESCALATION",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "MONITORING_OWNER_REF",
            _identity(f"owners/{case_name}/monitoring"),
            option_code="ACCEPT_AND_MONITOR",
            valid_through="NO_EXPIRY",
        ),
        _fact(
            case_name,
            "MONITORING_NEXT_REVIEW_AT",
            "2026-08-02T00:00:00+00:00",
            option_code="ACCEPT_AND_MONITOR",
            valid_through="NO_EXPIRY",
        ),
    ]
    if release_preview is not None:
        facts.extend(
            [
                _fact(
                    case_name,
                    "REVISED_PROVISIONAL_HIGH_LOAD_PREVIEW",
                    {
                        "value": True,
                        "preview_ref": release_preview["preview_id"],
                        "preview_hash": release_preview["content_hash"],
                    },
                    option_code="RELEASE_TIMING_ADJUSTMENT",
                    valid_through="NO_EXPIRY",
                ),
                _fact(
                    case_name,
                    "MONITORING_ESCALATION_TRIGGER_REF",
                    {
                        "reference": _identity(
                            "monitoring-triggers/accept-and-monitor/proactive/v1"
                        ),
                        "content_hash": _digest(
                            {"case_name": case_name, "trigger_mode": "PROACTIVE"}
                        ),
                    },
                    option_code="ACCEPT_AND_MONITOR",
                    valid_through="NO_EXPIRY",
                ),
            ]
        )
    else:
        facts.append(
            _fact(
                case_name,
                "MONITORING_ESCALATION_TRIGGER_REF",
                {
                    "reference": _identity(
                        "monitoring-triggers/accept-and-monitor/reactive/v1"
                    ),
                    "content_hash": _digest(
                        {"case_name": case_name, "trigger_mode": "REACTIVE"}
                    ),
                },
                option_code="ACCEPT_AND_MONITOR",
                valid_through="NO_EXPIRY",
            )
        )
    mode = "proactive" if release_preview is not None else "reactive"
    facts.append(
        _fact(
            case_name,
            "COMPOSITE_COMPATIBILITY_REVIEW_REF",
            {
                "reference": _identity(
                    f"composite-reviews/protected-slot-with-phased-delivery/{mode}/v1"
                ),
                "content_hash": _digest({"case_name": case_name, "mode": mode}),
            },
            option_code="PROTECTED_SLOT_WITH_PHASED_DELIVERY",
            valid_through="NO_EXPIRY",
        )
    )
    snapshot = {
        "snapshot_id": _identity(f"constraints/{case_name}/v1"),
        "record_id": _identity(f"constraints/{case_name}/v1"),
        "schema_identifier": "case-constraint-snapshot",
        "schema_version": "1",
        "snapshot_version": "1",
        "subject_identity": subject_id,
        "causal_decision_at": PUBLISHED_AT,
        "constraints_as_of": PUBLISHED_AT,
        "created_at": PUBLISHED_AT,
        "idempotency_key": _identity(f"constraint-attempts/{case_name}/v1"),
        "source": {
            "source_type": "SYNTHETIC_CONFORMANCE_FIXTURE",
            "source_kind": "synthetic_conformance",
            "provenance_ref": _identity(f"provenance/{case_name}"),
        },
        "evidence_refs": [_evidence_ref(f"evidence/constraints/{case_name}/v1")],
        "facts": facts,
        "provenance": deepcopy(PROVENANCE),
    }
    snapshot["content_hash"] = _digest(snapshot)
    return snapshot


def _case(
    case_name: str,
    *,
    fixture_kind: str,
    trigger_mode: str,
    expected_branch: str,
    driver_active: bool,
    permission: bool,
    include_operational_inputs: bool,
    lifecycle_variant_ids: list[str],
) -> dict[str, object]:
    fixture_id = _identity(f"fixtures/{case_name}")
    subject_id = _identity(f"subjects/{case_name}")
    identity: dict[str, object] = {
        "dataset_version_id": _identity(f"datasets/{case_name}"),
        "supplier_id": _identity(f"suppliers/{case_name}"),
    }
    subject_driver_state = {
        "schema_identifier": "subject-driver-state",
        "schema_version": "1",
        "kind": (
            "high_load_exposure"
            if trigger_mode == "reactive"
            else "provisional_high_load_preview"
        ),
        "value": driver_active,
        "subject_identity": subject_id,
        "trigger_mode": trigger_mode.upper(),
        "synthetic_only": True,
    }
    if trigger_mode == "reactive":
        identity["order_line_id"] = subject_id
    else:
        identity["preview_subject_digest"] = subject_id

    operational_inputs: dict[str, object] = {
        "case_constraint_snapshot": None,
        "release_timing_preview": None,
    }
    if include_operational_inputs:
        release_preview: dict[str, object] | None = None
        if trigger_mode == "proactive":
            release_preview = _build_release_timing_preview(case_name, subject_id)
            operational_inputs["release_timing_preview"] = release_preview
        operational_inputs["case_constraint_snapshot"] = (
            _build_case_constraint_snapshot(
                case_name,
                subject_id,
                release_preview=release_preview,
            )
        )

    case = {
        "fixture_id": fixture_id,
        "fixture_version": "v1",
        "fixture_kind": fixture_kind,
        "label": f"Synthetic conformance — {case_name.replace('-', ' ')}",
        "trigger_mode": trigger_mode,
        "expected_branch": expected_branch,
        "identity": identity,
        "provenance": deepcopy(PROVENANCE),
        "labels": list(LABELS),
        "release_metadata": deepcopy(RELEASE_METADATA),
        "release_binding": deepcopy(RELEASE_BINDING),
        "presentation": deepcopy(PRESENTATION),
        "subject_driver_state": subject_driver_state,
        "evidence": {
            "subject_verdict": {
                "record_id": _identity(f"evidence/{case_name}/subject-verdict/v1"),
                "schema_identifier": "evidence-verdict",
                "schema_version": "evidence-verdict.v2",
                "scope": "subject",
                "verdict_code": (
                    "SUPPORTED_UNDER_ASSUMPTIONS" if permission else "TENTATIVE"
                ),
                "subject_identity": subject_id,
                "decision_support_role_permitted": permission,
                "decision_support_evaluation_permitted": permission,
                "synthetic_only": True,
            },
            "permission_reason_code": (
                None if permission else "SYNTHETIC_FIXTURE_PERMISSION_DENIED"
            ),
        },
        "operational_inputs": operational_inputs,
        "governed_record_refs": {
            "intervention_library": _identity("intervention-libraries/core/v1"),
            "driver_action_links": [
                _identity(
                    f"driver-action-links/protected_production_slot/{trigger_mode}/v1"
                ),
                _identity(f"driver-action-links/accept_and_monitor/{trigger_mode}/v1"),
            ],
            "advisory_rubrics": [
                _identity(
                    f"advisory-rubrics/protected_production_slot/{trigger_mode}/contractual_relationship_risk/v1"
                ),
                _identity(
                    f"advisory-rubrics/protected_production_slot/{trigger_mode}/operational_disruption/v1"
                ),
                _identity(
                    f"advisory-rubrics/protected_production_slot/{trigger_mode}/reversibility/v1"
                ),
            ],
            "monitoring_triggers": [
                _identity(f"monitoring-triggers/accept-and-monitor/{trigger_mode}/v1")
            ],
            "composite_reviews": [
                _identity(
                    f"composite-reviews/protected-slot-with-phased-delivery/{trigger_mode}/v1"
                )
            ],
        },
        "lifecycle_variant_ids": lifecycle_variant_ids,
    }
    case["content_hash"] = _digest(case)
    return case


def _build_cases(
    records: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    return [
        _case(
            "approved-reactive",
            fixture_kind="APPROVAL_BEARING_ACTIVE",
            trigger_mode="reactive",
            expected_branch="ACTIVE_APPROVED_REACTIVE",
            driver_active=True,
            permission=True,
            include_operational_inputs=True,
            lifecycle_variant_ids=[
                str(
                    next(
                        record["record_id"]
                        for record in records["lifecycle_variants"]
                        if record["lifecycle_state"] == "APPROVED"
                    )
                )
            ],
        ),
        _case(
            "approved-proactive",
            fixture_kind="APPROVAL_BEARING_ACTIVE",
            trigger_mode="proactive",
            expected_branch="ACTIVE_APPROVED_PROACTIVE",
            driver_active=True,
            permission=True,
            include_operational_inputs=True,
            lifecycle_variant_ids=[],
        ),
        _case(
            "inactive-driver",
            fixture_kind="INACTIVE_DRIVER",
            trigger_mode="reactive",
            expected_branch="INACTIVE_DRIVER",
            driver_active=False,
            permission=True,
            include_operational_inputs=False,
            lifecycle_variant_ids=[],
        ),
        _case(
            "permission-denied",
            fixture_kind="PERMISSION_DENIED",
            trigger_mode="reactive",
            expected_branch="PERMISSION_DENIED",
            driver_active=True,
            permission=False,
            include_operational_inputs=False,
            lifecycle_variant_ids=[],
        ),
        _case(
            "lifecycle-superseded",
            fixture_kind="LIFECYCLE_VARIANT",
            trigger_mode="reactive",
            expected_branch="LIFECYCLE_SUPERSEDED",
            driver_active=True,
            permission=True,
            include_operational_inputs=True,
            lifecycle_variant_ids=[
                str(
                    next(
                        record["record_id"]
                        for record in records["lifecycle_variants"]
                        if record["lifecycle_state"] == "SUPERSEDED"
                    )
                ),
                str(
                    next(
                        record["record_id"]
                        for record in records["lifecycle_variants"]
                        if record["lifecycle_state"] == "RETIRED"
                    )
                ),
            ],
        ),
        _case(
            "operational-fact-expired",
            fixture_kind="LIFECYCLE_VARIANT",
            trigger_mode="reactive",
            expected_branch="OPERATIONAL_FACT_EXPIRED",
            driver_active=True,
            permission=True,
            include_operational_inputs=True,
            lifecycle_variant_ids=[
                str(
                    next(
                        record["record_id"]
                        for record in records["lifecycle_variants"]
                        if record["lifecycle_state"] == "EXPIRED"
                    )
                ),
            ],
        ),
        _case(
            "link-rejected",
            fixture_kind="LIFECYCLE_VARIANT",
            trigger_mode="reactive",
            expected_branch="LINK_REJECTED",
            driver_active=True,
            permission=True,
            include_operational_inputs=True,
            lifecycle_variant_ids=[
                str(
                    next(
                        record["record_id"]
                        for record in records["lifecycle_variants"]
                        if record["lifecycle_state"] == "REJECTED"
                    )
                ),
            ],
        ),
    ]


def _finalize_case_bindings(
    records: dict[str, list[dict[str, object]]],
    cases: list[dict[str, object]],
) -> None:
    triggers = {
        str(record["trigger_mode"]): record for record in records["monitoring_triggers"]
    }
    composites = {
        str(record["trigger_mode"]): record for record in records["composite_reviews"]
    }
    for case in cases:
        operational_inputs = case.get("operational_inputs")
        if not isinstance(operational_inputs, dict):
            continue
        snapshot = operational_inputs.get("case_constraint_snapshot")
        if not isinstance(snapshot, dict):
            continue
        mode = str(case["trigger_mode"]).upper()
        composite = composites[mode]
        facts = [
            fact
            for fact in snapshot["facts"]
            if fact["fact_code"] != "COMPOSITE_COMPATIBILITY_REVIEW_REF"
        ]
        trigger = triggers[mode]
        for fact in snapshot["facts"]:
            if fact["fact_code"] == "MONITORING_ESCALATION_TRIGGER_REF":
                fact["value"] = {
                    "reference": trigger["record_id"],
                    "content_hash": trigger["content_hash"],
                }

        if str(case["expected_branch"]).startswith("ACTIVE_APPROVED_"):
            composite["composite_compatibility_input_digest"] = _digest(
                {
                    "snapshot_id": snapshot["snapshot_id"],
                    "subject_identity": snapshot["subject_identity"],
                    "causal_decision_at": snapshot["causal_decision_at"],
                    "constraints_as_of": snapshot["constraints_as_of"],
                    "ordered_snapshot_facts_excluding_COMPOSITE_COMPATIBILITY_REVIEW_REF": facts,
                }
            )
            composite["content_hash"] = _digest(
                {
                    key: value
                    for key, value in composite.items()
                    if key != "content_hash"
                }
            )

        for fact in snapshot["facts"]:
            if fact["fact_code"] == "COMPOSITE_COMPATIBILITY_REVIEW_REF":
                fact["value"] = {
                    "reference": composite["record_id"],
                    "content_hash": composite["content_hash"],
                }
        snapshot["content_hash"] = _digest(
            {key: value for key, value in snapshot.items() if key != "content_hash"}
        )
        case["content_hash"] = _digest(
            {key: value for key, value in case.items() if key != "content_hash"}
        )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def main() -> None:
    records = _build_records()
    cases = _build_cases(records)
    _finalize_case_bindings(records, cases)
    records_payload = {
        "schema_version": "synthetic-governed-records.v1",
        "fixture_pack_id": PACK_ID,
        **records,
    }
    cases_payload = {
        "schema_version": "synthetic-decision-support-cases.v1",
        "fixture_pack_id": PACK_ID,
        "fixtures": cases,
    }
    _write_json(FIXTURE_ROOT / "records.json", records_payload)
    _write_json(FIXTURE_ROOT / "cases.json", cases_payload)

    manifest = {
        "fixture_pack_schema_version": "decision-support-conformance-fixtures.v1",
        "fixture_pack_id": PACK_ID,
        "fixture_pack_version": "v1",
        "storage_namespace": STORAGE_NAMESPACE,
        "source_kind": "synthetic_conformance",
        "intended_role": "synthetic_conformance",
        "contract_status": "SYNTHETIC_CONFORMANCE_ONLY",
        "delivery_binding": deepcopy(DELIVERY_BINDING),
        "records_path": "records.json",
        "cases_path": "cases.json",
        "records_sha256": "sha256:"
        + hashlib.sha256((FIXTURE_ROOT / "records.json").read_bytes()).hexdigest(),
        "cases_sha256": "sha256:"
        + hashlib.sha256((FIXTURE_ROOT / "cases.json").read_bytes()).hexdigest(),
        "fixture_ids": [str(case["fixture_id"]) for case in cases],
        "fixture_count": len(cases),
        "labels": list(LABELS),
        "synthetic_disclosure": {
            "is_synthetic": True,
            "label": "Synthetic conformance fixture pack",
            "provenance": deepcopy(PROVENANCE),
            "practitioner_validation": "NOT_PERFORMED",
            "production_authority": "PROHIBITED",
        },
        "release_metadata": {
            **deepcopy(RELEASE_METADATA),
            "release_binding_state": "TEST_ONLY_NOT_SHIPPED",
        },
        "presentation": deepcopy(PRESENTATION),
    }
    _write_json(FIXTURE_ROOT / "manifest.json", manifest)


if __name__ == "__main__":
    main()
