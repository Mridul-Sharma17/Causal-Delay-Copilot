from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import math
from typing import Any

from .canonical import sha256
from .diagnostics import (
    DIAGNOSTIC_POLICY_ID,
    DIAGNOSTIC_POLICY_VERSION,
    DIAGNOSTIC_SCOPE,
    DiagnosticIntegrityError,
    _make_result,
)


EVIDENCE_VERDICT_SCHEMA_VERSION = "evidence-verdict.v2"
ROBUSTNESS_GRADE_SCHEMA_VERSION = "robustness-grade.v1"
VALIDITY_TRIGGER_REGISTRY_ID = "validity-trigger-registry"
VALIDITY_TRIGGER_REGISTRY_VERSION = "1"
VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID = "validity-next-step-templates"
VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_VERSION = "1"
VALIDITY_LANGUAGE_POLICY_ID = "causal-validity-language-policy"
VALIDITY_LANGUAGE_POLICY_VERSION = "1"

SPECIFICATION_STABILITY_DIAGNOSTIC_ID = "specification_stability"
CROSS_FORM_DIRECTION_DIAGNOSTIC_ID = "cross_form_direction"
COMPARISON_TRIANGULATION_DIAGNOSTIC_ID = "comparison_triangulation"
HIDDEN_CONFOUNDING_DIAGNOSTIC_ID = "hidden_confounding_benchmark"
REPEAT_STABILITY_DIAGNOSTIC_ID = "repeat_stability"
VALIDITY_DIAGNOSTIC_IDS = (
    SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
    CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
    COMPARISON_TRIANGULATION_DIAGNOSTIC_ID,
    HIDDEN_CONFOUNDING_DIAGNOSTIC_ID,
    REPEAT_STABILITY_DIAGNOSTIC_ID,
)

VERDICT_CODES = frozenset(
    {
        "SUPPORTED_UNDER_ASSUMPTIONS",
        "TENTATIVE",
        "ASSOCIATION_ONLY",
        "INSUFFICIENT",
    }
)
EFFECT_DISPLAYS = frozenset(
    {"NONE", "INCONCLUSIVE_ESTIMATE", "ADJUSTED_ASSOCIATION", "CAUSAL_ESTIMATE"}
)
ROBUSTNESS_GRADES = frozenset({"STRONG", "MODERATE", "WEAK", "UNAVAILABLE"})
CORE_ROLES = frozenset(
    {"semi_synthetic_hero", "out_of_domain_validation", "rejection_vignette"}
)
_SPECIFICATION_VARIANTS = (
    "sensitivity_stricter_atte_slippage",
    "sensitivity_short_history_atte_slippage",
    "sensitivity_long_history_atte_slippage",
)
_CROSS_FORM_VARIANTS = (
    "sensitivity_late_risk_atte",
    "sensitivity_continuous_load_slope",
)
_COMPARISONS = ("covariate_ols", "normalized_ipw_atte", "supplier_fe_ols")


# Numeric ordering is the precedence contract. A trigger is never ordered by
# discovery or by the order in which independent computations complete.
TRIGGER_PRIORITIES: dict[str, int] = {
    "SOURCE_SEMANTICS_INELIGIBLE": 100,
    "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT": 110,
    "CORE_TEMPORAL_COVERAGE_INSUFFICIENT": 120,
    "CANCELLATION_COMPETING_EVENT_PRESENT": 130,
    "OUTCOME_COVERAGE_INSUFFICIENT": 140,
    "COVARIATE_COVERAGE_INSUFFICIENT": 150,
    "COHORT_SUPPORT_INSUFFICIENT": 160,
    "OUTCOME_DEGENERATE": 170,
    "OVERLAP_COHORT_INSUFFICIENT": 180,
    "PROACTIVE_SUBJECT_INPUT_UNUSABLE": 190,
    "COMMITMENT_CUTOFF_UNUSABLE": 191,
    "TARGET_MILESTONE_UNSUPPORTED": 192,
    "LOAD_SNAPSHOT_UNRESOLVABLE": 193,
    "SUPPLIER_HISTORY_INSUFFICIENT": 194,
    "FROZEN_PROMISE_UNAVAILABLE": 195,
    "FROZEN_PROMISE_CONFLICT": 196,
    "FROZEN_PROMISE_TEMPORALLY_INVALID": 197,
    "COVARIATE_TEMPORAL_LEAKAGE": 198,
    "REQUIRED_COVARIATE_UNUSABLE": 199,
    "SUBJECT_OVERLAP_INSUFFICIENT": 200,
    "SUBJECT_PROPENSITY_UNAVAILABLE": 201,
    "SUBJECT_DISTRIBUTION_UNSUPPORTED": 210,
    "PRIMARY_INTERVAL_INCLUDES_NULL": 220,
    "PRIMARY_EFFECT_OPPOSITE_DIRECTION": 230,
    "COVARIATE_BALANCE_FAILED": 300,
    "NEGATIVE_CONTROL_UNSUPPORTED": 310,
    "NEGATIVE_CONTROL_FAILED": 320,
    "PLACEBO_REFUTER_UNSUPPORTED": 330,
    "PLACEBO_REFUTER_FAILED": 340,
    "DUMMY_OUTCOME_REFUTER_UNSUPPORTED": 350,
    "DUMMY_OUTCOME_REFUTER_FAILED": 360,
    "RANDOM_COMMON_CAUSE_REFUTER_UNSUPPORTED": 370,
    "RANDOM_COMMON_CAUSE_REFUTER_FAILED": 380,
    "DATA_SUBSET_REFUTER_UNSUPPORTED": 390,
    "DATA_SUBSET_REFUTER_FAILED": 400,
    "SPECIFICATION_DIRECTION_REVERSED": 410,
    "CROSS_FORM_DIRECTION_REVERSED": 420,
    "REPEAT_DIRECTION_UNSTABLE": 430,
    "ROBUSTNESS_WEAK": 440,
    "ROBUSTNESS_UNAVAILABLE": 450,
    "COMPARISON_ONLY_COMPLEX_SUPPORT": 460,
    "SPECIFICATION_MAGNITUDE_DIVERGENT": 500,
    "SPECIFICATION_VARIANT_UNSUPPORTED": 510,
    "CROSS_FORM_INTERVAL_INCLUDES_NULL": 520,
    "BINARY_LATE_SENSITIVITY_UNSUPPORTED": 530,
    "REPEAT_MAGNITUDE_DIVERGENT": 540,
    "ROBUSTNESS_MODERATE": 550,
    "COMPARISON_DIRECTION_MIXED": 560,
    "EVIDENCE_POLICY_PASSED": 10_000,
}


_NEXT_STEPS: dict[str, str] = {
    "SOURCE_SEMANTICS_INELIGIBLE": "Review and approve the source-to-estimand mapping before any new run; do not infer semantics from field names.",
    "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT": "Repair verifiable load-snapshot coverage for the reported overall and supplier deficits, then create a new Dataset Version.",
    "CORE_TEMPORAL_COVERAGE_INSUFFICIENT": "Repair commitment and frozen-promise chronology for the reported deficits; later-known promises cannot fill the gap.",
    "CANCELLATION_COMPETING_EVENT_PRESENT": "Specify and review a competing-event estimand; the current continuous-slippage estimand must remain abstained.",
    "OUTCOME_COVERAGE_INSUFFICIENT": "Add verified supplier-controlled actual milestones for the exact reported coverage deficits, then create a new Dataset Version.",
    "COVARIATE_COVERAGE_INSUFFICIENT": "Improve the pre-treatment covariate records that miss their frozen coverage rules; do not remove a confounder after seeing results.",
    "COHORT_SUPPORT_INSUFFICIENT": "Add the exact reported eligible-line, arm, supplier, or mixed-supplier deficit; do not loosen the support threshold.",
    "OUTCOME_DEGENERATE": "Use a newly pre-registered eligible observation window with genuine outcome variation; never add jitter or outcome-selected exclusions.",
    "OVERLAP_COHORT_INSUFFICIENT": "Collect comparable exposed and unexposed orders for the reported deficient support; do not move the propensity threshold or retune for the result.",
    "PROACTIVE_SUBJECT_INPUT_UNUSABLE": "Complete or verify the subject's pre-cutoff supplier, promise, and covariate inputs before applying population evidence.",
    "COMMITMENT_CUTOFF_UNUSABLE": "Repair and verify the subject's decision-time cutoff and source chronology; later-known values cannot backfill the cutoff.",
    "TARGET_MILESTONE_UNSUPPORTED": "Select a reviewed supplier-controlled milestone supported by source semantics; do not infer eligibility from a field name.",
    "LOAD_SNAPSHOT_UNRESOLVABLE": "Resolve every material open-line membership comparison using information known by the cutoff; do not guess unresolved membership.",
    "SUPPLIER_HISTORY_INSUFFICIENT": "Add the exact reported deficit of valid prior supplier snapshots; do not lower the frozen history threshold.",
    "FROZEN_PROMISE_UNAVAILABLE": "Establish a source-verified target promise known by commitment; a later-known promise cannot replace it.",
    "FROZEN_PROMISE_CONFLICT": "Reconcile the promise provenance chain and publish a new Dataset Version; do not choose the favorable promise.",
    "FROZEN_PROMISE_TEMPORALLY_INVALID": "Repair the promise and cutoff chronology so the frozen baseline is safely comparable at decision time.",
    "COVARIATE_TEMPORAL_LEAKAGE": "Pre-register a strictly pre-treatment covariate derivation and execute a new run; do not use later-known values.",
    "REQUIRED_COVARIATE_UNUSABLE": "Repair the required pre-treatment covariate or its declared missingness handling; do not drop it after seeing results.",
    "SUBJECT_OVERLAP_INSUFFICIENT": "Do not apply the population effect to this order; collect comparable historical cases or use the non-causal risk workflow.",
    "SUBJECT_PROPENSITY_UNAVAILABLE": "Supply the frozen subject propensity support before applying population evidence; do not infer support from the risk score.",
    "SUBJECT_DISTRIBUTION_UNSUPPORTED": "Do not apply the population effect to this order; add comparable two-arm history for the reported unsupported profile.",
    "PRIMARY_INTERVAL_INCLUDES_NULL": "Treat congestion as an unconfirmed delay driver; gather additional eligible evidence or investigate another pre-specified driver.",
    "PRIMARY_EFFECT_OPPOSITE_DIRECTION": "Do not recommend a congestion-targeted action; review the causal question and investigate an alternative driver or protective mechanism.",
    "COVARIATE_BALANCE_FAILED": "Pre-register a revised graph, adjustment set, or propensity specification using separate evidence, then execute a new run; never repair this run after seeing balance.",
    "NEGATIVE_CONTROL_UNSUPPORTED": "Add a provenance-verified pre-exposure negative-control outcome or narrow the causal claim.",
    "NEGATIVE_CONTROL_FAILED": "Review residual confounding, temporal semantics, and the causal graph before making a causal claim.",
    "PLACEBO_REFUTER_UNSUPPORTED": "Add the reported grouped support or narrow the claim; do not substitute a proxy estimator.",
    "PLACEBO_REFUTER_FAILED": "Investigate exposure construction, estimator calibration, and residual structure before a new policy-version run.",
    "DUMMY_OUTCOME_REFUTER_UNSUPPORTED": "Add the reported scientific support or narrow the claim; do not substitute a proxy estimator.",
    "DUMMY_OUTCOME_REFUTER_FAILED": "Investigate estimator calibration and false-effect behavior before a new policy-version run.",
    "RANDOM_COMMON_CAUSE_REFUTER_UNSUPPORTED": "Add the reported scientific support or narrow the claim; do not substitute a proxy estimator.",
    "RANDOM_COMMON_CAUSE_REFUTER_FAILED": "Review estimator instability and adjustment behavior before a new policy-version run.",
    "DATA_SUBSET_REFUTER_UNSUPPORTED": "Add sufficient grouped support; do not fall back to unclustered row sampling.",
    "DATA_SUBSET_REFUTER_FAILED": "Review supplier concentration and subset instability; add eligible supplier support before rerunning.",
    "SPECIFICATION_DIRECTION_REVERSED": "Revisit and domain-review the exposure threshold and history definition; do not select the favorable specification.",
    "CROSS_FORM_DIRECTION_REVERSED": "Review whether the alternate exposure or outcome represents the same causal story before retaining the driver claim.",
    "REPEAT_DIRECTION_UNSTABLE": "Inspect grouped-fold sensitivity and add support if needed; do not select or retry seeds for a favorable sign.",
    "ROBUSTNESS_WEAK": "Measure the plausible omitted-confounder proxies represented by the adverse benchmarks or revise the graph before a causal claim.",
    "ROBUSTNESS_UNAVAILABLE": "Register and collect reviewed benchmark covariates before assigning hidden-confounding robustness.",
    "COMPARISON_ONLY_COMPLEX_SUPPORT": "Review model dependence, adjustment choices, and estimand alignment before relying on the primary DML result.",
    "SPECIFICATION_MAGNITUDE_DIVERGENT": "Investigate threshold and history sensitivity before using the magnitude for decision support.",
    "SPECIFICATION_VARIANT_UNSUPPORTED": "Add the exact missing coverage or support for that pre-registered variant before strengthening the claim.",
    "CROSS_FORM_INTERVAL_INCLUDES_NULL": "Add support for the alternate exposure or outcome form before strengthening the claim.",
    "BINARY_LATE_SENSITIVITY_UNSUPPORTED": "Add the exact late or non-late deficit before relying on outcome-form stability.",
    "REPEAT_MAGNITUDE_DIVERGENT": "Review grouped-fold instability and add supplier support; do not seed-shop or average away the disagreement.",
    "ROBUSTNESS_MODERATE": "Measure or control the strongest credible observed-confounder analogue before strengthening the claim.",
    "COMPARISON_DIRECTION_MIXED": "Review model dependence and estimand differences; keep the claim tentative until the disagreement is explained.",
}


class ValidityIntegrityError(ValueError):
    """A validity input or immutable validity record is not contract-safe."""


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, Mapping) and value.get("state") == "present":
        return _number(value.get("value"))
    return None


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"state": "positive_infinity" if value > 0 else "negative_infinity"}
    return value


def _plain_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    plain = _plain(value)
    if not isinstance(plain, Mapping):
        raise ValidityIntegrityError("validity record contains a non-object value")
    return {str(key): item for key, item in plain.items()}


def _effect_values(value: object, *, interval: bool = False) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        number = _number(value)
        if number is None:
            return None
        return {"estimate": number}
    candidate: Mapping[str, Any] = value
    nested = candidate.get("effect", candidate.get("result"))
    if isinstance(nested, Mapping) and "estimate" not in candidate:
        candidate = nested
    estimate = _number(candidate.get("estimate", candidate.get("effect")))
    standard_error = _number(candidate.get("standard_error", candidate.get("se")))
    lower = _number(candidate.get("ci_lower", candidate.get("interval_lower")))
    upper = _number(candidate.get("ci_upper", candidate.get("interval_upper")))
    interval_value = candidate.get("confidence_interval", candidate.get("interval"))
    if isinstance(interval_value, Mapping):
        lower = _number(interval_value.get("lower", interval_value.get("ci_lower")))
        upper = _number(interval_value.get("upper", interval_value.get("ci_upper")))
    if estimate is None:
        return None
    if standard_error is not None and standard_error <= 0:
        return None
    if interval and (
        lower is None
        or upper is None
        or lower > upper
        or _number(candidate.get("ci_level", 0.95)) != 0.95
    ):
        return None
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "ci_lower": lower,
        "ci_upper": upper,
        "ci_level": _number(candidate.get("ci_level", 0.95)) or 0.95,
        "unit": candidate.get("unit", "days"),
        "duration_basis": candidate.get(
            "duration_basis", candidate.get("canonical_slippage_duration_basis")
        ),
    }


def _status(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    candidate = value.get("status", value.get("state"))
    return str(candidate).lower() if isinstance(candidate, str) else None


def _identity(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "analysis_run_id": kwargs.get("analysis_run_id"),
        "bundle_manifest_hash": kwargs.get("bundle_manifest_hash"),
        "evidence_refs": kwargs.get("evidence_refs", ()),
        "input_refs": kwargs.get("input_refs", ()),
    }


def _diagnostic(
    diagnostic_id: str,
    *,
    rule_id: str,
    status: str,
    observed: Mapping[str, Any] | None,
    threshold: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    verdict_effect: str,
    trigger_codes: Sequence[str],
    reason_code: str,
    reason: str,
    upstream_trigger: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return _make_result(
            diagnostic_id,
            rule_id=rule_id,
            rule_version="1",
            status=status,
            scope=kwargs.pop("scope", DIAGNOSTIC_SCOPE),
            observed=None if observed is None else _plain_mapping(observed),
            threshold=_plain_mapping(threshold),
            result=None if result is None else _plain_mapping(result),
            verdict_effect=verdict_effect,
            trigger_codes=trigger_codes,
            reason_code=reason_code,
            reason=reason,
            upstream_trigger=upstream_trigger,
            policy_id=kwargs.pop("policy_id", DIAGNOSTIC_POLICY_ID),
            policy_version=kwargs.pop("policy_version", DIAGNOSTIC_POLICY_VERSION),
            **_identity(kwargs),
        )
    except (DiagnosticIntegrityError, TypeError, ValueError) as error:
        raise ValidityIntegrityError("validity diagnostic could not be sealed") from error


def _safe_ratio(delta: float, denominator: float) -> tuple[float, object]:
    if denominator == 0.0:
        if delta == 0.0:
            return 0.0, 0.0
        return math.inf, {"state": "positive_infinity"}
    value = abs(delta) / denominator
    return value, value


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidityIntegrityError(f"{label} is unsupported")

    def contains_legacy_reference(candidate: object) -> bool:
        if isinstance(candidate, Mapping):
            return "analysis_authorization_ref" in candidate or any(
                contains_legacy_reference(item) for item in candidate.values()
            )
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
            return any(contains_legacy_reference(item) for item in candidate)
        return False

    if contains_legacy_reference(value):
        raise ValidityIntegrityError("analysis_authorization_ref is not part of the validity contract")
    return value


def evaluate_specification_stability(
    primary_effect: Mapping[str, Any] | None,
    variants: Mapping[str, Any] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate the three pre-registered same-estimand variants."""

    threshold = {
        "compatibility_z_max": 1.96,
        "positive_estimate_required": True,
        "zero_is_reversal": True,
        "variant_ids": list(_SPECIFICATION_VARIANTS),
    }
    if primary_effect is None or variants is None:
        return _diagnostic(
            SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
            rule_id="same-estimand-specification-stability",
            status="UNAVAILABLE",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="SPECIFICATION_STABILITY_UNAVAILABLE",
            reason="The complete pre-registered same-estimand sensitivity set is unavailable.",
            **kwargs,
        )
    primary = _effect_values(_require_mapping(primary_effect, "primary effect"))
    if primary is None or primary["standard_error"] is None:
        return _diagnostic(
            SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
            rule_id="same-estimand-specification-stability",
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="SPECIFICATION_PRIMARY_INVALID",
            reason="The primary effect lacks a finite estimate and strictly positive standard error.",
            **kwargs,
        )
    if not isinstance(variants, Mapping):
        raise ValidityIntegrityError("specification variants are unsupported")
    observations: list[dict[str, Any]] = []
    unsupported: list[str] = []
    reversals: list[str] = []
    divergent: list[str] = []
    for variant_id in _SPECIFICATION_VARIANTS:
        if variant_id not in variants:
            return _diagnostic(
                SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
                rule_id="same-estimand-specification-stability",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="SPECIFICATION_VARIANT_MISSING",
                reason="A required same-estimand variant is missing from the verified engine result.",
                **kwargs,
            )
        raw = _require_mapping(variants[variant_id], f"{variant_id} result")
        raw_status = _status(raw)
        if raw_status in {"unsupported", "scientifically_unavailable"}:
            unsupported.append(variant_id)
            observations.append({"variant_id": variant_id, "status": "UNSUPPORTED"})
            continue
        if raw_status in {"failed", "execution_failed", "integrity_failed"}:
            return _diagnostic(
                SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
                rule_id="same-estimand-specification-stability",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="SPECIFICATION_VARIANT_FAILED",
                reason="A required same-estimand variant failed execution.",
                **kwargs,
            )
        value = _effect_values(raw)
        if value is None or value["standard_error"] is None:
            return _diagnostic(
                SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
                rule_id="same-estimand-specification-stability",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="SPECIFICATION_VARIANT_INVALID",
                reason="A same-estimand variant lacks a finite estimate and strictly positive standard error.",
                **kwargs,
            )
        z, encoded_z = _safe_ratio(
            value["estimate"] - primary["estimate"],
            math.sqrt(value["standard_error"] ** 2 + primary["standard_error"] ** 2),
        )
        if value["estimate"] <= 0:
            reversals.append(variant_id)
        if z > 1.96:
            divergent.append(variant_id)
        observations.append(
            {
                "variant_id": variant_id,
                "status": "ESTIMATED",
                "estimate": value["estimate"],
                "standard_error": value["standard_error"],
                "compatibility_z": encoded_z,
            }
        )
    trigger_codes: list[str] = []
    if reversals:
        trigger_codes.append("SPECIFICATION_DIRECTION_REVERSED")
    elif divergent:
        trigger_codes.append("SPECIFICATION_MAGNITUDE_DIVERGENT")
    if unsupported:
        trigger_codes.append("SPECIFICATION_VARIANT_UNSUPPORTED")
    if reversals:
        status, effect, reason_code, reason = (
            "FAIL",
            "VETO",
            "SPECIFICATION_DIRECTION_REVERSED",
            "At least one same-estimand specification reverses the proposed positive direction.",
        )
    elif divergent:
        status, effect, reason_code, reason = (
            "FAIL",
            "FRAGILITY",
            "SPECIFICATION_MAGNITUDE_DIVERGENT",
            "All estimated variants remain positive, but at least one differs beyond compatibility z 1.96.",
        )
    elif unsupported:
        status, effect, reason_code, reason = (
            "UNSUPPORTED",
            "FRAGILITY",
            "SPECIFICATION_VARIANT_UNSUPPORTED",
            "A permitted same-estimand variant lacks scientific support, so stability evidence is incomplete.",
        )
    else:
        status, effect, reason_code, reason = (
            "PASS",
            "NONE",
            "SPECIFICATION_STABILITY_PASSED",
            "All three same-estimand variants are positive and compatible with the primary estimate.",
        )
    return _diagnostic(
        SPECIFICATION_STABILITY_DIAGNOSTIC_ID,
        rule_id="same-estimand-specification-stability",
        status=status,
        scope=scope,
        observed={"primary_estimate": primary["estimate"], "variants": observations},
        threshold=threshold,
        result={"estimated_variant_count": len(observations) - len(unsupported)},
        verdict_effect=effect,
        trigger_codes=trigger_codes,
        reason_code=reason_code,
        reason=reason,
        **kwargs,
    )


def evaluate_cross_form_direction(
    variants: Mapping[str, Any] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate direction-only binary-late and continuous-load sensitivities."""

    threshold = {
        "ci_level": 0.95,
        "positive_interval_required": True,
        "zero_is_reversal": True,
        "variant_ids": list(_CROSS_FORM_VARIANTS),
    }
    if variants is None:
        return _diagnostic(
            CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
            rule_id="cross-form-directional-stability",
            status="UNAVAILABLE",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="CROSS_FORM_STABILITY_UNAVAILABLE",
            reason="The registered cross-form sensitivities are unavailable.",
            **kwargs,
        )
    variants = _require_mapping(variants, "cross-form variants")
    trigger_codes: list[str] = []
    observations: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []
    for variant_id in _CROSS_FORM_VARIANTS:
        if variant_id not in variants:
            return _diagnostic(
                CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
                rule_id="cross-form-directional-stability",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="CROSS_FORM_VARIANT_MISSING",
                reason="A required cross-form sensitivity is missing from the verified engine result.",
                **kwargs,
            )
        raw = _require_mapping(variants[variant_id], f"{variant_id} result")
        raw_status = _status(raw)
        if raw_status in {"unsupported", "scientifically_unavailable"}:
            if variant_id != "sensitivity_late_risk_atte":
                return _diagnostic(
                    CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
                    rule_id="cross-form-directional-stability",
                    status="FAILED",
                    scope=scope,
                    observed=None,
                    threshold=threshold,
                    result=None,
                    verdict_effect="NONE",
                    trigger_codes=[],
                    reason_code="CONTINUOUS_LOAD_SENSITIVITY_INVALID",
                    reason="The continuous-load sensitivity has no permitted unsupported state.",
                    **kwargs,
                )
            trigger_codes.append("BINARY_LATE_SENSITIVITY_UNSUPPORTED")
            observations.append({"variant_id": variant_id, "status": "UNSUPPORTED"})
            continue
        if raw_status in {"failed", "execution_failed", "integrity_failed"}:
            return _diagnostic(
                CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
                rule_id="cross-form-directional-stability",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="CROSS_FORM_VARIANT_FAILED",
                reason="A required cross-form sensitivity failed execution.",
                **kwargs,
            )
        value = _effect_values(raw, interval=True)
        if value is None:
            return _diagnostic(
                CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
                rule_id="cross-form-directional-stability",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="CROSS_FORM_VARIANT_INVALID",
                reason="A cross-form sensitivity lacks a finite ordered 95% interval.",
                **kwargs,
            )
        if value["estimate"] <= 0:
            code = "CROSS_FORM_DIRECTION_REVERSED"
            failures.append((variant_id, code))
        elif value["ci_lower"] <= 0:
            code = "CROSS_FORM_INTERVAL_INCLUDES_NULL"
            failures.append((variant_id, code))
        else:
            code = ""
        if code:
            trigger_codes.append(code)
        observations.append(
            {
                "variant_id": variant_id,
                "status": "FAIL" if code else "PASS",
                "estimate": value["estimate"],
                "ci_lower": value["ci_lower"],
                "ci_upper": value["ci_upper"],
            }
        )
    if "CROSS_FORM_DIRECTION_REVERSED" in trigger_codes:
        status, effect, reason_code, reason = (
            "FAIL",
            "VETO",
            "CROSS_FORM_DIRECTION_REVERSED",
            "At least one alternate exposure or outcome form reverses the proposed positive direction.",
        )
    elif "CROSS_FORM_INTERVAL_INCLUDES_NULL" in trigger_codes:
        status, effect, reason_code, reason = (
            "FAIL",
            "FRAGILITY",
            "CROSS_FORM_INTERVAL_INCLUDES_NULL",
            "A positive alternate-form estimate has a two-sided interval that includes zero.",
        )
    elif "BINARY_LATE_SENSITIVITY_UNSUPPORTED" in trigger_codes:
        status, effect, reason_code, reason = (
            "UNSUPPORTED",
            "FRAGILITY",
            "BINARY_LATE_SENSITIVITY_UNSUPPORTED",
            "The permitted binary-late sensitivity is scientifically unsupported.",
        )
    else:
        status, effect, reason_code, reason = (
            "PASS",
            "NONE",
            "CROSS_FORM_DIRECTION_PASSED",
            "Both alternate forms have intervals wholly above zero.",
        )
    return _diagnostic(
        CROSS_FORM_DIRECTION_DIAGNOSTIC_ID,
        rule_id="cross-form-directional-stability",
        status=status,
        scope=scope,
        observed={"variants": observations},
        threshold=threshold,
        result={"failed_variants": [variant_id for variant_id, _ in failures]},
        verdict_effect=effect,
        trigger_codes=trigger_codes,
        reason_code=reason_code,
        reason=reason,
        **kwargs,
    )


def evaluate_comparison_triangulation(
    comparisons: Mapping[str, Any] | None,
    *,
    primary_effect: Mapping[str, Any] | None,
    scope: str = DIAGNOSTIC_SCOPE,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate direction-only triangulation across the three adjusted comparisons."""

    threshold = {"comparison_ids": list(_COMPARISONS), "positive_estimate_required": True}
    if comparisons is None:
        return _diagnostic(
            COMPARISON_TRIANGULATION_DIAGNOSTIC_ID,
            rule_id="comparison-estimator-triangulation",
            status="UNAVAILABLE",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="COMPARISON_TRIANGULATION_UNAVAILABLE",
            reason="The complete registered comparison-estimator set is unavailable.",
            **kwargs,
        )
    comparisons = _require_mapping(comparisons, "comparison results")
    estimates: dict[str, float] = {}
    for comparison_id in _COMPARISONS:
        if comparison_id not in comparisons:
            return _diagnostic(
                COMPARISON_TRIANGULATION_DIAGNOSTIC_ID,
                rule_id="comparison-estimator-triangulation",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="COMPARISON_RESULT_MISSING",
                reason="A required adjusted comparison result is missing.",
                **kwargs,
            )
        value = _effect_values(_require_mapping(comparisons[comparison_id], f"{comparison_id} result"))
        if value is None:
            return _diagnostic(
                COMPARISON_TRIANGULATION_DIAGNOSTIC_ID,
                rule_id="comparison-estimator-triangulation",
                status="FAILED",
                scope=scope,
                observed=None,
                threshold=threshold,
                result=None,
                verdict_effect="NONE",
                trigger_codes=[],
                reason_code="COMPARISON_RESULT_INVALID",
                reason="A required adjusted comparison result is invalid or unidentified.",
                **kwargs,
            )
        estimates[comparison_id] = value["estimate"]
    non_positive = [key for key, value in estimates.items() if value <= 0]
    primary = _effect_values(primary_effect) if primary_effect is not None else None
    all_non_positive = len(non_positive) == len(_COMPARISONS) and primary is not None and primary["estimate"] > 0
    if all_non_positive:
        status, effect, reason_code, reason, trigger = (
            "FAIL",
            "VETO",
            "COMPARISON_ONLY_COMPLEX_SUPPORT",
            "All adjusted comparison estimates are non-positive while the primary estimate is positive.",
            "COMPARISON_ONLY_COMPLEX_SUPPORT",
        )
    elif non_positive:
        status, effect, reason_code, reason, trigger = (
            "FAIL",
            "FRAGILITY",
            "COMPARISON_DIRECTION_MIXED",
            "One or two adjusted comparison estimates are non-positive.",
            "COMPARISON_DIRECTION_MIXED",
        )
    else:
        status, effect, reason_code, reason, trigger = (
            "PASS",
            "NONE",
            "COMPARISON_TRIANGULATION_PASSED",
            "All three adjusted comparison estimates are positive.",
            None,
        )
    return _diagnostic(
        COMPARISON_TRIANGULATION_DIAGNOSTIC_ID,
        rule_id="comparison-estimator-triangulation",
        status=status,
        scope=scope,
        observed={"estimates": estimates},
        threshold=threshold,
        result={"non_positive_comparisons": non_positive},
        verdict_effect=effect,
        trigger_codes=[] if trigger is None else [trigger],
        reason_code=reason_code,
        reason=reason,
        **kwargs,
    )


def _benchmark_lower(value: Mapping[str, Any]) -> float | None:
    for key in ("sensitivity_adjusted_ci_lower", "adjusted_ci_lower", "adjusted_lower", "ci_lower"):
        candidate = _number(value.get(key))
        if candidate is not None:
            return candidate
    nested = value.get("sensitivity_analysis")
    if isinstance(nested, Mapping):
        return _benchmark_lower(nested)
    return None


def _benchmark_ref(value: Mapping[str, Any], index: int) -> str:
    for key in ("group_ref", "covariate_group", "group_id", "id"):
        if isinstance(value.get(key), str) and value[key]:
            return value[key]
    return f"benchmark-group-{index + 1}"


def evaluate_robustness_grade(
    primary_effect: Mapping[str, Any] | None,
    benchmark_groups: Sequence[Mapping[str, Any]] | None,
    *,
    canonical_group_order: Sequence[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Classify reviewed hidden-confounding benchmarks without merging diagnostics."""

    if primary_effect is None:
        primary = None
    else:
        primary_mapping = _require_mapping(primary_effect, "primary effect")
        primary = (
            None
            if _status(primary_mapping)
            in {
                "abstained",
                "not_estimable",
                "scientifically_unavailable",
                "failed",
                "execution_failed",
                "integrity_failed",
            }
            else _effect_values(primary_mapping)
        )
        if primary is None:
            if _status(primary_mapping) not in {
                "abstained",
                "not_estimable",
                "scientifically_unavailable",
                "failed",
                "execution_failed",
                "integrity_failed",
            }:
                raise ValidityIntegrityError("primary effect is invalid")
    valid_groups: list[dict[str, Any]] = []
    if benchmark_groups is not None:
        if not isinstance(benchmark_groups, Sequence) or isinstance(benchmark_groups, (str, bytes)):
            raise ValidityIntegrityError("benchmark groups are unsupported")
        order = {str(item): index for index, item in enumerate(canonical_group_order or ())}
        for index, raw in enumerate(benchmark_groups):
            group = _require_mapping(raw, "benchmark group")
            eligible = group.get(
                "benchmark_eligible",
                group.get("sensitivity_benchmark_eligible", group.get("eligible", True)),
            )
            if not isinstance(eligible, bool):
                raise ValidityIntegrityError("benchmark eligibility marker is malformed")
            if not eligible:
                continue
            if _status(group) in {"unsupported", "unavailable", "failed", "not_estimable"}:
                continue
            lower = _benchmark_lower(group)
            if lower is None:
                continue
            reference = _benchmark_ref(group, index)
            declared_order = _number(group.get("canonical_order", group.get("order")))
            valid_groups.append(
                {
                    "group_ref": reference,
                    "adjusted_ci_lower": lower,
                    "canonical_order": int(declared_order)
                    if declared_order is not None
                    else order.get(reference, len(order) + index),
                }
            )
    valid_groups.sort(key=lambda item: (item["adjusted_ci_lower"], item["canonical_order"], item["group_ref"]))
    if primary is None or not valid_groups:
        grade = "UNAVAILABLE"
        strongest = None
        median = None
        strongest_bound = None
        median_bound = None
    else:
        strongest = valid_groups[0]
        median = valid_groups[(len(valid_groups) - 1) // 2]
        strongest_bound = strongest["adjusted_ci_lower"]
        median_bound = median["adjusted_ci_lower"]
        if strongest_bound > 0:
            grade = "STRONG"
        elif median_bound > 0:
            grade = "MODERATE"
        else:
            grade = "WEAK"
    record: dict[str, Any] = {
        "schema_version": ROBUSTNESS_GRADE_SCHEMA_VERSION,
        "grade": grade,
        "analysis_run_id": kwargs.get("analysis_run_id"),
        "bundle_manifest_hash": kwargs.get("bundle_manifest_hash"),
        "benchmark_group_refs": [item["group_ref"] for item in valid_groups],
        "benchmark_groups": [
            {"group_ref": item["group_ref"], "adjusted_ci_lower": item["adjusted_ci_lower"]}
            for item in valid_groups
        ],
        "strongest_group_ref": None if strongest is None else strongest["group_ref"],
        "median_group_ref": None if median is None else median["group_ref"],
        "strongest_adjusted_ci_lower": strongest_bound,
        "median_adjusted_ci_lower": median_bound,
        "sensitivity_method": "DoubleML.sensitivity_benchmark_and_sensitivity_analysis",
        "sensitivity_method_version": "0.11.3",
        "configuration_ref": "sensitivity-benchmark:doubleml-primary-atte",
        "evidence_refs": list(dict.fromkeys(str(item) for item in kwargs.get("evidence_refs", ()) if item)),
        "input_refs": list(dict.fromkeys(str(item) for item in kwargs.get("input_refs", ()) if item)),
    }
    record["content_hash"] = sha256(_plain(record))
    return record


def evaluate_hidden_confounding_benchmark(
    primary_effect: Mapping[str, Any] | None,
    benchmark_groups: Sequence[Mapping[str, Any]] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    **kwargs: Any,
) -> dict[str, Any]:
    grade = evaluate_robustness_grade(primary_effect, benchmark_groups, **kwargs)
    if grade["grade"] == "STRONG":
        status, effect, trigger, reason = "PASS", "NONE", None, "The strongest reviewed benchmark retains a positive adjusted lower bound."
    elif grade["grade"] == "MODERATE":
        status, effect, trigger, reason = "FAIL", "FRAGILITY", "ROBUSTNESS_MODERATE", "The median benchmark remains positive, but the strongest benchmark crosses zero."
    elif grade["grade"] == "WEAK":
        status, effect, trigger, reason = "FAIL", "VETO", "ROBUSTNESS_WEAK", "The median adverse benchmark crosses zero, so hidden-confounding robustness is weak."
    else:
        status, effect, trigger, reason = "UNAVAILABLE", "VETO", "ROBUSTNESS_UNAVAILABLE", "No eligible valid hidden-confounding benchmark is available for the valid estimate."
    return _diagnostic(
        HIDDEN_CONFOUNDING_DIAGNOSTIC_ID,
        rule_id="hidden-confounding-sensitivity-benchmark",
        status=status,
        scope=scope,
        observed={"grade": grade["grade"], "strongest_adjusted_ci_lower": grade["strongest_adjusted_ci_lower"], "median_adjusted_ci_lower": grade["median_adjusted_ci_lower"]},
        threshold={"strongest_lower_bound_positive_for_strong": True, "median_index": "floor((n - 1) / 2)"},
        result={"robustness_grade": grade},
        verdict_effect=effect,
        trigger_codes=[] if trigger is None else [trigger],
        reason_code="ROBUSTNESS_GRADE_" + grade["grade"],
        reason=reason,
        **kwargs,
    )


def evaluate_repeat_stability(
    repeats: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    *,
    scope: str = DIAGNOSTIC_SCOPE,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate the two engine-provided primary repeat results."""

    threshold = {"compatibility_z_max": 1.96, "positive_estimate_required": True, "zero_is_reversal": True}
    if repeats is None:
        return _diagnostic(
            REPEAT_STABILITY_DIAGNOSTIC_ID,
            rule_id="primary-repeat-stability",
            status="UNAVAILABLE",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="REPEAT_STABILITY_UNAVAILABLE",
            reason="The two engine-provided primary repeat results are unavailable.",
            **kwargs,
        )
    values: dict[str, Any] = {}
    if isinstance(repeats, Mapping):
        for key in ("repeat_0", "repeat_1", "repeat_2"):
            if key in repeats:
                values[key] = repeats[key]
        if "repeat_0" not in values and "repeat_1" in repeats and "repeat_2" in repeats:
            values = {"repeat_0": repeats["repeat_1"], "repeat_1": repeats["repeat_2"]}
    elif isinstance(repeats, Sequence) and not isinstance(repeats, (str, bytes)):
        values = {f"repeat_{index}": value for index, value in enumerate(repeats[:2])}
    else:
        raise ValidityIntegrityError("repeat results are unsupported")
    if set(values) != {"repeat_0", "repeat_1"}:
        return _diagnostic(
            REPEAT_STABILITY_DIAGNOSTIC_ID,
            rule_id="primary-repeat-stability",
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="REPEAT_RESULT_MISSING",
            reason="Both primary repeat estimates and standard errors are required.",
            **kwargs,
        )
    first = _effect_values(_require_mapping(values["repeat_0"], "repeat 0"))
    second = _effect_values(_require_mapping(values["repeat_1"], "repeat 1"))
    if first is None or second is None or first["standard_error"] is None or second["standard_error"] is None:
        return _diagnostic(
            REPEAT_STABILITY_DIAGNOSTIC_ID,
            rule_id="primary-repeat-stability",
            status="FAILED",
            scope=scope,
            observed=None,
            threshold=threshold,
            result=None,
            verdict_effect="NONE",
            trigger_codes=[],
            reason_code="REPEAT_RESULT_INVALID",
            reason="A primary repeat lacks a finite estimate and strictly positive standard error.",
            **kwargs,
        )
    z, encoded_z = _safe_ratio(
        first["estimate"] - second["estimate"],
        math.sqrt(first["standard_error"] ** 2 + second["standard_error"] ** 2),
    )
    if first["estimate"] <= 0 or second["estimate"] <= 0:
        status, effect, trigger, reason = "FAIL", "VETO", "REPEAT_DIRECTION_UNSTABLE", "At least one primary repeat reverses the proposed positive direction."
    elif z > 1.96:
        status, effect, trigger, reason = "FAIL", "FRAGILITY", "REPEAT_MAGNITUDE_DIVERGENT", "Both primary repeats are positive, but their compatibility z exceeds 1.96."
    else:
        status, effect, trigger, reason = "PASS", "NONE", None, "Both primary repeats are positive and compatible."
    return _diagnostic(
        REPEAT_STABILITY_DIAGNOSTIC_ID,
        rule_id="primary-repeat-stability",
        status=status,
        scope=scope,
        observed={
            "repeat_0": {"estimate": first["estimate"], "standard_error": first["standard_error"]},
            "repeat_1": {"estimate": second["estimate"], "standard_error": second["standard_error"]},
            "compatibility_z": encoded_z,
        },
        threshold=threshold,
        result=None,
        verdict_effect=effect,
        trigger_codes=[] if trigger is None else [trigger],
        reason_code="REPEAT_STABILITY_PASSED" if trigger is None else trigger,
        reason=reason,
        **kwargs,
    )


def _trigger_codes(
    diagnostics: Sequence[Mapping[str, Any]],
    *,
    upstream_abstained: bool = False,
) -> list[str]:
    found: set[str] = set()
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Mapping):
            raise ValidityIntegrityError("diagnostic set contains a non-object")
        if "analysis_authorization_ref" in diagnostic:
            raise ValidityIntegrityError("legacy authorization reference is unsupported")
        if (
            diagnostic.get("policy_id", DIAGNOSTIC_POLICY_ID) != DIAGNOSTIC_POLICY_ID
            or diagnostic.get("policy_version", DIAGNOSTIC_POLICY_VERSION) != DIAGNOSTIC_POLICY_VERSION
        ):
            raise ValidityIntegrityError("diagnostic policy binding is unsupported")
        if diagnostic.get("status") == "FAILED":
            raise ValidityIntegrityError("diagnostic execution or integrity failure produces no verdict")
        if diagnostic.get("status") not in {
            "PASS",
            "FAIL",
            "UNSUPPORTED",
            "UNAVAILABLE",
            "NOT_RUN",
        }:
            raise ValidityIntegrityError("diagnostic status is unsupported")
        if diagnostic.get("verdict_effect") not in {
            "NONE",
            "FRAGILITY",
            "VETO",
            "INSUFFICIENT",
        }:
            raise ValidityIntegrityError("diagnostic verdict effect is unsupported")
        if diagnostic.get("verdict_effect") != "NONE" and not diagnostic.get("trigger_codes"):
            raise ValidityIntegrityError("non-neutral diagnostic has no trigger")
        if (
            diagnostic.get("status") == "NOT_RUN"
            or (
                diagnostic.get("status") == "UNAVAILABLE"
                and not diagnostic.get("trigger_codes")
            )
        ) and not upstream_abstained:
            raise ValidityIntegrityError("incomplete post-estimation diagnostics produce no verdict")
        values = diagnostic.get("trigger_codes", [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValidityIntegrityError("diagnostic trigger set is malformed")
        for code in values:
            if code not in TRIGGER_PRIORITIES or code == "EVIDENCE_POLICY_PASSED":
                raise ValidityIntegrityError(f"unknown validity trigger: {code}")
            found.add(code)
    return sorted(found, key=lambda code: (TRIGGER_PRIORITIES[code], code))


def _primary_effect(engine_result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("primary_effect", "primary_atte", "primary_atte_slippage", "effect"):
        candidate = engine_result.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    effects = engine_result.get("effects", engine_result.get("effect_results"))
    if isinstance(effects, Mapping):
        for key in ("primary_atte_slippage", "primary_atte", "primary"):
            candidate = effects.get(key)
            if isinstance(candidate, Mapping):
                return candidate
    return None


def _role_permissions(intended_role: str) -> tuple[bool, bool, str]:
    if intended_role not in CORE_ROLES:
        raise ValidityIntegrityError("intended_role is outside the closed Core role set")
    if intended_role == "semi_synthetic_hero":
        return True, True, "population_and_subject"
    return False, False, "population"


def _effect_projection(effect: Mapping[str, Any]) -> dict[str, Any]:
    values = _effect_values(effect, interval=True)
    if values is None:
        raise ValidityIntegrityError("effect-bearing verdict requires a valid effect and interval")
    basis = values.get("duration_basis")
    if values.get("unit") == "days" and basis not in {"CALENDAR_DAY", "ELAPSED_86400_SECOND_DAY"}:
        raise ValidityIntegrityError("effect-bearing slippage verdict requires a duration basis")
    return {
        "estimate": values["estimate"],
        "standard_error": values["standard_error"],
        "ci_lower": values["ci_lower"],
        "ci_upper": values["ci_upper"],
        "ci_level": values["ci_level"],
        "unit": values.get("unit"),
        "duration_basis": basis,
    }


def _inconclusive_trigger(triggers: Sequence[str]) -> str | None:
    for code in ("PRIMARY_INTERVAL_INCLUDES_NULL", "PRIMARY_EFFECT_OPPOSITE_DIRECTION"):
        if code in triggers:
            return code
    return None


def derive_evidence_verdict(
    engine_result: Mapping[str, Any],
    diagnostics: Sequence[Mapping[str, Any]],
    *,
    intended_role: str,
    scope: str = DIAGNOSTIC_SCOPE,
    robustness_grade: Mapping[str, Any] | None = None,
    canonical_slippage_duration_basis: str | None = None,
    effect_result_ref: str | None = None,
    claim_scope: str | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Derive the immutable Evidence Verdict; presentation is a separate projection."""

    engine = _require_mapping(engine_result, "engine result")
    if scope != "population":
        raise ValidityIntegrityError("population verdict scope is required")
    role_subject_permitted, role_decision_permitted, default_claim_scope = _role_permissions(intended_role)
    status = _status(engine)
    engine_role = engine.get("intended_role")
    if engine_role is not None and engine_role != intended_role:
        raise ValidityIntegrityError("engine role does not match the validity role")
    if claim_scope is not None:
        if claim_scope not in {"population", "population_and_subject"}:
            raise ValidityIntegrityError("claim scope is unsupported")
        if default_claim_scope == "population" and claim_scope != default_claim_scope:
            raise ValidityIntegrityError("claim scope exceeds the role ceiling")
    if status in {"failed", "execution_failed", "integrity_failed"}:
        return None
    if intended_role == "rejection_vignette" and status not in {
        "abstained",
        "not_estimable",
        "scientifically_unavailable",
    }:
        return None
    primary_raw = _primary_effect(engine)
    primary = (
        None
        if status in {"abstained", "not_estimable", "scientifically_unavailable"} or primary_raw is None
        else _effect_projection(primary_raw)
    )
    if status not in {"abstained", "not_estimable", "scientifically_unavailable"} and primary is None:
        return None
    triggers = _trigger_codes(
        diagnostics,
        upstream_abstained=status in {"abstained", "not_estimable", "scientifically_unavailable"},
    )
    if status in {"abstained", "not_estimable", "scientifically_unavailable"} and not triggers:
        triggers = ["COHORT_SUPPORT_INSUFFICIENT"]

    inconclusive = _inconclusive_trigger(triggers)
    if status in {"abstained", "not_estimable", "scientifically_unavailable"}:
        verdict_code = "INSUFFICIENT"
        reason_class = "NOT_ESTIMABLE"
        effect_display = "NONE"
        primary_trigger = triggers[0]
    elif inconclusive is not None:
        verdict_code = "INSUFFICIENT"
        reason_class = "INCONCLUSIVE"
        effect_display = "INCONCLUSIVE_ESTIMATE"
        primary_trigger = triggers[0]
    elif any(
        diagnostic.get("verdict_effect") == "VETO"
        for diagnostic in diagnostics
        if isinstance(diagnostic, Mapping)
    ):
        verdict_code = "ASSOCIATION_ONLY"
        reason_class = None
        effect_display = "ADJUSTED_ASSOCIATION"
        primary_trigger = triggers[0] if triggers else "COVARIATE_BALANCE_FAILED"
    elif any(
        diagnostic.get("verdict_effect") == "FRAGILITY"
        for diagnostic in diagnostics
        if isinstance(diagnostic, Mapping)
    ):
        verdict_code = "TENTATIVE"
        reason_class = None
        effect_display = "NONE"
        primary_trigger = triggers[0] if triggers else "COMPARISON_DIRECTION_MIXED"
    else:
        verdict_code = "SUPPORTED_UNDER_ASSUMPTIONS"
        reason_class = None
        effect_display = "CAUSAL_ESTIMATE"
        primary_trigger = "EVIDENCE_POLICY_PASSED"
        triggers = [primary_trigger]

    if primary_trigger not in TRIGGER_PRIORITIES:
        raise ValidityIntegrityError("primary trigger is not registered")
    triggers = sorted(set(triggers), key=lambda code: (TRIGGER_PRIORITIES[code], code))
    if verdict_code == "SUPPORTED_UNDER_ASSUMPTIONS":
        triggers = ["EVIDENCE_POLICY_PASSED"]
    if primary_trigger != "EVIDENCE_POLICY_PASSED" and primary_trigger not in triggers:
        triggers.insert(0, primary_trigger)
        triggers.sort(key=lambda code: (TRIGGER_PRIORITIES[code], code))
        primary_trigger = triggers[0]

    if effect_display != "NONE":
        if primary is None:
            raise ValidityIntegrityError("effect-bearing verdict has no primary effect")
        expected_basis = canonical_slippage_duration_basis or primary.get("duration_basis")
        if expected_basis not in {"CALENDAR_DAY", "ELAPSED_86400_SECOND_DAY"}:
            raise ValidityIntegrityError("effect-bearing verdict requires a canonical duration basis")
        if primary.get("duration_basis") not in {None, expected_basis}:
            raise ValidityIntegrityError("effect duration basis disagrees with the engine result")
        engine_basis = engine.get(
            "canonical_slippage_duration_basis",
            engine.get("duration_basis"),
        )
        if engine_basis is not None and engine_basis != expected_basis:
            raise ValidityIntegrityError("effect duration basis disagrees with the sealed engine request")
        if primary.get("unit") not in {"days", "days_per_unit_load_percentile"}:
            raise ValidityIntegrityError("effect unit is not a canonical slippage unit")
        reference = effect_result_ref or engine.get("effect_result_ref") or engine.get("effect_ref")
        if not isinstance(reference, str) or not reference:
            raise ValidityIntegrityError("effect-bearing verdict requires an engine effect reference")
        effect_result_ref = reference
        canonical_slippage_duration_basis = expected_basis
    else:
        primary = None
        effect_result_ref = None
        canonical_slippage_duration_basis = None

    decision_support_permitted = role_decision_permitted
    decision_support_evaluation_permitted = (
        verdict_code == "SUPPORTED_UNDER_ASSUMPTIONS" and decision_support_permitted
    )

    grade_record = None
    if robustness_grade is not None:
        grade_record = verify_robustness_grade(
            _require_mapping(robustness_grade, "robustness grade")
        )

    record: dict[str, Any] = {
        "schema_version": EVIDENCE_VERDICT_SCHEMA_VERSION,
        "scope": scope,
        "verdict_code": verdict_code,
        "insufficient_evidence_reason_class": reason_class,
        "intended_role": intended_role,
        "permitted_claim_scope": claim_scope or default_claim_scope,
        "claim_scope": claim_scope or default_claim_scope,
        "subject_application_role_permitted": role_subject_permitted,
        "decision_support_role_permitted": decision_support_permitted,
        "decision_support_evaluation_permitted": decision_support_evaluation_permitted,
        "population_verdict_ref": None,
        "engine_status_ref": engine.get("status", engine.get("engine_result_status")),
        "artifact_integrity_status_ref": engine.get("artifact_integrity_status", "verified"),
        "robustness_grade_ref": None if grade_record is None else grade_record["content_hash"],
        "effect_display": effect_display,
        "effect_result_ref": effect_result_ref,
        "effect_result_hash": None if primary is None else sha256(_plain(primary)),
        "canonical_unit": None if primary is None else primary.get("unit"),
        "canonical_slippage_duration_basis": canonical_slippage_duration_basis,
        "effect": deepcopy(primary) if primary is not None else None,
        "primary_trigger_code": primary_trigger,
        "primary_trigger": primary_trigger,
        "trigger_codes": triggers,
        "next_step_template_id": f"{VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID}:{primary_trigger.lower()}",
        "next_step_template_ids": [
            f"{VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID}:{code.lower()}" for code in triggers
        ],
        "language_policy_id": VALIDITY_LANGUAGE_POLICY_ID,
        "language_policy_version": VALIDITY_LANGUAGE_POLICY_VERSION,
        "verdict_policy_id": DIAGNOSTIC_POLICY_ID,
        "verdict_policy_version": DIAGNOSTIC_POLICY_VERSION,
        "trigger_registry_id": VALIDITY_TRIGGER_REGISTRY_ID,
        "trigger_registry_version": VALIDITY_TRIGGER_REGISTRY_VERSION,
        "next_step_template_registry_id": VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID,
        "next_step_template_registry_version": VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_VERSION,
        "analysis_run_id": kwargs.get("analysis_run_id"),
        "bundle_manifest_hash": kwargs.get("bundle_manifest_hash"),
        "evidence_refs": list(dict.fromkeys(str(item) for item in kwargs.get("evidence_refs", ()) if item)),
        "input_refs": list(dict.fromkeys(str(item) for item in kwargs.get("input_refs", ()) if item)),
    }
    if intended_role == "out_of_domain_validation":
        record["out_of_domain_prefix_required"] = True
        record["dataset_display_name"] = str(engine.get("dataset_display_name", "the validation population"))
    record["content_hash"] = sha256(_plain(record))
    return record


def verify_robustness_grade(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema_version") != ROBUSTNESS_GRADE_SCHEMA_VERSION:
        raise ValidityIntegrityError("robustness grade schema is unsupported")
    record = deepcopy(dict(value))
    content_hash = record.pop("content_hash", None)
    if not isinstance(content_hash, str) or sha256(_plain(record)) != content_hash:
        raise ValidityIntegrityError("robustness grade hash does not match")
    if record.get("grade") not in ROBUSTNESS_GRADES:
        raise ValidityIntegrityError("robustness grade is unsupported")
    for key in ("benchmark_group_refs", "evidence_refs", "input_refs"):
        values = record.get(key)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValidityIntegrityError("robustness grade references are malformed")
    groups = record.get("benchmark_groups")
    if not isinstance(groups, list) or any(
        not isinstance(group, Mapping)
        or not isinstance(group.get("group_ref"), str)
        or _number(group.get("adjusted_ci_lower")) is None
        for group in groups
    ):
        raise ValidityIntegrityError("robustness grade benchmark groups are malformed")
    if [group["group_ref"] for group in groups] != record.get("benchmark_group_refs"):
        raise ValidityIntegrityError("robustness grade group order is inconsistent")
    if record.get("grade") == "UNAVAILABLE":
        if any(
            record.get(key) is not None
            for key in (
                "strongest_group_ref",
                "median_group_ref",
                "strongest_adjusted_ci_lower",
                "median_adjusted_ci_lower",
            )
        ):
            raise ValidityIntegrityError("unavailable robustness grade exposes a benchmark")
    elif any(
        record.get(key) is None
        for key in (
            "strongest_group_ref",
            "median_group_ref",
            "strongest_adjusted_ci_lower",
            "median_adjusted_ci_lower",
        )
    ):
        raise ValidityIntegrityError("available robustness grade is incomplete")
    record["content_hash"] = content_hash
    return record


def verify_evidence_verdict(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema_version") != EVIDENCE_VERDICT_SCHEMA_VERSION:
        raise ValidityIntegrityError("evidence verdict schema is unsupported")
    if any(key in value for key in ("language", "next_step", "rendered_text")):
        raise ValidityIntegrityError("generated text is not part of an Evidence Verdict record")
    record = deepcopy(dict(value))
    content_hash = record.pop("content_hash", None)
    if not isinstance(content_hash, str) or sha256(_plain(record)) != content_hash:
        raise ValidityIntegrityError("evidence verdict hash does not match")
    if record.get("scope") != "population":
        raise ValidityIntegrityError("evidence verdict scope is unsupported")
    if record.get("intended_role") not in CORE_ROLES:
        raise ValidityIntegrityError("evidence verdict role is unsupported")
    if record.get("verdict_code") not in VERDICT_CODES or record.get("effect_display") not in EFFECT_DISPLAYS:
        raise ValidityIntegrityError("evidence verdict vocabulary is unsupported")
    expected_subject, expected_decision, default_scope = _role_permissions(
        str(record["intended_role"])
    )
    claim_scope = record.get("claim_scope", record.get("permitted_claim_scope"))
    if claim_scope not in {"population", "population_and_subject"}:
        raise ValidityIntegrityError("evidence verdict claim scope is unsupported")
    if default_scope == "population" and claim_scope != default_scope:
        raise ValidityIntegrityError("evidence verdict claim scope exceeds the role ceiling")
    if record.get("permitted_claim_scope") != claim_scope:
        raise ValidityIntegrityError("evidence verdict claim scope fields disagree")
    if record.get("subject_application_role_permitted") is not expected_subject:
        raise ValidityIntegrityError("subject permission exceeds the role ceiling")
    if record.get("decision_support_role_permitted") is not expected_decision:
        raise ValidityIntegrityError("decision-support permission exceeds the role ceiling")
    if record.get("population_verdict_ref") is not None:
        raise ValidityIntegrityError("population verdict cannot reference a subject parent")
    verdict_code = record["verdict_code"]
    reason_class = record.get("insufficient_evidence_reason_class")
    if reason_class not in {None, "NOT_ESTIMABLE", "INCONCLUSIVE"}:
        raise ValidityIntegrityError("evidence verdict reason class is unsupported")
    if (verdict_code == "INSUFFICIENT") != (reason_class is not None):
        raise ValidityIntegrityError("evidence verdict reason class is inconsistent")
    if record["intended_role"] == "out_of_domain_validation":
        if record.get("out_of_domain_prefix_required") is not True or not isinstance(
            record.get("dataset_display_name"), str
        ) or not record["dataset_display_name"]:
            raise ValidityIntegrityError("out-of-domain verdict prefix is missing")
    elif "out_of_domain_prefix_required" in record or "dataset_display_name" in record:
        raise ValidityIntegrityError("out-of-domain fields are mis-scoped")
    if record["intended_role"] == "rejection_vignette" and record["verdict_code"] != "INSUFFICIENT":
        raise ValidityIntegrityError("rejection vignette cannot publish an estimable verdict")
    if (
        record.get("verdict_policy_id") != DIAGNOSTIC_POLICY_ID
        or record.get("verdict_policy_version") != DIAGNOSTIC_POLICY_VERSION
        or record.get("trigger_registry_id") != VALIDITY_TRIGGER_REGISTRY_ID
        or record.get("trigger_registry_version") != VALIDITY_TRIGGER_REGISTRY_VERSION
        or record.get("next_step_template_registry_id") != VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID
        or record.get("next_step_template_registry_version") != VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_VERSION
        or record.get("language_policy_id") != VALIDITY_LANGUAGE_POLICY_ID
        or record.get("language_policy_version") != VALIDITY_LANGUAGE_POLICY_VERSION
    ):
        raise ValidityIntegrityError("evidence verdict policy binding is unsupported")
    trigger_codes = record.get("trigger_codes")
    if not isinstance(trigger_codes, list) or not trigger_codes:
        raise ValidityIntegrityError("evidence verdict trigger set is missing")
    if any(code not in TRIGGER_PRIORITIES for code in trigger_codes):
        raise ValidityIntegrityError("evidence verdict trigger is unregistered")
    if len(set(trigger_codes)) != len(trigger_codes):
        raise ValidityIntegrityError("evidence verdict trigger set is duplicated")
    if any(code == "EVIDENCE_POLICY_PASSED" for code in trigger_codes[1:]):
        raise ValidityIntegrityError("success trigger is not a secondary trigger")
    if trigger_codes != sorted(trigger_codes, key=lambda code: (TRIGGER_PRIORITIES[code], code)):
        raise ValidityIntegrityError("evidence verdict triggers are not canonically ordered")
    primary_trigger = record.get("primary_trigger_code")
    if primary_trigger != record.get("primary_trigger") or primary_trigger != trigger_codes[0]:
        raise ValidityIntegrityError("evidence verdict primary trigger is inconsistent")
    if verdict_code == "SUPPORTED_UNDER_ASSUMPTIONS":
        if trigger_codes != ["EVIDENCE_POLICY_PASSED"]:
            raise ValidityIntegrityError("supported verdict has non-success triggers")
    elif "EVIDENCE_POLICY_PASSED" in trigger_codes or primary_trigger not in _NEXT_STEPS:
        raise ValidityIntegrityError("non-supported verdict trigger is invalid")
    expected_template_ids = [
        f"{VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID}:{code.lower()}" for code in trigger_codes
    ]
    if record.get("next_step_template_ids") != expected_template_ids or record.get(
        "next_step_template_id"
    ) != expected_template_ids[0]:
        raise ValidityIntegrityError("evidence verdict next-step templates are inconsistent")
    effect_display = record["effect_display"]
    effect = record.get("effect")
    if effect_display == "NONE":
        if any(
            record.get(key) is not None
            for key in (
                "effect_result_ref",
                "effect_result_hash",
                "canonical_unit",
                "canonical_slippage_duration_basis",
                "effect",
            )
        ):
            raise ValidityIntegrityError("effect-free verdict exposes effect fields")
    else:
        if not isinstance(effect, Mapping):
            raise ValidityIntegrityError("effect-bearing verdict has no effect")
        projected = _effect_projection(effect)
        if (
            not isinstance(record.get("effect_result_ref"), str)
            or not record["effect_result_ref"]
            or record.get("effect_result_hash") != sha256(_plain(effect))
        ):
            raise ValidityIntegrityError("effect-bearing verdict is not bound to its effect")
        if record.get("canonical_unit") != projected.get("unit") or record.get(
            "canonical_slippage_duration_basis"
        ) != projected.get("duration_basis"):
            raise ValidityIntegrityError("effect-bearing verdict unit binding is inconsistent")
    expected_effect = {
        "SUPPORTED_UNDER_ASSUMPTIONS": "CAUSAL_ESTIMATE",
        "TENTATIVE": "NONE",
        "ASSOCIATION_ONLY": "ADJUSTED_ASSOCIATION",
        "INSUFFICIENT": "INCONCLUSIVE_ESTIMATE"
        if reason_class == "INCONCLUSIVE"
        else "NONE",
    }[verdict_code]
    if effect_display != expected_effect:
        raise ValidityIntegrityError("effect display exceeds the verdict permission")
    if record.get("decision_support_evaluation_permitted") is not (
        record.get("verdict_code") == "SUPPORTED_UNDER_ASSUMPTIONS"
        and record.get("decision_support_role_permitted") is True
    ):
        raise ValidityIntegrityError("decision-support permission exceeds the verdict ceiling")
    record["content_hash"] = content_hash
    return record


def _subject_profile_is_explicit(subject_profile: object) -> bool:
    if not isinstance(subject_profile, Mapping) or not subject_profile:
        return False
    return all(
        isinstance(field, Mapping)
        and field.get("state") in {"present", "missing", "not_applicable"}
        for field in subject_profile.values()
    )


def _subject_propensity_value(subject_propensity: object) -> float | None:
    if not isinstance(subject_propensity, Mapping):
        return None
    if subject_propensity.get("state") != "present":
        return None
    return _number(subject_propensity.get("value"))


def _subject_gate(
    name: str,
    *,
    state: str,
    code: str | None = None,
    detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "gate": name,
        "state": state,
        "code": code,
    }
    if detail:
        result.update(deepcopy(dict(detail)))
    return result


def derive_subject_evidence_verdict(
    population_verdict: Mapping[str, Any],
    *,
    subject_id: str,
    subject_profile: Mapping[str, Any],
    subject_propensity: Mapping[str, Any],
    distribution_support: Mapping[str, Any],
    source_role: str | None = None,
) -> dict[str, Any]:
    """Publish a subject applicability verdict without estimating a subject effect.

    The subject record is a bounded application of a verified population
    verdict. It consumes the already-frozen subject profile and support
    results; it never fits a model, recalculates currentness, or turns a
    predictive score into causal evidence.
    """

    population = verify_evidence_verdict(population_verdict)
    subject_role = source_role or str(population["intended_role"])
    expected_subject_permission, _, _ = _role_permissions(subject_role)
    population_permission = (
        population["scope"] == "population"
        and population["subject_application_role_permitted"] is True
        and population["permitted_claim_scope"] == "population_and_subject"
    )
    role_permission = subject_role == "semi_synthetic_hero" and expected_subject_permission

    gates = [
        _subject_gate(
            "source_role_ceiling",
            state="passed" if role_permission and population_permission else "failed",
            code=None if role_permission and population_permission else "SOURCE_SEMANTICS_INELIGIBLE",
            detail={
                "source_role": subject_role,
                "population_subject_permission": population_permission,
            },
        ),
        _subject_gate(
            "population_permission",
            state="passed" if population_permission else "failed",
            code=None if population_permission else "SOURCE_SEMANTICS_INELIGIBLE",
            detail={
                "population_verdict_code": population["verdict_code"],
                "permitted_claim_scope": population["permitted_claim_scope"],
            },
        ),
        _subject_gate(
            "subject_profile",
            state="passed" if _subject_profile_is_explicit(subject_profile) else "failed",
            code=None
            if _subject_profile_is_explicit(subject_profile)
            else "SUBJECT_DISTRIBUTION_UNSUPPORTED",
            detail={"profile_hash": sha256(_plain(subject_profile))},
        ),
    ]

    propensity = _subject_propensity_value(subject_propensity)
    interval = {
        "lower": 0.10,
        "upper": 0.90,
        "inclusive": True,
    }
    if propensity is None:
        gates.append(
            _subject_gate(
                "propensity_support",
                state="unavailable",
                code="SUBJECT_PROPENSITY_UNAVAILABLE",
                detail={"support_interval": interval},
            )
        )
    else:
        gates.append(
            _subject_gate(
                "propensity_support",
                state=(
                    "passed"
                    if interval["lower"] <= propensity <= interval["upper"]
                    else "failed"
                ),
                code=(
                    None
                    if interval["lower"] <= propensity <= interval["upper"]
                    else "SUBJECT_OVERLAP_INSUFFICIENT"
                ),
                detail={
                    "support_interval": interval,
                    "value": propensity,
                },
            )
        )

    distribution_state = (
        distribution_support.get("state")
        if isinstance(distribution_support, Mapping)
        else None
    )
    gates.append(
        _subject_gate(
            "distribution_support",
            state="passed" if distribution_state == "supported" else "failed",
            code=None
            if distribution_state == "supported"
            else "SUBJECT_DISTRIBUTION_UNSUPPORTED",
            detail={
                "support_hash": sha256(_plain(distribution_support)),
                "reported_state": distribution_state or "unavailable",
            },
        )
    )

    failure_codes = sorted(
        {
            str(gate["code"])
            for gate in gates
            if gate.get("state") != "passed" and isinstance(gate.get("code"), str)
        },
        key=lambda code: (TRIGGER_PRIORITIES[code], code),
    )
    subject_profile_hash = sha256(_plain(subject_profile))
    subject_support_hash = sha256(_plain(gates))
    subject_claim_scope = "population_and_subject" if role_permission else "population"
    common_fields = {
        "schema_version": EVIDENCE_VERDICT_SCHEMA_VERSION,
        "scope": "subject",
        "intended_role": subject_role,
        "population_verdict_ref": population["content_hash"],
        "subject_identity": subject_id,
        "subject_profile_hash": subject_profile_hash,
        "subject_support_hash": subject_support_hash,
        "subject_gates": deepcopy(gates),
        "subject_gate_codes": failure_codes,
        "subject_applicability_state": "abstained" if failure_codes else (
            "applicable"
            if population["verdict_code"] == "SUPPORTED_UNDER_ASSUMPTIONS"
            else "population_limited"
        ),
        "permitted_claim_scope": subject_claim_scope,
        "claim_scope": subject_claim_scope,
        "subject_application_role_permitted": role_permission,
        "decision_support_role_permitted": (
            population["decision_support_role_permitted"] if not failure_codes else False
        ),
        "engine_status_ref": population.get("engine_status_ref"),
        "artifact_integrity_status_ref": population.get("artifact_integrity_status_ref"),
        "robustness_grade_ref": population.get("robustness_grade_ref"),
        "analysis_run_id": population.get("analysis_run_id"),
        "bundle_manifest_hash": population.get("bundle_manifest_hash"),
        "evidence_refs": list(population.get("evidence_refs", [])),
        "input_refs": list(population.get("input_refs", [])),
        "verdict_policy_id": population["verdict_policy_id"],
        "verdict_policy_version": population["verdict_policy_version"],
        "trigger_registry_id": population["trigger_registry_id"],
        "trigger_registry_version": population["trigger_registry_version"],
        "next_step_template_registry_id": population["next_step_template_registry_id"],
        "next_step_template_registry_version": population["next_step_template_registry_version"],
        "language_policy_id": population["language_policy_id"],
        "language_policy_version": population["language_policy_version"],
    }

    if not failure_codes:
        record = deepcopy(dict(population))
        record.update(common_fields)
        record["verdict_code"] = population["verdict_code"]
        record["insufficient_evidence_reason_class"] = population[
            "insufficient_evidence_reason_class"
        ]
        record["effect_display"] = population["effect_display"]
        record["effect_result_ref"] = population["effect_result_ref"]
        record["effect_result_hash"] = population.get("effect_result_hash")
        record["canonical_unit"] = population["canonical_unit"]
        record["canonical_slippage_duration_basis"] = population[
            "canonical_slippage_duration_basis"
        ]
        record["effect"] = deepcopy(population["effect"])
        record["primary_trigger_code"] = population["primary_trigger_code"]
        record["primary_trigger"] = population["primary_trigger"]
        record["trigger_codes"] = list(population["trigger_codes"])
    else:
        primary_trigger = failure_codes[0]
        record = {
            **common_fields,
            "verdict_code": "INSUFFICIENT",
            "insufficient_evidence_reason_class": "NOT_ESTIMABLE",
            "effect_display": "NONE",
            "effect_result_ref": None,
            "effect_result_hash": None,
            "canonical_unit": None,
            "canonical_slippage_duration_basis": None,
            "effect": None,
            "primary_trigger_code": primary_trigger,
            "primary_trigger": primary_trigger,
            "trigger_codes": failure_codes,
            "decision_support_evaluation_permitted": False,
        }

    record["decision_support_evaluation_permitted"] = bool(
        record["verdict_code"] == "SUPPORTED_UNDER_ASSUMPTIONS"
        and record["decision_support_role_permitted"] is True
        and not failure_codes
    )
    record["next_step_template_id"] = (
        f"{VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID}:{record['primary_trigger_code'].lower()}"
    )
    record["next_step_template_ids"] = [
        f"{VALIDITY_NEXT_STEP_TEMPLATE_REGISTRY_ID}:{code.lower()}"
        for code in record["trigger_codes"]
    ]
    record.pop("content_hash", None)
    record["content_hash"] = sha256(_plain(record))
    return verify_subject_evidence_verdict(record)


def verify_subject_evidence_verdict(value: Mapping[str, Any]) -> dict[str, Any]:
    """Verify the subject-scoped extension of the immutable verdict schema."""

    if not isinstance(value, Mapping) or value.get("scope") != "subject":
        raise ValidityIntegrityError("subject evidence verdict scope is unsupported")
    record = deepcopy(dict(value))
    content_hash = record.pop("content_hash", None)
    if not isinstance(content_hash, str) or sha256(_plain(record)) != content_hash:
        raise ValidityIntegrityError("subject evidence verdict hash does not match")
    if not isinstance(record.get("population_verdict_ref"), str) or not record[
        "population_verdict_ref"
    ]:
        raise ValidityIntegrityError("subject verdict is not bound to a population verdict")
    if not isinstance(record.get("subject_identity"), str) or not record["subject_identity"]:
        raise ValidityIntegrityError("subject verdict identity is missing")
    if record.get("subject_applicability_state") not in {
        "applicable",
        "population_limited",
        "abstained",
    }:
        raise ValidityIntegrityError("subject applicability state is unsupported")
    for key in ("subject_profile_hash", "subject_support_hash"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValidityIntegrityError("subject support binding is missing")
    gate_codes = record.get("subject_gate_codes")
    if not isinstance(gate_codes, list) or any(
        not isinstance(code, str) or code not in TRIGGER_PRIORITIES for code in gate_codes
    ):
        raise ValidityIntegrityError("subject gate codes are unsupported")
    if record.get("subject_applicability_state") == "abstained" and (
        record.get("verdict_code") != "INSUFFICIENT" or not gate_codes
    ):
        raise ValidityIntegrityError("abstained subject applicability is inconsistent")
    if record.get("subject_applicability_state") != "abstained" and gate_codes:
        raise ValidityIntegrityError("subject gate codes exceed the applicability state")
    if record.get("verdict_code") == "INSUFFICIENT" and record.get("effect") is not None:
        raise ValidityIntegrityError("subject abstention exposes an effect")

    population_projection = deepcopy(record)
    population_projection["scope"] = "population"
    population_projection["population_verdict_ref"] = None
    expected_subject, expected_decision, _ = _role_permissions(
        str(record["intended_role"])
    )
    population_projection["subject_application_role_permitted"] = expected_subject
    population_projection["decision_support_role_permitted"] = expected_decision
    population_projection.pop("subject_identity", None)
    population_projection.pop("subject_profile_hash", None)
    population_projection.pop("subject_support_hash", None)
    population_projection.pop("subject_gate_codes", None)
    population_projection.pop("subject_applicability_state", None)
    population_projection.pop("content_hash", None)
    population_projection["content_hash"] = sha256(_plain(population_projection))
    verify_evidence_verdict(population_projection)
    record["content_hash"] = content_hash
    return record


def render_subject_evidence_verdict(verdict: Mapping[str, Any]) -> dict[str, str]:
    """Render subject applicability without individualized causal language."""

    record = verify_subject_evidence_verdict(verdict)
    state = str(record["subject_applicability_state"])
    code = str(record["verdict_code"])
    if state == "applicable" and code == "SUPPORTED_UNDER_ASSUMPTIONS":
        language = (
            "Population evidence is applicable to this subject profile under the stated assumptions. "
            "This is not a case-level causal claim."
        )
        next_step = (
            "The separate Decision Support contract may inspect governed options; no action is authorized here."
        )
    elif state == "population_limited":
        language = (
            "The population evidence boundary remains in force for this subject profile; "
            "no stronger subject claim is made."
        )
        next_step = "Report the population result within its recorded claim scope; do not strengthen it for this subject."
    else:
        label = _trigger_label(str(record["primary_trigger_code"]))
        language = (
            f"Subject applicability is unavailable because {label}. "
            "No subject effect or case-level causal claim is shown."
        )
        next_step = _NEXT_STEPS[str(record["primary_trigger_code"])]
    return {
        "language": language,
        "next_step": next_step,
        "primary_trigger_label": _trigger_label(str(record["primary_trigger_code"])),
        "next_step_template_id": str(record["next_step_template_id"]),
    }


def _trigger_label(code: str) -> str:
    return code.replace("_", " ").lower()


def render_evidence_verdict(verdict: Mapping[str, Any]) -> dict[str, str]:
    """Render only the closed language and next-step registries."""

    record = verify_evidence_verdict(verdict)
    code = str(record["verdict_code"])
    primary_trigger = str(record["primary_trigger_code"])
    label = _trigger_label(primary_trigger)
    effect = record.get("effect")
    if not isinstance(effect, Mapping):
        effect = {}
    unit = "calendar days"
    if record.get("canonical_slippage_duration_basis") == "ELAPSED_86400_SECOND_DAY":
        unit = "elapsed 86,400-second days"
    if code == "SUPPORTED_UNDER_ASSUMPTIONS":
        language = (
            f"High-Load Exposure is estimated to increase Supplier Milestone Slippage by "
            f"{effect.get('estimate')} {unit} (95% interval {effect.get('ci_lower')} to {effect.get('ci_upper')}), under the stated assumptions."
        )
        if record.get("out_of_domain_prefix_required"):
            dataset_display_name = str(record.get("dataset_display_name", "the validation population"))
            language = (
                "Out-of-domain validation only — this result describes "
                f"{dataset_display_name}'s validation population and is not a construction effect claim. "
                + language
            )
        next_step = (
            "Evaluate eligible Intervention Options under the separate Decision Support contract."
            if record.get("decision_support_evaluation_permitted")
            else "Report the result within the recorded claim scope; Decision Support is prohibited."
        )
    elif code == "TENTATIVE":
        language = f"Evidence suggests a possible increase, but it is fragile because {label}."
        next_step = _NEXT_STEPS[primary_trigger]
    elif code == "ASSOCIATION_ONLY":
        language = (
            f"The adjusted association is {effect.get('estimate')} {unit} (95% interval "
            f"{effect.get('ci_lower')} to {effect.get('ci_upper')}); causal interpretation is not supported because {label}."
        )
        next_step = _NEXT_STEPS[primary_trigger]
    else:
        scope = str(record["scope"])
        language = f"The proposed driver is not supported for this {scope} because {label}."
        next_step = _NEXT_STEPS[primary_trigger]
        if record.get("insufficient_evidence_reason_class") == "INCONCLUSIVE":
            if primary_trigger == "PRIMARY_INTERVAL_INCLUDES_NULL":
                language += (
                    f" The estimate is {effect.get('estimate')} {unit}; its two-sided 95% interval, "
                    f"{effect.get('ci_lower')} to {effect.get('ci_upper')}, includes zero, so the proposed increase is inconclusive."
                )
            elif primary_trigger == "PRIMARY_EFFECT_OPPOSITE_DIRECTION":
                language += (
                    f" The estimate is {effect.get('estimate')} {unit}; its two-sided 95% interval, "
                    f"{effect.get('ci_lower')} to {effect.get('ci_upper')}, lies below zero and points opposite to the proposed delay-driver direction."
                )
    return {
        "language": language,
        "next_step": next_step,
        "primary_trigger_label": label,
        "next_step_template_id": str(record["next_step_template_id"]),
    }


def evaluate_complete_validity(
    *,
    base_diagnostics: Sequence[Mapping[str, Any]],
    primary_effect: Mapping[str, Any] | None,
    specification_variants: Mapping[str, Any] | None = None,
    cross_form_variants: Mapping[str, Any] | None = None,
    comparison_results: Mapping[str, Any] | None = None,
    benchmark_groups: Sequence[Mapping[str, Any]] | None = None,
    repeat_results: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    engine_result: Mapping[str, Any] | None = None,
    intended_role: str = "semi_synthetic_hero",
    scope: str = DIAGNOSTIC_SCOPE,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compose the complete post-estimation diagnostic set and verdict."""

    if engine_result is not None:
        engine_mapping = _require_mapping(engine_result, "engine result")
        if primary_effect is None:
            primary_effect = _primary_effect(engine_mapping)
        sensitivity_values = engine_mapping.get(
            "sensitivity_results",
            engine_mapping.get("sensitivities", engine_mapping.get("sensitivity_effects")),
        )
        if isinstance(sensitivity_values, Mapping):
            if specification_variants is None:
                specification_candidate = {
                    key: sensitivity_values[key]
                    for key in _SPECIFICATION_VARIANTS
                    if key in sensitivity_values
                }
                specification_variants = specification_candidate or None
            if cross_form_variants is None:
                cross_form_candidate = {
                    key: sensitivity_values[key]
                    for key in _CROSS_FORM_VARIANTS
                    if key in sensitivity_values
                }
                cross_form_variants = cross_form_candidate or None
        if comparison_results is None:
            comparison_candidate = engine_mapping.get(
                "comparison_results", engine_mapping.get("comparisons")
            )
            if isinstance(comparison_candidate, Mapping):
                comparison_results = comparison_candidate
        if benchmark_groups is None:
            benchmark_candidate = engine_mapping.get(
                "sensitivity_benchmarks",
                engine_mapping.get("hidden_confounding_benchmarks"),
            )
            if isinstance(benchmark_candidate, Sequence) and not isinstance(
                benchmark_candidate, (str, bytes)
            ):
                benchmark_groups = benchmark_candidate
        if repeat_results is None:
            repeat_candidate: object = engine_mapping.get("repeat_results")
            if repeat_candidate is None and isinstance(primary_effect, Mapping):
                repeat_candidate = primary_effect.get("repeat_results")
            if isinstance(repeat_candidate, (Mapping, Sequence)) and not isinstance(
                repeat_candidate, (str, bytes)
            ):
                repeat_results = repeat_candidate

    diagnostics = [dict(item) for item in base_diagnostics]
    diagnostics.extend(
        [
            evaluate_specification_stability(primary_effect, specification_variants, scope=scope, **kwargs),
            evaluate_cross_form_direction(cross_form_variants, scope=scope, **kwargs),
            evaluate_comparison_triangulation(comparison_results, primary_effect=primary_effect, scope=scope, **kwargs),
            evaluate_hidden_confounding_benchmark(primary_effect, benchmark_groups, scope=scope, **kwargs),
            evaluate_repeat_stability(repeat_results, scope=scope, **kwargs),
        ]
    )
    grade = diagnostics[-2]["result"]["robustness_grade"]
    verdict = derive_evidence_verdict(
        engine_result or {"status": "estimated", "primary_effect": primary_effect},
        diagnostics,
        intended_role=intended_role,
        scope=scope,
        robustness_grade=grade,
        **kwargs,
    )
    return {
        "diagnostics": diagnostics,
        "robustness_grade": grade,
        "evidence_verdict": verdict,
    }


def publish_validity_results(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    *,
    analysis_run_id: str,
    bundle_manifest_hash: str,
    evidence_refs: Sequence[str] = (),
    input_refs: Sequence[str] = (),
    policy_id: str = DIAGNOSTIC_POLICY_ID,
    policy_version: str = DIAGNOSTIC_POLICY_VERSION,
) -> dict[str, Any]:
    """Verify the complete diagnostic, grade, and verdict read model."""

    from .diagnostics import publish_diagnostic_results

    diagnostics = publish_diagnostic_results(
        payload,
        analysis_run_id=analysis_run_id,
        bundle_manifest_hash=bundle_manifest_hash,
        evidence_refs=evidence_refs,
        input_refs=input_refs,
        policy_id=policy_id,
        policy_version=policy_version,
    )
    robustness_grade = None
    evidence_verdict = None
    if isinstance(payload, Mapping):
        grade_value = payload.get("robustness_grade")
        verdict_value = payload.get("evidence_verdict")
        if grade_value is not None:
            if not isinstance(grade_value, Mapping):
                raise ValidityIntegrityError("robustness grade payload is unsupported")
            robustness_grade = verify_robustness_grade(grade_value)
            if robustness_grade.get("analysis_run_id") != analysis_run_id:
                raise ValidityIntegrityError("Robustness Grade run binding does not match")
            if robustness_grade.get("bundle_manifest_hash") != bundle_manifest_hash:
                raise ValidityIntegrityError("Robustness Grade bundle binding does not match")
        if verdict_value is not None:
            if not isinstance(verdict_value, Mapping):
                raise ValidityIntegrityError("evidence verdict payload is unsupported")
            evidence_verdict = verify_evidence_verdict(verdict_value)
            if evidence_verdict.get("analysis_run_id") != analysis_run_id:
                raise ValidityIntegrityError("Evidence Verdict run binding does not match")
            if evidence_verdict.get("bundle_manifest_hash") != bundle_manifest_hash:
                raise ValidityIntegrityError("Evidence Verdict bundle binding does not match")
            if (
                evidence_verdict.get("robustness_grade_ref") is not None
                and (
                    robustness_grade is None
                    or evidence_verdict["robustness_grade_ref"] != robustness_grade["content_hash"]
                )
            ):
                raise ValidityIntegrityError("verdict and Robustness Grade bindings disagree")
    return {
        "diagnostics": diagnostics,
        "robustness_grade": robustness_grade,
        "evidence_verdict": evidence_verdict,
    }


def evaluate_validity_diagnostics(**kwargs: Any) -> dict[str, Any]:
    """Public complete-validity alias for callers outside the legacy module."""

    return evaluate_complete_validity(**kwargs)


# Short aliases make the declared public seam discoverable without duplicating
# policy implementations in the existing diagnostics module.
evaluate_specification_sensitivity = evaluate_specification_stability
evaluate_cross_form_stability = evaluate_cross_form_direction
evaluate_hidden_confounding = evaluate_hidden_confounding_benchmark
evaluate_verdict = derive_evidence_verdict
evaluate_evidence_verdict = derive_evidence_verdict
publish_evidence_verdict = derive_evidence_verdict
render_verdict = render_evidence_verdict
