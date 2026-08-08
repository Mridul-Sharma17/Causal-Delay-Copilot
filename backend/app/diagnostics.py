from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping, Sequence

from .canonical import sha256
from .eligibility import evaluate_propensity_overlap


DIAGNOSTIC_RESULT_SCHEMA_VERSION = "diagnostic-result.v1"
DIAGNOSTIC_ARTIFACT_SCHEMA_VERSION = "diagnostic_artifacts.v1"
DIAGNOSTIC_POLICY_ID = "causal-validity-verdict-policy"
DIAGNOSTIC_POLICY_VERSION = "1"
DIAGNOSTIC_SCOPE = "population"

PRIMARY_INTERVAL_DIAGNOSTIC_ID = "primary_interval"
COVARIATE_BALANCE_DIAGNOSTIC_ID = "covariate_balance"
OVERLAP_DIAGNOSTIC_ID = "overlap"
INHERITED_ELIGIBILITY_DIAGNOSTIC_ID = "inherited_eligibility"
CORE_DIAGNOSTIC_IDS = (
    PRIMARY_INTERVAL_DIAGNOSTIC_ID,
    COVARIATE_BALANCE_DIAGNOSTIC_ID,
    OVERLAP_DIAGNOSTIC_ID,
    INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
)

DIAGNOSTIC_STATUSES = frozenset(
    {"PASS", "FAIL", "UNSUPPORTED", "UNAVAILABLE", "FAILED", "NOT_RUN"}
)
VERDICT_EFFECTS = frozenset({"NONE", "FRAGILITY", "VETO", "INSUFFICIENT"})

_DIAGNOSTIC_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "diagnostic_id",
        "diagnostic_version",
        "scope",
        "status",
        "policy_id",
        "policy_version",
        "rule_id",
        "rule_version",
        "observed",
        "threshold",
        "result",
        "verdict_effect",
        "trigger_codes",
        "reason_code",
        "reason",
        "analysis_run_id",
        "bundle_manifest_hash",
        "evidence_refs",
        "input_refs",
        "diagnostic_identity",
        "content_hash",
    }
)
_DIAGNOSTIC_OPTIONAL_KEYS = frozenset({"upstream_trigger"})

_INTERVAL_RULE = "primary-interval-sign"
_BALANCE_RULE = "atte-covariate-balance"
_OVERLAP_RULE = "propensity-common-support"
_ELIGIBILITY_RULE = "inherited-eligibility"

_POPULATION_ELIGIBILITY_CODES = (
    "SOURCE_SEMANTICS_INELIGIBLE",
    "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT",
    "CORE_TEMPORAL_COVERAGE_INSUFFICIENT",
    "OUTCOME_COVERAGE_INSUFFICIENT",
    "CANCELLATION_COMPETING_EVENT_PRESENT",
    "COVARIATE_COVERAGE_INSUFFICIENT",
    "COHORT_SUPPORT_INSUFFICIENT",
    "OUTCOME_DEGENERATE",
    "OVERLAP_COHORT_INSUFFICIENT",
)
_SUBJECT_ELIGIBILITY_CODES = (
    "PROACTIVE_SUBJECT_INPUT_UNUSABLE",
    "COMMITMENT_CUTOFF_UNUSABLE",
    "TARGET_MILESTONE_UNSUPPORTED",
    "LOAD_SNAPSHOT_UNRESOLVABLE",
    "SUPPLIER_HISTORY_INSUFFICIENT",
    "FROZEN_PROMISE_UNAVAILABLE",
    "FROZEN_PROMISE_CONFLICT",
    "FROZEN_PROMISE_TEMPORALLY_INVALID",
    "COVARIATE_TEMPORAL_LEAKAGE",
    "REQUIRED_COVARIATE_UNUSABLE",
    "SUBJECT_OVERLAP_INSUFFICIENT",
    "SUBJECT_DISTRIBUTION_UNSUPPORTED",
)
_POPULATION_CODE_ORDER = {
    code: index for index, code in enumerate(_POPULATION_ELIGIBILITY_CODES)
}
_SUBJECT_CODE_ORDER = {
    code: index for index, code in enumerate(_SUBJECT_ELIGIBILITY_CODES)
}


class DiagnosticIntegrityError(ValueError):
    """A diagnostic payload is not a valid immutable Core result."""


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: object) -> float | None:
    if _finite_number(value):
        return float(value)
    if isinstance(value, Mapping) and value.get("state") == "present":
        return _number(value.get("value"))
    return None


def _ordered_unique(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result


def _context(
    *,
    analysis_run_id: str | None,
    bundle_manifest_hash: str | None,
    evidence_refs: Sequence[str],
    input_refs: Sequence[str],
    policy_id: str,
    policy_version: str,
) -> dict[str, Any]:
    return {
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": _ordered_unique(evidence_refs),
        "input_refs": _ordered_unique(input_refs),
        "policy_id": policy_id,
        "policy_version": policy_version,
    }


def _make_result(
    diagnostic_id: str,
    *,
    rule_id: str,
    status: str,
    scope: str,
    observed: Mapping[str, Any] | None,
    threshold: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    verdict_effect: str,
    trigger_codes: Sequence[str],
    reason_code: str,
    reason: str,
    upstream_trigger: str | None = None,
    diagnostic_version: str = "1",
    rule_version: str = "1",
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    if status not in DIAGNOSTIC_STATUSES:
        raise DiagnosticIntegrityError("diagnostic status is unsupported")
    if verdict_effect not in VERDICT_EFFECTS:
        raise DiagnosticIntegrityError("diagnostic verdict effect is unsupported")
    if not isinstance(reason_code, str) or not reason_code:
        raise DiagnosticIntegrityError("diagnostic reason code is unavailable")
    if not isinstance(reason, str) or not reason:
        raise DiagnosticIntegrityError("diagnostic reason is unavailable")

    context = _context(
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
        policy_id=policy_id,
        policy_version=policy_version,
    )
    identity_payload = {
        "schema_version": DIAGNOSTIC_RESULT_SCHEMA_VERSION,
        "diagnostic_id": diagnostic_id,
        "diagnostic_version": diagnostic_version,
        "scope": scope,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "observed": deepcopy(dict(observed)) if observed is not None else None,
        "threshold": deepcopy(dict(threshold)),
        "result": deepcopy(dict(result)) if result is not None else None,
        "verdict_effect": verdict_effect,
        "trigger_codes": _ordered_unique(trigger_codes),
        "reason_code": reason_code,
        "reason": reason,
        **context,
    }
    record: dict[str, Any] = {
        "schema_version": DIAGNOSTIC_RESULT_SCHEMA_VERSION,
        "diagnostic_id": diagnostic_id,
        "diagnostic_version": diagnostic_version,
        "scope": scope,
        "status": status,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "observed": deepcopy(dict(observed)) if observed is not None else None,
        "threshold": deepcopy(dict(threshold)),
        "result": deepcopy(dict(result)) if result is not None else None,
        "verdict_effect": verdict_effect,
        "trigger_codes": _ordered_unique(trigger_codes),
        "reason_code": reason_code,
        "reason": reason,
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": _ordered_unique(evidence_refs),
        "input_refs": _ordered_unique(input_refs),
        "diagnostic_identity": sha256(identity_payload),
    }
    if upstream_trigger is not None:
        record["upstream_trigger"] = upstream_trigger
    record["content_hash"] = sha256(record)
    return record


def _unavailable(
    diagnostic_id: str,
    *,
    rule_id: str,
    reason_code: str,
    reason: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return _make_result(
        diagnostic_id,
        rule_id=rule_id,
        status="UNAVAILABLE",
        scope=kwargs.pop("scope", DIAGNOSTIC_SCOPE),
        observed=None,
        threshold=kwargs.pop("threshold", {}),
        result=None,
        verdict_effect="NONE",
        trigger_codes=(),
        reason_code=reason_code,
        reason=reason,
        **kwargs,
    )


def _not_run(
    diagnostic_id: str,
    *,
    rule_id: str,
    upstream_trigger: str,
    reason: str,
    threshold: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    return _make_result(
        diagnostic_id,
        rule_id=rule_id,
        status="NOT_RUN",
        scope=kwargs.pop("scope", DIAGNOSTIC_SCOPE),
        observed=None,
        threshold=threshold,
        result=None,
        verdict_effect="NONE",
        trigger_codes=(),
        reason_code="UPSTREAM_SHORT_CIRCUIT",
        reason=reason,
        upstream_trigger=upstream_trigger,
        **kwargs,
    )


def _interval_values(effect: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    estimate = _number(effect.get("estimate", effect.get("effect")))
    lower = _number(effect.get("ci_lower", effect.get("interval_lower")))
    upper = _number(effect.get("ci_upper", effect.get("interval_upper")))
    interval = effect.get("confidence_interval", effect.get("interval"))
    if isinstance(interval, Mapping):
        lower = _number(interval.get("lower", interval.get("ci_lower")))
        upper = _number(interval.get("upper", interval.get("ci_upper")))
    if estimate is None or lower is None or upper is None:
        return None
    return estimate, lower, upper, _number(effect.get("ci_level", 0.95)) or 0.0


def evaluate_primary_interval(
    effect: Mapping[str, Any] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    """Evaluate the directional primary two-sided 95% interval policy."""

    threshold = {
        "direction": "positive",
        "null": 0.0,
        "ci_level": 0.95,
        "endpoint_rule": "zero_is_inconclusive",
    }
    identity = {
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": evidence_refs,
        "input_refs": input_refs,
        "policy_id": policy_id,
        "policy_version": policy_version,
    }
    if effect is None:
        return _unavailable(
            PRIMARY_INTERVAL_DIAGNOSTIC_ID,
            rule_id=_INTERVAL_RULE,
            reason_code="PRIMARY_INTERVAL_UNAVAILABLE",
            reason="The verified evidence bundle contains no primary interval.",
            threshold=threshold,
            scope=scope,
            **identity,
        )
    values = _interval_values(effect)
    if values is None:
        return _make_result(
            PRIMARY_INTERVAL_DIAGNOSTIC_ID,
            rule_id=_INTERVAL_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="PRIMARY_INTERVAL_INVALID",
            reason="The primary interval is not a finite ordered 95% interval.",
            **identity,
        )
    estimate, lower, upper, ci_level = values
    observed = {
        "estimate": estimate,
        "ci_lower": lower,
        "ci_upper": upper,
        "ci_level": ci_level,
    }
    if ci_level != 0.95 or lower > upper:
        return _make_result(
            PRIMARY_INTERVAL_DIAGNOSTIC_ID,
            rule_id=_INTERVAL_RULE,
            status="FAILED",
            scope=scope,
            observed=observed,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="PRIMARY_INTERVAL_INVALID",
            reason="The primary interval is not a finite ordered 95% interval.",
            **identity,
        )
    if lower > 0:
        return _make_result(
            PRIMARY_INTERVAL_DIAGNOSTIC_ID,
            rule_id=_INTERVAL_RULE,
            status="PASS",
            scope=scope,
            observed=observed,
            threshold=threshold,
            result={"direction": "positive"},
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="PRIMARY_INTERVAL_POSITIVE",
            reason="The complete primary interval is above zero.",
            **identity,
        )
    trigger = (
        "PRIMARY_INTERVAL_INCLUDES_NULL" if upper >= 0 else "PRIMARY_EFFECT_OPPOSITE_DIRECTION"
    )
    reason = (
        "The primary interval includes zero, so the proposed delay driver is inconclusive."
        if trigger == "PRIMARY_INTERVAL_INCLUDES_NULL"
        else "The primary interval is below zero and points opposite to the proposed delay driver."
    )
    return _make_result(
        PRIMARY_INTERVAL_DIAGNOSTIC_ID,
        rule_id=_INTERVAL_RULE,
        status="FAIL",
        scope=scope,
        observed=observed,
        threshold=threshold,
        result={"direction": "non_positive", "reason_class": "INCONCLUSIVE"},
        verdict_effect="INSUFFICIENT",
        trigger_codes=[trigger],
        reason_code=trigger,
        reason=reason,
        **identity,
    )


def _row_features(row: Mapping[str, Any], feature_order: Sequence[str] | None) -> Mapping[str, Any] | None:
    for key in ("features", "covariates", "adjustment_features"):
        candidate = row.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    if feature_order is None:
        return None
    return {feature: row.get(feature) for feature in feature_order}


def _row_exposure(row: Mapping[str, Any]) -> bool | None:
    for key in ("exposure", "high_load_exposure", "treatment"):
        if key not in row:
            continue
        value = row[key]
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        return None
    return None


def _row_propensity(row: Mapping[str, Any]) -> float | None:
    for key in ("propensity", "p", "mean_out_of_fold_propensity"):
        if key in row:
            return _number(row[key])
    return None


def _normalise_balance_rows(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    feature_matrix: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]] | None,
    exposure: Sequence[Any] | None,
    propensities: Sequence[Any] | None,
    feature_order: Sequence[str] | None,
) -> tuple[list[dict[str, Any]] | None, list[str] | None, str | None]:
    if rows is None and feature_matrix is not None:
        if isinstance(feature_matrix, Mapping):
            if exposure is None or propensities is None:
                return None, None, "BALANCE_INPUT_INVALID"
            lengths = {len(values) for values in feature_matrix.values()}
            lengths.update({len(exposure), len(propensities)})
            if len(lengths) != 1:
                return None, None, "BALANCE_INPUT_INVALID"
            ordered = list(feature_order or feature_matrix.keys())
            rows = [
                {
                    "exposure": exposure[index],
                    "propensity": propensities[index],
                    "features": {
                        name: feature_matrix[name][index]
                        for name in ordered
                        if name in feature_matrix
                    },
                }
                for index in range(len(exposure))
            ]
        elif isinstance(feature_matrix, Sequence) and not isinstance(feature_matrix, (str, bytes)):
            rows = feature_matrix
        else:
            return None, None, "BALANCE_INPUT_INVALID"
    if rows is None:
        return None, None, None
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        return None, None, "BALANCE_INPUT_INVALID"

    normalised: list[dict[str, Any]] = []
    discovered_order: list[str] = list(feature_order or ())
    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            return None, None, "BALANCE_INPUT_INVALID"
        row_features = _row_features(raw_row, feature_order)
        row_exposure = _row_exposure(raw_row)
        row_propensity = _row_propensity(raw_row)
        if row_features is None or row_exposure is None or row_propensity is None:
            return None, None, "BALANCE_INPUT_INVALID"
        if not discovered_order:
            discovered_order = [str(name) for name in row_features]
        elif list(row_features) != discovered_order:
            if set(row_features) != set(discovered_order):
                return None, None, "BALANCE_FEATURE_ORDER_INVALID"
        normalised.append(
            {
                "exposure": row_exposure,
                "propensity": row_propensity,
                "features": dict(row_features),
            }
        )
    return normalised, discovered_order, None


def _sample_variance(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    total = sum(weights)
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / total


def _diagnostic_number(value: float) -> float | dict[str, str]:
    if math.isinf(value):
        return {"state": "positive_infinity"}
    return value


def evaluate_covariate_balance(
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    feature_matrix: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]] | None = None,
    exposure: Sequence[Any] | None = None,
    propensities: Sequence[Any] | None = None,
    feature_order: Sequence[str] | None = None,
    scope: str = DIAGNOSTIC_SCOPE,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    """Evaluate ATTE weighted standardized mean differences on post-trim rows."""

    threshold = {
        "absolute_weighted_smd_max": 0.10,
        "inclusive": True,
        "exposed_weight": "1",
        "unexposed_weight": "p / (1 - p)",
        "unexposed_weight_normalization": "sum_equals_exposed_count",
        "variance_denominator": "n-1",
    }
    identity = {
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": evidence_refs,
        "input_refs": input_refs,
        "policy_id": policy_id,
        "policy_version": policy_version,
    }
    normalised, ordered_features, error_code = _normalise_balance_rows(
        rows,
        feature_matrix=feature_matrix,
        exposure=exposure,
        propensities=propensities,
        feature_order=feature_order,
    )
    if normalised is None:
        if error_code is None:
            return _unavailable(
                COVARIATE_BALANCE_DIAGNOSTIC_ID,
                rule_id=_BALANCE_RULE,
                reason_code="COVARIATE_BALANCE_UNAVAILABLE",
                reason="The verified evidence bundle contains no post-trim balance inputs.",
                threshold=threshold,
                scope=scope,
                **identity,
            )
        return _make_result(
            COVARIATE_BALANCE_DIAGNOSTIC_ID,
            rule_id=_BALANCE_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code=error_code,
            reason="The verified balance inputs do not match the frozen feature contract.",
            **identity,
        )
    assert ordered_features is not None
    if not ordered_features or len(set(ordered_features)) != len(ordered_features):
        return _make_result(
            COVARIATE_BALANCE_DIAGNOSTIC_ID,
            rule_id=_BALANCE_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="BALANCE_FEATURE_ORDER_INVALID",
            reason="The verified balance feature order is not canonical.",
            **identity,
        )

    exposed = [row for row in normalised if row["exposure"]]
    unexposed = [row for row in normalised if not row["exposure"]]
    if len(exposed) < 2 or len(unexposed) < 2:
        return _make_result(
            COVARIATE_BALANCE_DIAGNOSTIC_ID,
            rule_id=_BALANCE_RULE,
            status="FAILED",
            scope=scope,
            observed={"exposed_count": len(exposed), "unexposed_count": len(unexposed)},
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="BALANCE_ARM_SUPPORT_INVALID",
            reason="An ATTE balance arm has fewer than two post-trim rows.",
            **identity,
        )

    unexposed_raw_weights: list[float] = []
    for row in unexposed:
        propensity = row["propensity"]
        if not _finite_number(propensity) or not 0.0 <= float(propensity) < 1.0:
            return _make_result(
                COVARIATE_BALANCE_DIAGNOSTIC_ID,
                rule_id=_BALANCE_RULE,
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=(),
                reason_code="BALANCE_PROPENSITY_INVALID",
                reason="The authoritative propensity contains a non-finite or out-of-range value.",
                **identity,
            )
        unexposed_raw_weights.append(float(propensity) / (1.0 - float(propensity)))
    exposed_weights = [1.0] * len(exposed)
    raw_sum = sum(unexposed_raw_weights)
    if not math.isfinite(raw_sum) or raw_sum <= 0.0:
        return _make_result(
            COVARIATE_BALANCE_DIAGNOSTIC_ID,
            rule_id=_BALANCE_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="BALANCE_WEIGHT_INVALID",
            reason="The ATTE unexposed weights cannot be normalized.",
            **identity,
        )
    normalization = len(exposed) / raw_sum
    unexposed_weights = [weight * normalization for weight in unexposed_raw_weights]
    if not all(math.isfinite(weight) and weight > 0.0 for weight in unexposed_weights):
        return _make_result(
            COVARIATE_BALANCE_DIAGNOSTIC_ID,
            rule_id=_BALANCE_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="BALANCE_WEIGHT_INVALID",
            reason="The ATTE unexposed weights cannot be normalized.",
            **identity,
        )

    feature_results: list[dict[str, Any]] = []
    smd_values: list[float] = []
    for feature in ordered_features:
        exposed_values = [_number(row["features"].get(feature)) for row in exposed]
        unexposed_values = [_number(row["features"].get(feature)) for row in unexposed]
        if any(value is None for value in (*exposed_values, *unexposed_values)):
            return _make_result(
                COVARIATE_BALANCE_DIAGNOSTIC_ID,
                rule_id=_BALANCE_RULE,
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=(),
                reason_code="BALANCE_FEATURE_VALUE_INVALID",
                reason="A materialized balance feature is not finite numeric data.",
                **identity,
            )
        exposed_numeric = [float(value) for value in exposed_values if value is not None]
        unexposed_numeric = [float(value) for value in unexposed_values if value is not None]
        exposed_mean = _weighted_mean(exposed_numeric, exposed_weights)
        unexposed_mean = _weighted_mean(unexposed_numeric, unexposed_weights)
        pooled_variance = (
            _sample_variance(exposed_numeric) + _sample_variance(unexposed_numeric)
        ) / 2.0
        mean_difference = abs(exposed_mean - unexposed_mean)
        if pooled_variance == 0.0:
            smd = 0.0 if mean_difference == 0.0 else math.inf
        else:
            smd = mean_difference / math.sqrt(pooled_variance)
        if math.isclose(smd, 0.10, rel_tol=0.0, abs_tol=math.ulp(0.10) * 4):
            smd = 0.10
        smd_values.append(smd)
        feature_results.append(
            {
                "feature": feature,
                "weighted_mean_exposed": exposed_mean,
                "weighted_mean_unexposed": unexposed_mean,
                "unweighted_variance_exposed": _sample_variance(exposed_numeric),
                "unweighted_variance_unexposed": _sample_variance(unexposed_numeric),
                "absolute_weighted_smd": _diagnostic_number(smd),
            }
        )
    maximum = max(smd_values)
    offending = [
        item["feature"]
        for item, smd in zip(feature_results, smd_values, strict=True)
        if smd > threshold["absolute_weighted_smd_max"]
    ]
    status = "FAIL" if offending else "PASS"
    return _make_result(
        COVARIATE_BALANCE_DIAGNOSTIC_ID,
        rule_id=_BALANCE_RULE,
        status=status,
        scope=scope,
        observed={
            "exposed_count": len(exposed),
            "unexposed_count": len(unexposed),
            "exposed_weight_sum": sum(exposed_weights),
            "unexposed_raw_weight_sum": raw_sum,
            "unexposed_weight_sum": sum(unexposed_weights),
            "features": feature_results,
            "maximum_absolute_weighted_smd": _diagnostic_number(maximum),
            "offending_features": offending,
        },
        threshold=threshold,
        result={"feature_order": list(ordered_features)},
        verdict_effect="VETO" if offending else "NONE",
        trigger_codes=["COVARIATE_BALANCE_FAILED"] if offending else [],
        reason_code="COVARIATE_BALANCE_FAILED" if offending else "COVARIATE_BALANCE_PASSED",
        reason=(
            "At least one absolute weighted standardized mean difference is above 0.10."
            if offending
            else "Every absolute weighted standardized mean difference is at most 0.10."
        ),
        **identity,
    )


def _overlap_threshold() -> dict[str, Any]:
    return {"lower": 0.10, "upper": 0.90, "inclusive": True}


def evaluate_overlap(
    overlap: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    """Publish the frozen inclusive common-support result without refitting."""

    threshold = _overlap_threshold()
    identity = {
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": evidence_refs,
        "input_refs": input_refs,
        "policy_id": policy_id,
        "policy_version": policy_version,
    }
    if overlap is None:
        return _unavailable(
            OVERLAP_DIAGNOSTIC_ID,
            rule_id=_OVERLAP_RULE,
            reason_code="OVERLAP_UNAVAILABLE",
            reason="The verified evidence bundle contains no overlap result.",
            threshold=threshold,
            scope=scope,
            **identity,
        )
    if isinstance(overlap, Sequence) and not isinstance(overlap, (str, bytes, Mapping)):
        if not overlap:
            return _unavailable(
                OVERLAP_DIAGNOSTIC_ID,
                rule_id=_OVERLAP_RULE,
                reason_code="OVERLAP_UNAVAILABLE",
                reason="The verified evidence bundle contains no overlap result.",
                threshold=threshold,
                scope=scope,
                **identity,
            )
        try:
            payload = evaluate_propensity_overlap(overlap)
        except (TypeError, ValueError, KeyError):
            payload = None
        if payload is None:
            return _make_result(
                OVERLAP_DIAGNOSTIC_ID,
                rule_id=_OVERLAP_RULE,
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=(),
                reason_code="OVERLAP_INPUT_INVALID",
                reason="The verified overlap inputs do not match the frozen score contract.",
                **identity,
            )
    elif isinstance(overlap, Mapping):
        if "diagnostic_result" in overlap and isinstance(overlap["diagnostic_result"], Mapping):
            verified = verify_diagnostic_result(
                overlap["diagnostic_result"],
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                policy_id=policy_id,
                policy_version=policy_version,
            )
            if verified.get("diagnostic_id") != OVERLAP_DIAGNOSTIC_ID:
                raise DiagnosticIntegrityError("overlap diagnostic identity is unsupported")
            return verified
        nested_overlap = overlap.get("overlap")
        payload = (
            deepcopy(dict(nested_overlap))
            if isinstance(nested_overlap, Mapping)
            else deepcopy(dict(overlap))
        )
        if "support_interval" not in payload and isinstance(overlap.get("support_interval"), Mapping):
            payload["support_interval"] = deepcopy(dict(overlap["support_interval"]))
    else:
        return _make_result(
            OVERLAP_DIAGNOSTIC_ID,
            rule_id=_OVERLAP_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="OVERLAP_INPUT_INVALID",
            reason="The verified overlap inputs do not match the frozen score contract.",
            **identity,
        )

    supplied_threshold = payload.get("support_interval", payload.get("threshold"))
    if supplied_threshold is not None:
        if not isinstance(supplied_threshold, Mapping) or dict(supplied_threshold) != threshold:
            return _make_result(
                OVERLAP_DIAGNOSTIC_ID,
                rule_id=_OVERLAP_RULE,
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=(),
                reason_code="OVERLAP_POLICY_MISMATCH",
                reason="The verified overlap result does not bind the frozen support interval.",
                **identity,
            )
    state = payload.get("state", payload.get("status"))
    if state in {"supported", "passed", "PASS", "eligible"}:
        status = "PASS"
        effect = "NONE"
        triggers: list[str] = []
        reason_code = "OVERLAP_SUPPORTED"
        reason = "The retained propensity cohort satisfies the inclusive common-support rule."
    elif state in {"not_run", "NOT_RUN"}:
        trigger_codes = _ordered_unique(
            payload.get("eligibility_codes", payload.get("trigger_codes", []))
        )
        upstream_trigger = str(
            payload.get("reason_code")
            or (trigger_codes[0] if trigger_codes else "UPSTREAM_SHORT_CIRCUIT")
        )
        return _not_run(
            OVERLAP_DIAGNOSTIC_ID,
            rule_id=_OVERLAP_RULE,
            upstream_trigger=upstream_trigger,
            reason="The upstream scientific gate stopped overlap evaluation before execution.",
            threshold=threshold,
            scope=scope,
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
            policy_id=policy_id,
            policy_version=policy_version,
        )
    elif state in {"unsupported", "scientifically_unavailable", "failed", "FAIL"}:
        status = "FAIL"
        effect = "INSUFFICIENT"
        triggers = _ordered_unique(payload.get("eligibility_codes", payload.get("trigger_codes", [])))
        if not triggers:
            triggers = ["OVERLAP_COHORT_INSUFFICIENT"]
        if "PROPENSITY_SCORES_UNAVAILABLE" in triggers:
            return _make_result(
                OVERLAP_DIAGNOSTIC_ID,
                rule_id=_OVERLAP_RULE,
                status="FAILED",
                scope=scope,
                observed=payload,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=triggers,
                reason_code="PROPENSITY_SCORES_UNAVAILABLE",
                reason="The verified overlap result has no authoritative propensity scores.",
                **identity,
            )
        reason_code = triggers[0]
        reason = "The retained propensity cohort does not satisfy the common-support rule."
    elif state in {"unavailable", "UNAVAILABLE"}:
        return _unavailable(
            OVERLAP_DIAGNOSTIC_ID,
            rule_id=_OVERLAP_RULE,
            reason_code="OVERLAP_UNAVAILABLE",
            reason="The verified evidence bundle contains no usable overlap result.",
            threshold=threshold,
            scope=scope,
            **identity,
        )
    else:
        return _make_result(
            OVERLAP_DIAGNOSTIC_ID,
            rule_id=_OVERLAP_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="OVERLAP_RESULT_INVALID",
            reason="The verified overlap result has an unsupported state.",
            **identity,
        )
    return _make_result(
        OVERLAP_DIAGNOSTIC_ID,
        rule_id=_OVERLAP_RULE,
        status=status,
        scope=scope,
        observed=payload,
        threshold=threshold,
        result={
            "retained_count": payload.get("retained_count"),
            "trimmed_count": payload.get("trimmed_count"),
        },
        verdict_effect=effect,
        trigger_codes=triggers,
        reason_code=reason_code,
        reason=reason,
        **identity,
    )


def _eligibility_codes(value: Mapping[str, Any], scope: str) -> list[str]:
    if scope == "subject":
        subject = value.get("subject")
        if isinstance(subject, Mapping) and isinstance(subject.get("eligibility_codes"), list):
            return _ordered_unique(subject["eligibility_codes"])
        return _ordered_unique(value.get("subject_eligibility_codes", []))
    variants = value.get("variants")
    if isinstance(variants, Mapping):
        primary = variants.get("primary")
        if isinstance(primary, Mapping) and isinstance(primary.get("eligibility_codes"), list):
            return _ordered_unique(primary["eligibility_codes"])
    cohort = value.get("cohort")
    if isinstance(cohort, Mapping) and isinstance(cohort.get("eligibility_codes"), list):
        return _ordered_unique(cohort["eligibility_codes"])
    for key in ("inherited_codes", "eligibility_codes", "codes"):
        if isinstance(value.get(key), list):
            return _ordered_unique(value[key])
    return []


def evaluate_inherited_eligibility(
    eligibility: Mapping[str, Any] | Sequence[str] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    """Publish upstream eligibility without recomputing or changing its meaning."""

    threshold = {
        "scope": scope,
        "code_registry_version": "validity-inherited-eligibility.v1",
    }
    identity = {
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": evidence_refs,
        "input_refs": input_refs,
        "policy_id": policy_id,
        "policy_version": policy_version,
    }
    if scope not in {"population", "subject"}:
        return _make_result(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="INHERITED_ELIGIBILITY_SCOPE_INVALID",
            reason="The inherited eligibility scope is not registered.",
            **identity,
        )
    if eligibility is None:
        return _unavailable(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            reason_code="INHERITED_ELIGIBILITY_UNAVAILABLE",
            reason="The verified evidence bundle contains no upstream eligibility result.",
            threshold=threshold,
            scope=scope,
            **identity,
        )
    if isinstance(eligibility, Mapping):
        codes = _eligibility_codes(eligibility, scope)
        upstream_state = eligibility.get("state", eligibility.get("status"))
    elif isinstance(eligibility, Sequence) and not isinstance(eligibility, (str, bytes)):
        codes = _ordered_unique(eligibility)
        upstream_state = None
    else:
        return _make_result(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="INHERITED_ELIGIBILITY_INPUT_INVALID",
            reason="The verified upstream eligibility result has an unsupported shape.",
            **identity,
        )

    allowed = _POPULATION_ELIGIBILITY_CODES if scope == "population" else _SUBJECT_ELIGIBILITY_CODES
    allowed_set = set(allowed)
    unknown = [code for code in codes if code not in allowed_set]
    if unknown:
        return _make_result(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            status="FAILED",
            scope=scope,
            observed={"eligibility_codes": codes},
            threshold=threshold,
            result={"unknown_codes": unknown},
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="INHERITED_ELIGIBILITY_CODE_INVALID",
            reason="The upstream eligibility result contains an unknown or mis-scoped code.",
            **identity,
        )
    ordered = sorted(codes, key=lambda code: _POPULATION_CODE_ORDER[code] if scope == "population" else _SUBJECT_CODE_ORDER[code])
    if ordered:
        reason_code = ordered[0]
        return _make_result(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            status="FAIL",
            scope=scope,
            observed={
                "state": upstream_state,
                "eligibility_codes": ordered,
            },
            threshold=threshold,
            result={"reason_class": "NOT_ESTIMABLE"},
            verdict_effect="INSUFFICIENT",
            trigger_codes=ordered,
            reason_code=reason_code,
            reason="An upstream eligibility gate abstained this population before a valid estimate.",
            **identity,
        )
    if upstream_state in {"eligible", "supported", "passed", "estimated"}:
        return _make_result(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            status="PASS",
            scope=scope,
            observed={"state": upstream_state, "eligibility_codes": []},
            threshold=threshold,
            result={"reason_class": None},
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="INHERITED_ELIGIBILITY_PASSED",
            reason="The upstream eligibility result reports no applicable abstention code.",
            **identity,
        )
    if upstream_state in {"scientifically_unavailable", "ineligible", "unsupported", "failed"}:
        return _make_result(
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            rule_id=_ELIGIBILITY_RULE,
            status="FAILED",
            scope=scope,
            observed={"state": upstream_state, "eligibility_codes": []},
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=(),
            reason_code="INHERITED_ELIGIBILITY_CODE_MISSING",
            reason="The upstream eligibility state is negative but provides no registered code.",
            **identity,
        )
    return _unavailable(
        INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
        rule_id=_ELIGIBILITY_RULE,
        reason_code="INHERITED_ELIGIBILITY_UNAVAILABLE",
        reason="The verified evidence bundle contains no resolved upstream eligibility state.",
        threshold=threshold,
        scope=scope,
        **identity,
    )


def _first_mapping(value: Mapping[str, Any], keys: Sequence[str]) -> Mapping[str, Any] | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _not_run_after(
    diagnostic_id: str,
    *,
    rule_id: str,
    trigger: str,
    threshold: Mapping[str, Any],
    scope: str,
    analysis_run_id: str | None,
    bundle_manifest_hash: str | None,
    evidence_refs: Sequence[str],
    input_refs: Sequence[str],
    policy_id: str,
    policy_version: str,
) -> dict[str, Any]:
    return _not_run(
        diagnostic_id,
        rule_id=rule_id,
        upstream_trigger=trigger,
        reason="The upstream scientific gate stopped this diagnostic before execution.",
        threshold=threshold,
        scope=scope,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
        policy_id=policy_id,
        policy_version=policy_version,
    )


def evaluate_core_diagnostics(
    *,
    engine_result: Mapping[str, Any] | None = None,
    eligibility: Mapping[str, Any] | None = None,
    overlap: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    balance_rows: Sequence[Mapping[str, Any]] | None = None,
    balance_feature_matrix: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]] | None = None,
    balance_exposure: Sequence[Any] | None = None,
    balance_propensities: Sequence[Any] | None = None,
    feature_order: Sequence[str] | None = None,
    scope: str = DIAGNOSTIC_SCOPE,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> list[dict[str, Any]]:
    """Evaluate the four Core 10 diagnostics in a fixed publication order."""

    identity = {
        "analysis_run_id": analysis_run_id,
        "bundle_manifest_hash": bundle_manifest_hash,
        "evidence_refs": evidence_refs,
        "input_refs": input_refs,
        "policy_id": policy_id,
        "policy_version": policy_version,
    }
    upstream_eligibility = eligibility
    if upstream_eligibility is None and isinstance(engine_result, Mapping):
        candidate = engine_result.get("eligibility")
        if isinstance(candidate, Mapping):
            upstream_eligibility = candidate
    inherited = evaluate_inherited_eligibility(upstream_eligibility, scope=scope, **identity)

    overlap_input = overlap
    if overlap_input is None and isinstance(upstream_eligibility, Mapping):
        variants = upstream_eligibility.get("variants")
        primary = variants.get("primary") if isinstance(variants, Mapping) else None
        if isinstance(primary, Mapping):
            overlap_input = primary.get("overlap")
            if overlap_input is None:
                stages = primary.get("stages")
                if isinstance(stages, Mapping):
                    overlap_input = stages.get("S9_OVERLAP")
    if overlap_input is None and isinstance(engine_result, Mapping):
        overlap_input = _first_mapping(engine_result, ("overlap", "overlap_result"))
    overlap_result = evaluate_overlap(overlap_input, scope=scope, **identity)

    engine_status = None
    if isinstance(engine_result, Mapping):
        engine_status = engine_result.get("status", engine_result.get("engine_result_status"))
    upstream_failure: str | None = None
    if inherited["status"] in {"FAIL", "FAILED"}:
        upstream_failure = inherited["reason_code"]
    elif overlap_result["status"] in {"FAIL", "FAILED"}:
        upstream_failure = overlap_result["reason_code"]
    elif overlap_result["status"] == "NOT_RUN":
        upstream_failure = str(overlap_result.get("upstream_trigger", "UPSTREAM_SHORT_CIRCUIT"))
    elif engine_status == "failed":
        upstream_failure = "ENGINE_EXECUTION_FAILED"
    elif engine_status in {"abstained", "not_estimable"}:
        upstream_failure = "ENGINE_NOT_ESTIMABLE"

    if upstream_failure is not None:
        interval = _not_run_after(
            PRIMARY_INTERVAL_DIAGNOSTIC_ID,
            rule_id=_INTERVAL_RULE,
            trigger=upstream_failure,
            threshold={"direction": "positive", "null": 0.0, "ci_level": 0.95},
            scope=scope,
            **{key: value for key, value in identity.items() if key != "scope"},
        )
        balance = _not_run_after(
            COVARIATE_BALANCE_DIAGNOSTIC_ID,
            rule_id=_BALANCE_RULE,
            trigger=upstream_failure,
            threshold={"absolute_weighted_smd_max": 0.10, "inclusive": True},
            scope=scope,
            **{key: value for key, value in identity.items() if key != "scope"},
        )
        return [interval, balance, overlap_result, inherited]

    if engine_result is None:
        interval = evaluate_primary_interval(None, scope=scope, **identity)
        balance = evaluate_covariate_balance(
            balance_rows,
            feature_matrix=balance_feature_matrix,
            exposure=balance_exposure,
            propensities=balance_propensities,
            feature_order=feature_order,
            scope=scope,
            **identity,
        )
    else:
        primary_effect = _first_mapping(
            engine_result,
            ("primary_effect", "primary", "effect", "primary_atte"),
        )
        interval = evaluate_primary_interval(primary_effect, scope=scope, **identity)
        rows = balance_rows
        if rows is None:
            for key in ("balance_rows", "post_trim_rows", "estimator_visible_rows"):
                candidate = engine_result.get(key)
                if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
                    rows = candidate
                    break
        matrix = balance_feature_matrix
        if matrix is None:
            candidate = engine_result.get("feature_matrix")
            if isinstance(candidate, (Mapping, Sequence)) and not isinstance(candidate, (str, bytes)):
                matrix = candidate
        balance = evaluate_covariate_balance(
            rows,
            feature_matrix=matrix,
            exposure=balance_exposure,
            propensities=balance_propensities,
            feature_order=feature_order,
            scope=scope,
            **identity,
        )
    return [interval, balance, overlap_result, inherited]


def verify_diagnostic_result(
    value: Mapping[str, Any],
    *,
    analysis_run_id: str | None = None,
    bundle_manifest_hash: str | None = None,
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    """Verify a sealed diagnostic record before returning it to a reader."""

    if not isinstance(value, Mapping):
        raise DiagnosticIntegrityError("diagnostic result is not an object")
    record = deepcopy(dict(value))
    keys = set(record)
    if not _DIAGNOSTIC_REQUIRED_KEYS <= keys or not keys <= (
        _DIAGNOSTIC_REQUIRED_KEYS | _DIAGNOSTIC_OPTIONAL_KEYS
    ):
        raise DiagnosticIntegrityError("diagnostic result fields are unsupported")
    if record.get("schema_version") != DIAGNOSTIC_RESULT_SCHEMA_VERSION:
        raise DiagnosticIntegrityError("diagnostic result schema is unsupported")
    for key in (
        "diagnostic_id",
        "diagnostic_version",
        "scope",
        "policy_id",
        "policy_version",
        "rule_id",
        "rule_version",
        "reason_code",
        "reason",
    ):
        if not isinstance(record.get(key), str) or not record[key]:
            raise DiagnosticIntegrityError(f"diagnostic result {key} is invalid")
    if record.get("status") not in DIAGNOSTIC_STATUSES:
        raise DiagnosticIntegrityError("diagnostic result status is unsupported")
    if record.get("verdict_effect") not in VERDICT_EFFECTS:
        raise DiagnosticIntegrityError("diagnostic result verdict effect is unsupported")
    for key in ("observed", "result"):
        if record[key] is not None and not isinstance(record[key], Mapping):
            raise DiagnosticIntegrityError(f"diagnostic result {key} is invalid")
    if not isinstance(record["threshold"], Mapping):
        raise DiagnosticIntegrityError("diagnostic result threshold is invalid")
    for key in ("trigger_codes", "evidence_refs", "input_refs"):
        values = record[key]
        if not isinstance(values, list) or any(
            not isinstance(item, str) or not item for item in values
        ):
            raise DiagnosticIntegrityError(f"diagnostic result {key} is invalid")
    for key in ("analysis_run_id", "bundle_manifest_hash"):
        if record[key] is not None and not isinstance(record[key], str):
            raise DiagnosticIntegrityError(f"diagnostic result {key} is invalid")
    if record["status"] == "NOT_RUN":
        if not isinstance(record.get("upstream_trigger"), str) or not record["upstream_trigger"]:
            raise DiagnosticIntegrityError("not-run diagnostic trigger is missing")
        if record["observed"] is not None or record["result"] is not None:
            raise DiagnosticIntegrityError("not-run diagnostic contains an observed result")
    elif "upstream_trigger" in record:
        raise DiagnosticIntegrityError("upstream trigger is only valid for not-run results")
    if record.get("policy_id") != policy_id or record.get("policy_version") != policy_version:
        raise DiagnosticIntegrityError("diagnostic result policy does not match")
    if analysis_run_id is not None and record.get("analysis_run_id") != analysis_run_id:
        raise DiagnosticIntegrityError("diagnostic result run binding does not match")
    if bundle_manifest_hash is not None and record.get("bundle_manifest_hash") != bundle_manifest_hash:
        raise DiagnosticIntegrityError("diagnostic result bundle binding does not match")
    content_hash = record.pop("content_hash", None)
    if not isinstance(content_hash, str):
        raise DiagnosticIntegrityError("diagnostic result content hash is missing")
    try:
        content_matches = sha256(record) == content_hash
    except (TypeError, ValueError, OverflowError) as error:
        raise DiagnosticIntegrityError("diagnostic result content is not canonical") from error
    if not content_matches:
        raise DiagnosticIntegrityError("diagnostic result content hash does not match")
    identity_payload = {
        key: record.get(key)
        for key in (
            "schema_version",
            "diagnostic_id",
            "diagnostic_version",
            "scope",
            "rule_id",
            "rule_version",
            "analysis_run_id",
            "bundle_manifest_hash",
            "evidence_refs",
            "input_refs",
            "policy_id",
            "policy_version",
        )
    }
    identity_payload.update(
        {
            "observed": record.get("observed"),
            "threshold": record.get("threshold"),
            "result": record.get("result"),
            "verdict_effect": record.get("verdict_effect"),
            "trigger_codes": record.get("trigger_codes"),
            "reason_code": record.get("reason_code"),
            "reason": record.get("reason"),
        }
    )
    try:
        identity_matches = record.get("diagnostic_identity") == sha256(identity_payload)
    except (TypeError, ValueError, OverflowError) as error:
        raise DiagnosticIntegrityError("diagnostic result identity is not canonical") from error
    if not identity_matches:
        raise DiagnosticIntegrityError("diagnostic result identity does not match")
    record["content_hash"] = content_hash
    return record


def _missing_core_results(**kwargs: Any) -> list[dict[str, Any]]:
    rules = {
        PRIMARY_INTERVAL_DIAGNOSTIC_ID: _INTERVAL_RULE,
        COVARIATE_BALANCE_DIAGNOSTIC_ID: _BALANCE_RULE,
        OVERLAP_DIAGNOSTIC_ID: _OVERLAP_RULE,
        INHERITED_ELIGIBILITY_DIAGNOSTIC_ID: _ELIGIBILITY_RULE,
    }
    reasons = {
        PRIMARY_INTERVAL_DIAGNOSTIC_ID: "PRIMARY_INTERVAL_UNAVAILABLE",
        COVARIATE_BALANCE_DIAGNOSTIC_ID: "COVARIATE_BALANCE_UNAVAILABLE",
        OVERLAP_DIAGNOSTIC_ID: "OVERLAP_UNAVAILABLE",
        INHERITED_ELIGIBILITY_DIAGNOSTIC_ID: "INHERITED_ELIGIBILITY_UNAVAILABLE",
    }
    return [
        _unavailable(
            diagnostic_id,
            rule_id=rules[diagnostic_id],
            reason_code=reasons[diagnostic_id],
            reason="The verified evidence bundle contains no diagnostic inputs.",
            threshold=(
                _overlap_threshold()
                if diagnostic_id == OVERLAP_DIAGNOSTIC_ID
                else {"diagnostic_id": diagnostic_id}
            ),
            **kwargs,
        )
        for diagnostic_id in CORE_DIAGNOSTIC_IDS
    ]


def publish_diagnostic_results(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    *,
    analysis_run_id: str,
    bundle_manifest_hash: str,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> list[dict[str, Any]]:
    """Build or verify the four immutable Core 10 results from a reference payload."""

    if payload is None:
        return _missing_core_results(
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
            policy_id=policy_id,
            policy_version=policy_version,
        )
    records: object
    if isinstance(payload, Mapping):
        records = payload.get("results", payload.get("diagnostic_results"))
        if records is None:
            records = payload.get("diagnostics")
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        records = payload
    else:
        raise DiagnosticIntegrityError("diagnostic payload is unsupported")
    if isinstance(records, list):
        if not records:
            raise DiagnosticIntegrityError("diagnostic result list is empty")
        verified = [
            verify_diagnostic_result(
                item,
                analysis_run_id=analysis_run_id,
                bundle_manifest_hash=bundle_manifest_hash,
                policy_id=policy_id,
                policy_version=policy_version,
            )
            for item in records
        ]
        by_id = {item.get("diagnostic_id"): item for item in verified}
        if len(by_id) != len(verified):
            raise DiagnosticIntegrityError("diagnostic result set is incomplete or duplicated")
        from .refuters import NEGATIVE_CONTROL_DIAGNOSTIC_ID, REFUTER_DIAGNOSTIC_IDS

        refuter_order = (
            *CORE_DIAGNOSTIC_IDS,
            *REFUTER_DIAGNOSTIC_IDS,
            NEGATIVE_CONTROL_DIAGNOSTIC_ID,
        )
        expected_order: tuple[str, ...]
        if set(by_id) == set(CORE_DIAGNOSTIC_IDS):
            expected_order = CORE_DIAGNOSTIC_IDS
        elif set(by_id) == set(refuter_order):
            expected_order = refuter_order
        else:
            from .validity import VALIDITY_DIAGNOSTIC_IDS

            complete_order = (*refuter_order, *VALIDITY_DIAGNOSTIC_IDS)
            if set(by_id) != set(complete_order):
                raise DiagnosticIntegrityError("diagnostic result set is incomplete or unsupported")
            expected_order = complete_order
        if set(by_id) != set(expected_order):
            raise DiagnosticIntegrityError("diagnostic result set is incomplete or unsupported")
        return [by_id[diagnostic_id] for diagnostic_id in expected_order]
    if records is not None:
        raise DiagnosticIntegrityError("diagnostic result list is unsupported")

    raw = dict(payload)
    engine_result = _first_mapping(raw, ("engine_result", "causal_engine_result"))
    eligibility = _first_mapping(raw, ("eligibility", "pre_estimation_eligibility"))
    overlap = _first_mapping(raw, ("overlap", "overlap_result"))
    balance_rows = raw.get("balance_rows", raw.get("post_trim_rows"))
    balance_matrix = raw.get("feature_matrix")
    balance_exposure = raw.get("balance_exposure", raw.get("exposure"))
    balance_propensities = raw.get("balance_propensities", raw.get("propensities"))
    feature_order = raw.get("feature_order")
    has_raw_inputs = any(
        value is not None
        for value in (
            engine_result,
            eligibility,
            overlap,
            balance_rows,
            balance_matrix,
        )
    )
    if not has_raw_inputs:
        return _missing_core_results(
            analysis_run_id=analysis_run_id,
            bundle_manifest_hash=bundle_manifest_hash,
            evidence_refs=evidence_refs,
            input_refs=input_refs,
            policy_id=policy_id,
            policy_version=policy_version,
        )
    results = evaluate_core_diagnostics(
        engine_result=engine_result,
        eligibility=eligibility,
        overlap=overlap,
        balance_rows=balance_rows if isinstance(balance_rows, Sequence) else None,
        balance_feature_matrix=(
            balance_matrix
            if isinstance(balance_matrix, (Mapping, Sequence))
            and not isinstance(balance_matrix, (str, bytes))
            else None
        ),
        balance_exposure=(balance_exposure if isinstance(balance_exposure, Sequence) else None),
        balance_propensities=(
            balance_propensities if isinstance(balance_propensities, Sequence) else None
        ),
        feature_order=feature_order if isinstance(feature_order, Sequence) else None,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
        policy_id=policy_id,
        policy_version=policy_version,
    )
    if len(results) != len(CORE_DIAGNOSTIC_IDS):
        raise DiagnosticIntegrityError("diagnostic result set is incomplete")
    return results


def diagnostic_summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a small deterministic summary suitable for the first Evidence layer."""

    statuses = [str(item.get("status")) for item in results]
    if any(status in {"FAILED", "FAIL"} for status in statuses):
        state = "attention_required"
    elif any(status in {"UNAVAILABLE", "NOT_RUN", "UNSUPPORTED"} for status in statuses):
        state = "limited"
    else:
        state = "complete"
    return {
        "state": state,
        "diagnostic_count": len(results),
        "status_counts": {
            status: statuses.count(status)
            for status in sorted(set(statuses))
        },
    }


def evaluate_diagnostics(**kwargs: Any) -> list[dict[str, Any]]:
    """Compatibility alias for the declared Core diagnostic public seam."""

    if any(
        key in kwargs
        for key in (
            "refuter_rows",
            "refuter_primary_effect",
            "refuter_estimator_adapter",
            "negative_control_rows",
            "negative_control",
            "negative_control_spec",
            "specification_variants",
            "cross_form_variants",
            "comparison_results",
            "benchmark_groups",
            "repeat_results",
        )
    ):
        return evaluate_validity_diagnostics(**kwargs)
    return evaluate_core_diagnostics(**kwargs)


def build_diagnostic_results(
    payload: Mapping[str, Any] | None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Compatibility alias for publishing reference-bound diagnostic records."""

    return publish_diagnostic_results(payload, **kwargs)


def apply_refuter_transformation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Expose the registered transformation seam from the diagnostics module."""

    from .refuters import apply_refuter_transformation as _apply_refuter_transformation

    return _apply_refuter_transformation(*args, **kwargs)


def run_refuter_battery(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Run and seal the four registered refuter diagnostics."""

    from .refuters import run_refuter_battery as _run_refuter_battery

    return _run_refuter_battery(*args, **kwargs)


def evaluate_refuter_battery(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """Return the four refuter Diagnostic Results in canonical battery order."""

    from .refuters import evaluate_refuter_battery as _evaluate_refuter_battery

    return _evaluate_refuter_battery(*args, **kwargs)


def evaluate_negative_control(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Evaluate the reviewed negative-control outcome at its public seam."""

    from .refuters import evaluate_negative_control as _evaluate_negative_control

    return _evaluate_negative_control(*args, **kwargs)


def evaluate_validity_diagnostics(
    *,
    refuter_rows: Sequence[Mapping[str, Any]] | None = None,
    refuter_primary_effect: Mapping[str, Any] | None = None,
    refuter_estimator_adapter: object | None = None,
    refuter_seed_context: Mapping[str, Any] | None = None,
    refuter_primary_artifacts: Mapping[str, Any] | None = None,
    negative_control_rows: Sequence[Mapping[str, Any]] | None = None,
    negative_control: Mapping[str, Any] | None = None,
    negative_control_spec: Mapping[str, Any] | None = None,
    negative_control_estimator_adapter: object | None = None,
    negative_control_primary_outer_splits: Sequence[Mapping[str, Any]] | None = None,
    negative_control_primary_propensity_predictions: Mapping[str, Any] | Sequence[Any] | None = None,
    negative_control_primary_artifacts: Mapping[str, Any] | None = None,
    specification_variants: Mapping[str, Any] | None = None,
    cross_form_variants: Mapping[str, Any] | None = None,
    comparison_results: Mapping[str, Any] | None = None,
    benchmark_groups: Sequence[Mapping[str, Any]] | None = None,
    repeat_results: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    intended_role: str | None = None,
    **core_kwargs: Any,
) -> list[dict[str, Any]]:
    """Publish Core 10 plus refuter and negative-control diagnostics.

    The four existing Core diagnostics remain the first records. When an
    upstream eligibility or engine gate short-circuits, every added check is
    explicitly ``NOT_RUN`` rather than being omitted or treated as passing.
    """

    from .refuters import run_refuter_battery as _run_refuter_battery
    from .refuters import evaluate_negative_control as _evaluate_negative_control

    core_results = evaluate_core_diagnostics(**core_kwargs)
    upstream_trigger: str | None = None
    for diagnostic in core_results:
        if diagnostic.get("status") == "NOT_RUN":
            upstream_trigger = str(
                diagnostic.get("upstream_trigger", diagnostic.get("reason_code"))
            )
            break
    if upstream_trigger is None:
        for diagnostic_id in (
            INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
            OVERLAP_DIAGNOSTIC_ID,
        ):
            diagnostic = next(
                (
                    item
                    for item in core_results
                    if item.get("diagnostic_id") == diagnostic_id
                ),
                None,
            )
            if diagnostic is not None and diagnostic.get("status") in {"FAIL", "FAILED"}:
                upstream_trigger = str(diagnostic.get("reason_code"))
                break

    run_kwargs = {
        "rows": refuter_rows,
        "primary_effect": refuter_primary_effect,
        "estimator_adapter": refuter_estimator_adapter,
        "seed_context": refuter_seed_context,
        "primary_artifacts": refuter_primary_artifacts,
        "analysis_run_id": core_kwargs.get("analysis_run_id"),
        "bundle_manifest_hash": core_kwargs.get("bundle_manifest_hash"),
        "evidence_refs": core_kwargs.get("evidence_refs", ()),
        "input_refs": core_kwargs.get("input_refs", ()),
    }
    if upstream_trigger is not None:
        run_kwargs["upstream_trigger"] = upstream_trigger
    refuter_results = _run_refuter_battery(**run_kwargs)["diagnostics"]

    negative_result = _evaluate_negative_control(
        negative_control_rows,
        negative_control=(
            negative_control_spec if negative_control_spec is not None else negative_control
        ),
        estimator_adapter=negative_control_estimator_adapter,
        primary_outer_splits=negative_control_primary_outer_splits,
        primary_propensity_predictions=negative_control_primary_propensity_predictions,
        primary_artifacts=negative_control_primary_artifacts,
        analysis_run_id=core_kwargs.get("analysis_run_id"),
        bundle_manifest_hash=core_kwargs.get("bundle_manifest_hash"),
        evidence_refs=core_kwargs.get("evidence_refs", ()),
        input_refs=core_kwargs.get("input_refs", ()),
        upstream_trigger=upstream_trigger,
    )
    base_results = [*core_results, *refuter_results, negative_result]
    if not any(
        value is not None
        for value in (
            specification_variants,
            cross_form_variants,
            comparison_results,
            benchmark_groups,
            repeat_results,
            intended_role,
        )
    ):
        return base_results

    from .validity import evaluate_complete_validity

    engine_result = core_kwargs.get("engine_result")
    primary_effect = refuter_primary_effect
    if primary_effect is None and isinstance(engine_result, Mapping):
        for key in ("primary_effect", "primary_atte", "primary_atte_slippage", "effect"):
            candidate = engine_result.get(key)
            if isinstance(candidate, Mapping):
                primary_effect = candidate
                break
    if primary_effect is None:
        primary_effect = core_kwargs.get("primary_effect")
    complete = evaluate_complete_validity(
        base_diagnostics=base_results,
        primary_effect=primary_effect,
        specification_variants=specification_variants,
        cross_form_variants=cross_form_variants,
        comparison_results=comparison_results,
        benchmark_groups=benchmark_groups,
        repeat_results=repeat_results,
        engine_result=engine_result if isinstance(engine_result, Mapping) else None,
        intended_role=intended_role or "semi_synthetic_hero",
        scope=str(core_kwargs.get("scope", DIAGNOSTIC_SCOPE)),
        analysis_run_id=core_kwargs.get("analysis_run_id"),
        bundle_manifest_hash=core_kwargs.get("bundle_manifest_hash"),
        evidence_refs=core_kwargs.get("evidence_refs", ()),
        input_refs=core_kwargs.get("input_refs", ()),
    )
    return complete["diagnostics"]


def evaluate_specification_stability(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_specification_stability as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_cross_form_direction(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_cross_form_direction as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_cross_form_stability(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_cross_form_stability as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_comparison_triangulation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_comparison_triangulation as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_robustness_grade(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_robustness_grade as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_hidden_confounding_benchmark(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_hidden_confounding_benchmark as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_hidden_confounding(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_hidden_confounding as _evaluate

    return _evaluate(*args, **kwargs)


def evaluate_repeat_stability(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_repeat_stability as _evaluate

    return _evaluate(*args, **kwargs)


def derive_evidence_verdict(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    from .validity import derive_evidence_verdict as _derive

    return _derive(*args, **kwargs)


def evaluate_evidence_verdict(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    from .validity import evaluate_evidence_verdict as _evaluate

    return _evaluate(*args, **kwargs)


def render_evidence_verdict(*args: Any, **kwargs: Any) -> dict[str, str]:
    from .validity import render_evidence_verdict as _render

    return _render(*args, **kwargs)


def evaluate_complete_validity(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import evaluate_complete_validity as _evaluate

    return _evaluate(*args, **kwargs)


def publish_validity_results(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .validity import publish_validity_results as _publish

    return _publish(*args, **kwargs)
