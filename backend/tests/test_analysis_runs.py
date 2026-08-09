from __future__ import annotations

from copy import deepcopy
import json
import re
from pathlib import Path
import time

from fastapi.testclient import TestClient

from backend.app import analysis_runs as analysis_runs_module
from backend.app.analysis_runs import (
    ENGINE_INPUT_SCHEMA_VERSION,
    analysis_run_id_for_operation,
    build_reproduction_projection,
    compare_reproduction_projections,
    estimate_primary_atte_and_context,
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


def test_reproduction_projection_ignores_run_identity_and_compares_declared_tolerances() -> None:
    target = {
        "engine_request": {
            "dataset_version_id": "dataset-1",
            "root_seed": 17,
            "analysis_run_id": "analysis-run-target",
            "accepted_at": "2026-08-09T00:00:00+00:00",
        },
        "runtime_fingerprint": {
            "schema_version": "analysis-runtime-fingerprint.v1",
            "python": {"version": "3.12.13"},
            "analysis_run_id": "analysis-run-target",
        },
        "engine_result": {
            "status": "estimated",
            "estimate": 1.0,
            "analysis_run_id": "analysis-run-target",
        },
    }
    candidate = {
        **target,
        "engine_request": {
            **target["engine_request"],
            "analysis_run_id": "analysis-run-candidate",
            "accepted_at": "2026-08-09T00:01:00+00:00",
        },
        "runtime_fingerprint": {
            **target["runtime_fingerprint"],
            "analysis_run_id": "analysis-run-candidate",
        },
        "engine_result": {
            **target["engine_result"],
            "analysis_run_id": "analysis-run-candidate",
            "estimate": 1.000000001,
        },
    }

    expected = build_reproduction_projection(target)
    observed = build_reproduction_projection(candidate)
    comparison = compare_reproduction_projections(expected, observed)

    assert expected["schema_version"] == "analysis-run-reproduction-projection.v1"
    assert "analysis_run_id" not in json.dumps(expected)
    assert comparison["status"] == "passed"
    assert comparison["declared_tolerances"]["schema_version"] == (
        "causal-engine-numeric-tolerances.v1"
    )


def test_reproduction_projection_mismatch_is_typed_and_fails_closed() -> None:
    expected = build_reproduction_projection(
        {"engine_result": {"status": "abstained", "reason_code": "A"}}
    )
    observed = build_reproduction_projection(
        {"engine_result": {"status": "abstained", "reason_code": "B"}}
    )

    comparison = compare_reproduction_projections(expected, observed)

    assert comparison["status"] == "failed"
    assert comparison["failure_code"] == "RUN_REPRODUCIBILITY_VIOLATION"
    assert comparison["comparison_classes"][0]["status"] == "failed"


def test_reproduction_member_hash_mismatch_is_typed_and_fails_closed() -> None:
    expected = build_reproduction_projection(
        {"engine_result": {"status": "abstained", "reason_code": "A"}}
    )
    observed = build_reproduction_projection(
        {"engine_result": {"status": "abstained", "reason_code": "A"}}
    )

    comparison = compare_reproduction_projections(
        expected,
        observed,
        expected_member_hashes={"engine_result": "sha256:expected"},
        observed_member_hashes={"engine_result": "sha256:observed"},
    )

    assert comparison["status"] == "failed"
    assert comparison["failure_code"] == "RUN_REPRODUCIBILITY_VIOLATION"
    assert comparison["comparison_classes"][0]["status"] == "failed"


def test_reproduction_projection_preserves_scientific_null_presence() -> None:
    expected = build_reproduction_projection(
        {"engine_result": {"status": "abstained", "reason_code": None}}
    )
    observed = build_reproduction_projection(
        {"engine_result": {"status": "abstained"}}
    )

    comparison = compare_reproduction_projections(expected, observed)

    assert comparison["status"] == "failed"
    assert comparison["failure_code"] == "RUN_REPRODUCIBILITY_VIOLATION"


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
    assert terminal["analysis_run"]["lifecycle"] == "sealed"
    assert terminal["analysis_run"]["verification_state"] == "machine_verified"
    assert terminal["analysis_run"]["availability_state"] == "available"
    assert terminal["analysis_run"]["bundle_manifest_hash"].startswith("sha256:")
    assert len(terminal["analysis_run"]["diagnostics"]) == 14
    assert terminal["analysis_run"]["diagnostic_summary"]["diagnostic_count"] == 14
    assert terminal["analysis_run"]["robustness_grade"]["grade"] == "UNAVAILABLE"
    assert terminal["analysis_run"]["evidence_verdict"]["verdict_code"] == "INSUFFICIENT"
    assert terminal["analysis_run"]["primary_result"] is None
    detail = terminal["analysis_run"]["fresh_run_detail"]
    assert detail["schema_version"] == "analysis-run-safe-detail.v1"
    assert detail["execution_state"] == "complete"
    assert detail["component_failures"] == []
    assert "lineage:dataset-1" not in str(detail)


def test_corrupt_fresh_bundle_is_suppressed_from_the_current_read_model(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    with _client(state_root, start_operation_runner=True) as client:
        response = client.post(
            "/api/operations",
            json={
                "idempotency_key": "fresh-analysis-corrupt-bundle-test",
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
        analysis_run_id = terminal["analysis_run"]["analysis_run_id"]
        manifest_path = (
            state_root
            / "artifacts"
            / "runs"
            / analysis_run_id
            / "manifest.json"
        )
        result_path = (
            state_root
            / "artifacts"
            / "runs"
            / operation_id
            / "analysis-run-result.json"
        )
        original_result = result_path.read_text(encoding="utf-8")
        tampered_result = json.loads(original_result)
        tampered_result["diagnostics"][0]["reason"] = "tampered"
        result_path.write_text(
            json.dumps(tampered_result, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        tampered_read_back = client.get(f"/api/analysis-runs/{analysis_run_id}")
        assert tampered_read_back.json()["availability_state"] == "suppressed"
        result_path.write_text(original_result, encoding="utf-8")
        manifest_path.unlink()
        read_back = client.get(f"/api/analysis-runs/{analysis_run_id}")

    assert read_back.status_code == 200
    assert read_back.json()["status"] == "FAILED"
    assert read_back.json()["lifecycle"] == "quarantined"
    assert read_back.json()["verification_state"] == "invalid"
    assert read_back.json()["availability_state"] == "suppressed"
    assert read_back.json()["reason_code"] == "RUN_ARTIFACT_INTEGRITY_FAILED"
    assert read_back.json()["recovery_action"] == "EXPLICIT_RETRY_AS_NEW_OPERATION"
    assert read_back.json()["primary_result"] is None
    assert read_back.json()["diagnostics"] == []


def _released_propensity_rows(request: dict[str, object]) -> list[dict[str, object]]:
    adjustment_set = request["adjustment_set"]
    assert isinstance(adjustment_set, dict)
    fields = adjustment_set["fields"]
    assert isinstance(fields, list)
    categorical_values = {
        "material_class": ("class-a", "class-b"),
        "complexity_class": ("standard", "complex"),
        "project_id": ("project-a", "project-b"),
        "project_phase": ("substructure", "fitout"),
        "urgency_class": ("normal", "urgent"),
        "geography_code": ("north", "south"),
        "contract_form": ("lump-sum", "remeasure"),
    }
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
                        field: {
                            "state": "present",
                            "value": (
                                float(row_index + offset)
                                if field in {"quantity", "value"}
                                else categorical_values[field][supplier_index % 2]
                            ),
                        }
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
        subject_values = {
            "material_class": "class-a",
            "complexity_class": "standard",
            "quantity": 0.0,
            "value": 1.0,
            "project_id": "project-a",
            "project_phase": "substructure",
            "urgency_class": "normal",
            "geography_code": "north",
            "contract_form": "lump-sum",
        }
        request["subject"] = {
            "state": "eligible",
            "subject_id": "current-subject",
            "profile": {
                "adjustment_inputs": {
                    field: {"state": "present", "value": subject_values[field]}
                    for field in fields
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


def _released_supported_primary_request() -> dict[str, object]:
    request = _suite_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    fields = request["adjustment_set"]["fields"]
    assert isinstance(fields, list)
    rows: list[dict[str, object]] = []
    categorical_values = {
        "material_class": ("class-a", "class-b"),
        "complexity_class": ("standard", "complex"),
        "project_id": ("project-a", "project-b"),
        "project_phase": ("substructure", "fitout"),
        "urgency_class": ("normal", "urgent"),
        "geography_code": ("north", "south"),
        "contract_form": ("lump-sum", "remeasure"),
    }
    for supplier_index in range(50):
        for within_supplier in range(20):
            row_index = supplier_index * 20 + within_supplier
            exposed = within_supplier % 2 == 1
            covariates: dict[str, object] = {}
            for field in fields:
                if field in {"quantity", "value"}:
                    covariates[field] = {
                        "state": "present",
                        "value": float((supplier_index * 7 + (field == "value")) % 19),
                    }
                else:
                    values = categorical_values[field]
                    covariates[field] = {
                        "state": "present",
                        "value": values[supplier_index % 2],
                    }
            rows.append(
                {
                    "order_line_id": f"line-supported-{row_index:04d}",
                    "supplier_id": f"supplier-supported-{supplier_index:03d}",
                    "high_load_exposure": exposed,
                    "supplier_milestone_slippage_days": float(
                        (1.5 + (supplier_index % 5) * 0.03) * exposed
                        + (supplier_index % 5) * 0.1
                        + (within_supplier % 7) * 0.07
                    ),
                    "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
                    "supplier_milestone_late": bool(
                        (row_index + supplier_index * 7) % 7 == 0
                    ),
                    "load_percentile": 0.25 + (supplier_index % 10) / 20,
                    "covariates": covariates,
                    "lineage_refs": [f"lineage:line-supported-{row_index:04d}"],
                }
            )
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
    return request


def test_primary_atte_and_context_ate_share_clustered_nuisance_and_are_deterministic() -> None:
    request = _released_supported_primary_request()
    propensity_stage = materialize_propensity_and_s9(request)
    assert propensity_stage["variants"]["primary"]["s9"]["state"] == "supported"

    first = estimate_primary_atte_and_context(request, propensity_stage)
    second = estimate_primary_atte_and_context(request, propensity_stage)

    assert first["status"] == "estimated"
    assert first["estimator_executed"] is True
    assert first["result_identity_digest"] == second["result_identity_digest"]
    primary = first["primary_atte"]
    context = first["context_ate"]
    assert primary["estimand_id"] == "primary_atte_slippage"
    assert primary["score"] == "ATTE"
    assert context["estimand_id"] == "context_ate_slippage"
    assert context["score"] == "ATE"
    assert context["label"] == "overlap_trimmed_context"
    assert primary["estimator_class"] == context["estimator_class"] == "DoubleMLIRM"
    assert primary["nuisance_refs"] == context["nuisance_refs"]
    assert primary["fold_ref"] == context["fold_ref"]
    assert primary["cohort_identity_hash"] == context["cohort_identity_hash"]
    assert primary["cluster_key"] == context["cluster_key"] == "supplier_id"
    assert primary["cluster_count"] == context["cluster_count"] == 50
    assert primary["ci_level"] == context["ci_level"] == 0.95
    assert primary["ci_lower"] < primary["estimate"] < primary["ci_upper"]
    assert context["ci_lower"] < context["estimate"] < context["ci_upper"]
    assert len(primary["repeat_results"]) == len(context["repeat_results"]) == 2
    assert first["shared_nuisance"]["external_prediction_shapes"] == {
        "ml_g0": [1000, 2],
        "ml_g1": [1000, 2],
        "ml_m": [1000, 2],
    }
    assert first["shared_nuisance"]["external_predictions"][
        "high_load_exposure"
    ]["ml_m"][0][0] == first["shared_nuisance"]["external_predictions"][
        "high_load_exposure"
    ]["ml_m"][0][1]
    assert first["shared_nuisance"]["doubleml_refit_nuisance"] is False
    assert first["safe_detail"]["scope"] == "primary_atte_context_and_sensitivities"
    assert "line-supported-0000" not in str(first["safe_detail"])


def _released_supported_variants_request() -> dict[str, object]:
    request = _released_supported_primary_request()
    primary_variant = request["variant_inputs"][0]
    assert isinstance(primary_variant, dict)
    primary_rows = primary_variant["rows"]
    assert isinstance(primary_rows, list)
    for variant in request["variant_inputs"][1:]:
        assert isinstance(variant, dict)
        variant.update(
            {
                "upstream_status": "released",
                "rows": deepcopy(primary_rows),
                "cohort_stage_summaries": deepcopy(
                    primary_variant["cohort_stage_summaries"]
                ),
            }
        )
        variant.pop("scientific_code", None)
        variant.pop("gate_stage", None)
        variant["selector_refs"] = sorted(variant["selector_refs"])
        variant["s8_identity_hash"] = scientific_sha256(
            [row["order_line_id"] for row in primary_rows]
        )
        variant["s8_content_hash"] = scientific_sha256(
            {
                key: value
                for key, value in variant.items()
                if key not in {"s8_identity_hash", "s8_content_hash"}
            }
        )
    return request


def test_registered_sensitivities_use_variant_specific_cohorts_seeds_and_provenance() -> None:
    request = _released_supported_variants_request()
    propensity_stage = materialize_propensity_and_s9(request)

    for variant_id in ("primary", "stricter_threshold", "short_history", "long_history"):
        assert propensity_stage["variants"][variant_id]["s9"]["state"] == "supported"

    result = estimate_primary_atte_and_context(request, propensity_stage)

    assert result["status"] == "estimated"
    assert result["primary_atte"]["estimand_id"] == "primary_atte_slippage"
    assert result["context_ate"]["estimand_id"] == "context_ate_slippage"
    sensitivities = result["sensitivity_results"]
    estimands = {
        "stricter_threshold": "sensitivity_stricter_atte_slippage",
        "short_history": "sensitivity_short_history_atte_slippage",
        "long_history": "sensitivity_long_history_atte_slippage",
    }
    assert [estimand_id for estimand_id in sensitivities if estimand_id in estimands.values()] == list(
        estimands.values()
    )
    for variant_id, estimand_id in estimands.items():
        sensitivity = sensitivities[estimand_id]
        source_variant = next(
            variant
            for variant in request["variant_inputs"]
            if variant["variant_id"] == variant_id
        )
        stage_variant = propensity_stage["variants"][variant_id]
        assert sensitivity["status"] == "estimated"
        assert sensitivity["state"] == "estimated"
        assert sensitivity["estimand_id"] == estimand_id
        assert sensitivity["role"] == "sensitivity"
        assert sensitivity["score"] == "ATTE"
        assert sensitivity["estimator_class"] == "DoubleMLIRM"
        assert sensitivity["cohort_identity_hash"] == stage_variant["s9"]["identity_hash"]
        provenance = sensitivity["provenance"]
        assert provenance["variant_id"] == variant_id
        assert provenance["threshold_rule_ref"] == source_variant["threshold_rule_ref"]
        assert provenance["selector_refs"] == source_variant["selector_refs"]
        assert provenance["s8_identity_hash"] == source_variant["s8_identity_hash"]
        assert provenance["s8_content_hash"] == source_variant["s8_content_hash"]
        assert provenance["root_seed"] == request["root_seed"]
        assert provenance["seed_policy"] == {
            "id": "sha256-coordinate-seeds",
            "version": "v1",
        }
        assert len(provenance["seed_registry"]) == 82
        assert all(item["variant_id"] == variant_id for item in provenance["seed_registry"])
    assert (
        propensity_stage["variants"]["primary"]["fold_assignments"]
        != propensity_stage["variants"]["stricter_threshold"]["fold_assignments"]
    )


def test_closed_suite_publishes_secondary_forms_and_registered_comparisons() -> None:
    result = estimate_primary_atte_and_context(_released_supported_variants_request())

    assert result["status"] == "estimated"
    late = result["sensitivity_results"]["sensitivity_late_risk_atte"]
    assert late["status"] == "estimated"
    assert late["estimand_id"] == "sensitivity_late_risk_atte"
    assert late["unit"] == "absolute_probability"
    assert late["display_transform"] == {
        "scale": 100.0,
        "display_unit": "percentage_points",
        "estimate": late["estimate"] * 100.0,
        "standard_error": late["standard_error"] * 100.0,
        "ci_lower": late["ci_lower"] * 100.0,
        "ci_upper": late["ci_upper"] * 100.0,
    }

    continuous = result["sensitivity_results"]["sensitivity_continuous_load_slope"]
    assert continuous["status"] == "estimated"
    assert continuous["estimator_class"] == "DoubleMLPLR"
    assert continuous["score"] == "partialling out"
    assert continuous["label"] == "linear_average_slope"
    assert continuous["unit"] == "days_per_unit_load_percentile"
    assert continuous["display_transform"]["scale"] == 0.10

    comparisons = result["comparison_results"]
    assert list(comparisons) == [
        "naive_mean_difference",
        "covariate_ols",
        "normalized_ipw_atte",
        "supplier_fe_ols",
    ]
    assert all(
        comparison["coefficient_name"] == "high_load_exposure"
        and comparison["covariance_type"] == "cluster"
        and comparison["cluster_key"] == "supplier_id"
        and comparison["inference_df"] == comparison["supplier_count"] - 1
        for comparison in comparisons.values()
    )
    comparison_fields = {
        "comparison_id",
        "model_class",
        "coefficient_name",
        "estimate",
        "standard_error",
        "t_statistic",
        "p_value",
        "ci_level",
        "ci_lower",
        "ci_upper",
        "covariance_type",
        "cluster_key",
        "use_correction",
        "df_correction",
        "use_t",
        "inference_df",
        "row_count",
        "exposed_count",
        "unexposed_count",
        "supplier_count",
        "matrix_column_count",
        "matrix_rank",
        "condition_number",
        "design_matrix_digest",
        "feature_schema_digest",
        "cohort_identity_hash",
    }
    assert set(comparisons["naive_mean_difference"]) == comparison_fields
    assert set(comparisons["normalized_ipw_atte"]) == comparison_fields | {
        "propensity_ref",
        "fold_ref",
        "weight_diagnostics",
    }
    weight_diagnostics = comparisons["normalized_ipw_atte"]["weight_diagnostics"]
    assert weight_diagnostics["normalized_weight_sums"]["unexposed"] == (
        weight_diagnostics["normalized_weight_sums"]["exposed"]
    )
    assert comparisons["naive_mean_difference"]["cohort_identity_hash"] == result[
        "primary_atte"
    ]["cohort_identity_hash"]
    assert "cate" not in str(result).lower()
    assert "individualized_effect" not in result


def test_late_support_failure_preserves_primary_and_marks_only_late_unsupported() -> None:
    request = _released_supported_primary_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    rows = variant["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["supplier_milestone_late"] = False
    variant["s8_content_hash"] = scientific_sha256(
        {
            key: value
            for key, value in variant.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )

    result = estimate_primary_atte_and_context(request)

    assert result["status"] == "estimated"
    assert result["primary_atte"]["estimand_id"] == "primary_atte_slippage"
    late = result["sensitivity_results"]["sensitivity_late_risk_atte"]
    assert late["status"] == "unsupported"
    assert late["reason_code"] == "COHORT_SUPPORT_INSUFFICIENT"
    assert late["effect"] is None
    assert result["sensitivity_results"]["sensitivity_continuous_load_slope"]["status"] == (
        "estimated"
    )


def test_subject_support_is_published_without_an_individualized_effect() -> None:
    request = _released_supported_primary_request()
    variant = request["variant_inputs"][0]
    assert isinstance(variant, dict)
    rows = variant["rows"]
    assert isinstance(rows, list) and rows
    first_row = rows[0]
    assert isinstance(first_row, dict)
    request["subject"] = {
        "state": "eligible",
        "subject_id": "current-subject",
        "profile": {"adjustment_inputs": deepcopy(first_row["covariates"])},
    }

    result = estimate_primary_atte_and_context(request)

    assert result["status"] == "estimated"
    subject = result["subject_support"]
    assert subject["subject_id"] == "current-subject"
    assert subject["subject_profile"]["adjustment_inputs"] == first_row["covariates"]
    assert len(subject["propensity"]["repeat_fold_predictions"]) == 10
    assert subject["overlap"]["support_interval"] == {
        "lower": 0.10,
        "upper": 0.90,
        "inclusive": True,
    }
    assert "distribution_support" in subject
    assert "individualized_effect" not in subject
    assert all(str(key).lower() != "cate" for key in subject)


def test_required_comparison_failure_fails_closed_without_primary_result(monkeypatch) -> None:
    def fail_comparisons(request, nuisances):
        raise analysis_runs_module.EstimatorStageError("ENGINE_COMPARISON_FIT_FAILED")

    monkeypatch.setattr(analysis_runs_module, "_comparison_suite", fail_comparisons)

    result = estimate_primary_atte_and_context(_released_supported_primary_request())

    assert result["status"] == "failed"
    assert result["reason_code"] == "ENGINE_COMPARISON_FIT_FAILED"
    assert "primary_atte" not in result
    assert result["safe_detail"]["component_failures"] == [
        {
            "component": "secondary_suite",
            "variant_id": "primary",
            "code": "ENGINE_COMPARISON_FIT_FAILED",
        }
    ]


def test_unavailable_sensitivities_remain_explicit_without_replacing_primary() -> None:
    request = _released_supported_primary_request()
    result = estimate_primary_atte_and_context(request)

    assert result["status"] == "estimated"
    assert result["primary_atte"]["estimand_id"] == "primary_atte_slippage"
    for variant_id in ("stricter_threshold", "short_history", "long_history"):
        sensitivity = result["sensitivity_results"][
            {
                "stricter_threshold": "sensitivity_stricter_atte_slippage",
                "short_history": "sensitivity_short_history_atte_slippage",
                "long_history": "sensitivity_long_history_atte_slippage",
            }[variant_id]
        ]
        assert sensitivity["status"] == "unsupported"
        assert sensitivity["state"] == "unsupported"
        assert sensitivity["reason_code"] == "COHORT_SUPPORT_INSUFFICIENT"
        assert sensitivity["effect"] is None


def test_failed_sensitivity_is_explicit_without_replacing_primary() -> None:
    request = _released_supported_variants_request()
    propensity_stage = materialize_propensity_and_s9(request)
    tampered_stage = deepcopy(propensity_stage)
    short_history = tampered_stage["variants"]["short_history"]
    short_history["propensity_predictions"][0]["row_id"] = "unknown-row"

    result = estimate_primary_atte_and_context(request, tampered_stage)

    assert result["status"] == "failed"
    assert result["scientific_outcome"] == "failed"
    assert result["reason_code"] == "ENGINE_NUISANCE_PREDICTION_INVALID"
    assert result["estimator_executed"] is True
    assert "primary_atte" not in result
    assert "context_ate" not in result
    failed = result["sensitivity_results"]["sensitivity_short_history_atte_slippage"]
    assert failed["status"] == "failed"
    assert failed["state"] == "failed"
    assert failed["reason_code"] == "ENGINE_NUISANCE_PREDICTION_INVALID"
    assert failed["effect"] is None
    assert failed["component_failures"] == [
        {
            "component": "sensitivity_atte",
            "variant_id": "short_history",
            "code": "ENGINE_NUISANCE_PREDICTION_INVALID",
        }
    ]
    assert result["safe_detail"]["execution_state"] == "failed"


def test_primary_estimator_abstains_without_consumable_effect_when_primary_s9_is_unsupported() -> None:
    result = estimate_primary_atte_and_context(_released_primary_request())

    assert result["status"] == "abstained"
    assert result["reason_code"] == "OVERLAP_COHORT_INSUFFICIENT"
    assert result["estimator_executed"] is False
    assert "primary_atte" not in result
    assert "context_ate" not in result
    assert "line-000" not in str(result["safe_detail"])


def test_primary_estimator_fails_closed_on_tampered_external_prediction_identity() -> None:
    request = _released_supported_primary_request()
    propensity_stage = materialize_propensity_and_s9(request)
    tampered_stage = deepcopy(propensity_stage)
    tampered_stage["variants"]["primary"]["propensity_predictions"][0][
        "row_id"
    ] = "unknown-row"

    result = estimate_primary_atte_and_context(request, tampered_stage)

    assert result["status"] == "failed"
    assert result["reason_code"] == "ENGINE_NUISANCE_PREDICTION_INVALID"
    assert result["estimator_executed"] is True
    assert "primary_atte" not in result
    assert "context_ate" not in result
    assert "unknown-row" not in str(result["safe_detail"])


def test_fresh_worker_publishes_sealed_estimated_result_with_verdict(
    tmp_path: Path,
) -> None:
    request = _released_supported_primary_request()
    with _client(tmp_path / "state", start_operation_runner=True) as client:
        response = client.post(
            "/api/operations",
            json={
                "idempotency_key": "fresh-analysis-estimated-test",
                "operation_kind": "FRESH_ANALYSIS",
                "memory_required_bytes": 1024,
                "request": {"suite_request": request},
            },
        )
        operation_id = response.json()["operation"]["operation_id"]
        terminal = response.json()["operation"]
        for _ in range(900):
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
            time.sleep(0.1)

    assert terminal["state"] == "SUCCEEDED"
    analysis_run = terminal["analysis_run"]
    assert analysis_run["status"] == "ESTIMATED"
    assert analysis_run["scientific_outcome"] == "estimated"
    assert analysis_run["estimator_executed"] is True
    assert analysis_run["primary_result"]["schema_version"] == "fresh-primary-result.v2"
    assert analysis_run["primary_result"]["state"] == "sealed"
    assert analysis_run["bundle_manifest_hash"].startswith("sha256:")
    assert len(analysis_run["diagnostics"]) == 14
    assert analysis_run["evidence_verdict"]["verdict_code"] == "ASSOCIATION_ONLY"
    public_result = analysis_run["primary_result"]
    assert public_result["primary_atte"] is not None
    assert public_result["context_ate"] is None
    assert public_result["comparison_results"] == {}
    assert public_result["permission"] == {
        "evidence_verdict": True,
        "action_permission": False,
        "state": "sealed_machine_verified",
        "claim_scope": analysis_run["evidence_verdict"]["permitted_claim_scope"],
        "effect_display": "ADJUSTED_ASSOCIATION",
    }


def test_fresh_reproduction_is_a_new_run_with_a_verified_comparison(
    tmp_path: Path,
) -> None:
    with _client(tmp_path / "state", start_operation_runner=True) as client:
        original = client.post(
            "/api/operations",
            json={
                "idempotency_key": "reproduction-source",
                "operation_kind": "FRESH_ANALYSIS",
                "memory_required_bytes": 1024,
                "request": {"suite_request": _suite_request()},
            },
        )
        assert original.status_code == 202
        original_operation = original.json()["operation"]
        original_operation_id = original_operation["operation_id"]
        original_terminal = original_operation
        for _ in range(200):
            original_terminal = client.get(
                f"/api/operations/{original_operation_id}"
            ).json()
            if original_terminal["state"] in {"SUCCEEDED", "FAILED"}:
                break
            time.sleep(0.05)
        assert original_terminal["state"] == "SUCCEEDED"
        target = original_terminal["analysis_run"]

        reproduction = client.post(
            "/api/operations",
            json={
                "idempotency_key": "reproduction-candidate",
                "operation_kind": "FRESH_REPRODUCTION",
                "memory_required_bytes": 1024,
                "request": {
                    "target_analysis_run_id": target["analysis_run_id"],
                },
            },
        )
        assert reproduction.status_code == 202
        accepted = reproduction.json()["operation"]
        assert accepted["operation_kind"] == "FRESH_REPRODUCTION"
        assert accepted["analysis_run"]["run_relationship"] == "reproduction"
        assert accepted["analysis_run"]["reproduces_run_id"] == target[
            "analysis_run_id"
        ]

        terminal = accepted
        for _ in range(200):
            terminal = client.get(
                f"/api/operations/{accepted['operation_id']}"
            ).json()
            if terminal["state"] in {"SUCCEEDED", "FAILED"}:
                break
            time.sleep(0.05)

    assert terminal["state"] == "SUCCEEDED"
    reproduced = terminal["analysis_run"]
    assert reproduced["status"] == target["status"]
    assert reproduced["analysis_run_id"] != target["analysis_run_id"]
    assert reproduced["scientific_request_digest"] == target[
        "scientific_request_digest"
    ]
    assert reproduced["runtime_fingerprint_digest"] == target[
        "runtime_fingerprint_digest"
    ]
    assert reproduced["reproduces_run_id"] == target["analysis_run_id"]
    assert reproduced["reproduction_comparison"]["status"] == "passed"


def test_fresh_reproduction_rejects_an_unavailable_target_without_admission(
    tmp_path: Path,
) -> None:
    with _client(tmp_path / "state", start_operation_runner=False) as client:
        response = client.post(
            "/api/operations",
            json={
                "idempotency_key": "reproduction-missing-target",
                "operation_kind": "FRESH_REPRODUCTION",
                "memory_required_bytes": 1024,
                "request": {"target_analysis_run_id": "analysis-run-missing"},
            },
        )

    assert response.status_code == 404
    assert response.json() == {
        "code": "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
        "recovery_action": "SELECT_A_VERIFIED_ANALYSIS_RUN_AND_RETRY",
    }
