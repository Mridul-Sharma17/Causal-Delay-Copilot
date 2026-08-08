from __future__ import annotations

import re
from pathlib import Path
import time

from fastapi.testclient import TestClient

from backend.app.analysis_runs import (
    ENGINE_INPUT_SCHEMA_VERSION,
    analysis_run_id_for_operation,
    materialize_propensity_and_s9,
    scientific_json,
    scientific_sha256,
    validate_suite_request,
)
from backend.app.main import create_app
from backend.app.settings import DeliveryProfile, Settings


def _suite_request() -> dict[str, object]:
    variants = []
    for variant_id, threshold in (
        ("primary", "nearest-rank-percentile-0.67.v1"),
        ("stricter_threshold", "nearest-rank-percentile-0.75.v1"),
        ("short_history", "nearest-rank-percentile-0.67.v1"),
        ("long_history", "nearest-rank-percentile-0.67.v1"),
    ):
        variants.append(
            {
                "variant_id": variant_id,
                "threshold_rule_ref": threshold,
                "selector_refs": ["history-lookback.v1", "estimator-window.v1"],
                "cohort_stage_summaries": {
                    "S8_OUTCOME": {"status": "failed", "count": 0}
                },
                "upstream_status": "scientifically_unavailable",
                "scientific_code": "COHORT_SUPPORT_INSUFFICIENT",
                "gate_stage": "S8_OUTCOME",
                "evidence_refs": ["lineage:dataset-1"],
            }
        )
    return {
        "engine_input_schema_version": ENGINE_INPUT_SCHEMA_VERSION,
        "engine_output_schema_version": "causal-engine-suite-result.v2",
        "error_registry_version": "causal-engine-errors.v1",
        "causal_question_id": "supplier-congestion-to-milestone-slippage",
        "causal_question_version": "v1",
        "engine_config_id": "core-local-cpu-hgb-doubleml",
        "engine_config_version": "v1",
        "dataset_version_id": "dv-test",
        "intended_role": "semi_synthetic_hero",
        "target_milestone_kind": "supplier_handoff",
        "canonical_slippage_duration_basis": "CALENDAR_DAY",
        "trigger_mode": "reactive",
        "observation_cutoff": {
            "state": "present",
            "value": {
                "kind": "date",
                "source_value": "2026-01-01",
                "normalized_value": "2026-01-01",
                "precision": "day",
                "timezone_status": "not_applicable",
                "source_timezone": {"state": "not_applicable"},
            },
        },
        "suite_id": "core-supplier-congestion-suite",
        "suite_version": "v1",
        "variant_inputs": variants,
        "adjustment_set": {
            "schema_version": "adjustment-set.v1",
            "adjustment_set_id": "core-pre-treatment-adjustment-set",
            "adjustment_set_version": "v1",
            "fields": [
                "material_class",
                "complexity_class",
                "quantity",
                "value",
                "project_id",
                "project_phase",
                "urgency_class",
                "geography_code",
                "contract_form",
            ],
        },
        "propensity_spec": {
            "propensity_spec_id": "supplier-grouped-calibrated-hgb-5x2",
            "propensity_spec_version": "v1",
            "training_stage": "S8_OUTCOME",
            "feature_schema_ref": {
                "adjustment_set_id": "core-pre-treatment-adjustment-set",
                "adjustment_set_version": "v1",
            },
            "outer_splitter": "sklearn.model_selection.StratifiedGroupKFold",
            "outer_n_splits": 5,
            "outer_n_repeats": 2,
            "outer_stratify": "high_load_exposure",
            "outer_group": "supplier_id",
            "outer_shuffle": True,
            "base_learner": "sklearn.ensemble.HistGradientBoostingClassifier",
            "base_learner_parameters": {
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
            },
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
            "seed_policy_id": "sha256-coordinate-seeds",
            "seed_policy_version": "v1",
        },
        "root_seed": 17,
        "evidence_refs": ["lineage:dataset-1"],
    }


def _client(state_root: Path, *, start_operation_runner: bool = False) -> TestClient:
    settings = Settings(
        profile=DeliveryProfile.LOCAL_FALLBACK,
        state_root=state_root,
        public_origin="http://127.0.0.1:8000",
    )
    return TestClient(create_app(settings, start_operation_runner=start_operation_runner))


def test_scientific_encoding_is_float_stable_and_excludes_delivery_metadata() -> None:
    assert scientific_json({"value": 0.0, "text": "e\u0301"}) == (
        '{"text":"é","value":"f64:0x0.0p+0"}'
    )
    base = _suite_request()
    with_delivery_metadata = {
        **base,
        "delivery_metadata": {
            "run_id": "analysis-run-transient",
            "ui_route": "/workspace",
        },
    }
    assert scientific_sha256(base) == scientific_sha256(with_delivery_metadata)


def test_suite_request_validation_has_closed_schema_and_fixed_variant_order() -> None:
    validated = validate_suite_request(_suite_request())
    assert validated.request["engine_input_schema_version"] == ENGINE_INPUT_SCHEMA_VERSION
    assert [
        item["variant_id"] for item in validated.request["variant_inputs"]
    ] == ["primary", "stricter_threshold", "short_history", "long_history"]

    invalid = _suite_request()
    invalid["engine_input_schema_version"] = "causal-engine-suite-request.v1"
    try:
        validate_suite_request(invalid)
    except ValueError as error:
        assert str(error) == "ENGINE_INPUT_SCHEMA_UNSUPPORTED"
    else:
        raise AssertionError("unsupported suite schema must fail closed")


def test_released_s8_rows_are_sorted_and_content_bound() -> None:
    request = _suite_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    variant.update(
        {
            "upstream_status": "released",
            "rows": [
                {
                    "order_line_id": "line-2",
                    "supplier_id": "supplier-2",
                    "high_load_exposure": False,
                    "supplier_milestone_slippage_days": 1.5,
                    "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
                    "supplier_milestone_late": True,
                    "load_percentile": 0.25,
                    "covariates": {
                        name: {"state": "missing"}
                        for name in request["adjustment_set"]["fields"]
                    },
                    "lineage_refs": ["lineage:line-2"],
                }
            ],
        }
    )
    variant.pop("scientific_code", None)
    variant.pop("gate_stage", None)
    variant["selector_refs"] = sorted(variant["selector_refs"])
    variant["s8_identity_hash"] = scientific_sha256(["line-2"])
    variant["s8_content_hash"] = scientific_sha256(
        {
            key: value
            for key, value in variant.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )
    validated = validate_suite_request(request)
    assert validated.request["variant_inputs"][0]["rows"][0]["order_line_id"] == "line-2"


def test_fresh_analysis_admission_exposes_occurrence_identity_and_replays_exactly(
    tmp_path: Path,
) -> None:
    with _client(tmp_path / "state") as client:
        request = {
            "idempotency_key": "fresh-analysis-test",
            "operation_kind": "FRESH_ANALYSIS",
            "memory_required_bytes": 1024,
            "request": {"suite_request": _suite_request()},
        }
        created = client.post("/api/operations", json=request)
        replay = client.post("/api/operations", json=request)

        assert created.status_code == 202
        assert replay.status_code == 200
        first_operation = created.json()["operation"]
        replay_operation = replay.json()["operation"]
        status = first_operation["analysis_run"]

        assert replay_operation["operation_id"] == first_operation["operation_id"]
        assert replay_operation["analysis_run"]["analysis_run_id"] == status[
            "analysis_run_id"
        ]
        assert re.fullmatch(
            r"analysis-run-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            status["analysis_run_id"],
        )
        assert status["scientific_request_digest"].startswith("sha256:")
        assert status["delivery_mode"] == "fresh_execution"
        assert status["verification_state"] == "pending"

        read_back = client.get(
            f"/api/analysis-runs/{status['analysis_run_id']}"
        )
        assert read_back.status_code == 200
        assert read_back.json() == status


def test_fresh_analysis_rejects_missing_root_seed_at_the_public_boundary(
    tmp_path: Path,
) -> None:
    with _client(tmp_path / "state") as client:
        response = client.post(
            "/api/operations",
            json={
                "idempotency_key": "fresh-analysis-no-seed",
                "operation_kind": "FRESH_ANALYSIS",
                "memory_required_bytes": 1024,
                "request": {"investigation_request_id": "ir-missing"},
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": "ENGINE_INPUT_SCHEMA_UNSUPPORTED",
        "recovery_action": "PROVIDE_AN_EXPLICIT_ROOT_SEED_AND_RETRY",
    }


def test_analysis_run_id_is_derived_from_a_v4_operation_identity() -> None:
    operation_id = "operation-12345678-1234-4234-8234-123456789abc"
    assert analysis_run_id_for_operation(operation_id) == (
        "analysis-run-12345678-1234-4234-8234-123456789abc"
    )


def test_validation_only_worker_ends_in_typed_abstention_without_an_estimate(
    tmp_path: Path,
) -> None:
    with _client(tmp_path / "state", start_operation_runner=True) as client:
        response = client.post(
            "/api/operations",
            json={
                "idempotency_key": "fresh-analysis-worker-test",
                "operation_kind": "FRESH_ANALYSIS",
                "memory_required_bytes": 1024,
                "request": {"suite_request": _suite_request()},
            },
        )
        operation_id = response.json()["operation"]["operation_id"]
        terminal = response.json()["operation"]
        for _ in range(100):
            terminal = client.get(f"/api/operations/{operation_id}").json()
            if terminal["state"] in {
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                "TIMED_OUT",
                "INTERRUPTED",
                "REJECTED",
            }:
                break
            time.sleep(0.05)

    assert terminal["state"] == "SUCCEEDED"
    assert terminal["analysis_run"]["status"] == "ABSTAINED"
    assert terminal["analysis_run"]["scientific_outcome"] == "abstained"
    assert terminal["analysis_run"]["estimator_executed"] is False
    detail = terminal["analysis_run"]["fresh_run_detail"]
    assert detail["schema_version"] == "analysis-run-safe-detail.v1"
    assert detail["execution_state"] == "complete"
    assert detail["component_failures"] == []
    assert "lineage:dataset-1" not in str(detail)


def _released_propensity_rows(request: dict[str, object]) -> list[dict[str, object]]:
    adjustment_set = request["adjustment_set"]
    assert isinstance(adjustment_set, dict)
    fields = adjustment_set["fields"]
    assert isinstance(fields, list)
    rows: list[dict[str, object]] = []
    for supplier_index in range(30):
        for within_supplier in range(2):
            row_index = supplier_index * 2 + within_supplier
            rows.append(
                {
                    "order_line_id": f"line-{row_index:03d}",
                    "supplier_id": f"supplier-{supplier_index:03d}",
                    "high_load_exposure": bool((supplier_index + within_supplier) % 2),
                    "supplier_milestone_slippage_days": float(row_index % 17),
                    "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
                    "supplier_milestone_late": bool(row_index % 3),
                    "load_percentile": (row_index % 10) / 10,
                    "covariates": {
                        field: {"state": "present", "value": float(row_index + offset)}
                        for offset, field in enumerate(fields)
                    },
                    "lineage_refs": [f"lineage:line-{row_index:03d}"],
                }
            )
    return rows


def test_propensity_stage_materializes_grouped_oof_mean_s9_and_external_slots() -> None:
    request = _suite_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    rows = _released_propensity_rows(request)
    variant.update(
        {
            "upstream_status": "released",
            "rows": rows,
            "cohort_stage_summaries": {
                "S8_OUTCOME": {
                    "status": "passed",
                    "selected_count": len(rows),
                    "selected_identity_hash": scientific_sha256(
                        [row["order_line_id"] for row in rows]
                    ),
                }
            },
        }
    )
    variant.pop("scientific_code", None)
    variant.pop("gate_stage", None)
    variant["selector_refs"] = sorted(variant["selector_refs"])
    variant["s8_identity_hash"] = scientific_sha256(
        [row["order_line_id"] for row in rows]
    )
    variant["s8_content_hash"] = scientific_sha256(
        {
            key: value
            for key, value in variant.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )

    result = materialize_propensity_and_s9(request)
    primary = result["variants"]["primary"]

    assert result["schema_version"] == "analysis-run-propensity-result.v1"
    assert result["status"] == "abstained"
    assert result["reason_code"] == "OVERLAP_COHORT_INSUFFICIENT"
    assert primary["state"] == "materialized"
    assert primary["folds"]["outer_repeats"] == 2
    assert primary["folds"]["outer_folds_per_repeat"] == 5
    assert len(primary["propensity_predictions"]) == len(rows)
    for repeat_index in range(2):
        repeat_folds = [
            item
            for item in primary["fold_assignments"]
            if item["repeat_index"] == repeat_index
        ]
        assert len(repeat_folds) == 5
        assert sorted(
            row_id
            for item in repeat_folds
            for row_id in item["test_ids"]
        ) == [f"line-{index:03d}" for index in range(len(rows))]
        assert all(
            set(item["train_supplier_ids"]).isdisjoint(item["test_supplier_ids"])
            for item in repeat_folds
        )
    assert primary["s9"]["retained_ids"] == [
        item["row_id"]
        for item in primary["propensity_predictions"]
        if 0.10 <= item["mean"] <= 0.90
    ]
    assert all(
        item["external_prediction_slots"] == [item["mean"], item["mean"]]
        for item in primary["propensity_predictions"]
        if item["row_id"] in primary["s9"]["retained_ids"]
    )
    assert result["safe_detail"]["component_failures"] == []
    assert "line-000" not in str(result["safe_detail"])


def _released_primary_request(*, subject: bool = False) -> dict[str, object]:
    request = _suite_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    rows = _released_propensity_rows(request)
    variant.update(
        {
            "upstream_status": "released",
            "rows": rows,
            "cohort_stage_summaries": {
                "S8_OUTCOME": {
                    "status": "passed",
                    "selected_count": len(rows),
                    "selected_identity_hash": scientific_sha256(
                        [row["order_line_id"] for row in rows]
                    ),
                }
            },
        }
    )
    variant.pop("scientific_code", None)
    variant.pop("gate_stage", None)
    variant["selector_refs"] = sorted(variant["selector_refs"])
    variant["s8_identity_hash"] = scientific_sha256(
        [row["order_line_id"] for row in rows]
    )
    variant["s8_content_hash"] = scientific_sha256(
        {
            key: value
            for key, value in variant.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )
    if subject:
        fields = request["adjustment_set"]["fields"]
        assert isinstance(fields, list)
        request["subject"] = {
            "state": "eligible",
            "subject_id": "current-subject",
            "profile": {
                "adjustment_inputs": {
                    field: {"state": "present", "value": float(offset)}
                    for offset, field in enumerate(fields)
                }
            },
        }
    return request


def test_propensity_stage_subject_score_uses_all_ten_primary_outer_models() -> None:
    result = materialize_propensity_and_s9(_released_primary_request(subject=True))
    subject = result["variants"]["primary"]["subject_propensity"]

    assert subject["state"] == "present"
    assert len(subject["repeat_fold_predictions"]) == 10
    assert 0.0 <= subject["value"] <= 1.0
    assert subject["aggregation"] == "arithmetic_mean_of_ten_primary_outer_fold_models"


def test_propensity_stage_is_deterministic_for_identical_request() -> None:
    request = _released_primary_request()
    first = materialize_propensity_and_s9(request)
    second = materialize_propensity_and_s9(request)

    first_primary = first["variants"]["primary"]
    second_primary = second["variants"]["primary"]
    assert first["scientific_request_digest"] == second["scientific_request_digest"]
    assert first_primary["fold_assignments"] == second_primary["fold_assignments"]
    assert first_primary["propensity_predictions"] == second_primary["propensity_predictions"]
    assert first_primary["s9"] == second_primary["s9"]


def test_propensity_stage_returns_safe_component_failure_without_partial_s9() -> None:
    request = _released_primary_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    rows = variant["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["high_load_exposure"] = False
    variant["s8_content_hash"] = scientific_sha256(
        {
            key: value
            for key, value in variant.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )

    result = materialize_propensity_and_s9(request)
    primary = result["variants"]["primary"]

    assert result["status"] == "failed"
    assert primary["state"] == "failed"
    assert primary["reason_code"] == "ENGINE_SPLIT_INFEASIBLE"
    assert primary["component_failures"] == [
        {
            "component": "propensity_ensemble",
            "variant_id": "primary",
            "code": "ENGINE_SPLIT_INFEASIBLE",
        }
    ]
    assert primary.get("s9") is None
    assert "line-000" not in str(result["safe_detail"])
