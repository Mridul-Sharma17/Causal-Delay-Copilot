from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
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

from .canonical import canonical_json, sha256 as content_sha256
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
PROPENSITY_RESULT_SCHEMA_VERSION = "analysis-run-propensity-result.v1"
VARIANT_ORDER = ("primary", "stricter_threshold", "short_history", "long_history")
SENSITIVITY_VARIANTS = ("stricter_threshold", "short_history", "long_history")
SENSITIVITY_ESTIMAND_IDS = {
    "stricter_threshold": "sensitivity_stricter_atte_slippage",
    "short_history": "sensitivity_short_history_atte_slippage",
    "long_history": "sensitivity_long_history_atte_slippage",
}
LATE_SENSITIVITY_ESTIMAND_ID = "sensitivity_late_risk_atte"
CONTINUOUS_LOAD_SENSITIVITY_ESTIMAND_ID = "sensitivity_continuous_load_slope"
SECONDARY_ESTIMAND_IDS = (
    *SENSITIVITY_ESTIMAND_IDS.values(),
    LATE_SENSITIVITY_ESTIMAND_ID,
    CONTINUOUS_LOAD_SENSITIVITY_ESTIMAND_ID,
)
COMPARISON_IDS = (
    "naive_mean_difference",
    "covariate_ols",
    "normalized_ipw_atte",
    "supplier_fe_ols",
)
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
NUMERIC_ADJUSTMENT_FIELDS = frozenset({"quantity", "value"})
VALUE_STATES = ("present", "missing", "not_applicable", "unknown", "redacted")
CATEGORICAL_ADJUSTMENT_VOCABULARIES = {
    "material_class": ["class-a", "class-b"],
    "complexity_class": ["standard", "complex"],
    "project_id": ["project-a", "project-b"],
    "project_phase": ["substructure", "fitout"],
    "urgency_class": ["normal", "urgent"],
    "geography_code": ["north", "south"],
    "contract_form": ["lump-sum", "remeasure"],
}
PROPENSITY_FAILURE_CODES = frozenset(
    {
        "ENGINE_FEATURE_CONTRACT_VIOLATION",
        "ENGINE_INTERNAL_ERROR",
        "ENGINE_NUISANCE_FIT_FAILED",
        "ENGINE_NUISANCE_PREDICTION_INVALID",
        "ENGINE_SPLIT_INFEASIBLE",
        "ENGINE_SPLIT_INTEGRITY_VIOLATION",
    }
)
PROPENSITY_ABSTENTION_CODES = frozenset({"OVERLAP_COHORT_INSUFFICIENT"})
ESTIMATOR_FAILURE_CODES = frozenset(
    {
        "ENGINE_ESTIMATOR_FIT_FAILED",
        "ENGINE_COMPARISON_FIT_FAILED",
        "ENGINE_FEATURE_CONTRACT_VIOLATION",
        "ENGINE_INPUT_INTEGRITY_MISMATCH",
        "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
        "ENGINE_INTERNAL_ERROR",
        "ENGINE_NUISANCE_FIT_FAILED",
        "ENGINE_NUISANCE_PREDICTION_INVALID",
        "ENGINE_REPRODUCIBILITY_VIOLATION",
        "ENGINE_RESULT_INVALID",
        "ENGINE_SPLIT_INFEASIBLE",
        "ENGINE_SPLIT_INTEGRITY_VIOLATION",
    }
)
NUMERIC_TOLERANCE_REGISTRY = {
    "schema_version": "causal-engine-numeric-tolerances.v1",
    "replay_absolute": 1e-10,
    "replay_relative": 1e-8,
    "processed_propensity_absolute": 1e-15,
    "external_prediction_absolute": 1e-12,
}
REPRODUCTION_PROJECTION_SCHEMA_VERSION = "analysis-run-reproduction-projection.v1"
REPRODUCTION_COMPARISON_SCHEMA_VERSION = "analysis-run-reproduction-comparison.v1"
_REPRODUCTION_ADMINISTRATIVE_KEYS = frozenset(
    {
        "accepted_at",
        "analysis_run_id",
        "audit_actor",
        "audit_event_id",
        "bundle_manifest_hash",
        "bundle_ref",
        "completed_at",
        "content_hash",
        "created_at",
        "delivery_attempt_id",
        "delivery_mode",
        "diagnostic_identity",
        "developer_diagnostic_id",
        "effect_result_hash",
        "effect_result_ref",
        "event_seq",
        "investigation_request_id",
        "occurrence_id",
        "received_at",
        "reference_validated",
        "reproduces_run_id",
        "retries_run_id",
        "result_identity_digest",
        "run_relationship",
        "started_at",
        "validated_at",
        "validation_attestation_id",
        "validation_attestation_ref",
        "robustness_grade_ref",
        "verification_report",
        "verification_state",
    }
)
_REPRODUCTION_OMIT = object()
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


def _reproduction_projection_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key in _REPRODUCTION_ADMINISTRATIVE_KEYS:
        return _REPRODUCTION_OMIT
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for child_key in sorted(value, key=lambda item: str(item).encode("utf-8")):
            text_key = str(child_key)
            child = _reproduction_projection_value(value[child_key], key=text_key)
            if child is not _REPRODUCTION_OMIT:
                projected[text_key] = child
        return projected
    if isinstance(value, (list, tuple)):
        return [
            _reproduction_projection_value(item)
            for item in value
        ]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("RUN_REPRODUCIBILITY_VIOLATION")
        return value
    return deepcopy(value)


def build_reproduction_projection(
    payloads: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the run-neutral scientific projection used by exact reproduction."""

    if not isinstance(payloads, Mapping):
        raise ValueError("RUN_REPRODUCIBILITY_VIOLATION")
    projections: dict[str, Any] = {}
    entries = [
        (str(key), value)
        for key, value in payloads.items()
        if str(key) not in {"dataset_version_id", "intended_role"}
    ]
    for role, raw_value in sorted(
        entries,
        key=lambda item: item[0].encode("utf-8"),
    ):
        if role in {"verification_report", "reproduction_comparison"}:
            continue
        value = _reproduction_projection_value(raw_value)
        if value is not _REPRODUCTION_OMIT:
            projections[role] = value
    role_digests = {
        role: scientific_sha256(value)
        for role, value in projections.items()
    }
    digest_payload = {
        "schema_version": REPRODUCTION_PROJECTION_SCHEMA_VERSION,
        "roles": list(projections),
        "projections": projections,
    }
    return {
        **digest_payload,
        "role_digests": role_digests,
        "projection_digest": scientific_sha256(digest_payload),
    }


def _compare_reproduction_values(
    expected: Any,
    observed: Any,
    *,
    path: str,
    mismatches: list[dict[str, Any]],
) -> None:
    if isinstance(expected, Mapping) and isinstance(observed, Mapping):
        expected_keys = {str(key) for key in expected}
        observed_keys = {str(key) for key in observed}
        for missing in sorted(expected_keys - observed_keys):
            mismatches.append({"path": f"{path}.{missing}", "reason": "missing"})
        for unexpected in sorted(observed_keys - expected_keys):
            mismatches.append({"path": f"{path}.{unexpected}", "reason": "unexpected"})
        for key in sorted(expected_keys & observed_keys):
            _compare_reproduction_values(
                expected[key],
                observed[key],
                path=f"{path}.{key}",
                mismatches=mismatches,
            )
        return
    if isinstance(expected, list) and isinstance(observed, list):
        if len(expected) != len(observed):
            mismatches.append(
                {
                    "path": path,
                    "reason": "length",
                    "expected": len(expected),
                    "observed": len(observed),
                }
            )
            return
        for index, (expected_item, observed_item) in enumerate(zip(expected, observed, strict=True)):
            _compare_reproduction_values(
                expected_item,
                observed_item,
                path=f"{path}[{index}]",
                mismatches=mismatches,
            )
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool) and isinstance(
        observed, (int, float)
    ) and not isinstance(observed, bool):
        absolute = abs(float(observed) - float(expected))
        allowed = NUMERIC_TOLERANCE_REGISTRY["replay_absolute"] + (
            NUMERIC_TOLERANCE_REGISTRY["replay_relative"] * abs(float(expected))
        )
        if absolute > allowed:
            mismatches.append(
                {
                    "path": path,
                    "reason": "out_of_tolerance",
                    "expected": float(expected),
                    "observed": float(observed),
                    "absolute_error": absolute,
                    "allowed_error": allowed,
                }
            )
        return
    if expected != observed:
        mismatches.append(
            {
                "path": path,
                "reason": "value",
                "expected": deepcopy(expected),
                "observed": deepcopy(observed),
            }
        )


def compare_reproduction_projections(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    expected_member_hashes: Mapping[str, str] | None = None,
    observed_member_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compare two run-neutral projections under the locked numeric tolerances."""

    if not isinstance(expected, Mapping) or not isinstance(observed, Mapping):
        raise ValueError("RUN_REPRODUCIBILITY_VIOLATION")
    if (
        expected.get("schema_version") != REPRODUCTION_PROJECTION_SCHEMA_VERSION
        or observed.get("schema_version") != REPRODUCTION_PROJECTION_SCHEMA_VERSION
    ):
        raise ValueError("RUN_REPRODUCIBILITY_VIOLATION")
    mismatches: list[dict[str, Any]] = []
    try:
        expected_recomputed = build_reproduction_projection(
            expected.get("projections")
        )
        observed_recomputed = build_reproduction_projection(
            observed.get("projections")
        )
    except (TypeError, ValueError):
        raise ValueError("RUN_REPRODUCIBILITY_VIOLATION") from None
    for label, supplied, recomputed in (
        ("expected", expected, expected_recomputed),
        ("observed", observed, observed_recomputed),
    ):
        if supplied.get("roles") != recomputed["roles"]:
            mismatches.append(
                {
                    "path": f"{label}.roles",
                    "reason": "identity",
                    "expected": deepcopy(recomputed["roles"]),
                    "observed": deepcopy(supplied.get("roles")),
                }
            )
        if supplied.get("role_digests") != recomputed["role_digests"]:
            mismatches.append(
                {
                    "path": f"{label}.role_digests",
                    "reason": "identity",
                    "expected": deepcopy(recomputed["role_digests"]),
                    "observed": deepcopy(supplied.get("role_digests")),
                }
            )
        if supplied.get("projection_digest") != recomputed["projection_digest"]:
            mismatches.append(
                {
                    "path": f"{label}.projection_digest",
                    "reason": "identity",
                    "expected": recomputed["projection_digest"],
                    "observed": supplied.get("projection_digest"),
                }
            )
    _compare_reproduction_values(
        expected.get("projections"),
        observed.get("projections"),
        path="projections",
        mismatches=mismatches,
    )
    expected_roles = expected.get("roles")
    observed_roles = observed.get("roles")
    if expected_roles != observed_roles:
        mismatches.append(
            {
                "path": "roles",
                "reason": "role_set",
                "expected": deepcopy(expected_roles),
                "observed": deepcopy(observed_roles),
            }
        )
    if expected_member_hashes is not None or observed_member_hashes is not None:
        expected_hashes = dict(expected_member_hashes or {})
        observed_hashes = dict(observed_member_hashes or {})
        if expected_hashes != observed_hashes:
            mismatches.append(
                {
                    "path": "member_hashes",
                    "reason": "value",
                    "expected": deepcopy(expected_hashes),
                    "observed": deepcopy(observed_hashes),
                }
            )
    comparison_class: dict[str, Any] = {
        "comparison_id": "run_neutral_scientific_projection",
        "status": "passed" if not mismatches else "failed",
        "expected_digest": expected.get("projection_digest"),
        "observed_digest": observed.get("projection_digest"),
        "tolerance": deepcopy(NUMERIC_TOLERANCE_REGISTRY),
    }
    if mismatches:
        comparison_class["mismatches"] = mismatches[:32]
    result: dict[str, Any] = {
        "schema_version": REPRODUCTION_COMPARISON_SCHEMA_VERSION,
        "status": "passed" if not mismatches else "failed",
        "failure_code": None if not mismatches else "RUN_REPRODUCIBILITY_VIOLATION",
        "declared_tolerances": deepcopy(NUMERIC_TOLERANCE_REGISTRY),
        "comparison_classes": [comparison_class],
        "expected_projection": deepcopy(dict(expected)),
        "observed_projection": deepcopy(dict(observed)),
    }
    if expected_member_hashes is not None or observed_member_hashes is not None:
        result["member_hashes"] = {
            "expected": deepcopy(dict(expected_member_hashes or {})),
            "observed": deepcopy(dict(observed_member_hashes or {})),
        }
    return result


class PropensityStageError(ValueError):
    """A closed, safe failure raised inside the propensity stage."""

    def __init__(self, code: str) -> None:
        self.code = code if code in PROPENSITY_FAILURE_CODES else "ENGINE_INTERNAL_ERROR"
        super().__init__(self.code)


class EstimatorStageError(ValueError):
    """A closed, safe failure raised inside the primary estimator stage."""

    def __init__(self, code: str) -> None:
        self.code = code if code in ESTIMATOR_FAILURE_CODES else "ENGINE_INTERNAL_ERROR"
        super().__init__(self.code)


class FreshAnalysisFinalizationError(ValueError):
    """A fresh engine result could not be sealed as verified evidence."""

    def __init__(self, code: str) -> None:
        self.code = code
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


def _propensity_learner_parameters() -> dict[str, Any]:
    return {
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


def _propensity_spec(adjustment_set: Mapping[str, Any]) -> dict[str, Any]:
    adjustment_ref = {
        "adjustment_set_id": adjustment_set.get("adjustment_set_id"),
        "adjustment_set_version": adjustment_set.get("adjustment_set_version"),
    }
    learner_parameters = _propensity_learner_parameters()
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
    row_ids = [row.get("order_line_id") for row in ordered_rows]
    if not all(isinstance(row_id, str) for row_id in row_ids):
        raise ValueError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    if len(set(row_ids)) != len(row_ids):
        raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
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
        if (
            not isinstance(row_mapping["order_line_id"], str)
            or not row_mapping["order_line_id"]
            or not isinstance(row_mapping["supplier_id"], str)
            or not row_mapping["supplier_id"]
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
    summary = normalised.get("cohort_stage_summaries", {}).get("S8_OUTCOME")
    if isinstance(summary, Mapping):
        if (
            "selected_count" in summary
            and summary.get("selected_count") != len(ordered_rows)
        ):
            raise ValueError("ENGINE_INPUT_INTEGRITY_MISMATCH")
        if (
            "selected_identity_hash" in summary
            and summary.get("selected_identity_hash") != identity_hash
        ):
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
    if state != "eligible":
        return {
            "state": "scientifically_unavailable",
            "subject_id": subject_id,
            "eligibility_codes": deepcopy(
                eligibility_subject.get("eligibility_codes", [])
                if isinstance(eligibility_subject, Mapping)
                else []
            ),
            "scientific_code": (
                eligibility_subject.get("reason_code")
                if isinstance(eligibility_subject, Mapping)
                else "COHORT_SUPPORT_INSUFFICIENT"
            ),
            "evidence_refs": sorted({str(ref) for ref in evidence_refs}),
        }
    profile = {
        "supplier_id": deepcopy(analytical.get("supplier_id")),
        "adjustment_inputs": deepcopy(analytical.get("adjustment_inputs", {})),
        "original_promise": deepcopy(analytical.get("original_promise")),
        "subject_exclusion_identity": subject_id,
        "decision_cutoff": deepcopy(causal_input.get("decision_cutoff")),
        "observation_cutoff": deepcopy(causal_input.get("observation_cutoff")),
        "target_milestone_kind": deepcopy(causal_input.get("target_milestone_kind")),
    }
    load_exposure = causal_input.get("supplier_load_exposure")
    if isinstance(load_exposure, Mapping):
        primary_exposure = load_exposure.get("primary")
        if isinstance(primary_exposure, Mapping):
            trigger_mode = investigation_request.get("trigger_mode")
            if isinstance(trigger_mode, str):
                profile[
                    "provisional_exposure_preview"
                    if trigger_mode == "proactive"
                    else "canonical_exposure"
                ] = deepcopy(dict(primary_exposure))
    return {
        "state": "eligible",
        "subject_id": subject_id,
        "profile": profile,
        "eligibility_codes": deepcopy(
            eligibility_subject.get("eligibility_codes", [])
            if isinstance(eligibility_subject, Mapping)
            else []
        ),
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
                **(
                    {"categories": deepcopy(CATEGORICAL_ADJUSTMENT_VOCABULARIES[name])}
                    if name in CATEGORICAL_ADJUSTMENT_VOCABULARIES
                    else {}
                ),
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
    subject_input = _subject_input(
        investigation_request,
        causal_input,
        eligibility,
        evidence_refs,
    )
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
        "evidence_refs": evidence_refs,
    }
    if subject_input is not None:
        suite["subject"] = subject_input
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
                    if component == "inner_calibration_split":
                        continue
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


def build_fresh_reproduction_payload(
    store: Any,
    workspace_id: str,
    request: Mapping[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """Admit a new process against one exact, currently verified source run."""

    if not isinstance(request, Mapping):
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
            "USE_THE_TYPED_FRESH_REPRODUCTION_REQUEST",
        )
    target_run_id = request.get("target_analysis_run_id")
    if not isinstance(target_run_id, str):
        raise AnalysisRunRequestError(
            "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            "SELECT_A_VERIFIED_ANALYSIS_RUN_AND_RETRY",
        )
    try:
        operation_id = "operation-" + target_run_id.removeprefix("analysis-run-")
        if analysis_run_id_for_operation(operation_id) != target_run_id:
            raise ValueError
    except ValueError:
        raise AnalysisRunRequestError(
            "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            "SELECT_A_VERIFIED_ANALYSIS_RUN_AND_RETRY",
            404,
        ) from None

    target_operation = store.get_operation(workspace_id, operation_id)
    target_request = store.get_operation_request(workspace_id, operation_id)
    if (
        target_operation is None
        or target_operation.state != "SUCCEEDED"
        or not isinstance(target_request, Mapping)
        or target_request.get("schema_version") != "analysis-run-admission.v1"
    ):
        raise AnalysisRunRequestError(
            "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            "SELECT_A_VERIFIED_ANALYSIS_RUN_AND_RETRY",
            404,
        )
    suite_request = target_request.get("suite_request")
    target_runtime = target_request.get("runtime_fingerprint")
    target_request_digest = target_request.get("scientific_request_digest")
    target_runtime_digest = target_request.get("runtime_fingerprint_digest")
    if (
        not isinstance(suite_request, Mapping)
        or not isinstance(target_runtime, Mapping)
        or not isinstance(target_request_digest, str)
        or not isinstance(target_runtime_digest, str)
    ):
        raise AnalysisRunRequestError(
            "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            "SELECT_A_VERIFIED_ANALYSIS_RUN_AND_RETRY",
            404,
        )

    from .references import read_verified_analysis_bundle

    try:
        manifest, payloads = read_verified_analysis_bundle(
            Path(settings.artifact_root),
            analysis_run_id=target_run_id,
            expected_build_id=str(settings.build_manifest_id),
            expected_runtime=target_runtime,
        )
    except (OSError, TypeError, ValueError):
        raise AnalysisRunRequestError(
            "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            "RESTORE_THE_VERIFIED_SOURCE_RUN_AND_RETRY",
            409,
        ) from None
    engine_payload = payloads.get("engine_result")
    if (
        manifest.get("scientific_request_digest") != target_request_digest
        or manifest.get("runtime_fingerprint_digest") != target_runtime_digest
        or not isinstance(engine_payload, Mapping)
        or engine_payload.get("status") not in {"estimated", "abstained"}
    ):
        raise AnalysisRunRequestError(
            "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            "RESTORE_THE_VERIFIED_SOURCE_RUN_AND_RETRY",
            409,
        )

    supplied_seed = request.get("root_seed", suite_request.get("root_seed"))
    if supplied_seed != suite_request.get("root_seed"):
        raise AnalysisRunRequestError(
            "ENGINE_INPUT_INTEGRITY_MISMATCH",
            "REPRODUCE_WITH_THE_SOURCE_ROOT_SEED",
        )
    admission = build_fresh_analysis_payload(
        store,
        workspace_id,
        {
            "suite_request": deepcopy(dict(suite_request)),
            "root_seed": supplied_seed,
            "scientific_request_digest": target_request_digest,
        },
        settings,
    )
    if (
        admission["scientific_request_digest"] != target_request_digest
        or admission["runtime_fingerprint_digest"] != target_runtime_digest
        or admission["runtime_fingerprint"] != dict(target_runtime)
    ):
        raise AnalysisRunRequestError(
            "ENGINE_RUNTIME_INCOMPATIBLE",
            "USE_THE_SEALED_ENGINE_RUNTIME_AND_RETRY",
            503,
        )
    admission["investigation_request_id"] = target_request.get(
        "investigation_request_id"
    )
    admission["run_relationship"] = "reproduction"
    admission["reproduces_run_id"] = target_run_id
    return admission


def _field_definition_map(adjustment_set: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    definitions = adjustment_set.get("field_definitions")
    if not isinstance(definitions, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for definition in definitions:
        if not isinstance(definition, Mapping):
            continue
        name = definition.get("name")
        if isinstance(name, str) and name:
            result[name] = definition
    return result


def _value_token(value: Mapping[str, Any]) -> str:
    state = value.get("state")
    if state != "present":
        if state not in VALUE_STATES:
            raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        return f"state:{state}"
    try:
        return f"value:{scientific_json(value.get('value'))}"
    except (TypeError, ValueError, OverflowError):
        raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION") from None


@dataclass(frozen=True, slots=True)
class _PropensityFeatureLayout:
    fields: tuple[str, ...]
    numeric_fields: frozenset[str]
    categorical_levels: dict[str, tuple[str, ...]]
    feature_names: tuple[str, ...]

    def transform(self, rows: Sequence[Mapping[str, Any]]) -> Any:
        import numpy as np

        matrix = np.zeros((len(rows), len(self.feature_names)), dtype=np.float64)
        for row_index, row in enumerate(rows):
            covariates = row.get("covariates")
            if not isinstance(covariates, Mapping):
                raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
            column = 0
            for field in self.fields:
                value = covariates.get(field)
                if not isinstance(value, Mapping):
                    raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
                state = value.get("state")
                if state not in VALUE_STATES:
                    raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
                if field in self.numeric_fields:
                    if state == "present":
                        raw_value = value.get("value")
                        if (
                            not isinstance(raw_value, (int, float))
                            or isinstance(raw_value, bool)
                            or not math.isfinite(float(raw_value))
                        ):
                            raise PropensityStageError(
                                "ENGINE_FEATURE_CONTRACT_VIOLATION"
                            )
                        matrix[row_index, column] = float(raw_value)
                    column += 1
                    token = f"state:{state}"
                    levels = self.categorical_levels[field]
                    if token not in levels:
                        raise PropensityStageError(
                            "ENGINE_FEATURE_CONTRACT_VIOLATION"
                        )
                    matrix[row_index, column + levels.index(token)] = 1.0
                    column += len(levels)
                    continue

                token = _value_token(value)
                levels = self.categorical_levels[field]
                if token not in levels:
                    raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
                matrix[row_index, column + levels.index(token)] = 1.0
                column += len(levels)
            if not np.isfinite(matrix[row_index]).all():
                raise PropensityStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
        return matrix


def _declared_categorical_values(definition: Mapping[str, Any]) -> list[Any] | None:
    for key in ("categories", "vocabulary", "ordered_vocabulary", "allowed_values"):
        values = definition.get(key)
        if isinstance(values, list):
            return deepcopy(values)
    return None


def _build_propensity_feature_layout(
    request: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    subject_rows: Sequence[Mapping[str, Any]],
) -> _PropensityFeatureLayout:
    adjustment_set = request.get("adjustment_set")
    if not isinstance(adjustment_set, Mapping):
        raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    fields = adjustment_set.get("fields")
    if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
        raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    field_names = tuple(str(field) for field in fields)
    definitions = _field_definition_map(adjustment_set)
    numeric_fields = frozenset(
        field
        for field in field_names
        if field in NUMERIC_ADJUSTMENT_FIELDS
        or definitions.get(field, {}).get("estimation_type") in {"numeric", "continuous"}
        or definitions.get(field, {}).get("logical_type") in {"numeric", "number"}
    )
    categorical_levels: dict[str, tuple[str, ...]] = {}
    feature_names: list[str] = []
    for field in field_names:
        if field in numeric_fields:
            levels = tuple(f"state:{state}" for state in VALUE_STATES)
            categorical_levels[field] = levels
            feature_names.append(f"{field}::value")
            feature_names.extend(f"{field}::{level}" for level in levels)
            continue

        definition = definitions.get(field, {})
        declared_values = _declared_categorical_values(definition)
        if declared_values is not None:
            ordered_levels: list[str] = [f"state:{state}" for state in VALUE_STATES]
            seen_levels = set(ordered_levels)
            for value in declared_values:
                try:
                    token = f"value:{scientific_json(value)}"
                except (TypeError, ValueError, OverflowError):
                    raise PropensityStageError(
                        "ENGINE_FEATURE_CONTRACT_VIOLATION"
                    ) from None
                if token not in seen_levels:
                    ordered_levels.append(token)
                    seen_levels.add(token)
        else:
            # A subject must never expand or otherwise alter the historical
            # feature layout. Legacy requests without a declared vocabulary
            # may derive a compatibility layout from S8 rows only.
            levels = {f"state:{state}" for state in VALUE_STATES}
            for row in rows:
                covariates = row.get("covariates")
                value = covariates.get(field) if isinstance(covariates, Mapping) else None
                if not isinstance(value, Mapping):
                    raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
                levels.add(_value_token(value))
            ordered_levels = sorted(levels, key=lambda item: item.encode("utf-8"))
        ordered_levels = tuple(ordered_levels)
        categorical_levels[field] = ordered_levels
        feature_names.extend(f"{field}::{level}" for level in ordered_levels)
    return _PropensityFeatureLayout(
        fields=field_names,
        numeric_fields=numeric_fields,
        categorical_levels=categorical_levels,
        feature_names=tuple(feature_names),
    )


def _stage_seed(
    request: Mapping[str, Any],
    *,
    variant_id: str,
    repeat_index: int,
    outer_fold_index: int | None,
    component: str,
) -> int:
    material = _seed_material(
        request,
        variant_id=variant_id,
        repeat_index=repeat_index,
        outer_fold_index=outer_fold_index,
        inner_fold_index=None,
        component=component,
    )
    return int.from_bytes(
        hashlib.sha256(scientific_json(material).encode("utf-8")).digest()[:4],
        "big",
    )


def _validate_split_partition(
    train_indices: Sequence[int],
    test_indices: Sequence[int],
    *,
    row_count: int,
    exposure: Any,
    groups: Any,
    require_both_train: bool,
    require_both_test: bool = False,
) -> tuple[Any, Any]:
    import numpy as np

    train = np.asarray(sorted(int(index) for index in train_indices), dtype=int)
    test = np.asarray(sorted(int(index) for index in test_indices), dtype=int)
    if (
        len(train) == 0
        or len(test) == 0
        or len(set(train.tolist()).intersection(test.tolist()))
        or sorted([*train.tolist(), *test.tolist()]) != list(range(row_count))
    ):
        raise PropensityStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
    if set(groups[train].tolist()).intersection(groups[test].tolist()):
        raise PropensityStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
    if require_both_train and len(set(exposure[train].tolist())) != 2:
        raise PropensityStageError("ENGINE_SPLIT_INFEASIBLE")
    if require_both_test and len(set(exposure[test].tolist())) != 2:
        raise PropensityStageError("ENGINE_SPLIT_INFEASIBLE")
    return train, test


def _outer_split_records(
    request: Mapping[str, Any],
    variant_id: str,
    rows: Sequence[Mapping[str, Any]],
    exposure: Any,
    groups: Any,
) -> list[tuple[int, Any, Any, list[dict[str, Any]]]]:
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold

    row_count = len(rows)
    splitter_input = np.zeros((row_count, 1), dtype=np.float64)
    records: list[tuple[int, Any, Any, list[dict[str, Any]]]] = []
    row_ids = [str(row["order_line_id"]) for row in rows]
    for repeat_index in range(2):
        outer_split_seed = _stage_seed(
            request,
            variant_id=variant_id,
            repeat_index=repeat_index,
            outer_fold_index=None,
            component="outer_split",
        )
        splitter = StratifiedGroupKFold(
            n_splits=5,
            shuffle=True,
            random_state=outer_split_seed,
        )
        splits = list(splitter.split(splitter_input, exposure, groups=groups))
        if len(splits) != 5:
            raise PropensityStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
        seen_test: list[int] = []
        for fold_index, (raw_train, raw_test) in enumerate(splits):
            train, test = _validate_split_partition(
                raw_train,
                raw_test,
                row_count=row_count,
                exposure=exposure,
                groups=groups,
                require_both_train=True,
            )
            seen_test.extend(test.tolist())
            calibration_records: list[dict[str, Any]] = []
            local_exposure = exposure[train]
            local_groups = groups[train]
            local_input = np.zeros((len(train), 1), dtype=np.float64)
            calibration_splitter = StratifiedGroupKFold(
                n_splits=3,
                shuffle=True,
                random_state=_stage_seed(
                    request,
                    variant_id=variant_id,
                    repeat_index=repeat_index,
                    outer_fold_index=fold_index,
                    component="inner_calibration_split",
                ),
            )
            calibration_splits = list(
                calibration_splitter.split(
                    local_input,
                    local_exposure,
                    groups=local_groups,
                )
            )
            if len(calibration_splits) != 3:
                raise PropensityStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
            inner_calibration_split_seed = _stage_seed(
                request,
                variant_id=variant_id,
                repeat_index=repeat_index,
                outer_fold_index=fold_index,
                component="inner_calibration_split",
            )
            propensity_learner_seed = _stage_seed(
                request,
                variant_id=variant_id,
                repeat_index=repeat_index,
                outer_fold_index=fold_index,
                component="propensity_learner",
            )
            for calibration_index, (calibration_train, calibration_test) in enumerate(
                calibration_splits
            ):
                calibration_train, calibration_test = _validate_split_partition(
                    calibration_train,
                    calibration_test,
                    row_count=len(train),
                    exposure=local_exposure,
                    groups=local_groups,
                    require_both_train=True,
                    require_both_test=True,
                )
                calibration_records.append(
                    {
                        "fold_index": calibration_index,
                        "train_ids": [row_ids[int(train[index])] for index in calibration_train],
                        "test_ids": [row_ids[int(train[index])] for index in calibration_test],
                        "train_supplier_ids": sorted(
                            str(groups[int(train[index])]) for index in calibration_train
                        ),
                        "test_supplier_ids": sorted(
                            str(groups[int(train[index])]) for index in calibration_test
                        ),
                    }
                )
            records.append(
                (
                    repeat_index,
                    train,
                    test,
                    [
                        {
                            "fold_index": fold_index,
                            "outer_split_seed": outer_split_seed,
                            "inner_calibration_split_seed": inner_calibration_split_seed,
                            "propensity_learner_seed": propensity_learner_seed,
                            "train_ids": [row_ids[int(index)] for index in train],
                            "test_ids": [row_ids[int(index)] for index in test],
                            "train_supplier_ids": sorted(str(value) for value in groups[train]),
                            "test_supplier_ids": sorted(str(value) for value in groups[test]),
                            "calibration_folds": calibration_records,
                        }
                    ],
                )
            )
        if sorted(seen_test) != list(range(row_count)):
            raise PropensityStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
    return records


def _propensity_classifier(seed: int) -> Any:
    from sklearn.ensemble import HistGradientBoostingClassifier

    parameters = _propensity_learner_parameters()
    parameters.update(
        {
            "loss": "log_loss",
            "class_weight": None,
            "random_state": seed,
        }
    )
    return HistGradientBoostingClassifier(**parameters)


def _safe_stage_error(error: BaseException) -> str:
    code = getattr(error, "code", None)
    if isinstance(code, str) and code in PROPENSITY_FAILURE_CODES:
        return code
    if isinstance(error, ValueError) and str(error) in PROPENSITY_FAILURE_CODES:
        return str(error)
    if isinstance(error, (TypeError, ValueError, RuntimeError)):
        return "ENGINE_NUISANCE_FIT_FAILED"
    return "ENGINE_INTERNAL_ERROR"


def _variant_summary_count(variant: Mapping[str, Any]) -> int:
    summaries = variant.get("cohort_stage_summaries")
    if not isinstance(summaries, Mapping):
        return 0
    summary = summaries.get("S8_OUTCOME")
    if not isinstance(summary, Mapping):
        return 0
    for key in ("selected_count", "count", "denominator_count"):
        value = summary.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return 0


def _safe_variant_detail(
    variant_id: str,
    source_variant: Mapping[str, Any],
    materialized_variant: Mapping[str, Any],
) -> dict[str, Any]:
    state = materialized_variant.get("state")
    if state == "scientifically_unavailable":
        return {
            "variant_id": variant_id,
            "s8_status": "scientifically_unavailable",
            "s8_count": _variant_summary_count(source_variant),
            "propensity_status": "not_run",
            "overlap_status": "not_run",
            "s9_status": "not_run",
            "s9_count": 0,
            "reason_code": materialized_variant.get("reason_code"),
            "component_failures": [],
        }
    if state == "failed":
        return {
            "variant_id": variant_id,
            "s8_status": "released",
            "s8_count": materialized_variant.get("s8_count", 0),
            "propensity_status": "failed",
            "overlap_status": "not_run",
            "s9_status": "not_run",
            "s9_count": 0,
            "reason_code": materialized_variant.get("reason_code"),
            "component_failures": deepcopy(
                materialized_variant.get("component_failures", [])
            ),
        }
    overlap = materialized_variant.get("overlap")
    s9 = materialized_variant.get("s9")
    if not isinstance(overlap, Mapping) or not isinstance(s9, Mapping):
        return {
            "variant_id": variant_id,
            "s8_status": "released",
            "s8_count": materialized_variant.get("s8_count", 0),
            "propensity_status": "failed",
            "overlap_status": "failed",
            "s9_status": "not_run",
            "s9_count": 0,
            "reason_code": "ENGINE_INTERNAL_ERROR",
            "component_failures": [
                {
                    "component": "s9_materialization",
                    "variant_id": variant_id,
                    "code": "ENGINE_INTERNAL_ERROR",
                }
            ],
        }
    return {
        "variant_id": variant_id,
        "s8_status": "released",
        "s8_count": materialized_variant.get("s8_count", 0),
        "propensity_status": "complete",
        "propensity_count": materialized_variant.get("propensity_count", 0),
        "propensity_repeat_count": 2,
        "overlap_status": overlap.get("state"),
        "retained_count": s9.get("retained_count", 0),
        "trimmed_count": s9.get("trimmed_count", 0),
        "overall_trim_rate": s9.get("overall_trim_rate"),
        "arm_trim_rates": deepcopy(s9.get("arm_trim_rates", {})),
        "post_trim_support_status": (
            overlap.get("post_trim_support", {}).get("state")
            if isinstance(overlap.get("post_trim_support"), Mapping)
            else None
        ),
        "s9_status": s9.get("state"),
        "s9_count": s9.get("retained_count", 0),
        "reason_code": materialized_variant.get("reason_code"),
        "component_failures": [],
    }


def _safe_detail(
    request: Mapping[str, Any],
    source_variants: Mapping[str, Mapping[str, Any]],
    variants: Mapping[str, Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    details = [
        _safe_variant_detail(variant_id, source_variants[variant_id], variants[variant_id])
        for variant_id in VARIANT_ORDER
    ]
    return {
        "schema_version": "analysis-run-safe-detail.v1",
        "execution_state": "failed" if failures else "complete",
        "last_completed_stage": (
            "S9_OVERLAP"
            if any(item.get("propensity_status") == "complete" for item in details)
            else "S8_OUTCOME"
        ),
        "variants": details,
        "component_failures": deepcopy(list(failures)),
        "estimator_executed": False,
        "scope": "propensity_and_overlap_only",
    }


def _materialize_propensity_variant(
    request: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> dict[str, Any]:
    import numpy as np
    from threadpoolctl import threadpool_limits

    variant_id = str(variant["variant_id"])
    rows = variant.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    subject = request.get("subject")
    subject_rows: list[dict[str, Any]] = []
    if isinstance(subject, Mapping) and subject.get("state") == "eligible":
        profile = subject.get("profile")
        if not isinstance(profile, Mapping) or not isinstance(
            profile.get("adjustment_inputs"), Mapping
        ):
            raise PropensityStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        subject_rows.append(
            {
                "order_line_id": str(subject.get("subject_id", "subject")),
                "covariates": deepcopy(profile["adjustment_inputs"]),
            }
        )
    feature_layout = _build_propensity_feature_layout(request, rows, subject_rows)
    matrix = feature_layout.transform(rows)
    subject_matrix = feature_layout.transform(subject_rows) if subject_rows else None
    exposure = np.asarray(
        [1 if bool(row["high_load_exposure"]) else 0 for row in rows], dtype=np.int8
    )
    groups = np.asarray([str(row["supplier_id"]) for row in rows], dtype=object)
    if len(set(exposure.tolist())) != 2:
        raise PropensityStageError("ENGINE_SPLIT_INFEASIBLE")
    split_records = _outer_split_records(request, variant_id, rows, exposure, groups)
    raw_predictions = np.full((2, len(rows)), np.nan, dtype=np.float64)
    subject_predictions: list[float] = []
    fold_assignments: list[dict[str, Any]] = []
    row_ids = [str(row["order_line_id"]) for row in rows]
    with threadpool_limits(limits=1):
        for repeat_index, train, test, records in split_records:
            fold_record = records[0]
            fold_index = int(fold_record["fold_index"])
            calibration_splits = [
                (
                    np.asarray(
                        [
                            next(
                                index
                                for index, global_index in enumerate(train)
                                if row_ids[int(global_index)] == row_id
                            )
                            for row_id in calibration["train_ids"]
                        ],
                        dtype=int,
                    ),
                    np.asarray(
                        [
                            next(
                                index
                                for index, global_index in enumerate(train)
                                if row_ids[int(global_index)] == row_id
                            )
                            for row_id in calibration["test_ids"]
                        ],
                        dtype=int,
                    ),
                )
                for calibration in fold_record["calibration_folds"]
            ]
            model = _propensity_classifier(
                _stage_seed(
                    request,
                    variant_id=variant_id,
                    repeat_index=repeat_index,
                    outer_fold_index=fold_index,
                    component="propensity_learner",
                )
            )
            try:
                from sklearn.calibration import CalibratedClassifierCV

                calibrated = CalibratedClassifierCV(
                    estimator=model,
                    method="sigmoid",
                    cv=calibration_splits,
                    n_jobs=1,
                    ensemble=True,
                )
                calibrated.fit(matrix[train], exposure[train])
                predictions = calibrated.predict_proba(matrix[test])[:, 1]
                if subject_matrix is not None:
                    subject_predictions.append(
                        float(calibrated.predict_proba(subject_matrix)[:, 1][0])
                    )
            except PropensityStageError:
                raise
            except Exception as error:
                raise PropensityStageError(_safe_stage_error(error)) from None
            predictions = np.asarray(predictions, dtype=np.float64)
            if (
                len(predictions) != len(test)
                or not np.isfinite(predictions).all()
                or np.any(predictions < 0.0)
                or np.any(predictions > 1.0)
            ):
                raise PropensityStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
            raw_predictions[repeat_index, test] = predictions
            fold_assignments.append(
                {
                    "repeat_index": repeat_index,
                    **deepcopy(fold_record),
                }
            )
    if not np.isfinite(raw_predictions).all():
        raise PropensityStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    means = raw_predictions.mean(axis=0)
    if (
        not np.isfinite(means).all()
        or np.any(means < 0.0)
        or np.any(means > 1.0)
    ):
        raise PropensityStageError("ENGINE_NUISANCE_PREDICTION_INVALID")

    from .eligibility import evaluate_propensity_overlap

    overlap_rows = [
        {
            "id": row_ids[index],
            "supplier_id": str(rows[index]["supplier_id"]),
            "exposure": bool(exposure[index]),
            "propensity": float(means[index]),
        }
        for index in range(len(rows))
    ]
    overlap = evaluate_propensity_overlap(overlap_rows)
    retained_ids = [str(value) for value in overlap.get("retained_ids", [])]
    retained_id_set = set(retained_ids)
    propensity_predictions = [
        {
            "row_id": row_ids[index],
            "repeat_predictions": [
                float(raw_predictions[0, index]),
                float(raw_predictions[1, index]),
            ],
            "mean": float(means[index]),
            "external_prediction_slots": [float(means[index]), float(means[index])],
            "retained_in_s9": row_ids[index] in retained_id_set,
        }
        for index in range(len(rows))
    ]
    s9_state = "supported" if overlap.get("state") == "supported" else "unsupported"
    subject_result: dict[str, Any]
    if subject_matrix is None:
        subject_result = {
            "state": "scientifically_unavailable",
            "reason_code": (
                subject.get("scientific_code", "SUBJECT_PROPENSITY_UNAVAILABLE")
                if isinstance(subject, Mapping)
                else "SUBJECT_PROPENSITY_UNAVAILABLE"
            ),
        }
    else:
        if len(subject_predictions) != 10 or not all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for value in subject_predictions
        ):
            raise PropensityStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
        subject_result = {
            "state": "present",
            "repeat_fold_predictions": subject_predictions,
            "value": sum(subject_predictions) / len(subject_predictions),
            "aggregation": "arithmetic_mean_of_ten_primary_outer_fold_models",
        }
    return {
        "variant_id": variant_id,
        "state": "materialized",
        "reason_code": None if s9_state == "supported" else overlap.get("reason_code"),
        "s8_count": len(rows),
        "s8_identity_hash": variant.get("s8_identity_hash"),
        "s8_content_hash": variant.get("s8_content_hash"),
        "feature_schema": {
            "schema_version": "analysis-run-feature-matrix.v1",
            "ordered_feature_names": list(feature_layout.feature_names),
            "feature_schema_digest": scientific_sha256(
                list(feature_layout.feature_names)
            ),
            "row_identity_hash": scientific_sha256(row_ids),
            "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        },
        "folds": {
            "outer_repeats": 2,
            "outer_folds_per_repeat": 5,
            "inner_calibration_folds": 3,
            "group_field": "supplier_id",
            "stratify_field": "high_load_exposure",
            "assignments": fold_assignments,
        },
        "fold_assignments": deepcopy(fold_assignments),
        "propensity": {
            "state": "complete",
            "repeat_count": 2,
            "outer_fold_count": 10,
            "aggregation": "arithmetic_mean_of_repeat_oof_probabilities",
            "authoritative_identity_hash": scientific_sha256(
                [item["mean"] for item in propensity_predictions]
            ),
        },
        "propensity_predictions": propensity_predictions,
        "propensity_count": len(propensity_predictions),
        "external_predictions": {
            "schema_version": "doubleml-external-predictions.v1",
            "row_ids": retained_ids,
            "repeat_columns": [0, 1],
            "ml_m": [
                [item["mean"], item["mean"]]
                for item in propensity_predictions
                if item["row_id"] in retained_id_set
            ],
            "source": "authoritative_mean_calibrated_oof_propensity",
            "refit_inside_doubleml": False,
        },
        "subject_propensity": subject_result,
        "overlap": deepcopy(overlap),
        "s9": {
            "state": s9_state,
            "retained_ids": retained_ids,
            "retained_count": len(retained_ids),
            "identity_hash": overlap.get("retained_identity_hash"),
            "trimmed_ids": [str(value) for value in overlap.get("trimmed_ids", [])],
            "trimmed_count": int(overlap.get("trimmed_count", 0)),
            "overall_trim_rate": overlap.get("overall_trim_rate"),
            "arm_trim_rates": deepcopy(overlap.get("arm_trim_rates", {})),
            "support_interval": deepcopy(overlap.get("support_interval", {})),
        },
    }


def materialize_propensity_and_s9(
    value: Mapping[str, Any] | ValidatedSuiteRequest,
) -> dict[str, Any]:
    """Fit the authoritative propensity stage and materialize S9 exactly once.

    This is the public engine seam for Core 16. It never fits an effect model
    or calls DoubleML; its external prediction slots are the handoff for the
    subsequent estimator ticket.
    """

    validated = (
        value
        if isinstance(value, ValidatedSuiteRequest)
        else validate_suite_request(value)
    )
    request = validated.request
    source_variants = {
        variant_id: variant
        for variant_id, variant in zip(
            VARIANT_ORDER,
            request["variant_inputs"],
            strict=True,
        )
    }
    variants: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    has_released_variant = False
    for variant_id in VARIANT_ORDER:
        source_variant = source_variants[variant_id]
        if source_variant["upstream_status"] == "scientifically_unavailable":
            variants[variant_id] = {
                "variant_id": variant_id,
                "state": "scientifically_unavailable",
                "reason_code": source_variant.get("scientific_code"),
                "s8_count": 0,
                "component_failures": [],
            }
            continue
        has_released_variant = True
        try:
            variants[variant_id] = _materialize_propensity_variant(
                request,
                source_variant,
            )
        except PropensityStageError as error:
            failure = {
                "component": "propensity_ensemble",
                "variant_id": variant_id,
                "code": error.code,
            }
            failures.append(failure)
            variants[variant_id] = {
                "variant_id": variant_id,
                "state": "failed",
                "reason_code": error.code,
                "s8_count": len(source_variant.get("rows", [])),
                "component_failures": [failure],
            }
        except Exception:
            failure = {
                "component": "propensity_ensemble",
                "variant_id": variant_id,
                "code": "ENGINE_INTERNAL_ERROR",
            }
            failures.append(failure)
            variants[variant_id] = {
                "variant_id": variant_id,
                "state": "failed",
                "reason_code": "ENGINE_INTERNAL_ERROR",
                "s8_count": len(source_variant.get("rows", [])),
                "component_failures": [failure],
            }
    status = "failed" if failures else "abstained"
    reason_code = (
        failures[0]["code"]
        if failures
        else next(
            (
                variant.get("reason_code")
                for variant in variants.values()
                if variant.get("reason_code") in PROPENSITY_ABSTENTION_CODES
            ),
            "ENGINE_EXECUTION_DEFERRED",
        )
    )
    safe_detail = _safe_detail(request, source_variants, variants, failures)
    return {
        "schema_version": PROPENSITY_RESULT_SCHEMA_VERSION,
        "scientific_request_digest": validated.scientific_request_digest,
        "status": status,
        "scientific_outcome": "failed" if status == "failed" else "abstained",
        "reason_code": reason_code,
        "estimator_executed": False,
        "scope": "propensity_and_overlap_only",
        "has_released_variant": has_released_variant,
        "variants": variants,
        "component_failures": failures,
        "safe_detail": safe_detail,
    }


def _outcome_regressor(seed: int) -> Any:
    from sklearn.ensemble import HistGradientBoostingRegressor

    parameters = _propensity_learner_parameters()
    parameters.update(
        {
            "loss": "squared_error",
            "quantile": None,
            "random_state": seed,
        }
    )
    return HistGradientBoostingRegressor(**parameters)


def _outcome_classifier(seed: int) -> Any:
    from sklearn.ensemble import HistGradientBoostingClassifier

    parameters = _propensity_learner_parameters()
    parameters.update(
        {
            "loss": "log_loss",
            "class_weight": None,
            "random_state": seed,
        }
    )
    return HistGradientBoostingClassifier(**parameters)


def _variant_rows_and_layout(
    request: Mapping[str, Any],
    propensity_stage: Mapping[str, Any],
    variant_id: str,
) -> tuple[list[Mapping[str, Any]], Any, list[str]]:
    variants = propensity_stage.get("variants")
    if not isinstance(variants, Mapping):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    variant_stage = variants.get(variant_id)
    if not isinstance(variant_stage, Mapping):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    source_variant = next(
        (
            variant
            for variant in request.get("variant_inputs", [])
            if isinstance(variant, Mapping) and variant.get("variant_id") == variant_id
        ),
        None,
    )
    if not isinstance(source_variant, Mapping):
        raise EstimatorStageError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    source_rows = source_variant.get("rows")
    s9 = variant_stage.get("s9")
    if not isinstance(source_rows, list) or not isinstance(s9, Mapping):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    retained_ids = s9.get("retained_ids")
    if not isinstance(retained_ids, list) or not all(
        isinstance(row_id, str) for row_id in retained_ids
    ):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    if len(set(retained_ids)) != len(retained_ids) or s9.get(
        "identity_hash"
    ) != scientific_sha256(retained_ids):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    rows_by_id = {
        str(row["order_line_id"]): row
        for row in source_rows
        if isinstance(row, Mapping) and isinstance(row.get("order_line_id"), str)
    }
    if len(rows_by_id) != len(source_rows) or any(
        row_id not in rows_by_id for row_id in retained_ids
    ):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    retained_set = set(retained_ids)
    canonical_ids = [
        str(row["order_line_id"])
        for row in source_rows
        if isinstance(row, Mapping) and row.get("order_line_id") in retained_set
    ]
    if canonical_ids != retained_ids:
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    rows = [rows_by_id[row_id] for row_id in retained_ids]
    try:
        layout = _build_propensity_feature_layout(request, source_rows, [])
        matrix = layout.transform(rows)
    except PropensityStageError as error:
        raise EstimatorStageError(error.code) from None
    feature_schema = variant_stage.get("feature_schema")
    feature_digest = scientific_sha256(list(layout.feature_names))
    if not isinstance(feature_schema, Mapping) or feature_schema.get(
        "feature_schema_digest"
    ) != feature_digest:
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    if list(feature_schema.get("ordered_feature_names", [])) != list(
        layout.feature_names
    ) or feature_schema.get("shape") != [len(source_rows), matrix.shape[1]]:
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    if feature_schema.get("row_identity_hash") != scientific_sha256(
        [str(row["order_line_id"]) for row in source_rows]
    ):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    if not matrix.size or not matrix.shape[1]:
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    return rows, layout, retained_ids


def _variant_s9_splits(
    variant_stage: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    retained_ids: Sequence[str],
) -> tuple[list[list[tuple[Any, Any]]], list[list[tuple[list[Any], list[Any]]]], list[dict[str, Any]]]:
    import numpy as np

    assignments = variant_stage.get("fold_assignments")
    if not isinstance(assignments, list):
        raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
    row_index = {row_id: index for index, row_id in enumerate(retained_ids)}
    s9_record = variant_stage.get("s9")
    trimmed_ids = s9_record.get("trimmed_ids") if isinstance(s9_record, Mapping) else None
    if not isinstance(trimmed_ids, list) or not all(
        isinstance(row_id, str) for row_id in trimmed_ids
    ):
        raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
    if len(set(trimmed_ids)) != len(trimmed_ids) or set(retained_ids).intersection(
        trimmed_ids
    ):
        raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
    source_ids = set(retained_ids) | set(trimmed_ids)
    exposure = np.asarray(
        [bool(row["high_load_exposure"]) for row in rows],
        dtype=np.int8,
    )
    groups = np.asarray([str(row["supplier_id"]) for row in rows], dtype=object)
    grouped: dict[int, dict[int, Mapping[str, Any]]] = {0: {}, 1: {}}
    for assignment in assignments:
        if not isinstance(assignment, Mapping):
            raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
        repeat_index = assignment.get("repeat_index")
        fold_index = assignment.get("fold_index")
        if (
            not isinstance(repeat_index, int)
            or isinstance(repeat_index, bool)
            or repeat_index not in grouped
            or not isinstance(fold_index, int)
            or isinstance(fold_index, bool)
            or not 0 <= fold_index < 5
            or fold_index in grouped[repeat_index]
        ):
            raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
        grouped[repeat_index][fold_index] = assignment

    all_smpls: list[list[tuple[Any, Any]]] = []
    all_smpls_cluster: list[list[tuple[list[Any], list[Any]]]] = []
    retained_fold_records: list[dict[str, Any]] = []
    for repeat_index in range(2):
        if set(grouped[repeat_index]) != set(range(5)):
            raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
        repeat_smpls: list[tuple[Any, Any]] = []
        repeat_cluster_smpls: list[tuple[list[Any], list[Any]]] = []
        test_seen: list[int] = []
        for fold_index in range(5):
            assignment = grouped[repeat_index][fold_index]
            train_ids = assignment.get("train_ids")
            test_ids = assignment.get("test_ids")
            if not isinstance(train_ids, list) or not isinstance(test_ids, list):
                raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
            if (
                len(set(train_ids)) != len(train_ids)
                or len(set(test_ids)) != len(test_ids)
                or not all(
                    isinstance(row_id, str) for row_id in [*train_ids, *test_ids]
                )
                or set(train_ids).intersection(test_ids)
                or set([*train_ids, *test_ids]) != source_ids
            ):
                raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
            train = [row_index[row_id] for row_id in train_ids if row_id in row_index]
            test = [row_index[row_id] for row_id in test_ids if row_id in row_index]
            try:
                train_array, test_array = _validate_split_partition(
                    train,
                    test,
                    row_count=len(rows),
                    exposure=exposure,
                    groups=groups,
                    require_both_train=True,
                )
            except PropensityStageError as error:
                raise EstimatorStageError(error.code) from None
            train_clusters = sorted({str(groups[index]) for index in train_array})
            test_clusters = sorted({str(groups[index]) for index in test_array})
            if not train_clusters or not test_clusters:
                raise EstimatorStageError("ENGINE_SPLIT_INFEASIBLE")
            repeat_smpls.append((train_array, test_array))
            repeat_cluster_smpls.append(
                (
                    [np.asarray(train_clusters, dtype=object)],
                    [np.asarray(test_clusters, dtype=object)],
                )
            )
            test_seen.extend(test_array.tolist())
            retained_fold_records.append(
                {
                    "repeat_index": repeat_index,
                    "fold_index": fold_index,
                    "train_ids": [retained_ids[index] for index in train_array],
                    "test_ids": [retained_ids[index] for index in test_array],
                    "train_supplier_ids": train_clusters,
                    "test_supplier_ids": test_clusters,
                }
            )
        if sorted(test_seen) != list(range(len(rows))):
            raise EstimatorStageError("ENGINE_SPLIT_INTEGRITY_VIOLATION")
        all_smpls.append(repeat_smpls)
        all_smpls_cluster.append(repeat_cluster_smpls)
    return all_smpls, all_smpls_cluster, retained_fold_records


def _fit_variant_outcome_nuisances(
    request: Mapping[str, Any],
    variant_id: str,
    rows: Sequence[Mapping[str, Any]],
    layout: Any,
    retained_ids: Sequence[str],
    variant_stage: Mapping[str, Any],
    *,
    outcome_field: str = "supplier_milestone_slippage_days",
    outcome_kind: str = "continuous",
) -> dict[str, Any]:
    import numpy as np
    from threadpoolctl import threadpool_limits

    try:
        matrix = layout.transform(rows)
    except PropensityStageError as error:
        raise EstimatorStageError(error.code) from None
    if outcome_kind not in {"continuous", "binary"}:
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    if outcome_kind == "binary":
        if not all(isinstance(row.get(outcome_field), bool) for row in rows):
            raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        outcome = np.asarray(
            [1.0 if bool(row[outcome_field]) else 0.0 for row in rows],
            dtype=np.float64,
        )
    else:
        outcome = np.asarray(
            [float(row[outcome_field]) for row in rows],
            dtype=np.float64,
        )
    exposure = np.asarray(
        [1 if bool(row["high_load_exposure"]) else 0 for row in rows],
        dtype=np.int8,
    )
    groups = np.asarray([str(row["supplier_id"]) for row in rows], dtype=object)
    if not np.isfinite(matrix).all() or not np.isfinite(outcome).all():
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    if len(set(exposure.tolist())) != 2:
        raise EstimatorStageError("ENGINE_SPLIT_INFEASIBLE")
    try:
        all_smpls, all_smpls_cluster, fold_records = _variant_s9_splits(
            variant_stage,
            rows,
            retained_ids,
        )
    except EstimatorStageError:
        raise

    propensity_predictions = variant_stage.get("propensity_predictions")
    if not isinstance(propensity_predictions, list):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    trimmed_ids = variant_stage.get("s9", {}).get("trimmed_ids")
    if not isinstance(trimmed_ids, list) or not all(
        isinstance(row_id, str) for row_id in trimmed_ids
    ):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    if len(set(trimmed_ids)) != len(trimmed_ids) or set(retained_ids).intersection(
        trimmed_ids
    ):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    source_ids = set(retained_ids) | set(trimmed_ids)
    prediction_ids = [
        item.get("row_id")
        for item in propensity_predictions
        if isinstance(item, Mapping)
    ]
    if (
        len(prediction_ids) != len(propensity_predictions)
        or not all(isinstance(row_id, str) for row_id in prediction_ids)
        or len(set(prediction_ids)) != len(prediction_ids)
        or set(prediction_ids) != source_ids
    ):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    for item in propensity_predictions:
        repeat_predictions = item.get("repeat_predictions")
        slots = item.get("external_prediction_slots")
        mean = item.get("mean")
        if (
            not isinstance(repeat_predictions, list)
            or len(repeat_predictions) != 2
            or not isinstance(slots, list)
            or len(slots) != 2
            or not isinstance(mean, (int, float))
            or isinstance(mean, bool)
            or not math.isfinite(float(mean))
            or not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and 0.0 <= float(value) <= 1.0
                for value in [*repeat_predictions, *slots]
            )
            or abs(
                float(mean)
                - (float(repeat_predictions[0]) + float(repeat_predictions[1])) / 2.0
            )
            > NUMERIC_TOLERANCE_REGISTRY["processed_propensity_absolute"]
            or any(
                abs(float(value) - float(mean))
                > NUMERIC_TOLERANCE_REGISTRY["processed_propensity_absolute"]
                for value in slots
            )
        ):
            raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    propensity_by_id = {
        item["row_id"]: item for item in propensity_predictions
    }
    try:
        external_propensity = np.asarray(
            [
                [
                    float(propensity_by_id[row_id]["mean"]),
                    float(propensity_by_id[row_id]["mean"]),
                ]
                for row_id in retained_ids
            ],
            dtype=np.float64,
        )
    except (KeyError, TypeError, ValueError):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID") from None
    if (
        external_propensity.shape != (len(rows), 2)
        or not np.isfinite(external_propensity).all()
        or np.any(external_propensity < 0.10)
        or np.any(external_propensity > 0.90)
    ):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")

    g0 = np.full((len(rows), 2), np.nan, dtype=np.float64)
    g1 = np.full((len(rows), 2), np.nan, dtype=np.float64)
    learner_factory = (
        _outcome_classifier if outcome_kind == "binary" else _outcome_regressor
    )
    unexposed_component = (
        "binary_outcome_learner_unexposed"
        if outcome_kind == "binary"
        else "outcome_learner_unexposed"
    )
    exposed_component = (
        "binary_outcome_learner_exposed"
        if outcome_kind == "binary"
        else "outcome_learner_exposed"
    )
    with threadpool_limits(limits=1):
        for repeat_index, repeat_smpls in enumerate(all_smpls):
            for fold_index, (train, test) in enumerate(repeat_smpls):
                train_unexposed = train[exposure[train] == 0]
                train_exposed = train[exposure[train] == 1]
                if len(train_unexposed) == 0 or len(train_exposed) == 0:
                    raise EstimatorStageError("ENGINE_SPLIT_INFEASIBLE")
                try:
                    unexposed_model = learner_factory(
                        _stage_seed(
                            request,
                            variant_id=variant_id,
                            repeat_index=repeat_index,
                            outer_fold_index=fold_index,
                            component=unexposed_component,
                        )
                    )
                    exposed_model = learner_factory(
                        _stage_seed(
                            request,
                            variant_id=variant_id,
                            repeat_index=repeat_index,
                            outer_fold_index=fold_index,
                            component=exposed_component,
                        )
                    )
                    unexposed_model.fit(matrix[train_unexposed], outcome[train_unexposed])
                    exposed_model.fit(matrix[train_exposed], outcome[train_exposed])
                    if outcome_kind == "binary":
                        g0[test, repeat_index] = unexposed_model.predict_proba(
                            matrix[test]
                        )[:, 1]
                        g1[test, repeat_index] = exposed_model.predict_proba(
                            matrix[test]
                        )[:, 1]
                    else:
                        g0[test, repeat_index] = unexposed_model.predict(matrix[test])
                        g1[test, repeat_index] = exposed_model.predict(matrix[test])
                except EstimatorStageError:
                    raise
                except Exception:
                    raise EstimatorStageError("ENGINE_NUISANCE_FIT_FAILED") from None
    if (
        not np.isfinite(g0).all()
        or not np.isfinite(g1).all()
        or external_propensity.shape != (len(rows), 2)
    ):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    return {
        "matrix": matrix,
        "rows": deepcopy(list(rows)),
        "outcome": outcome,
        "outcome_field": outcome_field,
        "outcome_kind": outcome_kind,
        "exposure": exposure,
        "groups": groups,
        "cohort_identity_hash": variant_stage["s9"].get("identity_hash"),
        "retained_ids": list(retained_ids),
        "feature_names": list(layout.feature_names),
        "feature_schema_digest": scientific_sha256(list(layout.feature_names)),
        "all_smpls": all_smpls,
        "all_smpls_cluster": all_smpls_cluster,
        "fold_records": fold_records,
        "g0": g0,
        "g1": g1,
        "ml_m": external_propensity,
    }


def _fit_variant_irm(
    request: Mapping[str, Any],
    variant_id: str,
    nuisances: Mapping[str, Any],
    *,
    score: str,
    outcome_field: str = "supplier_milestone_slippage_days",
    outcome_kind: str = "continuous",
) -> Any:
    from doubleml import DoubleMLClusterData, DoubleMLIRM
    from doubleml.utils.propensity_score_processing import PSProcessorConfig
    import numpy as np
    import pandas as pd
    from threadpoolctl import threadpool_limits

    feature_names = list(nuisances["feature_names"])
    frame = pd.DataFrame(nuisances["matrix"], columns=feature_names)
    frame[outcome_field] = nuisances["outcome"]
    frame["high_load_exposure"] = nuisances["exposure"]
    frame["supplier_id"] = nuisances["groups"]
    if outcome_kind not in {"continuous", "binary"}:
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    outcome_learner = (
        _outcome_classifier
        if outcome_kind == "binary"
        else _outcome_regressor
    )
    outcome_component = (
        "binary_outcome_learner_unexposed"
        if outcome_kind == "binary"
        else "outcome_learner_unexposed"
    )
    try:
        data = DoubleMLClusterData(
            frame,
            y_col=outcome_field,
            d_cols="high_load_exposure",
            cluster_cols="supplier_id",
            x_cols=feature_names,
        )
        model = DoubleMLIRM(
            data,
            outcome_learner(
                _stage_seed(
                    request,
                    variant_id=variant_id,
                    repeat_index=0,
                    outer_fold_index=0,
                    component=outcome_component,
                )
            ),
            _propensity_classifier(
                _stage_seed(
                    request,
                    variant_id=variant_id,
                    repeat_index=0,
                    outer_fold_index=0,
                    component="propensity_learner",
                )
            ),
            n_folds=5,
            n_rep=2,
            score=score,
            normalize_ipw=False,
            ps_processor_config=PSProcessorConfig(
                clipping_threshold=0.10,
                extreme_threshold=1e-12,
                calibration_method=None,
                cv_calibration=False,
            ),
            draw_sample_splitting=False,
        )
        model.set_sample_splitting(
            nuisances["all_smpls"],
            nuisances["all_smpls_cluster"],
        )
        external_predictions = {
            "high_load_exposure": {
                "ml_g0": nuisances["g0"],
                "ml_g1": nuisances["g1"],
                "ml_m": nuisances["ml_m"],
            }
        }
        with threadpool_limits(limits=1):
            model.fit(
                n_jobs_cv=1,
                store_predictions=True,
                external_predictions=external_predictions,
            )
        for learner_name in ("ml_g0", "ml_g1", "ml_m"):
            observed = np.asarray(model.predictions[learner_name], dtype=np.float64)
            if observed.shape == (len(nuisances["retained_ids"]), 2, 1):
                observed = observed[:, :, 0]
            elif observed.shape == (len(nuisances["retained_ids"]), 1, 2):
                observed = observed[:, 0, :]
            expected_key = {"ml_g0": "g0", "ml_g1": "g1", "ml_m": "ml_m"}[learner_name]
            expected = np.asarray(nuisances[expected_key], dtype=np.float64)
            if (
                observed.shape != expected.shape
                or not np.isfinite(observed).all()
                or not np.allclose(
                    observed,
                    expected,
                    atol=(
                        NUMERIC_TOLERANCE_REGISTRY["processed_propensity_absolute"]
                        if learner_name == "ml_m"
                        else NUMERIC_TOLERANCE_REGISTRY["external_prediction_absolute"]
                    ),
                    rtol=0.0,
                )
            ):
                raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    except EstimatorStageError:
        raise
    except Exception:
        raise EstimatorStageError("ENGINE_ESTIMATOR_FIT_FAILED") from None
    return model


def _effect_result(
    request: Mapping[str, Any],
    model: Any,
    nuisances: Mapping[str, Any],
    *,
    variant_id: str = "primary",
    estimand_id: str,
    role: str,
    score: str,
    label: str | None = None,
    estimator_class: str = "DoubleMLIRM",
    unit: str = "days",
    display_scale: float = 1.0,
    display_unit: str | None = None,
    duration_basis: str | None = None,
    nuisance_keys: Sequence[tuple[str, str]] = (
        ("ml_g0", "g0"),
        ("ml_g1", "g1"),
        ("ml_m", "ml_m"),
    ),
) -> dict[str, Any]:
    import numpy as np

    def flat(value: Any) -> np.ndarray:
        return np.asarray(value, dtype=np.float64).reshape(-1)

    try:
        coefficient = flat(model.coef)
        standard_error = flat(model.se)
        repeat_coefficients = flat(model.all_coef)
        repeat_standard_errors = flat(model.all_se)
        t_statistic = flat(model.t_stat)
        p_value = flat(model.pval)
        interval = model.confint(level=0.95)
        ci_lower = float(interval.iloc[0, 0])
        ci_upper = float(interval.iloc[0, 1])
    except Exception:
        raise EstimatorStageError("ENGINE_RESULT_INVALID") from None
    if (
        len(coefficient) != 1
        or len(standard_error) != 1
        or len(repeat_coefficients) != 2
        or len(repeat_standard_errors) != 2
        or len(t_statistic) != 1
        or len(p_value) != 1
        or not all(
            math.isfinite(float(value))
            for value in [
                coefficient[0],
                standard_error[0],
                *repeat_coefficients.tolist(),
                *repeat_standard_errors.tolist(),
                t_statistic[0],
                p_value[0],
                ci_lower,
                ci_upper,
            ]
        )
        or standard_error[0] <= 0
        or any(value <= 0 for value in repeat_standard_errors)
        or not 0 <= p_value[0] <= 1
        or ci_lower > ci_upper
    ):
        raise EstimatorStageError("ENGINE_RESULT_INVALID")
    nuisance_refs = [
        f"nuisance:{name}:{scientific_sha256(nuisances[key].tolist())}"
        for name, key in nuisance_keys
    ]
    if display_unit is None:
        display_unit = unit
    if duration_basis is None:
        duration_basis = (
            request["canonical_slippage_duration_basis"]
            if unit != "absolute_probability"
            else "NOT_APPLICABLE"
        )
    display_values = {
        "estimate": float(coefficient[0]) * display_scale,
        "standard_error": float(standard_error[0]) * display_scale,
        "ci_lower": ci_lower * display_scale,
        "ci_upper": ci_upper * display_scale,
    }
    repeat_results = [
        {
            "repeat_index": index,
            "estimate": float(repeat_coefficients[index]),
            "standard_error": float(repeat_standard_errors[index]),
        }
        for index in range(2)
    ]
    result = {
        "estimand_id": estimand_id,
        "role": role,
        "label": label,
        "estimator_class": estimator_class,
        "score": score,
        "estimate": float(coefficient[0]),
        "standard_error": float(standard_error[0]),
        "t_statistic": float(t_statistic[0]),
        "p_value": float(p_value[0]),
        "ci_level": 0.95,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "unit": unit,
        "duration_basis": duration_basis,
        "display_transform": {
            "scale": display_scale,
            "display_unit": display_unit,
            **display_values,
        },
        "cluster_key": "supplier_id",
        "cluster_count": len(set(nuisances["groups"].tolist())),
        "exposed_count": int(sum(nuisances["exposure"].tolist())),
        "unexposed_count": int(len(nuisances["exposure"]) - sum(nuisances["exposure"].tolist())),
        "row_count": len(nuisances["retained_ids"]),
        "repeat_results": repeat_results,
        "cohort_identity_hash": nuisances["cohort_identity_hash"],
        "nuisance_refs": nuisance_refs,
        "fold_ref": f"folds:{variant_id}-s9:{scientific_sha256(nuisances['fold_records'])}",
        "inference": {
            "method": "DoubleML.native",
            "covariance": "supplier_clustered",
            "confidence_interval": "two_sided_95_percent_marginal",
        },
        "numeric_tolerances": deepcopy(NUMERIC_TOLERANCE_REGISTRY),
    }
    if not isinstance(result["cohort_identity_hash"], str):
        raise EstimatorStageError("ENGINE_RESULT_INVALID")
    return result


def _fit_variant_plr_nuisances(
    request: Mapping[str, Any],
    variant_id: str,
    rows: Sequence[Mapping[str, Any]],
    layout: Any,
    retained_ids: Sequence[str],
    variant_stage: Mapping[str, Any],
) -> dict[str, Any]:
    import numpy as np
    from threadpoolctl import threadpool_limits

    try:
        matrix = layout.transform(rows)
    except PropensityStageError as error:
        raise EstimatorStageError(error.code) from None
    outcome = np.asarray(
        [float(row["supplier_milestone_slippage_days"]) for row in rows],
        dtype=np.float64,
    )
    load = np.asarray(
        [float(row["load_percentile"]) for row in rows],
        dtype=np.float64,
    )
    groups = np.asarray([str(row["supplier_id"]) for row in rows], dtype=object)
    if (
        not np.isfinite(matrix).all()
        or not np.isfinite(outcome).all()
        or not np.isfinite(load).all()
        or np.any(load < 0.0)
        or np.any(load > 1.0)
    ):
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    try:
        all_smpls, all_smpls_cluster, fold_records = _variant_s9_splits(
            variant_stage,
            rows,
            retained_ids,
        )
    except EstimatorStageError:
        raise
    ml_l = np.full((len(rows), 2), np.nan, dtype=np.float64)
    ml_m = np.full((len(rows), 2), np.nan, dtype=np.float64)
    with threadpool_limits(limits=1):
        for repeat_index, repeat_smpls in enumerate(all_smpls):
            for fold_index, (train, test) in enumerate(repeat_smpls):
                try:
                    outcome_model = _outcome_regressor(
                        _stage_seed(
                            request,
                            variant_id=variant_id,
                            repeat_index=repeat_index,
                            outer_fold_index=fold_index,
                            component="continuous_outcome_learner",
                        )
                    )
                    exposure_model = _outcome_regressor(
                        _stage_seed(
                            request,
                            variant_id=variant_id,
                            repeat_index=repeat_index,
                            outer_fold_index=fold_index,
                            component="continuous_exposure_learner",
                        )
                    )
                    outcome_model.fit(matrix[train], outcome[train])
                    exposure_model.fit(matrix[train], load[train])
                    ml_l[test, repeat_index] = outcome_model.predict(matrix[test])
                    ml_m[test, repeat_index] = exposure_model.predict(matrix[test])
                except EstimatorStageError:
                    raise
                except Exception:
                    raise EstimatorStageError("ENGINE_NUISANCE_FIT_FAILED") from None
    if not np.isfinite(ml_l).all() or not np.isfinite(ml_m).all():
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    return {
        "matrix": matrix,
        "outcome": outcome,
        "continuous_exposure": load,
        "exposure": np.asarray(
            [1 if bool(row["high_load_exposure"]) else 0 for row in rows],
            dtype=np.int8,
        ),
        "groups": groups,
        "cohort_identity_hash": variant_stage["s9"].get("identity_hash"),
        "retained_ids": list(retained_ids),
        "feature_names": list(layout.feature_names),
        "feature_schema_digest": scientific_sha256(list(layout.feature_names)),
        "all_smpls": all_smpls,
        "all_smpls_cluster": all_smpls_cluster,
        "fold_records": fold_records,
        "l": ml_l,
        "m": ml_m,
    }


def _fit_variant_plr(
    request: Mapping[str, Any],
    variant_id: str,
    nuisances: Mapping[str, Any],
) -> Any:
    from doubleml import DoubleMLClusterData, DoubleMLPLR
    import numpy as np
    import pandas as pd
    from threadpoolctl import threadpool_limits

    feature_names = list(nuisances["feature_names"])
    frame = pd.DataFrame(nuisances["matrix"], columns=feature_names)
    frame["supplier_milestone_slippage_days"] = nuisances["outcome"]
    frame["load_percentile"] = nuisances["continuous_exposure"]
    frame["supplier_id"] = nuisances["groups"]
    try:
        data = DoubleMLClusterData(
            frame,
            y_col="supplier_milestone_slippage_days",
            d_cols="load_percentile",
            cluster_cols="supplier_id",
            x_cols=feature_names,
        )
        model = DoubleMLPLR(
            data,
            _outcome_regressor(
                _stage_seed(
                    request,
                    variant_id=variant_id,
                    repeat_index=0,
                    outer_fold_index=0,
                    component="continuous_outcome_learner",
                )
            ),
            _outcome_regressor(
                _stage_seed(
                    request,
                    variant_id=variant_id,
                    repeat_index=0,
                    outer_fold_index=0,
                    component="continuous_exposure_learner",
                )
            ),
            n_folds=5,
            n_rep=2,
            score="partialling out",
            draw_sample_splitting=False,
        )
        model.set_sample_splitting(
            nuisances["all_smpls"],
            nuisances["all_smpls_cluster"],
        )
        external_predictions = {
            "load_percentile": {
                "ml_l": nuisances["l"],
                "ml_m": nuisances["m"],
            }
        }
        with threadpool_limits(limits=1):
            model.fit(
                n_jobs_cv=1,
                store_predictions=True,
                external_predictions=external_predictions,
            )
        for learner_name, expected_key in (("ml_l", "l"), ("ml_m", "m")):
            observed = np.asarray(model.predictions[learner_name], dtype=np.float64)
            if observed.shape == (len(nuisances["retained_ids"]), 2, 1):
                observed = observed[:, :, 0]
            elif observed.shape == (len(nuisances["retained_ids"]), 1, 2):
                observed = observed[:, 0, :]
            expected = np.asarray(nuisances[expected_key], dtype=np.float64)
            if (
                observed.shape != expected.shape
                or not np.isfinite(observed).all()
                or not np.allclose(
                    observed,
                    expected,
                    atol=NUMERIC_TOLERANCE_REGISTRY["external_prediction_absolute"],
                    rtol=0.0,
                )
            ):
                raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    except EstimatorStageError:
        raise
    except Exception:
        raise EstimatorStageError("ENGINE_ESTIMATOR_FIT_FAILED") from None
    return model


def _comparison_feature_layout(
    request: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[str], Any]:
    import numpy as np

    adjustment_set = request.get("adjustment_set")
    if not isinstance(adjustment_set, Mapping):
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    fields = adjustment_set.get("fields")
    if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    definitions = _field_definition_map(adjustment_set)
    numeric_fields = {
        field
        for field in fields
        if field in NUMERIC_ADJUSTMENT_FIELDS
        or definitions.get(field, {}).get("estimation_type") in {"numeric", "continuous"}
        or definitions.get(field, {}).get("logical_type") in {"numeric", "number"}
    }
    feature_names: list[str] = []
    columns: list[list[float]] = []
    for field in fields:
        values = [
            row.get("covariates", {}).get(field)
            for row in rows
            if isinstance(row.get("covariates"), Mapping)
        ]
        if len(values) != len(rows) or any(not isinstance(value, Mapping) for value in values):
            raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        if field in numeric_fields:
            value_column = [
                float(value.get("value"))
                if value.get("state") == "present"
                and isinstance(value.get("value"), (int, float))
                and not isinstance(value.get("value"), bool)
                and math.isfinite(float(value.get("value")))
                else 0.0
                for value in values
            ]
            if any(value != 0.0 for value in value_column):
                feature_names.append(f"{field}::value")
                columns.append(value_column)
            for state in VALUE_STATES[1:]:
                state_column = [
                    1.0 if value.get("state") == state else 0.0 for value in values
                ]
                if any(state_column):
                    feature_names.append(f"{field}::state:{state}")
                    columns.append(state_column)
            continue

        declared_values = _declared_categorical_values(definitions.get(field, {}))
        levels: list[str] = []
        if declared_values is not None:
            try:
                for value in declared_values:
                    token = f"value:{scientific_json(value)}"
                    if token not in levels:
                        levels.append(token)
            except (TypeError, ValueError, OverflowError):
                raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION") from None
        else:
            try:
                observed_values = {_value_token(value) for value in values}
            except PropensityStageError as error:
                raise EstimatorStageError(error.code) from None
            levels.extend(
                sorted(
                    (token for token in observed_values if token.startswith("value:")),
                    key=lambda token: token.encode("utf-8"),
                )
            )
        levels.extend(
            token
            for token in (f"state:{state}" for state in VALUE_STATES[1:])
            if token not in levels
        )
        if len(levels) < 1:
            raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        observed_tokens = set(observed_values) if declared_values is None else set()
        if declared_values is not None:
            try:
                observed_tokens = {_value_token(value) for value in values}
            except PropensityStageError as error:
                raise EstimatorStageError(error.code) from None
            if not observed_tokens.issubset(set(levels)):
                raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
        for token in levels[1:]:
            if declared_values is None and token not in observed_tokens:
                continue
            column = [1.0 if _value_token(value) == token else 0.0 for value in values]
            if not any(column):
                continue
            feature_names.append(f"{field}::{token}")
            columns.append(column)
    matrix = np.asarray(columns, dtype=np.float64).T if columns else np.empty((len(rows), 0))
    if not np.isfinite(matrix).all():
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    return feature_names, matrix


def _comparison_result(
    request: Mapping[str, Any],
    nuisances: Mapping[str, Any],
    comparison_id: str,
) -> dict[str, Any]:
    import numpy as np
    import statsmodels.api as sm

    if comparison_id not in COMPARISON_IDS:
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
    y = np.asarray(nuisances["outcome"], dtype=np.float64)
    exposure = np.asarray(nuisances["exposure"], dtype=np.float64)
    groups = np.asarray(nuisances["groups"], dtype=object)
    row_count = len(y)
    supplier_ids = sorted({str(value) for value in groups.tolist()}, key=lambda value: value.encode("utf-8"))
    if row_count == 0 or len(set(exposure.tolist())) != 2 or len(supplier_ids) < 2:
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
    feature_names: list[str] = []
    feature_matrix = np.empty((row_count, 0), dtype=np.float64)
    if comparison_id in {"covariate_ols", "supplier_fe_ols"}:
        feature_names, feature_matrix = _comparison_feature_layout(
            request,
            [
                {
                    "covariates": {
                        field: row["covariates"][field]
                        for field in request["adjustment_set"]["fields"]
                    }
                }
                for row in nuisances["rows"]
            ],
        )
    columns = ["intercept", "high_load_exposure", *feature_names]
    design_parts = [np.ones((row_count, 1)), exposure.reshape(-1, 1)]
    if feature_matrix.shape[1]:
        design_parts.append(feature_matrix)
    if comparison_id == "supplier_fe_ols":
        supplier_columns = [
            (f"supplier_id::{supplier_id}", (groups == supplier_id).astype(np.float64))
            for supplier_id in supplier_ids[1:]
        ]
        columns.extend(name for name, _ in supplier_columns)
        if supplier_columns:
            design_parts.append(
                np.column_stack([values for _, values in supplier_columns])
            )
    design = np.column_stack(design_parts)
    weights = None
    weight_diagnostics: dict[str, Any] | None = None
    model_class = "OLS"
    if comparison_id == "normalized_ipw_atte":
        propensity = np.asarray(nuisances["ml_m"], dtype=np.float64)[:, 0]
        if (
            propensity.shape != (row_count,)
            or not np.isfinite(propensity).all()
            or np.any(propensity <= 0.0)
            or np.any(propensity >= 1.0)
        ):
            raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
        weights = np.where(exposure == 1.0, 1.0, propensity / (1.0 - propensity))
        exposed_mask = exposure == 1.0
        unexposed_mask = ~exposed_mask
        exposed_count = int(exposed_mask.sum())
        unexposed_raw_sum = float(weights[unexposed_mask].sum())
        if exposed_count <= 0 or unexposed_raw_sum <= 0.0:
            raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
        weights[unexposed_mask] *= exposed_count / unexposed_raw_sum
        model_class = "WLS"
        weight_diagnostics = {
            "raw_weight_sums": {
                "exposed": float(weights[exposed_mask].sum()),
                "unexposed": unexposed_raw_sum,
            },
            "normalized_weight_sums": {
                "exposed": float(weights[exposed_mask].sum()),
                "unexposed": float(weights[unexposed_mask].sum()),
            },
            "effective_sample_sizes": {
                "exposed": float(
                    weights[exposed_mask].sum() ** 2
                    / np.square(weights[exposed_mask]).sum()
                ),
                "unexposed": float(
                    weights[unexposed_mask].sum() ** 2
                    / np.square(weights[unexposed_mask]).sum()
                ),
            },
        }
    if not np.isfinite(design).all():
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
    design_rank = np.linalg.matrix_rank(design)
    if design_rank <= 1:
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
    exposure_rank = np.linalg.matrix_rank(np.delete(design, 1, axis=1))
    if exposure_rank == design_rank:
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
    try:
        if model_class == "WLS":
            fitted = sm.WLS(y, design, weights=weights).fit(
                cov_type="cluster",
                cov_kwds={
                    "groups": np.asarray(
                        [supplier_ids.index(str(value)) for value in groups],
                        dtype=int,
                    ),
                    "use_correction": True,
                    "df_correction": True,
                },
                use_t=True,
            )
        else:
            fitted = sm.OLS(y, design).fit(
                cov_type="cluster",
                cov_kwds={
                    "groups": np.asarray(
                        [supplier_ids.index(str(value)) for value in groups],
                        dtype=int,
                    ),
                    "use_correction": True,
                    "df_correction": True,
                },
                use_t=True,
            )
        coefficient = float(fitted.params[1])
        standard_error = float(fitted.bse[1])
        t_statistic = float(fitted.tvalues[1])
        p_value = float(fitted.pvalues[1])
        interval = fitted.conf_int(alpha=0.05)
        ci_lower = float(interval[1, 0])
        ci_upper = float(interval[1, 1])
        rank = int(design_rank)
        condition_number = float(np.linalg.cond(design))
    except Exception:
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED") from None
    if (
        not all(
            math.isfinite(value)
            for value in [coefficient, standard_error, t_statistic, p_value, ci_lower, ci_upper, condition_number]
        )
        or standard_error <= 0.0
        or not 0.0 <= p_value <= 1.0
        or ci_lower > ci_upper
        or not math.isfinite(condition_number)
        or condition_number <= 0.0
    ):
        raise EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")
    result = {
        "comparison_id": comparison_id,
        "model_class": model_class,
        "coefficient_name": "high_load_exposure",
        "estimate": coefficient,
        "standard_error": standard_error,
        "t_statistic": t_statistic,
        "p_value": p_value,
        "ci_level": 0.95,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "covariance_type": "cluster",
        "cluster_key": "supplier_id",
        "use_correction": True,
        "df_correction": True,
        "use_t": True,
        "inference_df": len(supplier_ids) - 1,
        "row_count": row_count,
        "exposed_count": int(exposure.sum()),
        "unexposed_count": int(row_count - exposure.sum()),
        "supplier_count": len(supplier_ids),
        "matrix_column_count": int(design.shape[1]),
        "matrix_rank": rank,
        "condition_number": condition_number,
        "design_matrix_digest": scientific_sha256(
            {"columns": columns, "shape": list(design.shape), "values": design.tolist()}
        ),
        "feature_schema_digest": scientific_sha256(columns),
        "cohort_identity_hash": nuisances["cohort_identity_hash"],
    }
    if comparison_id == "normalized_ipw_atte":
        result["propensity_ref"] = (
            f"nuisance:ml_m:{scientific_sha256(nuisances['ml_m'].tolist())}"
        )
        result["fold_ref"] = (
            f"folds:primary-s9:{scientific_sha256(nuisances['fold_records'])}"
        )
        result["weight_diagnostics"] = weight_diagnostics
    return result


def _comparison_suite(
    request: Mapping[str, Any],
    nuisances: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        comparison_id: _comparison_result(request, nuisances, comparison_id)
        for comparison_id in COMPARISON_IDS
    }


def _subject_support_result(
    request: Mapping[str, Any],
    primary_stage: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    subject = request.get("subject")
    if subject is None:
        return None
    if not isinstance(subject, Mapping):
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    if subject.get("state") == "scientifically_unavailable":
        return {
            "state": "unsupported",
            "scope": "subject",
            "reason_code": subject.get("scientific_code"),
            "subject_id": subject.get("subject_id"),
            "subject_profile": None,
            "propensity": None,
            "overlap": None,
            "distribution_support": None,
            "eligibility_codes": deepcopy(subject.get("eligibility_codes", [])),
            "evidence_refs": deepcopy(subject.get("evidence_refs", [])),
        }
    if subject.get("state") != "eligible":
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    subject_id = subject.get("subject_id")
    profile = subject.get("profile")
    if (
        not isinstance(subject_id, str)
        or not subject_id
        or not isinstance(profile, Mapping)
        or not isinstance(profile.get("adjustment_inputs"), Mapping)
    ):
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    adjustment_set = request.get("adjustment_set")
    subject_inputs = profile["adjustment_inputs"]
    if (
        not isinstance(adjustment_set, Mapping)
        or set(subject_inputs) != set(adjustment_set.get("fields", []))
        or any(
            not isinstance(subject_inputs[field], Mapping)
            for field in subject_inputs
        )
    ):
        raise EstimatorStageError("ENGINE_FEATURE_CONTRACT_VIOLATION")
    subject_propensity = primary_stage.get("subject_propensity")
    if not isinstance(subject_propensity, Mapping):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    predictions = subject_propensity.get("repeat_fold_predictions")
    mean = subject_propensity.get("value")
    if (
        not isinstance(predictions, list)
        or len(predictions) != 10
        or not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and 0.0 <= float(value) <= 1.0
            for value in predictions
        )
        or not isinstance(mean, (int, float))
        or isinstance(mean, bool)
        or not math.isfinite(float(mean))
    ):
        raise EstimatorStageError("ENGINE_NUISANCE_PREDICTION_INVALID")
    from .eligibility import evaluate_subject_distribution_support

    historical_rows = [
        {
            "order_line_id": str(row["order_line_id"]),
            "supplier_id": str(row["supplier_id"]),
            "exposure": bool(row["high_load_exposure"]),
            "inputs": deepcopy(row["covariates"]),
        }
        for row in rows
    ]
    distribution_support = evaluate_subject_distribution_support(
        subject_inputs,
        historical_rows,
    )
    subject_overlap_supported = 0.10 <= float(mean) <= 0.90
    overlap = {
        "state": "supported" if subject_overlap_supported else "unsupported",
        "support_interval": {"lower": 0.10, "upper": 0.90, "inclusive": True},
        "value": float(mean),
        "reason_code": None
        if subject_overlap_supported
        else "SUBJECT_OVERLAP_INSUFFICIENT",
    }
    distribution_supported = distribution_support.get("state") == "supported"
    reason_code = (
        None
        if subject_overlap_supported and distribution_supported
        else (
            "SUBJECT_OVERLAP_INSUFFICIENT"
            if not subject_overlap_supported
            else "SUBJECT_DISTRIBUTION_UNSUPPORTED"
        )
    )
    result = {
        "state": "supported" if reason_code is None else "unsupported",
        "scope": "subject",
        "reason_code": reason_code,
        "subject_id": subject_id,
        "subject_profile": deepcopy(dict(profile)),
        "canonical_exposure": deepcopy(
            subject.get(
                "canonical_exposure",
                profile.get("canonical_exposure", profile.get("provisional_exposure_preview")),
            )
        ),
        "provisional_exposure_preview": deepcopy(
            subject.get(
                "provisional_exposure_preview",
                profile.get("provisional_exposure_preview"),
            )
        ),
        "propensity": {
            "state": "present",
            "repeat_fold_predictions": [float(value) for value in predictions],
            "value": float(mean),
            "aggregation": subject_propensity.get(
                "aggregation", "arithmetic_mean_of_ten_primary_outer_fold_models"
            ),
        },
        "overlap": overlap,
        "distribution_support": distribution_support,
        "eligibility_codes": deepcopy(subject.get("eligibility_codes", [])),
        "evidence_refs": deepcopy(subject.get("evidence_refs", [])),
    }
    return result


def _variant_seed_registry(
    request: Mapping[str, Any],
    variant_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            key: deepcopy(entry[key])
            for key in (
                "variant_id",
                "component",
                "repeat_index",
                "outer_fold_index",
                "inner_fold_index",
                "seed",
            )
        }
        for entry in derived_seed_registry(request)
        if entry.get("variant_id") == variant_id
    ]


def _variant_provenance(
    request: Mapping[str, Any],
    source_variant: Mapping[str, Any],
    materialized_variant: Mapping[str, Any],
    *,
    fold_ref: str | None = None,
) -> dict[str, Any]:
    s9 = materialized_variant.get("s9")
    s9_mapping = s9 if isinstance(s9, Mapping) else {}
    seed_registry = _variant_seed_registry(
        request,
        str(source_variant.get("variant_id")),
    )
    feature_schema = materialized_variant.get("feature_schema")
    return {
        "variant_id": source_variant.get("variant_id"),
        "threshold_rule_ref": deepcopy(source_variant.get("threshold_rule_ref")),
        "selector_refs": deepcopy(source_variant.get("selector_refs", [])),
        "cohort_stage_summaries": deepcopy(
            source_variant.get("cohort_stage_summaries", {})
        ),
        "upstream_status": source_variant.get("upstream_status"),
        "scientific_code": source_variant.get("scientific_code"),
        "gate_stage": source_variant.get("gate_stage"),
        "s8_identity_hash": source_variant.get("s8_identity_hash"),
        "s8_content_hash": source_variant.get("s8_content_hash"),
        "s9_identity_hash": s9_mapping.get("identity_hash"),
        "evidence_refs": deepcopy(source_variant.get("evidence_refs", [])),
        "root_seed": request["root_seed"],
        "seed_policy": {"id": SEED_POLICY_ID, "version": SEED_POLICY_VERSION},
        "seed_registry": seed_registry,
        "seed_registry_digest": scientific_sha256(seed_registry),
        "feature_schema_digest": (
            feature_schema.get("feature_schema_digest")
            if isinstance(feature_schema, Mapping)
            else None
        ),
        "fold_ref": fold_ref,
    }


def _sensitivity_state_result(
    request: Mapping[str, Any],
    source_variant: Mapping[str, Any],
    materialized_variant: Mapping[str, Any],
    *,
    state: str,
    reason_code: str | None,
    component_failures: Sequence[Mapping[str, Any]] = (),
    last_completed_stage: str,
    effect: Mapping[str, Any] | None = None,
    estimand_id: str | None = None,
) -> dict[str, Any]:
    variant_id = str(source_variant["variant_id"])
    resolved_estimand_id = estimand_id or SENSITIVITY_ESTIMAND_IDS[variant_id]
    provenance = _variant_provenance(
        request,
        source_variant,
        materialized_variant,
        fold_ref=effect.get("fold_ref") if isinstance(effect, Mapping) else None,
    )
    if state == "estimated" and isinstance(effect, Mapping):
        result = deepcopy(dict(effect))
        result.update(
            {
                "variant_id": variant_id,
                "status": "estimated",
                "state": "estimated",
                "provenance": provenance,
            }
        )
        return result
    return {
        "variant_id": variant_id,
        "status": state,
        "state": state,
        "reason_code": reason_code,
        "estimand_id": resolved_estimand_id,
        "role": "sensitivity",
        "effect": None,
        "component_failures": deepcopy(list(component_failures)),
        "last_completed_stage": last_completed_stage,
        "provenance": provenance,
    }


def _estimator_safe_detail(
    propensity_stage: Mapping[str, Any],
    *,
    execution_state: str,
    last_completed_stage: str,
    estimator_executed: bool,
    failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    safe_detail = deepcopy(propensity_stage.get("safe_detail", {}))
    if not isinstance(safe_detail, dict):
        safe_detail = {
            "schema_version": "analysis-run-safe-detail.v1",
            "variants": [],
        }
    safe_detail.update(
        {
            "execution_state": execution_state,
            "last_completed_stage": last_completed_stage,
            "component_failures": deepcopy(list(failures)),
            "estimator_executed": estimator_executed,
            "scope": "primary_atte_context_and_sensitivities",
        }
    )
    return safe_detail


def _primary_engine_common(
    request: Mapping[str, Any],
    propensity_stage: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ENGINE_OUTPUT_SCHEMA_VERSION,
        "engine_input_schema_version": request["engine_input_schema_version"],
        "engine_output_schema_version": request["engine_output_schema_version"],
        "error_registry_version": request["error_registry_version"],
        "causal_question_id": request["causal_question_id"],
        "causal_question_version": request["causal_question_version"],
        "engine_config_id": request["engine_config_id"],
        "engine_config_version": request["engine_config_version"],
        "dataset_version_id": request["dataset_version_id"],
        "intended_role": request["intended_role"],
        "target_milestone_kind": request["target_milestone_kind"],
        "canonical_slippage_duration_basis": request[
            "canonical_slippage_duration_basis"
        ],
        "suite_id": request["suite_id"],
        "suite_version": request["suite_version"],
        "root_seed": request["root_seed"],
        "evidence_refs": deepcopy(request["evidence_refs"]),
        "variants": deepcopy(propensity_stage.get("variants", {})),
        "scope": "primary_atte_context_and_sensitivities",
    }


def _public_primary_result(engine_result: Mapping[str, Any]) -> dict[str, Any] | None:
    if engine_result.get("status") != "estimated":
        return None
    safe_effect_fields = (
        "estimand_id",
        "role",
        "label",
        "estimator_class",
        "score",
        "estimate",
        "standard_error",
        "t_statistic",
        "p_value",
        "ci_level",
        "ci_lower",
        "ci_upper",
        "unit",
        "duration_basis",
        "display_transform",
        "cluster_key",
        "cluster_count",
        "exposed_count",
        "unexposed_count",
        "row_count",
        "repeat_results",
        "cohort_identity_hash",
        "nuisance_refs",
        "fold_ref",
        "inference",
    )
    public_sensitivities: dict[str, dict[str, Any]] = {}
    raw_sensitivities = engine_result.get("sensitivity_results")
    if isinstance(raw_sensitivities, Mapping):
        for estimand_id in SECONDARY_ESTIMAND_IDS:
            raw = raw_sensitivities.get(estimand_id)
            if not isinstance(raw, Mapping):
                continue
            visible = {
                key: deepcopy(raw[key])
                for key in (
                    "variant_id",
                    "status",
                    "state",
                    "reason_code",
                    "estimand_id",
                    "role",
                    "label",
                    "estimator_class",
                    "score",
                    "estimate",
                    "standard_error",
                    "t_statistic",
                    "p_value",
                    "ci_level",
                    "ci_lower",
                    "ci_upper",
                    "unit",
                    "duration_basis",
                    "display_transform",
                    "cluster_key",
                    "cluster_count",
                    "exposed_count",
                    "unexposed_count",
                    "row_count",
                    "repeat_results",
                    "cohort_identity_hash",
                    "nuisance_refs",
                    "fold_ref",
                    "inference",
                    "component_failures",
                    "last_completed_stage",
                    "effect",
                    "provenance",
                )
                if key in raw
            }
            public_sensitivities[estimand_id] = visible
    return {
        "schema_version": "fresh-primary-result.v1",
        "state": "provisional",
        "primary_atte": {
            key: deepcopy(engine_result["primary_atte"].get(key))
            for key in safe_effect_fields
            if key in engine_result["primary_atte"]
        },
        "context_ate": {
            key: deepcopy(engine_result["context_ate"].get(key))
            for key in safe_effect_fields
            if key in engine_result["context_ate"]
        },
        "sensitivity_results": public_sensitivities,
        "comparison_results": deepcopy(engine_result.get("comparison_results", {})),
        "subject_support": deepcopy(engine_result.get("subject_support")),
        "permission": {
            "evidence_verdict": False,
            "action_permission": False,
            "state": "provisional_run_output_only",
        },
    }


def estimate_primary_atte_and_context(
    value: Mapping[str, Any] | ValidatedSuiteRequest,
    propensity_stage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate the closed causal engine suite.

    The primary ATTE remains authoritative when the suite completes. The
    registered alternate forms and comparisons are descriptive or sensitivity
    outputs and never replace it. Scientific unavailability remains a typed
    subordinate state, while a required runtime failure fails closed without
    publishing a partial primary estimate.
    """

    validated = (
        value
        if isinstance(value, ValidatedSuiteRequest)
        else validate_suite_request(value)
    )
    request = validated.request
    stage = (
        propensity_stage
        if propensity_stage is not None
        else materialize_propensity_and_s9(validated)
    )
    if not isinstance(stage, Mapping):
        raise EstimatorStageError("ENGINE_INTERNAL_ERROR")
    result = _primary_engine_common(request, stage)
    stage_failures = stage.get("component_failures")
    if not isinstance(stage_failures, list):
        stage_failures = []
    stage_variants = stage.get("variants")
    if not isinstance(stage_variants, Mapping):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    source_variants = {
        str(variant["variant_id"]): variant
        for variant in request["variant_inputs"]
        if isinstance(variant, Mapping) and isinstance(variant.get("variant_id"), str)
    }
    primary_stage = stage_variants.get("primary")
    if not isinstance(primary_stage, Mapping):
        raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
    primary_source = source_variants.get("primary")
    if not isinstance(primary_source, Mapping):
        raise EstimatorStageError("ENGINE_INPUT_SCHEMA_UNSUPPORTED")
    primary_s9 = primary_stage.get("s9")
    primary_is_supported = (
        primary_stage.get("state") == "materialized"
        and isinstance(primary_s9, Mapping)
        and primary_s9.get("state") == "supported"
    )
    if primary_stage.get("state") == "failed":
        code = primary_stage.get("reason_code") or "ENGINE_INTERNAL_ERROR"
        result.update(
            {
                "status": "failed",
                "scientific_outcome": "failed",
                "reason_code": code,
                "estimator_executed": False,
                "safe_detail": _estimator_safe_detail(
                    stage,
                    execution_state="failed",
                    last_completed_stage="S8_OUTCOME",
                    estimator_executed=False,
                    failures=stage_failures,
                ),
            }
        )
        result["result_identity_digest"] = scientific_sha256(result)
        return result
    if not primary_is_supported:
        code = (
            primary_stage.get("reason_code")
            or stage.get("reason_code")
            or "OVERLAP_COHORT_INSUFFICIENT"
        )
        result.update(
            {
                "status": "abstained",
                "scientific_outcome": "abstained",
                "reason_code": code,
                "estimator_executed": False,
                "safe_detail": _estimator_safe_detail(
                    stage,
                    execution_state="complete",
                    last_completed_stage="S9_OVERLAP",
                    estimator_executed=False,
                    failures=[],
                ),
            }
        )
        result["result_identity_digest"] = scientific_sha256(result)
        return result

    estimator_executed = True
    try:
        rows, layout, retained_ids = _variant_rows_and_layout(request, stage, "primary")
        nuisances = _fit_variant_outcome_nuisances(
            request,
            "primary",
            rows,
            layout,
            retained_ids,
            primary_stage,
        )
        primary_model = _fit_variant_irm(request, "primary", nuisances, score="ATTE")
        primary_effect = _effect_result(
            request,
            primary_model,
            nuisances,
            variant_id="primary",
            estimand_id="primary_atte_slippage",
            role="primary",
            score="ATTE",
        )
        context_model = _fit_variant_irm(request, "primary", nuisances, score="ATE")
        context_effect = _effect_result(
            request,
            context_model,
            nuisances,
            variant_id="primary",
            estimand_id="context_ate_slippage",
            role="context",
            score="ATE",
            label="overlap_trimmed_context",
        )
    except EstimatorStageError as error:
        failure = {
            "component": "primary_atte",
            "variant_id": "primary",
            "code": error.code,
        }
        result.update(
            {
                "status": "failed",
                "scientific_outcome": "failed",
                "reason_code": error.code,
                "estimator_executed": estimator_executed,
                "safe_detail": _estimator_safe_detail(
                    stage,
                    execution_state="failed",
                    last_completed_stage="S9_OVERLAP",
                    estimator_executed=estimator_executed,
                    failures=[failure],
                ),
            }
        )
        result["result_identity_digest"] = scientific_sha256(result)
        return result
    except Exception:
        failure = {
            "component": "primary_atte",
            "variant_id": "primary",
            "code": "ENGINE_INTERNAL_ERROR",
        }
        result.update(
            {
                "status": "failed",
                "scientific_outcome": "failed",
                "reason_code": "ENGINE_INTERNAL_ERROR",
                "estimator_executed": estimator_executed,
                "safe_detail": _estimator_safe_detail(
                    stage,
                    execution_state="failed",
                    last_completed_stage="S9_OVERLAP",
                    estimator_executed=estimator_executed,
                    failures=[failure],
                ),
            }
        )
        result["result_identity_digest"] = scientific_sha256(result)
        return result

    prediction_identity = scientific_sha256(
        {
            "ml_g0": nuisances["g0"].tolist(),
            "ml_g1": nuisances["g1"].tolist(),
            "ml_m": nuisances["ml_m"].tolist(),
        }
    )
    sensitivity_results: dict[str, dict[str, Any]] = {}
    sensitivity_failures: list[dict[str, Any]] = []
    for variant_id in SENSITIVITY_VARIANTS:
        source_variant = source_variants.get(variant_id)
        materialized_variant = stage_variants.get(variant_id)
        if not isinstance(source_variant, Mapping) or not isinstance(
            materialized_variant, Mapping
        ):
            raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
        if source_variant.get("upstream_status") == "scientifically_unavailable":
            sensitivity_results[SENSITIVITY_ESTIMAND_IDS[variant_id]] = _sensitivity_state_result(
                request,
                source_variant,
                materialized_variant,
                state="unsupported",
                reason_code=source_variant.get("scientific_code"),
                last_completed_stage=str(
                    source_variant.get("gate_stage") or "S8_OUTCOME"
                ),
            )
            continue
        if materialized_variant.get("state") == "failed":
            failures = materialized_variant.get("component_failures")
            if not isinstance(failures, list) or not failures:
                failures = [
                    {
                        "component": "propensity_ensemble",
                        "variant_id": variant_id,
                        "code": materialized_variant.get(
                            "reason_code", "ENGINE_INTERNAL_ERROR"
                        ),
                    }
                ]
            failure_code = materialized_variant.get("reason_code") or "ENGINE_INTERNAL_ERROR"
            sensitivity_results[SENSITIVITY_ESTIMAND_IDS[variant_id]] = _sensitivity_state_result(
                request,
                source_variant,
                materialized_variant,
                state="failed",
                reason_code=failure_code,
                component_failures=failures,
                last_completed_stage=str(
                    stage.get("safe_detail", {}).get(
                        "last_completed_stage", "S8_OUTCOME"
                    )
                    if isinstance(stage.get("safe_detail"), Mapping)
                    else "S8_OUTCOME"
                ),
            )
            sensitivity_failures.extend(deepcopy(failures))
            continue
        sensitivity_s9 = materialized_variant.get("s9")
        if materialized_variant.get("state") != "materialized" or not isinstance(
            sensitivity_s9, Mapping
        ) or sensitivity_s9.get("state") != "supported":
            sensitivity_results[SENSITIVITY_ESTIMAND_IDS[variant_id]] = _sensitivity_state_result(
                request,
                source_variant,
                materialized_variant,
                state="unsupported",
                reason_code=(
                    materialized_variant.get("reason_code")
                    or "OVERLAP_COHORT_INSUFFICIENT"
                ),
                last_completed_stage="S9_OVERLAP",
            )
            continue
        try:
            sensitivity_rows, sensitivity_layout, sensitivity_ids = (
                _variant_rows_and_layout(request, stage, variant_id)
            )
            sensitivity_nuisances = _fit_variant_outcome_nuisances(
                request,
                variant_id,
                sensitivity_rows,
                sensitivity_layout,
                sensitivity_ids,
                materialized_variant,
            )
            sensitivity_model = _fit_variant_irm(
                request,
                variant_id,
                sensitivity_nuisances,
                score="ATTE",
            )
            sensitivity_effect = _effect_result(
                request,
                sensitivity_model,
                sensitivity_nuisances,
                variant_id=variant_id,
                estimand_id=SENSITIVITY_ESTIMAND_IDS[variant_id],
                role="sensitivity",
                score="ATTE",
            )
        except EstimatorStageError as error:
            failure = {
                "component": "sensitivity_atte",
                "variant_id": variant_id,
                "code": error.code,
            }
            sensitivity_results[SENSITIVITY_ESTIMAND_IDS[variant_id]] = _sensitivity_state_result(
                request,
                source_variant,
                materialized_variant,
                state="failed",
                reason_code=error.code,
                component_failures=[failure],
                last_completed_stage="S9_OVERLAP",
            )
            sensitivity_failures.append(failure)
            continue
        except Exception:
            failure = {
                "component": "sensitivity_atte",
                "variant_id": variant_id,
                "code": "ENGINE_INTERNAL_ERROR",
            }
            sensitivity_results[SENSITIVITY_ESTIMAND_IDS[variant_id]] = _sensitivity_state_result(
                request,
                source_variant,
                materialized_variant,
                state="failed",
                reason_code="ENGINE_INTERNAL_ERROR",
                component_failures=[failure],
                last_completed_stage="S9_OVERLAP",
            )
            sensitivity_failures.append(failure)
            continue
        sensitivity_results[SENSITIVITY_ESTIMAND_IDS[variant_id]] = _sensitivity_state_result(
            request,
            source_variant,
            materialized_variant,
            state="estimated",
            reason_code=None,
            last_completed_stage="SENSITIVITY_ESTIMATION",
            effect=sensitivity_effect,
        )

    if sensitivity_failures:
        failed_sensitivities = {
            estimand_id: sensitivity_results[estimand_id]
            for variant_id in SENSITIVITY_VARIANTS
            for estimand_id in (SENSITIVITY_ESTIMAND_IDS[variant_id],)
            if estimand_id in sensitivity_results
            and sensitivity_results[estimand_id].get("state") == "failed"
        }
        result.update(
            {
                "status": "failed",
                "scientific_outcome": "failed",
                "reason_code": sensitivity_failures[0]["code"],
                "estimator_executed": estimator_executed,
                "sensitivity_results": failed_sensitivities,
                "sensitivity_failures": sensitivity_failures,
                "safe_detail": _estimator_safe_detail(
                    stage,
                    execution_state="failed",
                    last_completed_stage="S9_OVERLAP",
                    estimator_executed=estimator_executed,
                    failures=sensitivity_failures,
                ),
            }
        )
        result["result_identity_digest"] = scientific_sha256(result)
        return result

    secondary_failures: list[dict[str, Any]] = []
    try:
        late_support_rows = primary_source.get("rows")
        if not isinstance(late_support_rows, list):
            raise EstimatorStageError("ENGINE_REPRODUCIBILITY_VIOLATION")
        late_count = sum(
            1
            for row in late_support_rows
            if isinstance(row.get("supplier_milestone_late"), bool)
            and row["supplier_milestone_late"]
        )
        non_late_count = len(late_support_rows) - late_count
        if late_count < 50 or non_late_count < 50:
            sensitivity_results[LATE_SENSITIVITY_ESTIMAND_ID] = _sensitivity_state_result(
                request,
                primary_source,
                primary_stage,
                state="unsupported",
                reason_code="COHORT_SUPPORT_INSUFFICIENT",
                last_completed_stage="S9_OVERLAP",
                estimand_id=LATE_SENSITIVITY_ESTIMAND_ID,
            )
        else:
            late_nuisances = _fit_variant_outcome_nuisances(
                request,
                "primary",
                rows,
                layout,
                retained_ids,
                primary_stage,
                outcome_field="supplier_milestone_late",
                outcome_kind="binary",
            )
            late_model = _fit_variant_irm(
                request,
                "primary",
                late_nuisances,
                score="ATTE",
                outcome_field="supplier_milestone_late",
                outcome_kind="binary",
            )
            late_effect = _effect_result(
                request,
                late_model,
                late_nuisances,
                variant_id="primary",
                estimand_id=LATE_SENSITIVITY_ESTIMAND_ID,
                role="sensitivity",
                score="ATTE",
                label="binary_late_risk_difference",
                unit="absolute_probability",
                display_scale=100.0,
                display_unit="percentage_points",
                duration_basis="NOT_APPLICABLE",
            )
            sensitivity_results[LATE_SENSITIVITY_ESTIMAND_ID] = _sensitivity_state_result(
                request,
                primary_source,
                primary_stage,
                state="estimated",
                reason_code=None,
                last_completed_stage="SENSITIVITY_ESTIMATION",
                effect=late_effect,
                estimand_id=LATE_SENSITIVITY_ESTIMAND_ID,
            )

        continuous_nuisances = _fit_variant_plr_nuisances(
            request,
            "primary",
            rows,
            layout,
            retained_ids,
            primary_stage,
        )
        continuous_model = _fit_variant_plr(
            request,
            "primary",
            continuous_nuisances,
        )
        continuous_effect = _effect_result(
            request,
            continuous_model,
            continuous_nuisances,
            variant_id="primary",
            estimand_id=CONTINUOUS_LOAD_SENSITIVITY_ESTIMAND_ID,
            role="sensitivity",
            score="partialling out",
            label="linear_average_slope",
            estimator_class="DoubleMLPLR",
            unit="days_per_unit_load_percentile",
            display_scale=0.10,
            display_unit="days_per_0_10_load_percentile",
            nuisance_keys=(("ml_l", "l"), ("ml_m", "m")),
        )
        sensitivity_results[CONTINUOUS_LOAD_SENSITIVITY_ESTIMAND_ID] = _sensitivity_state_result(
            request,
            primary_source,
            primary_stage,
            state="estimated",
            reason_code=None,
            last_completed_stage="SENSITIVITY_ESTIMATION",
            effect=continuous_effect,
            estimand_id=CONTINUOUS_LOAD_SENSITIVITY_ESTIMAND_ID,
        )
        comparison_results = _comparison_suite(request, nuisances)
        subject_support = _subject_support_result(request, primary_stage, rows)
    except EstimatorStageError as error:
        secondary_failures.append(
            {
                "component": "secondary_suite",
                "variant_id": "primary",
                "code": error.code,
            }
        )
    except Exception:
        secondary_failures.append(
            {
                "component": "secondary_suite",
                "variant_id": "primary",
                "code": "ENGINE_INTERNAL_ERROR",
            }
        )

    if secondary_failures:
        result.update(
            {
                "status": "failed",
                "scientific_outcome": "failed",
                "reason_code": secondary_failures[0]["code"],
                "estimator_executed": estimator_executed,
                "sensitivity_failures": secondary_failures,
                "safe_detail": _estimator_safe_detail(
                    stage,
                    execution_state="failed",
                    last_completed_stage="S9_OVERLAP",
                    estimator_executed=estimator_executed,
                    failures=secondary_failures,
                ),
            }
        )
        result["result_identity_digest"] = scientific_sha256(result)
        return result

    result.update(
        {
            "status": "estimated",
            "scientific_outcome": "estimated",
            "reason_code": None,
            "estimator_executed": True,
            "primary_atte": primary_effect,
            "context_ate": context_effect,
            "sensitivity_results": sensitivity_results,
            "sensitivity_failures": sensitivity_failures,
            "comparison_results": comparison_results,
            "subject_support": subject_support,
            "shared_nuisance": {
                "schema_version": "doubleml-shared-nuisance.v1",
                "feature_schema_digest": nuisances["feature_schema_digest"],
                "feature_names": deepcopy(nuisances["feature_names"]),
                "row_ids": deepcopy(nuisances["retained_ids"]),
                "external_prediction_shapes": {
                    "ml_g0": list(nuisances["g0"].shape),
                    "ml_g1": list(nuisances["g1"].shape),
                    "ml_m": list(nuisances["ml_m"].shape),
                },
                "external_predictions": {
                    "high_load_exposure": {
                        "ml_g0": nuisances["g0"].tolist(),
                        "ml_g1": nuisances["g1"].tolist(),
                        "ml_m": nuisances["ml_m"].tolist(),
                    }
                },
                "prediction_identity_hash": prediction_identity,
                "fit_once_for_estimands": [
                    "primary_atte_slippage",
                    "context_ate_slippage",
                ],
                "doubleml_refit_nuisance": False,
                "fold_records": deepcopy(nuisances["fold_records"]),
                "numeric_tolerances": deepcopy(NUMERIC_TOLERANCE_REGISTRY),
            },
            "safe_detail": _estimator_safe_detail(
                stage,
                execution_state="complete",
                last_completed_stage="PRIMARY_ESTIMATION",
                estimator_executed=True,
                failures=sensitivity_failures,
            ),
        }
    )
    result["result_identity_digest"] = scientific_sha256(result)
    return result


def _fresh_json_bytes(value: object) -> bytes:
    try:
        return canonical_json(value).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise FreshAnalysisFinalizationError("RUN_ARTIFACT_SERIALIZATION_FAILED") from error


def _fresh_validate_engine_result(
    request: Mapping[str, Any],
    stage: Mapping[str, Any],
    engine_result: Mapping[str, Any],
) -> None:
    if engine_result.get("schema_version") != ENGINE_OUTPUT_SCHEMA_VERSION:
        raise FreshAnalysisFinalizationError("ENGINE_RESULT_SCHEMA_UNSUPPORTED")
    if engine_result.get("engine_output_schema_version") != request.get(
        "engine_output_schema_version"
    ):
        raise FreshAnalysisFinalizationError("ENGINE_RESULT_INPUT_MISMATCH")
    for key in (
        "engine_input_schema_version",
        "error_registry_version",
        "causal_question_id",
        "causal_question_version",
        "engine_config_id",
        "engine_config_version",
        "dataset_version_id",
        "intended_role",
        "target_milestone_kind",
        "canonical_slippage_duration_basis",
        "suite_id",
        "suite_version",
        "root_seed",
    ):
        if engine_result.get(key) != request.get(key):
            raise FreshAnalysisFinalizationError("ENGINE_RESULT_INPUT_MISMATCH")
    if engine_result.get("evidence_refs") != request.get("evidence_refs"):
        raise FreshAnalysisFinalizationError("ENGINE_RESULT_INPUT_MISMATCH")
    stage_digest = stage.get("scientific_request_digest")
    if stage_digest != scientific_sha256(request):
        raise FreshAnalysisFinalizationError("ENGINE_STAGE_INPUT_MISMATCH")
    if scientific_sha256(engine_result.get("variants")) != scientific_sha256(
        stage.get("variants")
    ):
        raise FreshAnalysisFinalizationError("ENGINE_STAGE_RESULT_MISMATCH")
    result_identity_digest = engine_result.get("result_identity_digest")
    if not isinstance(result_identity_digest, str):
        raise FreshAnalysisFinalizationError("ENGINE_RESULT_IDENTITY_UNAVAILABLE")
    identity_payload = {
        key: value
        for key, value in engine_result.items()
        if key != "result_identity_digest"
    }
    if scientific_sha256(identity_payload) != result_identity_digest:
        raise FreshAnalysisFinalizationError("ENGINE_RESULT_IDENTITY_MISMATCH")


def _fresh_artifact_member(
    *,
    logical_role: str,
    logical_id: str,
    producer_schema_id: str,
    producer_schema_version: str,
    payload: Mapping[str, Any],
    evidence_refs: Sequence[str] = (),
    scientific_content: bool = True,
) -> Any:
    from .references import ArtifactMember

    content = _fresh_json_bytes(payload)
    return ArtifactMember(
        logical_role=logical_role,
        logical_id=logical_id,
        producer_schema_id=producer_schema_id,
        producer_schema_version=producer_schema_version,
        media_type="application/json",
        confidentiality_class="public_safe",
        content=content,
        evidence_refs=tuple(evidence_refs),
        scientific_content_digest=content_sha256(payload) if scientific_content else None,
    )


def _fresh_primary_diagnostic_inputs(
    request: Mapping[str, Any],
    stage: Mapping[str, Any],
    engine_result: Mapping[str, Any],
) -> dict[str, Any]:
    stage_variants = stage.get("variants")
    if not isinstance(stage_variants, Mapping):
        raise FreshAnalysisFinalizationError("ENGINE_REPRODUCIBILITY_VIOLATION")
    source_variants = {
        str(variant["variant_id"]): variant
        for variant in request.get("variant_inputs", [])
        if isinstance(variant, Mapping) and isinstance(variant.get("variant_id"), str)
    }
    primary_source = source_variants.get("primary")
    primary_stage = stage_variants.get("primary")
    if not isinstance(primary_source, Mapping) or not isinstance(primary_stage, Mapping):
        raise FreshAnalysisFinalizationError("ENGINE_REPRODUCIBILITY_VIOLATION")

    primary_rows: list[dict[str, Any]] | None = None
    feature_order: list[str] | None = None
    balance_rows: list[dict[str, Any]] | None = None
    feature_matrix: list[list[float]] = []
    primary_feature_schema: dict[str, Any] = {
        "schema_version": "feature_schema.v1",
        "ordered_feature_names": [],
        "row_identity_hash": scientific_sha256([]),
        "shape": [0, 0],
    }
    if engine_result.get("status") == "estimated":
        try:
            rows, layout, retained_ids = _variant_rows_and_layout(
                request,
                stage,
                "primary",
            )
            matrix = layout.transform(rows)
        except (EstimatorStageError, PropensityStageError, KeyError, TypeError, ValueError):
            raise FreshAnalysisFinalizationError("ENGINE_REPRODUCIBILITY_VIOLATION") from None
        primary_rows = [deepcopy(dict(row)) for row in rows]
        feature_order = [str(name) for name in layout.feature_names]
        feature_matrix = [
            [float(value) for value in row]
            for row in matrix.tolist()
        ]
        raw_feature_schema = primary_stage.get("feature_schema")
        primary_feature_schema = {
            "schema_version": "feature_schema.v1",
            "ordered_feature_names": feature_order,
            "feature_schema_digest": (
                raw_feature_schema.get("feature_schema_digest")
                if isinstance(raw_feature_schema, Mapping)
                else scientific_sha256(feature_order)
            ),
            "row_identity_hash": scientific_sha256(list(retained_ids)),
            "shape": [len(feature_matrix), len(feature_order)],
        }
        predictions = primary_stage.get("propensity_predictions")
        if not isinstance(predictions, list):
            raise FreshAnalysisFinalizationError("ENGINE_NUISANCE_PREDICTION_INVALID")
        propensity_by_id = {
            str(item.get("row_id")): item
            for item in predictions
            if isinstance(item, Mapping) and isinstance(item.get("row_id"), str)
        }
        if set(propensity_by_id) != set(retained_ids):
            raise FreshAnalysisFinalizationError("ENGINE_NUISANCE_PREDICTION_INVALID")
        balance_rows = []
        for row, matrix_row, row_id in zip(
            primary_rows,
            feature_matrix,
            retained_ids,
            strict=True,
        ):
            prediction = propensity_by_id[row_id]
            mean = prediction.get("mean")
            if not isinstance(mean, (int, float)) or isinstance(mean, bool) or not math.isfinite(float(mean)):
                raise FreshAnalysisFinalizationError("ENGINE_NUISANCE_PREDICTION_INVALID")
            balance_rows.append(
                {
                    "row_id": row_id,
                    "exposure": bool(row["high_load_exposure"]),
                    "propensity": float(mean),
                    "features": {
                        name: value for name, value in zip(feature_order, matrix_row, strict=True)
                    },
                }
            )

    upstream_status = primary_source.get("upstream_status")
    if upstream_status == "released":
        eligibility = {"state": "eligible", "eligibility_codes": []}
    else:
        code = (
            primary_source.get("scientific_code")
            or primary_stage.get("reason_code")
            or "COHORT_SUPPORT_INSUFFICIENT"
        )
        eligibility = {
            "state": "scientifically_unavailable",
            "eligibility_codes": [str(code)],
        }
    overlap = primary_stage.get("overlap")
    if not isinstance(overlap, Mapping):
        overlap = None

    primary_artifacts: dict[str, Any] | None = None
    if primary_rows is not None:
        retained_ids = [str(row["order_line_id"]) for row in primary_rows]
        fold_assignments = primary_stage.get("fold_assignments")
        if not isinstance(fold_assignments, list) or not fold_assignments:
            raise FreshAnalysisFinalizationError("ENGINE_FOLD_ASSIGNMENT_INVALID")
        primary_artifacts = {
            "outer_splits": deepcopy(fold_assignments),
            "inner_splits": deepcopy(fold_assignments),
            "canonical_row_ids": retained_ids,
            "propensity_predictions": {
                row_id: [
                    float(next(item["mean"] for item in primary_stage["propensity_predictions"] if item.get("row_id") == row_id)),
                    float(next(item["mean"] for item in primary_stage["propensity_predictions"] if item.get("row_id") == row_id)),
                ]
                for row_id in retained_ids
            },
            "fold_provenance_verified": True,
            "propensity_provenance_verified": True,
            "propensity_provenance_ref": "nuisance_predictions:primary",
            "support": deepcopy(overlap) if overlap is not None else {"state": "supported"},
        }

    return {
        "eligibility": eligibility,
        "overlap": overlap,
        "primary_rows": primary_rows,
        "balance_rows": balance_rows,
        "feature_order": feature_order,
        "feature_matrix": feature_matrix,
        "primary_feature_schema": primary_feature_schema,
        "primary_artifacts": primary_artifacts,
    }


def _fresh_diagnostic_payload(
    *,
    request: Mapping[str, Any],
    stage: Mapping[str, Any],
    engine_result: Mapping[str, Any],
    analysis_run_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from .diagnostics import diagnostic_summary, evaluate_validity_diagnostics
    from .refuters import ExactEstimatorAdapter

    inputs = _fresh_primary_diagnostic_inputs(request, stage, engine_result)
    evidence_refs = (
        "engine_request:request",
        "engine_result:result",
        "cohort_stage_records:cohorts",
    )
    input_refs = (
        "engine_result:result",
        "feature_matrix:primary",
        "fold_assignments:folds",
        "nuisance_predictions:nuisance",
    )
    estimator_adapter = None
    if inputs["primary_rows"] is not None:
        estimator_adapter = ExactEstimatorAdapter(
            lambda _request: {
                "status": "unsupported",
                "support_failure": {
                    "state": "unsupported",
                    "invariant": "fresh-exact-refuter-adapter-not-configured",
                },
            },
            support_state="unsupported",
        )
    diagnostics = evaluate_validity_diagnostics(
        engine_result=engine_result,
        eligibility=inputs["eligibility"],
        overlap=inputs["overlap"],
        balance_rows=inputs["balance_rows"],
        feature_order=inputs["feature_order"],
        refuter_rows=inputs["primary_rows"],
        refuter_primary_effect=(
            engine_result.get("primary_atte")
            if isinstance(engine_result.get("primary_atte"), Mapping)
            else None
        ),
        refuter_estimator_adapter=estimator_adapter,
        refuter_seed_context={
            "root_seed": request["root_seed"],
            "dataset_version_id": request["dataset_version_id"],
            "causal_question_id": request["causal_question_id"],
            "causal_question_version": request["causal_question_version"],
            "engine_config_id": request["engine_config_id"],
            "engine_config_version": request["engine_config_version"],
            "suite_id": request["suite_id"],
            "suite_version": request["suite_version"],
            "validity_policy_id": "causal-validity-verdict-policy",
            "validity_policy_version": "1",
        },
        refuter_primary_artifacts=inputs["primary_artifacts"],
        negative_control_rows=inputs["primary_rows"],
        negative_control_estimator_adapter=estimator_adapter,
        negative_control_primary_artifacts=inputs["primary_artifacts"],
        intended_role=str(request["intended_role"]),
        canonical_slippage_duration_basis=str(
            request["canonical_slippage_duration_basis"]
        ),
        effect_result_ref="engine_result:primary_atte",
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=None,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
    )
    if not isinstance(diagnostics, list) or len(diagnostics) != 14:
        raise FreshAnalysisFinalizationError("DIAGNOSTIC_SET_INCOMPLETE")
    validity = {
        "schema_version": "diagnostic_artifacts.v1",
        "diagnostics": diagnostics,
        "diagnostic_summary": diagnostic_summary(diagnostics),
    }
    from .validity import evaluate_complete_validity

    # evaluate_validity_diagnostics returns only records; reproduce the locked
    # validity projection from those same records and exact engine outputs.
    complete = evaluate_complete_validity(
        base_diagnostics=diagnostics[:9],
        primary_effect=(
            engine_result.get("primary_atte")
            if isinstance(engine_result.get("primary_atte"), Mapping)
            else None
        ),
        engine_result=engine_result,
        intended_role=str(request["intended_role"]),
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=None,
        canonical_slippage_duration_basis=str(
            request["canonical_slippage_duration_basis"]
        ),
        effect_result_ref="engine_result:primary_atte",
        evidence_refs=evidence_refs,
        input_refs=input_refs,
    )
    if [item.get("content_hash") for item in complete["diagnostics"]] != [
        item.get("content_hash") for item in diagnostics
    ]:
        raise FreshAnalysisFinalizationError("DIAGNOSTIC_RESULT_IDENTITY_MISMATCH")
    validity.update(
        {
            "robustness_grade": complete["robustness_grade"],
            "evidence_verdict": complete["evidence_verdict"],
        }
    )
    from .validity import (
        derive_subject_evidence_verdict,
        render_evidence_verdict,
        render_subject_evidence_verdict,
    )

    subject_verdict = None
    rendered_subject_verdict = None
    subject_support = engine_result.get("subject_support")
    request_subject = request.get("subject")
    if subject_support is None and isinstance(request_subject, Mapping):
        subject_support = {
            "subject_id": request_subject.get("subject_id"),
            "subject_profile": request_subject.get("profile"),
            "propensity": {"state": "unavailable"},
            "distribution_support": {"state": "unavailable"},
        }
    if isinstance(subject_support, Mapping) and isinstance(
        subject_support.get("subject_id"), str
    ):
        profile = subject_support.get("subject_profile")
        subject_profile = (
            profile.get("adjustment_inputs")
            if isinstance(profile, Mapping)
            and isinstance(profile.get("adjustment_inputs"), Mapping)
            else profile
            if isinstance(profile, Mapping)
            else {}
        )
        subject_propensity = subject_support.get("propensity")
        if not isinstance(subject_propensity, Mapping):
            subject_propensity = {"state": "unavailable"}
        distribution_support = subject_support.get("distribution_support")
        if not isinstance(distribution_support, Mapping):
            distribution_support = {"state": "unavailable"}
        subject_verdict = derive_subject_evidence_verdict(
            complete["evidence_verdict"],
            subject_id=str(subject_support["subject_id"]),
            subject_profile=subject_profile,
            subject_propensity=subject_propensity,
            distribution_support=distribution_support,
            source_role=str(request["intended_role"]),
        )
        rendered_subject_verdict = render_subject_evidence_verdict(subject_verdict)
    validity["subject_verdict"] = subject_verdict
    validity["rendered_verdict"] = render_evidence_verdict(complete["evidence_verdict"])
    validity["rendered_subject_verdict"] = rendered_subject_verdict
    return validity, inputs


def _fresh_effect_free_result(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "variant_id",
        "status",
        "state",
        "reason_code",
        "estimand_id",
        "role",
        "label",
        "component_failures",
        "last_completed_stage",
        "provenance",
    }
    return {key: deepcopy(value[key]) for key in allowed if key in value}


def _fresh_sealed_primary_result(
    engine_result: Mapping[str, Any],
    evidence_verdict: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    public = _public_primary_result(engine_result)
    if public is None:
        return None
    sealed = deepcopy(public)
    sealed["schema_version"] = "fresh-primary-result.v2"
    sealed["state"] = "sealed"
    verdict_code = evidence_verdict.get("verdict_code") if evidence_verdict else None
    effect_display = evidence_verdict.get("effect_display") if evidence_verdict else "NONE"
    if verdict_code == "SUPPORTED_UNDER_ASSUMPTIONS":
        pass
    elif (
        verdict_code in {"ASSOCIATION_ONLY", "INSUFFICIENT"}
        and effect_display != "NONE"
        and evidence_verdict is not None
    ):
        sealed["primary_atte"] = deepcopy(evidence_verdict.get("effect"))
        sealed["context_ate"] = None
        sealed["sensitivity_results"] = {
            key: _fresh_effect_free_result(value)
            for key, value in sealed.get("sensitivity_results", {}).items()
            if isinstance(value, Mapping)
        }
        sealed["comparison_results"] = {}
    else:
        sealed["primary_atte"] = None
        sealed["context_ate"] = None
        sealed["sensitivity_results"] = {
            key: _fresh_effect_free_result(value)
            for key, value in sealed.get("sensitivity_results", {}).items()
            if isinstance(value, Mapping)
        }
        sealed["comparison_results"] = {}
    sealed["permission"] = {
        "evidence_verdict": evidence_verdict is not None,
        "action_permission": bool(
            evidence_verdict
            and evidence_verdict.get("decision_support_evaluation_permitted") is True
        ),
        "state": "sealed_machine_verified",
        "claim_scope": (
            evidence_verdict.get("permitted_claim_scope")
            if evidence_verdict is not None
            else None
        ),
        "effect_display": effect_display,
    }
    return sealed


def _fresh_artifact_members(
    *,
    request: Mapping[str, Any],
    admission: Mapping[str, Any],
    stage: Mapping[str, Any],
    engine_result: Mapping[str, Any],
    diagnostic_payload: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> list[Any]:
    from .references import VERIFICATION_REPORT_SCHEMA_VERSION

    source_variants = {
        str(variant["variant_id"]): variant
        for variant in request.get("variant_inputs", [])
        if isinstance(variant, Mapping) and isinstance(variant.get("variant_id"), str)
    }
    stage_variants = stage.get("variants")
    if not isinstance(stage_variants, Mapping):
        raise FreshAnalysisFinalizationError("ENGINE_REPRODUCIBILITY_VIOLATION")
    runtime = admission.get("runtime_fingerprint")
    if not isinstance(runtime, Mapping):
        raise FreshAnalysisFinalizationError("ENGINE_RUNTIME_INCOMPATIBLE")
    primary_feature_schema = inputs["primary_feature_schema"]
    feature_matrix_payload = {
        "schema_version": "feature_matrix.v1",
        "row_ids": [str(row["order_line_id"]) for row in inputs["primary_rows"] or []],
        "ordered_feature_names": list(primary_feature_schema["ordered_feature_names"]),
        "shape": list(primary_feature_schema["shape"]),
        "dtype": "float64",
        "values": deepcopy(inputs["feature_matrix"]),
    }
    cohort_variants: dict[str, Any] = {}
    visible_variants: dict[str, Any] = {}
    feature_schemas: dict[str, Any] = {}
    fold_variants: dict[str, Any] = {}
    nuisance_variants: dict[str, Any] = {}
    for variant_id in VARIANT_ORDER:
        source = source_variants.get(variant_id, {})
        materialized = stage_variants.get(variant_id, {})
        cohort_variants[variant_id] = {
            "source": deepcopy(dict(source)) if isinstance(source, Mapping) else {},
            "materialized": deepcopy(dict(materialized))
            if isinstance(materialized, Mapping)
            else {},
        }
        rows = source.get("rows", []) if isinstance(source, Mapping) else []
        s9 = materialized.get("s9") if isinstance(materialized, Mapping) else None
        visible_variants[variant_id] = {
            "s8_rows": deepcopy(rows) if isinstance(rows, list) else [],
            "s9": deepcopy(dict(s9)) if isinstance(s9, Mapping) else None,
        }
        raw_schema = materialized.get("feature_schema") if isinstance(materialized, Mapping) else None
        feature_schemas[variant_id] = (
            deepcopy(dict(raw_schema)) if isinstance(raw_schema, Mapping) else {
                "schema_version": "analysis-run-feature-matrix.v1",
                "ordered_feature_names": [],
                "shape": [0, 0],
            }
        )
        fold_variants[variant_id] = deepcopy(
            materialized.get("fold_assignments", [])
            if isinstance(materialized, Mapping)
            else []
        )
        nuisance_variants[variant_id] = deepcopy(
            materialized.get("propensity_predictions", [])
            if isinstance(materialized, Mapping)
            else []
        )

    model_recipe = {
        "schema_version": "model_recipe_registry.v1",
        "recipes": [
            {
                "recipe_id": "propensity",
                "estimator": deepcopy(request.get("propensity_spec", {})),
                "runtime_dependencies": deepcopy(runtime.get("loaded_engine_dependencies", {})),
            },
            {
                "recipe_id": "outcome_nuisances",
                "estimator": "HistGradientBoostingRegressor",
                "training_policy": "supplier_grouped_outer_oof",
                "runtime_dependencies": deepcopy(runtime.get("loaded_engine_dependencies", {})),
            },
            {
                "recipe_id": "causal_effect",
                "estimator": "DoubleMLIRM",
                "score": "ATTE",
                "inference": "supplier_clustered",
                "n_jobs_cv": 1,
            },
        ],
    }
    seed_registry = {
        "schema_version": "derived_seed_registry.v1",
        "records": deepcopy(admission.get("derived_seed_registry", [])),
    }
    cohort_records = {
        "schema_version": "cohort_stage_records.v1",
        "variants": cohort_variants,
    }
    visible_rows = {
        "schema_version": "estimator_visible_rows.v1",
        "variants": visible_variants,
    }
    feature_schema = {
        "schema_version": "feature_schema.v1",
        "primary": primary_feature_schema,
        "variants": feature_schemas,
    }
    fold_assignments = {
        "schema_version": "fold_assignments.v1",
        "variants": fold_variants,
    }
    nuisance_predictions = {
        "schema_version": "nuisance_predictions.v1",
        "variants": nuisance_variants,
        "shared_nuisance": deepcopy(engine_result.get("shared_nuisance")),
        "subject_support": deepcopy(engine_result.get("subject_support")),
    }
    common_refs = ("engine_request:request", "runtime_fingerprint:runtime")
    members = [
        _fresh_artifact_member(
            logical_role="engine_request",
            logical_id="request",
            producer_schema_id="causal-engine-input",
            producer_schema_version="v2",
            payload=dict(request),
            evidence_refs=("runtime_fingerprint:runtime",),
            scientific_content=False,
        ),
        _fresh_artifact_member(
            logical_role="runtime_fingerprint",
            logical_id="runtime",
            producer_schema_id="analysis-runtime-fingerprint",
            producer_schema_version="v1",
            payload=dict(runtime),
            scientific_content=False,
        ),
        _fresh_artifact_member(
            logical_role="model_recipe_registry",
            logical_id="recipes",
            producer_schema_id="model_recipe_registry",
            producer_schema_version="v1",
            payload=model_recipe,
            evidence_refs=common_refs,
        ),
        _fresh_artifact_member(
            logical_role="derived_seed_registry",
            logical_id="seeds",
            producer_schema_id="derived_seed_registry",
            producer_schema_version="v1",
            payload=seed_registry,
            evidence_refs=("engine_request:request",),
        ),
        _fresh_artifact_member(
            logical_role="cohort_stage_records",
            logical_id="cohorts",
            producer_schema_id="cohort_stage_records",
            producer_schema_version="v1",
            payload=cohort_records,
            evidence_refs=("engine_request:request",),
        ),
        _fresh_artifact_member(
            logical_role="estimator_visible_rows",
            logical_id="rows",
            producer_schema_id="estimator_visible_rows",
            producer_schema_version="v1",
            payload=visible_rows,
            evidence_refs=("cohort_stage_records:cohorts",),
        ),
        _fresh_artifact_member(
            logical_role="feature_schema",
            logical_id="schema",
            producer_schema_id="feature_schema",
            producer_schema_version="v1",
            payload=feature_schema,
            evidence_refs=("estimator_visible_rows:rows",),
        ),
        _fresh_artifact_member(
            logical_role="feature_matrix",
            logical_id="primary",
            producer_schema_id="feature_matrix",
            producer_schema_version="v1",
            payload=feature_matrix_payload,
            evidence_refs=("feature_schema:schema", "estimator_visible_rows:rows"),
        ),
        _fresh_artifact_member(
            logical_role="fold_assignments",
            logical_id="folds",
            producer_schema_id="fold_assignments",
            producer_schema_version="v1",
            payload=fold_assignments,
            evidence_refs=("estimator_visible_rows:rows",),
        ),
        _fresh_artifact_member(
            logical_role="nuisance_predictions",
            logical_id="nuisance",
            producer_schema_id="nuisance_predictions",
            producer_schema_version="v1",
            payload=nuisance_predictions,
            evidence_refs=("fold_assignments:folds", "feature_matrix:primary"),
        ),
        _fresh_artifact_member(
            logical_role="engine_result",
            logical_id="result",
            producer_schema_id="causal-engine-result",
            producer_schema_version="v1",
            payload=dict(engine_result),
            evidence_refs=("engine_request:request", "nuisance_predictions:nuisance"),
        ),
        _fresh_artifact_member(
            logical_role="diagnostic_artifacts",
            logical_id="diagnostics",
            producer_schema_id="diagnostic_artifacts",
            producer_schema_version="v1",
            payload=dict(diagnostic_payload),
            evidence_refs=("engine_result:result", "feature_matrix:primary"),
        ),
    ]
    check_basis = {
        "roles": sorted(member.logical_role for member in members),
        "request_digest": admission.get("scientific_request_digest"),
        "runtime_digest": admission.get("runtime_fingerprint_digest"),
        "engine_result_digest": content_sha256(engine_result),
    }
    verification_report = {
        "schema_version": VERIFICATION_REPORT_SCHEMA_VERSION,
        "validation_policy_version": "analysis-run-verification.v1",
        "status": "passed",
        "checks": [
            {
                "check_id": "required_roles",
                "status": "passed",
                "evidence_digest": content_sha256(check_basis),
            },
            {
                "check_id": "cross_reference_integrity",
                "status": "passed",
                "evidence_digest": content_sha256(
                    {
                        "request": admission.get("scientific_request_digest"),
                        "runtime": admission.get("runtime_fingerprint_digest"),
                    }
                ),
            },
        ],
    }
    members.append(
        _fresh_artifact_member(
            logical_role="verification_report",
            logical_id="verification",
            producer_schema_id="analysis-run-verification",
            producer_schema_version="v1",
            payload=verification_report,
            evidence_refs=tuple(
                f"{member.logical_role}:{member.logical_id}" for member in members
            ),
            scientific_content=False,
        )
    )
    return members


def finalize_fresh_analysis(
    *,
    artifact_root: Path,
    analysis_run_id: str,
    admission: Mapping[str, Any],
    propensity_stage: Mapping[str, Any],
    engine_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Turn one fresh engine execution into a verified, sealed read projection."""

    from .references import (
        ARTIFACT_CONTRACT_VERSION,
        BUNDLE_MANIFEST_SCHEMA_VERSION,
        build_cache_key,
        publish_analysis_bundle,
        verify_published_analysis_bundle,
    )
    from .validity import publish_validity_results

    try:
        analysis_run_id_for_operation("operation-" + analysis_run_id.removeprefix("analysis-run-"))
    except ValueError:
        raise FreshAnalysisFinalizationError("RUN_ID_INVALID") from None
    request_value = admission.get("suite_request")
    runtime_value = admission.get("runtime_fingerprint")
    if not isinstance(request_value, Mapping) or not isinstance(runtime_value, Mapping):
        raise FreshAnalysisFinalizationError("ENGINE_INPUT_INTEGRITY_MISMATCH")
    try:
        request = validate_suite_request(request_value).request
    except (TypeError, ValueError):
        raise FreshAnalysisFinalizationError("ENGINE_INPUT_INTEGRITY_MISMATCH") from None
    if admission.get("scientific_request_digest") != scientific_sha256(request):
        raise FreshAnalysisFinalizationError("ENGINE_INPUT_INTEGRITY_MISMATCH")
    if engine_result.get("status") not in {"estimated", "abstained"}:
        raise FreshAnalysisFinalizationError("ENGINE_EXECUTION_FAILED")
    if not isinstance(propensity_stage.get("variants"), Mapping):
        raise FreshAnalysisFinalizationError("ENGINE_REPRODUCIBILITY_VIOLATION")
    _fresh_validate_engine_result(request, propensity_stage, engine_result)
    diagnostic_payload, inputs = _fresh_diagnostic_payload(
        request=request,
        stage=propensity_stage,
        engine_result=engine_result,
        analysis_run_id=analysis_run_id,
    )
    validity = publish_validity_results(
        diagnostic_payload,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=None,
        evidence_refs=("engine_request:request", "engine_result:result"),
        input_refs=("diagnostic_artifacts:diagnostics",),
    )
    if validity["evidence_verdict"] is None or validity["robustness_grade"] is None:
        raise FreshAnalysisFinalizationError("EVIDENCE_VERDICT_UNAVAILABLE")
    diagnostic_payload.update(
        {
            "diagnostics": validity["diagnostics"],
            "diagnostic_summary": diagnostic_payload["diagnostic_summary"],
            "robustness_grade": validity["robustness_grade"],
            "evidence_verdict": validity["evidence_verdict"],
        }
    )
    members = _fresh_artifact_members(
        request=request,
        admission=admission,
        stage=propensity_stage,
        engine_result=engine_result,
        diagnostic_payload=diagnostic_payload,
        inputs=inputs,
    )
    reproduces_run_id = admission.get("reproduces_run_id")
    reproduction_comparison: dict[str, Any] | None = None
    if reproduces_run_id is not None:
        if not isinstance(reproduces_run_id, str):
            raise FreshAnalysisFinalizationError("RUN_REPRODUCTION_TARGET_UNAVAILABLE")
        from .references import read_verified_analysis_bundle

        try:
            target_manifest, target_payloads = read_verified_analysis_bundle(
                artifact_root,
                analysis_run_id=reproduces_run_id,
                expected_build_id=str(runtime_value.get("application_build_id", "")),
                expected_runtime=runtime_value,
            )
        except (OSError, TypeError, ValueError):
            raise FreshAnalysisFinalizationError(
                "RUN_REPRODUCTION_TARGET_UNAVAILABLE"
            ) from None
        if (
            target_manifest.get("scientific_request_digest")
            != admission.get("scientific_request_digest")
            or target_manifest.get("runtime_fingerprint_digest")
            != admission.get("runtime_fingerprint_digest")
            or target_payloads.get("runtime_fingerprint") != dict(runtime_value)
        ):
            raise FreshAnalysisFinalizationError("RUN_REPRODUCIBILITY_VIOLATION")
        try:
            candidate_payloads = {
                member.logical_role: json.loads(member.content.decode("utf-8"))
                for member in members
            }
        except (UnicodeError, TypeError, ValueError):
            raise FreshAnalysisFinalizationError("RUN_REPRODUCIBILITY_VIOLATION") from None
        expected_projection = build_reproduction_projection(target_payloads)
        observed_projection = build_reproduction_projection(candidate_payloads)
        reproduction_comparison = compare_reproduction_projections(
            expected_projection,
            observed_projection,
            expected_member_hashes=expected_projection["role_digests"],
            observed_member_hashes=observed_projection["role_digests"],
        )
        reproduction_comparison.update(
            {
                "target_run_id": reproduces_run_id,
                "scientific_request_digest": admission["scientific_request_digest"],
                "runtime_fingerprint_digest": admission["runtime_fingerprint_digest"],
            }
        )
        if reproduction_comparison["status"] != "passed":
            raise FreshAnalysisFinalizationError("RUN_REPRODUCIBILITY_VIOLATION")
        members.append(
            _fresh_artifact_member(
                logical_role="reproduction_comparison",
                logical_id="comparison",
                producer_schema_id="analysis-run-reproduction-comparison",
                producer_schema_version="v1",
                payload=reproduction_comparison,
                evidence_refs=(
                    "engine_request:request",
                    "engine_result:result",
                ),
                scientific_content=False,
            )
        )
    started_at = datetime.now(timezone.utc).isoformat()
    completed_at = datetime.now(timezone.utc).isoformat()
    runtime_digest = str(admission["runtime_fingerprint_digest"])
    request_digest = str(admission["scientific_request_digest"])
    engine_schema = str(engine_result.get("schema_version"))
    cache_key = build_cache_key(
        scientific_request_digest=request_digest,
        runtime_fingerprint_digest=runtime_digest,
        engine_output_schema_version=engine_schema,
    )
    build_id = runtime_value.get("application_build_id")
    if not isinstance(build_id, str) or not build_id:
        raise FreshAnalysisFinalizationError("ENGINE_RUNTIME_INCOMPATIBLE")
    manifest: dict[str, Any] = {
        "manifest_schema_version": BUNDLE_MANIFEST_SCHEMA_VERSION,
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "scientific_request_digest": request_digest,
        "runtime_fingerprint_digest": runtime_digest,
        "cache_key": cache_key,
        "engine_result_status": str(engine_result["status"]),
        "started_at": started_at,
        "completed_at": completed_at,
        "producer_application_build_id": build_id,
    }
    investigation_request_id = admission.get("investigation_request_id")
    if isinstance(investigation_request_id, str) and investigation_request_id:
        manifest["investigation_request_id"] = investigation_request_id
    if isinstance(reproduces_run_id, str) and reproduces_run_id:
        manifest["reproduces_run_id"] = reproduces_run_id
    published = publish_analysis_bundle(
        artifact_root,
        analysis_run_id=analysis_run_id,
        manifest=manifest,
        members=members,
    )
    verified = verify_published_analysis_bundle(
        artifact_root,
        analysis_run_id=analysis_run_id,
        expected_build_id=build_id,
        expected_runtime=runtime_value,
    )
    if verified.bundle_manifest_hash != published.bundle_manifest_hash:
        raise FreshAnalysisFinalizationError("RUN_ARTIFACT_INTEGRITY_MISMATCH")
    verified_validity = publish_validity_results(
        diagnostic_payload,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=None,
        evidence_refs=("engine_request:request", "engine_result:result"),
        input_refs=("diagnostic_artifacts:diagnostics",),
    )
    if verified_validity["evidence_verdict"] != validity["evidence_verdict"]:
        raise FreshAnalysisFinalizationError("EVIDENCE_VERDICT_INTEGRITY_MISMATCH")
    result = {
        "schema_version": "analysis-run-execution-result.v1",
        "scientific_request_digest": request_digest,
        "runtime_fingerprint": deepcopy(dict(runtime_value)),
        "runtime_fingerprint_digest": runtime_digest,
        "status": str(engine_result["status"]),
        "reason_code": engine_result.get("reason_code"),
        "failure_code": None,
        "estimator_executed": engine_result.get("estimator_executed") is True,
        "primary_result": _fresh_sealed_primary_result(
            engine_result,
            validity["evidence_verdict"],
        ),
        "safe_detail": deepcopy(dict(engine_result.get("safe_detail", {}))),
        "bundle_manifest_hash": published.bundle_manifest_hash,
        "verification_state": "machine_verified",
        "post_publication_verified": True,
        "diagnostics": deepcopy(validity["diagnostics"]),
        "diagnostic_summary": deepcopy(diagnostic_payload["diagnostic_summary"]),
        "robustness_grade": deepcopy(validity["robustness_grade"]),
        "evidence_verdict": deepcopy(validity["evidence_verdict"]),
        "rendered_verdict": deepcopy(diagnostic_payload["rendered_verdict"]),
        "subject_verdict": deepcopy(diagnostic_payload["subject_verdict"]),
        "rendered_subject_verdict": deepcopy(
            diagnostic_payload["rendered_subject_verdict"]
        ),
    }
    if reproduction_comparison is not None:
        result["reproduces_run_id"] = reproduces_run_id
        result["reproduction_comparison"] = deepcopy(reproduction_comparison)
    result["run_relationship"] = (
        admission.get("run_relationship")
        if admission.get("run_relationship") in {"fresh", "reproduction", "refresh"}
        else "fresh"
    )
    if isinstance(admission.get("refresh_of_request_id"), str):
        result["refresh_of_request_id"] = admission["refresh_of_request_id"]
    result["result_identity_digest"] = scientific_sha256(result)
    return result


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


def _admission_safe_detail(payload: Mapping[str, Any]) -> dict[str, Any]:
    request = payload.get("suite_request")
    variants: list[dict[str, Any]] = []
    if isinstance(request, Mapping) and isinstance(request.get("variant_inputs"), list):
        for variant in request["variant_inputs"]:
            if not isinstance(variant, Mapping):
                continue
            variant_id = variant.get("variant_id")
            if not isinstance(variant_id, str):
                continue
            released = variant.get("upstream_status") == "released"
            variants.append(
                {
                    "variant_id": variant_id,
                    "s8_status": "released" if released else "scientifically_unavailable",
                    "s8_count": len(variant.get("rows", [])) if released else 0,
                    "propensity_status": "pending" if released else "not_run",
                    "overlap_status": "pending" if released else "not_run",
                    "s9_status": "pending" if released else "not_run",
                    "s9_count": 0,
                    "reason_code": variant.get("scientific_code") if not released else None,
                    "component_failures": [],
                }
            )
    return {
        "schema_version": "analysis-run-safe-detail.v1",
        "execution_state": "pending",
        "last_completed_stage": "S8_OUTCOME",
        "variants": variants,
        "component_failures": [],
        "estimator_executed": False,
        "scope": "propensity_and_overlap_only",
    }


def load_fresh_analysis_result(layout: Any, operation_id: str) -> dict[str, Any] | None:
    """Read only the worker's typed, redacted result projection."""

    if layout is None or not isinstance(operation_id, str) or not operation_id.startswith(
        "operation-"
    ):
        return None
    result_path = Path(layout.run_root) / operation_id / "analysis-run-result.json"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError):
        return None
    if not isinstance(result, Mapping) or result.get("schema_version") != (
        "analysis-run-execution-result.v1"
    ):
        return None
    safe_detail = result.get("safe_detail")
    if not isinstance(safe_detail, Mapping):
        return None
    status = result.get("status")
    if status not in {"estimated", "abstained", "failed"}:
        return None
    analysis_run_id = analysis_run_id_for_operation(operation_id)

    def quarantined_projection() -> dict[str, Any] | None:
        from .artifacts import artifact_read_status

        artifact_status = artifact_read_status(
            Path(layout.artifact_root),
            analysis_run_id,
        )
        if artifact_status.lifecycle != "quarantined":
            return None
        return {
            "status": "failed",
            "reason_code": artifact_status.reason_code
            or "RUN_ARTIFACT_INTEGRITY_FAILED",
            "failure_code": "RUN_ARTIFACT_INTEGRITY_FAILED",
            "recovery_action": artifact_status.recovery_action,
            "artifact_lifecycle": artifact_status.lifecycle,
            "safe_detail": deepcopy(dict(safe_detail)),
        }

    if status in {"estimated", "abstained"}:
        result_identity_digest = result.get("result_identity_digest")
        identity_payload = {
            key: value
            for key, value in result.items()
            if key != "result_identity_digest"
        }
        if (
            not isinstance(result_identity_digest, str)
            or scientific_sha256(identity_payload) != result_identity_digest
        ):
            return None
    bundle_manifest_hash = result.get("bundle_manifest_hash")
    runtime = result.get("runtime_fingerprint")
    if status in {"estimated", "abstained"}:
        if (
            not isinstance(bundle_manifest_hash, str)
            or not isinstance(runtime, Mapping)
            or not isinstance(runtime.get("application_build_id"), str)
            or result.get("post_publication_verified") is not True
            or result.get("verification_state") != "machine_verified"
            or not hasattr(layout, "artifact_root")
        ):
            return None
        try:
            from .artifacts import ArtifactLifecycleError, quarantine_analysis_run
            from .references import verify_published_analysis_bundle

            verified = verify_published_analysis_bundle(
                Path(layout.artifact_root),
                analysis_run_id=analysis_run_id,
                expected_build_id=str(runtime["application_build_id"]),
                expected_runtime=runtime,
            )
            if verified.bundle_manifest_hash != bundle_manifest_hash:
                quarantine_analysis_run(
                    Path(layout.artifact_root),
                    analysis_run_id,
                    reason_code="RUN_ARTIFACT_BINDING_MISMATCH",
                )
                return quarantined_projection()
        except (ArtifactLifecycleError, OSError, TypeError, ValueError):
            return quarantined_projection()
        diagnostics = result.get("diagnostics")
        grade = result.get("robustness_grade")
        verdict = result.get("evidence_verdict")
        diagnostic_summary_value = result.get("diagnostic_summary")
        if (
            not isinstance(diagnostics, list)
            or not isinstance(grade, Mapping)
            or not isinstance(verdict, Mapping)
            or not isinstance(diagnostic_summary_value, Mapping)
        ):
            return None
        try:
            from .diagnostics import diagnostic_summary as build_diagnostic_summary
            from .validity import publish_validity_results

            if dict(diagnostic_summary_value) != build_diagnostic_summary(diagnostics):
                return None
            publish_validity_results(
                {
                    "schema_version": "diagnostic_artifacts.v1",
                    "diagnostics": diagnostics,
                    "robustness_grade": grade,
                    "evidence_verdict": verdict,
                },
                analysis_run_id=analysis_run_id_for_operation(operation_id),
                bundle_manifest_hash=None,
                evidence_refs=("engine_request:request", "engine_result:result"),
                input_refs=("diagnostic_artifacts:diagnostics",),
            )
            from .validity import (
                render_evidence_verdict,
                render_subject_evidence_verdict,
            )

            if result.get("rendered_verdict") != render_evidence_verdict(verdict):
                return None
            subject_verdict = result.get("subject_verdict")
            rendered_subject_verdict = result.get("rendered_subject_verdict")
            if subject_verdict is None:
                if rendered_subject_verdict is not None:
                    return None
            elif not isinstance(subject_verdict, Mapping) or rendered_subject_verdict != render_subject_evidence_verdict(subject_verdict):
                return None
        except (KeyError, TypeError, ValueError):
            return None
    else:
        diagnostics = None
        grade = None
        verdict = None
    return {
        "status": status,
        "reason_code": result.get("reason_code"),
        "failure_code": result.get("failure_code"),
        "estimator_executed": result.get("estimator_executed") is True,
        "primary_result": (
            deepcopy(dict(result["primary_result"]))
            if isinstance(result.get("primary_result"), Mapping)
            else None
        ),
        "safe_detail": deepcopy(dict(safe_detail)),
        "runtime_fingerprint": (
            deepcopy(dict(runtime)) if isinstance(runtime, Mapping) else None
        ),
        "bundle_manifest_hash": bundle_manifest_hash,
        "verification_state": result.get("verification_state"),
        "post_publication_verified": result.get("post_publication_verified") is True,
        "diagnostics": deepcopy(diagnostics) if isinstance(diagnostics, list) else [],
        "diagnostic_summary": (
            deepcopy(dict(result["diagnostic_summary"]))
            if isinstance(result.get("diagnostic_summary"), Mapping)
            else None
        ),
        "robustness_grade": deepcopy(dict(grade)) if isinstance(grade, Mapping) else None,
        "evidence_verdict": deepcopy(dict(verdict)) if isinstance(verdict, Mapping) else None,
        "rendered_verdict": (
            deepcopy(dict(result["rendered_verdict"]))
            if isinstance(result.get("rendered_verdict"), Mapping)
            else None
        ),
        "subject_verdict": (
            deepcopy(dict(result["subject_verdict"]))
            if isinstance(result.get("subject_verdict"), Mapping)
            else None
        ),
        "rendered_subject_verdict": (
            deepcopy(dict(result["rendered_subject_verdict"]))
            if isinstance(result.get("rendered_subject_verdict"), Mapping)
            else None
        ),
        "reproduces_run_id": (
            result.get("reproduces_run_id")
            if isinstance(result.get("reproduces_run_id"), str)
            else None
        ),
        "run_relationship": (
            result.get("run_relationship")
            if result.get("run_relationship") in {"fresh", "reproduction", "refresh"}
            else "fresh"
        ),
        "refresh_of_request_id": (
            result.get("refresh_of_request_id")
            if isinstance(result.get("refresh_of_request_id"), str)
            else None
        ),
        "reproduction_comparison": (
            deepcopy(dict(result["reproduction_comparison"]))
            if isinstance(result.get("reproduction_comparison"), Mapping)
            else None
        ),
        "artifact_lifecycle": "sealed" if status in {"estimated", "abstained"} else None,
    }


def analysis_run_status(
    operation: Any,
    payload: Mapping[str, Any],
    execution_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = str(operation.state)
    result_status = execution_result.get("status") if execution_result else None
    artifact_lifecycle = (
        execution_result.get("artifact_lifecycle")
        if execution_result and isinstance(execution_result.get("artifact_lifecycle"), str)
        else None
    )
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
    elif state == "SUCCEEDED" and result_status == "estimated":
        status = "ESTIMATED"
        lifecycle = "sealed"
        outcome = "estimated"
        verification = "machine_verified"
        availability = "available"
        reason_code = None
    elif state == "SUCCEEDED" and result_status == "failed":
        status = "FAILED"
        lifecycle = (
            "quarantined" if artifact_lifecycle == "quarantined" else "failed"
        )
        outcome = "failed"
        verification = "invalid"
        availability = "suppressed"
        reason_code = execution_result.get("reason_code") or (
            "RUN_ARTIFACT_INTEGRITY_FAILED"
            if artifact_lifecycle == "quarantined"
            else "ENGINE_INTERNAL_ERROR"
        )
    elif state == "SUCCEEDED" and result_status == "abstained":
        status = "ABSTAINED"
        lifecycle = "sealed"
        outcome = "abstained"
        verification = "machine_verified"
        availability = "available"
        reason_code = (
            execution_result.get("reason_code")
            if execution_result and isinstance(execution_result.get("reason_code"), str)
            else "ENGINE_EXECUTION_DEFERRED"
        )
    elif state in {"INTERRUPTED", "TIMED_OUT"}:
        status = "FAILED"
        lifecycle = "quarantined"
        outcome = "failed"
        verification = "invalid"
        availability = "suppressed"
        reason_code = operation.failure_code or "RUN_EXECUTION_INTERRUPTED"
    elif state == "SUCCEEDED":
        status = "FAILED"
        lifecycle = "failed"
        outcome = "failed"
        verification = "invalid"
        availability = "suppressed"
        reason_code = "RUN_RESULT_UNAVAILABLE"
    else:
        status = "FAILED"
        lifecycle = "failed"
        outcome = "failed"
        verification = "invalid"
        availability = "suppressed"
        reason_code = operation.failure_code or "ENGINE_EXECUTION_FAILED"
    fresh_run_detail = (
        deepcopy(dict(execution_result["safe_detail"]))
        if execution_result and isinstance(execution_result.get("safe_detail"), Mapping)
        else _admission_safe_detail(payload)
    )
    execution_failure_code = (
        execution_result.get("failure_code")
        if execution_result and isinstance(execution_result.get("failure_code"), str)
        else None
    )
    estimator_descriptor = deepcopy(payload["estimator_descriptor"])
    if execution_result is not None:
        estimator_descriptor["estimator_executed"] = bool(
            execution_result.get("estimator_executed") is True
        )
        estimator_descriptor["estimator_stage"] = (
            "PRIMARY_ATTE_CONTEXT_AND_SENSITIVITIES"
            if execution_result.get("estimator_executed") is True
            else estimator_descriptor.get("estimator_stage")
        )
        estimator_descriptor["next_stage"] = (
            "DIAGNOSTICS"
            if result_status == "estimated"
            else estimator_descriptor.get("next_stage")
        )
    primary_result = (
        deepcopy(dict(execution_result["primary_result"]))
        if execution_result and isinstance(execution_result.get("primary_result"), Mapping)
        else None
    )
    final_evidence = execution_result if execution_result and result_status in {"estimated", "abstained"} else {}
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
        "run_relationship": (
            payload.get("run_relationship")
            if payload.get("run_relationship") in {"fresh", "reproduction", "refresh"}
            else "reproduction"
            if isinstance(payload.get("reproduces_run_id"), str)
            else "fresh"
        ),
        "reproduces_run_id": (
            payload.get("reproduces_run_id")
            if isinstance(payload.get("reproduces_run_id"), str)
            else None
        ),
        "refresh_of_request_id": (
            payload.get("refresh_of_request_id")
            if isinstance(payload.get("refresh_of_request_id"), str)
            else None
        ),
        "reason_code": reason_code,
        "failure_code": operation.failure_code or execution_failure_code,
        "recovery_action": (
            execution_result.get("recovery_action")
            if execution_result
            and isinstance(execution_result.get("recovery_action"), str)
            else operation.recovery_action
        ),
        "estimator_executed": bool(
            execution_result.get("estimator_executed") is True
            if execution_result
            else False
        ),
        "request_schema_version": payload["suite_request"]["engine_input_schema_version"],
        "scientific_request_digest": payload["scientific_request_digest"],
        "runtime_fingerprint": deepcopy(payload["runtime_fingerprint"]),
        "runtime_fingerprint_digest": payload["runtime_fingerprint_digest"],
        "root_seed": payload["suite_request"]["root_seed"],
        "derived_seed_registry": deepcopy(payload["derived_seed_registry"]),
        "estimator_descriptor": estimator_descriptor,
        "feature_descriptor": deepcopy(payload["feature_descriptor"]),
        "fold_descriptor": deepcopy(payload["fold_descriptor"]),
        "fresh_run_detail": fresh_run_detail,
        "primary_result": primary_result,
        "bundle_manifest_hash": (
            final_evidence.get("bundle_manifest_hash")
            if isinstance(final_evidence.get("bundle_manifest_hash"), str)
            else None
        ),
        "diagnostics": (
            deepcopy(final_evidence.get("diagnostics"))
            if isinstance(final_evidence.get("diagnostics"), list)
            else []
        ),
        "diagnostic_summary": (
            deepcopy(final_evidence.get("diagnostic_summary"))
            if isinstance(final_evidence.get("diagnostic_summary"), Mapping)
            else None
        ),
        "robustness_grade": (
            deepcopy(final_evidence.get("robustness_grade"))
            if isinstance(final_evidence.get("robustness_grade"), Mapping)
            else None
        ),
        "evidence_verdict": (
            deepcopy(final_evidence.get("evidence_verdict"))
            if isinstance(final_evidence.get("evidence_verdict"), Mapping)
            else None
        ),
        "rendered_verdict": (
            deepcopy(final_evidence.get("rendered_verdict"))
            if isinstance(final_evidence.get("rendered_verdict"), Mapping)
            else None
        ),
        "subject_verdict": (
            deepcopy(final_evidence.get("subject_verdict"))
            if isinstance(final_evidence.get("subject_verdict"), Mapping)
            else None
        ),
        "rendered_subject_verdict": (
            deepcopy(final_evidence.get("rendered_subject_verdict"))
            if isinstance(final_evidence.get("rendered_subject_verdict"), Mapping)
            else None
        ),
        "reproduction_comparison": (
            deepcopy(final_evidence.get("reproduction_comparison"))
            if isinstance(final_evidence.get("reproduction_comparison"), Mapping)
            else None
        ),
    }


def is_strict_fresh_analysis_request(request: Mapping[str, Any]) -> bool:
    return any(
        key in request
        for key in ("suite_request", "investigation_request_id", "root_seed")
    )
