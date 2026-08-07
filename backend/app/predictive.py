from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import shap
from sklearn import __version__ as sklearn_version
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)

from .canonical import sha256 as _sha256


PREDICTIVE_BASELINE_ARTIFACT_SCHEMA_VERSION = "predictive-baseline-artifact.v1"
PREDICTIVE_BASELINE_REPORT_SCHEMA_VERSION = "predictive-baseline-report.v1"
PREDICTIVE_ATTRIBUTION_SCHEMA_VERSION = "predictive-attribution.v1"
PREDICTOR_ID = "predictive-stub"
PREDICTOR_VERSION = "predictive-stub.v1"
FEATURE_CONTRACT_VERSION = "predictive-features.v1"
TARGET_DEFINITION_ID = "supplier_milestone_miss.v1"
TARGET_MILESTONE_KIND = "supplier_handoff"
SCORE_SEMANTIC = "probability_supplier_milestone_miss"
ALERT_THRESHOLD = 0.50
PREDICTIVE_ATTRIBUTION_LABEL = "Predictive attribution - not causal evidence."
PREDICTION_PERFORMANCE_LABEL = (
    "prediction performance - not causal or decision evidence"
)
BACKGROUND_SELECTOR_VERSION = "predictive-background-first-hash.v1"
EVALUATION_SELECTOR_VERSION = "predictive-evaluation-first-hash.v1"
SHAP_METHOD = "PermutationExplainer"
SHAP_LINK = "identity"
SHAP_SEED = 0
PINNED_SKLEARN_VERSION = "1.6.1"
PINNED_SHAP_VERSION = "0.48.0"
PINNED_JOBLIB_VERSION = "1.5.3"

FEATURE_NAMES = (
    "load_at_placement",
    "quantity_amount",
    "value_amount",
    "lead_time_days",
    "predictive_correlate",
)

_MODEL_CONSTRUCTOR_DEFAULTS: dict[str, Any] = {
    "loss": "log_loss",
    "learning_rate": 0.1,
    "max_iter": 100,
    "max_leaf_nodes": 31,
    "max_depth": None,
    "max_bins": 255,
    "min_samples_leaf": 20,
    "l2_regularization": 0.0,
    "max_features": 1.0,
    "categorical_features": "from_dtype",
    "monotonic_cst": None,
    "warm_start": False,
    "interaction_cst": None,
    "early_stopping": False,
    "scoring": "loss",
    "validation_fraction": 0.1,
    "n_iter_no_change": 10,
    "tol": 1e-7,
    "verbose": 0,
    "random_state": 0,
    "class_weight": None,
}


class PredictiveScoringFailure(Exception):
    """A registered, safe failure in predictive artifact or subject handling."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PredictiveTrainingRow:
    row_id: str
    dataset_version_id: str
    committed_at: datetime
    features: Mapping[str, float]
    target: bool
    original_promise: str | None = None
    follow_up_maturity: datetime | None = None
    lineage_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PredictiveSubject:
    prediction_record_id: str | None
    dataset_version_id: str
    order_line_id: str
    generated_at: datetime
    features: Mapping[str, float]


@dataclass(slots=True)
class PredictiveBaseline:
    base_model: HistGradientBoostingClassifier
    calibrated_model: CalibratedClassifierCV
    background_features: np.ndarray
    background_row_ids: tuple[str, ...]
    report: dict[str, Any]
    artifact_ref: str = "unsealed"

    def artifact_payload(self) -> dict[str, Any]:
        return {
            "schema_version": PREDICTIVE_BASELINE_ARTIFACT_SCHEMA_VERSION,
            "predictor_id": PREDICTOR_ID,
            "predictor_version": PREDICTOR_VERSION,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "target_definition_id": TARGET_DEFINITION_ID,
            "target_milestone_kind": TARGET_MILESTONE_KIND,
            "score_semantic": SCORE_SEMANTIC,
            "alert_threshold": ALERT_THRESHOLD,
            "feature_names": list(FEATURE_NAMES),
            "base_model": self.base_model,
            "calibrated_model": self.calibrated_model,
            "background_features": np.asarray(self.background_features, dtype=np.float64),
            "background_row_ids": list(self.background_row_ids),
        }


@dataclass(frozen=True, slots=True)
class PredictiveScoreResult:
    prediction_record: dict[str, Any]
    attribution: dict[str, Any]


def _json_hash(value: object) -> str:
    return _sha256(value)


def _utc_datetime(value: datetime, *, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PredictiveScoringFailure(code, "A timezone-aware datetime is required.")
    return value.astimezone(timezone.utc)


def _iso_datetime(value: datetime) -> str:
    return _utc_datetime(value, code="PREDICTIVE_SUBJECT_UNSCORABLE").isoformat()


def predictive_prediction_record_id(
    dataset_version_id: str,
    order_line_id: str,
    generated_at: datetime,
) -> str:
    return "prediction-" + _json_hash(
        {
            "dataset_version_id": dataset_version_id,
            "order_line_id": order_line_id,
            "predictor_version": PREDICTOR_VERSION,
            "generated_at": _iso_datetime(generated_at),
        }
    )[7:]


def _feature_vector(
    features: Mapping[str, float],
    *,
    missing_code: str,
) -> np.ndarray:
    if not isinstance(features, Mapping):
        raise PredictiveScoringFailure(
            missing_code,
            "The predictive feature snapshot is not a mapping.",
        )
    missing = [name for name in FEATURE_NAMES if name not in features]
    if missing:
        raise PredictiveScoringFailure(
            missing_code,
            "Required predictive subject features are unavailable.",
        )
    extras = [name for name in features if name not in FEATURE_NAMES]
    if extras:
        raise PredictiveScoringFailure(
            "PREDICTIVE_FEATURE_CONTRACT_MISMATCH",
            "The predictive feature snapshot contains unsupported fields.",
        )
    values: list[float] = []
    for name in FEATURE_NAMES:
        value = features[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PredictiveScoringFailure(
                missing_code,
                "Predictive feature values must be finite numbers.",
            )
        numeric = float(value)
        if not math.isfinite(numeric):
            raise PredictiveScoringFailure(
                missing_code,
                "Predictive feature values must be finite numbers.",
            )
        values.append(numeric)
    return np.asarray(values, dtype=np.float64)


def _normalise_training_rows(
    rows: Sequence[PredictiveTrainingRow],
) -> list[PredictiveTrainingRow]:
    if not rows:
        raise PredictiveScoringFailure(
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
            "The locked predictive cohort is empty.",
        )
    identifiers: set[str] = set()
    dataset_versions: set[str] = set()
    normalized: list[PredictiveTrainingRow] = []
    for row in rows:
        if not isinstance(row, PredictiveTrainingRow) or not row.row_id:
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive cohort contains an invalid identity.",
            )
        if row.row_id in identifiers:
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive cohort contains duplicate identities.",
            )
        identifiers.add(row.row_id)
        if not row.dataset_version_id:
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive cohort has no Dataset Version identity.",
            )
        dataset_versions.add(row.dataset_version_id)
        _feature_vector(
            row.features,
            missing_code="PREDICTIVE_FEATURE_CONTRACT_MISMATCH",
        )
        if not isinstance(row.target, bool):
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive target is not binary.",
            )
        if row.original_promise is None or row.follow_up_maturity is None or not row.lineage_refs:
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive cohort is missing commitment, promise, maturity, or lineage evidence.",
            )
        if not isinstance(row.original_promise, str) or not row.original_promise:
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive cohort has an invalid original promise.",
            )
        if not isinstance(row.lineage_refs, (tuple, list)) or not all(
            isinstance(reference, str) and reference for reference in row.lineage_refs
        ):
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The locked predictive cohort has invalid lineage references.",
            )
        normalized.append(
            PredictiveTrainingRow(
                row_id=row.row_id,
                dataset_version_id=row.dataset_version_id,
                committed_at=_utc_datetime(
                    row.committed_at,
                    code="PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                ),
                features=dict(row.features),
                target=row.target,
                original_promise=row.original_promise,
                follow_up_maturity=(
                    _utc_datetime(
                        row.follow_up_maturity,
                        code="PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    )
                    if row.follow_up_maturity is not None
                    else None
                ),
                lineage_refs=tuple(row.lineage_refs),
            )
        )
    if len(dataset_versions) != 1:
        raise PredictiveScoringFailure(
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
            "The locked predictive cohort spans multiple Dataset Versions.",
        )
    return sorted(normalized, key=lambda row: (row.committed_at, row.row_id))


def _cohort_hash(rows: Sequence[PredictiveTrainingRow]) -> str:
    return _json_hash(
        [
            {
                "row_id": row.row_id,
                "dataset_version_id": row.dataset_version_id,
                "committed_at": row.committed_at.isoformat(),
                "features": {name: row.features[name] for name in FEATURE_NAMES},
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
        ]
    )


def _stable_row_identity_hash(row: PredictiveTrainingRow) -> str:
    return _json_hash(
        {"dataset_version_id": row.dataset_version_id, "row_id": row.row_id}
    )


def _partition_report(rows: Sequence[PredictiveTrainingRow]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "outcome_prevalence": sum(row.target for row in rows) / len(rows),
    }


def _safe_metric(metric: Any, y_true: np.ndarray, scores: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    return float(metric(y_true, scores))


def _evaluation_metrics(
    rows: Sequence[PredictiveTrainingRow],
    scores: np.ndarray,
) -> dict[str, Any]:
    targets = np.asarray([row.target for row in rows], dtype=np.int8)
    thresholded = scores >= ALERT_THRESHOLD
    positives = targets == 1
    negatives = targets == 0
    true_positives = int(np.sum(thresholded & positives))
    false_positives = int(np.sum(thresholded & negatives))
    true_negatives = int(np.sum(~thresholded & negatives))
    false_negatives = int(np.sum(~thresholded & positives))

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    bins = min(10, max(2, len(rows)))
    calibration = calibration_curve(
        targets,
        scores,
        n_bins=bins,
        strategy="uniform",
    )
    return {
        "auroc": _safe_metric(roc_auc_score, targets, scores),
        "average_precision": float(average_precision_score(targets, scores)),
        "brier_score": float(brier_score_loss(targets, scores)),
        "calibration_curve": {
            "fraction_of_positives": [float(value) for value in calibration[0]],
            "mean_predicted_value": [float(value) for value in calibration[1]],
        },
        "threshold_0_50": {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
            "recall": ratio(true_positives, true_positives + false_negatives),
            "precision": ratio(true_positives, true_positives + false_positives),
            "specificity": ratio(true_negatives, true_negatives + false_positives),
            "alert_rate": float(np.mean(thresholded)),
        },
    }


def _build_hist_gradient_boosting_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(**_MODEL_CONSTRUCTOR_DEFAULTS)


def fit_predictive_baseline(
    rows: Sequence[PredictiveTrainingRow],
    *,
    fit_end: datetime,
    calibration_end: datetime,
) -> PredictiveBaseline:
    """Fit the locked baseline on explicit chronological partitions.

    This is the build-time seam. Runtime scoring uses a serialized result from
    this function and never invokes it.
    """
    normalized_rows = _normalise_training_rows(rows)
    fit_boundary = _utc_datetime(
        fit_end,
        code="PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
    )
    calibration_boundary = _utc_datetime(
        calibration_end,
        code="PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
    )
    if fit_boundary >= calibration_boundary:
        raise PredictiveScoringFailure(
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
            "Predictive partition boundaries are not chronological.",
        )

    fit_rows = [row for row in normalized_rows if row.committed_at < fit_boundary]
    calibration_rows = [
        row
        for row in normalized_rows
        if fit_boundary <= row.committed_at < calibration_boundary
    ]
    evaluation_rows = [
        row for row in normalized_rows if row.committed_at >= calibration_boundary
    ]
    if not fit_rows or not calibration_rows or not evaluation_rows:
        raise PredictiveScoringFailure(
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
            "Every locked chronological predictive partition must contain rows.",
        )
    if len({row.target for row in fit_rows}) < 2 or len({row.target for row in calibration_rows}) < 2:
        raise PredictiveScoringFailure(
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
            "Fit and calibration partitions must contain both target classes.",
        )

    fit_features = np.vstack(
        [_feature_vector(row.features, missing_code="PREDICTIVE_FEATURE_CONTRACT_MISMATCH") for row in fit_rows]
    )
    calibration_features = np.vstack(
        [
            _feature_vector(
                row.features,
                missing_code="PREDICTIVE_FEATURE_CONTRACT_MISMATCH",
            )
            for row in calibration_rows
        ]
    )
    evaluation_features = np.vstack(
        [
            _feature_vector(
                row.features,
                missing_code="PREDICTIVE_FEATURE_CONTRACT_MISMATCH",
            )
            for row in evaluation_rows
        ]
    )
    fit_targets = np.asarray([row.target for row in fit_rows], dtype=np.int8)
    calibration_targets = np.asarray(
        [row.target for row in calibration_rows],
        dtype=np.int8,
    )
    model = _build_hist_gradient_boosting_model()
    model.fit(fit_features, fit_targets)
    calibrated_model = CalibratedClassifierCV(
        estimator=FrozenEstimator(model),
        method="sigmoid",
        cv=None,
        n_jobs=1,
        ensemble="auto",
    )
    calibrated_model.fit(calibration_features, calibration_targets)
    evaluation_scores = calibrated_model.predict_proba(evaluation_features)[:, 1]
    if not np.isfinite(evaluation_scores).all() or not (
        (evaluation_scores >= 0).all() and (evaluation_scores <= 1).all()
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_SCORE_INVALID",
            "The calibrated evaluation scores are outside the probability range.",
        )

    background_rows = sorted(
        fit_rows,
        key=_stable_row_identity_hash,
    )[:200]
    evaluation_order = sorted(evaluation_rows, key=_stable_row_identity_hash)
    background_features = np.vstack(
        [
            _feature_vector(
                row.features,
                missing_code="PREDICTIVE_FEATURE_CONTRACT_MISMATCH",
            )
            for row in background_rows
        ]
    )
    report = {
        "schema_version": PREDICTIVE_BASELINE_REPORT_SCHEMA_VERSION,
        "dataset_version_id": normalized_rows[0].dataset_version_id,
        "training_dataset_version_id": normalized_rows[0].dataset_version_id,
        "fit_cohort_hash": _cohort_hash(fit_rows),
        "calibration_cohort_hash": _cohort_hash(calibration_rows),
        "evaluation_cohort_hash": _cohort_hash(evaluation_rows),
        "partition_boundaries": {
            "fit_end": fit_boundary.isoformat(),
            "calibration_end": calibration_boundary.isoformat(),
        },
        "target": {
            "definition_id": TARGET_DEFINITION_ID,
            "milestone_kind": TARGET_MILESTONE_KIND,
            "semantic": SCORE_SEMANTIC,
        },
        "feature_contract": {
            "version": FEATURE_CONTRACT_VERSION,
            "ordered_features": list(FEATURE_NAMES),
            "dtype": "float64",
            "missingness": "required-point-in-time-features-only",
            "forbidden_inputs": [
                "later_progress",
                "promise_revisions",
                "escalation",
                "expediting",
                "premium_freight",
                "recovery_actions",
                "outcomes",
            ],
        },
        "cohort_contract": {
            "commitment_clock": "committed_at",
            "original_promise": "original_promise",
            "target_outcome": TARGET_DEFINITION_ID,
            "follow_up_maturity": "follow_up_maturity",
            "lineage": "lineage_refs",
        },
        "model": {
            "implementation": "sklearn.ensemble.HistGradientBoostingClassifier",
            "constructor_defaults": deepcopy(_MODEL_CONSTRUCTOR_DEFAULTS),
            "random_state": 0,
            "early_stopping": False,
            "class_weight": None,
        },
        "calibration": {
            "method": "sigmoid",
            "estimator": "sklearn.frozen.FrozenEstimator",
            "calibration_n_jobs": 1,
        },
        "dependencies": {
            "scikit-learn": sklearn_version,
            "shap": shap.__version__,
            "joblib": joblib.__version__,
        },
        "partitions": {
            "fit": _partition_report(fit_rows),
            "calibration": _partition_report(calibration_rows),
            "evaluation": _partition_report(evaluation_rows),
        },
        "evaluation": _evaluation_metrics(evaluation_rows, evaluation_scores),
        "threshold": ALERT_THRESHOLD,
        "background_selector": {
            "version": BACKGROUND_SELECTOR_VERSION,
            "source": "fit_population",
            "outcome_independent": True,
            "maximum_rows": 200,
            "ordered_row_ids": [row.row_id for row in background_rows],
            "identity_hash": _json_hash(
                [row.row_id for row in background_rows]
            ),
            "feature_matrix_hash": _json_hash(background_features.tolist()),
        },
        "evaluation_selector": {
            "version": EVALUATION_SELECTOR_VERSION,
            "source": "untouched_evaluation_partition",
            "ordered_row_ids": [row.row_id for row in evaluation_order],
            "identity_hash": _json_hash([row.row_id for row in evaluation_order]),
        },
        "shap": {
            "method": SHAP_METHOD,
            "link": SHAP_LINK,
            "seed": SHAP_SEED,
            "max_evals": 10 * (2 * len(FEATURE_NAMES) + 1),
            "background_feature_matrix_hash": _json_hash(background_features.tolist()),
        },
        "model_artifact_ref": "",
        "artifact_sha256": "",
        "report_sha256": "",
        "non_causal_label": PREDICTION_PERFORMANCE_LABEL,
    }
    return PredictiveBaseline(
        base_model=model,
        calibrated_model=calibrated_model,
        background_features=background_features,
        background_row_ids=tuple(row.row_id for row in background_rows),
        report=report,
    )


def _artifact_ref(artifact_sha256: str) -> str:
    return f"bundled://predictive-stub/model/{artifact_sha256}"


def _report_hash(report: Mapping[str, Any]) -> str:
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    return _json_hash(body)


def write_predictive_baseline(
    baseline: PredictiveBaseline,
    artifact_path: Path,
    report_path: Path,
) -> None:
    """Seal one build-time model artifact and its report."""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    joblib.dump(baseline.artifact_payload(), buffer, compress=3, protocol=5)
    artifact_bytes = buffer.getvalue()
    artifact_path.write_bytes(artifact_bytes)
    artifact_sha256 = _sha256(artifact_bytes)
    baseline.artifact_ref = _artifact_ref(artifact_sha256)
    baseline.report["model_artifact_ref"] = baseline.artifact_ref
    baseline.report["artifact_sha256"] = artifact_sha256
    baseline.report["report_sha256"] = _report_hash(baseline.report)
    report_path.write_text(
        json.dumps(
            baseline.report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("report is not an object")
    return value


def _artifact_failure(message: str) -> PredictiveScoringFailure:
    return PredictiveScoringFailure("PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE", message)


def load_predictive_baseline(
    artifact_path: Path,
    report_path: Path,
) -> PredictiveBaseline:
    """Load and verify a bundled artifact; never trains at runtime."""
    try:
        artifact_bytes = artifact_path.read_bytes()
        report = _load_json(report_path)
        artifact_sha256 = _sha256(artifact_bytes)
        if report.get("schema_version") != PREDICTIVE_BASELINE_REPORT_SCHEMA_VERSION:
            raise _artifact_failure("The predictive report schema is unsupported.")
        if report.get("artifact_sha256") != artifact_sha256:
            raise _artifact_failure("The predictive artifact digest does not match.")
        if report.get("model_artifact_ref") != _artifact_ref(artifact_sha256):
            raise _artifact_failure("The predictive artifact reference is inconsistent.")
        if report.get("report_sha256") != _report_hash(report):
            raise _artifact_failure("The predictive report integrity check failed.")
        payload = joblib.load(BytesIO(artifact_bytes))
        if not isinstance(payload, Mapping):
            raise _artifact_failure("The predictive artifact is not a sealed mapping.")
        required = {
            "schema_version",
            "predictor_id",
            "predictor_version",
            "feature_contract_version",
            "target_definition_id",
            "target_milestone_kind",
            "score_semantic",
            "alert_threshold",
            "feature_names",
            "base_model",
            "calibrated_model",
            "background_features",
            "background_row_ids",
        }
        if set(payload) != required:
            raise _artifact_failure("The predictive artifact fields are incomplete.")
        if (
            payload["schema_version"] != PREDICTIVE_BASELINE_ARTIFACT_SCHEMA_VERSION
            or payload["predictor_id"] != PREDICTOR_ID
            or payload["predictor_version"] != PREDICTOR_VERSION
            or payload["feature_contract_version"] != FEATURE_CONTRACT_VERSION
            or payload["target_definition_id"] != TARGET_DEFINITION_ID
            or payload["target_milestone_kind"] != TARGET_MILESTONE_KIND
            or payload["score_semantic"] != SCORE_SEMANTIC
            or payload["alert_threshold"] != ALERT_THRESHOLD
            or payload["feature_names"] != list(FEATURE_NAMES)
        ):
            raise _artifact_failure("The predictive artifact contract is incompatible.")
        base_model = payload["base_model"]
        calibrated_model = payload["calibrated_model"]
        if not isinstance(base_model, HistGradientBoostingClassifier):
            raise _artifact_failure("The predictive base estimator is unsupported.")
        if not isinstance(calibrated_model, CalibratedClassifierCV):
            raise _artifact_failure("The predictive calibrator is unsupported.")
        if not isinstance(calibrated_model.estimator, FrozenEstimator):
            raise _artifact_failure("The predictive calibrator is not frozen.")
        if calibrated_model.n_jobs != 1 or calibrated_model.method != "sigmoid":
            raise _artifact_failure("The predictive calibrator settings are incompatible.")
        if sklearn_version != PINNED_SKLEARN_VERSION or shap.__version__ != PINNED_SHAP_VERSION:
            raise _artifact_failure("The scientific dependency versions are unsupported.")
        if joblib.__version__ != PINNED_JOBLIB_VERSION:
            raise _artifact_failure("The model serialization dependency version is unsupported.")
        if base_model.get_params() != _MODEL_CONSTRUCTOR_DEFAULTS:
            raise _artifact_failure("The predictive base estimator settings are incompatible.")
        background_features = np.asarray(payload["background_features"], dtype=np.float64)
        background_row_ids = tuple(str(value) for value in payload["background_row_ids"])
        if (
            background_features.ndim != 2
            or background_features.shape[1] != len(FEATURE_NAMES)
            or background_features.shape[0] != len(background_row_ids)
            or background_features.shape[0] == 0
            or not np.isfinite(background_features).all()
        ):
                raise _artifact_failure("The predictive background matrix is invalid.")
        if report.get("feature_contract", {}).get("ordered_features") != list(FEATURE_NAMES):
            raise _artifact_failure("The runtime feature contract does not match the report.")
        if report.get("threshold") != ALERT_THRESHOLD:
            raise _artifact_failure("The predictive threshold is not the locked value.")
        if report.get("target") != {
            "definition_id": TARGET_DEFINITION_ID,
            "milestone_kind": TARGET_MILESTONE_KIND,
            "semantic": SCORE_SEMANTIC,
        }:
            raise _artifact_failure("The predictive target report is incompatible.")
        if report.get("model") != {
            "implementation": "sklearn.ensemble.HistGradientBoostingClassifier",
            "constructor_defaults": _MODEL_CONSTRUCTOR_DEFAULTS,
            "random_state": 0,
            "early_stopping": False,
            "class_weight": None,
        }:
            raise _artifact_failure("The predictive model report is incompatible.")
        if report.get("calibration") != {
            "method": "sigmoid",
            "estimator": "sklearn.frozen.FrozenEstimator",
            "calibration_n_jobs": 1,
        }:
            raise _artifact_failure("The predictive calibration report is incompatible.")
        if report.get("dependencies") != {
            "scikit-learn": PINNED_SKLEARN_VERSION,
            "shap": PINNED_SHAP_VERSION,
            "joblib": PINNED_JOBLIB_VERSION,
        }:
            raise _artifact_failure("The predictive dependency report is incompatible.")
        if report.get("non_causal_label") != PREDICTION_PERFORMANCE_LABEL:
            raise _artifact_failure("The predictive non-causal label is missing.")
        background_selector = report.get("background_selector")
        if not isinstance(background_selector, Mapping) or (
            background_selector.get("version") != BACKGROUND_SELECTOR_VERSION
            or background_selector.get("ordered_row_ids") != list(background_row_ids)
            or background_selector.get("identity_hash")
            != _json_hash(list(background_row_ids))
            or background_selector.get("feature_matrix_hash")
            != _json_hash(background_features.tolist())
        ):
            raise _artifact_failure("The predictive background selector is incompatible.")
        evaluation_selector = report.get("evaluation_selector")
        if not isinstance(evaluation_selector, Mapping):
            raise _artifact_failure("The predictive evaluation selector is missing.")
        evaluation_row_ids = evaluation_selector.get("ordered_row_ids")
        if (
            evaluation_selector.get("version") != EVALUATION_SELECTOR_VERSION
            or evaluation_selector.get("source") != "untouched_evaluation_partition"
            or not isinstance(evaluation_row_ids, list)
            or not evaluation_row_ids
            or not all(isinstance(row_id, str) and row_id for row_id in evaluation_row_ids)
            or len(set(evaluation_row_ids)) != len(evaluation_row_ids)
            or evaluation_selector.get("identity_hash") != _json_hash(evaluation_row_ids)
        ):
            raise _artifact_failure("The predictive evaluation selector is incompatible.")
        shap_report = report.get("shap")
        if not isinstance(shap_report, Mapping) or shap_report.get("method") != SHAP_METHOD or (
            shap_report.get("link") != SHAP_LINK
            or shap_report.get("seed") != SHAP_SEED
            or shap_report.get("max_evals") != 10 * (2 * len(FEATURE_NAMES) + 1)
            or shap_report.get("background_feature_matrix_hash")
            != _json_hash(background_features.tolist())
        ):
            raise _artifact_failure("The predictive attribution settings are incompatible.")
        return PredictiveBaseline(
            base_model=base_model,
            calibrated_model=calibrated_model,
            background_features=background_features,
            background_row_ids=background_row_ids,
            report=report,
            artifact_ref=str(report["model_artifact_ref"]),
        )
    except PredictiveScoringFailure:
        raise
    except Exception as error:
        raise _artifact_failure("The predictive artifact could not be loaded safely.") from error


def _validate_prediction_score(score_value: float) -> None:
    if not math.isfinite(score_value) or not 0 <= score_value <= 1:
        raise PredictiveScoringFailure(
            "PREDICTIVE_SCORE_INVALID",
            "The calibrated score is outside the probability range.",
        )


def _attribution_ref(attribution: Mapping[str, Any]) -> str:
    body = {key: value for key, value in attribution.items() if key != "artifact_ref"}
    return f"bundled://predictive-stub/attribution/{_json_hash(body)}"


def _validate_additivity(
    attribution: Mapping[str, Any],
    *,
    expected_score: float,
) -> None:
    if attribution.get("schema_version") != PREDICTIVE_ATTRIBUTION_SCHEMA_VERSION:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution schema is unsupported.",
        )
    if (
        attribution.get("label") != PREDICTIVE_ATTRIBUTION_LABEL
        or attribution.get("predictor_id") != PREDICTOR_ID
        or attribution.get("predictor_version") != PREDICTOR_VERSION
        or attribution.get("feature_contract_version") != FEATURE_CONTRACT_VERSION
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution identity is incompatible.",
        )
    contributions = attribution.get("contributions")
    if (
        not isinstance(contributions, list)
        or [
            item.get("name") for item in contributions if isinstance(item, Mapping)
        ] != list(FEATURE_NAMES)
        or not all(
            isinstance(item, Mapping)
            and isinstance(item.get("contribution"), (int, float))
            and math.isfinite(float(item["contribution"]))
            for item in contributions
        )
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution feature alignment is invalid.",
        )
    base_value = attribution.get("base_value")
    reconstructed = attribution.get("reconstructed_probability")
    residual = attribution.get("additivity_residual")
    if not all(
        isinstance(value, (int, float)) and math.isfinite(float(value))
        for value in (base_value, reconstructed, residual)
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution contains a non-finite value.",
        )
    expected_reconstruction = float(base_value) + sum(
        float(item["contribution"]) for item in contributions
    )
    if abs(expected_reconstruction - float(expected_score)) > 1e-6:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution does not reconstruct the calibrated score.",
        )
    if abs(float(reconstructed) - float(expected_score)) > 1e-6 or abs(float(residual)) > 1e-6:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution additivity validation failed.",
        )


def _validate_attribution_binding(
    attribution: Mapping[str, Any],
    *,
    expected_model_artifact_ref: str | None = None,
    expected_prediction_record_id: str | None = None,
    expected_dataset_version_id: str | None = None,
    expected_order_line_id: str | None = None,
    expected_background_identity_hash: str | None = None,
    expected_features: Mapping[str, float] | None = None,
) -> None:
    expected_values = {
        "model_artifact_ref": expected_model_artifact_ref,
        "prediction_record_id": expected_prediction_record_id,
        "dataset_version_id": expected_dataset_version_id,
        "order_line_id": expected_order_line_id,
        "background_identity_hash": expected_background_identity_hash,
    }
    for field_name, expected in expected_values.items():
        if expected is not None and attribution.get(field_name) != expected:
            raise PredictiveScoringFailure(
                "PREDICTIVE_ATTRIBUTION_INVALID",
                "The predictive attribution is not bound to its prediction artifact.",
            )
    if expected_features is not None:
        feature_values = attribution.get("feature_values")
        if not isinstance(feature_values, list) or len(feature_values) != len(FEATURE_NAMES):
            raise PredictiveScoringFailure(
                "PREDICTIVE_ATTRIBUTION_INVALID",
                "The predictive attribution feature snapshot is invalid.",
            )
        for item, name in zip(feature_values, FEATURE_NAMES, strict=True):
            if (
                not isinstance(item, Mapping)
                or item.get("name") != name
                or item.get("missingness") != "present"
                or not isinstance(item.get("value"), (int, float))
                or float(item["value"]) != float(expected_features[name])
            ):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution feature snapshot does not match the subject.",
                )


def validate_predictive_attribution(
    attribution: Mapping[str, Any],
    *,
    expected_score: float,
    expected_model_artifact_ref: str | None = None,
    expected_prediction_record_id: str | None = None,
    expected_dataset_version_id: str | None = None,
    expected_order_line_id: str | None = None,
    expected_background_identity_hash: str | None = None,
    expected_features: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Validate a local attribution before it is exposed to the UI."""
    _validate_additivity(attribution, expected_score=expected_score)
    _validate_attribution_binding(
        attribution,
        expected_model_artifact_ref=expected_model_artifact_ref,
        expected_prediction_record_id=expected_prediction_record_id,
        expected_dataset_version_id=expected_dataset_version_id,
        expected_order_line_id=expected_order_line_id,
        expected_background_identity_hash=expected_background_identity_hash,
        expected_features=expected_features,
    )
    return dict(attribution)


def _global_attribution_ref(attribution: Mapping[str, Any]) -> str:
    body = {key: value for key, value in attribution.items() if key != "artifact_ref"}
    return f"bundled://predictive-stub/global-attribution/{_json_hash(body)}"


def _validate_global_attribution(
    attribution: Mapping[str, Any],
    *,
    expected_model_artifact_ref: str | None = None,
) -> None:
    if (
        attribution.get("schema_version") != "predictive-global-attribution.v1"
        or attribution.get("label") != PREDICTIVE_ATTRIBUTION_LABEL
        or not isinstance(attribution.get("artifact_ref"), str)
        or attribution.get("artifact_ref") != _global_attribution_ref(attribution)
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The global predictive attribution identity is invalid.",
        )
    if (
        expected_model_artifact_ref is not None
        and attribution.get("model_artifact_ref") != expected_model_artifact_ref
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The global predictive attribution is bound to another model.",
        )
    feature_names = attribution.get("feature_names")
    mean_absolute_contributions = attribution.get("mean_absolute_contributions")
    if feature_names != list(FEATURE_NAMES) or not isinstance(
        mean_absolute_contributions, list
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The global predictive attribution feature contract is invalid.",
        )
    if [
        item.get("name") for item in mean_absolute_contributions if isinstance(item, Mapping)
    ] != list(FEATURE_NAMES) or not all(
        isinstance(item, Mapping)
        and isinstance(item.get("mean_absolute_contribution"), (int, float))
        and math.isfinite(float(item["mean_absolute_contribution"]))
        and float(item["mean_absolute_contribution"]) >= 0
        for item in mean_absolute_contributions
    ):
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The global predictive attribution values are invalid.",
        )


def load_predictive_attribution_bundle(
    path: Path,
    *,
    expected_model_artifact_ref: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Load and verify the local attribution artifacts referenced by signals."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping) or raw.get("schema_version") != (
            "predictive-attribution-bundle.v1"
        ):
            raise PredictiveScoringFailure(
                "PREDICTIVE_ATTRIBUTION_INVALID",
                "The predictive attribution bundle schema is unsupported.",
            )
        items = raw.get("items")
        if not isinstance(items, list):
            raise PredictiveScoringFailure(
                "PREDICTIVE_ATTRIBUTION_INVALID",
                "The predictive attribution bundle has no item list.",
            )
        verified: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, Mapping):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution bundle contains an invalid item.",
                )
            attribution = dict(item)
            artifact_ref = attribution.get("artifact_ref")
            expected_ref = _attribution_ref(attribution)
            if not isinstance(artifact_ref, str) or artifact_ref != expected_ref:
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution reference is inconsistent.",
                )
            score_value = attribution.get("score_value")
            if not isinstance(score_value, (int, float)):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution has no score.",
                )
            _validate_additivity(attribution, expected_score=float(score_value))
            if not isinstance(attribution.get("model_artifact_ref"), str) or not attribution[
                "model_artifact_ref"
            ]:
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution has no model artifact identity.",
                )
            if (
                expected_model_artifact_ref is not None
                and attribution["model_artifact_ref"] != expected_model_artifact_ref
            ):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution is bound to another model.",
                )
            if artifact_ref in verified:
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The predictive attribution bundle contains duplicate references.",
                )
            verified[artifact_ref] = attribution
        global_attribution = raw.get("global")
        if global_attribution is not None:
            if not isinstance(global_attribution, Mapping):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The global predictive attribution is not an object.",
                )
            _validate_global_attribution(
                global_attribution,
                expected_model_artifact_ref=expected_model_artifact_ref,
            )
            local_refs = global_attribution.get("local_attribution_refs")
            if not isinstance(local_refs, list) or not local_refs or any(
                not isinstance(reference, str) or reference not in verified
                for reference in local_refs
            ):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_ATTRIBUTION_INVALID",
                    "The global predictive attribution references unknown local artifacts.",
                )
        return verified
    except PredictiveScoringFailure:
        raise
    except Exception as error:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution bundle could not be loaded safely.",
        ) from error


def _build_attribution(
    baseline: PredictiveBaseline,
    subject: PredictiveSubject,
    vector: np.ndarray,
    score_value: float,
) -> dict[str, Any]:
    max_evals = 10 * (2 * len(FEATURE_NAMES) + 1)

    def calibrated_probability(values: np.ndarray) -> np.ndarray:
        matrix = np.asarray(values, dtype=np.float64)
        return baseline.calibrated_model.predict_proba(matrix)[:, 1]

    try:
        explainer = shap.PermutationExplainer(
            calibrated_probability,
            np.asarray(baseline.background_features, dtype=np.float64),
            link=shap.links.identity,
            feature_names=list(FEATURE_NAMES),
            seed=SHAP_SEED,
        )
        explanation = explainer(vector.reshape(1, -1), max_evals=max_evals)
        values = np.asarray(explanation.values, dtype=np.float64).reshape(-1)
        base_values = np.asarray(explanation.base_values, dtype=np.float64).reshape(-1)
        if len(values) != len(FEATURE_NAMES) or len(base_values) == 0:
            raise ValueError("SHAP output shape is invalid")
        base_value = float(base_values[0])
        reconstructed = base_value + float(np.sum(values))
        residual = abs(reconstructed - score_value)
        if not math.isfinite(residual) or residual > 1e-6:
            raise PredictiveScoringFailure(
                "PREDICTIVE_ATTRIBUTION_INVALID",
                "The predictive attribution failed calibrated-score reconstruction.",
            )
        contributions = [
            {"name": name, "contribution": float(value)}
            for name, value in zip(FEATURE_NAMES, values, strict=True)
        ]
        ranked = sorted(
            contributions,
            key=lambda item: (-abs(float(item["contribution"])), str(item["name"])),
        )
        top = ranked[:5]
        top_names = {str(item["name"]) for item in top}
        other_features = sum(
            float(item["contribution"])
            for item in contributions
            if str(item["name"]) not in top_names
        )
        attribution = {
            "schema_version": PREDICTIVE_ATTRIBUTION_SCHEMA_VERSION,
            "artifact_ref": "",
            "label": PREDICTIVE_ATTRIBUTION_LABEL,
            "predictor_id": PREDICTOR_ID,
            "predictor_version": PREDICTOR_VERSION,
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "model_artifact_ref": baseline.artifact_ref,
            "prediction_record_id": subject.prediction_record_id,
            "dataset_version_id": subject.dataset_version_id,
            "order_line_id": subject.order_line_id,
            "generated_at": _iso_datetime(subject.generated_at),
            "background_selector_version": BACKGROUND_SELECTOR_VERSION,
            "background_row_ids": list(baseline.background_row_ids),
            "background_identity_hash": baseline.report["background_selector"][
                "identity_hash"
            ],
            "shap": {
                "version": shap.__version__,
                "method": SHAP_METHOD,
                "link": SHAP_LINK,
                "seed": SHAP_SEED,
                "feature_count": len(FEATURE_NAMES),
                "max_evals": max_evals,
            },
            "feature_values": [
                {"name": name, "value": float(vector[index]), "missingness": "present"}
                for index, name in enumerate(FEATURE_NAMES)
            ],
            "base_value": base_value,
            "contributions": contributions,
            "reconstructed_probability": reconstructed,
            "score_value": score_value,
            "additivity_residual": residual,
            "validation_status": "valid",
            "presentation": {
                "top_contributions": top,
                "other_features": float(other_features),
            },
        }
        _validate_additivity(attribution, expected_score=score_value)
        attribution["artifact_ref"] = _attribution_ref(attribution)
        return attribution
    except PredictiveScoringFailure:
        raise
    except Exception as error:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The predictive attribution could not be generated safely.",
        ) from error


def load_prediction_record_bundle(
    path: Path,
    *,
    expected_model_artifact_ref: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Load immutable prediction records and verify their deterministic identities."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping) or raw.get("schema_version") != (
            "prediction-record-bundle.v1"
        ):
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The prediction record bundle schema is unsupported.",
            )
        items = raw.get("items")
        if not isinstance(items, list):
            raise PredictiveScoringFailure(
                "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                "The prediction record bundle has no item list.",
            )
        verified: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, Mapping):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    "The prediction record bundle contains an invalid item.",
                )
            record = dict(item)
            record_id = record.get("prediction_record_id")
            generated_at = record.get("generated_at")
            if not isinstance(record_id, str) or not record_id or not isinstance(
                generated_at, str
            ):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    "A prediction record has no deterministic identity.",
                )
            try:
                expected_id = predictive_prediction_record_id(
                    str(record["dataset_version_id"]),
                    str(record["order_line_id"]),
                    datetime.fromisoformat(generated_at),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise PredictiveScoringFailure(
                    "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    "A prediction record has an invalid scoring clock.",
                ) from error
            score_value = record.get("score_value")
            if (
                record.get("schema_version") != "prediction-record.v1"
                or record_id != expected_id
                or not isinstance(record.get("dataset_version_id"), str)
                or not isinstance(record.get("order_line_id"), str)
                or record.get("predictor_id") != PREDICTOR_ID
                or record.get("predictor_version") != PREDICTOR_VERSION
                or record.get("feature_contract_version") != FEATURE_CONTRACT_VERSION
                or record.get("target_definition_id") != TARGET_DEFINITION_ID
                or record.get("target_milestone_kind") != TARGET_MILESTONE_KIND
                or record.get("score_semantic") != SCORE_SEMANTIC
                or record.get("alert_threshold") != ALERT_THRESHOLD
                or not isinstance(score_value, (int, float))
                or not math.isfinite(float(score_value))
                or not 0 <= float(score_value) <= 1
                or record.get("flagged") != (float(score_value) >= ALERT_THRESHOLD)
                or not isinstance(record.get("model_artifact_ref"), str)
                or not record["model_artifact_ref"]
                or not isinstance(record.get("feature_snapshot_hash"), str)
                or not record["feature_snapshot_hash"]
            ):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    "A prediction record is incompatible with the locked contract.",
                )
            if (
                expected_model_artifact_ref is not None
                and record["model_artifact_ref"] != expected_model_artifact_ref
            ):
                raise PredictiveScoringFailure(
                    "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    "A prediction record is bound to another model artifact.",
                )
            if record_id in verified:
                raise PredictiveScoringFailure(
                    "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
                    "The prediction record bundle contains duplicate identities.",
                )
            verified[record_id] = record
        return verified
    except PredictiveScoringFailure:
        raise
    except Exception as error:
        raise PredictiveScoringFailure(
            "PREDICTIVE_STUB_ARTIFACT_UNAVAILABLE",
            "The prediction record bundle could not be loaded safely.",
        ) from error


def score_predictive_subject(
    baseline: PredictiveBaseline,
    subject: PredictiveSubject,
) -> PredictiveScoreResult:
    """Score one point-in-time subject and create its non-causal attribution."""
    _utc_datetime(
        subject.generated_at,
        code="PREDICTIVE_SUBJECT_UNSCORABLE",
    )
    expected_prediction_record_id = predictive_prediction_record_id(
        subject.dataset_version_id,
        subject.order_line_id,
        subject.generated_at,
    )
    if subject.prediction_record_id not in (None, expected_prediction_record_id):
        raise PredictiveScoringFailure(
            "PREDICTIVE_SUBJECT_UNSCORABLE",
            "The prediction record identity does not match the frozen subject.",
        )
    resolved_subject = PredictiveSubject(
        prediction_record_id=expected_prediction_record_id,
        dataset_version_id=subject.dataset_version_id,
        order_line_id=subject.order_line_id,
        generated_at=subject.generated_at,
        features=subject.features,
    )
    vector = _feature_vector(
        subject.features,
        missing_code="PREDICTIVE_SUBJECT_UNSCORABLE",
    )
    try:
        score_value = float(baseline.calibrated_model.predict_proba(vector.reshape(1, -1))[0, 1])
    except Exception as error:
        raise PredictiveScoringFailure(
            "PREDICTIVE_SCORE_INVALID",
            "The predictive artifact could not score the subject.",
        ) from error
    _validate_prediction_score(score_value)
    feature_snapshot_hash = _json_hash(
        {
            "dataset_version_id": subject.dataset_version_id,
            "order_line_id": subject.order_line_id,
            "generated_at": _iso_datetime(subject.generated_at),
            "features": {
                name: float(subject.features[name]) for name in FEATURE_NAMES
            },
        }
    )
    prediction_record = {
        "schema_version": "prediction-record.v1",
        "prediction_record_id": expected_prediction_record_id,
        "dataset_version_id": subject.dataset_version_id,
        "order_line_id": subject.order_line_id,
        "predictor_id": PREDICTOR_ID,
        "predictor_version": PREDICTOR_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "target_definition_id": TARGET_DEFINITION_ID,
        "target_milestone_kind": TARGET_MILESTONE_KIND,
        "generated_at": _iso_datetime(subject.generated_at),
        "score_semantic": SCORE_SEMANTIC,
        "score_value": score_value,
        "alert_threshold": ALERT_THRESHOLD,
        "flagged": score_value >= ALERT_THRESHOLD,
        "model_artifact_ref": baseline.artifact_ref,
        "feature_snapshot_hash": feature_snapshot_hash,
        "predictive_attribution_ref": {"state": "missing"},
    }
    attribution = _build_attribution(baseline, resolved_subject, vector, score_value)
    prediction_record["predictive_attribution_ref"] = {
        "state": "present",
        "value": attribution["artifact_ref"],
    }
    return PredictiveScoreResult(
        prediction_record=prediction_record,
        attribution=attribution,
    )


def build_global_predictive_attribution(
    baseline: PredictiveBaseline,
    subjects: Sequence[PredictiveSubject],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Explain the untouched evaluation cohort and retain a global summary."""
    if not subjects:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The global predictive attribution cohort is empty.",
        )
    dataset_versions = {subject.dataset_version_id for subject in subjects}
    if len(dataset_versions) != 1:
        raise PredictiveScoringFailure(
            "PREDICTIVE_ATTRIBUTION_INVALID",
            "The global predictive attribution cohort spans Dataset Versions.",
        )
    ordered_subjects = sorted(
        subjects,
        key=lambda subject: _json_hash(
            {
                "dataset_version_id": subject.dataset_version_id,
                "order_line_id": subject.order_line_id,
                "prediction_record_id": subject.prediction_record_id,
            }
        ),
    )
    results = tuple(score_predictive_subject(baseline, subject) for subject in ordered_subjects)
    mean_absolute_contributions = [
        {
            "name": name,
            "mean_absolute_contribution": float(
                np.mean(
                    [
                        abs(float(next(item["contribution"] for item in result.attribution["contributions"] if item["name"] == name)))
                        for result in results
                    ]
                )
            ),
        }
        for name in FEATURE_NAMES
    ]
    attribution = {
        "schema_version": "predictive-global-attribution.v1",
        "artifact_ref": "",
        "label": PREDICTIVE_ATTRIBUTION_LABEL,
        "model_artifact_ref": baseline.artifact_ref,
        "predictor_id": PREDICTOR_ID,
        "predictor_version": PREDICTOR_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "dataset_version_id": next(iter(dataset_versions)),
        "background_selector_version": BACKGROUND_SELECTOR_VERSION,
        "background_identity_hash": baseline.report["background_selector"]["identity_hash"],
        "evaluation_prediction_record_ids": [
            result.prediction_record["prediction_record_id"] for result in results
        ],
        "local_attribution_refs": [result.attribution["artifact_ref"] for result in results],
        "feature_names": list(FEATURE_NAMES),
        "mean_absolute_contributions": mean_absolute_contributions,
        "validation_status": "valid",
    }
    attribution["artifact_ref"] = _global_attribution_ref(attribution)
    _validate_global_attribution(attribution, expected_model_artifact_ref=baseline.artifact_ref)
    return attribution, tuple(result.attribution for result in results)
