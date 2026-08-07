from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.predictive import (
    ALERT_THRESHOLD,
    FEATURE_NAMES,
    PREDICTIVE_ATTRIBUTION_LABEL,
    PredictiveScoringFailure,
    PredictiveSubject,
    PredictiveTrainingRow,
    build_global_predictive_attribution,
    fit_predictive_baseline,
    load_predictive_baseline,
    load_prediction_record_bundle,
    prediction_record_bundle_hash,
    score_predictive_subject,
    validate_prediction_record_attribution_bindings,
    validate_predictive_attribution,
    write_predictive_baseline,
)
from backend.app.settings import Settings


def make_training_rows() -> list[PredictiveTrainingRow]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[PredictiveTrainingRow] = []
    for index in range(60):
        correlate = float(index % 4 in {0, 1})
        rows.append(
            PredictiveTrainingRow(
                row_id=f"training-{index:03d}",
                dataset_version_id="sha256:training-dataset-v1",
                committed_at=start + timedelta(days=index),
                features={
                    "load_at_placement": float(index % 7),
                    "quantity_amount": float(10 + index),
                    "value_amount": float(100 + (index * 5)),
                    "lead_time_days": float(12 + (index % 9)),
                    "predictive_correlate": correlate,
                },
                target=index % 3 == 0,
                original_promise=(start + timedelta(days=index + 30)).date().isoformat(),
                follow_up_maturity=start + timedelta(days=index + 90),
                lineage_refs=(f"bundled://test-training/{index:03d}",),
            )
        )
    return rows


def make_baseline():
    return fit_predictive_baseline(
        make_training_rows(),
        fit_end=datetime(2026, 2, 6, tzinfo=timezone.utc),
        calibration_end=datetime(2026, 2, 18, tzinfo=timezone.utc),
    )


def make_subject() -> PredictiveSubject:
    return PredictiveSubject(
        prediction_record_id=None,
        dataset_version_id="sha256:hero-dataset-v1",
        order_line_id="order-line-001",
        generated_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
        features={
            "load_at_placement": 4.0,
            "quantity_amount": 75.0,
            "value_amount": 450.0,
            "lead_time_days": 18.0,
            "predictive_correlate": 1.0,
        },
    )


def test_baseline_uses_locked_chronological_partitions_and_report_contract() -> None:
    baseline = make_baseline()

    assert baseline.report["schema_version"] == "predictive-baseline-report.v1"
    assert baseline.report["model"]["implementation"] == (
        "sklearn.ensemble.HistGradientBoostingClassifier"
    )
    assert baseline.report["model"]["random_state"] == 0
    assert baseline.report["model"]["early_stopping"] is False
    assert baseline.report["calibration"] == {
        "method": "sigmoid",
        "estimator": "sklearn.frozen.FrozenEstimator",
        "calibration_n_jobs": 1,
    }
    assert baseline.report["threshold"] == ALERT_THRESHOLD
    assert baseline.report["partitions"] == {
        "fit": {"count": 36, "outcome_prevalence": 0.3333333333333333},
        "calibration": {"count": 12, "outcome_prevalence": 0.3333333333333333},
        "evaluation": {"count": 12, "outcome_prevalence": 0.3333333333333333},
    }
    assert baseline.report["feature_contract"]["version"] == "predictive-features.v1"
    assert baseline.report["feature_contract"]["ordered_features"] == list(FEATURE_NAMES)
    assert baseline.report["non_causal_label"] == (
        "prediction performance - not causal or decision evidence"
    )


def test_subject_score_and_shap_attribution_are_deterministic_and_additive() -> None:
    baseline = make_baseline()
    subject = make_subject()

    first = score_predictive_subject(baseline, subject)
    second = score_predictive_subject(baseline, subject)

    assert first.prediction_record == second.prediction_record
    assert first.attribution == second.attribution
    assert 0.0 <= first.prediction_record["score_value"] <= 1.0
    assert first.prediction_record["alert_threshold"] == ALERT_THRESHOLD
    assert first.prediction_record["flagged"] is (
        first.prediction_record["score_value"] >= ALERT_THRESHOLD
    )
    assert first.attribution["label"] == PREDICTIVE_ATTRIBUTION_LABEL
    assert first.attribution["validation_status"] == "valid"
    assert first.attribution["additivity_residual"] <= 1e-6
    assert len(first.attribution["contributions"]) == len(FEATURE_NAMES)
    assert len(first.attribution["presentation"]["top_contributions"]) <= 5
    assert (
        sum(
            item["contribution"]
            for item in first.attribution["presentation"]["top_contributions"]
        )
        + first.attribution["presentation"]["other_features"]
        == pytest.approx(sum(item["contribution"] for item in first.attribution["contributions"]))
    )


def test_attribution_binding_and_global_evaluation_summary_are_verified() -> None:
    baseline = make_baseline()
    subject = make_subject()
    result = score_predictive_subject(baseline, subject)

    validate_predictive_attribution(
        result.attribution,
        expected_score=result.prediction_record["score_value"],
        expected_model_artifact_ref=baseline.artifact_ref,
        expected_prediction_record_id=result.prediction_record["prediction_record_id"],
        expected_dataset_version_id=subject.dataset_version_id,
        expected_order_line_id=subject.order_line_id,
        expected_background_identity_hash=baseline.report["background_selector"][
            "identity_hash"
        ],
        expected_features=subject.features,
    )
    with pytest.raises(PredictiveScoringFailure) as error:
        validate_predictive_attribution(
            result.attribution,
            expected_score=result.prediction_record["score_value"],
            expected_model_artifact_ref="bundled://other-model",
        )
    assert error.value.code == "PREDICTIVE_ATTRIBUTION_INVALID"

    global_attribution, local_attributions = build_global_predictive_attribution(
        baseline,
        [subject],
    )
    assert global_attribution["label"] == PREDICTIVE_ATTRIBUTION_LABEL
    assert global_attribution["local_attribution_refs"] == [
        local_attributions[0]["artifact_ref"]
    ]
    assert [
        item["name"] for item in global_attribution["mean_absolute_contributions"]
    ] == list(FEATURE_NAMES)


def test_unscorable_subject_exposes_a_registered_reason() -> None:
    baseline = make_baseline()
    subject = make_subject()
    subject.features.pop("value_amount")

    with pytest.raises(PredictiveScoringFailure) as error:
        score_predictive_subject(baseline, subject)

    assert error.value.code == "PREDICTIVE_SUBJECT_UNSCORABLE"


def test_serialized_baseline_is_verified_before_runtime_use(tmp_path: Path) -> None:
    baseline = make_baseline()
    artifact_path = tmp_path / "predictive-baseline.joblib"
    report_path = tmp_path / "predictive-baseline.json"

    write_predictive_baseline(baseline, artifact_path, report_path)
    loaded = load_predictive_baseline(artifact_path, report_path)

    assert loaded.artifact_ref == baseline.artifact_ref
    assert loaded.report == baseline.report

    report_path.write_text("{}", encoding="utf-8")
    with pytest.raises(PredictiveScoringFailure) as error:
        load_predictive_baseline(artifact_path, report_path)

    assert error.value.code == "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE"


def test_prediction_records_are_sealed_and_bound_to_attributions(tmp_path: Path) -> None:
    baseline = make_baseline()
    result = score_predictive_subject(baseline, make_subject())
    items = [result.prediction_record]
    bundle_path = tmp_path / "prediction-records.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": "prediction-record-bundle.v1",
                "bundle_sha256": prediction_record_bundle_hash(items),
                "items": items,
            }
        ),
        encoding="utf-8",
    )
    records = load_prediction_record_bundle(
        bundle_path,
        expected_model_artifact_ref=baseline.artifact_ref,
    )
    validate_prediction_record_attribution_bindings(
        records,
        {result.attribution["artifact_ref"]: result.attribution},
    )

    tampered = dict(result.prediction_record)
    tampered["score_value"] = 0.01
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": "prediction-record-bundle.v1",
                "bundle_sha256": prediction_record_bundle_hash(items),
                "items": [tampered],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PredictiveScoringFailure) as error:
        load_prediction_record_bundle(bundle_path)
    assert error.value.code == "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE"


def test_verified_bundled_signal_opens_reactive_intake_and_keeps_manual_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app import risk as risk_module

    state_root = tmp_path / "state"
    with TestClient(create_app(Settings(state_root=state_root))) as client:
        imported = client.post(
            "/api/ingestion-runs",
            json={
                "idempotency_key": "predictive-baseline-test",
                "dataset_key": "semi-synthetic-hero",
                "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
            },
        )
        dataset_version_id = imported.json()["dataset_version_id"]
        signals = client.get(
            "/api/risk-signals",
            params={"dataset_version_id": dataset_version_id},
        )
        generated = next(
            item
            for item in signals.json()["items"]
            if item["fixture_id"] == "hero-reactive-risk-predictive-baseline-v1"
        )
        assert generated["signal"]["score_value"] >= ALERT_THRESHOLD
        assert generated["signal"]["predictive_attribution_ref"]["state"] == "present"
        assert signals.json()["predictive_status"] == {
            "state": "verified",
            "code": "PREDICTIVE_ARTIFACTS_VERIFIED",
            "message": "The bundled predictive artifact, attribution bundle, and prediction records passed integrity checks.",
            "manual_investigation_available": True,
        }

        accepted = client.post(
            "/api/investigations/reactive/fixtures",
            json={
                "dataset_version_id": dataset_version_id,
                "fixture_id": "hero-reactive-risk-predictive-baseline-v1",
            },
        )
        assert accepted.status_code == 201
        assert accepted.json()["attempt"]["status"] == "accepted"
        assert accepted.json()["attempt"]["primary_code"] == "RISK_SIGNAL_ACCEPTED"

        monkeypatch.setattr(
            risk_module,
            "PREDICTIVE_ARTIFACT_FILE",
            tmp_path / "missing-predictive-baseline.joblib",
        )
        unavailable = client.get(
            "/api/risk-signals",
            params={"dataset_version_id": dataset_version_id},
        )
        assert unavailable.json()["predictive_status"]["state"] == "unavailable"
        assert unavailable.json()["predictive_status"]["code"] == (
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE"
        )
        assert unavailable.json()["predictive_status"]["manual_investigation_available"] is True
        assert all(
            item["fixture_id"] != "hero-reactive-risk-predictive-baseline-v1"
            for item in unavailable.json()["items"]
        )
        with TestClient(
            create_app(Settings(state_root=tmp_path / "fallback-state"))
        ) as fallback_client:
            fallback_import = fallback_client.post(
                "/api/ingestion-runs",
                json={
                    "idempotency_key": "predictive-manual-fallback-test",
                    "dataset_key": "semi-synthetic-hero",
                    "mapping_manifest_id": "semi-synthetic-hero.mapping.v1",
                },
            )
            fallback_dataset_version_id = fallback_import.json()["dataset_version_id"]
            manual = fallback_client.post(
                "/api/investigations/reactive/fixtures",
                json={
                    "dataset_version_id": fallback_dataset_version_id,
                    "fixture_id": "hero-reactive-risk-metadata-unavailable-v1",
                },
            )
            assert manual.status_code == 201
            assert manual.json()["attempt"]["status"] == "accepted_with_warning"
            assert [finding["code"] for finding in manual.json()["attempt"]["findings"]] == [
                "PREDICTOR_ARTIFACT_UNAVAILABLE",
                "PREDICTIVE_ATTRIBUTION_UNAVAILABLE",
            ]
