from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import struct
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import UUID

from .eligibility_contract import ADJUSTMENT_SET_FIELDS, LOAD_EXPOSURE_VARIANTS


ENGINE_INPUT_SCHEMA_VERSION = "causal-engine-suite-request.v2"
ENGINE_OUTPUT_SCHEMA_VERSION = "causal-engine-suite-result.v2"
ERROR_REGISTRY_VERSION = "causal-engine-errors.v1"
CAUSAL_QUESTION_ID = "supplier-congestion-to-milestone-slippage"
CAUSAL_QUESTION_VERSION = "v1"
ENGINE_CONFIG_ID = "core-local-cpu-hgb-doubleml"
ENGINE_CONFIG_VERSION = "v1"
SUITE_ID = "core-supplier-congestion-suite"
SUITE_VERSION = "v1"
PROPENSITY_SPEC_ID = "supplier-grouped-calibrated-hgb-5x2"
PROPENSITY_SPEC_VERSION = "v1"
SEED_POLICY_ID = "sha256-coordinate-seeds"
SEED_POLICY_VERSION = "v1"
ARTIFACT_CONTRACT_VERSION = "analysis-run-artifacts.v1"
VARIANT_ORDER = ("primary", "stricter_threshold", "short_history", "long_history")
ALLOWED_ROLES = frozenset(
    {"semi_synthetic_hero", "out_of_domain_validation", "rejection_vignette"}
)
ALLOWED_TRIGGER_MODES = frozenset({"historical", "reactive", "proactive"})
ALLOWED_UNAVAILABLE_CODES = frozenset(
    {
        "SOURCE_SEMANTICS_INELIGIBLE",
        "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT",
        "CORE_TEMPORAL_COVERAGE_INSUFFICIENT",
        "OUTCOME_COVERAGE_INSUFFICIENT",
        "CANCELLATION_COMPETING_EVENT_PRESENT",
        "COVARIATE_COVERAGE_INSUFFICIENT",
        "COHORT_SUPPORT_INSUFFICIENT",
        "OUTCOME_DEGENERATE",
    }
)
PROHIBITED_SCIENTIFIC_FIELDS = frozenset(
    {
        "analysis_run_id",
        "audit_actor",
        "delivery_mode",
        "evaluation_only_ground_truth",
        "post_treatment",
        "process_identity",
        "recommendation",
        "ui_route",
    }
)
OPERATIONAL_DELIVERY_FIELDS = frozenset(
    {
        "analysis_run_id",
        "audit_actor",
        "delivery_metadata",
        "delivery_mode",
        "process_identity",
        "requested_at",
        "started_at",
        "ui_route",
        "validation_state",
    }
)
SEED_COMPONENTS = (
    "inner_calibration_split",
    "propensity_learner",
    "outcome_learner_unexposed",
    "outcome_learner_exposed",
    "binary_outcome_learner_unexposed",
    "binary_outcome_learner_exposed",
    "continuous_outcome_learner",
    "continuous_exposure_learner",
)
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
REQUIRED_RUNTIME_DEPENDENCIES = {
    "doubleml": "0.11.3",
    "numpy": "2.2.6",
    "scikit-learn": "1.6.1",
    "scipy": "1.15.3",
    "statsmodels": "0.14.6",
}


class AnalysisRunRequestError(ValueError):
    """A fail-closed, redacted error at the fresh-run request boundary."""

    def __init__(
        self,
        code: str,
        recovery_action: str,
        status_code: int = 422,
    ) -> None:
        self.code = code
        self.recovery_action = recovery_action
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidatedSuiteRequest:
    request: dict[str, Any]
    scientific_request_digest: str


def _normalise_scientific(value: Any) -> Any:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("SCIENTIFIC_NUMBER_NONFINITE")
        if value == 0.0:
            return "f64:0x0.0p+0"
        return f"f64:{value.hex().lower()}"
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        normalised: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("SCIENTIFIC_OBJECT_KEY_INVALID")
            normalised_key = unicodedata.normalize("NFC", key)
            if normalised_key in normalised:
                raise ValueError("SCIENTIFIC_OBJECT_KEY_COLLISION")
            normalised[normalised_key] = _normalise_scientific(item)
        return normalised
    if isinstance(value, (list, tuple)):
        return [_normalise_scientific(item) for item in value]
    raise TypeError(f"unsupported scientific value: {type(value).__name__}")


def _scientific_input(value: object) -> object:
    if not isinstance(value, Mapping):
        return value
    return {
        key: item
        for key, item in value.items()
        if key not in OPERATIONAL_DELIVERY_FIELDS
    }


def scientific_json(value: object) -> str:
    """Encode the closed scientific JSON form without platform float drift."""

    return json.dumps(
        _normalise_scientific(_scientific_input(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def scientific_sha256(value: object) -> str:
    return f"sha256:{hashlib.sha256(scientific_json(value).encode('utf-8')).hexdigest()}"


def _require_mapping(value: Any, code: str = "ENGINE_INPUT_SCHEMA_UNSUPPORTED") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


def _require_text(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    return value


def _require_refs(value: Any) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    normalised = deepcopy(value)
    if any(item is None for item in normalised):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    try:
        return sorted(normalised, key=lambda item: scientific_json(item).encode("utf-8"))
    except (TypeError, ValueError):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED") from None


def _propensity_spec(adjustment_set: Mapping[str, Any]) -> dict[str, Any]:
    adjustment_ref = {
        "adjustment_set_id": adjustment_set.get("adjustment_set_id"),
        "adjustment_set_version": adjustment_set.get("adjustment_set_version"),
    }
    learner_parameters = {
        "learning_rate": 0.05,
        "max_iter": 200,
        "max_leaf_nodes": 15,
        "max_depth": None,
        "min_samples_leaf": 20,
        "l2_regularization": 1.0,
        "max_features": 1.0,
        "max_bins": 255,
        "categorical_features": None,
        "monotonic_cst": None,
        "interaction_cst": None,
        "early_stopping": False,
        "warm_start": False,
        "scoring": "loss",
        "validation_fraction": None,
        "n_iter_no_change": 10,
        "tol": 1e-7,
        "verbose": 0,
    }
    return {
        "propensity_spec_id": PROPENSITY_SPEC_ID,
        "propensity_spec_version": PROPENSITY_SPEC_VERSION,
        "training_stage": "S8_OUTCOME",
        "feature_schema_ref": adjustment_ref,
        "outer_splitter": "sklearn.model_selection.StratifiedGroupKFold",
        "outer_n_splits": 5,
        "outer_n_repeats": 2,
        "outer_stratify": "high_load_exposure",
        "outer_group": "supplier_id",
        "outer_shuffle": True,
        "base_learner": "sklearn.ensemble.HistGradientBoostingClassifier",
        "base_learner_parameters": learner_parameters,
        "calibrator": "sklearn.calibration.CalibratedClassifierCV",
        "calibration_method": "sigmoid",
        "calibration_splits": 3,
        "calibration_group": "supplier_id",
        "calibration_stratify": "high_load_exposure",
        "calibration_ensemble": True,
        "calibration_n_jobs": 1,
        "historical_aggregation": "arithmetic_mean_of_repeat_oof_probabilities",
        "subject_aggregation": "arithmetic_mean_of_ten_primary_outer_fold_models",
        "support_interval": {"lower": 0.10, "upper": 0.90, "inclusive": True},
        "doubleml_integration": "authoritative_mean_external_replicated_to_both_repeat_slots",
        "seed_policy_id": SEED_POLICY_ID,
        "seed_policy_version": SEED_POLICY_VERSION,
    }


def _validate_variant_input(value: Any, expected_variant: str) -> dict[str, Any]:
    variant = _require_mapping(value)
    if variant.get("variant_id") != expected_variant:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    expected_threshold = dict(
        (variant_id, rule_id)
        for variant_id, _, _, rule_id in LOAD_EXPOSURE_VARIANTS
    )[expected_variant]
    if variant.get("threshold_rule_ref") != expected_threshold:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    for key in ("cohort_stage_summaries", "upstream_status"):
        if key not in variant:
            raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if not isinstance(variant.get("cohort_stage_summaries"), Mapping) or not variant[
        "cohort_stage_summaries"
    ]:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if variant.get("upstream_status") not in {"released", "scientifically_unavailable"}:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    normalised = deepcopy(dict(variant))
    normalised["selector_refs"] = _require_refs(variant.get("selector_refs"))
    normalised["evidence_refs"] = _require_refs(variant.get("evidence_refs"))
    if variant["upstream_status"] == "scientifically_unavailable":
        if not isinstance(variant.get("gate_stage"), str) or not variant["gate_stage"]:
            raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
        if variant.get("scientific_code") not in ALLOWED_UNAVAILABLE_CODES:
            raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
        if "rows" in variant or "s8_identity_hash" in variant or "s8_content_hash" in variant:
            raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
        return normalised

    rows = variant.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    ordered_rows = sorted(
        (deepcopy(row) for row in rows),
        key=lambda row: str(row.get("order_line_id", "")).encode("utf-8"),
    )
    required_row_fields = {
        "order_line_id",
        "supplier_id",
        "high_load_exposure",
        "supplier_milestone_slippage_days",
        "supplier_milestone_slippage_duration_basis",
        "supplier_milestone_late",
        "load_percentile",
        "covariates",
        "lineage_refs",
    }
    for row in ordered_rows:
        row_mapping = _require_mapping(row)
        if set(row_mapping) != required_row_fields:
            raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
        if any(key in row_mapping for key in PROHIBITED_SCIENTIFIC_FIELDS):
            raise ValueError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        if not isinstance(row_mapping["order_line_id"], str) or not isinstance(
            row_mapping["supplier_id"], str
        ):
            raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
        if not isinstance(row_mapping["high_load_exposure"], bool) or not isinstance(
            row_mapping["supplier_milestone_late"], bool
        ):
            raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
        if (
            not isinstance(row_mapping["supplier_milestone_slippage_days"], (int, float))
            or isinstance(row_mapping["supplier_milestone_slippage_days"], bool)
            or not math.isfinite(float(row_mapping["supplier_milestone_slippage_days"]))
            or row_mapping["supplier_milestone_slippage_duration_basis"]
            not in {"CALENDAR_DAY", "ELAPSED_86400_SECOND_DAY"}
            or not isinstance(row_mapping["load_percentile"], (int, float))
            or isinstance(row_mapping["load_percentile"], bool)
            or not math.isfinite(float(row_mapping["load_percentile"]))
            or not 0 <= float(row_mapping["load_percentile"]) <= 1
        ):
            raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
        if not isinstance(row_mapping["covariates"], Mapping) or set(
            row_mapping["covariates"]
        ) != set(ADJUSTMENT_SET_FIELDS):
            raise ValueError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        row_mapping["lineage_refs"] = _require_refs(row_mapping["lineage_refs"])
    normalised["rows"] = ordered_rows
    identity_hash = scientific_sha256([row["order_line_id"] for row in ordered_rows])
    content_hash = scientific_sha256(
        {
            key: value
            for key, value in normalised.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )
    if normalised.get("s8_identity_hash") != identity_hash or normalised.get(
        "s8_content_hash"
    ) != content_hash:
        raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
    return normalised


def validate_suite_request(value: Mapping[str, Any]) -> ValidatedSuiteRequest:
    request = _require_mapping(value)
    required = {
        "engine_input_schema_version",
        "engine_output_schema_version",
        "error_registry_version",
        "causal_question_id",
        "causal_question_version",
        "engine_config_id",
        "engine_config_version",
        "dataset_version_id",
        "intended_role",
        "target_milestone_kind",
        "canonical_slippage_duration_basis",
        "trigger_mode",
        "observation_cutoff",
        "suite_id",
        "suite_version",
        "variant_inputs",
        "adjustment_set",
        "propensity_spec",
        "root_seed",
        "evidence_refs",
    }
    if set(request) - (required | {"subject"}) or not required.issubset(request):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if request.get("engine_input_schema_version") != ENGINE_INPUT_SCHEMA_VERSION:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if request.get("engine_output_schema_version") != ENGINE_OUTPUT_SCHEMA_VERSION:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if request.get("error_registry_version") != ERROR_REGISTRY_VERSION:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    exact_values = {
        "causal_question_id": CAUSAL_QUESTION_ID,
        "causal_question_version": CAUSAL_QUESTION_VERSION,
        "engine_config_id": ENGINE_CONFIG_ID,
        "engine_config_version": ENGINE_CONFIG_VERSION,
        "suite_id": SUITE_ID,
        "suite_version": SUITE_VERSION,
    }
    if any(request.get(key) != value for key, value in exact_values.items()):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if request.get("intended_role") not in ALLOWED_ROLES or request.get(
        "target_milestone_kind"
    ) not in {"supplier_completion", "supplier_handoff"}:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if request.get("canonical_slippage_duration_basis") not in {
        "CALENDAR_DAY",
        "ELAPSED_86400_SECOND_DAY",
    }:
        raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
    if request.get("trigger_mode") not in ALLOWED_TRIGGER_MODES:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if not isinstance(request.get("observation_cutoff"), Mapping):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    root_seed = request.get("root_seed")
    if (
        not isinstance(root_seed, int)
        or isinstance(root_seed, bool)
        or not 0 <= root_seed <= (2**64 - 1)
    ):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    variants = request.get("variant_inputs")
    if not isinstance(variants, list) or len(variants) != len(VARIANT_ORDER):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    normalised_variants = [
        _validate_variant_input(variant, expected)
        for variant, expected in zip(variants, VARIANT_ORDER, strict=True)
    ]
    for variant in normalised_variants:
        for row in variant.get("rows", []):
            if row["supplier_milestone_slippage_duration_basis"] != request[
                "canonical_slippage_duration_basis"
            ]:
                raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
    adjustment_set = _require_mapping(request.get("adjustment_set"))
    if adjustment_set.get("schema_version") != "adjustment-set.v1":
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if adjustment_set.get("fields") != list(ADJUSTMENT_SET_FIELDS):
        raise ValueError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    if not isinstance(adjustment_set.get("adjustment_set_id"), str) or not isinstance(
        adjustment_set.get("adjustment_set_version"), str
    ):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    expected_propensity = _propensity_spec(adjustment_set)
    if request.get("propensity_spec") != expected_propensity:
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    normalised: dict[str, Any] = deepcopy(dict(request))
    normalised["variant_inputs"] = normalised_variants
    normalised["evidence_refs"] = _require_refs(request.get("evidence_refs"))
    if "subject" in request:
        subject = _require_mapping(request.get("subject"))
        if any(key in subject for key in PROHIBITED_SCIENTIFIC_FIELDS):
            raise ValueError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        normalised["subject"] = deepcopy(dict(subject))
    try:
        digest = scientific_sha256(normalised)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH") from None
    return ValidatedSuiteRequest(normalised, digest)


def _field_value(value: Any) -> Any:
    if isinstance(value, Mapping) and value.get("state") == "present":
        return value.get("value")
    return value


def _dataset_follow_up_horizon_days(lineage: Mapping[str, Any]) -> int:
    for container in (
        lineage.get("dataset_version"),
        lineage.get("mapping_manifest"),
    ):
        if isinstance(container, Mapping):
            value = container.get("follow_up_horizon_days")
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
    return 0


def _first_unavailable_code(variant: Mapping[str, Any]) -> str:
    for gate in variant.get("gates", []):
        if isinstance(gate, Mapping) and gate.get("code") in ALLOWED_UNAVAILABLE_CODES:
            return str(gate["code"])
    code = variant.get("reason_code")
    if code in ALLOWED_UNAVAILABLE_CODES:
        return str(code)
    return "COHORT_SUPPORT_INSUFFICIENT"


def _stage_summaries(variant: Mapping[str, Any]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    stages = variant.get("stages", {})
    if not isinstance(stages, Mapping):
        return summaries
    for name, stage in stages.items():
        if not isinstance(stage, Mapping):
            continue
        summaries[str(name)] = {
            key: deepcopy(stage[key])
            for key in (
                "status",
                "selected_count",
                "selected_identity_hash",
                "denominator_count",
                "numerator_count",
                "eligibility_codes",
            )
            if key in stage
        }
    return summaries


def _row_from_eligibility(row: Mapping[str, Any], duration_basis: str) -> dict[str, Any]:
    outcome = row.get("outcome")
    inputs = row.get("inputs")
    if not isinstance(outcome, Mapping) or not isinstance(inputs, Mapping):
        raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
    slippage = outcome.get("supplier_milestone_slippage_days")
    if not isinstance(slippage, (int, float)) or isinstance(slippage, bool):
        raise ValueError("OUTCOME_COVERAGE_INSUFFICIENT")
    lineage_refs = row.get("lineage_refs")
    if not isinstance(lineage_refs, list) or not lineage_refs:
        raise ValueError("COVARIATE_COVERAGE_INSUFFICIENT")
    return {
        "order_line_id": str(row.get("id")),
        "supplier_id": str(row.get("supplier_id")),
        "high_load_exposure": bool(row.get("exposure")),
        "supplier_milestone_slippage_days": float(slippage),
        "supplier_milestone_slippage_duration_basis": duration_basis,
        "supplier_milestone_late": bool(outcome.get("supplier_milestone_late")),
        "load_percentile": row.get("load_percentile"),
        "covariates": deepcopy(dict(inputs)),
        "lineage_refs": sorted({str(ref) for ref in lineage_refs}),
    }


def _subject_input(
    investigation_request: Mapping[str, Any],
    causal_input: Mapping[str, Any],
    eligibility: Mapping[str, Any],
    evidence_refs: Sequence[Any],
) -> dict[str, Any] | None:
    subject = investigation_request.get("subject")
    analytical = causal_input.get("subject_analytical_values")
    if not isinstance(subject, Mapping) or not isinstance(analytical, Mapping):
        return None
    subject_id = subject.get("order_line_id") or subject.get("preview_subject_digest")
    if not isinstance(subject_id, str) or not subject_id:
        return None
    eligibility_subject = eligibility.get("subject")
    state = (
        str(eligibility_subject.get("state"))
        if isinstance(eligibility_subject, Mapping)
        else "unavailable"
    )
    return {
        "state": "eligible" if state == "eligible" else "scientifically_unavailable",
        "subject_id": subject_id,
        "profile": {
            "supplier_id": deepcopy(analytical.get("supplier_id")),
            "adjustment_inputs": deepcopy(analytical.get("adjustment_inputs", {})),
            "original_promise": deepcopy(analytical.get("original_promise")),
            "subject_exclusion_identity": subject_id,
            "decision_cutoff": deepcopy(causal_input.get("decision_cutoff")),
            "observation_cutoff": deepcopy(causal_input.get("observation_cutoff")),
            "target_milestone_kind": deepcopy(causal_input.get("target_milestone_kind")),
        },
        "scientific_code": (
            eligibility_subject.get("reason_code")
            if isinstance(eligibility_subject, Mapping)
            else "COHORT_SUPPORT_INSUFFICIENT"
        ),
        "evidence_refs": sorted({str(ref) for ref in evidence_refs}),
    }


def build_suite_request_from_investigation(
    store: Any,
    workspace_id: str,
    investigation_request: Mapping[str, Any],
    *,
    root_seed: int,
) -> dict[str, Any]:
    from .eligibility import evaluate_pre_estimation_eligibility

    causal_input = _require_mapping(investigation_request.get("causal_engine_input"))
    dataset_version_id = _require_text(investigation_request.get("dataset_version_id"))
    lineage = store.get_lineage(dataset_version_id)
    trigger_mode = str(investigation_request.get("trigger_mode"))
    if trigger_mode not in ALLOWED_TRIGGER_MODES:
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
            "SUBMIT_AN_ACCEPTED_INVESTIGATION_REQUEST_AND_RETRY",
        )
    subject = _require_mapping(investigation_request.get("subject"))
    subject_id = subject.get("order_line_id") or subject.get("preview_subject_digest")
    analytical = _require_mapping(causal_input.get("subject_analytical_values"))
    subject_supplier_id = _field_value(analytical.get("supplier_id"))
    target_milestone_kind = _field_value(causal_input.get("target_milestone_kind"))
    if not isinstance(subject_id, str) or not isinstance(subject_supplier_id, str):
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_INTEGRITY_MISMATCH",
            "SUBMIT_AN_ACCEPTED_INVESTIGATION_REQUEST_AND_RETRY",
        )
    subject_inputs = analytical.get("adjustment_inputs")
    eligibility = evaluate_pre_estimation_eligibility(
        lineage,
        subject_id=subject_id,
        subject_supplier_id=subject_supplier_id,
        decision_cutoff=causal_input.get("decision_cutoff"),
        observation_cutoff=causal_input.get("observation_cutoff"),
        target_milestone_kind=str(target_milestone_kind),
        duration_basis=str(causal_input.get("canonical_slippage_duration_basis")),
        trigger_mode=trigger_mode,
        follow_up_horizon_days=_dataset_follow_up_horizon_days(lineage),
        subject_inputs=subject_inputs if trigger_mode == "proactive" and isinstance(subject_inputs, Mapping) else None,
        subject_original_promise=analytical.get("original_promise") if trigger_mode == "proactive" else None,
        subject_target_milestone=subject.get("target_milestone_kind") if trigger_mode == "proactive" else None,
        include_engine_rows=True,
    )
    evidence_refs = [
        *(
            causal_input.get("analytical_fact_lineage_refs", [])
            if isinstance(causal_input.get("analytical_fact_lineage_refs"), list)
            else []
        ),
        *(
            investigation_request.get("provenance_refs", [])
            if isinstance(investigation_request.get("provenance_refs"), list)
            else []
        ),
        *(
            investigation_request.get("ingress_validation_refs", [])
            if isinstance(investigation_request.get("ingress_validation_refs"), list)
            else []
        ),
    ]
    evidence_refs = sorted({str(ref) for ref in evidence_refs if str(ref)})
    if not evidence_refs:
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_INTEGRITY_MISMATCH",
            "RESTORE_INVESTIGATION_EVIDENCE_AND_RETRY",
        )
    dataset = _require_mapping(lineage.get("dataset_version"))
    adjustment_set = {
        "schema_version": "adjustment-set.v1",
        "adjustment_set_id": "core-pre-treatment-adjustment-set",
        "adjustment_set_version": "v1",
        "fields": list(ADJUSTMENT_SET_FIELDS),
        "missingness_encoding": {
            "missing": "explicit_category",
            "not_applicable": "explicit_category",
            "unknown": "explicit_category",
            "redacted": "explicit_category",
        },
        "source_role": "pre_decision_canonical_or_proactive_input",
        "pre_treatment": True,
        "transformation_rule_id": "explicit-state-preserving.v1",
        "transformation_rule_version": "v1",
        "output_feature_names": list(ADJUSTMENT_SET_FIELDS),
        "field_definitions": [
            {
                "name": name,
                "logical_type": "typed_value",
                "estimation_encoding": "explicit_state_preserving",
                "pre_treatment": True,
            }
            for name in ADJUSTMENT_SET_FIELDS
        ],
    }
    variant_inputs: list[dict[str, Any]] = []
    private_rows = eligibility.get("_engine_rows", {})
    public_variants = eligibility.get("variants", {})
    for variant_id, _, _, threshold_rule_ref in LOAD_EXPOSURE_VARIANTS:
        public_variant = public_variants.get(variant_id, {})
        rows = private_rows.get(variant_id, []) if isinstance(private_rows, Mapping) else []
        row_payload: list[dict[str, Any]] = []
        row_error: str | None = None
        try:
            row_payload = [
                _row_from_eligibility(row, str(causal_input.get("canonical_slippage_duration_basis")))
                for row in rows
                if isinstance(row, Mapping)
            ]
        except ValueError as error:
            row_error = str(error)
        released = bool(row_payload) and row_error is None
        if released:
            row_payload = sorted(row_payload, key=lambda row: row["order_line_id"].encode("utf-8"))
            selector_refs = sorted(
                [
                    deepcopy(causal_input.get("estimator_window_ref")),
                    deepcopy(causal_input.get("history_lookback_ref")),
                ],
                key=lambda item: scientific_json(item).encode("utf-8"),
            )
            variant: dict[str, Any] = {
                "variant_id": variant_id,
                "threshold_rule_ref": threshold_rule_ref,
                "selector_refs": selector_refs,
                "cohort_stage_summaries": _stage_summaries(public_variant),
                "upstream_status": "released",
                "s8_identity_hash": scientific_sha256(
                    [row["order_line_id"] for row in row_payload]
                ),
                "s8_content_hash": "",
                "rows": row_payload,
                "evidence_refs": sorted({str(ref) for ref in evidence_refs}),
            }
            variant["s8_content_hash"] = scientific_sha256(
                {
                    key: value
                    for key, value in variant.items()
                    if key not in {"s8_identity_hash", "s8_content_hash"}
                }
            )
        else:
            code = row_error if row_error in ALLOWED_UNAVAILABLE_CODES else _first_unavailable_code(public_variant)
            selector_refs = sorted(
                [
                    deepcopy(causal_input.get("estimator_window_ref")),
                    deepcopy(causal_input.get("history_lookback_ref")),
                ],
                key=lambda item: scientific_json(item).encode("utf-8"),
            )
            variant = {
                "variant_id": variant_id,
                "threshold_rule_ref": threshold_rule_ref,
                "selector_refs": selector_refs,
                "cohort_stage_summaries": _stage_summaries(public_variant),
                "upstream_status": "scientifically_unavailable",
                "scientific_code": code,
                "gate_stage": "S8_OUTCOME",
                "evidence_refs": sorted({str(ref) for ref in evidence_refs}),
            }
        variant_inputs.append(variant)
    suite: dict[str, Any] = {
        "engine_input_schema_version": ENGINE_INPUT_SCHEMA_VERSION,
        "engine_output_schema_version": ENGINE_OUTPUT_SCHEMA_VERSION,
        "error_registry_version": ERROR_REGISTRY_VERSION,
        "causal_question_id": CAUSAL_QUESTION_ID,
        "causal_question_version": CAUSAL_QUESTION_VERSION,
        "engine_config_id": ENGINE_CONFIG_ID,
        "engine_config_version": ENGINE_CONFIG_VERSION,
        "dataset_version_id": dataset_version_id,
        "intended_role": dataset.get("intended_role"),
        "target_milestone_kind": target_milestone_kind,
        "canonical_slippage_duration_basis": causal_input.get(
            "canonical_slippage_duration_basis"
        ),
        "trigger_mode": trigger_mode,
        "observation_cutoff": deepcopy(causal_input.get("observation_cutoff")),
        "suite_id": SUITE_ID,
        "suite_version": SUITE_VERSION,
        "variant_inputs": variant_inputs,
        "adjustment_set": adjustment_set,
        "propensity_spec": _propensity_spec(adjustment_set),
        "root_seed": root_seed,
        "subject": _subject_input(investigation_request, causal_input, eligibility, evidence_refs),
        "evidence_refs": evidence_refs,
    }
    return suite


def _seed_material(request: Mapping[str, Any], **coordinates: Any) -> dict[str, Any]:
    return {
        "root_seed": request["root_seed"],
        "dataset_version_id": request["dataset_version_id"],
        "causal_question_id": request["causal_question_id"],
        "causal_question_version": request["causal_question_version"],
        "engine_config_id": request["engine_config_id"],
        "engine_config_version": request["engine_config_version"],
        "suite_id": request["suite_id"],
        "suite_version": request["suite_version"],
        "fixture_id": coordinates.get("fixture_id"),
        "variant_id": coordinates.get("variant_id"),
        "repeat_index": coordinates.get("repeat_index"),
        "outer_fold_index": coordinates.get("outer_fold_index"),
        "inner_fold_index": coordinates.get("inner_fold_index"),
        "component": coordinates["component"],
    }


def derived_seed_registry(request: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for variant_id in VARIANT_ORDER:
        for repeat_index in range(2):
            outer_material = _seed_material(
                request,
                variant_id=variant_id,
                repeat_index=repeat_index,
                outer_fold_index=None,
                inner_fold_index=None,
                component="outer_split",
            )
            entries.append(
                {
                    "component": "outer_split",
                    "variant_id": variant_id,
                    "repeat_index": repeat_index,
                    "outer_fold_index": None,
                    "inner_fold_index": None,
                    "seed_material": outer_material,
                    "seed": int.from_bytes(
                        hashlib.sha256(scientific_json(outer_material).encode("utf-8")).digest()[:4],
                        "big",
                    ),
                }
            )
            for outer_fold_index in range(5):
                for component in SEED_COMPONENTS:
                    material = _seed_material(
                        request,
                        variant_id=variant_id,
                        repeat_index=repeat_index,
                        outer_fold_index=outer_fold_index,
                        inner_fold_index=None,
                        component=component,
                    )
                    entries.append(
                        {
                            "component": component,
                            "variant_id": variant_id,
                            "repeat_index": repeat_index,
                            "outer_fold_index": outer_fold_index,
                            "inner_fold_index": None,
                            "seed_material": material,
                            "seed": int.from_bytes(
                                hashlib.sha256(scientific_json(material).encode("utf-8")).digest()[:4],
                                "big",
                            ),
                        }
                    )
                material = _seed_material(
                    request,
                    variant_id=variant_id,
                    repeat_index=repeat_index,
                    outer_fold_index=outer_fold_index,
                    inner_fold_index=None,
                    component="inner_calibration_split",
                )
                entries.append(
                    {
                        "component": "inner_calibration_split",
                        "variant_id": variant_id,
                        "repeat_index": repeat_index,
                        "outer_fold_index": outer_fold_index,
                        "inner_fold_index": None,
                        "seed_material": material,
                        "seed": int.from_bytes(
                            hashlib.sha256(scientific_json(material).encode("utf-8")).digest()[:4],
                            "big",
                        ),
                    }
                )
    return entries


def _lock_digest(path: Path) -> str | None:
    try:
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    except OSError:
        return None


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _runtime_is_compatible(runtime: Mapping[str, Any]) -> bool:
    python = runtime.get("python")
    dependencies = runtime.get("loaded_engine_dependencies")
    return (
        isinstance(python, Mapping)
        and python.get("implementation") == "CPython"
        and python.get("version") == "3.12.13"
        and dependencies == REQUIRED_RUNTIME_DEPENDENCIES
    )


def runtime_fingerprint(settings: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    base = settings.runtime_fingerprint.model_dump(mode="json")
    repo_root = Path(__file__).resolve().parents[2]
    dependencies = {
        "doubleml": _package_version("doubleml"),
        "numpy": _package_version("numpy"),
        "scikit-learn": _package_version("scikit-learn"),
        "scipy": _package_version("scipy"),
        "statsmodels": _package_version("statsmodels"),
    }
    environment_lock_digest = scientific_sha256(dependencies)
    return {
        "schema_version": "analysis-runtime-fingerprint.v1",
        "application_build_id": base["build_manifest_id"],
        "release_candidate_id": base["release_candidate_id"],
        "uv_lock_sha256": _lock_digest(repo_root / "uv.lock"),
        "environment_lock_sha256": environment_lock_digest,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "byteorder": sys.byteorder,
            "float_representation": {
                "format": "IEEE-754-binary64",
                "size_bytes": struct.calcsize("d"),
            },
        },
        "operating_system": {
            "family": platform.system(),
            "version": platform.release(),
            "architecture": platform.machine(),
        },
        "loaded_engine_dependencies": dependencies,
        "engine_contract": {
            "input_schema_version": request["engine_input_schema_version"],
            "output_schema_version": request["engine_output_schema_version"],
            "causal_question_id": request["causal_question_id"],
            "causal_question_version": request["causal_question_version"],
            "engine_config_id": request["engine_config_id"],
            "engine_config_version": request["engine_config_version"],
            "suite_id": request["suite_id"],
            "suite_version": request["suite_version"],
            "propensity_spec_id": PROPENSITY_SPEC_ID,
            "propensity_spec_version": PROPENSITY_SPEC_VERSION,
            "seed_policy_id": SEED_POLICY_ID,
            "seed_policy_version": SEED_POLICY_VERSION,
            "feature_schema_version": request["adjustment_set"]["adjustment_set_version"],
            "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        },
        "thread_policy": {
            "single_thread": True,
            "doubleml_n_jobs_cv": 1,
            "calibration_n_jobs": 1,
            "environment_variables": {name: "1" for name in THREAD_VARIABLES},
        },
        "numerical_backends": {"threadpoolctl": _package_version("threadpoolctl")},
    }


def build_fresh_analysis_payload(
    store: Any,
    workspace_id: str,
    request: Mapping[str, Any],
    settings: Any,
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
            "USE_THE_TYPED_FRESH_ANALYSIS_REQUEST",
        )
    suite_input = request.get("suite_request")
    investigation_request_id = request.get("investigation_request_id")
    if suite_input is None:
        if not isinstance(investigation_request_id, str) or not investigation_request_id:
            raise AnalysisRunRequestError(
                "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
                "SUBMIT_AN_ACCEPTED_INVESTIGATION_REQUEST_AND_RETRY",
            )
        if "root_seed" not in request:
            raise AnalysisRunRequestError(
                "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
                "PROVIDE_AN_EXPLICIT_ROOT_SEED_AND_RETRY",
            )
        investigation_request = store.get_investigation_request(
            workspace_id,
            investigation_request_id,
        )
        if investigation_request is None:
            raise AnalysisRunRequestError(
                "INVESTIGATION_REQUEST_UNAVAILABLE",
                "SUBMIT_AN_ACCEPTED_INVESTIGATION_REQUEST_AND_RETRY",
                404,
            )
        try:
            suite_input = build_suite_request_from_investigation(
                store,
                workspace_id,
                investigation_request,
                root_seed=request["root_seed"],
            )
        except AnalysisRunRequestError:
            raise
        except (KeyError, TypeError, ValueError):
            raise AnalysisRunRequestError(
                "ENGINE_INPUT_INTEGRITY_MISMATCH",
                "REBUILD_THE_FROZEN_ENGINE_REQUEST_AND_RETRY",
            ) from None
    try:
        validated = validate_suite_request(_require_mapping(suite_input))
    except ValueError as error:
        code = str(error)
        if code not in {
            "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
            "ENGINE_INPUT_INTEGRITY_MISMATCH",
            "ENGINE_FEATURE_CONTRACT_VIOLATION",
        }:
            code = "ENGINE_INPUT_INTEGRITY_MISMATCH"
        raise AnalysisRunRequestError(
            code,
            "CORRECT_THE_FROZEN_ENGINE_REQUEST_AND_RETRY",
        ) from None
    supplied_digest = request.get("scientific_request_digest")
    if supplied_digest is not None and supplied_digest != validated.scientific_request_digest:
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_INTEGRITY_MISMATCH",
            "REBUILD_THE_FROZEN_ENGINE_REQUEST_AND_RETRY",
        )
    supplied_root_seed = request.get("root_seed")
    if supplied_root_seed is not None and supplied_root_seed != validated.request["root_seed"]:
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_INTEGRITY_MISMATCH",
            "USE_ONE_ROOT_SEED_FOR_THE_FRESH_OCCURRENCE",
        )
    runtime = runtime_fingerprint(settings, validated.request)
    if not _runtime_is_compatible(runtime):
        raise AnalysisRunRequestError(
            "ENGINE_RUNTIME_INCOMPATIBLE",
            "USE_THE_SEALED_ENGINE_RUNTIME_AND_RETRY",
            503,
        )
    return {
        "schema_version": "analysis-run-admission.v1",
        "investigation_request_id": investigation_request_id,
        "suite_request": validated.request,
        "scientific_request_digest": validated.scientific_request_digest,
        "runtime_fingerprint": runtime,
        "runtime_fingerprint_digest": scientific_sha256(runtime),
        "derived_seed_registry": derived_seed_registry(validated.request),
        "estimator_descriptor": {
            "schema_version": "analysis-run-estimator-descriptor.v1",
            "estimator_executed": False,
            "estimator_stage": "S8_OUTCOME",
            "next_stage": "S9_OVERLAP",
            "propensity_spec": deepcopy(validated.request["propensity_spec"]),
            "execution_policy": "single_bounded_compute_subprocess",
        },
        "feature_descriptor": {
            "schema_version": "analysis-run-feature-descriptor.v1",
            "adjustment_set": deepcopy(validated.request["adjustment_set"]),
            "ordered_feature_names": list(ADJUSTMENT_SET_FIELDS),
            "prohibited_fields": sorted(
                {
                    "supplier_id",
                    "order_line_id",
                    "outcome_values",
                    "exposure_values",
                    "post_treatment",
                    "recommendation",
                    "evaluation_only_ground_truth",
                    "planted_effect",
                }
            ),
        },
        "fold_descriptor": {
            "schema_version": "analysis-run-fold-descriptor.v1",
            "splitter": "StratifiedGroupKFold",
            "outer_n_splits": 5,
            "outer_n_repeats": 2,
            "group_field": "supplier_id",
            "stratify_field": "high_load_exposure",
            "calibration_splits": 3,
            "n_jobs": 1,
            "sequential_variants": True,
        },
    }


def analysis_run_id_for_operation(operation_id: str) -> str:
    if not operation_id.startswith("operation-"):
        raise ValueError("operation identity is invalid")
    suffix = operation_id.removeprefix("operation-")
    try:
        parsed = UUID(suffix)
    except ValueError:
        raise ValueError("operation identity is invalid") from None
    if parsed.version != 4 or str(parsed) != suffix:
        raise ValueError("operation identity is invalid")
    return "analysis-run-" + suffix


def analysis_run_status(operation: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    state = str(operation.state)
    if state in {"QUEUED", "CANCELLING"}:
        status = "PENDING"
        lifecycle = "executing"
        outcome = "pending"
        verification = "pending"
        availability = "suppressed"
        reason_code = None
    elif state == "RUNNING":
        status = "RUNNING"
        lifecycle = "executing"
        outcome = "pending"
        verification = "pending"
        availability = "suppressed"
        reason_code = None
    elif state == "SUCCEEDED":
        status = "ABSTAINED"
        lifecycle = "sealed"
        outcome = "abstained"
        verification = "machine_verified"
        availability = "available"
        reason_code = "ENGINE_EXECUTION_DEFERRED"
    elif state in {"INTERRUPTED", "TIMED_OUT"}:
        status = "FAILED"
        lifecycle = "quarantined"
        outcome = "failed"
        verification = "invalid"
        availability = "suppressed"
        reason_code = operation.failure_code or "RUN_EXECUTION_INTERRUPTED"
    else:
        status = "FAILED"
        lifecycle = "failed"
        outcome = "failed"
        verification = "invalid"
        availability = "suppressed"
        reason_code = operation.failure_code or "ENGINE_EXECUTION_FAILED"
    return {
        "schema_version": "analysis-run-status.v1",
        "analysis_run_id": analysis_run_id_for_operation(operation.operation_id),
        "occurrence_id": operation.operation_id,
        "operation_id": operation.operation_id,
        "status": status,
        "lifecycle": lifecycle,
        "scientific_outcome": outcome,
        "verification_state": verification,
        "availability_state": availability,
        "delivery_mode": "fresh_execution",
        "reason_code": reason_code,
        "failure_code": operation.failure_code,
        "recovery_action": operation.recovery_action,
        "estimator_executed": False,
        "request_schema_version": payload["suite_request"]["engine_input_schema_version"],
        "scientific_request_digest": payload["scientific_request_digest"],
        "runtime_fingerprint": deepcopy(payload["runtime_fingerprint"]),
        "runtime_fingerprint_digest": payload["runtime_fingerprint_digest"],
        "root_seed": payload["suite_request"]["root_seed"],
        "derived_seed_registry": deepcopy(payload["derived_seed_registry"]),
        "estimator_descriptor": deepcopy(payload["estimator_descriptor"]),
        "feature_descriptor": deepcopy(payload["feature_descriptor"]),
        "fold_descriptor": deepcopy(payload["fold_descriptor"]),
    }


def is_strict_fresh_analysis_request(request: Mapping[str, Any]) -> bool:
    return any(
        key in request
        for key in ("suite_request", "investigation_request_id", "root_seed")
    )
