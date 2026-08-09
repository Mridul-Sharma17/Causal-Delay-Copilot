from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import math
import unicodedata
from typing import Any, Callable

import numpy as np

from .canonical import canonical_json, sha256
from .diagnostics import (
    DIAGNOSTIC_POLICY_ID,
    DIAGNOSTIC_POLICY_VERSION,
    DIAGNOSTIC_SCOPE,
    _make_result,
)


REFUTER_BATTERY_SCHEMA_VERSION = "core-refuter-battery.v1"
REFUTER_SIMULATION_SCHEMA_VERSION = "refuter-simulation.v1"
NEGATIVE_CONTROL_ADAPTER_SCHEMA_VERSION = "negative-control-adapter-request.v1"
REFUTER_ADAPTER_ID = "exact-doubleml-dowhy-refuter-adapter"
REFUTER_ADAPTER_VERSION = "1"
EXACT_ESTIMATOR_ID = "DoubleMLIRM"
EXACT_ESTIMATOR_SCORE = "ATTE"
EXACT_ESTIMATOR_CLUSTER = "supplier_id"
EXACT_ESTIMATOR_INFERENCE = "supplier_clustered"
EXACT_ESTIMATOR_SECOND_OVERLAP_TRIM = False
EXACT_ESTIMATOR_LIBRARY = "DoubleML"
EXACT_ESTIMATOR_LIBRARY_VERSION = "0.11.3"
EXACT_ESTIMATOR_CONTRACT = {
    "estimator_id": EXACT_ESTIMATOR_ID,
    "score": EXACT_ESTIMATOR_SCORE,
    "cluster": EXACT_ESTIMATOR_CLUSTER,
    "inference": EXACT_ESTIMATOR_INFERENCE,
    "second_overlap_trim": EXACT_ESTIMATOR_SECOND_OVERLAP_TRIM,
}
EXACT_ESTIMATOR_RECEIPT_SCHEMA_VERSION = "exact-estimator-receipt.v1"
REFUTER_SEED_POLICY_ID = "sha256-refuter-coordinate-seeds"
REFUTER_SEED_POLICY_VERSION = "v1"
REFUTER_BATTERY_ID = "core-refuter-battery"
REFUTER_BATTERY_VERSION = "1"
REFUTER_SIMULATION_COUNT = 100
REFUTER_ALPHA = 0.05
REFUTER_RANDOM_COMMON_CAUSE_FEATURE = "refuter_random_common_cause"

_REFUTER_SEED_COMPONENTS = {
    "placebo_treatment_within_supplier": frozenset(
        {
            "outer_split",
            "inner_calibration_split",
            "propensity_learner",
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        }
    ),
    "random_common_cause_standard_normal": frozenset(
        {
            "propensity_learner",
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        }
    ),
    "data_subset_supplier_arm_80pct": frozenset(
        {
            "propensity_learner",
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        }
    ),
    "dummy_outcome_standard_normal": frozenset(
        {
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        }
    ),
}

PLACEBO_REFUTER_ID = "placebo_treatment_within_supplier"
RANDOM_COMMON_CAUSE_REFUTER_ID = "random_common_cause_standard_normal"
DATA_SUBSET_REFUTER_ID = "data_subset_supplier_arm_80pct"
DUMMY_OUTCOME_REFUTER_ID = "dummy_outcome_standard_normal"
REFUTER_DIAGNOSTIC_IDS = (
    PLACEBO_REFUTER_ID,
    RANDOM_COMMON_CAUSE_REFUTER_ID,
    DATA_SUBSET_REFUTER_ID,
    DUMMY_OUTCOME_REFUTER_ID,
)
REFUTER_IDS = REFUTER_DIAGNOSTIC_IDS

_REFUTER_CODE_PREFIX = {
    PLACEBO_REFUTER_ID: "PLACEBO_REFUTER",
    RANDOM_COMMON_CAUSE_REFUTER_ID: "RANDOM_COMMON_CAUSE_REFUTER",
    DATA_SUBSET_REFUTER_ID: "DATA_SUBSET_REFUTER",
    DUMMY_OUTCOME_REFUTER_ID: "DUMMY_OUTCOME_REFUTER",
}

NEGATIVE_CONTROL_DIAGNOSTIC_ID = "negative_control_outcome"
NEGATIVE_CONTROL_OUTCOME_DIAGNOSTIC_ID = NEGATIVE_CONTROL_DIAGNOSTIC_ID

REFUTER_ADAPTER_MATRIX: dict[str, dict[str, str]] = {
    PLACEBO_REFUTER_ID: {
        "outer_splits": "rebuild_stratified_supplier_grouped",
        "inner_splits": "rebuild_stratified_supplier_grouped",
        "propensity": "refit_and_recalibrate",
        "outcome_nuisances": "refit_both_arms",
    },
    RANDOM_COMMON_CAUSE_REFUTER_ID: {
        "outer_splits": "reuse_primary",
        "inner_splits": "reuse_primary",
        "propensity": "refit_and_recalibrate_augmented_features",
        "outcome_nuisances": "refit_both_arms_augmented_features",
    },
    DATA_SUBSET_REFUTER_ID: {
        "outer_splits": "restrict_primary",
        "inner_splits": "restrict_primary",
        "propensity": "refit_and_recalibrate_restricted_rows",
        "outcome_nuisances": "refit_both_arms_restricted_rows",
    },
    DUMMY_OUTCOME_REFUTER_ID: {
        "outer_splits": "reuse_primary",
        "inner_splits": "not_executed",
        "propensity": "reuse_primary_repeat_specific_predictions",
        "outcome_nuisances": "refit_both_arms_generated_outcome",
    },
}


class RefuterInputError(ValueError):
    """A refuter input is not a well-formed canonical estimator input."""


class NegativeControlSupportError(RefuterInputError):
    """A well-formed negative-control restriction lacks scientific support."""


@dataclass(frozen=True, slots=True)
class ExactEstimatorAdapter:
    """Registered seam for the authoritative DoubleML ATTE execution."""

    estimate_fn: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    adapter_id: str = REFUTER_ADAPTER_ID
    adapter_version: str = REFUTER_ADAPTER_VERSION
    estimator_id: str = EXACT_ESTIMATOR_ID
    score: str = EXACT_ESTIMATOR_SCORE
    cluster: str = EXACT_ESTIMATOR_CLUSTER
    inference: str = EXACT_ESTIMATOR_INFERENCE
    second_overlap_trim: bool = EXACT_ESTIMATOR_SECOND_OVERLAP_TRIM
    support_state: str = "configured"

    def estimate(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.estimate_fn(request)


@dataclass(frozen=True, slots=True)
class _RowContract:
    rows: list[dict[str, Any]]
    row_id_key: str
    supplier_key: str
    exposure_key: str
    outcome_key: str
    features_key: str


def _plain(value: object) -> object:
    if isinstance(value, np.generic):
        return _plain(value.item())
    if isinstance(value, np.ndarray):
        return [_plain(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _scientific_value(value: object) -> object:
    value = _plain(value)
    if isinstance(value, Mapping):
        return {
            unicodedata.normalize("NFC", str(key)): _scientific_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scientific_value(item) for item in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RefuterInputError("scientific content contains a non-finite number")
        if value == 0.0:
            value = 0.0
        return f"f64:{value.hex().lower()}"
    raise RefuterInputError("scientific content contains an unsupported value")


def _scientific_sha256(value: object) -> str:
    return sha256(canonical_json(_scientific_value(value)))


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float, np.integer, np.floating))
        and not isinstance(value, (bool, np.bool_))
        and math.isfinite(float(value))
    )


def _number(value: object) -> float | None:
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(
        value, (bool, np.bool_)
    ):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    if isinstance(value, Mapping) and value.get("state") == "present":
        return _number(value.get("value"))
    return None


def _required_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RefuterInputError(f"{label} is unavailable")
    return value


def _resolve_field(
    rows: Sequence[Mapping[str, Any]],
    candidates: Sequence[str],
    label: str,
    *,
    allow_missing: bool = False,
) -> str:
    selected = next((candidate for candidate in candidates if any(candidate in row for row in rows)), None)
    if selected is None:
        raise RefuterInputError(f"{label} is unavailable")
    if not allow_missing and any(selected not in row for row in rows):
        raise RefuterInputError(f"{label} is not present on every estimator row")
    return selected


def _normalise_exposure(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value in (0, 1):
        return bool(value)
    raise RefuterInputError("exposure is not binary")


def _prepare_rows(rows: Sequence[Mapping[str, Any]]) -> _RowContract:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise RefuterInputError("canonical estimator rows are unavailable")
    copied: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise RefuterInputError("canonical estimator row is not an object")
        copied.append(deepcopy(dict(row)))

    row_id_key = _resolve_field(copied, ("order_line_id", "row_id", "id"), "row identity")
    supplier_key = _resolve_field(copied, ("supplier_id", "supplier"), "supplier identity")
    exposure_key = _resolve_field(
        copied,
        ("high_load_exposure", "exposure", "treatment"),
        "exposure",
    )
    outcome_key = _resolve_field(
        copied,
        (
            "supplier_milestone_slippage_days",
            "outcome",
            "slippage_days",
        ),
        "continuous outcome",
    )
    features_key = next(
        (
            candidate
            for candidate in ("covariates", "features", "adjustment_features")
            if any(candidate in row for row in copied)
        ),
        "covariates",
    )

    for row in copied:
        row_id = _required_identifier(row.get(row_id_key), "row identity")
        _required_identifier(row.get(supplier_key), "supplier identity")
        row[exposure_key] = _normalise_exposure(row.get(exposure_key))
        if _number(row.get(outcome_key)) is None:
            raise RefuterInputError("continuous outcome is not finite")
        if features_key in row and not isinstance(row[features_key], Mapping):
            raise RefuterInputError("covariates are not an object")
        row[row_id_key] = row_id

    row_ids = [str(row[row_id_key]) for row in copied]
    if len(set(row_ids)) != len(row_ids):
        raise RefuterInputError("canonical row identities are duplicated")
    return _RowContract(
        rows=copied,
        row_id_key=row_id_key,
        supplier_key=supplier_key,
        exposure_key=exposure_key,
        outcome_key=outcome_key,
        features_key=features_key,
    )


def _rng(seed: int) -> np.random.Generator:
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise RefuterInputError("simulation root seed is invalid")
    seed_value = int(seed)
    if seed_value < 0 or seed_value >= 2**64:
        raise RefuterInputError("simulation root seed is outside uint64")
    return np.random.default_rng(seed_value)


def _supplier_positions(contract: _RowContract) -> tuple[list[str], dict[str, list[int]]]:
    order: list[str] = []
    positions: dict[str, list[int]] = {}
    for index, row in enumerate(contract.rows):
        supplier = str(row[contract.supplier_key])
        if supplier not in positions:
            order.append(supplier)
            positions[supplier] = []
        positions[supplier].append(index)
    return order, positions


def apply_refuter_transformation(
    refuter_id: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    simulation_root_seed: int,
) -> dict[str, Any]:
    """Apply one registered transformation to rows already in canonical S9 order."""

    if refuter_id not in REFUTER_DIAGNOSTIC_IDS:
        raise RefuterInputError("refuter is not registered")
    contract = _prepare_rows(rows)
    generator = _rng(simulation_root_seed)
    transformed = deepcopy(contract.rows)
    supplier_order, supplier_positions = _supplier_positions(contract)
    metadata: dict[str, Any] = {
        "refuter_id": refuter_id,
        "simulation_root_seed": int(simulation_root_seed),
        "row_count_before": len(contract.rows),
        "row_count_after": len(contract.rows),
        "retained_row_indices": list(range(len(contract.rows))),
        "supplier_order": supplier_order,
    }

    if refuter_id == PLACEBO_REFUTER_ID:
        for supplier in supplier_order:
            positions = supplier_positions[supplier]
            exposures = [contract.rows[index][contract.exposure_key] for index in positions]
            if len(set(exposures)) == 1:
                continue
            permutation = generator.permutation(np.asarray(exposures, dtype=np.bool_))
            for index, exposure in zip(positions, permutation, strict=True):
                transformed[index][contract.exposure_key] = bool(exposure)
        metadata["transformation"] = "permute_exposure_within_supplier"

    elif refuter_id == RANDOM_COMMON_CAUSE_REFUTER_ID:
        generated = generator.normal(0.0, 1.0, size=len(transformed))
        for row, value in zip(transformed, generated, strict=True):
            features = dict(row.get(contract.features_key, {}))
            if REFUTER_RANDOM_COMMON_CAUSE_FEATURE in features:
                raise RefuterInputError("refuter feature already exists")
            features[REFUTER_RANDOM_COMMON_CAUSE_FEATURE] = float(value)
            row[contract.features_key] = features
        metadata["transformation"] = "append_standard_normal_feature"
        metadata["generated_feature"] = REFUTER_RANDOM_COMMON_CAUSE_FEATURE

    elif refuter_id == DATA_SUBSET_REFUTER_ID:
        selected: set[int] = set()
        stratum_counts: list[dict[str, Any]] = []
        for supplier in supplier_order:
            positions = supplier_positions[supplier]
            for arm in (False, True):
                stratum = [
                    index
                    for index in positions
                    if bool(contract.rows[index][contract.exposure_key]) is arm
                ]
                take = math.ceil(0.80 * len(stratum))
                if take == len(stratum):
                    chosen = stratum
                else:
                    chosen = [
                        int(index)
                        for index in generator.choice(
                            np.asarray(stratum, dtype=np.int64),
                            size=take,
                            replace=False,
                        )
                    ]
                selected.update(chosen)
                stratum_counts.append(
                    {
                        "supplier_id": supplier,
                        "exposure": int(arm),
                        "original_count": len(stratum),
                        "retained_count": len(chosen),
                    }
                )
        retained_indices = sorted(selected)
        transformed = [transformed[index] for index in retained_indices]
        metadata["transformation"] = "sample_supplier_exposure_strata_without_replacement"
        metadata["retained_row_indices"] = retained_indices
        metadata["row_count_after"] = len(transformed)
        metadata["stratum_counts"] = stratum_counts

    else:
        generated = generator.normal(0.0, 1.0, size=len(transformed))
        for row, value in zip(transformed, generated, strict=True):
            row[contract.outcome_key] = float(value)
        metadata["transformation"] = "replace_outcome_with_standard_normal"

    return {
        "schema_version": "refuter-transformation.v1",
        **metadata,
        "rows": transformed,
        "transformed_input_digest": _scientific_sha256(
            {"refuter_id": refuter_id, "rows": transformed}
        ),
    }


def transform_placebo_treatment_within_supplier(
    rows: Sequence[Mapping[str, Any]], *, simulation_root_seed: int
) -> list[dict[str, Any]]:
    return apply_refuter_transformation(
        PLACEBO_REFUTER_ID,
        rows,
        simulation_root_seed=simulation_root_seed,
    )["rows"]


def transform_random_common_cause_standard_normal(
    rows: Sequence[Mapping[str, Any]], *, simulation_root_seed: int
) -> list[dict[str, Any]]:
    return apply_refuter_transformation(
        RANDOM_COMMON_CAUSE_REFUTER_ID,
        rows,
        simulation_root_seed=simulation_root_seed,
    )["rows"]


def transform_data_subset_supplier_arm_80pct(
    rows: Sequence[Mapping[str, Any]], *, simulation_root_seed: int
) -> list[dict[str, Any]]:
    return apply_refuter_transformation(
        DATA_SUBSET_REFUTER_ID,
        rows,
        simulation_root_seed=simulation_root_seed,
    )["rows"]


def transform_dummy_outcome_standard_normal(
    rows: Sequence[Mapping[str, Any]], *, simulation_root_seed: int
) -> list[dict[str, Any]]:
    return apply_refuter_transformation(
        DUMMY_OUTCOME_REFUTER_ID,
        rows,
        simulation_root_seed=simulation_root_seed,
    )["rows"]


def evaluate_refuter_statistics(
    estimates: Sequence[float],
    *,
    reference_target: float,
    primary_atte_standard_error: float,
) -> dict[str, Any]:
    """Apply the locked DoWhy-compatible percentile and median rules."""

    if len(estimates) != REFUTER_SIMULATION_COUNT:
        raise RefuterInputError("refuter estimates do not have 100 simulations")
    target = _number(reference_target)
    standard_error = _number(primary_atte_standard_error)
    if target is None or standard_error is None or standard_error < 0.0:
        raise RefuterInputError("refuter statistic target or standard error is invalid")
    values = [
        _number(value)
        for value in estimates
    ]
    if any(value is None for value in values):
        raise RefuterInputError("refuter estimates contain a non-finite value")
    finite_values = [float(value) for value in values if value is not None]
    greater_count = sum(value > target for value in finite_values)
    equality_count = sum(value == target for value in finite_values)
    half_p = (greater_count + 0.5 * equality_count) / REFUTER_SIMULATION_COUNT
    p_value = 2.0 * min(half_p, 1.0 - half_p)
    ordered = sorted(finite_values)
    median = (ordered[49] + ordered[50]) / 2.0
    median_shift = abs(median - target)
    return {
        "reference_target": target,
        "primary_atte_standard_error": standard_error,
        "greater_count": greater_count,
        "equality_count": equality_count,
        "p_value_denominator": REFUTER_SIMULATION_COUNT,
        "half_p": half_p,
        "p_value": p_value,
        "median_simulation_estimate": median,
        "median_shift": median_shift,
        "median_shift_tolerance": standard_error,
        "passed": p_value > REFUTER_ALPHA and median_shift <= standard_error,
    }


def _refuter_threshold(refuter_id: str) -> dict[str, Any]:
    reference_target: object = (
        0.0
        if refuter_id in {PLACEBO_REFUTER_ID, DUMMY_OUTCOME_REFUTER_ID}
        else "primary_atte_estimate"
    )
    return {
        "simulation_count": REFUTER_SIMULATION_COUNT,
        "alpha": REFUTER_ALPHA,
        "p_value_rule": "two_sided_percentile_bootstrap_strict_greater_half_equal",
        "p_value_inclusive": False,
        "median_rule": "sorted_zero_based_indices_49_50_arithmetic_mean",
        "median_shift_rule": "absolute_shift_at_most_primary_atte_standard_error",
        "reference_target": reference_target,
        "n_jobs": 1,
        "seed_policy_id": REFUTER_SEED_POLICY_ID,
        "seed_policy_version": REFUTER_SEED_POLICY_VERSION,
    }


def _refuter_code(refuter_id: str, suffix: str) -> str:
    return f"{_REFUTER_CODE_PREFIX[refuter_id]}_{suffix}"


def _refuter_result(
    refuter_id: str,
    *,
    status: str,
    threshold: Mapping[str, Any],
    observed: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
    reason_code: str,
    reason: str,
    trigger_codes: Sequence[str] = (),
    upstream_trigger: str | None = None,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    return _make_result(
        refuter_id,
        rule_id=f"{refuter_id}.v1",
        status=status,
        scope=DIAGNOSTIC_SCOPE,
        observed=observed,
        threshold=threshold,
        result=result,
        verdict_effect="VETO" if status in {"FAIL", "UNSUPPORTED"} else "NONE",
        trigger_codes=trigger_codes,
        reason_code=reason_code,
        reason=reason,
        upstream_trigger=upstream_trigger,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
        policy_id=policy_id,
        policy_version=policy_version,
    )


def _refuter_observed(
    *,
    valid_count: int,
    unsupported_count: int,
    failed_count: int,
    unavailable_count: int = 0,
    not_run_count: int = 0,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "simulation_count": REFUTER_SIMULATION_COUNT,
        "valid_simulation_count": valid_count,
        "unsupported_simulation_count": unsupported_count,
        "failed_simulation_count": failed_count,
        "unavailable_simulation_count": unavailable_count,
        "not_run_simulation_count": not_run_count,
        **extra,
    }


def _resolve_seed_context(
    *,
    seed_context: Mapping[str, Any] | None,
    root_seed: int | None,
    dataset_version_id: str | None,
    causal_question_id: str | None,
    causal_question_version: str | None,
    engine_config_id: str | None,
    engine_config_version: str | None,
    suite_id: str | None,
    suite_version: str | None,
    validity_policy_id: str,
    validity_policy_version: str,
) -> dict[str, Any]:
    context = dict(seed_context or {})
    explicit = {
        "root_seed": root_seed,
        "dataset_version_id": dataset_version_id,
        "causal_question_id": causal_question_id,
        "causal_question_version": causal_question_version,
        "engine_config_id": engine_config_id,
        "engine_config_version": engine_config_version,
        "suite_id": suite_id,
        "suite_version": suite_version,
        "validity_policy_id": validity_policy_id,
        "validity_policy_version": validity_policy_version,
    }
    context.update({key: value for key, value in explicit.items() if value is not None})
    required = (
        "root_seed",
        "dataset_version_id",
        "causal_question_id",
        "causal_question_version",
        "engine_config_id",
        "engine_config_version",
        "suite_id",
        "suite_version",
        "validity_policy_id",
        "validity_policy_version",
    )
    if any(key not in context for key in required):
        raise RefuterInputError("refuter seed context is incomplete")
    if (
        isinstance(context["root_seed"], bool)
        or not isinstance(context["root_seed"], int)
        or context["root_seed"] < 0
        or context["root_seed"] >= 2**64
    ):
        raise RefuterInputError("root seed is outside uint64")
    for key in required[1:]:
        _required_identifier(context[key], key)
    return context


def _adapter_call(
    estimator_adapter: object,
    request: dict[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(estimator_adapter, ExactEstimatorAdapter):
        raise RefuterInputError("registered exact estimator adapter is required")
    if (
        estimator_adapter.adapter_id != REFUTER_ADAPTER_ID
        or estimator_adapter.adapter_version != REFUTER_ADAPTER_VERSION
        or estimator_adapter.estimator_id != EXACT_ESTIMATOR_ID
        or estimator_adapter.score != EXACT_ESTIMATOR_SCORE
        or estimator_adapter.cluster != EXACT_ESTIMATOR_CLUSTER
        or estimator_adapter.inference != EXACT_ESTIMATOR_INFERENCE
        or estimator_adapter.second_overlap_trim != EXACT_ESTIMATOR_SECOND_OVERLAP_TRIM
    ):
        raise RefuterInputError("exact estimator adapter identity is unsupported")
    if request.get("estimator_contract") != EXACT_ESTIMATOR_CONTRACT:
        raise RefuterInputError("exact estimator contract is unsupported")
    response = estimator_adapter.estimate(request)
    if not isinstance(response, Mapping):
        raise RefuterInputError("exact estimator adapter returned a non-object")
    return response


def _validate_exact_estimator_receipt(
    response: Mapping[str, Any], request: Mapping[str, Any]
) -> None:
    receipt = response.get("estimator_receipt")
    if not isinstance(receipt, Mapping):
        raise RefuterInputError("exact estimator execution receipt is unavailable")
    expected = {
        "schema_version": EXACT_ESTIMATOR_RECEIPT_SCHEMA_VERSION,
        "adapter_id": REFUTER_ADAPTER_ID,
        "adapter_version": REFUTER_ADAPTER_VERSION,
        "estimator_library": EXACT_ESTIMATOR_LIBRARY,
        "estimator_library_version": EXACT_ESTIMATOR_LIBRARY_VERSION,
        "estimator_contract": EXACT_ESTIMATOR_CONTRACT,
        "n_jobs_cv": 1,
        "execution_status": "complete",
        "second_overlap_trim": EXACT_ESTIMATOR_SECOND_OVERLAP_TRIM,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise RefuterInputError("exact estimator execution receipt is invalid")
    if receipt.get("adapter_matrix") != request.get("adapter_matrix"):
        raise RefuterInputError("exact estimator adapter matrix receipt is invalid")


def _validate_downstream_seed_records(
    response: Mapping[str, Any], request: Mapping[str, Any]
) -> None:
    records = response.get("seed_records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise RefuterInputError("exact estimator downstream seed coordinates are unavailable")
    refuter_id = request.get("refuter_id")
    if not isinstance(refuter_id, str) or refuter_id not in _REFUTER_SEED_COMPONENTS:
        raise RefuterInputError("exact estimator refuter seed context is invalid")
    seen: set[tuple[str, int, int | None, int | None]] = set()
    allowed_components = _REFUTER_SEED_COMPONENTS[refuter_id]
    for record in records:
        if not isinstance(record, Mapping):
            raise RefuterInputError("exact estimator downstream seed coordinate is malformed")
        component = record.get("component")
        if not isinstance(component, str) or component not in allowed_components:
            raise RefuterInputError("exact estimator downstream seed component is invalid")
        seed = record.get("seed")
        if (
            isinstance(seed, bool)
            or not isinstance(seed, (int, np.integer))
            or seed < 0
            or seed >= 2**32
        ):
            raise RefuterInputError("exact estimator downstream seed is invalid")
        coordinates = record.get("coordinates")
        if not isinstance(coordinates, Mapping):
            raise RefuterInputError("exact estimator seed coordinates are unavailable")
        if set(coordinates) != {
            "variant_id",
            "repeat_index",
            "outer_fold_index",
            "inner_fold_index",
        }:
            raise RefuterInputError("exact estimator seed coordinate shape is invalid")
        if coordinates.get("variant_id") != refuter_id:
            raise RefuterInputError("exact estimator seed variant is invalid")
        repeat_index = coordinates.get("repeat_index")
        outer_fold_index = coordinates.get("outer_fold_index")
        inner_fold_index = coordinates.get("inner_fold_index")
        if (
            not isinstance(repeat_index, int)
            or isinstance(repeat_index, bool)
            or repeat_index not in {0, 1}
            or inner_fold_index is not None
            or (
                outer_fold_index is not None
                and (
                    not isinstance(outer_fold_index, int)
                    or isinstance(outer_fold_index, bool)
                    or outer_fold_index < 0
                )
            )
        ):
            raise RefuterInputError("exact estimator seed coordinate values are invalid")
        if component == "outer_split" and outer_fold_index is not None:
            raise RefuterInputError("outer split seed coordinate is invalid")
        if component != "outer_split" and outer_fold_index is None:
            raise RefuterInputError("learner seed coordinate is incomplete")
        coordinate_key = (component, repeat_index, outer_fold_index, inner_fold_index)
        if coordinate_key in seen:
            raise RefuterInputError("exact estimator seed coordinate is duplicated")
        seen.add(coordinate_key)
    expected_coordinates = {
        (
            component,
            repeat_index,
            outer_fold_index,
            None,
        )
        for component in allowed_components
        for repeat_index in (0, 1)
        for outer_fold_index in (
            (None,) if component == "outer_split" else (0, 1, 2, 3, 4)
        )
    }
    if seen != expected_coordinates:
        raise RefuterInputError("exact estimator downstream seed coordinate matrix is incomplete")


def _validate_scientific_unsupported_response(response: Mapping[str, Any]) -> None:
    support_failure = response.get("support_failure")
    if not isinstance(support_failure, Mapping):
        raise RefuterInputError("scientific unsupported support evidence is unavailable")
    if support_failure.get("state") != "unsupported":
        raise RefuterInputError("scientific unsupported support evidence is invalid")
    if not isinstance(support_failure.get("invariant"), str) or not support_failure["invariant"]:
        raise RefuterInputError("scientific unsupported invariant is unavailable")


def _adapter_status(response: Mapping[str, Any]) -> str:
    raw = response.get("status", "estimated")
    if not isinstance(raw, str):
        raise RefuterInputError("estimator adapter status is invalid")
    return raw.upper()


def _effect_mapping(response: Mapping[str, Any]) -> Mapping[str, Any]:
    effect = response.get("effect", response.get("primary_effect", response))
    if not isinstance(effect, Mapping):
        raise RefuterInputError("estimator adapter effect is invalid")
    if _number(effect.get("estimate", effect.get("effect"))) is None:
        raise RefuterInputError("estimator adapter effect estimate is invalid")
    return effect


def _adapter_result_status(status: str) -> str:
    if status in {"UNSUPPORTED", "SCIENTIFICALLY_UNSUPPORTED"}:
        return "UNSUPPORTED"
    if status in {"UNAVAILABLE"}:
        return "UNAVAILABLE"
    if status in {"NOT_RUN"}:
        return "NOT_RUN"
    if status in {"FAILED", "FAILURE", "ERROR"}:
        return "FAILED"
    if status not in {"ESTIMATED", "VALID", "PASS", ""}:
        return "FAILED"
    return "VALID"


def _simulation_record(
    *,
    refuter_id: str,
    simulation_index: int,
    coordinate_ordinal: int,
    simulation_root_seed: int,
    transformed_input_digest: str,
    adapter_request_digest: str,
    status: str,
    effect: Mapping[str, Any] | None = None,
    response: Mapping[str, Any] | None = None,
    reason_code: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": REFUTER_SIMULATION_SCHEMA_VERSION,
        "refuter_id": refuter_id,
        "simulation_index": simulation_index,
        "coordinate_ordinal": coordinate_ordinal,
        "simulation_root_seed": simulation_root_seed,
        "transformed_input_digest": transformed_input_digest,
        "adapter_request_digest": adapter_request_digest,
        "status": status,
    }
    if effect is not None:
        record["effect"] = _plain(dict(effect))
    if response is not None and "seed_records" in response:
        record["downstream_seed_records"] = _plain(response["seed_records"])
    if reason_code is not None:
        record["reason_code"] = reason_code
    if reason is not None:
        record["reason"] = reason
    record["content_hash"] = _scientific_sha256(record)
    return record


def _base_material(
    context: Mapping[str, Any],
    *,
    refuter_adapter_id: str,
    refuter_adapter_version: str,
) -> dict[str, Any]:
    if (
        refuter_adapter_id != REFUTER_ADAPTER_ID
        or refuter_adapter_version != REFUTER_ADAPTER_VERSION
    ):
        raise RefuterInputError("refuter adapter identity is unsupported")
    return {
        "root_seed": context["root_seed"],
        "dataset_version_id": context["dataset_version_id"],
        "causal_question_id": context["causal_question_id"],
        "causal_question_version": context["causal_question_version"],
        "engine_config_id": context["engine_config_id"],
        "engine_config_version": context["engine_config_version"],
        "suite_id": context["suite_id"],
        "suite_version": context["suite_version"],
        "validity_policy_id": context["validity_policy_id"],
        "validity_policy_version": context["validity_policy_version"],
        "refuter_adapter_id": refuter_adapter_id,
        "refuter_adapter_version": refuter_adapter_version,
        "battery_id": REFUTER_BATTERY_ID,
        "battery_version": REFUTER_BATTERY_VERSION,
    }


def _empty_refuter_diagnostic(
    refuter_id: str,
    *,
    status: str,
    reason_code: str,
    reason: str,
    upstream_trigger: str | None = None,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
) -> dict[str, Any]:
    not_run = status == "NOT_RUN"
    return _refuter_result(
        refuter_id,
        status=status,
        threshold=_refuter_threshold(refuter_id),
        observed=None if not_run else _refuter_observed(
            valid_count=0,
            unsupported_count=0,
            failed_count=0,
            not_run_count=REFUTER_SIMULATION_COUNT if status == "NOT_RUN" else 0,
        ),
        result=None,
        reason_code=reason_code,
        reason=reason,
        upstream_trigger=upstream_trigger,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
    )


def _battery_without_seed_context(
    diagnostics: Sequence[Mapping[str, Any]],
    *,
    refuter_adapter_id: str,
    refuter_adapter_version: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": REFUTER_BATTERY_SCHEMA_VERSION,
        "battery_id": REFUTER_BATTERY_ID,
        "battery_version": REFUTER_BATTERY_VERSION,
        "refuter_adapter_id": refuter_adapter_id,
        "refuter_adapter_version": refuter_adapter_version,
        "seed_policy_id": REFUTER_SEED_POLICY_ID,
        "seed_policy_version": REFUTER_SEED_POLICY_VERSION,
        "base_material": None,
        "base_digest": None,
        "simulation_count_per_refuter": REFUTER_SIMULATION_COUNT,
        "coordinates": [],
        "diagnostics": [dict(item) for item in diagnostics],
    }
    payload["content_hash"] = _scientific_sha256(payload)
    return payload


def _refuter_artifacts_are_available(primary_artifacts: Mapping[str, Any] | None) -> bool:
    if not isinstance(primary_artifacts, Mapping):
        return False
    for key in ("outer_splits", "inner_splits", "propensity_predictions"):
        value = primary_artifacts.get(key)
        if value is None or (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and not value
        ) or (isinstance(value, Mapping) and not value):
            return False
    canonical_row_ids = primary_artifacts.get("canonical_row_ids")
    if (
        not isinstance(canonical_row_ids, Sequence)
        or isinstance(canonical_row_ids, (str, bytes))
        or not canonical_row_ids
        or any(not isinstance(row_id, str) or not row_id for row_id in canonical_row_ids)
    ):
        return False
    return (
        primary_artifacts.get("fold_provenance_verified") is True
        and primary_artifacts.get("propensity_provenance_verified") is True
        and isinstance(primary_artifacts.get("propensity_provenance_ref"), str)
        and bool(primary_artifacts["propensity_provenance_ref"])
    )


def _canonical_row_order_matches(
    canonical_rows: Sequence[Mapping[str, Any]],
    row_id_key: str,
    primary_artifacts: Mapping[str, Any],
) -> bool:
    return list(primary_artifacts["canonical_row_ids"]) == [
        str(row[row_id_key]) for row in canonical_rows
    ]


def _execute_refuter(
    refuter_id: str,
    *,
    canonical_rows: Sequence[Mapping[str, Any]],
    primary_effect: Mapping[str, Any],
    estimator_adapter: object,
    base: Mapping[str, Any],
    base_digest: str,
    primary_artifacts: Mapping[str, Any] | None,
    analysis_run_id: str | None,
    bundle_manifest_hash: str | None,
    evidence_refs: Sequence[str],
    input_refs: Sequence[str],
) -> dict[str, Any]:
    threshold = _refuter_threshold(refuter_id)
    primary_estimate = _number(primary_effect.get("estimate", primary_effect.get("effect")))
    primary_standard_error = _number(
        primary_effect.get(
            "standard_error",
            primary_effect.get("std_error", primary_effect.get("se")),
        )
    )
    if primary_estimate is None or primary_standard_error is None or primary_standard_error < 0:
        return _empty_refuter_diagnostic(
            refuter_id,
            status="UNAVAILABLE",
            reason_code="PRIMARY_ATTE_STANDARD_ERROR_UNAVAILABLE",
            reason="The primary ATTE estimate or standard error is unavailable for refuter evaluation.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    reference_target = (
        0.0
        if refuter_id in {PLACEBO_REFUTER_ID, DUMMY_OUTCOME_REFUTER_ID}
        else primary_estimate
    )
    records: list[dict[str, Any]] = []
    for simulation_index in range(REFUTER_SIMULATION_COUNT):
        coordinate_ordinal = REFUTER_DIAGNOSTIC_IDS.index(refuter_id) * REFUTER_SIMULATION_COUNT + simulation_index
        base_bytes = bytes.fromhex(base_digest.split(":", 1)[1])
        base_value = int.from_bytes(base_bytes[:8], byteorder="big", signed=False)
        simulation_root_seed = (base_value + coordinate_ordinal) % 2**64
        try:
            transformed = apply_refuter_transformation(
                refuter_id,
                canonical_rows,
                simulation_root_seed=simulation_root_seed,
            )
            request: dict[str, Any] = {
                "schema_version": "exact-refuter-adapter-request.v1",
                "refuter_id": refuter_id,
                "refuter_index": REFUTER_DIAGNOSTIC_IDS.index(refuter_id),
                "simulation_index": simulation_index,
                "coordinate_ordinal": coordinate_ordinal,
                "simulation_root_seed": simulation_root_seed,
                "root_seed": simulation_root_seed,
                "refuter_adapter_id": base["refuter_adapter_id"],
                "refuter_adapter_version": base["refuter_adapter_version"],
                "reference_target": reference_target,
                "primary_atte_standard_error": primary_standard_error,
                "rows": transformed["rows"],
                "transformed_rows": transformed["rows"],
                "transformed_input_digest": transformed["transformed_input_digest"],
                "transformation": transformed["transformation"],
                "retained_row_indices": transformed["retained_row_indices"],
                "adapter_matrix": REFUTER_ADAPTER_MATRIX[refuter_id],
                "estimator_contract": dict(EXACT_ESTIMATOR_CONTRACT),
                "seed_policy": {
                    "policy_id": REFUTER_SEED_POLICY_ID,
                    "policy_version": REFUTER_SEED_POLICY_VERSION,
                    "downstream_root_seed": simulation_root_seed,
                },
                "primary_artifacts": deepcopy(dict(primary_artifacts or {})),
            }
            request_digest = _scientific_sha256(request)
            response = _adapter_call(estimator_adapter, request)
            response_status = _adapter_result_status(_adapter_status(response))
            if response_status == "VALID":
                _validate_exact_estimator_receipt(response, request)
                _validate_downstream_seed_records(response, request)
                effect = _effect_mapping(response)
                record = _simulation_record(
                    refuter_id=refuter_id,
                    simulation_index=simulation_index,
                    coordinate_ordinal=coordinate_ordinal,
                    simulation_root_seed=simulation_root_seed,
                    transformed_input_digest=str(transformed["transformed_input_digest"]),
                    adapter_request_digest=request_digest,
                    status="VALID",
                    effect=effect,
                    response=response,
                )
            else:
                if response_status == "UNSUPPORTED":
                    _validate_scientific_unsupported_response(response)
                default_reason_code = (
                    _refuter_code(refuter_id, "UNSUPPORTED")
                    if response_status == "UNSUPPORTED"
                    else "REFUTER_ESTIMATOR_EXECUTION_FAILED"
                )
                reason_code = str(
                    response.get(
                        "reason_code",
                        default_reason_code,
                    )
                )
                reason = str(
                    response.get(
                        "reason",
                        "The exact refuter adapter did not produce a supported effect result.",
                    )
                )
                record = _simulation_record(
                    refuter_id=refuter_id,
                    simulation_index=simulation_index,
                    coordinate_ordinal=coordinate_ordinal,
                    simulation_root_seed=simulation_root_seed,
                    transformed_input_digest=str(transformed["transformed_input_digest"]),
                    adapter_request_digest=request_digest,
                    status=response_status,
                    response=response,
                    reason_code=reason_code,
                    reason=reason,
                )
        except Exception:
            transformed_digest = "sha256:" + "0" * 64
            request_digest = "sha256:" + "0" * 64
            record = _simulation_record(
                refuter_id=refuter_id,
                simulation_index=simulation_index,
                coordinate_ordinal=coordinate_ordinal,
                simulation_root_seed=simulation_root_seed,
                transformed_input_digest=transformed_digest,
                adapter_request_digest=request_digest,
                status="FAILED",
                reason_code="REFUTER_ESTIMATOR_EXECUTION_FAILED",
                reason="The exact refuter transformation or estimator execution failed.",
            )
        records.append(record)

    valid_records = [record for record in records if record["status"] == "VALID"]
    unsupported_count = sum(record["status"] == "UNSUPPORTED" for record in records)
    failed_count = sum(record["status"] == "FAILED" for record in records)
    unavailable_count = sum(record["status"] == "UNAVAILABLE" for record in records)
    not_run_count = sum(record["status"] == "NOT_RUN" for record in records)
    observed = _refuter_observed(
        valid_count=len(valid_records),
        unsupported_count=unsupported_count,
        failed_count=failed_count,
        unavailable_count=unavailable_count,
        not_run_count=not_run_count,
    )
    if failed_count:
        return _refuter_result(
            refuter_id,
            status="FAILED",
            threshold=threshold,
            observed=observed,
            result={"base_material": dict(base), "base_digest": base_digest, "simulation_records": records},
            reason_code="REFUTER_EXECUTION_FAILED",
            reason="At least one exact refuter simulation failed during transformation or estimation.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    if unsupported_count:
        return _refuter_result(
            refuter_id,
            status="UNSUPPORTED",
            threshold=threshold,
            observed=observed,
            result={"base_material": dict(base), "base_digest": base_digest, "simulation_records": records},
            reason_code=_refuter_code(refuter_id, "UNSUPPORTED"),
            reason="At least one transformed simulation lacks the exact estimator support required by the refuter adapter.",
            trigger_codes=[_refuter_code(refuter_id, "UNSUPPORTED")],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    if unavailable_count:
        return _refuter_result(
            refuter_id,
            status="UNAVAILABLE",
            threshold=threshold,
            observed=observed,
            result={"base_material": dict(base), "base_digest": base_digest, "simulation_records": records},
            reason_code="REFUTER_RESULT_UNAVAILABLE",
            reason="The exact refuter adapter did not make every required simulation result available.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    if not_run_count == len(records) and not_run_count == REFUTER_SIMULATION_COUNT:
        return _refuter_result(
            refuter_id,
            status="NOT_RUN",
            threshold=threshold,
            observed=None,
            result=None,
            reason_code="REFUTER_NOT_RUN",
            reason="The exact refuter adapter did not execute any required simulation.",
            upstream_trigger="REFUTER_ADAPTER_NOT_RUN",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    if not_run_count or len(valid_records) != REFUTER_SIMULATION_COUNT:
        return _refuter_result(
            refuter_id,
            status="FAILED",
            threshold=threshold,
            observed=observed,
            result={"base_material": dict(base), "base_digest": base_digest, "simulation_records": records},
            reason_code="REFUTER_SIMULATION_DENOMINATOR_INVALID",
            reason="The refuter did not produce exactly 100 valid simulation records.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )

    estimates = [
        float(record["effect"]["estimate"])
        for record in valid_records
    ]
    statistics = evaluate_refuter_statistics(
        estimates,
        reference_target=reference_target,
        primary_atte_standard_error=primary_standard_error,
    )
    observed.update(statistics)
    passed = bool(statistics["passed"])
    return _refuter_result(
        refuter_id,
        status="PASS" if passed else "FAIL",
        threshold=threshold,
        observed=observed,
        result={
            "base_material": dict(base),
            "base_digest": base_digest,
            "reference_target": reference_target,
            "statistics": statistics,
            "simulation_records": records,
        },
        reason_code=_refuter_code(refuter_id, "PASSED" if passed else "FAILED"),
        reason=(
            "All 100 exact-estimator simulations satisfy the registered refuter rule."
            if passed
            else "The refuter p-value or median-shift rule failed."
        ),
        trigger_codes=[] if passed else [_refuter_code(refuter_id, "FAILED")],
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
    )


def run_refuter_battery(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    primary_effect: Mapping[str, Any] | None = None,
    estimator_adapter: object | None = None,
    seed_context: Mapping[str, Any] | None = None,
    root_seed: int | None = None,
    dataset_version_id: str | None = None,
    causal_question_id: str | None = None,
    causal_question_version: str | None = None,
    engine_config_id: str | None = None,
    engine_config_version: str | None = None,
    suite_id: str | None = None,
    suite_version: str | None = None,
    validity_policy_id: str = DIAGNOSTIC_POLICY_ID,
    validity_policy_version: str = DIAGNOSTIC_POLICY_VERSION,
    refuter_adapter_id: str = REFUTER_ADAPTER_ID,
    refuter_adapter_version: str = REFUTER_ADAPTER_VERSION,
    primary_artifacts: Mapping[str, Any] | None = None,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    upstream_trigger: str | None = None,
) -> dict[str, Any]:
    """Execute and seal the four registered exact-estimator refuters."""

    if upstream_trigger is not None:
        diagnostics = [
            _empty_refuter_diagnostic(
                refuter_id,
                status="NOT_RUN",
                reason_code="UPSTREAM_SHORT_CIRCUIT",
                reason="The upstream scientific gate stopped this refuter before execution.",
                upstream_trigger=upstream_trigger,
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
            for refuter_id in REFUTER_DIAGNOSTIC_IDS
        ]
        payload: dict[str, Any] = {
            "schema_version": REFUTER_BATTERY_SCHEMA_VERSION,
            "battery_id": REFUTER_BATTERY_ID,
            "battery_version": REFUTER_BATTERY_VERSION,
            "base_material": None,
            "base_digest": None,
            "simulation_count_per_refuter": REFUTER_SIMULATION_COUNT,
            "diagnostics": diagnostics,
        }
        payload["content_hash"] = _scientific_sha256(payload)
        return payload

    if rows is None:
        return _battery_without_seed_context(
            [
                _empty_refuter_diagnostic(
                    refuter_id,
                    status="UNAVAILABLE",
                    reason_code="PRIMARY_ESTIMATOR_ROWS_UNAVAILABLE",
                    reason="The canonical primary estimator rows are unavailable for refuter evaluation.",
                    analysis_run_id=analysis_run_id,
                    bundle_manifest_hash=bundle_manifest_hash,
                    evidence_refs=evidence_refs,
                    input_refs=input_refs,
                )
                for refuter_id in REFUTER_DIAGNOSTIC_IDS
            ],
            refuter_adapter_id=refuter_adapter_id,
            refuter_adapter_version=refuter_adapter_version,
        )
    if estimator_adapter is None:
        return _battery_without_seed_context(
            [
                _empty_refuter_diagnostic(
                    refuter_id,
                    status="FAILED",
                    reason_code="REFUTER_ADAPTER_EXECUTION_FAILED",
                    reason="The registered exact-estimator refuter adapter is absent, so the required execution failed.",
                    analysis_run_id=analysis_run_id,
                    bundle_manifest_hash=bundle_manifest_hash,
                    evidence_refs=evidence_refs,
                    input_refs=input_refs,
                )
                for refuter_id in REFUTER_DIAGNOSTIC_IDS
            ],
            refuter_adapter_id=refuter_adapter_id,
            refuter_adapter_version=refuter_adapter_version,
        )
    if getattr(estimator_adapter, "support_state", "configured") == "unsupported":
        diagnostics = [
            _refuter_result(
                refuter_id,
                status="UNSUPPORTED",
                threshold=_refuter_threshold(refuter_id),
                observed=_refuter_observed(
                    valid_count=0,
                    unsupported_count=REFUTER_SIMULATION_COUNT,
                    failed_count=0,
                ),
                result={
                    "support_failure": {
                        "state": "unsupported",
                        "invariant": "registered-exact-refuter-adapter-not-configured",
                    }
                },
                reason_code=_refuter_code(refuter_id, "UNSUPPORTED"),
                reason="The fresh-run exact refuter adapter is not configured, so no refuter simulation was executed.",
                trigger_codes=[_refuter_code(refuter_id, "UNSUPPORTED")],
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
            for refuter_id in REFUTER_DIAGNOSTIC_IDS
        ]
        return _battery_without_seed_context(
            diagnostics,
            refuter_adapter_id=refuter_adapter_id,
            refuter_adapter_version=refuter_adapter_version,
        )
    if primary_effect is None:
        return _battery_without_seed_context(
            [
                _empty_refuter_diagnostic(
                    refuter_id,
                    status="UNAVAILABLE",
                    reason_code="PRIMARY_EFFECT_UNAVAILABLE",
                    reason="The primary ATTE effect is unavailable for refuter evaluation.",
                    analysis_run_id=analysis_run_id,
                    bundle_manifest_hash=bundle_manifest_hash,
                    evidence_refs=evidence_refs,
                    input_refs=input_refs,
                )
                for refuter_id in REFUTER_DIAGNOSTIC_IDS
            ],
            refuter_adapter_id=refuter_adapter_id,
            refuter_adapter_version=refuter_adapter_version,
        )
    if not isinstance(primary_effect, Mapping):
        return _battery_without_seed_context(
            [
                _empty_refuter_diagnostic(
                    refuter_id,
                    status="FAILED",
                    reason_code="PRIMARY_EFFECT_INVALID",
                    reason="The primary ATTE effect is not a valid object for refuter evaluation.",
                    analysis_run_id=analysis_run_id,
                    bundle_manifest_hash=bundle_manifest_hash,
                    evidence_refs=evidence_refs,
                    input_refs=input_refs,
                )
                for refuter_id in REFUTER_DIAGNOSTIC_IDS
            ],
            refuter_adapter_id=refuter_adapter_id,
            refuter_adapter_version=refuter_adapter_version,
        )

    try:
        context = _resolve_seed_context(
            seed_context=seed_context,
            root_seed=root_seed,
            dataset_version_id=dataset_version_id,
            causal_question_id=causal_question_id,
            causal_question_version=causal_question_version,
            engine_config_id=engine_config_id,
            engine_config_version=engine_config_version,
            suite_id=suite_id,
            suite_version=suite_version,
            validity_policy_id=validity_policy_id,
            validity_policy_version=validity_policy_version,
        )
        base = _base_material(
            context,
            refuter_adapter_id=refuter_adapter_id,
            refuter_adapter_version=refuter_adapter_version,
        )
        base_digest = _scientific_sha256(base)
    except RefuterInputError:
        diagnostics = [
            _empty_refuter_diagnostic(
                refuter_id,
                status="FAILED",
                reason_code="REFUTER_SEED_INPUT_INVALID",
                reason="The refuter seed context is malformed or incomplete.",
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
            for refuter_id in REFUTER_DIAGNOSTIC_IDS
        ]
        payload = {
            "schema_version": REFUTER_BATTERY_SCHEMA_VERSION,
            "battery_id": REFUTER_BATTERY_ID,
            "battery_version": REFUTER_BATTERY_VERSION,
            "base_material": None,
            "base_digest": None,
            "simulation_count_per_refuter": REFUTER_SIMULATION_COUNT,
            "diagnostics": diagnostics,
        }
        payload["content_hash"] = _scientific_sha256(payload)
        return payload

    try:
        canonical_contract = _prepare_rows(rows)
        canonical_rows = canonical_contract.rows
    except RefuterInputError:
        diagnostics = [
            _empty_refuter_diagnostic(
                refuter_id,
                status="FAILED",
                reason_code="PRIMARY_ESTIMATOR_ROWS_INVALID",
                reason="The canonical primary estimator rows failed refuter input validation.",
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
            for refuter_id in REFUTER_DIAGNOSTIC_IDS
        ]
    else:
        if not _refuter_artifacts_are_available(primary_artifacts):
            diagnostics = [
                _empty_refuter_diagnostic(
                    refuter_id,
                    status="UNAVAILABLE",
                    reason_code="REFUTER_PRIMARY_ARTIFACTS_UNAVAILABLE",
                    reason="The exact primary fold, calibration, and propensity artifacts are required for refuter execution.",
                    analysis_run_id=analysis_run_id,
                    bundle_manifest_hash=bundle_manifest_hash,
                    evidence_refs=evidence_refs,
                    input_refs=input_refs,
                )
                for refuter_id in REFUTER_DIAGNOSTIC_IDS
            ]
        else:
            assert isinstance(primary_artifacts, Mapping)
            if not _canonical_row_order_matches(
                canonical_rows,
                canonical_contract.row_id_key,
                primary_artifacts,
            ):
                diagnostics = [
                    _empty_refuter_diagnostic(
                        refuter_id,
                        status="FAILED",
                        reason_code="PRIMARY_S9_ROW_ORDER_INVALID",
                        reason="The supplied estimator rows do not match the sealed canonical primary S9 order.",
                        analysis_run_id=analysis_run_id,
                        bundle_manifest_hash=bundle_manifest_hash,
                        evidence_refs=evidence_refs,
                        input_refs=input_refs,
                    )
                    for refuter_id in REFUTER_DIAGNOSTIC_IDS
                ]
            else:
                diagnostics = [
                    _execute_refuter(
                        refuter_id,
                        canonical_rows=canonical_rows,
                        primary_effect=primary_effect,
                        estimator_adapter=estimator_adapter,
                        base=base,
                        base_digest=base_digest,
                        primary_artifacts=primary_artifacts,
                        analysis_run_id=analysis_run_id,
                        bundle_manifest_hash=bundle_manifest_hash,
                        evidence_refs=evidence_refs,
                        input_refs=input_refs,
                    )
                    for refuter_id in REFUTER_DIAGNOSTIC_IDS
                ]

    coordinates = []
    if base_digest is not None:
        base_bytes = bytes.fromhex(base_digest.split(":", 1)[1])
        base_value = int.from_bytes(base_bytes[:8], byteorder="big", signed=False)
        for refuter_index, refuter_id in enumerate(REFUTER_DIAGNOSTIC_IDS):
            for simulation_index in range(REFUTER_SIMULATION_COUNT):
                coordinate_ordinal = refuter_index * REFUTER_SIMULATION_COUNT + simulation_index
                coordinates.append(
                    {
                        "refuter_id": refuter_id,
                        "refuter_index": refuter_index,
                        "simulation_index": simulation_index,
                        "coordinate_ordinal": coordinate_ordinal,
                        "simulation_root_seed": (base_value + coordinate_ordinal) % 2**64,
                    }
                )
    payload = {
        "schema_version": REFUTER_BATTERY_SCHEMA_VERSION,
        "battery_id": REFUTER_BATTERY_ID,
        "battery_version": REFUTER_BATTERY_VERSION,
        "refuter_adapter_id": refuter_adapter_id,
        "refuter_adapter_version": refuter_adapter_version,
        "seed_policy_id": REFUTER_SEED_POLICY_ID,
        "seed_policy_version": REFUTER_SEED_POLICY_VERSION,
        "base_material": dict(base),
        "base_digest": base_digest,
        "simulation_count_per_refuter": REFUTER_SIMULATION_COUNT,
        "coordinates": coordinates,
        "diagnostics": diagnostics,
    }
    payload["content_hash"] = _scientific_sha256(payload)
    return payload


def evaluate_refuter_battery(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    return list(run_refuter_battery(*args, **kwargs)["diagnostics"])


def _negative_control_threshold() -> dict[str, Any]:
    return {
        "overall_coverage_min": 0.95,
        "arm_coverage_min": 0.90,
        "arm_coverage_gap_max": 0.05,
        "equivalence_lower": -0.10,
        "equivalence_upper": 0.10,
        "equivalence_inclusive": True,
        "confidence_level": 0.95,
        "estimator": EXACT_ESTIMATOR_ID,
        "score": EXACT_ESTIMATOR_SCORE,
        "cluster": EXACT_ESTIMATOR_CLUSTER,
        "p_value_is_measurement_only": True,
    }


def _negative_result(
    *,
    status: str,
    observed: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
    reason_code: str,
    reason: str,
    trigger_codes: Sequence[str] = (),
    upstream_trigger: str | None = None,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
) -> dict[str, Any]:
    return _make_result(
        NEGATIVE_CONTROL_DIAGNOSTIC_ID,
        rule_id="negative-control-outcome-equivalence.v1",
        status=status,
        scope=DIAGNOSTIC_SCOPE,
        observed=observed,
        threshold=_negative_control_threshold(),
        result=result,
        verdict_effect="VETO" if status in {"FAIL", "UNSUPPORTED"} else "NONE",
        trigger_codes=trigger_codes,
        reason_code=reason_code,
        reason=reason,
        upstream_trigger=upstream_trigger,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
    )


def _negative_coverage_observed(
    *,
    total_count: int,
    present_count: int,
    exposed_total: int,
    exposed_present: int,
    unexposed_total: int,
    unexposed_present: int,
) -> dict[str, Any]:
    overall = present_count / total_count if total_count else 0.0
    exposed = exposed_present / exposed_total if exposed_total else 0.0
    unexposed = unexposed_present / unexposed_total if unexposed_total else 0.0
    return {
        "primary_s9_denominator": total_count,
        "present_control_count": present_count,
        "exposed_denominator": exposed_total,
        "exposed_present_count": exposed_present,
        "unexposed_denominator": unexposed_total,
        "unexposed_present_count": unexposed_present,
        "overall_coverage": overall,
        "exposed_coverage": exposed,
        "unexposed_coverage": unexposed,
        "coverage_gap": abs(exposed - unexposed),
    }


def _reviewed_control_manifest(spec: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Resolve exactly one reviewed manifest without trusting an eligibility flag."""

    collection_keys = (
        "reviewed_controls",
        "reviewed_negative_controls",
        "negative_control_outcomes",
    )
    declared_collections = [key for key in collection_keys if key in spec]
    if len(declared_collections) > 1:
        return None
    if declared_collections:
        controls = spec[declared_collections[0]]
        if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
            return None
        if len(controls) != 1 or not isinstance(controls[0], Mapping):
            return None
        manifest = controls[0]
    else:
        manifest = spec

    control_id = manifest.get("control_id", manifest.get("reviewed_control_id"))
    if not isinstance(control_id, str) or not control_id:
        return None
    if manifest.get("eligible") is False:
        return None
    required = (
        "pre_exposure_verified",
        "causal_graph_disjoint",
        "excluded_from_primary",
        "provenance_verified",
        "temporal_verified",
    )
    if any(manifest.get(key) is not True for key in required):
        return None
    return manifest


def _restricted_splits(
    splits: Sequence[Mapping[str, Any]] | None,
    *,
    contract: _RowContract,
    present_indices: set[int],
) -> list[dict[str, Any]]:
    if splits is None:
        raise RefuterInputError("primary fold assignments are unavailable")
    if not isinstance(splits, Sequence) or isinstance(splits, (str, bytes)):
        raise RefuterInputError("primary fold assignments are malformed")
    if not splits:
        raise RefuterInputError("primary fold assignments are empty")
    id_to_index = {
        str(row[contract.row_id_key]): index
        for index, row in enumerate(contract.rows)
    }

    def resolve_indices(value: object) -> list[int]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise RefuterInputError("primary fold assignment member is malformed")
        resolved: list[int] = []
        for item in value:
            if isinstance(item, (int, np.integer)) and not isinstance(item, bool):
                index = int(item)
            elif isinstance(item, str) and item in id_to_index:
                index = id_to_index[item]
            else:
                raise RefuterInputError("primary fold assignment identity is invalid")
            if index < 0 or index >= len(contract.rows):
                raise RefuterInputError("primary fold assignment index is out of range")
            resolved.append(index)
        return resolved

    restricted: list[dict[str, Any]] = []
    repeat_test_indices: dict[int, set[int]] = {}
    repeat_fold_counts: dict[int, int] = {}
    for split_index, split in enumerate(splits):
        if not isinstance(split, Mapping):
            raise RefuterInputError("primary fold assignment is not an object")
        full_train = resolve_indices(split.get("train"))
        full_test = resolve_indices(split.get("test"))
        if (
            len(set(full_train)) != len(full_train)
            or len(set(full_test)) != len(full_test)
            or set(full_train).intersection(full_test)
        ):
            raise RefuterInputError("primary fold assignment overlaps or duplicates rows")
        train_suppliers = {
            str(contract.rows[index][contract.supplier_key]) for index in full_train
        }
        test_suppliers = {
            str(contract.rows[index][contract.supplier_key]) for index in full_test
        }
        if train_suppliers.intersection(test_suppliers):
            raise RefuterInputError("primary fold assignment leaks supplier groups")
        repeat_value = split.get("repeat_index", split_index // 5)
        if (
            isinstance(repeat_value, bool)
            or not isinstance(repeat_value, int)
            or repeat_value not in {0, 1}
        ):
            raise RefuterInputError("primary fold repeat coordinate is invalid")
        repeat_seen = repeat_test_indices.setdefault(repeat_value, set())
        restricted_test = {index for index in full_test if index in present_indices}
        if repeat_seen.intersection(restricted_test):
            raise RefuterInputError("primary fold test assignment duplicates rows")
        repeat_seen.update(restricted_test)
        repeat_fold_counts[repeat_value] = repeat_fold_counts.get(repeat_value, 0) + 1
        train = [index for index in full_train if index in present_indices]
        test = [index for index in full_test if index in present_indices]
        if not train or not test:
            raise NegativeControlSupportError("negative-control restricted fold is empty")
        train_arms = {bool(contract.rows[index][contract.exposure_key]) for index in train}
        if train_arms != {False, True}:
            raise NegativeControlSupportError(
                "negative-control restricted training fold lacks both arms"
            )
        restricted.append(
            {
                "train": [contract.rows[index][contract.row_id_key] for index in train],
                "test": [contract.rows[index][contract.row_id_key] for index in test],
            }
        )
    if set(repeat_test_indices) != {0, 1} or any(
        count < 5 for count in repeat_fold_counts.values()
    ):
        raise RefuterInputError("primary fold assignments do not contain two five-fold repeats")
    if any(seen != present_indices for seen in repeat_test_indices.values()):
        raise RefuterInputError("primary fold assignments omit or add restricted rows")
    return restricted


def _restrict_propensity_predictions(
    predictions: Mapping[str, Any] | Sequence[Any] | None,
    *,
    contract: _RowContract,
    present_indices: set[int],
) -> object:
    if predictions is None:
        raise RefuterInputError("negative-control propensity provenance is unavailable")

    def validate(value: object) -> float:
        numeric = _number(value)
        if numeric is None or not 0.0 <= numeric <= 1.0:
            raise RefuterInputError("negative-control propensity prediction is invalid")
        return numeric

    def repeat_pair(value: object) -> list[float]:
        if isinstance(value, Mapping):
            value = [value.get("repeat_0"), value.get("repeat_1")]
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
            raise RefuterInputError(
                "negative-control repeat-specific propensity provenance is malformed"
            )
        return [validate(value[0]), validate(value[1])]

    present_rows = [
        (index, str(contract.rows[index][contract.row_id_key]))
        for index in sorted(present_indices)
    ]

    if isinstance(predictions, Mapping):
        if {
            "repeat_0",
            "repeat_1",
        } <= set(predictions) and all(
            isinstance(predictions[key], Mapping) for key in ("repeat_0", "repeat_1")
        ):
            repeat_maps = (predictions["repeat_0"], predictions["repeat_1"])
            if any(
                row_id not in repeat_maps[0] or row_id not in repeat_maps[1]
                for _, row_id in present_rows
            ):
                raise RefuterInputError("negative-control propensity provenance is incomplete")
            return [
                {
                    "row_id": row_id,
                    "repeat_predictions": [
                        validate(repeat_maps[0][row_id]),
                        validate(repeat_maps[1][row_id]),
                    ],
                }
                for _, row_id in present_rows
            ]
        values = []
        for _, row_id in present_rows:
            if row_id not in predictions:
                raise RefuterInputError("negative-control propensity provenance is incomplete")
            values.append(
                {"row_id": row_id, "repeat_predictions": repeat_pair(predictions[row_id])}
            )
        return values
    if isinstance(predictions, Sequence) and not isinstance(predictions, (str, bytes)):
        if len(predictions) == len(contract.rows):
            return [
                {
                    "row_id": row_id,
                    "repeat_predictions": repeat_pair(predictions[index]),
                }
                for index, row_id in present_rows
            ]
        if (
            len(predictions) == 2
            and all(
                isinstance(repeat_values, Sequence)
                and not isinstance(repeat_values, (str, bytes))
                and len(repeat_values) == len(contract.rows)
                for repeat_values in predictions
            )
        ):
            return [
                {
                    "row_id": row_id,
                    "repeat_predictions": [
                        validate(predictions[0][index]),
                        validate(predictions[1][index]),
                    ],
                }
                for index, row_id in present_rows
            ]
        raise RefuterInputError("negative-control propensity provenance has the wrong denominator")
    raise RefuterInputError("negative-control propensity provenance is malformed")


def _negative_effect(response: Mapping[str, Any]) -> tuple[Mapping[str, Any], float, float, float]:
    effect = _effect_mapping(response)
    lower = _number(effect.get("ci_lower", effect.get("interval_lower")))
    upper = _number(effect.get("ci_upper", effect.get("interval_upper")))
    interval = effect.get("confidence_interval", effect.get("interval"))
    if isinstance(interval, Mapping):
        lower = _number(interval.get("lower", interval.get("ci_lower")))
        upper = _number(interval.get("upper", interval.get("ci_upper")))
    ci_level = _number(effect.get("ci_level", 0.95))
    if lower is None or upper is None or ci_level is None or ci_level != 0.95 or lower > upper:
        raise RefuterInputError("negative-control interval is not a finite ordered 95% interval")
    p_value = _number(effect.get("p_value"))
    if "p_value" in effect and (p_value is None or p_value < 0.0 or p_value > 1.0):
        raise RefuterInputError("negative-control p-value measurement is invalid")
    return effect, lower, upper, p_value if p_value is not None else float("nan")


def evaluate_negative_control(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    negative_control: Mapping[str, Any] | None = None,
    estimator_adapter: object | None = None,
    primary_outer_splits: Sequence[Mapping[str, Any]] | None = None,
    primary_propensity_predictions: Mapping[str, Any] | Sequence[Any] | None = None,
    primary_artifacts: Mapping[str, Any] | None = None,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    upstream_trigger: str | None = None,
) -> dict[str, Any]:
    """Evaluate the reviewed negative-control outcome through the exact ATTE adapter."""

    threshold = _negative_control_threshold()
    if upstream_trigger is not None:
        return _negative_result(
            status="NOT_RUN",
            observed=None,
            result=None,
            reason_code="UPSTREAM_SHORT_CIRCUIT",
            reason="The upstream scientific gate stopped the negative-control diagnostic before execution.",
            upstream_trigger=upstream_trigger,
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    if rows is None:
        return _negative_result(
            status="UNAVAILABLE",
            observed=None,
            result=None,
            reason_code="PRIMARY_ESTIMATOR_ROWS_UNAVAILABLE",
            reason="The canonical primary estimator rows are unavailable for negative-control evaluation.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    try:
        contract = _prepare_rows(rows)
    except RefuterInputError:
        return _negative_result(
            status="FAILED",
            observed=None,
            result=None,
            reason_code="PRIMARY_ESTIMATOR_ROWS_INVALID",
            reason="The canonical primary estimator rows failed negative-control input validation.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    reviewed_control = (
        _reviewed_control_manifest(negative_control)
        if isinstance(negative_control, Mapping)
        else None
    )
    if reviewed_control is None:
        return _negative_result(
            status="UNSUPPORTED",
            observed=None,
            result=None,
            reason_code="NEGATIVE_CONTROL_UNSUPPORTED",
            reason="No reviewed pre-exposure negative-control outcome is eligible under the registered graph and provenance rules.",
            trigger_codes=["NEGATIVE_CONTROL_UNSUPPORTED"],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    negative_control = reviewed_control
    if estimator_adapter is None:
        return _negative_result(
            status="UNAVAILABLE",
            observed=None,
            result=None,
            reason_code="NEGATIVE_CONTROL_ADAPTER_UNAVAILABLE",
            reason="The exact negative-control estimator adapter is unavailable; no result was counted as evidence.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )

    field_name = next(
        (
            negative_control.get(key)
            for key in ("field", "value_field", "outcome_field", "control_field")
            if isinstance(negative_control.get(key), str)
        ),
        None,
    )
    if field_name is None:
        return _negative_result(
            status="UNSUPPORTED",
            observed=None,
            result=None,
            reason_code="NEGATIVE_CONTROL_UNSUPPORTED",
            reason="The reviewed negative-control manifest does not declare one value field.",
            trigger_codes=["NEGATIVE_CONTROL_UNSUPPORTED"],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )

    present_indices: set[int] = set()
    values: list[float] = []
    for index, row in enumerate(contract.rows):
        value = _number(row.get(field_name))
        if value is not None:
            present_indices.add(index)
            values.append(value)
    exposed_total = sum(bool(row[contract.exposure_key]) for row in contract.rows)
    unexposed_total = len(contract.rows) - exposed_total
    exposed_present = sum(
        bool(contract.rows[index][contract.exposure_key]) for index in present_indices
    )
    unexposed_present = len(present_indices) - exposed_present
    coverage = _negative_coverage_observed(
        total_count=len(contract.rows),
        present_count=len(present_indices),
        exposed_total=exposed_total,
        exposed_present=exposed_present,
        unexposed_total=unexposed_total,
        unexposed_present=unexposed_present,
    )
    if (
        exposed_total == 0
        or unexposed_total == 0
        or coverage["overall_coverage"] < threshold["overall_coverage_min"]
        or coverage["exposed_coverage"] < threshold["arm_coverage_min"]
        or coverage["unexposed_coverage"] < threshold["arm_coverage_min"]
        or coverage["coverage_gap"] > threshold["arm_coverage_gap_max"]
    ):
        return _negative_result(
            status="UNSUPPORTED",
            observed=coverage,
            result=None,
            reason_code="NEGATIVE_CONTROL_UNSUPPORTED",
            reason="The reviewed negative control does not meet the frozen primary S9 coverage denominators.",
            trigger_codes=["NEGATIVE_CONTROL_UNSUPPORTED"],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )

    mean = math.fsum(values) / len(values) if values else float("nan")
    variance = (
        math.fsum((value - mean) ** 2 for value in values) / len(values)
        if values
        else float("nan")
    )
    standard_deviation = math.sqrt(variance) if math.isfinite(variance) and variance >= 0 else float("nan")
    coverage.update(
        {
            "standardization_mean": mean,
            "standard_deviation": standard_deviation,
        }
    )
    if not math.isfinite(standard_deviation) or standard_deviation <= 0.0:
        return _negative_result(
            status="UNSUPPORTED",
            observed=coverage,
            result=None,
            reason_code="NEGATIVE_CONTROL_UNSUPPORTED",
            reason="The eligible negative-control subcohort is degenerate and cannot be standardized.",
            trigger_codes=["NEGATIVE_CONTROL_UNSUPPORTED"],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )

    artifacts = dict(primary_artifacts or {})
    if primary_outer_splits is None:
        candidate_splits = artifacts.get("outer_splits")
        if isinstance(candidate_splits, Sequence) and not isinstance(candidate_splits, (str, bytes)):
            primary_outer_splits = candidate_splits
    if primary_propensity_predictions is None:
        candidate_predictions = artifacts.get("propensity_predictions")
        if isinstance(candidate_predictions, (Mapping, Sequence)) and not isinstance(candidate_predictions, (str, bytes)):
            primary_propensity_predictions = candidate_predictions
    if not _refuter_artifacts_are_available(artifacts):
        return _negative_result(
            status="UNAVAILABLE",
            observed=coverage,
            result=None,
            reason_code="NEGATIVE_CONTROL_PRIMARY_ARTIFACTS_UNAVAILABLE",
            reason="The sealed primary folds, canonical row order, and authoritative propensity provenance are required for negative-control evaluation.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    if not _canonical_row_order_matches(
        contract.rows,
        contract.row_id_key,
        artifacts,
    ):
        return _negative_result(
            status="FAILED",
            observed=coverage,
            result=None,
            reason_code="PRIMARY_S9_ROW_ORDER_INVALID",
            reason="The supplied estimator rows do not match the sealed canonical primary S9 order.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    primary_outer_splits = artifacts["outer_splits"]
    primary_propensity_predictions = artifacts["propensity_predictions"]
    try:
        restricted_splits = _restricted_splits(
            primary_outer_splits,
            contract=contract,
            present_indices=present_indices,
        )
        restricted_predictions = _restrict_propensity_predictions(
            primary_propensity_predictions,
            contract=contract,
            present_indices=present_indices,
        )
        if not (
            negative_control.get("propensity_provenance_verified") is True
            or artifacts.get("propensity_provenance_verified") is True
        ):
            raise RefuterInputError("negative-control propensity provenance is not verified")
        support = negative_control.get("support", artifacts.get("support"))
        if not isinstance(support, Mapping):
            raise NegativeControlSupportError(
                "negative-control support invariants are unavailable"
            )
        if str(support.get("state", "")).lower() != "supported":
            raise NegativeControlSupportError(
                "negative-control support is scientifically unavailable"
            )
        support_flags = (
            "total_rows_supported",
            "supplier_supported",
            "mixed_supplier_supported",
            "clustered_inference_supported",
            "two_arm_training_supported",
        )
        if any(support.get(key) is not True for key in support_flags):
            raise NegativeControlSupportError(
                "negative-control support invariant is not met"
            )
        standardised_rows: list[dict[str, Any]] = []
        for index in sorted(present_indices):
            row = deepcopy(contract.rows[index])
            control_value = _number(row[field_name])
            if control_value is None:
                raise RefuterInputError("negative-control value disappeared during restriction")
            row["negative_control_standardized"] = (
                (control_value - mean) / standard_deviation
            )
            standardised_rows.append(row)
        request: dict[str, Any] = {
            "schema_version": NEGATIVE_CONTROL_ADAPTER_SCHEMA_VERSION,
            "diagnostic_id": NEGATIVE_CONTROL_DIAGNOSTIC_ID,
            "estimator_adapter_id": REFUTER_ADAPTER_ID,
            "estimator_adapter_version": REFUTER_ADAPTER_VERSION,
            "rows": standardised_rows,
            "present_row_indices": sorted(present_indices),
            "present_row_ids": [
                contract.rows[index][contract.row_id_key]
                for index in sorted(present_indices)
            ],
            "outcome_field": "negative_control_standardized",
            "outcome_standardization": {
                "mean": mean,
                "population_standard_deviation": standard_deviation,
                "source_field": field_name,
            },
            "adapter_matrix": {
                "outer_splits": "restrict_primary",
                "inner_splits": "not_executed",
                "propensity": "reuse_primary_repeat_specific_predictions",
                "outcome_nuisances": "refit_both_arms_restricted_rows",
            },
            "estimator_contract": dict(EXACT_ESTIMATOR_CONTRACT),
            "restricted_outer_splits": restricted_splits,
            "primary_propensity_predictions": restricted_predictions,
            "primary_artifacts": deepcopy(artifacts),
        }
        request_digest = _scientific_sha256(request)
        response = _adapter_call(estimator_adapter, request)
        response_status = _adapter_result_status(_adapter_status(response))
        if response_status == "UNSUPPORTED":
            _validate_scientific_unsupported_response(response)
            return _negative_result(
                status="UNSUPPORTED",
                observed=coverage,
                result={"adapter_request_digest": request_digest},
                reason_code="NEGATIVE_CONTROL_UNSUPPORTED",
                reason="The exact negative-control estimator lacks the required restricted support.",
                trigger_codes=["NEGATIVE_CONTROL_UNSUPPORTED"],
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
        if response_status == "UNAVAILABLE":
            return _negative_result(
                status="UNAVAILABLE",
                observed=coverage,
                result={"adapter_request_digest": request_digest},
                reason_code="NEGATIVE_CONTROL_RESULT_UNAVAILABLE",
                reason="The exact negative-control estimator did not return a result.",
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
        if response_status == "NOT_RUN":
            return _negative_result(
                status="NOT_RUN",
                observed=None,
                result=None,
                reason_code="NEGATIVE_CONTROL_NOT_RUN",
                reason="The exact negative-control adapter did not execute the required test.",
                upstream_trigger="NEGATIVE_CONTROL_ADAPTER_NOT_RUN",
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                evidence_refs=evidence_refs,
                input_refs=input_refs,
            )
        if response_status != "VALID":
            raise RefuterInputError("negative-control estimator execution failed")
        _validate_exact_estimator_receipt(response, request)
        effect, lower, upper, p_value = _negative_effect(response)
        coverage.update(
            {
                "estimate": _number(effect.get("estimate", effect.get("effect"))),
                "ci_lower": lower,
                "ci_upper": upper,
                "ci_level": 0.95,
            }
        )
        if math.isfinite(p_value):
            coverage["p_value"] = p_value
        passed = lower >= threshold["equivalence_lower"] and upper <= threshold["equivalence_upper"]
        return _negative_result(
            status="PASS" if passed else "FAIL",
            observed=coverage,
            result={
                "adapter_request_digest": request_digest,
                "effect": _plain(dict(effect)),
                "equivalence_passed": passed,
                "standardized_present_row_digest": _scientific_sha256(standardised_rows),
            },
            reason_code="NEGATIVE_CONTROL_PASSED" if passed else "NEGATIVE_CONTROL_FAILED",
            reason=(
                "The complete two-sided 95% negative-control interval lies inside the closed equivalence band."
                if passed
                else "The complete two-sided 95% negative-control interval lies outside the closed equivalence band."
            ),
            trigger_codes=[] if passed else ["NEGATIVE_CONTROL_FAILED"],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    except NegativeControlSupportError:
        return _negative_result(
            status="UNSUPPORTED",
            observed=coverage,
            result=None,
            reason_code="NEGATIVE_CONTROL_UNSUPPORTED",
            reason="The negative-control subcohort or restricted training splits lack the registered support invariant.",
            trigger_codes=["NEGATIVE_CONTROL_UNSUPPORTED"],
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
    except Exception:
        return _negative_result(
            status="FAILED",
            observed=coverage,
            result=None,
            reason_code="NEGATIVE_CONTROL_EXECUTION_FAILED",
            reason="The negative-control transformation, provenance restriction, or exact estimator execution failed.",
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
        )
