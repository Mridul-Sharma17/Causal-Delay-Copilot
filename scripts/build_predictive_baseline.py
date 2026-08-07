from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import json
from pathlib import Path

from backend.app.predictive import (
    PredictiveSubject,
    build_global_predictive_attribution,
    PredictiveTrainingRow,
    fit_predictive_baseline,
    predictive_attribution_bundle_hash,
    prediction_record_bundle_hash,
    score_predictive_subject,
    predictive_prediction_record_id,
    write_predictive_baseline,
)
from backend.app.contracts import RiskSignalRequest
from backend.app.ingestion import _build_bundle
from backend.app.risk import (
    SOURCE_NAMESPACE,
    _canonical_id,
    _canonical_json,
    _protected_signal_payload,
    _sha256,
    _source_signal_identity,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "backend" / "app" / "data"
DATASET_VERSION_ID = "sha256:predictive-harness-v1"
FIT_END = datetime(2024, 2, 18, tzinfo=timezone.utc)
CALIBRATION_END = datetime(2024, 3, 5, tzinfo=timezone.utc)
PREDICTIVE_FIXTURE_ID = "hero-reactive-risk-predictive-baseline-v1"
PREDICTIVE_FIXTURE_LOCATOR = (
    "bundled://risk-signal/hero-reactive-risk-predictive-baseline-v1"
)


def build_rows() -> list[PredictiveTrainingRow]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows: list[PredictiveTrainingRow] = []
    for index in range(72):
        rows.append(
            PredictiveTrainingRow(
                row_id=f"predictive-harness-{index:03d}",
                dataset_version_id=DATASET_VERSION_ID,
                committed_at=start + timedelta(days=index),
                features={
                    "load_at_placement": float(index % 9),
                    "quantity_amount": float(20 + (index * 3)),
                    "value_amount": float(500 + (index * 17)),
                    "lead_time_days": float(14 + (index % 11)),
                    "predictive_correlate": float(index % 6 in {0, 1, 2}),
                },
                target=index % 6 in {0, 1, 2},
                original_promise=(start + timedelta(days=index + 30)).date().isoformat(),
                follow_up_maturity=start + timedelta(days=index + 90),
                lineage_refs=(
                    f"bundled://predictive-harness/row/{index:03d}",
                    "bundled://predictive-harness/ground-truth-v1",
                ),
            )
        )
    return rows


def _instant(value: str) -> dict[str, object]:
    return {
        "value": value,
        "kind": "instant",
        "precision": "minute",
        "timezone_status": "known",
        "source_timezone": "Asia/Kolkata",
    }


def build_predictive_signal(baseline, dataset_version_id: str) -> tuple[dict, dict, dict]:
    order_line_id = _canonical_id(
        SOURCE_NAMESPACE,
        "order-line",
        "hero-line-001",
    )
    generated_at = datetime(2026, 1, 10, 3, 30, tzinfo=timezone.utc)
    scored = score_predictive_subject(
        baseline,
        PredictiveSubject(
            prediction_record_id=predictive_prediction_record_id(
                dataset_version_id,
                order_line_id,
                generated_at,
            ),
            dataset_version_id=dataset_version_id,
            order_line_id=order_line_id,
            generated_at=generated_at,
            features={
                "load_at_placement": 0.0,
                "quantity_amount": 120.0,
                "value_amount": 185000.0,
                "lead_time_days": 41.0,
                "predictive_correlate": 1.0,
            },
        ),
    )
    report_ref = f"bundled://predictive-stub/report/{baseline.report['report_sha256']}"
    ranking_ref = f"bundled://predictive-stub/ranking/{_sha256({'order_line_id': order_line_id, 'score_value': scored.prediction_record['score_value']})}"
    signal: dict = {
        "schema_version": "risk-signal.v1",
        "trigger_mode": "reactive",
        "source": {
            "schema_version": "trigger-source-envelope.v1",
            "source_system": "bundled-predictive-stub",
            "source_payload_sha256": "sha256:" + ("0" * 64),
            "protected_source_locator": PREDICTIVE_FIXTURE_LOCATOR,
            "data_classification": "generated",
        },
        "source_signal_id": "pending-source-signal-id",
        "source_revision": "v1",
        "scored_dataset_version_ref": dataset_version_id,
        "source_order_line_ref": {
            "namespace": "semi-synthetic-hero",
            "key": "hero-line-001",
        },
        "predictor_id": scored.prediction_record["predictor_id"],
        "predictor_version": scored.prediction_record["predictor_version"],
        "feature_contract_version": scored.prediction_record["feature_contract_version"],
        "target_definition_id": scored.prediction_record["target_definition_id"],
        "target_milestone_kind": scored.prediction_record["target_milestone_kind"],
        "score_semantic": scored.prediction_record["score_semantic"],
        "score_value": scored.prediction_record["score_value"],
        "alert_threshold": scored.prediction_record["alert_threshold"],
        "flagged": scored.prediction_record["flagged"],
        "generated_at": _instant("2026-01-10T09:00:00+05:30"),
        "known_at": _instant("2026-01-10T09:05:00+05:30"),
        "predictor_artifact_ref": {
            "state": "present",
            "value": baseline.artifact_ref,
        },
        "predictive_attribution_ref": {
            "state": "present",
            "value": scored.attribution["artifact_ref"],
        },
        "prediction_explanation_ref": {
            "state": "present",
            "value": scored.attribution["artifact_ref"],
        },
        "prediction_calibration_ref": {
            "state": "present",
            "value": report_ref,
        },
        "prediction_ranking_ref": {
            "state": "present",
            "value": ranking_ref,
        },
        "prediction_delivery_metadata": {
            "state": "present",
            "value": {
                "channel": "bundled-predictive-stub",
                "rank": 1,
                "prediction_record_id": scored.prediction_record["prediction_record_id"],
            },
        },
        "advisory_context": {
            "state": "present",
            "value": {
                "source_supplier_ref": {
                    "state": "present",
                    "value": {
                        "namespace": "semi-synthetic-hero",
                        "key": "hero-supplier-001",
                    },
                },
                "source_target_milestone_kind": {
                    "state": "present",
                    "value": "supplier_handoff",
                },
                "source_original_promise": {
                    "state": "present",
                    "value": {
                        "value": "2026-02-15",
                        "kind": "date",
                        "precision": "date",
                        "timezone_status": "not_applicable",
                        "source_timezone": None,
                    },
                },
                "timeline_snapshot_as_of": {
                    "state": "present",
                    "value": _instant("2026-01-10T09:00:00+05:30"),
                },
            },
        },
    }
    signal_request = RiskSignalRequest.model_validate(signal)
    signal["source_signal_id"] = _source_signal_identity(
        signal_request.model_dump(mode="json")
    )
    signal_request = RiskSignalRequest.model_validate(signal)
    protected_bytes = _canonical_json(
        _protected_signal_payload(signal_request.model_dump(mode="json"))
    ).encode("utf-8")
    signal["source"]["source_payload_sha256"] = _sha256(protected_bytes)
    return signal, scored.prediction_record, scored.attribution


def main() -> None:
    rows = build_rows()
    baseline = fit_predictive_baseline(
        rows,
        fit_end=FIT_END,
        calibration_end=CALIBRATION_END,
    )
    write_predictive_baseline(
        baseline,
        DATA_ROOT / "predictive_baseline.joblib",
        DATA_ROOT / "predictive_baseline_report.json",
    )
    dataset_version_id = _build_bundle(
        ingestion_run_id="predictive-baseline-dataset-run",
        started_at="2026-01-01T00:00:00+00:00",
    )["dataset_version"]["dataset_version_id"]
    signal, prediction_record, attribution = build_predictive_signal(
        baseline,
        dataset_version_id,
    )
    evaluation_subjects = tuple(
        PredictiveSubject(
            prediction_record_id=predictive_prediction_record_id(
                row.dataset_version_id,
                row.row_id,
                row.committed_at,
            ),
            dataset_version_id=row.dataset_version_id,
            order_line_id=row.row_id,
            generated_at=row.committed_at,
            features=row.features,
        )
        for row in rows
        if row.committed_at >= CALIBRATION_END
    )
    global_attribution, evaluation_attributions = build_global_predictive_attribution(
        baseline,
        evaluation_subjects,
    )
    evaluation_prediction_records = tuple(
        score_predictive_subject(baseline, subject).prediction_record
        for subject in evaluation_subjects
    )
    (DATA_ROOT / "predictive_risk_signal_fixture.json").write_text(
        json.dumps(
            {
                "schema_version": "predictive-risk-signal-fixture.v1",
                "items": [
                    {
                        "fixture_id": PREDICTIVE_FIXTURE_ID,
                        "label": "Generated calibrated predictive Risk Signal",
                        "signal": signal,
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (DATA_ROOT / "predictive_attributions.json").write_text(
        json.dumps(
            {
                "schema_version": "predictive-attribution-bundle.v1",
                "bundle_sha256": predictive_attribution_bundle_hash(
                    [attribution, *evaluation_attributions],
                    global_attribution,
                ),
                "items": [attribution, *evaluation_attributions],
                "global": global_attribution,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (DATA_ROOT / "predictive_prediction_records.json").write_text(
        json.dumps(
            {
                "schema_version": "prediction-record-bundle.v1",
                "bundle_sha256": prediction_record_bundle_hash(
                    [prediction_record, *evaluation_prediction_records]
                ),
                "items": [prediction_record, *evaluation_prediction_records],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    protected_bytes = _canonical_json(
        _protected_signal_payload(RiskSignalRequest.model_validate(signal).model_dump(mode="json"))
    ).encode("utf-8")
    (DATA_ROOT / "predictive_protected_sources.json").write_text(
        json.dumps(
            {
                "schema_version": "risk-signal-protected-source-bytes.v1",
                "items": [
                    {
                        "locator": PREDICTIVE_FIXTURE_LOCATOR,
                        "bytes_base64": base64.b64encode(protected_bytes).decode("ascii"),
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    cohort = {
        "schema_version": "predictive-training-cohort.v1",
        "dataset_version_id": DATASET_VERSION_ID,
        "source_kind": "semi_synthetic_predictive_harness",
        "generated_by": "scripts/build_predictive_baseline.py",
        "fit_end": FIT_END.isoformat(),
        "calibration_end": CALIBRATION_END.isoformat(),
        "rows": [
            {
                "row_id": row.row_id,
                "dataset_version_id": row.dataset_version_id,
                "committed_at": row.committed_at.isoformat(),
                "features": dict(row.features),
                "target": row.target,
                "original_promise": row.original_promise,
                "follow_up_maturity": (
                    row.follow_up_maturity.isoformat()
                    if row.follow_up_maturity is not None
                    else None
                ),
                "lineage_refs": list(row.lineage_refs),
            }
            for row in rows
        ],
    }
    (DATA_ROOT / "predictive_training_cohort.json").write_text(
        json.dumps(
            cohort,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(baseline.artifact_ref)
    print(baseline.report["fit_cohort_hash"])
    print(baseline.report["calibration_cohort_hash"])
    print(baseline.report["evaluation_cohort_hash"])


if __name__ == "__main__":
    main()
