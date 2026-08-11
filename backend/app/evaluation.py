"""Deterministic, evaluator-only scientific acceptance harness.

The harness is deliberately separate from the operational causal engine.  Its
simulation truth and policy oracle are review evidence; they are never inputs
to the estimator, the policy selectors, or the product read model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import tempfile
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from .canonical import canonical_json, sha256


EVALUATION_MANIFEST_SCHEMA_VERSION = "scientific-evaluation-manifest.v1"
EVALUATION_RESULT_SCHEMA_VERSION = "scientific-evaluation-result.v1"
EVIDENCE_PACK_SCHEMA_VERSION = "scientific-evidence-pack.v1"
# This is the content address of the reviewed frozen manifest.  A recomputed
# self-hash is not sufficient evidence that a campaign is still the registered
# campaign, so verification also binds to this immutable value.
FROZEN_MANIFEST_CONTENT_HASH = (
    "sha256:6745f14bdc6f279209a0a0c02bccd4488dedd5f94ec92f7e67ccec39d73ef0ff"
)
FROZEN_EVIDENCE_PACK_HASH = (
    "sha256:6673879bafcbded3163c7dbb171167038d143942491c70c08d04688900e6d4a5"
)

CLAIM_STATES = ("ACCEPTED", "REJECTED", "UNAVAILABLE", "INVALID")

CORE_SCENARIO_IDS = (
    "TRUE_EFFECT",
    "NULL_EFFECT",
    "PLANTED_CORRELATE",
    "HIDDEN_CONFOUNDING",
    "POOR_OVERLAP",
)

POLICY_IDS = (
    "COPILOT",
    "PREDICTION_ONLY",
    "CORRELATION_ONLY",
    "ALWAYS_EXPEDITE",
    "STATIC_LOAD_RULE",
    "ORACLE",
)

ORDINARY_TRUE_ATTE_DAYS = 1.5

RUNTIME_LOCK = {
    "python": "3.12.13",
    "numpy": "2.2.6",
    "scipy": "1.15.3",
    "scikit_learn": "1.6.1",
    "doubleml": "0.11.3",
    "dowhy": "0.14",
    "evaluation_runtime": "stdlib-deterministic-v1",
}


class EvaluationIntegrityError(ValueError):
    """Raised when an evaluation manifest or evidence pack is not trustworthy."""


def _ordered_unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(member) for key, member in value.items() if key != "content_hash"}


def _content_hash(value: Mapping[str, Any]) -> str:
    return sha256(_without_hash(value))


def _safe_content_hash(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return _content_hash(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _scenario_specs() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "TRUE_EFFECT",
            "label": "true effect",
            "delta_version": "true-effect.v1",
            "true_primary_atte_days": ORDINARY_TRUE_ATTE_DAYS,
            "hidden_confounding": False,
            "overlap_failure": False,
            "spurious_predictor": False,
            "action_benefit_mode": "EFFECTIVE",
            "gates": {
                "relative_bias_max": 0.10,
                "interval_coverage_min": 0.90,
                "interval_coverage_max": 0.99,
            },
        },
        {
            "scenario_id": "NULL_EFFECT",
            "label": "null effect",
            "delta_version": "null-effect.v1",
            "true_primary_atte_days": 0.0,
            "hidden_confounding": False,
            "overlap_failure": False,
            "spurious_predictor": False,
            "action_benefit_mode": "ZERO",
            "gates": {
                "supported_rate_max": 0.05,
                "driver_recommendation_rate_max": 0.0,
            },
        },
        {
            "scenario_id": "PLANTED_CORRELATE",
            "label": "planted spurious correlate",
            "delta_version": "planted-correlate.v1",
            "true_primary_atte_days": 0.0,
            "hidden_confounding": False,
            "overlap_failure": False,
            "spurious_predictor": True,
            "action_benefit_mode": "SPURIOUS",
            "gates": {
                "correlation_only_action_rate_min": 0.90,
                "copilot_driver_recommendation_rate_max": 0.0,
            },
        },
        {
            "scenario_id": "HIDDEN_CONFOUNDING",
            "label": "hidden confounding",
            "delta_version": "hidden-confounding.v1",
            "true_primary_atte_days": 0.0,
            "hidden_confounding": True,
            "overlap_failure": False,
            "spurious_predictor": False,
            "action_benefit_mode": "ZERO",
            "gates": {
                "weak_association_only_rate_min": 0.95,
                "supported_rate_max": 0.0,
                "driver_recommendation_rate_max": 0.0,
            },
        },
        {
            "scenario_id": "POOR_OVERLAP",
            "label": "poor overlap",
            "delta_version": "poor-overlap.v1",
            "true_primary_atte_days": ORDINARY_TRUE_ATTE_DAYS,
            "hidden_confounding": False,
            "overlap_failure": True,
            "spurious_predictor": False,
            "action_benefit_mode": "EFFECTIVE",
            "gates": {
                "abstention_precision_min": 0.95,
            },
        },
    ]


def _policy_specs() -> list[dict[str, Any]]:
    return [
        {
            "policy_id": "COPILOT",
            "label": "Copilot",
            "uses": ["governed_verdict_permission", "driver_logic", "typed_constraints"],
            "minimum_effect_days": 0.50,
            "oracle_access": False,
        },
        {
            "policy_id": "PREDICTION_ONLY",
            "label": "Prediction-only",
            "uses": ["fixed_predictive_threshold_0.50", "capacity_constraints"],
            "predictive_threshold": 0.50,
            "oracle_access": False,
        },
        {
            "policy_id": "CORRELATION_ONLY",
            "label": "Correlation-only",
            "uses": ["highest_positive_shap_feature", "frozen_feature_action_mapping"],
            "oracle_access": False,
        },
        {
            "policy_id": "ALWAYS_EXPEDITE",
            "label": "Always-expedite",
            "uses": ["capacity_constraints"],
            "oracle_access": False,
        },
        {
            "policy_id": "STATIC_LOAD_RULE",
            "label": "Static load rule",
            "uses": ["fixed_supplier_history_67th_percentile"],
            "reference_window_id": "supplier-load-reference-window.v1",
            "reference_window_quantile": 0.67,
            "threshold_source": "base_dgp.static_load_rule.thresholds",
            "oracle_access": False,
        },
        {
            "policy_id": "ORACLE",
            "label": "Oracle",
            "uses": ["evaluator_only_potential_outcomes", "evaluator_only_action_costs"],
            "oracle_access": True,
        },
    ]


def _metric_specs() -> dict[str, Any]:
    return {
        "relative_bias": {
            "formula": "abs(mean_atte - true_atte) / abs(true_atte)",
            "unit": "ratio",
        },
        "interval_coverage": {
            "formula": "count(true_atte in interval) / count(estimated_runs)",
            "unit": "ratio",
        },
        "raw_oracle_regret": {
            "formula": "oracle_realized_net_value - policy_realized_net_value",
            "unit": "declared_currency",
        },
        "normalized_regret": {
            "formula": "raw_regret / (oracle_value - monitoring_value)",
            "unit": "ratio_or_not_applicable",
        },
        "unnecessary_action_rate": {
            "formula": "actions_when_oracle_prefers_monitoring / eligible_subjects",
            "unit": "ratio",
        },
        "harmful_action_rate": {
            "formula": "actions_with_net_value_below_monitoring / eligible_subjects",
            "unit": "ratio",
        },
        "preventable_delay_recovery": {
            "formula": "project_delay_days_avoided_vs_monitoring",
            "unit": "calendar_days",
        },
        "cost_per_protected_day": {
            "formula": "actual_spend / positive_project_delay_days_recovered",
            "unit": "declared_currency_per_calendar_day_or_unavailable",
        },
    }


def build_frozen_evaluation_manifest() -> dict[str, Any]:
    """Build the immutable campaign definition used by the scientific harness."""

    reference_window_quantile = 0.67
    reference_window_values = [
        [
            round(
                0.20 + ((supplier_index * 29 + window_index * 11) % 65) / 100,
                4,
            )
            for window_index in range(9)
        ]
        for supplier_index in range(100)
    ]
    static_load_thresholds = [
        round(_percentile(sorted(values), reference_window_quantile), 4)
        for values in reference_window_values
    ]
    manifest: dict[str, Any] = {
        "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
        "manifest_id": "core-scientific-evaluation",
        "manifest_version": "v1",
        "source": {
            "module": "backend.app.evaluation",
            "implementation_id": "core-scientific-evaluation-harness",
            "implementation_version": "v1",
        },
        "base_dgp": {
            "base_manifest_id": "core-semi-synthetic-dgp-base",
            "base_manifest_version": "v1",
            "line_count": 5_000,
            "supplier_count": 100,
            "minimum_lines_per_arm": 1_000,
            "minimum_mixed_arm_suppliers": 60,
            "exposure_share_target": 0.27,
            "exposure_share_bounds": [0.22, 0.32],
            "mean_concurrent_load": 3.9,
            "concurrent_load_standard_deviation": 8.1,
            "late_handoff_rate": 0.09,
            "slippage_standard_deviation_days": 6.0,
            "ordinary_true_atte_days": ORDINARY_TRUE_ATTE_DAYS,
            "capacity_material_multipliers": [0.5, 1.0, 1.5],
            "parameter_tags": {
                "mean_concurrent_load": "olist_derived_analogue",
                "concurrent_load_standard_deviation": "olist_derived_analogue",
                "late_handoff_rate": "olist_derived_analogue",
                "slippage_standard_deviation_days": "literature_anchored_analogue",
                "ordinary_true_atte_days": "intentionally_simulated_stress_knob",
                "capacity_material_multipliers": "intentionally_simulated_stress_knob",
                "generation": "intentionally_simulated_stress_knob",
                "static_load_rule": "frozen_pre_evaluation_reference_window",
            },
            "exposure_schedule": [14] * 50 + [13] * 50,
            "generation": {
                "baseline_intercept_days": 4.0,
                "supplier_baseline_step_days": 0.15,
                "hidden_confounder_noise_standard_deviation": 1.0,
                "hidden_exposed_shift": 2.5,
                "hidden_unexposed_shift": -0.75,
                "hidden_effect_scale": 2.0,
                "load_percentile_base": 0.05,
                "load_supplier_stride": 17,
                "load_row_stride": 13,
                "load_modulus": 90,
                "risk_load_intercept_percentile": 0.45,
                "risk_load_scale_percentile": 0.12,
                "exposure_risk_lift": 0.85,
                "spurious_feature_noise_standard_deviation": 0.10,
                "ordinary_feature_noise_standard_deviation": 1.5,
                "capacity_unavailable_modulus": 13,
                "hard_constraint_failure_modulus": 17,
                "declared_cost_per_day": 2.0,
                "direct_action_cost_base": 1.5,
                "direct_action_cost_supplier_step": 0.10,
                "project_delay_base_days": 5.0,
                "project_delay_baseline_scale": 0.35,
                "project_delay_load_scale": 2.0,
                "effective_action_benefit_base_days": 3.0,
                "effective_action_benefit_risk_scale": 1.5,
                "zero_effect_action_benefit_days": 0.10,
                "spurious_correlate_action_benefit_days": 0.15,
                "subject_case_count": 40,
                "off_support_subject_case_count": 20,
                "provenance_tag": "evaluation-lineage.v1",
                "negative_control": {
                    "noise_standard_deviation": 0.01,
                    "spurious_effect_days": 0.25,
                    "equivalence_band": [-0.10, 0.10],
                },
                "hidden_sensitivity": {
                    "proxy_noise_standard_deviation": 0.50,
                    "proxy_hidden_exposed_shift": 2.50,
                    "proxy_hidden_unexposed_shift": -0.75,
                    "proxy_margin_multiplier": 2.30,
                    "weak_boundary": 0.0,
                },
            },
            "static_load_rule": {
                "reference_window_id": "supplier-load-reference-window.v1",
                "reference_window_quantile": reference_window_quantile,
                "reference_window_values": reference_window_values,
                "thresholds": static_load_thresholds,
            },
            "olist_microdata_included": False,
        },
        "design_validation": {
            "schema_version": "scientific-evaluation-design-validation.v1",
            "state": "ACCEPTED",
            "checks": [
                {
                    "check_id": "DGP_DIMENSIONS",
                    "rule": "line_count=5000 and supplier_count=100",
                },
                {
                    "check_id": "ARM_SUPPORT",
                    "rule": "each arm >= 1000 and exposure share in [0.22,0.32]",
                },
                {
                    "check_id": "MIXED_SUPPLIER_SUPPORT",
                    "rule": "mixed_arm_supplier_count >= 60",
                },
                {
                    "check_id": "TRUTH_BOUNDARY",
                    "rule": "potential outcomes and action responses are evaluator-only",
                },
                {
                    "check_id": "STATIC_REFERENCE_WINDOW",
                    "rule": "supplier-specific 67th percentile thresholds are frozen before scoring",
                },
            ],
        },
        "evaluation_estimator": {
            "estimator_id": "supplier-clustered-difference-in-means.v1",
            "estimator_class": "SupplierClusteredDifferenceInMeans",
            "estimand_id": "primary_atte_slippage",
            "cluster_key": "supplier_id",
            "inference": "deterministic_supplier_cluster_bootstrap",
            "role": "frozen_scientific_evaluation_reference_estimator",
        },
        "scenario_deltas": [
            {
                "scenario_id": item["scenario_id"],
                "delta_version": item["delta_version"],
                "true_primary_atte_days": item["true_primary_atte_days"],
                "hidden_confounding": item["hidden_confounding"],
                "overlap_failure": item["overlap_failure"],
                "spurious_predictor": item["spurious_predictor"],
                "action_benefit_mode": item["action_benefit_mode"],
            }
            for item in _scenario_specs()
        ],
        "scenarios": _scenario_specs(),
        "policies": _policy_specs(),
        "metrics": _metric_specs(),
        "repetitions": {
            "seed_policy_id": "sha256-coordinate-seeds",
            "seed_policy_version": "v1",
            "seed_start": 160016,
            "seed_count": 100,
            "paired_by_seed": True,
        },
        "bootstrap": {
            "method": "paired_seed_percentile_bootstrap",
            "replicates": 512,
            "confidence_level": 0.95,
            "finite_cluster_correction": 1.10,
            "seed_coordinate": "bootstrap_replicate",
            "one_sided_superiority_lower_bound": True,
        },
        "runtime_lock": deepcopy(RUNTIME_LOCK),
        "claim_states": list(CLAIM_STATES),
        "evaluator_only_fields": [
            "potential_outcomes",
            "action_responses",
            "realized_action_costs",
            "oracle_policy_choice",
        ],
        "evaluator_only_boundary": {
            "namespace": "evaluation-only://core-scientific-evaluation/v1",
            "canonical_outputs_may_include_truth_values": False,
            "policy_selectors_may_read_truth": False,
        },
    }
    manifest["content_hash"] = _content_hash(manifest)
    return manifest


def _invalid_manifest(reason_code: str) -> dict[str, Any]:
    return {
        "state": "INVALID",
        "reason_code": reason_code,
        "content_hash": None,
    }


def verify_evaluation_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Verify a frozen manifest without modifying it or filling defaults."""

    if not isinstance(manifest, Mapping):
        return _invalid_manifest("EVALUATION_MANIFEST_SCHEMA_UNSUPPORTED")
    declared_hash = manifest.get("content_hash")
    try:
        actual_hash = _content_hash(manifest)
    except (TypeError, ValueError, OverflowError):
        return _invalid_manifest("EVALUATION_MANIFEST_SCHEMA_UNSUPPORTED")
    if not isinstance(declared_hash, str) or declared_hash != actual_hash:
        return _invalid_manifest("EVALUATION_MANIFEST_HASH_MISMATCH")
    if declared_hash != FROZEN_MANIFEST_CONTENT_HASH:
        return _invalid_manifest("EVALUATION_MANIFEST_NOT_CANONICAL")
    if manifest.get("schema_version") != EVALUATION_MANIFEST_SCHEMA_VERSION:
        return _invalid_manifest("EVALUATION_MANIFEST_SCHEMA_UNSUPPORTED")
    scenarios = manifest.get("scenarios")
    policies = manifest.get("policies")
    if (
        not isinstance(scenarios, list)
        or not isinstance(policies, list)
        or any(not isinstance(item, Mapping) for item in scenarios)
        or any(not isinstance(item, Mapping) for item in policies)
    ):
        return _invalid_manifest("EVALUATION_MANIFEST_SCHEMA_UNSUPPORTED")
    if tuple(item.get("scenario_id") for item in scenarios) != CORE_SCENARIO_IDS:
        return _invalid_manifest("EVALUATION_SCENARIO_REGISTRY_INVALID")
    if tuple(item.get("policy_id") for item in policies) != POLICY_IDS:
        return _invalid_manifest("EVALUATION_POLICY_REGISTRY_INVALID")
    dgp = manifest.get("base_dgp")
    repetitions = manifest.get("repetitions")
    design_validation = manifest.get("design_validation")
    evaluation_estimator = manifest.get("evaluation_estimator")
    if (
        not isinstance(dgp, Mapping)
        or not isinstance(repetitions, Mapping)
        or not isinstance(design_validation, Mapping)
        or not isinstance(evaluation_estimator, Mapping)
    ):
        return _invalid_manifest("EVALUATION_MANIFEST_SCHEMA_UNSUPPORTED")
    if (
        dgp.get("line_count") != 5_000
        or dgp.get("supplier_count") != 100
        or scenarios[0].get("true_primary_atte_days")
        != dgp.get("ordinary_true_atte_days")
        or repetitions.get("seed_count") != 100
        or repetitions.get("paired_by_seed") is not True
    ):
        return _invalid_manifest("EVALUATION_MANIFEST_PARAMETERS_INVALID")
    static_load_rule = dgp.get("static_load_rule")
    reference_values = (
        static_load_rule.get("reference_window_values")
        if isinstance(static_load_rule, Mapping)
        else None
    )
    thresholds = (
        static_load_rule.get("thresholds")
        if isinstance(static_load_rule, Mapping)
        else None
    )
    if (
        design_validation.get("state") != "ACCEPTED"
        or len(dgp.get("exposure_schedule", [])) != dgp.get("supplier_count")
        or not isinstance(static_load_rule, Mapping)
        or not isinstance(reference_values, list)
        or len(reference_values) != dgp.get("supplier_count")
        or not isinstance(thresholds, list)
        or len(thresholds) != dgp.get("supplier_count")
        or not isinstance(dgp.get("generation"), Mapping)
        or evaluation_estimator.get("estimator_id")
        != "supplier-clustered-difference-in-means.v1"
        or evaluation_estimator.get("cluster_key") != "supplier_id"
        or any(
            not isinstance(values, list) or len(values) != 9
            for values in reference_values
        )
        or any(
            round(
                _percentile(
                    sorted(map(float, values)),
                    float(static_load_rule["reference_window_quantile"]),
                ),
                4,
            )
            != float(threshold)
            for values, threshold in zip(reference_values, thresholds, strict=True)
        )
    ):
        return _invalid_manifest("EVALUATION_DESIGN_VALIDATION_INVALID")
    if tuple(manifest.get("claim_states", ())) != CLAIM_STATES:
        return _invalid_manifest("EVALUATION_CLAIM_STATE_REGISTRY_INVALID")
    return {
        "state": "ACCEPTED",
        "reason_code": "EVALUATION_MANIFEST_VALID",
        "content_hash": declared_hash,
    }


def scenario_spec(manifest: Mapping[str, Any], scenario_id: str) -> Mapping[str, Any]:
    """Return one declared scenario or raise a typed integrity error."""

    for item in manifest.get("scenarios", []):
        if isinstance(item, Mapping) and item.get("scenario_id") == scenario_id:
            return item
    raise EvaluationIntegrityError("EVALUATION_SCENARIO_UNREGISTERED")


def policy_spec(manifest: Mapping[str, Any], policy_id: str) -> Mapping[str, Any]:
    """Return one declared policy or raise a typed integrity error."""

    for item in manifest.get("policies", []):
        if isinstance(item, Mapping) and item.get("policy_id") == policy_id:
            return item
    raise EvaluationIntegrityError("EVALUATION_POLICY_UNREGISTERED")


def _coordinate_seed(
    *,
    root_seed: int,
    scenario_id: str,
    coordinate: str,
    seed_policy_id: str,
    seed_policy_version: str,
) -> int:
    material = canonical_json(
        {
            "seed_policy_id": seed_policy_id,
            "seed_policy_version": seed_policy_version,
            "root_seed": root_seed,
            "scenario_id": scenario_id,
            "coordinate": coordinate,
        }
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big")


def derive_evaluation_seed(
    *,
    root_seed: int,
    scenario_id: str,
    coordinate: str,
    seed_policy_id: str,
    seed_policy_version: str,
) -> int:
    """Derive the stable unsigned 32-bit seed for one evaluator component."""

    if not isinstance(root_seed, int) or isinstance(root_seed, bool) or root_seed < 0:
        raise EvaluationIntegrityError("EVALUATION_SEED_INVALID")
    if scenario_id not in CORE_SCENARIO_IDS or not isinstance(coordinate, str) or not coordinate:
        raise EvaluationIntegrityError("EVALUATION_SEED_COORDINATE_INVALID")
    return _coordinate_seed(
        root_seed=root_seed,
        scenario_id=scenario_id,
        coordinate=coordinate,
        seed_policy_id=seed_policy_id,
        seed_policy_version=seed_policy_version,
    )


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-value)
        return 1.0 / (1.0 + inverse)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _hash_truth(truth: Mapping[str, Any]) -> str:
    return sha256({key: value for key, value in truth.items() if key != "content_hash"})


def _replicate_observation_summary(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    supplier_ids = {str(row["supplier_id"]) for row in observations}
    exposed = sum(bool(row["high_load_exposure"]) for row in observations)
    unexposed = len(observations) - exposed
    arms_by_supplier: dict[str, set[bool]] = {}
    for row in observations:
        arms_by_supplier.setdefault(str(row["supplier_id"]), set()).add(
            bool(row["high_load_exposure"])
        )
    mixed = sum(len(arms) == 2 for arms in arms_by_supplier.values())
    return {
        "line_count": len(observations),
        "supplier_count": len(supplier_ids),
        "exposed_count": exposed,
        "unexposed_count": unexposed,
        "mixed_arm_supplier_count": mixed,
        "exposure_share": round(exposed / len(observations), 2),
    }


def _validate_replicate_summary(summary: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    dgp = manifest["base_dgp"]
    if summary.get("line_count") != dgp["line_count"]:
        raise EvaluationIntegrityError("EVALUATION_LINE_COUNT_INVALID")
    if summary.get("supplier_count") != dgp["supplier_count"]:
        raise EvaluationIntegrityError("EVALUATION_SUPPLIER_COUNT_INVALID")
    if summary.get("exposed_count", 0) < dgp["minimum_lines_per_arm"]:
        raise EvaluationIntegrityError("EVALUATION_EXPOSURE_ARM_SUPPORT_INVALID")
    if summary.get("unexposed_count", 0) < dgp["minimum_lines_per_arm"]:
        raise EvaluationIntegrityError("EVALUATION_UNEXPOSURE_ARM_SUPPORT_INVALID")
    if summary.get("mixed_arm_supplier_count", 0) < dgp["minimum_mixed_arm_suppliers"]:
        raise EvaluationIntegrityError("EVALUATION_MIXED_SUPPLIER_SUPPORT_INVALID")
    lower, upper = dgp["exposure_share_bounds"]
    if not lower <= float(summary["exposure_share"]) <= upper:
        raise EvaluationIntegrityError("EVALUATION_EXPOSURE_SHARE_INVALID")


def generate_evaluation_replicate(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    seed: int,
) -> dict[str, Any]:
    """Generate one frozen public cohort plus a separately hashed truth ledger.

    The returned truth ledger is intentionally an in-memory evaluator boundary.
    Callers that build canonical observations must pass only ``observations``
    onward; policy selectors receive observations and typed estimator signals,
    never this ledger.
    """

    if verify_evaluation_manifest(manifest)["state"] != "ACCEPTED":
        raise EvaluationIntegrityError("EVALUATION_MANIFEST_INVALID")
    if scenario_id not in CORE_SCENARIO_IDS:
        raise EvaluationIntegrityError("EVALUATION_SCENARIO_UNREGISTERED")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise EvaluationIntegrityError("EVALUATION_SEED_INVALID")

    scenario = scenario_spec(manifest, scenario_id)
    dgp = manifest["base_dgp"]
    generation = dgp["generation"]
    static_load_rule = dgp["static_load_rule"]
    action_risk_threshold = float(
        policy_spec(manifest, "PREDICTION_ONLY")["predictive_threshold"]
    )
    seed_policy = manifest["repetitions"]
    line_count = int(dgp["line_count"])
    supplier_count = int(dgp["supplier_count"])
    lines_per_supplier = line_count // supplier_count
    if lines_per_supplier * supplier_count != line_count:
        raise EvaluationIntegrityError("EVALUATION_DGP_DIMENSIONS_INVALID")

    rng = random.Random(
        derive_evaluation_seed(
            root_seed=seed,
            scenario_id=scenario_id,
            coordinate="dgp_generator",
            seed_policy_id=seed_policy["seed_policy_id"],
            seed_policy_version=seed_policy["seed_policy_version"],
        )
    )
    observations: list[dict[str, Any]] = []
    potential_outcomes: list[dict[str, Any]] = []
    action_responses: list[dict[str, Any]] = []
    true_effect = float(scenario["true_primary_atte_days"])
    hidden_confounding = bool(scenario["hidden_confounding"])
    spurious_predictor = bool(scenario["spurious_predictor"])
    overlap_failure = bool(scenario["overlap_failure"])

    for index in range(line_count):
        supplier_index, local_index = divmod(index, lines_per_supplier)
        exposed_limit = int(dgp["exposure_schedule"][supplier_index])
        exposed = local_index < exposed_limit
        supplier_id = f"sim-supplier-{supplier_index:03d}"
        order_line_id = f"sim:{scenario_id.lower()}:{seed}:{index:05d}"
        noise = rng.gauss(0.0, float(dgp["slippage_standard_deviation_days"]))
        hidden = rng.gauss(
            0.0,
            float(generation["hidden_confounder_noise_standard_deviation"]),
        )
        if hidden_confounding:
            hidden += float(
                generation["hidden_exposed_shift"]
                if exposed
                else generation["hidden_unexposed_shift"]
            )
        baseline = (
            float(generation["baseline_intercept_days"])
            + (supplier_index % 7) * float(generation["supplier_baseline_step_days"])
            + noise
            + (
                float(generation["hidden_effect_scale"]) * hidden
                if hidden_confounding
                else 0.0
            )
        )
        outcome_without_exposure = baseline
        outcome_with_exposure = baseline + true_effect
        observed_outcome = outcome_with_exposure if exposed else outcome_without_exposure
        load_percentile = _clip(
            float(generation["load_percentile_base"])
            + (
                (
                    supplier_index * int(generation["load_supplier_stride"])
                    + local_index * int(generation["load_row_stride"])
                    + seed
                )
                % int(generation["load_modulus"])
            )
            / 100.0,
            0.0,
            0.99,
        )
        concurrent_load = max(
            0.0,
            rng.gauss(
                float(dgp["mean_concurrent_load"]),
                float(dgp["concurrent_load_standard_deviation"]),
            ),
        )
        late_handoff = rng.random() < float(dgp["late_handoff_rate"])
        spurious_feature = (
            observed_outcome
            + rng.gauss(
                0.0,
                float(generation["spurious_feature_noise_standard_deviation"]),
            )
            if spurious_predictor
            else baseline
            + rng.gauss(
                0.0,
                float(generation["ordinary_feature_noise_standard_deviation"]),
            )
        )
        negative_control_exposure = (
            (supplier_index * 7 + local_index * 13 + seed) % 2 == 0
        )
        negative_control_outcome = rng.gauss(
            0.0,
            float(generation["negative_control"]["noise_standard_deviation"]),
        ) + (
            float(generation["negative_control"]["spurious_effect_days"])
            if spurious_predictor and negative_control_exposure
            else 0.0
        )
        sensitivity_proxy = rng.gauss(
            0.0,
            float(generation["hidden_sensitivity"]["proxy_noise_standard_deviation"]),
        )
        if hidden_confounding:
            sensitivity_proxy += float(
                generation["hidden_sensitivity"][
                    "proxy_hidden_exposed_shift"
                    if exposed
                    else "proxy_hidden_unexposed_shift"
                ]
            )
        risk_score = _sigmoid(
            (
                load_percentile
                - float(generation["risk_load_intercept_percentile"])
            )
            / float(generation["risk_load_scale_percentile"])
            + (
                float(generation["exposure_risk_lift"])
                if exposed and not spurious_predictor
                else 0.0
            )
        )
        capacity_available = (
            index + supplier_index
        ) % int(generation["capacity_unavailable_modulus"]) != 0
        hard_constraints_pass = (
            index + supplier_index
        ) % int(generation["hard_constraint_failure_modulus"]) != 0
        cost_per_day = float(generation["declared_cost_per_day"])
        project_delay_if_monitor = max(
            0.0,
            float(generation["project_delay_base_days"])
            + max(0.0, baseline)
            * float(generation["project_delay_baseline_scale"])
            + load_percentile * float(generation["project_delay_load_scale"]),
        )
        if (
            scenario["action_benefit_mode"] == "EFFECTIVE"
            and exposed
            and risk_score >= action_risk_threshold
        ):
            protected_delay = max(
                0.0,
                float(generation["effective_action_benefit_base_days"])
                + (risk_score - 0.5)
                * float(generation["effective_action_benefit_risk_scale"]),
            )
        elif scenario["action_benefit_mode"] == "SPURIOUS":
            protected_delay = (
                float(generation["spurious_correlate_action_benefit_days"])
                if exposed
                else 0.0
            )
        else:
            protected_delay = (
                float(generation["zero_effect_action_benefit_days"])
                if exposed
                else 0.0
            )
        action_cost = float(generation["direct_action_cost_base"]) + (
            supplier_index % 5
        ) * float(generation["direct_action_cost_supplier_step"])
        capacity_material_multiplier = float(
            dgp["capacity_material_multipliers"][
                supplier_index % len(dgp["capacity_material_multipliers"])
            ]
        )
        protected_delay *= capacity_material_multiplier
        feasible = capacity_available and hard_constraints_pass
        realized_net_value = (
            protected_delay * cost_per_day - action_cost if feasible else float("-inf")
        )
        oracle_action = (
            "CAPACITY_BACKED_ACCELERATION"
            if feasible and realized_net_value > 0
            else "ACCEPT_AND_MONITOR"
        )
        stratum = (
            "OFF_SUPPORT"
            if overlap_failure
            and index < int(generation["off_support_subject_case_count"])
            else "SUPPORTED"
        )
        observations.append(
            {
                "order_line_id": order_line_id,
                "supplier_id": supplier_id,
                "high_load_exposure": exposed,
                "supplier_milestone_slippage_days": round(observed_outcome, 10),
                "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
                "supplier_milestone_late": late_handoff,
                "concurrent_load": round(concurrent_load, 10),
                "load_percentile": round(load_percentile, 10),
                "static_load_threshold": static_load_rule["thresholds"][supplier_index],
                "risk_score": round(risk_score, 10),
                "spurious_feature": round(spurious_feature, 10),
                "shap_top_feature": "spurious_feature"
                if spurious_predictor
                else "high_load_exposure",
                "shap_value": round(
                    1.0
                    if spurious_predictor
                    else 0.8
                    if exposed
                    else -0.1,
                    10,
                ),
                "capacity_mechanism_verified": capacity_available,
                "hard_constraints_pass": hard_constraints_pass,
                "subject_support_stratum": stratum,
                "negative_control_exposure": negative_control_exposure,
                "negative_control_outcome": round(negative_control_outcome, 10),
                "sensitivity_proxy": round(sensitivity_proxy, 10),
                "lineage_refs": [
                    f"{generation['provenance_tag']}:{scenario_id}:{seed}:{index:05d}"
                ],
            }
        )
        potential_outcomes.append(
            {
                "order_line_id": order_line_id,
                "potential_slippage_without_exposure": round(outcome_without_exposure, 10),
                "potential_slippage_with_exposure": round(outcome_with_exposure, 10),
                "primary_effect_days": true_effect,
                "hidden_confounder": round(hidden, 10),
            }
        )
        action_responses.append(
            {
                "order_line_id": order_line_id,
                "project_delay_if_monitor": round(project_delay_if_monitor, 10),
                "protected_project_delay_days": round(protected_delay, 10),
                "declared_cost_per_day": cost_per_day,
                "direct_action_cost": round(action_cost, 10),
                "capacity_material_multiplier": capacity_material_multiplier,
                "feasible": feasible,
                "realized_net_value": (
                    round(realized_net_value, 10) if feasible else None
                ),
                "oracle_action": oracle_action,
            }
        )

    summary = _replicate_observation_summary(observations)
    _validate_replicate_summary(summary, manifest)
    truth: dict[str, Any] = {
        "namespace": manifest["evaluator_only_boundary"]["namespace"],
        "schema_version": "evaluation-only-truth.v1",
        "scenario_id": scenario_id,
        "seed": seed,
        "primary_atte_days": true_effect,
        "potential_outcomes": potential_outcomes,
        "action_responses": action_responses,
    }
    truth["content_hash"] = _hash_truth(truth)
    replicate: dict[str, Any] = {
        "schema_version": "scientific-evaluation-replicate.v1",
        "manifest_hash": manifest["content_hash"],
        "scenario_id": scenario_id,
        "seed": seed,
        "observation_summary": summary,
        "observations": observations,
        "evaluator_only_truth": truth,
    }
    replicate["content_hash"] = _content_hash(replicate)
    return replicate


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise EvaluationIntegrityError("EVALUATION_BOOTSTRAP_EMPTY")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(
        sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction
    )


def _cluster_bootstrap_interval(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    seed: int,
    supplier_groups: Sequence[tuple[int, float, int, float]],
) -> dict[str, Any]:
    bootstrap_spec = manifest["bootstrap"]
    seed_policy = manifest["repetitions"]
    replicates = int(bootstrap_spec["replicates"])
    if replicates < 32:
        raise EvaluationIntegrityError("EVALUATION_BOOTSTRAP_CONFIGURATION_INVALID")
    rng = np.random.default_rng(
        derive_evaluation_seed(
            root_seed=seed,
            scenario_id=scenario_id,
            coordinate="primary_atte_supplier_cluster_bootstrap",
            seed_policy_id=seed_policy["seed_policy_id"],
            seed_policy_version=seed_policy["seed_policy_version"],
        )
    )
    group_array = np.asarray(supplier_groups, dtype=np.float64)
    sampled = group_array[
        rng.integers(0, len(supplier_groups), size=(replicates, len(supplier_groups)))
    ]
    exposed_counts = sampled[:, :, 0].sum(axis=1)
    unexposed_counts = sampled[:, :, 2].sum(axis=1)
    if np.any(exposed_counts == 0) or np.any(unexposed_counts == 0):
        raise EvaluationIntegrityError("EVALUATION_BOOTSTRAP_ARM_EMPTY")
    values = (
        sampled[:, :, 1].sum(axis=1) / exposed_counts
        - sampled[:, :, 3].sum(axis=1) / unexposed_counts
    ).tolist()
    values.sort()
    confidence_level = float(bootstrap_spec["confidence_level"])
    two_sided_tail = (1.0 - confidence_level) / 2.0
    raw_lower = _percentile(values, two_sided_tail)
    raw_upper = _percentile(values, 1.0 - two_sided_tail)
    center = (raw_lower + raw_upper) / 2.0
    correction = float(bootstrap_spec["finite_cluster_correction"])
    lower = center - (center - raw_lower) * correction
    upper = center + (raw_upper - center) * correction
    return {
        "method": bootstrap_spec["method"],
        "replicates": replicates,
        "confidence_level": confidence_level,
        "lower": round(lower, 10),
        "upper": round(upper, 10),
        "finite_cluster_correction": correction,
        "sample_digest": sha256([round(value, 12) for value in values]),
    }


def _difference_interval(
    exposed_values: Sequence[float],
    unexposed_values: Sequence[float],
    *,
    confidence_level: float,
) -> tuple[float, float, float]:
    """Return a deterministic normal interval for a public diagnostic contrast."""

    if len(exposed_values) < 2 or len(unexposed_values) < 2:
        raise EvaluationIntegrityError("EVALUATION_DIAGNOSTIC_SUPPORT_INVALID")

    def mean_and_variance(values: Sequence[float]) -> tuple[float, float]:
        mean = math.fsum(values) / len(values)
        variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
        return mean, variance

    exposed_mean, exposed_variance = mean_and_variance(exposed_values)
    unexposed_mean, unexposed_variance = mean_and_variance(unexposed_values)
    difference = exposed_mean - unexposed_mean
    standard_error = math.sqrt(
        exposed_variance / len(exposed_values)
        + unexposed_variance / len(unexposed_values)
    )
    z_value = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    margin = z_value * standard_error
    return difference, difference - margin, difference + margin


def _invalid_replicate_evaluation(
    *,
    manifest_hash: object,
    replicate_hash: object,
    code: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": EVALUATION_RESULT_SCHEMA_VERSION,
        "manifest_hash": manifest_hash,
        "replicate_hash": replicate_hash,
        "scenario_id": None,
        "seed": None,
        "state": "INVALID",
        "failure_identity": {
            "code": code,
            "manifest_hash": manifest_hash,
            "replicate_hash": replicate_hash,
        },
        "estimation": {"state": "INVALID", "estimate_days": None},
        "evidence_verdict": None,
        "abstention": {"state": "UNAVAILABLE", "reason_code": code},
    }
    result["content_hash"] = _content_hash(result)
    return result


def _estimate_supplier_clustered_difference_in_means(
    manifest: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    scenario_id: str,
    seed: int,
) -> dict[str, Any]:
    """Execute the registered frozen reference estimator implementation."""

    groups: dict[str, list[float | int]] = {}
    for row in observations:
        if not isinstance(row, Mapping):
            raise EvaluationIntegrityError("EVALUATION_OBSERVATION_SCHEMA_UNSUPPORTED")
        supplier_id = row.get("supplier_id")
        exposed = row.get("high_load_exposure")
        outcome = row.get("supplier_milestone_slippage_days")
        if (
            not isinstance(supplier_id, str)
            or not isinstance(exposed, bool)
            or not isinstance(outcome, (int, float))
            or isinstance(outcome, bool)
            or not math.isfinite(float(outcome))
        ):
            raise EvaluationIntegrityError("EVALUATION_OBSERVATION_SCHEMA_UNSUPPORTED")
        group = groups.setdefault(supplier_id, [0, 0.0, 0, 0.0])
        if exposed:
            group[0] += 1
            group[1] += float(outcome)
        else:
            group[2] += 1
            group[3] += float(outcome)
    supplier_groups = [
        (int(values[0]), float(values[1]), int(values[2]), float(values[3]))
        for values in groups.values()
    ]
    exposed_count = sum(group[0] for group in supplier_groups)
    unexposed_count = sum(group[2] for group in supplier_groups)
    exposed_sum = sum(group[1] for group in supplier_groups)
    unexposed_sum = sum(group[3] for group in supplier_groups)
    if exposed_count == 0 or unexposed_count == 0:
        raise EvaluationIntegrityError("EVALUATION_ARM_SUPPORT_INVALID")
    estimate = exposed_sum / exposed_count - unexposed_sum / unexposed_count
    interval = _cluster_bootstrap_interval(
        manifest,
        scenario_id=scenario_id,
        seed=seed,
        supplier_groups=supplier_groups,
    )
    return {
        "estimator_id": manifest["evaluation_estimator"]["estimator_id"],
        "estimator_class": manifest["evaluation_estimator"]["estimator_class"],
        "cluster_key": manifest["evaluation_estimator"]["cluster_key"],
        "estimate_days": estimate,
        "interval": interval,
        "numerator": exposed_count,
        "denominator": exposed_count + unexposed_count,
        "exposed_count": exposed_count,
        "unexposed_count": unexposed_count,
    }


def _resolve_evaluation_estimator(manifest: Mapping[str, Any]):
    registry = {
        "supplier-clustered-difference-in-means.v1": (
            _estimate_supplier_clustered_difference_in_means
        ),
    }
    estimator_id = manifest.get("evaluation_estimator", {}).get("estimator_id")
    estimator = registry.get(estimator_id)
    if estimator is None:
        raise EvaluationIntegrityError("EVALUATION_ESTIMATOR_UNREGISTERED")
    return estimator


def evaluate_evaluation_replicate(
    manifest: Mapping[str, Any],
    replicate: Mapping[str, Any],
    *,
    verify_generation: bool = True,
) -> dict[str, Any]:
    """Estimate one public replicate and emit only typed public evidence."""

    manifest_report = verify_evaluation_manifest(manifest)
    if manifest_report["state"] != "ACCEPTED":
        return _invalid_replicate_evaluation(
            manifest_hash=manifest.get("content_hash"),
            replicate_hash=replicate.get("content_hash") if isinstance(replicate, Mapping) else None,
            code=manifest_report["reason_code"],
        )
    if not isinstance(replicate, Mapping):
        return _invalid_replicate_evaluation(
            manifest_hash=manifest["content_hash"],
            replicate_hash=None,
            code="EVALUATION_REPLICATE_SCHEMA_UNSUPPORTED",
        )
    declared_replicate_hash = replicate.get("content_hash")
    if not isinstance(declared_replicate_hash, str) or declared_replicate_hash != _content_hash(replicate):
        return _invalid_replicate_evaluation(
            manifest_hash=manifest["content_hash"],
            replicate_hash=declared_replicate_hash,
            code="EVALUATION_REPLICATE_HASH_MISMATCH",
        )
    scenario_id = replicate.get("scenario_id")
    seed = replicate.get("seed")
    if (
        replicate.get("manifest_hash") != manifest["content_hash"]
        or scenario_id not in CORE_SCENARIO_IDS
        or not isinstance(seed, int)
        or isinstance(seed, bool)
        or not isinstance(replicate.get("observations"), list)
    ):
        return _invalid_replicate_evaluation(
            manifest_hash=manifest["content_hash"],
            replicate_hash=declared_replicate_hash,
            code="EVALUATION_REPLICATE_BINDING_INVALID",
        )
    if verify_generation:
        regenerated = generate_evaluation_replicate(
            manifest,
            scenario_id=scenario_id,
            seed=seed,
        )
        if regenerated.get("content_hash") != declared_replicate_hash:
            return _invalid_replicate_evaluation(
                manifest_hash=manifest["content_hash"],
                replicate_hash=declared_replicate_hash,
                code="EVALUATION_REPLICATE_NOT_REGENERATED",
            )
    observations = replicate["observations"]
    try:
        summary = _replicate_observation_summary(observations)
        if replicate.get("observation_summary") != summary:
            raise EvaluationIntegrityError("EVALUATION_OBSERVATION_SUMMARY_MISMATCH")
        _validate_replicate_summary(summary, manifest)
    except (EvaluationIntegrityError, KeyError, TypeError, ValueError) as error:
        return _invalid_replicate_evaluation(
            manifest_hash=manifest["content_hash"],
            replicate_hash=declared_replicate_hash,
            code=str(error) or "EVALUATION_REPLICATE_INVALID",
        )

    try:
        estimator = _resolve_evaluation_estimator(manifest)(
            manifest,
            observations,
            scenario_id=scenario_id,
            seed=seed,
        )
    except (EvaluationIntegrityError, KeyError, TypeError, ValueError) as error:
        return _invalid_replicate_evaluation(
            manifest_hash=manifest["content_hash"],
            replicate_hash=declared_replicate_hash,
            code=str(error) or "EVALUATION_ESTIMATOR_INVALID",
        )
    estimate = float(estimator["estimate_days"])
    interval = estimator["interval"]
    exposed_count = int(estimator["exposed_count"])
    denominator = int(estimator["denominator"])
    lower = float(interval["lower"])
    upper = float(interval["upper"])
    generation = manifest["base_dgp"]["generation"]
    negative_control_values: dict[bool, list[float]] = {True: [], False: []}
    sensitivity_proxy_values: dict[bool, list[float]] = {True: [], False: []}
    for row in observations:
        negative_control_exposure = row.get("negative_control_exposure")
        negative_control_outcome = row.get("negative_control_outcome")
        sensitivity_proxy = row.get("sensitivity_proxy")
        if (
            not isinstance(negative_control_exposure, bool)
            or not isinstance(negative_control_outcome, (int, float))
            or isinstance(negative_control_outcome, bool)
            or not math.isfinite(float(negative_control_outcome))
            or not isinstance(sensitivity_proxy, (int, float))
            or isinstance(sensitivity_proxy, bool)
            or not math.isfinite(float(sensitivity_proxy))
        ):
            return _invalid_replicate_evaluation(
                manifest_hash=manifest["content_hash"],
                replicate_hash=declared_replicate_hash,
                code="EVALUATION_DIAGNOSTIC_INPUT_INVALID",
            )
        negative_control_values[negative_control_exposure].append(
            float(negative_control_outcome)
        )
        exposed = bool(row["high_load_exposure"])
        sensitivity_proxy_values[exposed].append(float(sensitivity_proxy))
    try:
        (
            negative_control_difference,
            negative_control_lower,
            negative_control_upper,
        ) = _difference_interval(
            negative_control_values[True],
            negative_control_values[False],
            confidence_level=float(manifest["bootstrap"]["confidence_level"]),
        )
        sensitivity_proxy_difference, _, _ = _difference_interval(
            sensitivity_proxy_values[True],
            sensitivity_proxy_values[False],
            confidence_level=float(manifest["bootstrap"]["confidence_level"]),
        )
    except EvaluationIntegrityError as error:
        return _invalid_replicate_evaluation(
            manifest_hash=manifest["content_hash"],
            replicate_hash=declared_replicate_hash,
            code=str(error),
        )
    sensitivity_lower_bound = estimate - float(
        generation["hidden_sensitivity"]["proxy_margin_multiplier"]
    ) * abs(sensitivity_proxy_difference)
    equivalence_lower, equivalence_upper = generation["negative_control"][
        "equivalence_band"
    ]
    negative_control_failed = (
        negative_control_lower < float(equivalence_lower)
        or negative_control_upper > float(equivalence_upper)
    )
    sensitivity_weak_boundary = float(generation["hidden_sensitivity"]["weak_boundary"])
    has_subject_support_failure = any(
        row.get("subject_support_stratum") == "OFF_SUPPORT" for row in observations
    )
    if negative_control_failed:
        verdict_code = "ASSOCIATION_ONLY"
        robustness_grade = "WEAK"
        verdict_reason = "NEGATIVE_CONTROL_FAILED"
    elif sensitivity_lower_bound <= sensitivity_weak_boundary:
        verdict_code = "ASSOCIATION_ONLY"
        robustness_grade = "WEAK"
        verdict_reason = "HIDDEN_CONFOUNDING_SENSITIVITY_BOUNDARY"
    elif lower <= 0.0 <= upper:
        verdict_code = "INSUFFICIENT"
        robustness_grade = "UNAVAILABLE"
        verdict_reason = "PRIMARY_INTERVAL_INCLUDES_NULL"
    else:
        verdict_code = "SUPPORTED_UNDER_ASSUMPTIONS"
        robustness_grade = "STRONG"
        verdict_reason = "EVIDENCE_POLICY_PASSED"
    abstention: dict[str, Any]
    if has_subject_support_failure:
        subject_limit = int(generation["subject_case_count"])
        subject_candidates = observations[:subject_limit]
        subjects = [
            {
                "subject_id": str(row["order_line_id"]),
                "support_stratum": row["subject_support_stratum"],
                "subject_effect": None
                if row["subject_support_stratum"] == "OFF_SUPPORT"
                else round(estimate, 10),
                "driver_recommendation": False,
            }
            for row in subject_candidates
        ]
        off_support = sum(item["support_stratum"] == "OFF_SUPPORT" for item in subjects)
        abstained = sum(item["subject_effect"] is None for item in subjects)
        abstention = {
            "state": "ACCEPTED",
            "off_support_subjects": off_support,
            "abstained_subjects": abstained,
            "abstention_precision": round(abstained / off_support, 10),
            "abstention_coverage": round(abstained / len(subjects), 10),
            "subject_results": subjects,
        }
    else:
        abstention = {"state": "NOT_APPLICABLE"}
    result: dict[str, Any] = {
        "schema_version": EVALUATION_RESULT_SCHEMA_VERSION,
        "manifest_hash": manifest["content_hash"],
        "replicate_hash": declared_replicate_hash,
        "scenario_id": scenario_id,
        "seed": seed,
        "state": "ACCEPTED",
        "failure_identity": None,
        "estimation": {
            "state": "ACCEPTED",
            "estimand_id": manifest["evaluation_estimator"]["estimand_id"],
            "estimator_id": estimator["estimator_id"],
            "estimator_class": estimator["estimator_class"],
            "cluster_key": estimator["cluster_key"],
            "estimate_days": round(float(estimator["estimate_days"]), 10),
            "interval": interval,
            "numerator": estimator["numerator"],
            "denominator": denominator,
            "exposed_count": estimator["exposed_count"],
            "unexposed_count": estimator["unexposed_count"],
            "duration_basis": "CALENDAR_DAY",
        },
        "diagnostics": {
            "robustness_grade": robustness_grade,
            "interval_includes_null": lower <= 0.0 <= upper,
            "negative_control_interval": [
                round(negative_control_lower, 10),
                round(negative_control_upper, 10),
            ],
            "negative_control_difference": round(negative_control_difference, 10),
            "sensitivity_proxy_difference": round(sensitivity_proxy_difference, 10),
            "sensitivity_benchmark_lower_bound": round(sensitivity_lower_bound, 10),
            "verdict_reason": verdict_reason,
        },
        "evidence_verdict": {
            "verdict_code": verdict_code,
            "effect_display": "CAUSAL_ESTIMATE"
            if verdict_code == "SUPPORTED_UNDER_ASSUMPTIONS"
            else "ADJUSTED_ASSOCIATION"
            if verdict_code == "ASSOCIATION_ONLY"
            else "NONE",
            "decision_support_evaluation_permitted": verdict_code
            == "SUPPORTED_UNDER_ASSUMPTIONS",
            "primary_trigger": verdict_reason,
        },
        "abstention": abstention,
    }
    result["content_hash"] = _content_hash(result)
    return result


_ACCELERATION_ACTION = "CAPACITY_BACKED_ACCELERATION"
_MONITOR_ACTION = "ACCEPT_AND_MONITOR"


def _operationally_eligible(row: Mapping[str, Any]) -> bool:
    return bool(row.get("capacity_mechanism_verified")) and bool(
        row.get("hard_constraints_pass")
    )


def evaluate_policy_replicate(
    manifest: Mapping[str, Any],
    replicate: Mapping[str, Any],
    estimation: Mapping[str, Any],
    *,
    include_actions: bool = True,
) -> dict[str, Any]:
    """Score the six policies while keeping Oracle selection evaluator-only."""

    if verify_evaluation_manifest(manifest)["state"] != "ACCEPTED":
        raise EvaluationIntegrityError("EVALUATION_MANIFEST_INVALID")
    if (
        not isinstance(replicate, Mapping)
        or replicate.get("content_hash") != _content_hash(replicate)
        or estimation.get("state") != "ACCEPTED"
        or estimation.get("content_hash") != _content_hash(estimation)
        or estimation.get("manifest_hash") != manifest.get("content_hash")
        or estimation.get("replicate_hash") != replicate.get("content_hash")
        or estimation.get("scenario_id") != replicate.get("scenario_id")
        or estimation.get("seed") != replicate.get("seed")
    ):
        raise EvaluationIntegrityError("EVALUATION_ESTIMATION_BINDING_INVALID")
    observations = replicate.get("observations")
    truth = replicate.get("evaluator_only_truth")
    if not isinstance(observations, list) or not isinstance(truth, Mapping):
        raise EvaluationIntegrityError("EVALUATION_REPLICATE_BOUNDARY_INVALID")
    if truth.get("content_hash") != _hash_truth(truth):
        raise EvaluationIntegrityError("EVALUATION_TRUTH_HASH_MISMATCH")
    responses = truth.get("action_responses")
    if not isinstance(responses, list) or len(responses) != len(observations):
        raise EvaluationIntegrityError("EVALUATION_ACTION_RESPONSE_BINDING_INVALID")
    verdict = estimation.get("evidence_verdict")
    predictive_threshold = float(
        policy_spec(manifest, "PREDICTION_ONLY")["predictive_threshold"]
    )
    copilot_permitted = (
        isinstance(verdict, Mapping)
        and bool(verdict.get("decision_support_evaluation_permitted"))
        and float(estimation["estimation"].get("estimate_days", 0.0))
        >= float(policy_spec(manifest, "COPILOT")["minimum_effect_days"])
    )
    policy_outputs: dict[str, Any] = {
        policy_id: {
            "state": "ACCEPTED",
            "policy_id": policy_id,
            "eligible_subject_count": 0,
            "action_count": 0,
            "realized_net_value": 0.0,
            "oracle_net_value": 0.0,
            "unnecessary_action_count": 0,
            "harmful_action_count": 0,
            "preventable_delay_recovery": 0.0,
            "actual_spend": 0.0,
            **({"actions": []} if include_actions else {}),
        }
        for policy_id in POLICY_IDS
    }
    boundaries: dict[str, Any] = {
        policy_id: {
            "truth_access": policy_id == "ORACLE",
            "selection_inputs": ["evaluator_only_truth.action_responses"]
            if policy_id == "ORACLE"
            else ["public_observations", "typed_estimation_verdict"],
        }
        for policy_id in POLICY_IDS
    }
    for row, response in zip(observations, responses, strict=True):
        order_line_id = str(row["order_line_id"])
        if str(response.get("order_line_id")) != order_line_id:
            raise EvaluationIntegrityError("EVALUATION_ACTION_RESPONSE_ID_MISMATCH")
        eligible = _operationally_eligible(row)
        oracle_value = response.get("realized_net_value")
        oracle_value_number = float(oracle_value) if oracle_value is not None else 0.0
        oracle_positive_value = max(0.0, oracle_value_number)
        for policy_id in POLICY_IDS:
            metrics = policy_outputs[policy_id]
            metrics["oracle_net_value"] += oracle_positive_value
            if eligible:
                metrics["eligible_subject_count"] += 1
            if policy_id == "COPILOT":
                accelerate = (
                    copilot_permitted
                    and eligible
                    and bool(row.get("high_load_exposure"))
                    and float(row.get("risk_score", 0.0)) >= predictive_threshold
                )
            elif policy_id == "PREDICTION_ONLY":
                accelerate = eligible and float(row.get("risk_score", 0.0)) >= predictive_threshold
            elif policy_id == "CORRELATION_ONLY":
                accelerate = (
                    eligible
                    and row.get("shap_top_feature")
                    in {"spurious_feature", "high_load_exposure"}
                    and float(row.get("shap_value", 0.0)) > 0.0
                )
            elif policy_id == "ALWAYS_EXPEDITE":
                accelerate = eligible
            elif policy_id == "STATIC_LOAD_RULE":
                accelerate = eligible and float(row.get("load_percentile", 0.0)) >= float(
                    row.get("static_load_threshold", 1.0)
                )
            else:
                accelerate = response.get("oracle_action") == _ACCELERATION_ACTION
            action = _ACCELERATION_ACTION if accelerate else _MONITOR_ACTION
            if include_actions:
                metrics["actions"].append({"order_line_id": order_line_id, "action": action})
            if action != _ACCELERATION_ACTION:
                continue
            if response.get("feasible") is not True:
                raise EvaluationIntegrityError("EVALUATION_INFEASIBLE_POLICY_ACTION")
            metrics["action_count"] += 1
            metrics["realized_net_value"] += oracle_value_number
            metrics["preventable_delay_recovery"] += float(
                response["protected_project_delay_days"]
            )
            metrics["actual_spend"] += float(response["direct_action_cost"])
            if response.get("oracle_action") == _MONITOR_ACTION:
                metrics["unnecessary_action_count"] += 1
            if oracle_value_number < 0.0:
                metrics["harmful_action_count"] += 1
    for policy_id, metrics in policy_outputs.items():
        eligible_count = int(metrics["eligible_subject_count"])
        oracle_net_value = float(metrics["oracle_net_value"])
        realized_net_value = float(metrics["realized_net_value"])
        recovered_delay = float(metrics["preventable_delay_recovery"])
        metrics["action_rate"] = (
            round(int(metrics["action_count"]) / eligible_count, 10)
            if eligible_count
            else None
        )
        metrics["realized_net_value"] = round(realized_net_value, 10)
        metrics["oracle_net_value"] = round(oracle_net_value, 10)
        metrics["raw_oracle_regret"] = round(oracle_net_value - realized_net_value, 10)
        metrics["normalized_regret"] = (
            round((oracle_net_value - realized_net_value) / oracle_net_value, 10)
            if oracle_net_value > 0.0
            else None
        )
        metrics["unnecessary_action_rate"] = (
            round(int(metrics["unnecessary_action_count"]) / eligible_count, 10)
            if eligible_count
            else None
        )
        metrics["harmful_action_rate"] = (
            round(int(metrics["harmful_action_count"]) / eligible_count, 10)
            if eligible_count
            else None
        )
        metrics["preventable_delay_recovery"] = round(recovered_delay, 10)
        metrics["cost_per_protected_day"] = (
            round(float(metrics["actual_spend"]) / recovered_delay, 10)
            if recovered_delay > 0.0
            else None
        )
        metrics["cost_per_protected_day_state"] = (
            "AVAILABLE" if recovered_delay > 0.0 else "NO_POSITIVE_RECOVERY"
        )
        metrics["actual_spend"] = round(float(metrics["actual_spend"]), 10)
        metrics["driver_recommendation"] = (
            policy_id == "COPILOT" and copilot_permitted
        )
    result: dict[str, Any] = {
        "schema_version": "scientific-policy-evaluation.v1",
        "manifest_hash": manifest["content_hash"],
        "replicate_hash": replicate["content_hash"],
        "scenario_id": replicate["scenario_id"],
        "seed": replicate["seed"],
        "policy_input_boundaries": boundaries,
        "policies": policy_outputs,
    }
    result["content_hash"] = _content_hash(result)
    return result


def _claim(
    *,
    claim_id: str,
    state: str,
    observed: Mapping[str, Any] | None,
    threshold: Mapping[str, Any] | None,
    reason_code: str,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    if state not in CLAIM_STATES:
        raise EvaluationIntegrityError("EVALUATION_CLAIM_STATE_INVALID")
    return {
        "claim_id": claim_id,
        "state": state,
        "observed": deepcopy(dict(observed)) if observed is not None else None,
        "threshold": deepcopy(dict(threshold)) if threshold is not None else None,
        "reason_code": reason_code,
        "evidence_refs": list(evidence_refs),
    }


def _gate_state(*, passes: bool, invalid_count: int) -> str:
    if invalid_count:
        return "INVALID"
    return "ACCEPTED" if passes else "REJECTED"


def _numeric_mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 10) if values else None


def _paired_policy_bootstrap(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    seed_rows: Sequence[Mapping[str, Any]],
    challenger_id: str,
) -> dict[str, Any]:
    if not seed_rows:
        raise EvaluationIntegrityError("EVALUATION_POLICY_ROWS_EMPTY")
    bootstrap_spec = manifest["bootstrap"]
    seed_policy = manifest["repetitions"]
    replicates = int(bootstrap_spec["replicates"])
    copilot_regrets = [
        float(row["policy_metrics"]["COPILOT"]["raw_oracle_regret"])
        for row in seed_rows
    ]
    challenger_regrets = [
        float(row["policy_metrics"][challenger_id]["raw_oracle_regret"])
        for row in seed_rows
    ]
    improvements = [
        challenger - copilot
        for challenger, copilot in zip(challenger_regrets, copilot_regrets, strict=True)
    ]
    rng = np.random.default_rng(
        derive_evaluation_seed(
            root_seed=int(seed_rows[0]["seed"]),
            scenario_id=scenario_id,
            coordinate=f"paired_regret_bootstrap:{challenger_id}",
            seed_policy_id=seed_policy["seed_policy_id"],
            seed_policy_version=seed_policy["seed_policy_version"],
        )
    )
    improvement_array = np.asarray(improvements, dtype=np.float64)
    bootstrap_means = rng.choice(
        improvement_array,
        size=(replicates, len(improvements)),
        replace=True,
    ).mean(axis=1).tolist()
    bootstrap_means.sort()
    mean_improvement = _numeric_mean(improvements)
    confidence_level = float(bootstrap_spec["confidence_level"])
    lower = round(_percentile(bootstrap_means, 1.0 - confidence_level), 10)
    opportunity = _numeric_mean(
        [float(row["policy_metrics"]["ORACLE"]["oracle_net_value"]) for row in seed_rows]
    )
    minimum_improvement = 0.10 * float(opportunity or 0.0)
    passes = bool(
        mean_improvement is not None
        and lower > 0.0
        and mean_improvement >= minimum_improvement
    )
    return {
        "challenger_policy_id": challenger_id,
        "paired_seed_count": len(seed_rows),
        "mean_regret_reduction": mean_improvement,
        "oracle_over_monitor_opportunity": opportunity,
        "minimum_regret_reduction": round(minimum_improvement, 10),
        "bootstrap": {
            "method": bootstrap_spec["method"],
            "replicates": replicates,
            "confidence_level": confidence_level,
            "one_sided_lower_bound": lower,
            "sample_digest": sha256([round(value, 12) for value in bootstrap_means]),
        },
        "state": "ACCEPTED" if passes else "REJECTED",
        "reason_code": "COPILOT_SUPERIORITY_GATE_PASSED"
        if passes
        else "COPILOT_SUPERIORITY_GATE_FAILED",
    }


def _runtime_fingerprint(manifest: Mapping[str, Any]) -> dict[str, Any]:
    package_names = {
        "numpy": "numpy",
        "scipy": "scipy",
        "scikit_learn": "scikit-learn",
        "doubleml": "doubleml",
        "dowhy": "dowhy",
    }
    observed_dependencies: dict[str, str] = {}
    for key, package_name in package_names.items():
        try:
            observed_dependencies[key] = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            observed_dependencies[key] = "unavailable"
    observed = {
        "python": platform.python_version(),
        **observed_dependencies,
        "evaluation_runtime": "stdlib-deterministic-v1",
        "thread_policy": "single_process_single_threaded_evaluator",
    }
    expected = manifest["runtime_lock"]
    matches = (
        observed["python"] == expected["python"]
        and all(observed[key] == expected[key] for key in package_names)
        and observed["evaluation_runtime"] == expected["evaluation_runtime"]
    )
    return {
        "state": "ACCEPTED" if matches else "INVALID",
        "reason_code": "EVALUATION_RUNTIME_MATCHED"
        if matches
        else "EVALUATION_RUNTIME_INCOMPATIBLE",
        "expected": deepcopy(dict(expected)),
        "observed": observed,
        "runtime_lock_hash": sha256(expected),
    }


def _replay_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    scenario_projections: dict[str, Any] = {}
    for scenario_id, scenario in result.get("scenario_results", {}).items():
        scenario_projections[str(scenario_id)] = {
            "seed_rows": [
                {
                    "seed": row.get("seed"),
                    "replicate_hash": row.get("replicate_hash"),
                    "row_hash": row.get("row_hash"),
                    "failure_identity": row.get("failure_identity"),
                }
                for row in scenario.get("seed_rows", [])
            ]
        }
    return {
        "manifest_hash": result.get("manifest_hash"),
        "scenario_results": scenario_projections,
    }


def _invalid_campaign_result(
    *,
    manifest_hash: object,
    reason_code: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": EVALUATION_RESULT_SCHEMA_VERSION,
        "manifest_hash": manifest_hash,
        "scope": "INVALID",
        "scenarios": [],
        "scenario_results": {},
        "claims": [
            _claim(
                claim_id="CORE_EVALUATION_INTEGRITY",
                state="INVALID",
                observed=None,
                threshold=None,
                reason_code=reason_code,
                evidence_refs=[str(manifest_hash)] if manifest_hash else [],
            )
        ],
        "integrity": {"state": "INVALID", "reason_code": reason_code},
        "runtime": {"state": "UNAVAILABLE", "reason_code": "EVALUATION_NOT_RUN"},
        "reproducibility": {"state": "UNAVAILABLE", "reason_code": "EVALUATION_NOT_RUN"},
        "overall_status": "CORE_EVALUATION_INVALID",
    }
    result["content_hash"] = _content_hash(result)
    return result


def _execution_failure_identity(
    manifest_hash: str,
    scenario_id: str,
    seed: int,
    stage: str,
) -> dict[str, Any]:
    return {
        "code": "EVALUATION_EXECUTION_ERROR",
        "stage": stage,
        "input_hash": sha256(
            {
                "manifest_hash": manifest_hash,
                "scenario_id": scenario_id,
                "seed": seed,
                "stage": stage,
            }
        ),
    }


def _clear_seed_row_effects(seed_row: dict[str, Any], failure_identity: Mapping[str, Any]) -> None:
    """Ensure an invalid seed cannot retain an effect-bearing projection."""

    seed_row["estimation_hash"] = None
    seed_row["estimation"] = None
    seed_row["diagnostics"] = None
    seed_row["evidence_verdict"] = None
    seed_row["abstention"] = {
        "state": "UNAVAILABLE",
        "reason_code": failure_identity.get("code"),
    }
    seed_row["policy_metrics"] = {}
    seed_row["failure_identity"] = dict(failure_identity)


def run_scientific_evaluation(
    *,
    manifest: Mapping[str, Any] | None = None,
    scenario_ids: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
    verify_replay: bool = True,
) -> dict[str, Any]:
    """Run the registered campaign or an explicitly requested focused subset."""

    active_manifest = build_frozen_evaluation_manifest() if manifest is None else manifest
    manifest_report = verify_evaluation_manifest(active_manifest)
    if manifest_report["state"] != "ACCEPTED":
        return _invalid_campaign_result(
            manifest_hash=active_manifest.get("content_hash")
            if isinstance(active_manifest, Mapping)
            else None,
            reason_code=manifest_report["reason_code"],
        )
    active_scenarios = list(CORE_SCENARIO_IDS if scenario_ids is None else scenario_ids)
    if (
        not active_scenarios
        or len(_ordered_unique(active_scenarios)) != len(active_scenarios)
        or any(item not in CORE_SCENARIO_IDS for item in active_scenarios)
    ):
        return _invalid_campaign_result(
            manifest_hash=active_manifest["content_hash"],
            reason_code="EVALUATION_SCENARIO_SCOPE_INVALID",
        )
    repetition_spec = active_manifest["repetitions"]
    active_seeds = list(
        range(
            int(repetition_spec["seed_start"]),
            int(repetition_spec["seed_start"]) + int(repetition_spec["seed_count"]),
        )
        if seeds is None
        else seeds
    )
    if (
        not active_seeds
        or len(_ordered_unique([str(seed) for seed in active_seeds])) != len(active_seeds)
        or any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in active_seeds)
    ):
        return _invalid_campaign_result(
            manifest_hash=active_manifest["content_hash"],
            reason_code="EVALUATION_SEED_SCOPE_INVALID",
        )
    full_campaign = tuple(active_scenarios) == CORE_SCENARIO_IDS and tuple(active_seeds) == tuple(
        range(
            int(repetition_spec["seed_start"]),
            int(repetition_spec["seed_start"]) + int(repetition_spec["seed_count"]),
        )
    )
    result: dict[str, Any] = {
        "schema_version": EVALUATION_RESULT_SCHEMA_VERSION,
        "manifest_hash": active_manifest["content_hash"],
        "scope": "FULL_CAMPAIGN" if full_campaign else "FOCUSED_SUBSET",
        "scenarios": active_scenarios,
        "seeds": active_seeds,
        "scenario_results": {},
        "claims": [],
    }
    replay_mismatches: list[dict[str, Any]] = []
    replay_seed_rows: dict[str, list[dict[str, Any]]] = {
        scenario_id: [] for scenario_id in active_scenarios
    }
    invalid_count = 0
    for active_scenario_id in active_scenarios:
        scenario_seed_rows: list[dict[str, Any]] = []
        for active_seed in active_seeds:
            replicate: Mapping[str, Any] | None = None
            estimation: Mapping[str, Any] | None = None
            policy_metrics: dict[str, Any] = {}
            failure_identity: Mapping[str, Any] | None = None
            stage = "GENERATION"
            replay_estimation: Mapping[str, Any] | None = None
            replay_policy_metrics: dict[str, Any] = {}
            try:
                replicate = generate_evaluation_replicate(
                    active_manifest,
                    scenario_id=active_scenario_id,
                    seed=active_seed,
                )
                stage = "ESTIMATION"
                estimation = evaluate_evaluation_replicate(
                    active_manifest,
                    replicate,
                    verify_generation=False,
                )
                if estimation.get("state") != "ACCEPTED":
                    invalid_count += 1
                    failure_identity = estimation.get("failure_identity")
                else:
                    stage = "POLICY"
                    policies = evaluate_policy_replicate(
                        active_manifest,
                        replicate,
                        estimation,
                        include_actions=False,
                    )
                    policy_metrics = {
                        policy_id: {
                            key: value
                            for key, value in metrics.items()
                            if key != "actions"
                        }
                        for policy_id, metrics in policies["policies"].items()
                    }
            except Exception:
                invalid_count += 1
                failure_identity = _execution_failure_identity(
                    active_manifest["content_hash"],
                    active_scenario_id,
                    active_seed,
                    stage,
                )
            seed_row: dict[str, Any] = {
                "scenario_id": active_scenario_id,
                "seed": active_seed,
                "replicate_hash": replicate.get("content_hash")
                if replicate is not None
                else None,
                "observation_summary": replicate.get("observation_summary")
                if replicate is not None
                else None,
                "estimation_hash": estimation.get("content_hash")
                if estimation is not None and failure_identity is None
                else None,
                "estimation": estimation.get("estimation")
                if estimation is not None and failure_identity is None
                else None,
                "diagnostics": estimation.get("diagnostics")
                if estimation is not None and failure_identity is None
                else None,
                "evidence_verdict": estimation.get("evidence_verdict")
                if estimation is not None and failure_identity is None
                else None,
                "abstention": estimation.get("abstention")
                if estimation is not None and failure_identity is None
                else {"state": "UNAVAILABLE"},
                "policy_metrics": policy_metrics,
                "failure_identity": failure_identity,
            }
            seed_row["row_hash"] = _content_hash(seed_row)
            scenario_seed_rows.append(seed_row)
            if verify_replay and replicate is not None and estimation is not None:
                try:
                    stage = "REPLAY_GENERATION"
                    replay_replicate = generate_evaluation_replicate(
                        active_manifest,
                        scenario_id=active_scenario_id,
                        seed=active_seed,
                    )
                    stage = "REPLAY_ESTIMATION"
                    replay_estimation = evaluate_evaluation_replicate(
                        active_manifest,
                        replay_replicate,
                        verify_generation=False,
                    )
                    if replay_estimation.get("state") == "ACCEPTED":
                        stage = "REPLAY_POLICY"
                        replay_policies = evaluate_policy_replicate(
                            active_manifest,
                            replay_replicate,
                            replay_estimation,
                            include_actions=False,
                        )
                        replay_policy_metrics = {
                            policy_id: {
                                key: value
                                for key, value in metrics.items()
                                if key != "actions"
                            }
                            for policy_id, metrics in replay_policies["policies"].items()
                        }
                    replay_seed_row = {
                        key: value
                        for key, value in seed_row.items()
                        if key != "row_hash"
                    }
                    replay_seed_row.update(
                        {
                            "replicate_hash": replay_replicate.get("content_hash"),
                            "estimation_hash": replay_estimation.get("content_hash"),
                            "estimation": replay_estimation.get("estimation"),
                            "diagnostics": replay_estimation.get("diagnostics"),
                            "evidence_verdict": replay_estimation.get("evidence_verdict"),
                            "abstention": replay_estimation.get("abstention"),
                            "policy_metrics": replay_policy_metrics,
                            "failure_identity": replay_estimation.get("failure_identity"),
                        }
                    )
                    replay_seed_row["row_hash"] = _content_hash(replay_seed_row)
                    replay_seed_rows[active_scenario_id].append(
                        {
                            "seed": active_seed,
                            "replicate_hash": replay_replicate.get("content_hash"),
                            "row_hash": replay_seed_row["row_hash"],
                            "failure_identity": replay_seed_row["failure_identity"],
                        }
                    )
                    if (
                        replay_replicate.get("content_hash")
                        != replicate.get("content_hash")
                        or replay_seed_row["row_hash"] != seed_row["row_hash"]
                    ):
                        mismatch_identity = {
                            "code": "EVALUATION_REPLAY_MISMATCH",
                            "stage": "REPLAY_COMPARISON",
                            "input_hash": sha256(
                                {
                                    "manifest_hash": active_manifest["content_hash"],
                                    "scenario_id": active_scenario_id,
                                    "seed": active_seed,
                                }
                            ),
                        }
                        seed_row["failure_identity"] = mismatch_identity
                        _clear_seed_row_effects(seed_row, mismatch_identity)
                        seed_row["row_hash"] = _content_hash(seed_row)
                        replay_seed_row["failure_identity"] = mismatch_identity
                        replay_seed_rows[active_scenario_id][-1][
                            "failure_identity"
                        ] = mismatch_identity
                        replay_seed_rows[active_scenario_id][-1]["row_hash"] = _content_hash(
                            replay_seed_row
                        )
                        replay_mismatches.append(
                            {
                                "scenario_id": active_scenario_id,
                                "seed": active_seed,
                                "failure_identity": mismatch_identity,
                            }
                        )
                        invalid_count += 1
                except Exception:
                    replay_failure = _execution_failure_identity(
                        active_manifest["content_hash"],
                        active_scenario_id,
                        active_seed,
                        stage,
                    )
                    seed_row["failure_identity"] = replay_failure
                    _clear_seed_row_effects(seed_row, replay_failure)
                    seed_row["row_hash"] = _content_hash(seed_row)
                    replay_seed_rows[active_scenario_id].append(
                        {
                            "seed": active_seed,
                            "replicate_hash": None,
                            "row_hash": None,
                            "failure_identity": replay_failure,
                        }
                    )
                    replay_mismatches.append(
                        {
                            "scenario_id": active_scenario_id,
                            "seed": active_seed,
                            "failure_identity": replay_failure,
                        }
                    )
                    invalid_count += 1
            elif verify_replay:
                replay_failure = _execution_failure_identity(
                    active_manifest["content_hash"],
                    active_scenario_id,
                    active_seed,
                    stage,
                )
                replay_seed_rows[active_scenario_id].append(
                    {
                        "seed": active_seed,
                        "replicate_hash": None,
                        "row_hash": None,
                        "failure_identity": replay_failure,
                    }
                )
                replay_mismatches.append(
                    {
                        "scenario_id": active_scenario_id,
                        "seed": active_seed,
                        "failure_identity": replay_failure,
                    }
                )
                invalid_count += 1
        scenario = scenario_spec(active_manifest, active_scenario_id)
        valid_rows = [row for row in scenario_seed_rows if row["failure_identity"] is None]
        estimates = [
            float(row["estimation"]["estimate_days"])
            for row in valid_rows
            if isinstance(row.get("estimation"), Mapping)
            and row["estimation"].get("estimate_days") is not None
        ]
        true_atte = float(scenario["true_primary_atte_days"])
        intervals = [
            row["estimation"]["interval"]
            for row in valid_rows
            if isinstance(row.get("estimation"), Mapping)
            and isinstance(row["estimation"].get("interval"), Mapping)
        ]
        coverage_count = sum(
            float(interval["lower"]) <= true_atte <= float(interval["upper"])
            for interval in intervals
        )
        aggregate: dict[str, Any] = {
            "seed_count": len(scenario_seed_rows),
            "valid_seed_count": len(valid_rows),
            "invalid_seed_count": len(scenario_seed_rows) - len(valid_rows),
            "mean_atte_days": _numeric_mean(estimates),
            "relative_bias": round(
                abs(float(_numeric_mean(estimates) or 0.0) - true_atte) / abs(true_atte),
                10,
            )
            if estimates and true_atte != 0.0
            else None,
            "interval_coverage": round(coverage_count / len(intervals), 10)
            if intervals
            else None,
            "supported_rate": round(
                sum(
                    row.get("evidence_verdict", {}).get("verdict_code")
                    == "SUPPORTED_UNDER_ASSUMPTIONS"
                    for row in valid_rows
                )
                / len(valid_rows),
                10,
            )
            if valid_rows
            else None,
            "driver_recommendation_rate": round(
                sum(
                    bool(
                        row.get("policy_metrics", {})
                        .get("COPILOT", {})
                        .get("driver_recommendation")
                    )
                    for row in valid_rows
                )
                / len(valid_rows),
                10,
            )
            if valid_rows
            else None,
            "correlation_only_action_rate": _numeric_mean(
                [
                    float(
                        row["policy_metrics"]["CORRELATION_ONLY"]["action_rate"]
                    )
                    for row in valid_rows
                    if row.get("policy_metrics", {}).get("CORRELATION_ONLY")
                ]
            ),
            "weak_association_only_rate": round(
                sum(
                    row.get("evidence_verdict", {}).get("verdict_code")
                    == "ASSOCIATION_ONLY"
                    and row.get("diagnostics", {}).get("robustness_grade") == "WEAK"
                    for row in valid_rows
                )
                / len(valid_rows),
                10,
            )
            if valid_rows
            else None,
            "abstention_precision": _numeric_mean(
                [
                    float(row["abstention"]["abstention_precision"])
                    for row in valid_rows
                    if row.get("abstention", {}).get("state") == "ACCEPTED"
                ]
            ),
            "abstention_coverage": _numeric_mean(
                [
                    float(row["abstention"]["abstention_coverage"])
                    for row in valid_rows
                    if row.get("abstention", {}).get("state") == "ACCEPTED"
                ]
            ),
        }
        paired_comparisons: dict[str, Any] = {}
        if valid_rows:
            for challenger_id in ("PREDICTION_ONLY", "CORRELATION_ONLY", "STATIC_LOAD_RULE"):
                paired_comparisons[challenger_id] = _paired_policy_bootstrap(
                    active_manifest,
                    scenario_id=active_scenario_id,
                    seed_rows=valid_rows,
                    challenger_id=challenger_id,
                )
        scenario_result: dict[str, Any] = {
            "scenario_id": active_scenario_id,
            "seed_rows": scenario_seed_rows,
            "aggregate": aggregate,
            "paired_policy_comparisons": paired_comparisons,
            "evaluator_only_truth_reference": {
                "namespace": active_manifest["evaluator_only_boundary"]["namespace"],
                "primary_atte_days": true_atte,
            },
        }
        scenario_result["content_hash"] = _content_hash(scenario_result)
        result["scenario_results"][active_scenario_id] = scenario_result
        evidence_ref = scenario_result["content_hash"]
        gates = scenario["gates"]
        scenario_claims: list[dict[str, Any]] = []
        if active_scenario_id == "TRUE_EFFECT":
            scenario_claims.extend(
                [
                    _claim(
                        claim_id="TRUE_EFFECT_ESTIMATION_QUALITY",
                        state=_gate_state(
                            passes=aggregate["relative_bias"] is not None
                            and aggregate["relative_bias"] <= gates["relative_bias_max"],
                            invalid_count=aggregate["invalid_seed_count"],
                        ),
                        observed={"relative_bias": aggregate["relative_bias"]},
                        threshold={"relative_bias_max": gates["relative_bias_max"]},
                        reason_code="TRUE_EFFECT_BIAS_GATE_PASSED"
                        if aggregate["relative_bias"] is not None
                        and aggregate["relative_bias"] <= gates["relative_bias_max"]
                        else "TRUE_EFFECT_BIAS_GATE_FAILED",
                        evidence_refs=[evidence_ref],
                    ),
                    _claim(
                        claim_id="TRUE_EFFECT_INTERVAL_COVERAGE",
                        state=_gate_state(
                            passes=aggregate["interval_coverage"] is not None
                            and gates["interval_coverage_min"]
                            <= aggregate["interval_coverage"]
                            <= gates["interval_coverage_max"],
                            invalid_count=aggregate["invalid_seed_count"],
                        ),
                        observed={"interval_coverage": aggregate["interval_coverage"]},
                        threshold={
                            "minimum": gates["interval_coverage_min"],
                            "maximum": gates["interval_coverage_max"],
                        },
                        reason_code="TRUE_EFFECT_COVERAGE_GATE_PASSED"
                        if aggregate["interval_coverage"] is not None
                        and gates["interval_coverage_min"]
                        <= aggregate["interval_coverage"]
                        <= gates["interval_coverage_max"]
                        else "TRUE_EFFECT_COVERAGE_GATE_FAILED",
                        evidence_refs=[evidence_ref],
                    ),
                ]
            )
        elif active_scenario_id == "NULL_EFFECT":
            scenario_claims.append(
                _claim(
                    claim_id="NULL_EFFECT_NO_SUPPORTED_DRIVER",
                    state=_gate_state(
                        passes=(
                            aggregate["supported_rate"] is not None
                            and aggregate["supported_rate"] <= gates["supported_rate_max"]
                            and aggregate["driver_recommendation_rate"]
                            <= gates["driver_recommendation_rate_max"]
                        ),
                        invalid_count=aggregate["invalid_seed_count"],
                    ),
                    observed={
                        "supported_rate": aggregate["supported_rate"],
                        "driver_recommendation_rate": aggregate[
                            "driver_recommendation_rate"
                        ],
                    },
                    threshold=gates,
                    reason_code="NULL_EFFECT_REJECTION_GATE_PASSED"
                    if aggregate["supported_rate"] is not None
                    and aggregate["supported_rate"] <= gates["supported_rate_max"]
                    and aggregate["driver_recommendation_rate"]
                    <= gates["driver_recommendation_rate_max"]
                    else "NULL_EFFECT_REJECTION_GATE_FAILED",
                    evidence_refs=[evidence_ref],
                )
            )
        elif active_scenario_id == "PLANTED_CORRELATE":
            scenario_claims.append(
                _claim(
                    claim_id="PLANTED_CORRELATE_REJECTION",
                    state=_gate_state(
                        passes=(
                            aggregate["correlation_only_action_rate"] is not None
                            and aggregate["correlation_only_action_rate"]
                            >= gates["correlation_only_action_rate_min"]
                            and aggregate["driver_recommendation_rate"]
                            <= gates["copilot_driver_recommendation_rate_max"]
                        ),
                        invalid_count=aggregate["invalid_seed_count"],
                    ),
                    observed={
                        "correlation_only_action_rate": aggregate[
                            "correlation_only_action_rate"
                        ],
                        "copilot_driver_recommendation_rate": aggregate[
                            "driver_recommendation_rate"
                        ],
                    },
                    threshold=gates,
                    reason_code="PLANTED_CORRELATE_REJECTION_GATE_PASSED"
                    if aggregate["correlation_only_action_rate"] is not None
                    and aggregate["correlation_only_action_rate"]
                    >= gates["correlation_only_action_rate_min"]
                    and aggregate["driver_recommendation_rate"]
                    <= gates["copilot_driver_recommendation_rate_max"]
                    else "PLANTED_CORRELATE_REJECTION_GATE_FAILED",
                    evidence_refs=[evidence_ref],
                )
            )
        elif active_scenario_id == "HIDDEN_CONFOUNDING":
            scenario_claims.append(
                _claim(
                    claim_id="HIDDEN_CONFOUNDING_REJECTION",
                    state=_gate_state(
                        passes=(
                            aggregate["weak_association_only_rate"] is not None
                            and aggregate["weak_association_only_rate"]
                            >= gates["weak_association_only_rate_min"]
                            and aggregate["supported_rate"] <= gates["supported_rate_max"]
                            and aggregate["driver_recommendation_rate"]
                            <= gates["driver_recommendation_rate_max"]
                        ),
                        invalid_count=aggregate["invalid_seed_count"],
                    ),
                    observed={
                        "weak_association_only_rate": aggregate[
                            "weak_association_only_rate"
                        ],
                        "supported_rate": aggregate["supported_rate"],
                        "driver_recommendation_rate": aggregate[
                            "driver_recommendation_rate"
                        ],
                    },
                    threshold=gates,
                    reason_code="HIDDEN_CONFOUNDING_REJECTION_GATE_PASSED"
                    if aggregate["weak_association_only_rate"] is not None
                    and aggregate["weak_association_only_rate"]
                    >= gates["weak_association_only_rate_min"]
                    and aggregate["supported_rate"] <= gates["supported_rate_max"]
                    and aggregate["driver_recommendation_rate"]
                    <= gates["driver_recommendation_rate_max"]
                    else "HIDDEN_CONFOUNDING_REJECTION_GATE_FAILED",
                    evidence_refs=[evidence_ref],
                )
            )
        elif active_scenario_id == "POOR_OVERLAP":
            scenario_claims.append(
                _claim(
                    claim_id="POOR_OVERLAP_ABSTENTION",
                    state=_gate_state(
                        passes=aggregate["abstention_precision"] is not None
                        and aggregate["abstention_precision"]
                        >= gates["abstention_precision_min"],
                        invalid_count=aggregate["invalid_seed_count"],
                    ),
                    observed={"abstention_precision": aggregate["abstention_precision"]},
                    threshold=gates,
                    reason_code="POOR_OVERLAP_ABSTENTION_GATE_PASSED"
                    if aggregate["abstention_precision"] is not None
                    and aggregate["abstention_precision"]
                    >= gates["abstention_precision_min"]
                    else "POOR_OVERLAP_ABSTENTION_GATE_FAILED",
                    evidence_refs=[evidence_ref],
                )
            )
        for challenger_id, comparison in paired_comparisons.items():
            if (
                active_scenario_id == "TRUE_EFFECT"
                or (
                    active_scenario_id == "PLANTED_CORRELATE"
                    and challenger_id in {"PREDICTION_ONLY", "CORRELATION_ONLY"}
                )
            ):
                scenario_claims.append(
                    _claim(
                        claim_id=f"{active_scenario_id}_{challenger_id}_DECISION_VALUE",
                        state=comparison["state"],
                        observed={
                            "mean_regret_reduction": comparison["mean_regret_reduction"],
                            "one_sided_lower_bound": comparison["bootstrap"][
                                "one_sided_lower_bound"
                            ],
                        },
                        threshold={
                            "minimum_regret_reduction": comparison[
                                "minimum_regret_reduction"
                            ],
                            "lower_bound_strictly_positive": True,
                        },
                        reason_code=comparison["reason_code"],
                        evidence_refs=[evidence_ref],
                    )
                )
        result["claims"].extend(scenario_claims)
    result["runtime"] = _runtime_fingerprint(active_manifest)
    result["integrity"] = {
        "state": "ACCEPTED" if invalid_count == 0 else "INVALID",
        "reason_code": "EVALUATION_ARTIFACTS_INTEGRITY_VERIFIED"
        if invalid_count == 0
        else "EVALUATION_ARTIFACTS_INVALID",
        "manifest_hash": active_manifest["content_hash"],
        "invalid_seed_count": invalid_count,
    }
    replay_projection = _replay_projection(result)
    replayed_projection = _replay_projection(
        {
            "manifest_hash": active_manifest["content_hash"],
            "scenario_results": {
                scenario_id: {"seed_rows": rows}
                for scenario_id, rows in replay_seed_rows.items()
            },
        }
    )
    result["reproducibility"] = {
        "state": "ACCEPTED"
        if verify_replay and not replay_mismatches
        else "INVALID"
        if replay_mismatches
        else "UNAVAILABLE",
        "method": "deterministic_public_projection_replay",
        "projection_hash": sha256(replay_projection),
        "replayed_projection_hash": sha256(replayed_projection)
        if verify_replay
        else None,
        "mismatches": replay_mismatches,
        "reason_code": "EVALUATION_REPLAY_MATCHED"
        if verify_replay and not replay_mismatches
        else "EVALUATION_REPLAY_MISMATCH"
        if replay_mismatches
        else "EVALUATION_REPLAY_NOT_REQUESTED",
    }
    result["claims"].extend(
        [
            _claim(
                claim_id="EVALUATION_RUNTIME_COMPATIBILITY",
                state=result["runtime"]["state"],
                observed={"observed": result["runtime"]["observed"]},
                threshold={"runtime_lock_hash": result["runtime"]["runtime_lock_hash"]},
                reason_code=result["runtime"]["reason_code"],
                evidence_refs=[active_manifest["content_hash"]],
            ),
            _claim(
                claim_id="EVALUATION_INTEGRITY",
                state=result["integrity"]["state"],
                observed={"invalid_seed_count": invalid_count},
                threshold={"invalid_seed_count": 0},
                reason_code=result["integrity"]["reason_code"],
                evidence_refs=[active_manifest["content_hash"]],
            ),
            _claim(
                claim_id="EVALUATION_REPRODUCIBILITY",
                state=result["reproducibility"]["state"],
                observed={
                    "projection_hash": result["reproducibility"]["projection_hash"],
                    "mismatches": len(replay_mismatches),
                },
                threshold={"mismatches": 0},
                reason_code=result["reproducibility"]["reason_code"],
                evidence_refs=[active_manifest["content_hash"]],
            ),
            _claim(
                claim_id="EVALUATION_SCOPE_COMPLETENESS",
                state="ACCEPTED" if full_campaign else "UNAVAILABLE",
                observed={
                    "scenario_count": len(active_scenarios),
                    "seed_count": len(active_seeds),
                },
                threshold={"scenario_count": 5, "seed_count": 100},
                reason_code="FULL_CAMPAIGN_SCOPE_VERIFIED"
                if full_campaign
                else "FOCUSED_SUBSET_SCOPE",
                evidence_refs=[active_manifest["content_hash"]],
            ),
            _claim(
                claim_id="HUMAN_TRUST_AND_COMPREHENSION",
                state="UNAVAILABLE",
                observed=None,
                threshold=None,
                reason_code="HUMAN_VALIDATION_OUT_OF_SCOPE",
                evidence_refs=[],
            ),
        ]
    )
    non_blocking_claims = {"HUMAN_TRUST_AND_COMPREHENSION"}
    required_claim_states = [
        claim["state"]
        for claim in result["claims"]
        if claim["claim_id"] not in non_blocking_claims
    ]
    if "INVALID" in required_claim_states:
        overall_status = "CORE_EVALUATION_INVALID"
    elif "UNAVAILABLE" in required_claim_states:
        overall_status = "CORE_EVALUATION_UNAVAILABLE"
    elif full_campaign and all(state == "ACCEPTED" for state in required_claim_states):
        overall_status = "CORE_EVALUATION_ACCEPTED"
    elif full_campaign:
        overall_status = "CORE_EVALUATION_REJECTED"
    else:
        overall_status = "FOCUSED_EVALUATION_COMPLETE"
    result["overall_status"] = overall_status
    result["content_hash"] = _content_hash(result)
    return result


def _json_bytes(value: object) -> bytes:
    return canonical_json(value).encode("utf-8")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write one evidence member atomically in its destination directory."""

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _pack_identity_hash(
    manifest_hash: str,
    result_hash: str,
    members: Sequence[Mapping[str, Any]],
) -> str:
    return sha256(
        {
            "evaluation_manifest_hash": manifest_hash,
            "evaluation_result_hash": result_hash,
            "member_hashes": {
                str(member["path"]): str(member["content_hash"])
                for member in members
                if member.get("path") != "verification-command.txt"
            },
        }
    )


def _verification_command(
    manifest_hash: str,
    result_hash: str,
    identity_hash: str,
) -> str:
    """Return a location-independent, self-contained pack member check."""

    return (
        "python -c \"import hashlib,json; from pathlib import Path; "
        "r=Path.cwd(); c=lambda v: json.dumps(v,sort_keys=True,separators=(',',':'),"
        "ensure_ascii=False,allow_nan=False).encode(); "
        "h=lambda b: 'sha256:'+hashlib.sha256(b).hexdigest(); "
        "d=json.loads((r/'manifest.json').read_text()); "
        "m=json.loads((r/'evaluation-manifest.json').read_text()); "
        "q=json.loads((r/'evaluation-result.json').read_text()); "
        "assert d['content_hash']==h(c({k:v for k,v in d.items() if k!='content_hash'})); "
        "assert set(x['path'] for x in d['members'])=={'evaluation-manifest.json','evaluation-result.json','policy-config.json','runtime-lock.json','verification-command.txt'}; "
        "assert all(Path(x['path']).name==x['path'] and not Path(x['path']).is_absolute() and '..' not in Path(x['path']).parts for x in d['members']); "
        "assert d['evaluation_manifest_hash']=="
        + repr(manifest_hash)
        + "==m['content_hash']; "
        "assert d['evaluation_result_hash']=="
        + repr(result_hash)
        + "==q['content_hash']; "
        "assert d['canonical_identity_hash']=="
        + repr(identity_hash)
        + "==h(c({'evaluation_manifest_hash':d['evaluation_manifest_hash'],'evaluation_result_hash':d['evaluation_result_hash'],'member_hashes':{x['path']:x['content_hash'] for x in d['members'] if x['path']!='verification-command.txt'}})); "
        "assert q['content_hash']==h(c({k:v for k,v in q.items() if k!='content_hash'})); "
        "assert json.loads((r/'policy-config.json').read_text())=={'policies':m['policies'],'metrics':m['metrics']}; "
        "assert json.loads((r/'runtime-lock.json').read_text())==m['runtime_lock']; "
        "assert all(h((r/x['path']).read_bytes())==x['content_hash'] for x in d['members']); "
        "print({'state':'ACCEPTED','reason_code':'EVIDENCE_PACK_SELF_CHECKED'})\""
    )


def write_evidence_pack(
    destination: str | Path,
    *,
    manifest: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish an offline evidence pack with its descriptor written last."""

    if verify_evaluation_manifest(manifest)["state"] != "ACCEPTED":
        raise EvaluationIntegrityError("EVALUATION_MANIFEST_INVALID")
    if (
        result.get("manifest_hash") != manifest.get("content_hash")
        or result.get("content_hash") != _content_hash(result)
    ):
        raise EvaluationIntegrityError("EVALUATION_RESULT_HASH_MISMATCH")
    expected_seeds = list(
        range(
            int(manifest["repetitions"]["seed_start"]),
            int(manifest["repetitions"]["seed_start"])
            + int(manifest["repetitions"]["seed_count"]),
        )
    )
    if (
        result.get("scope") != "FULL_CAMPAIGN"
        or result.get("overall_status") != "CORE_EVALUATION_ACCEPTED"
        or result.get("scenarios") != list(CORE_SCENARIO_IDS)
        or result.get("seeds") != expected_seeds
        or result.get("integrity", {}).get("state") != "ACCEPTED"
        or result.get("runtime", {}).get("state") != "ACCEPTED"
        or result.get("reproducibility", {}).get("state") != "ACCEPTED"
        or result.get("integrity", {}).get("invalid_seed_count") != 0
    ):
        raise EvaluationIntegrityError("EVIDENCE_PACK_SCOPE_INVALID")
    root = Path(destination)
    if root.is_symlink():
        raise EvaluationIntegrityError("EVIDENCE_PACK_TARGET_SYMLINK")
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise EvaluationIntegrityError("EVIDENCE_PACK_TARGET_NOT_EMPTY")
    else:
        root.mkdir(parents=True)
    member_values: dict[str, object] = {
        "evaluation-manifest.json": manifest,
        "evaluation-result.json": result,
        "policy-config.json": {
            "policies": manifest["policies"],
            "metrics": manifest["metrics"],
        },
        "runtime-lock.json": manifest["runtime_lock"],
    }
    members: list[dict[str, Any]] = []
    for relative_path, value in member_values.items():
        payload = value.encode("utf-8") if isinstance(value, str) else _json_bytes(value)
        _atomic_write_bytes(root / relative_path, payload)
        members.append(
            {
                "path": relative_path,
                "content_hash": sha256(payload),
                "byte_count": len(payload),
                "media_type": "text/plain"
                if relative_path.endswith(".txt")
                else "application/json",
            }
        )
    identity_hash = _pack_identity_hash(
        manifest["content_hash"], result["content_hash"], members
    )
    verification_payload = _verification_command(
        manifest["content_hash"], result["content_hash"], identity_hash
    ).encode("utf-8")
    _atomic_write_bytes(root / "verification-command.txt", verification_payload)
    members.append(
        {
            "path": "verification-command.txt",
            "content_hash": sha256(verification_payload),
            "byte_count": len(verification_payload),
            "media_type": "text/plain",
        }
    )
    descriptor: dict[str, Any] = {
        "schema_version": EVIDENCE_PACK_SCHEMA_VERSION,
        "pack_id": "core-scientific-evaluation-evidence",
        "pack_version": "v1",
        "evaluation_manifest_hash": manifest["content_hash"],
        "evaluation_result_hash": result["content_hash"],
        "scope": result.get("scope"),
        "canonical_identity_hash": identity_hash,
        "members": members,
        "offline_verification": {
            "command_member": "verification-command.txt",
            "manifest_last": True,
        },
    }
    descriptor["content_hash"] = _content_hash(descriptor)
    _atomic_write_bytes(root / "manifest.json", _json_bytes(descriptor))
    return {
        "state": "ACCEPTED",
        "reason_code": "EVIDENCE_PACK_PUBLISHED",
        "path": str(root),
        "pack_hash": descriptor["content_hash"],
        "member_count": len(members),
    }


def _invalid_pack(reason_code: str, pack_hash: object = None) -> dict[str, Any]:
    return {
        "state": "INVALID",
        "reason_code": reason_code,
        "pack_hash": pack_hash,
    }


def verify_evidence_pack(destination: str | Path) -> dict[str, Any]:
    """Verify every member and cross-record binding in an evidence pack."""

    root = Path(destination)
    if root.is_symlink():
        return _invalid_pack("EVIDENCE_PACK_ROOT_SYMLINK")
    manifest_path = root / "manifest.json"
    if not root.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
        return _invalid_pack("EVIDENCE_PACK_MANIFEST_MISSING")
    try:
        descriptor = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _invalid_pack("EVIDENCE_PACK_MANIFEST_UNREADABLE")
    if not isinstance(descriptor, Mapping):
        return _invalid_pack("EVIDENCE_PACK_MANIFEST_SCHEMA_UNSUPPORTED")
    declared_hash = descriptor.get("content_hash")
    try:
        descriptor_hash = _content_hash(descriptor)
    except (TypeError, ValueError, OverflowError):
        return _invalid_pack("EVIDENCE_PACK_MANIFEST_SCHEMA_UNSUPPORTED", declared_hash)
    if not isinstance(declared_hash, str) or declared_hash != descriptor_hash:
        return _invalid_pack("EVIDENCE_PACK_MANIFEST_HASH_MISMATCH", declared_hash)
    if descriptor.get("schema_version") != EVIDENCE_PACK_SCHEMA_VERSION:
        return _invalid_pack("EVIDENCE_PACK_MANIFEST_SCHEMA_UNSUPPORTED", declared_hash)
    members = descriptor.get("members")
    if not isinstance(members, list) or not members:
        return _invalid_pack("EVIDENCE_PACK_MEMBERS_INVALID", declared_hash)
    seen: set[str] = set()
    parsed_members: dict[str, bytes] = {}
    for member in members:
        if not isinstance(member, Mapping):
            return _invalid_pack("EVIDENCE_PACK_MEMBER_SCHEMA_UNSUPPORTED", declared_hash)
        relative_path = member.get("path")
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or relative_path in seen
            or Path(relative_path).is_absolute()
            or Path(relative_path).name != relative_path
            or ".." in Path(relative_path).parts
        ):
            return _invalid_pack("EVIDENCE_PACK_MEMBER_PATH_INVALID", declared_hash)
        seen.add(relative_path)
        member_path = root / relative_path
        if member_path.is_symlink() or not member_path.is_file():
            return _invalid_pack("EVIDENCE_PACK_MEMBER_MISSING", declared_hash)
        try:
            payload = member_path.read_bytes()
        except OSError:
            return _invalid_pack("EVIDENCE_PACK_MEMBER_UNREADABLE", declared_hash)
        if member.get("content_hash") != sha256(payload):
            return _invalid_pack("EVIDENCE_PACK_MEMBER_HASH_MISMATCH", declared_hash)
        if member.get("byte_count") != len(payload):
            return _invalid_pack("EVIDENCE_PACK_MEMBER_SIZE_MISMATCH", declared_hash)
        parsed_members[relative_path] = payload
    required_members = {
        "evaluation-manifest.json",
        "evaluation-result.json",
        "policy-config.json",
        "runtime-lock.json",
        "verification-command.txt",
    }
    if seen != required_members:
        return _invalid_pack("EVIDENCE_PACK_MEMBER_SET_INVALID", declared_hash)
    actual_files = {
        item.name
        for item in root.iterdir()
        if item.is_file() and not item.is_symlink()
    }
    if actual_files != required_members | {"manifest.json"}:
        return _invalid_pack("EVIDENCE_PACK_EXTRA_MEMBER", declared_hash)
    try:
        identity_hash = _pack_identity_hash(
            str(descriptor.get("evaluation_manifest_hash")),
            str(descriptor.get("evaluation_result_hash")),
            [member for member in members if isinstance(member, Mapping)],
        )
    except (KeyError, TypeError, ValueError):
        return _invalid_pack("EVIDENCE_PACK_IDENTITY_INVALID", declared_hash)
    if descriptor.get("canonical_identity_hash") != identity_hash:
        return _invalid_pack("EVIDENCE_PACK_IDENTITY_INVALID", declared_hash)
    try:
        evaluation_manifest = json.loads(
            parsed_members["evaluation-manifest.json"].decode("utf-8")
        )
        evaluation_result = json.loads(
            parsed_members["evaluation-result.json"].decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, TypeError):
        return _invalid_pack("EVIDENCE_PACK_JSON_INVALID", declared_hash)
    manifest_report = verify_evaluation_manifest(evaluation_manifest)
    if manifest_report["state"] != "ACCEPTED":
        return _invalid_pack("EVIDENCE_PACK_EVALUATION_MANIFEST_INVALID", declared_hash)
    try:
        policy_config = json.loads(parsed_members["policy-config.json"].decode("utf-8"))
        runtime_lock = json.loads(parsed_members["runtime-lock.json"].decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError):
        return _invalid_pack("EVIDENCE_PACK_JSON_INVALID", declared_hash)
    if policy_config != {
        "policies": evaluation_manifest["policies"],
        "metrics": evaluation_manifest["metrics"],
    } or runtime_lock != evaluation_manifest["runtime_lock"]:
        return _invalid_pack("EVIDENCE_PACK_CANONICAL_MEMBER_INVALID", declared_hash)
    if (
        not isinstance(evaluation_result, Mapping)
        or _safe_content_hash(evaluation_result) != evaluation_result.get("content_hash")
        or evaluation_result.get("manifest_hash") != evaluation_manifest.get("content_hash")
        or descriptor.get("evaluation_manifest_hash") != evaluation_manifest.get("content_hash")
        or descriptor.get("evaluation_result_hash") != evaluation_result.get("content_hash")
        or evaluation_result.get("scope") != "FULL_CAMPAIGN"
    ):
        return _invalid_pack("EVIDENCE_PACK_CROSS_RECORD_BINDING_INVALID", declared_hash)
    if (
        evaluation_manifest.get("content_hash") == FROZEN_MANIFEST_CONTENT_HASH
        and declared_hash != FROZEN_EVIDENCE_PACK_HASH
    ):
        return _invalid_pack("EVIDENCE_PACK_NOT_CANONICAL", declared_hash)
    return {
        "state": "ACCEPTED",
        "reason_code": "EVIDENCE_PACK_VERIFIED",
        "pack_hash": declared_hash,
        "member_count": len(members),
        "evaluation_manifest_hash": evaluation_manifest["content_hash"],
        "evaluation_result_hash": evaluation_result["content_hash"],
    }
