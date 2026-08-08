from __future__ import annotations

import re
from pathlib import Path
import time

from fastapi.testclient import TestClient

from backend.app.analysis_runs import (
    ENGINE_INPUT_SCHEMA_VERSION,
    analysis_run_id_for_operation,
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
