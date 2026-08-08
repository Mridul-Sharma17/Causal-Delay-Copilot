from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.refuters import (
    ExactEstimatorAdapter,
    NEGATIVE_CONTROL_DIAGNOSTIC_ID,
    REFUTER_DIAGNOSTIC_IDS,
    apply_refuter_transformation,
    evaluate_negative_control,
    evaluate_refuter_statistics,
    run_refuter_battery,
)
from backend.app.diagnostics import evaluate_validity_diagnostics, publish_diagnostic_results


ROWS = [
    {
        "order_line_id": "line-001",
        "supplier_id": "supplier-a",
        "high_load_exposure": True,
        "supplier_milestone_slippage_days": 1.0,
        "covariates": {"x": 1.0},
        "negative_control": 10.0,
    },
    {
        "order_line_id": "line-002",
        "supplier_id": "supplier-a",
        "high_load_exposure": False,
        "supplier_milestone_slippage_days": 2.0,
        "covariates": {"x": 2.0},
        "negative_control": 11.0,
    },
    {
        "order_line_id": "line-003",
        "supplier_id": "supplier-a",
        "high_load_exposure": True,
        "supplier_milestone_slippage_days": 3.0,
        "covariates": {"x": 3.0},
        "negative_control": 12.0,
    },
    {
        "order_line_id": "line-004",
        "supplier_id": "supplier-b",
        "high_load_exposure": False,
        "supplier_milestone_slippage_days": 4.0,
        "covariates": {"x": 4.0},
        "negative_control": 13.0,
    },
    {
        "order_line_id": "line-005",
        "supplier_id": "supplier-b",
        "high_load_exposure": False,
        "supplier_milestone_slippage_days": 5.0,
        "covariates": {"x": 5.0},
        "negative_control": 14.0,
    },
    {
        "order_line_id": "line-006",
        "supplier_id": "supplier-c",
        "high_load_exposure": True,
        "supplier_milestone_slippage_days": 6.0,
        "covariates": {"x": 6.0},
        "negative_control": 15.0,
    },
]


SEED_CONTEXT = {
    "root_seed": 42,
    "dataset_version_id": "dataset-v1",
    "causal_question_id": "supplier-congestion-to-milestone-slippage",
    "causal_question_version": "v1",
    "engine_config_id": "core-local-cpu-hgb-doubleml",
    "engine_config_version": "v1",
    "suite_id": "core-supplier-congestion-suite",
    "suite_version": "v1",
    "validity_policy_id": "causal-validity-verdict-policy",
    "validity_policy_version": "1",
}

PRIMARY_OUTER_SPLITS = [
    {
        "train": ["line-001", "line-002", "line-004", "line-005"],
        "test": ["line-003", "line-006"],
    }
]
PRIMARY_ARTIFACTS = {
    "outer_splits": PRIMARY_OUTER_SPLITS,
    "inner_splits": PRIMARY_OUTER_SPLITS,
    "canonical_row_ids": [row["order_line_id"] for row in ROWS],
    "propensity_predictions": {
        row["order_line_id"]: [0.5, 0.5] for row in ROWS
    },
    "fold_provenance_verified": True,
    "propensity_provenance_verified": True,
    "propensity_provenance_ref": "artifact://primary-propensity-v1",
    "support": {
        "state": "supported",
        "total_rows_supported": True,
        "supplier_supported": True,
        "mixed_supplier_supported": True,
        "clustered_inference_supported": True,
        "two_arm_training_supported": True,
    },
}

NEGATIVE_ROWS = [
    {
        "order_line_id": f"negative-line-{index:02d}",
        "supplier_id": f"negative-supplier-{index:02d}",
        "high_load_exposure": index % 2 == 0,
        "supplier_milestone_slippage_days": float(index + 1),
        "covariates": {"x": float(index + 1)},
        "negative_control": float(index + 10),
    }
    for index in range(10)
]
NEGATIVE_FOLDS = [
    {
        "repeat_index": repeat_index,
        "outer_fold_index": fold_index,
        "train": [
            row["order_line_id"]
            for row in NEGATIVE_ROWS
            if row["order_line_id"] not in {
                NEGATIVE_ROWS[2 * fold_index]["order_line_id"],
                NEGATIVE_ROWS[2 * fold_index + 1]["order_line_id"],
            }
        ],
        "test": [
            NEGATIVE_ROWS[2 * fold_index]["order_line_id"],
            NEGATIVE_ROWS[2 * fold_index + 1]["order_line_id"],
        ],
    }
    for repeat_index in range(2)
    for fold_index in range(5)
]
NEGATIVE_ARTIFACTS = {
    "outer_splits": NEGATIVE_FOLDS,
    "inner_splits": NEGATIVE_FOLDS,
    "canonical_row_ids": [row["order_line_id"] for row in NEGATIVE_ROWS],
    "propensity_predictions": {
        row["order_line_id"]: [0.5, 0.5] for row in NEGATIVE_ROWS
    },
    "fold_provenance_verified": True,
    "propensity_provenance_verified": True,
    "propensity_provenance_ref": "artifact://primary-propensity-v1",
    "support": {
        "state": "supported",
        "total_rows_supported": True,
        "supplier_supported": True,
        "mixed_supplier_supported": True,
        "clustered_inference_supported": True,
        "two_arm_training_supported": True,
    },
}


def _negative_control_spec() -> dict[str, object]:
    return {
        "control_id": "reviewed-negative-control",
        "field": "negative_control",
        "eligible": True,
        "pre_exposure_verified": True,
        "causal_graph_disjoint": True,
        "excluded_from_primary": True,
        "provenance_verified": True,
        "temporal_verified": True,
        "propensity_provenance_verified": True,
    }


def _estimator_receipt(request: dict[str, object]) -> dict[str, object]:
    adapter_id = request.get("refuter_adapter_id", request.get("estimator_adapter_id"))
    adapter_version = request.get(
        "refuter_adapter_version", request.get("estimator_adapter_version")
    )
    return {
        "schema_version": "exact-estimator-receipt.v1",
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "estimator_library": "DoubleML",
        "estimator_library_version": "0.11.3",
        "estimator_contract": request["estimator_contract"],
        "n_jobs_cv": 1,
        "execution_status": "complete",
        "second_overlap_trim": False,
        "adapter_matrix": request["adapter_matrix"],
    }


def _seed_records(request: dict[str, object]) -> list[dict[str, object]]:
    components = {
        "placebo_treatment_within_supplier": {
            "outer_split",
            "inner_calibration_split",
            "propensity_learner",
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        },
        "random_common_cause_standard_normal": {
            "propensity_learner",
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        },
        "data_subset_supplier_arm_80pct": {
            "propensity_learner",
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        },
        "dummy_outcome_standard_normal": {
            "outcome_learner_unexposed",
            "outcome_learner_exposed",
        },
    }[request["refuter_id"]]
    return [
        {
            "component": component,
            "seed": (
                int(request["simulation_root_seed"])
                + repeat_index * 5
                + (outer_fold_index or 0)
            )
            % 2**32,
            "coordinates": {
                "variant_id": request["refuter_id"],
                "repeat_index": repeat_index,
                "outer_fold_index": outer_fold_index,
                "inner_fold_index": None,
            },
        }
        for component in sorted(components)
        for repeat_index in (0, 1)
        for outer_fold_index in (
            (None,) if component == "outer_split" else (0, 1, 2, 3, 4)
        )
    ]


def test_transformations_preserve_the_declared_grouped_design() -> None:
    original = deepcopy(ROWS)

    placebo = apply_refuter_transformation(
        "placebo_treatment_within_supplier", ROWS, simulation_root_seed=7
    )["rows"]
    subset = apply_refuter_transformation(
        "data_subset_supplier_arm_80pct", ROWS, simulation_root_seed=7
    )["rows"]
    common_cause = apply_refuter_transformation(
        "random_common_cause_standard_normal", ROWS, simulation_root_seed=7
    )["rows"]
    dummy = apply_refuter_transformation(
        "dummy_outcome_standard_normal", ROWS, simulation_root_seed=7
    )["rows"]

    assert ROWS == original
    assert [row["order_line_id"] for row in placebo] == [
        row["order_line_id"] for row in ROWS
    ]
    assert sum(row["high_load_exposure"] for row in placebo if row["supplier_id"] == "supplier-a") == 2
    assert [
        row["high_load_exposure"] for row in placebo if row["supplier_id"] == "supplier-b"
    ] == [False, False]

    assert len(subset) == 6
    assert sum(row["high_load_exposure"] for row in subset) == 3
    assert all(
        row["order_line_id"] in {item["order_line_id"] for item in ROWS}
        for row in subset
    )

    feature_name = "refuter_random_common_cause"
    assert all(feature_name in row["covariates"] for row in common_cause)
    assert all(feature_name not in row["covariates"] for row in ROWS)
    assert [row["high_load_exposure"] for row in dummy] == [
        row["high_load_exposure"] for row in ROWS
    ]
    assert [row["covariates"] for row in dummy] == [row["covariates"] for row in ROWS]
    assert [row["supplier_milestone_slippage_days"] for row in dummy] != [
        row["supplier_milestone_slippage_days"] for row in ROWS
    ]

    shuffled = [ROWS[3], ROWS[0], ROWS[5], ROWS[1], ROWS[4], ROWS[2]]
    assert [
        row["order_line_id"]
        for row in apply_refuter_transformation(
            "dummy_outcome_standard_normal", shuffled, simulation_root_seed=7
        )["rows"]
    ] == [row["order_line_id"] for row in shuffled]


def test_refuter_statistics_uses_strict_p_value_and_even_median_rules() -> None:
    estimates = [-1.0] * 95 + [0.0] * 5

    result = evaluate_refuter_statistics(
        estimates,
        reference_target=0.0,
        primary_atte_standard_error=2.0,
    )

    assert result["p_value"] == pytest.approx(0.05)
    assert result["median_simulation_estimate"] == -1.0
    assert result["passed"] is False

    equality = evaluate_refuter_statistics(
        [0.0] * 100,
        reference_target=0.0,
        primary_atte_standard_error=0.0,
    )
    assert equality["p_value"] == 1.0
    assert equality["passed"] is True


def test_battery_runs_400_seeded_adapter_calls_and_replays_exactly() -> None:
    calls: list[dict[str, object]] = []

    def adapter(request: dict[str, object]) -> dict[str, object]:
        calls.append(request)
        target = request["reference_target"]
        return {
            "status": "estimated",
            "estimate": target,
            "standard_error": 1.0,
            "estimator_receipt": _estimator_receipt(request),
            "seed_records": _seed_records(request),
        }

    first = run_refuter_battery(
        ROWS,
        primary_effect={"estimate": 1.0, "standard_error": 1.0},
        estimator_adapter=ExactEstimatorAdapter(adapter),
        primary_artifacts=PRIMARY_ARTIFACTS,
        **SEED_CONTEXT,
    )
    first_calls = deepcopy(calls)
    calls.clear()
    second = run_refuter_battery(
        ROWS,
        primary_effect={"estimate": 1.0, "standard_error": 1.0},
        estimator_adapter=ExactEstimatorAdapter(adapter),
        primary_artifacts=PRIMARY_ARTIFACTS,
        **SEED_CONTEXT,
    )

    assert len(calls) == 400
    assert first["content_hash"] == second["content_hash"]
    assert first["base_digest"] == second["base_digest"]
    assert [item["diagnostic_id"] for item in first["diagnostics"]] == list(
        REFUTER_DIAGNOSTIC_IDS
    )
    assert all(item["status"] == "PASS" for item in first["diagnostics"])
    coordinates = {
        (item["refuter_id"], item["simulation_index"], item["simulation_root_seed"])
        for item in first_calls
    }
    assert len(coordinates) == 400
    assert len({item["simulation_root_seed"] for item in first_calls}) == 400
    assert [
        item["simulation_root_seed"] for item in first_calls
    ] == [item["simulation_root_seed"] for item in calls]


def test_refuter_adapter_not_run_remains_not_run() -> None:
    result = run_refuter_battery(
        ROWS,
        primary_effect={"estimate": 1.0, "standard_error": 1.0},
        estimator_adapter=ExactEstimatorAdapter(lambda request: {"status": "not_run"}),
        primary_artifacts=PRIMARY_ARTIFACTS,
        **SEED_CONTEXT,
    )

    assert [item["status"] for item in result["diagnostics"]] == ["NOT_RUN"] * 4
    assert all(item["observed"] is None for item in result["diagnostics"])
    assert all(item["result"] is None for item in result["diagnostics"])
    assert all(
        item["upstream_trigger"] == "REFUTER_ADAPTER_NOT_RUN"
        for item in result["diagnostics"]
    )


def test_refuter_requires_primary_execution_artifacts() -> None:
    calls: list[dict[str, object]] = []

    def adapter(request: dict[str, object]) -> dict[str, object]:
        calls.append(request)
        return {"status": "estimated", "estimate": 0.0, "seed_records": [{"component": "x", "seed": 1}]}

    result = run_refuter_battery(
        ROWS,
        primary_effect={"estimate": 1.0, "standard_error": 1.0},
        estimator_adapter=ExactEstimatorAdapter(adapter),
        **SEED_CONTEXT,
    )

    assert [item["status"] for item in result["diagnostics"]] == ["UNAVAILABLE"] * 4
    assert calls == []


def test_negative_control_uses_frozen_coverage_and_closed_equivalence_band() -> None:
    calls: list[dict[str, object]] = []

    def adapter(request: dict[str, object]) -> dict[str, object]:
        calls.append(request)
        return {
            "status": "estimated",
            "estimate": 0.20,
            "ci_lower": -0.10,
            "ci_upper": 0.10,
            "p_value": 0.0,
            "estimator_receipt": _estimator_receipt(request),
        }

    result = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control=_negative_control_spec(),
        estimator_adapter=ExactEstimatorAdapter(adapter),
        primary_artifacts=NEGATIVE_ARTIFACTS,
    )

    assert result["diagnostic_id"] == NEGATIVE_CONTROL_DIAGNOSTIC_ID
    assert result["status"] == "PASS"
    assert result["threshold"]["equivalence_lower"] == -0.10
    assert result["threshold"]["equivalence_upper"] == 0.10
    assert result["observed"]["overall_coverage"] == 1.0
    assert result["observed"]["standard_deviation"] > 0.0
    assert len(calls) == 1
    assert len(calls[0]["rows"]) == len(NEGATIVE_ROWS)
    assert calls[0]["outcome_standardization"]["population_standard_deviation"] > 0.0


def test_negative_control_keeps_unavailable_unsupported_failed_and_not_run_distinct() -> None:
    unavailable = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control=_negative_control_spec(),
        estimator_adapter=None,
    )
    unsupported = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control={
            **_negative_control_spec(),
            "pre_exposure_verified": False,
        },
        estimator_adapter=ExactEstimatorAdapter(lambda request: {}),
    )
    missing_artifacts = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control=_negative_control_spec(),
        estimator_adapter=ExactEstimatorAdapter(lambda request: {}),
    )
    failed = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control=_negative_control_spec(),
        estimator_adapter=ExactEstimatorAdapter(
            lambda request: (_ for _ in ()).throw(RuntimeError("boom"))
        ),
        primary_artifacts=NEGATIVE_ARTIFACTS,
    )
    not_run = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control=_negative_control_spec(),
        estimator_adapter=ExactEstimatorAdapter(lambda request: {"status": "not_run"}),
        primary_artifacts=NEGATIVE_ARTIFACTS,
        upstream_trigger="ENGINE_NOT_ESTIMABLE",
    )
    adapter_not_run = evaluate_negative_control(
        NEGATIVE_ROWS,
        negative_control=_negative_control_spec(),
        estimator_adapter=ExactEstimatorAdapter(lambda request: {"status": "not_run"}),
        primary_artifacts=NEGATIVE_ARTIFACTS,
    )

    assert unavailable["status"] == "UNAVAILABLE"
    assert unsupported["status"] == "UNSUPPORTED"
    assert missing_artifacts["status"] == "UNAVAILABLE"
    assert failed["status"] == "FAILED"
    assert not_run["status"] == "NOT_RUN"
    assert not_run["upstream_trigger"] == "ENGINE_NOT_ESTIMABLE"
    assert adapter_not_run["status"] == "NOT_RUN"
    assert adapter_not_run["upstream_trigger"] == "NEGATIVE_CONTROL_ADAPTER_NOT_RUN"
    assert adapter_not_run["result"] is None


def test_validity_disclosure_keeps_added_checks_visible_after_upstream_short_circuit() -> None:
    results = evaluate_validity_diagnostics(
        engine_result={"status": "abstained"},
        eligibility={
            "state": "scientifically_unavailable",
            "eligibility_codes": ["COHORT_SUPPORT_INSUFFICIENT"],
        },
        analysis_run_id="analysis-run-00000000-0000-4000-8000-000000000029",
        bundle_manifest_hash="sha256:" + "b" * 64,
    )

    assert len(results) == 9
    assert [item["status"] for item in results[4:]] == ["NOT_RUN"] * 5
    assert results[4]["upstream_trigger"] == "COHORT_SUPPORT_INSUFFICIENT"


def test_extended_diagnostic_records_can_be_verified_and_published_in_order() -> None:
    analysis_run_id = "analysis-run-00000000-0000-4000-8000-000000000030"
    bundle_manifest_hash = "sha256:" + "c" * 64
    results = evaluate_validity_diagnostics(
        engine_result={"status": "abstained"},
        eligibility={
            "state": "scientifically_unavailable",
            "eligibility_codes": ["COHORT_SUPPORT_INSUFFICIENT"],
        },
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
    )

    published = publish_diagnostic_results(
        results,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
    )

    assert [item["diagnostic_id"] for item in published] == [
        "primary_interval",
        "covariate_balance",
        "overlap",
        "inherited_eligibility",
        *REFUTER_DIAGNOSTIC_IDS,
        NEGATIVE_CONTROL_DIAGNOSTIC_ID,
    ]
