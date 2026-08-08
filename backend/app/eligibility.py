from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping, Sequence

from .canonical import (
    Temporal as CanonicalTemporal,
    compare_temporal,
    field as canonical_field,
    sha256,
)
from .eligibility_contract import (
    ADJUSTMENT_SET_FIELDS,
    LOAD_EXPOSURE_VARIANTS,
    SUPPORTED_TARGET_MILESTONE_KINDS,
)

STAGE_ORDER = (
    "H0_HISTORY_SOURCE",
    "H1_HISTORY_COMMITMENT",
    "S0_SOURCE",
    "S1_COMMITMENT",
    "S2_WARMED",
    "S2_SNAPSHOT_OK",
    "S3_EXPOSURE",
    "S4_DESIGN",
    "S5_PROMISE",
    "S6_MATURE",
    "S7_COVARIATE",
    "S8_OUTCOME",
    "S9_OVERLAP",
)

_SUPPORTED_TARGETS = SUPPORTED_TARGET_MILESTONE_KINDS
_SUPPORTED_ROLES = frozenset(
    {"semi_synthetic_hero", "out_of_domain_validation", "rejection_vignette"}
)
_REVIEWED_FIELD_MAPPING_RULE_IDS = frozenset(
    {
        "field-state-preserving.v1",
        "olist.category-preserving.v1",
        "olist.complexity-not-mapped.v1",
        "olist.one-order-item-row.v1",
        "olist.price-brl-preserving.v1",
        "olist.project-not-mapped.v1",
        "olist.project-phase-not-mapped.v1",
        "olist.urgency-not-mapped.v1",
        "olist.customer-state-preserving.v1",
        "olist.contract-form-not-mapped.v1",
        "scms.product-group-preserving.v1",
        "scms.complexity-not-mapped.v1",
        "scms.quantity-not-captured.v1",
        "scms.value-not-captured.v1",
        "scms.project-not-mapped.v1",
        "scms.project-phase-not-mapped.v1",
        "scms.urgency-not-mapped.v1",
        "scms.geography-not-mapped.v1",
        "scms.contract-form-not-mapped.v1",
    }
)
_EXPOSURE_VARIANTS = LOAD_EXPOSURE_VARIANTS + (
    ("continuous_load", 0.67, 10, "history-midranks.v1"),
)
_BINARY_VARIANTS = frozenset(
    {"primary", "stricter_threshold", "short_history", "long_history"}
)
_NUMERIC_FIELDS = frozenset({"quantity", "value"})
_COMMON_SUPPORT_LOWER = 0.10
_COMMON_SUPPORT_UPPER = 0.90
_STAGE_DEFAULT_CODES = {
    "H0_HISTORY_SOURCE": "COHORT_SUPPORT_INSUFFICIENT",
    "H1_HISTORY_COMMITMENT": "COMMITMENT_CUTOFF_UNUSABLE",
    "S0_SOURCE": "COHORT_SUPPORT_INSUFFICIENT",
    "S1_COMMITMENT": "COMMITMENT_CUTOFF_UNUSABLE",
    "S2_WARMED": "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT",
    "S2_SNAPSHOT_OK": "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT",
    "S3_EXPOSURE": "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT",
    "S4_DESIGN": "CORE_TEMPORAL_COVERAGE_INSUFFICIENT",
    "S5_PROMISE": "CORE_TEMPORAL_COVERAGE_INSUFFICIENT",
    "S6_MATURE": "FOLLOW_UP_UNRESOLVABLE",
    "S7_COVARIATE": "COVARIATE_COVERAGE_INSUFFICIENT",
    "S8_OUTCOME": "OUTCOME_COVERAGE_INSUFFICIENT",
    "S9_OVERLAP": "OVERLAP_COHORT_INSUFFICIENT",
}

_REASONS: dict[str, tuple[str, str]] = {
    "SOURCE_SEMANTICS_INELIGIBLE": (
        "The frozen source role or target mapping cannot support this estimand.",
        "Use an authorized Dataset Version with reviewed supplier-milestone semantics.",
    ),
    "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT": (
        "Resolvable load snapshots do not cover the warmed supplier cohort sufficiently.",
        "Restore point-in-time supplier membership facts and rerun the frozen cohort.",
    ),
    "CORE_TEMPORAL_COVERAGE_INSUFFICIENT": (
        "Commitment or frozen-promise coverage does not meet the declared temporal gate.",
        "Repair canonical commitment and promise lineage before estimation.",
    ),
    "OUTCOME_COVERAGE_INSUFFICIENT": (
        "Mature supplier milestone outcomes do not meet the declared completeness gate.",
        "Wait for or repair the frozen follow-up and target-milestone observations.",
    ),
    "CANCELLATION_COMPETING_EVENT_PRESENT": (
        "A reliable pre-milestone cancellation competes with the supplier outcome.",
        "Resolve the cancellation estimand policy before releasing an outcome cohort.",
    ),
    "COVARIATE_COVERAGE_INSUFFICIENT": (
        "The pre-registered adjustment set is too incomplete or selectively retained.",
        "Repair source mappings or collect the registered pre-decision inputs.",
    ),
    "SLIPPAGE_DURATION_BASIS_MIXED": (
        "Releasable outcome rows do not share one request-wide duration basis.",
        "Select a frozen Dataset Version with one compatible duration basis.",
    ),
    "COHORT_SUPPORT_INSUFFICIENT": (
        "The retained cohort lacks the required treatment, supplier, or within-supplier support.",
        "Use a frozen cohort with the declared minimum support; do not relax the threshold.",
    ),
    "OUTCOME_DEGENERATE": (
        "The continuous supplier slippage outcome has no usable variation.",
        "Use a frozen cohort with at least two distinct, non-zero-variance outcomes.",
    ),
    "OVERLAP_COHORT_INSUFFICIENT": (
        "Propensity trimming exceeds the common-support or post-trim cohort limits.",
        "Use the frozen propensity specification with a supported cohort; do not move the interval.",
    ),
    "COMMITMENT_CUTOFF_UNUSABLE": (
        "The commitment correction graph or point-in-time clocks cannot establish one cutoff.",
        "Repair the immutable commitment lineage and rerun the Dataset Version.",
    ),
    "TARGET_MILESTONE_UNSUPPORTED": (
        "The requested target is not a reviewed supplier-controlled milestone.",
        "Select a supported supplier_completion or supplier_handoff target.",
    ),
    "LOAD_SNAPSHOT_UNRESOLVABLE": (
        "Supplier load membership cannot be resolved at the decision cutoff.",
        "Repair the relevant canonical commitment, closure, and known_at facts.",
    ),
    "SUPPLIER_HISTORY_INSUFFICIENT": (
        "The supplier has fewer valid strictly prior load snapshots than this variant requires.",
        "Wait for more expanding supplier history; a sensitivity cannot replace the primary rule.",
    ),
    "FROZEN_PROMISE_UNAVAILABLE": (
        "No valid promise for the target was known by the line commitment cutoff.",
        "Restore a point-in-time supplier promise or leave the line out of estimation.",
    ),
    "FROZEN_PROMISE_CONFLICT": (
        "Promise revisions or corrections do not establish one immutable baseline.",
        "Repair the promise revision graph before using the line.",
    ),
    "FROZEN_PROMISE_TEMPORALLY_INVALID": (
        "The frozen promise clocks or value cannot be compared safely with commitment.",
        "Repair the promise temporal precision and known_at lineage.",
    ),
    "FOLLOW_UP_IMMATURE": (
        "The declared follow-up horizon had not matured by the observation cutoff.",
        "Wait for the frozen follow-up horizon to mature.",
    ),
    "FOLLOW_UP_UNRESOLVABLE": (
        "Promise plus follow-up cannot be compared at the retained temporal precision.",
        "Repair the promise or observation temporal basis.",
    ),
    "COVARIATE_TEMPORAL_LEAKAGE": (
        "A registered covariate is not provably known by the line commitment cutoff.",
        "Provide point-in-time covariate lineage or leave the line out.",
    ),
    "REQUIRED_COVARIATE_UNUSABLE": (
        "A registered covariate is invalid or unresolved at the line cutoff.",
        "Repair the registered pre-decision input without changing the adjustment set.",
    ),
    "OUTCOME_UNOBSERVED": (
        "No valid target milestone was observed and known by the observation cutoff.",
        "Wait for the target milestone observation or keep the line out.",
    ),
    "OUTCOME_TEMPORALLY_INVALID": (
        "The promise, target milestone, or outcome clocks are not jointly comparable.",
        "Repair the outcome temporal lineage before estimation.",
    ),
    "CANCELLED_BEFORE_MILESTONE": (
        "A cancellation preceded the valid target milestone for this line.",
        "Resolve the competing-event policy before releasing this outcome.",
    ),
    "POST_FIRST_EXPOSURE_EXCLUDED": (
        "This line occurs after the first exposed line in the frozen design block.",
        "Use the frozen first-exposure design restriction; do not reclassify later exposure.",
    ),
    "MULTI_SUPPLIER_MILESTONE_AMBIGUOUS": (
        "The line belongs to a multi-supplier design group that cannot support the estimand.",
        "Use a single-supplier design group or resolve its reviewed identity mapping.",
    ),
    "PROACTIVE_SUBJECT_INPUT_UNUSABLE": (
        "The proactive subject input is missing, unmapped, invalid, or late-known.",
        "Submit the registered subject inputs with known_at no later than decision_at.",
    ),
    "SUBJECT_OVERLAP_INSUFFICIENT": (
        "The subject propensity is outside the inclusive historical common-support interval.",
        "Do not display an individualized effect; reassess the subject against supported history.",
    ),
    "SUBJECT_DISTRIBUTION_UNSUPPORTED": (
        "The subject lacks the required two-arm marginal or local distribution support.",
        "Do not display an individualized effect; collect a subject supported by the frozen cohort.",
    ),
    "PROPENSITY_SCORES_UNAVAILABLE": (
        "No frozen cross-fitted propensity scores were supplied at the eligibility boundary.",
        "Run the approved propensity stage and return its cross-fitted scores without fitting an effect model.",
    ),
    "SUBJECT_PROPENSITY_UNAVAILABLE": (
        "The subject propensity required for the subject overlap gate is unavailable.",
        "Supply the subject score from the paired frozen propensity ensemble.",
    ),
    "PRECEDING_ELIGIBILITY_GATE_FAILED": (
        "A preceding pre-estimation gate failed, so overlap was not evaluated.",
        "Resolve the earliest failed eligibility stage before supplying overlap scores.",
    ),
    "COHORT_GATE_FAILED": (
        "The historical cohort is not eligible for an estimator input.",
        "Resolve the earliest failed cohort gate before evaluating the subject.",
    ),
    "ELIGIBILITY_NOT_IMPLEMENTED": (
        "Eligibility stages are unavailable.",
        "Restore the versioned pre-estimation eligibility contract.",
    ),
}


def _ordered_unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _record_field(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump(mode="json")
        except TypeError:
            value = value.model_dump()
    if not isinstance(value, Mapping):
        return {"state": "missing"}
    state = value.get("state", "unresolved")
    result: dict[str, Any] = {"state": str(state)}
    if state == "present" and "value" in value:
        result["value"] = deepcopy(value.get("value"))
    for key in ("known_at", "lineage_ref"):
        if key in value:
            result[key] = deepcopy(value[key])
    return result


def _field_state(value: Any) -> str:
    return _record_field(value).get("state", "unresolved")


def _field_value(value: Any) -> Any:
    record = _record_field(value)
    return record.get("value") if record.get("state") == "present" else None


def _cutoff_field(value: Any) -> dict[str, Any]:
    if isinstance(value, CanonicalTemporal):
        return deepcopy(value.field)
    return _record_field(value)


def _temporal(value: Any) -> CanonicalTemporal:
    if isinstance(value, CanonicalTemporal):
        return value
    if isinstance(value, Mapping) and "state" in value:
        from .risk import _temporal_from_record

        return _temporal_from_record(value)
    from .canonical import normalise_temporal

    return normalise_temporal(value)


def _compare(left: Any, right: Any) -> int | None:
    return compare_temporal(_temporal(left), _temporal(right))


def _reason_details(code: str | None) -> tuple[str | None, str | None]:
    if not code:
        return None, None
    reason, next_step = _REASONS.get(
        code,
        (
            "The eligibility stage could not be resolved without inventing a fact.",
            "Repair the frozen lineage or configuration and rerun eligibility.",
        ),
    )
    return reason, next_step


def _identity_hash(values: Sequence[str]) -> str:
    return sha256(sorted(set(values)))


def _public_ids(values: Sequence[str], trigger_mode: str) -> list[str] | None:
    return list(sorted(set(values))) if trigger_mode == "reactive" else None


def _stage_record(
    stage: str,
    selected_ids: Sequence[str],
    *,
    trigger_mode: str,
    denominator_ids: Sequence[str] | None = None,
    numerator_ids: Sequence[str] | None = None,
    threshold: Any | None = None,
    eligibility_codes: Sequence[str] = (),
    status: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected = sorted(set(selected_ids))
    denominator = sorted(set(denominator_ids if denominator_ids is not None else selected))
    numerator = sorted(
        set(numerator_ids if numerator_ids is not None else selected)
    )
    codes = _ordered_unique(
        sorted({code for code in eligibility_codes if isinstance(code, str) and code})
    )
    if status is None:
        status = "passed" if not codes else "failed"
    if status != "passed" and not codes:
        default_code = _STAGE_DEFAULT_CODES.get(stage)
        if default_code:
            codes = [default_code]
    rate = len(numerator) / len(denominator) if denominator else None
    reason_code = codes[0] if codes else None
    reason, next_step = _reason_details(reason_code)
    result: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "state": "eligible" if status == "passed" else "scientifically_unavailable",
        "selected_count": len(selected),
        "selected_identity_hash": _identity_hash(selected),
        "denominator_count": len(denominator),
        "denominator_identity_hash": _identity_hash(denominator),
        "numerator_count": len(numerator),
        "numerator_identity_hash": _identity_hash(numerator),
        "overall_rate": rate,
        "threshold": threshold,
        "eligibility_codes": codes,
        "reason_code": reason_code,
        "reason": reason,
        "next_step": next_step,
    }
    if trigger_mode == "reactive":
        result["selected_ids"] = selected
        result["denominator_ids"] = denominator
        result["numerator_ids"] = numerator
    if extra:
        result.update(deepcopy(dict(extra)))
    return result


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _numeric_scalar(value: Any) -> float | None:
    if _finite_number(value):
        return float(value)
    if isinstance(value, Mapping):
        amount = value.get("amount")
        if _finite_number(amount):
            return float(amount)
    return None


def _nearest_rank(values: Sequence[float], percentile: float) -> float | None:
    ordered = sorted(float(value) for value in values if _finite_number(value))
    if not ordered:
        return None
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _treatment_support(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalised = [row for row in rows if isinstance(row, Mapping)]
    exposed = [row for row in normalised if bool(row.get("exposure"))]
    unexposed = [row for row in normalised if not bool(row.get("exposure"))]
    suppliers = {
        str(row.get("supplier_id"))
        for row in normalised
        if isinstance(row.get("supplier_id"), str) and row.get("supplier_id")
    }
    exposed_suppliers = {
        str(row.get("supplier_id"))
        for row in exposed
        if isinstance(row.get("supplier_id"), str) and row.get("supplier_id")
    }
    unexposed_suppliers = {
        str(row.get("supplier_id"))
        for row in unexposed
        if isinstance(row.get("supplier_id"), str) and row.get("supplier_id")
    }
    by_supplier: dict[str, set[bool]] = {}
    for row in normalised:
        supplier = row.get("supplier_id")
        if isinstance(supplier, str) and supplier:
            by_supplier.setdefault(supplier, set()).add(bool(row.get("exposure")))
    mixed_suppliers = {supplier for supplier, arms in by_supplier.items() if len(arms) == 2}
    count = len(normalised)
    exposed_count = len(exposed)
    prevalence = exposed_count / count if count else None
    result = {
        "state": "supported",
        "count": count,
        "exposed_count": exposed_count,
        "unexposed_count": len(unexposed),
        "exposure_prevalence": prevalence,
        "supplier_count": len(suppliers),
        "exposed_supplier_count": len(exposed_suppliers),
        "unexposed_supplier_count": len(unexposed_suppliers),
        "mixed_supplier_count": len(mixed_suppliers),
        "thresholds": {
            "minimum_lines": 500,
            "minimum_lines_per_arm": 100,
            "prevalence_lower": 0.10,
            "prevalence_upper": 0.90,
            "minimum_suppliers": 30,
            "minimum_suppliers_per_arm": 20,
            "minimum_mixed_suppliers": 20,
        },
        "eligibility_codes": [],
    }
    if (
        count < 500
        or exposed_count < 100
        or len(unexposed) < 100
        or prevalence is None
        or not 0.10 <= prevalence <= 0.90
        or len(suppliers) < 30
        or len(exposed_suppliers) < 20
        or len(unexposed_suppliers) < 20
        or len(mixed_suppliers) < 20
    ):
        result["state"] = "unsupported"
        result["eligibility_codes"] = ["COHORT_SUPPORT_INSUFFICIENT"]
    return result


def evaluate_propensity_overlap(
    rows: Sequence[Mapping[str, Any]],
    *,
    propensity_key: str = "propensity",
    exposure_key: str = "exposure",
    id_key: str = "id",
) -> dict[str, Any]:
    """Apply the frozen inclusive propensity common-support rule.

    This seam consumes scores only. It deliberately has no model-fitting or
    treatment-effect behavior.
    """
    normalised: list[dict[str, Any]] = []
    missing_scores: list[str] = []
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, Mapping):
            continue
        row = dict(raw_row)
        identity = row.get(id_key, row.get("order_line_id", str(index)))
        identity = str(identity)
        propensity = row.get(propensity_key)
        if isinstance(propensity, Mapping) and propensity.get("state") == "present":
            propensity = propensity.get("value")
        if not _finite_number(propensity):
            missing_scores.append(identity)
            continue
        row["id"] = identity
        row["exposure"] = bool(row.get(exposure_key))
        row["propensity"] = float(propensity)
        normalised.append(row)
    normalised.sort(key=lambda row: str(row["id"]))
    retained = [
        row
        for row in normalised
        if _COMMON_SUPPORT_LOWER <= row["propensity"] <= _COMMON_SUPPORT_UPPER
    ]
    trimmed = [row for row in normalised if row not in retained]
    retained_ids = [str(row["id"]) for row in retained]
    trimmed_ids = [str(row["id"]) for row in trimmed]
    all_count = len(normalised)
    overall_trim_rate = len(trimmed) / all_count if all_count else None
    arm_trim_rates: dict[str, float | None] = {}
    for arm, value in (("exposed", True), ("unexposed", False)):
        arm_rows = [row for row in normalised if bool(row["exposure"]) is value]
        arm_trimmed = [row for row in trimmed if bool(row["exposure"]) is value]
        arm_trim_rates[arm] = len(arm_trimmed) / len(arm_rows) if arm_rows else None
    post_trim_support = _treatment_support(
        [
            {
                "exposure": row["exposure"],
                "supplier_id": row.get("supplier_id"),
            }
            for row in retained
        ]
    )
    codes: list[str] = []
    if missing_scores:
        codes.append("PROPENSITY_SCORES_UNAVAILABLE")
    if (
        overall_trim_rate is None
        or overall_trim_rate > 0.20
        or any(rate is not None and rate > 0.20 for rate in arm_trim_rates.values())
        or post_trim_support["state"] != "supported"
    ):
        codes.append("OVERLAP_COHORT_INSUFFICIENT")
    state = "supported" if not codes else "unsupported"
    reason_code = codes[0] if codes else None
    reason, next_step = _reason_details(reason_code)
    return {
        "state": state,
        "support_interval": {
            "lower": _COMMON_SUPPORT_LOWER,
            "upper": _COMMON_SUPPORT_UPPER,
            "inclusive": True,
        },
        "scored_count": all_count,
        "scored_identity_hash": _identity_hash([str(row["id"]) for row in normalised]),
        "retained_count": len(retained),
        "retained_identity_hash": _identity_hash(retained_ids),
        "retained_ids": retained_ids,
        "trimmed_count": len(trimmed),
        "trimmed_identity_hash": _identity_hash(trimmed_ids),
        "trimmed_ids": trimmed_ids,
        "overall_trim_rate": overall_trim_rate,
        "arm_trim_rates": arm_trim_rates,
        "post_trim_support": post_trim_support,
        "missing_score_ids": sorted(missing_scores),
        "eligibility_codes": _ordered_unique(codes),
        "reason_code": reason_code,
        "reason": reason,
        "next_step": next_step,
    }


def _categorical_key(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return str(value)
    return str(value)


def _gower_contribution(
    subject_field: Mapping[str, Any],
    row_field: Mapping[str, Any],
    *,
    numeric: bool,
    pooled_range: float | None,
) -> float:
    subject_state = subject_field.get("state", "unresolved")
    row_state = row_field.get("state", "unresolved")
    if subject_state != "present" or row_state != "present":
        return 0.0 if subject_state == row_state else 1.0
    subject_value = subject_field.get("value")
    row_value = row_field.get("value")
    if not numeric:
        return 0.0 if subject_value == row_value else 1.0
    subject_numeric = _numeric_scalar(subject_value)
    row_numeric = _numeric_scalar(row_value)
    if subject_numeric is None or row_numeric is None:
        return 1.0
    if pooled_range is None or pooled_range == 0:
        return 0.0 if subject_numeric == row_numeric else 1.0
    return min(abs(subject_numeric - row_numeric) / pooled_range, 1.0)


def evaluate_subject_distribution_support(
    subject_inputs: Mapping[str, Any],
    historical_rows: Sequence[Mapping[str, Any]],
    *,
    exposure_key: str = "exposure",
) -> dict[str, Any]:
    """Check the frozen marginal and two-arm local subject support contract."""
    subject = {
        name: _record_field(subject_inputs.get(name))
        for name in subject_inputs
    }
    field_names = list(subject)
    rows = [row for row in historical_rows if isinstance(row, Mapping)]
    arms = {
        "unexposed": [row for row in rows if not bool(row.get(exposure_key))],
        "exposed": [row for row in rows if bool(row.get(exposure_key))],
    }
    support: dict[str, Any] = {
        "categorical_levels": {},
        "missingness_vectors": {},
        "numeric_ranges": {},
        "local_neighbors": {},
    }
    failures: list[str] = []

    def row_inputs(row: Mapping[str, Any]) -> Mapping[str, Any]:
        value = row.get("inputs", row.get("adjustment_inputs", {}))
        return value if isinstance(value, Mapping) else {}

    numeric_flags: dict[str, bool] = {}
    for name in field_names:
        subject_field = subject[name]
        numeric_flags[name] = name in _NUMERIC_FIELDS or _numeric_scalar(
            subject_field.get("value")
        ) is not None
        if not numeric_flags[name]:
            for row in rows:
                candidate = _record_field(row_inputs(row).get(name))
                if candidate.get("state") == "present" and _numeric_scalar(candidate.get("value")) is not None:
                    numeric_flags[name] = True
                    break

    for name in field_names:
        subject_field = subject[name]
        if numeric_flags[name]:
            ranges: dict[str, Any] = {}
            pooled_values: list[float] = []
            for arm, arm_rows in arms.items():
                values = [
                    _numeric_scalar(_record_field(row_inputs(row).get(name)).get("value"))
                    for row in arm_rows
                    if _record_field(row_inputs(row).get(name)).get("state") == "present"
                    and _numeric_scalar(_record_field(row_inputs(row).get(name)).get("value")) is not None
                ]
                values = [value for value in values if value is not None]
                lower = _nearest_rank(values, 0.01)
                upper = _nearest_rank(values, 0.99)
                ranges[arm] = {
                    "count": len(values),
                    "lower_1st_nearest_rank": lower,
                    "upper_99th_nearest_rank": upper,
                    "inclusive": True,
                }
                pooled_values.extend(values)
                if (
                    subject_field.get("state") == "present"
                    and _numeric_scalar(subject_field.get("value")) is not None
                    and (
                        lower is None
                        or upper is None
                        or not lower
                        <= _numeric_scalar(subject_field.get("value"))
                        <= upper
                    )
                ):
                    failures.append("numeric_range")
            support["numeric_ranges"][name] = ranges
            pooled_lower = _nearest_rank(pooled_values, 0.01)
            pooled_upper = _nearest_rank(pooled_values, 0.99)
            support["numeric_ranges"][name]["pooled_1st_nearest_rank"] = pooled_lower
            support["numeric_ranges"][name]["pooled_99th_nearest_rank"] = pooled_upper
            support["numeric_ranges"][name]["pooled_range"] = (
                pooled_upper - pooled_lower
                if pooled_lower is not None and pooled_upper is not None
                else None
            )
            continue

        levels: dict[str, dict[str, int]] = {}
        for arm, arm_rows in arms.items():
            for row in arm_rows:
                value = _record_field(row_inputs(row).get(name))
                if value.get("state") != "present":
                    continue
                key = _categorical_key(value.get("value"))
                levels.setdefault(key, {"unexposed": 0, "exposed": 0})[arm] += 1
        support["categorical_levels"][name] = levels
        subject_key = _categorical_key(subject_field.get("value"))
        counts = levels.get(subject_key, {"unexposed": 0, "exposed": 0})
        if subject_field.get("state") == "present" and (
            counts["unexposed"] < 20 or counts["exposed"] < 20
        ):
            failures.append("categorical_level")

    subject_missingness = tuple(subject[name].get("state", "unresolved") for name in field_names)
    missingness_counts: dict[str, int] = {"unexposed": 0, "exposed": 0}
    for arm, arm_rows in arms.items():
        vectors: dict[str, int] = {}
        for row in arm_rows:
            values = row_inputs(row)
            vector = tuple(_field_state(values.get(name)) for name in field_names)
            key = str(vector)
            vectors[key] = vectors.get(key, 0) + 1
        missingness_counts[arm] = vectors.get(str(subject_missingness), 0)
        support["missingness_vectors"][arm] = {
            "subject_vector": list(subject_missingness),
            "subject_vector_count": missingness_counts[arm],
            "counts": vectors,
        }
    if any(count < 20 for count in missingness_counts.values()):
        failures.append("missingness_vector")

    pooled_ranges = {
        name: support["numeric_ranges"].get(name, {}).get("pooled_range")
        for name in field_names
        if numeric_flags[name]
    }
    distances: dict[str, list[float]] = {"unexposed": [], "exposed": []}
    for arm, arm_rows in arms.items():
        for row in arm_rows:
            values = row_inputs(row)
            contributions = [
                _gower_contribution(
                    subject[name],
                    _record_field(values.get(name)),
                    numeric=numeric_flags[name],
                    pooled_range=pooled_ranges.get(name),
                )
                for name in field_names
            ]
            distances[arm].append(sum(contributions) / len(contributions) if contributions else 1.0)
    neighbor_counts = {
        arm: sum(distance <= 0.25 for distance in arm_distances)
        for arm, arm_distances in distances.items()
    }
    support["local_neighbors"] = {
        arm: {
            "distance_threshold": 0.25,
            "count_within_threshold": neighbor_counts[arm],
            "distance_count": len(distances[arm]),
        }
        for arm in distances
    }
    if any(count < 20 for count in neighbor_counts.values()):
        failures.append("local_neighbors")

    if not field_names or any(
        _field_state(subject_inputs.get(name)) not in {"present", "missing", "not_applicable"}
        for name in field_names
    ):
        failures.append("subject_input_state")
    state = "supported" if not failures else "unsupported"
    code = None if state == "supported" else "SUBJECT_DISTRIBUTION_UNSUPPORTED"
    reason, next_step = _reason_details(code)
    return {
        "state": state,
        "feature_count": len(field_names),
        "support": support,
        "eligibility_codes": [code] if code else [],
        "reason_code": code,
        "reason": reason,
        "next_step": next_step,
    }


def _line_events(lineage: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = {}
    events = lineage.get("order_line_events", [])
    if not isinstance(events, list):
        return result
    for event in events:
        if not isinstance(event, Mapping):
            continue
        line_id = event.get("order_line_id")
        if isinstance(line_id, str) and line_id:
            result.setdefault(line_id, []).append(event)
    return result


def _line_map(lineage: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    lines = lineage.get("order_lines", [])
    if not isinstance(lines, list):
        return result
    for line in lines:
        if not isinstance(line, Mapping):
            continue
        line_id = line.get("order_line_id")
        if isinstance(line_id, str) and line_id and line_id not in result:
            result[line_id] = line
    return result


def _quarantined_line_ids(lineage: Mapping[str, Any]) -> set[str]:
    findings = lineage.get("validation_findings", [])
    if not isinstance(findings, list):
        return set()
    result: set[str] = set()
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        disposition = finding.get("disposition")
        if disposition == "reject_run":
            return set(_line_map(lineage))
        if disposition != "quarantine_record":
            continue
        refs = finding.get("affected_refs", [])
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, str):
                    continue
                result.add(ref)
                result.update(
                    line_id
                    for line_id in _line_map(lineage)
                    if ref.startswith(f"{line_id}.")
                )
    return result


def _line_field(
    lineage: Mapping[str, Any],
    line: Mapping[str, Any],
    line_id: str,
    name: str,
    cutoff: CanonicalTemporal | None,
) -> dict[str, Any]:
    fields = line.get("fields", {})
    canonical = fields.get(name, {"state": "missing"}) if isinstance(fields, Mapping) else {"state": "missing"}
    observations = lineage.get("source_observations", [])
    has_observation = any(
        isinstance(observation, Mapping)
        and observation.get("target_record_id") == line_id
        and observation.get("target_field_path") == f"fields.{name}"
        for observation in observations
    ) if isinstance(observations, list) else False
    if not has_observation or cutoff is None:
        record = _record_field(canonical)
        return {"state": "unresolved"} if record.get("state") == "present" else record
    from .risk import resolve_field_as_of

    return _record_field(
        resolve_field_as_of(
            lineage,
            order_line_id=line_id,
            field_path=f"fields.{name}",
            canonical_value=canonical,
            cutoff=cutoff,
        )
    )


def _line_supplier(
    lineage: Mapping[str, Any],
    line: Mapping[str, Any],
    line_id: str,
    cutoff: CanonicalTemporal | None,
) -> dict[str, Any]:
    canonical = line.get("supplier_id", {"state": "missing"})
    if cutoff is not None:
        from .risk import resolve_field_as_of

        return _record_field(
            resolve_field_as_of(
                lineage,
                order_line_id=line_id,
                field_path="supplier_id",
                canonical_value=canonical,
                cutoff=cutoff,
            )
        )
    if isinstance(canonical, str):
        return canonical_field("present", canonical)
    return _record_field(canonical)


def _field_late_by_cutoff(
    lineage: Mapping[str, Any],
    line_id: str,
    field_path: str,
    cutoff: CanonicalTemporal,
) -> bool:
    observations = lineage.get("source_observations", [])
    if not isinstance(observations, list):
        return False
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        if observation.get("target_record_id") != line_id or observation.get("target_field_path") != field_path:
            continue
        order = _compare(observation.get("known_at"), cutoff)
        if order is None or order == 1:
            return True
    return False


def _source_semantics(lineage: Mapping[str, Any], target_milestone_kind: str) -> dict[str, Any]:
    dataset = lineage.get("dataset_version", {})
    manifest = lineage.get("mapping_manifest", {})
    role = dataset.get("intended_role") if isinstance(dataset, Mapping) else None
    source_kind = dataset.get("source_kind") if isinstance(dataset, Mapping) else None
    manifest_role = manifest.get("intended_role") if isinstance(manifest, Mapping) else None
    codes: list[str] = []
    if role not in _SUPPORTED_ROLES or manifest_role != role:
        codes.append("SOURCE_SEMANTICS_INELIGIBLE")
    if role == "rejection_vignette":
        codes.append("SOURCE_SEMANTICS_INELIGIBLE")
    if isinstance(manifest, Mapping):
        field_mappings = manifest.get("field_mappings")
        required_fields = set(ADJUSTMENT_SET_FIELDS)
        if not isinstance(field_mappings, Mapping) or set(field_mappings) != required_fields:
            codes.append("SOURCE_SEMANTICS_INELIGIBLE")
        else:
            if any(
                not isinstance(mapping, Mapping)
                or mapping.get("rule_id") not in _REVIEWED_FIELD_MAPPING_RULE_IDS
                or mapping.get("rule_version") != "1"
                for mapping in field_mappings.values()
            ):
                codes.append("SOURCE_SEMANTICS_INELIGIBLE")
        event_mappings = manifest.get("event_mappings")
        if not isinstance(event_mappings, Mapping) or not {
            "kind",
            "milestone_kind",
            "occurred_at",
            "known_at",
            "promised_for",
        }.issubset(event_mappings):
            codes.append("SOURCE_SEMANTICS_INELIGIBLE")
        assumptions = manifest.get("mapping_assumptions")
        if not isinstance(assumptions, list):
            codes.append("SOURCE_SEMANTICS_INELIGIBLE")
        elif role == "semi_synthetic_hero" and not {
            "semi_synthetic.clocks.v1",
            "semi_synthetic.generated_origin.v1",
        }.issubset(set(assumptions)):
            codes.append("SOURCE_SEMANTICS_INELIGIBLE")
        elif role == "out_of_domain_validation" and (
            source_kind != "olist"
            or not {
                "olist.transport_timing.v1",
                "olist.shipping_limit_known_at_purchase.v1",
            }.issubset(set(assumptions))
            or not isinstance(event_mappings, Mapping)
            or not isinstance(event_mappings.get("transport_timing"), Mapping)
            or not {"committed", "promised", "reached"}.issubset(
                event_mappings["transport_timing"]
            )
        ):
            codes.append("SOURCE_SEMANTICS_INELIGIBLE")
        elif role == "rejection_vignette" and source_kind != "scms":
            codes.append("SOURCE_SEMANTICS_INELIGIBLE")
    if target_milestone_kind not in _SUPPORTED_TARGETS:
        codes.append("SOURCE_SEMANTICS_INELIGIBLE")
    findings = lineage.get("validation_findings", [])
    if isinstance(findings, list) and any(
        isinstance(finding, Mapping)
        and finding.get("code") == "PROMISE_ACTUAL_EQUALITY_SUSPICIOUS"
        and finding.get("disposition") in {"quarantine_record", "reject_run"}
        for finding in findings
    ):
        codes.append("SOURCE_SEMANTICS_INELIGIBLE")
    code = "SOURCE_SEMANTICS_INELIGIBLE" if codes else None
    reason, next_step = _reason_details(code)
    return {
        "state": "eligible" if code is None else "ineligible",
        "intended_role": role,
        "mapping_role": manifest_role,
        "target_milestone_kind": target_milestone_kind,
        "eligibility_codes": [code] if code else [],
        "reason_code": code,
        "reason": reason,
        "next_step": next_step,
    }


def _commitment_for_line(
    events: Sequence[Mapping[str, Any]],
    cutoff: CanonicalTemporal,
) -> tuple[Mapping[str, Any] | None, CanonicalTemporal | None, str | None]:
    from .risk import resolve_commitment_cutoff, _temporal_from_record

    event, error = resolve_commitment_cutoff(list(events), known_cutoff=cutoff)
    if event is None:
        return None, None, error or "COMMITMENT_CUTOFF_UNUSABLE"
    occurred = _temporal_from_record(event.get("clocks", {}).get("occurred_at"))
    if occurred.field.get("state") != "present" or occurred.comparable is None:
        return None, None, "COMMITMENT_CUTOFF_UNUSABLE"
    return event, occurred, None


def _default_selector_ids(
    available_ids: Sequence[str],
    events_by_line: Mapping[str, Sequence[Mapping[str, Any]]],
    observation: CanonicalTemporal,
) -> list[str]:
    """Return the frozen global window, retaining unresolved lines for H1."""
    from .risk import _temporal_from_record, resolve_commitment_cutoff

    selected: list[str] = []
    for line_id in sorted(set(available_ids)):
        try:
            commitment, _ = resolve_commitment_cutoff(
                list(events_by_line.get(line_id, [])),
            )
        except (TypeError, ValueError, KeyError):
            selected.append(line_id)
            continue
        if commitment is None:
            selected.append(line_id)
            continue
        cutoff = _temporal_from_record(
            commitment.get("clocks", {}).get("occurred_at")
        )
        if (
            isinstance(cutoff, CanonicalTemporal)
            and _compare(cutoff, observation) == 1
        ):
            continue
        selected.append(line_id)
    return selected


def frozen_selector_ids(
    lineage: Mapping[str, Any],
    *,
    observation_cutoff: Any,
    subject_id: str,
    trigger_mode: str,
    history_selected_ids: Sequence[str] | None = None,
    estimator_selected_ids: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Resolve the outcome-independent H0/S0 selector populations once."""
    observation = _temporal(observation_cutoff)
    line_by_id = _line_map(lineage)
    events_by_line = _line_events(lineage)
    quarantined = _quarantined_line_ids(lineage)
    available_ids = sorted(line_id for line_id in line_by_id if line_id not in quarantined)
    default_selector_ids = _default_selector_ids(
        available_ids,
        events_by_line,
        observation,
    )
    history_ids = (
        sorted(set(history_selected_ids).intersection(available_ids))
        if history_selected_ids is not None
        else default_selector_ids
    )
    estimator_ids = (
        sorted(set(estimator_selected_ids).intersection(available_ids))
        if estimator_selected_ids is not None
        else default_selector_ids
    )
    normalised_trigger = "proactive" if trigger_mode == "proactive" else "reactive"
    subject_id = str(subject_id)
    if normalised_trigger == "reactive" and subject_id in available_ids:
        history_ids = sorted({*history_ids, subject_id})
        estimator_ids = sorted({*estimator_ids, subject_id})
    h0_ids = sorted(set(history_ids) | set(estimator_ids))
    s0_ids = [
        line_id
        for line_id in estimator_ids
        if not (normalised_trigger == "reactive" and line_id == subject_id)
    ]
    return {
        "history": history_ids,
        "estimator": estimator_ids,
        "h0": h0_ids,
        "s0": s0_ids,
    }


def _coverage(
    denominator_ids: Sequence[str],
    numerator_ids: Sequence[str],
    records: Mapping[str, Mapping[str, Any]],
    *,
    overall_minimum: float,
    arm_minimum: float | None = None,
    gap_maximum: float | None = None,
) -> dict[str, Any]:
    denominator = sorted(set(denominator_ids))
    numerator_set = set(numerator_ids)
    numerator = [line_id for line_id in denominator if line_id in numerator_set]
    overall_rate = len(numerator) / len(denominator) if denominator else None
    rates: dict[str, float | None] = {}
    for arm, value in (("exposed", True), ("unexposed", False)):
        arm_denominator = [
            line_id
            for line_id in denominator
            if records.get(line_id, {}).get("exposure") is value
        ]
        arm_numerator = [line_id for line_id in arm_denominator if line_id in numerator_set]
        rates[arm] = len(arm_numerator) / len(arm_denominator) if arm_denominator else None
    arm_gap = (
        abs(rates["exposed"] - rates["unexposed"])
        if rates["exposed"] is not None and rates["unexposed"] is not None
        else None
    )
    passes = denominator and overall_rate is not None and overall_rate >= overall_minimum
    if arm_minimum is not None:
        passes = bool(passes) and all(
            rate is not None and rate >= arm_minimum for rate in rates.values()
        )
    if gap_maximum is not None:
        passes = bool(passes) and arm_gap is not None and arm_gap <= gap_maximum
    return {
        "denominator_count": len(denominator),
        "numerator_count": len(numerator),
        "overall_rate": overall_rate,
        "arm_rates": rates,
        "arm_gap": arm_gap,
        "thresholds": {
            "overall_minimum": overall_minimum,
            "arm_minimum": arm_minimum,
            "gap_maximum": gap_maximum,
        },
        "state": "passed" if passes else "failed",
    }


def _lineage_refs(
    lineage: Mapping[str, Any],
    line_id: str,
    cutoff: CanonicalTemporal | None = None,
) -> list[str]:
    observations = lineage.get("source_observations", [])
    if not isinstance(observations, list):
        return []
    refs: list[str] = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        if observation.get("target_record_id") != line_id:
            continue
        if not isinstance(observation.get("source_observation_id"), str):
            continue
        if cutoff is not None and _compare(observation.get("known_at"), cutoff) not in {-1, 0}:
            continue
        refs.append(str(observation["source_observation_id"]))
    return sorted(refs)


def _design_group(line: Mapping[str, Any], fields: Mapping[str, Any]) -> str | None:
    project = _field_value(fields.get("project_id"))
    return str(project) if project is not None else None


def _is_olist_source(lineage: Mapping[str, Any]) -> bool:
    dataset = lineage.get("dataset_version", {})
    manifest = lineage.get("mapping_manifest", {})
    source_kind = dataset.get("source_kind") if isinstance(dataset, Mapping) else None
    role = dataset.get("intended_role") if isinstance(dataset, Mapping) else None
    schema_id = manifest.get("source_schema_id") if isinstance(manifest, Mapping) else None
    return (
        str(source_kind).lower() == "olist"
        or str(schema_id).lower() == "olist"
        or role == "out_of_domain_validation"
    )


def _sanitize_proactive(value: Any) -> Any:
    hidden_keys = {
        "selected_ids",
        "denominator_ids",
        "numerator_ids",
        "retained_ids",
        "trimmed_ids",
        "missing_score_ids",
        "contributing_order_line_ids",
        "canonical_line_identity",
        "canonical_line_identities",
        "lineage_refs",
        "event_id",
        "event_ids",
        "source_observation_id",
        "target_record_id",
        "evidence_refs",
        "provisional_load_snapshot",
        "qualifying_snapshots",
        "order_line_id",
        "subject_id",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_proactive(item)
            for key, item in value.items()
            if key not in hidden_keys
        }
    if isinstance(value, list):
        return [_sanitize_proactive(item) for item in value]
    return deepcopy(value)


def _variant_input(
    variant_id: str,
    ids: Sequence[str],
    records: Mapping[str, Mapping[str, Any]],
    *,
    trigger_mode: str,
) -> dict[str, Any]:
    selected = sorted(set(ids))
    payload: dict[str, Any] = {
        "schema_version": "pre-estimation-estimator-input.v1",
        "variant_id": variant_id,
        "selected_count": len(selected),
        "selected_identity_hash": _identity_hash(selected),
        "adjustment_set": list(ADJUSTMENT_SET_FIELDS),
        "model_fit": False,
        "effect_estimate": None,
    }
    if trigger_mode == "reactive":
        payload["selected_ids"] = selected
    if variant_id == "continuous_load":
        payload["exposure_field"] = "load_percentile"
    else:
        payload["exposure_field"] = "high_load_exposure"
    payload["outcome_field"] = (
        "supplier_milestone_late"
        if variant_id == "late_risk"
        else "supplier_milestone_slippage_days"
    )
    payload["lineage_ref_count"] = sum(
        len(records.get(line_id, {}).get("lineage_refs", [])) for line_id in selected
    )
    return payload


def evaluate_pre_estimation_eligibility(
    lineage: Mapping[str, Any],
    *,
    subject_id: str,
    subject_supplier_id: str,
    decision_cutoff: Any,
    observation_cutoff: Any,
    target_milestone_kind: str,
    duration_basis: str,
    trigger_mode: str,
    follow_up_horizon_days: int = 0,
    subject_inputs: Mapping[str, Any] | None = None,
    subject_original_promise: Any | None = None,
    subject_target_milestone: Any | None = None,
    propensity_scores: Mapping[str, Any] | None = None,
    historical_propensity_scores: Mapping[str, Any] | None = None,
    subject_propensity: Any | None = None,
    history_selected_ids: Sequence[str] | None = None,
    estimator_selected_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate the deterministic pre-estimation cohort and subject gates.

    The function consumes frozen canonical facts and, when present, supplied
    cross-fitted propensity scores. It never fits a model, selects a
    reference artifact, evaluates an intervention, or produces an effect.
    """
    trigger_mode = "proactive" if trigger_mode == "proactive" else "reactive"
    decision = _temporal(decision_cutoff)
    observation = _temporal(observation_cutoff)
    subject_id = str(subject_id)
    subject_supplier_id = str(subject_supplier_id)
    source = _source_semantics(lineage, target_milestone_kind)
    line_by_id = _line_map(lineage)
    events_by_line = _line_events(lineage)
    frozen_ids = frozen_selector_ids(
        lineage,
        observation_cutoff=observation,
        subject_id=subject_id,
        trigger_mode=trigger_mode,
        history_selected_ids=history_selected_ids,
        estimator_selected_ids=estimator_selected_ids,
    )
    history_selector_ids = frozen_ids["history"]
    estimator_selector_ids = frozen_ids["estimator"]
    h0_ids = frozen_ids["h0"]
    s0_ids = frozen_ids["s0"]
    records: dict[str, dict[str, Any]] = {}
    line_codes: dict[str, list[str]] = {line_id: [] for line_id in h0_ids}

    for line_id in h0_ids:
        line = line_by_id[line_id]
        events = events_by_line.get(line_id, [])
        record: dict[str, Any] = {
            "line": line,
            "events": events,
            "lineage_refs": [],
            "supplier_field": _record_field(line.get("supplier_id")),
            "supplier_id": None,
            "commitment": None,
            "commitment_cutoff": None,
            "commitment_code": None,
            "inputs": {},
            "snapshot": None,
            "history_ids": [],
            "history_valid_ids": [],
            "exposure_by_variant": {},
        }
        supplier = _line_supplier(lineage, line, line_id, observation)
        record["supplier_field"] = supplier
        if supplier.get("state") == "present":
            record["supplier_id"] = supplier.get("value")
        else:
            line_codes[line_id].append("LOAD_SNAPSHOT_UNRESOLVABLE")
        if target_milestone_kind not in _SUPPORTED_TARGETS:
            record["commitment_code"] = "TARGET_MILESTONE_UNSUPPORTED"
            line_codes[line_id].append("TARGET_MILESTONE_UNSUPPORTED")
        else:
            commitment, cutoff, code = _commitment_for_line(events, observation)
            record["commitment"] = commitment
            record["commitment_cutoff"] = cutoff
            record["commitment_code"] = code
            if code:
                line_codes[line_id].append(code)
            elif cutoff is not None:
                order = _compare(cutoff, observation)
                if order is None or order == 1:
                    record["commitment_code"] = "COMMITMENT_CUTOFF_UNUSABLE"
                    line_codes[line_id].append("COMMITMENT_CUTOFF_UNUSABLE")
        record["lineage_refs"] = _lineage_refs(
            lineage,
            line_id,
            record.get("commitment_cutoff") or observation,
        )
        records[line_id] = record

    h1_ids = [
        line_id
        for line_id in h0_ids
        if not records[line_id]["commitment_code"]
        and records[line_id]["commitment_cutoff"] is not None
    ]
    s1_ids = [line_id for line_id in s0_ids if line_id in set(h1_ids)]
    for line_id in s0_ids:
        if line_id not in s1_ids and not line_codes[line_id]:
            line_codes[line_id].append("COMMITMENT_CUTOFF_UNUSABLE")

    stages: dict[str, dict[str, Any]] = {}
    stages["H0_HISTORY_SOURCE"] = _stage_record(
        "H0_HISTORY_SOURCE",
        h0_ids,
        trigger_mode=trigger_mode,
        status="passed" if h0_ids else "unavailable",
    )
    stages["H1_HISTORY_COMMITMENT"] = _stage_record(
        "H1_HISTORY_COMMITMENT",
        h1_ids,
        trigger_mode=trigger_mode,
        denominator_ids=h0_ids,
        numerator_ids=h1_ids,
        eligibility_codes=_ordered_unique(
            code
            for line_id in h0_ids
            for code in line_codes[line_id]
            if code == "COMMITMENT_CUTOFF_UNUSABLE"
            or code == "TARGET_MILESTONE_UNSUPPORTED"
        ),
        status="passed" if h1_ids else "failed",
    )
    stages["S0_SOURCE"] = _stage_record(
        "S0_SOURCE",
        s0_ids,
        trigger_mode=trigger_mode,
        status="passed" if s0_ids else "unavailable",
    )
    stages["S1_COMMITMENT"] = _stage_record(
        "S1_COMMITMENT",
        s1_ids,
        trigger_mode=trigger_mode,
        denominator_ids=s0_ids,
        numerator_ids=s1_ids,
        eligibility_codes=_ordered_unique(
            code for line_id in s0_ids for code in line_codes[line_id]
        ),
        status="passed" if s1_ids else "failed",
    )

    snapshot_cache: dict[str, dict[str, Any]] = {}

    def snapshot_for(line_id: str) -> dict[str, Any]:
        if line_id in snapshot_cache:
            return snapshot_cache[line_id]
        record = records[line_id]
        cutoff = record.get("commitment_cutoff")
        supplier = record.get("supplier_id")
        if not isinstance(cutoff, CanonicalTemporal) or not isinstance(supplier, str):
            snapshot = {
                "state": "unresolved",
                "eligibility_codes": ["LOAD_SNAPSHOT_UNRESOLVABLE"],
            }
        else:
            try:
                from .risk import resolve_supplier_load_snapshot

                snapshot = resolve_supplier_load_snapshot(
                    lineage,
                    subject_id=line_id,
                    subject_supplier_id=supplier,
                    decision_cutoff=cutoff,
                    target_milestone_kind=target_milestone_kind,
                    duration_basis=duration_basis,
                )
            except (TypeError, ValueError, KeyError):
                snapshot = {
                    "state": "unresolved",
                    "eligibility_codes": ["LOAD_SNAPSHOT_UNRESOLVABLE"],
                }
        snapshot_cache[line_id] = deepcopy(snapshot)
        return snapshot_cache[line_id]

    built_variants: dict[str, dict[str, Any]] = {}
    for variant_id, percentile, minimum_history, _rule_id in _EXPOSURE_VARIANTS:
        if variant_id == "continuous_load" and "primary" in built_variants:
            primary = built_variants["primary"]
            s2_warmed_ids = list(primary["s2_warmed_ids"])
            s2_snapshot_ids = list(primary["s2_snapshot_ids"])
            s3_ids = list(primary["s3_ids"])
        else:
            s2_warmed_ids = []
            s2_snapshot_ids = []
            s3_ids = []
            for line_id in s1_ids:
                record = records[line_id]
                supplier = record.get("supplier_id")
                cutoff = record.get("commitment_cutoff")
                if not isinstance(supplier, str) or not isinstance(cutoff, CanonicalTemporal):
                    continue
                prior_ids = [
                    prior_id
                    for prior_id in h1_ids
                    if prior_id != line_id
                    and records[prior_id].get("supplier_id") == supplier
                    and isinstance(records[prior_id].get("commitment_cutoff"), CanonicalTemporal)
                    and _compare(records[prior_id]["commitment_cutoff"], cutoff) == -1
                ]
                prior_ids.sort()
                record["history_ids"] = prior_ids
                if len(prior_ids) < minimum_history:
                    line_codes[line_id].append("SUPPLIER_HISTORY_INSUFFICIENT")
                    continue
                s2_warmed_ids.append(line_id)
                snapshot = snapshot_for(line_id)
                record["snapshot"] = snapshot
                if snapshot.get("state") != "present":
                    codes = snapshot.get("eligibility_codes", [])
                    line_codes[line_id].extend(
                        str(code) for code in codes if isinstance(code, str)
                    )
                    if not codes:
                        line_codes[line_id].append("LOAD_SNAPSHOT_UNRESOLVABLE")
                    continue
                s2_snapshot_ids.append(line_id)
                valid_history_ids = [
                    prior_id
                    for prior_id in prior_ids
                    if snapshot_for(prior_id).get("state") == "present"
                ]
                record["history_valid_ids"] = valid_history_ids
                if len(valid_history_ids) < minimum_history:
                    line_codes[line_id].append("SUPPLIER_HISTORY_INSUFFICIENT")
                    continue
                history_counts = [
                    int(snapshot_for(prior_id).get("concurrent_load_count", 0))
                    for prior_id in valid_history_ids
                ]
                try:
                    from .risk import evaluate_supplier_load_exposure

                    load_result = evaluate_supplier_load_exposure(
                        current_load_count=int(snapshot.get("concurrent_load_count", 0)),
                        history_load_counts=history_counts,
                        duration_basis=duration_basis,
                    )
                    load_variant = load_result.get("variants", {}).get(variant_id)
                except (TypeError, ValueError, KeyError):
                    load_variant = None
                if not isinstance(load_variant, Mapping) or load_variant.get("state") != "present":
                    line_codes[line_id].extend(
                        str(code)
                        for code in (load_variant or {}).get("eligibility_codes", ["LOAD_SNAPSHOT_UNRESOLVABLE"])
                        if isinstance(code, str)
                    )
                    continue
                record["exposure_by_variant"][variant_id] = deepcopy(dict(load_variant))
                record["exposure"] = bool(load_variant.get("high_load_exposure"))
                s3_ids.append(line_id)

        s2_warmed_ids = sorted(set(s2_warmed_ids))
        s2_snapshot_ids = sorted(set(s2_snapshot_ids))
        s3_ids = sorted(set(s3_ids))

        if variant_id == "continuous_load" and "primary" in built_variants:
            for line_id in s3_ids:
                primary_exposure = records[line_id].get("exposure_by_variant", {}).get("primary")
                if primary_exposure is not None:
                    records[line_id]["exposure_by_variant"][variant_id] = deepcopy(primary_exposure)
                    records[line_id]["exposure"] = bool(
                        primary_exposure.get("high_load_exposure")
                    )

        design_source_ids = s3_ids
        if variant_id == "continuous_load" and "primary" in built_variants:
            design_source_ids = built_variants["primary"]["s4_ids"]
        olist_source = _is_olist_source(lineage)
        dataset = lineage.get("dataset_version", {})
        out_of_domain_olist = (
            olist_source
            and isinstance(dataset, Mapping)
            and dataset.get("intended_role") == "out_of_domain_validation"
        )
        groups: dict[str, set[str]] = {}
        for line_id in design_source_ids:
            record = records[line_id]
            record["inputs"] = {
                name: _line_field(
                    lineage,
                    record["line"],
                    line_id,
                    name,
                    record["commitment_cutoff"],
                )
                for name in ADJUSTMENT_SET_FIELDS
            }
        group_source_ids = sorted(line_by_id) if olist_source else design_source_ids
        for line_id in group_source_ids:
            if olist_source:
                record = records.get(line_id)
                line = record["line"] if record is not None else line_by_id[line_id]
                group = line.get("order_group_id")
                supplier = (
                    record.get("supplier_id")
                    if record is not None
                    else _field_value(_line_supplier(lineage, line, line_id, observation))
                )
                if (
                    isinstance(group, str)
                    and group
                    and isinstance(supplier, str)
                    and supplier
                ):
                    groups.setdefault(group, set()).add(supplier)
        multi_groups = {group for group, suppliers in groups.items() if len(suppliers) > 1}
        s4_ids: list[str] = []
        for line_id in design_source_ids:
            record = records[line_id]
            group = _design_group(record["line"], record.get("inputs", {}))
            olist_group = record["line"].get("order_group_id") if olist_source else None
            if group is None and not out_of_domain_olist:
                line_codes[line_id].append("SOURCE_SEMANTICS_INELIGIBLE")
                continue
            if olist_group in multi_groups:
                line_codes[line_id].append("MULTI_SUPPLIER_MILESTONE_AMBIGUOUS")
                continue
            exposure = record.get("exposure_by_variant", {}).get(variant_id)
            if variant_id == "continuous_load":
                exposure = record.get("exposure_by_variant", {}).get("primary", exposure)
            if not isinstance(exposure, Mapping):
                continue
            if variant_id in _BINARY_VARIANTS:
                current_exposed = exposure.get("high_load_exposure")
                if current_exposed:
                    current_cutoff = record.get("commitment_cutoff")
                    prior_exposed = False
                    for prior_id in design_source_ids:
                        if prior_id == line_id or records[prior_id].get("supplier_id") != record.get("supplier_id"):
                            continue
                        prior_group = _design_group(records[prior_id]["line"], records[prior_id].get("inputs", {}))
                        if prior_group != group:
                            continue
                        prior_exposure = records[prior_id].get("exposure_by_variant", {}).get(variant_id, {})
                        prior_cutoff = records[prior_id].get("commitment_cutoff")
                        if (
                            isinstance(prior_exposure, Mapping)
                            and prior_exposure.get("high_load_exposure")
                            and isinstance(current_cutoff, CanonicalTemporal)
                            and isinstance(prior_cutoff, CanonicalTemporal)
                            and _compare(prior_cutoff, current_cutoff) == -1
                        ):
                            prior_exposed = True
                            break
                    if prior_exposed:
                        line_codes[line_id].append("POST_FIRST_EXPOSURE_EXCLUDED")
                        continue
            s4_ids.append(line_id)

        promise_map: dict[str, Any] = {}
        s5_ids: list[str] = []
        for line_id in s4_ids:
            record = records[line_id]
            cutoff = record.get("commitment_cutoff")
            if not isinstance(cutoff, CanonicalTemporal):
                continue
            from .risk import resolve_frozen_promise

            resolution = resolve_frozen_promise(
                record["events"],
                target_milestone_kind=target_milestone_kind,
                commitment_cutoff=cutoff,
            )
            promise_map[line_id] = resolution
            if resolution.code is not None or resolution.value is None:
                line_codes[line_id].append(resolution.code or "FROZEN_PROMISE_UNAVAILABLE")
            else:
                s5_ids.append(line_id)

        outcome_map: dict[str, dict[str, Any]] = {}
        s6_ids: list[str] = []
        for line_id in s5_ids:
            record = records[line_id]
            resolution = promise_map[line_id]
            from .risk import resolve_supplier_milestone_slippage

            outcome = resolve_supplier_milestone_slippage(
                record["events"],
                target_milestone_kind=target_milestone_kind,
                commitment_cutoff=record["commitment_cutoff"],
                observation_cutoff=observation,
                canonical_slippage_duration_basis=duration_basis,
                follow_up_horizon_days=follow_up_horizon_days,
                role="ESTIMATION_LINE",
                frozen_promise=resolution,
            )
            outcome_map[line_id] = outcome
            follow_up = outcome.get("follow_up", {})
            if outcome.get("outcome_code") in {"FOLLOW_UP_IMMATURE", "FOLLOW_UP_UNRESOLVABLE"} or follow_up.get("state") != "present":
                line_codes[line_id].append(
                    outcome.get("outcome_code") or "FOLLOW_UP_UNRESOLVABLE"
                )
                continue
            s6_ids.append(line_id)

        s7_ids: list[str] = []
        for line_id in s6_ids:
            record = records[line_id]
            cutoff = record.get("commitment_cutoff")
            inputs = {
                name: _line_field(
                    lineage,
                    record["line"],
                    line_id,
                    name,
                    cutoff,
                )
                for name in ADJUSTMENT_SET_FIELDS
            }
            record["inputs"] = inputs
            unusable = False
            for name in ADJUSTMENT_SET_FIELDS:
                value = inputs[name]
                state = value.get("state")
                if isinstance(cutoff, CanonicalTemporal) and _field_late_by_cutoff(
                    lineage, line_id, f"fields.{name}", cutoff
                ):
                    line_codes[line_id].append("COVARIATE_TEMPORAL_LEAKAGE")
                    unusable = True
                elif state in {"invalid", "unresolved"}:
                    line_codes[line_id].append("REQUIRED_COVARIATE_UNUSABLE")
                    unusable = True
            if not unusable:
                s7_ids.append(line_id)

        s8_ids: list[str] = []
        cancellation_ids: list[str] = []
        for line_id in s7_ids:
            outcome = outcome_map[line_id]
            code = outcome.get("outcome_code")
            if outcome.get("state") == "present" and code is None:
                s8_ids.append(line_id)
            else:
                if code:
                    line_codes[line_id].append(str(code))
                if code == "CANCELLED_BEFORE_MILESTONE":
                    cancellation_ids.append(line_id)

        design_identity_missing_ids = []
        if not out_of_domain_olist:
            design_identity_missing_ids = [
                line_id
                for line_id in s3_ids
                if _design_group(
                    records[line_id]["line"],
                    records[line_id].get("inputs", {}),
                )
                is None
            ]
        design_identity_gate = {
            "gate": "design_identity",
            "code": (
                "SOURCE_SEMANTICS_INELIGIBLE"
                if design_identity_missing_ids
                else None
            ),
            "state": "failed" if design_identity_missing_ids else "passed",
            "denominator_count": len(s3_ids),
            "numerator_count": len(s3_ids) - len(design_identity_missing_ids),
            "missing_count": len(design_identity_missing_ids),
            "missing_identity_hash": _identity_hash(design_identity_missing_ids),
            "project_identity": (
                "not_required_for_out_of_domain_olist"
                if out_of_domain_olist
                else "required"
            ),
        }

        stages_for_variant: dict[str, dict[str, Any]] = {}
        stages_for_variant["S2_WARMED"] = _stage_record(
            "S2_WARMED",
            s2_warmed_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s1_ids,
            numerator_ids=s2_warmed_ids,
            eligibility_codes=[
                "SUPPLIER_HISTORY_INSUFFICIENT"
                for line_id in s1_ids
                if line_id not in s2_warmed_ids
            ],
            status="passed" if s2_warmed_ids else "failed",
            extra={"minimum_history": minimum_history},
        )
        stages_for_variant["S2_SNAPSHOT_OK"] = _stage_record(
            "S2_SNAPSHOT_OK",
            s2_snapshot_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s2_warmed_ids,
            numerator_ids=s2_snapshot_ids,
            eligibility_codes=[
                code
                for line_id in s2_warmed_ids
                if line_id not in s2_snapshot_ids
                for code in line_codes[line_id]
                if code in {"LOAD_SNAPSHOT_UNRESOLVABLE", "COMMITMENT_CUTOFF_UNUSABLE"}
            ],
            status="passed" if s2_snapshot_ids else "failed",
        )
        stages_for_variant["S3_EXPOSURE"] = _stage_record(
            "S3_EXPOSURE",
            s3_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s2_warmed_ids,
            numerator_ids=s3_ids,
            eligibility_codes=[
                "SUPPLIER_HISTORY_INSUFFICIENT"
                for line_id in s2_snapshot_ids
                if line_id not in s3_ids
            ],
            status="passed" if s3_ids else "failed",
            extra={"minimum_history": minimum_history},
        )
        stages_for_variant["S4_DESIGN"] = _stage_record(
            "S4_DESIGN",
            s4_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s3_ids,
            numerator_ids=s4_ids,
            eligibility_codes=[
                code
                for line_id in s3_ids
                if line_id not in s4_ids
                for code in line_codes[line_id]
                if code in {"MULTI_SUPPLIER_MILESTONE_AMBIGUOUS", "POST_FIRST_EXPOSURE_EXCLUDED"}
            ],
            status="passed" if s4_ids else "failed",
        )
        stages_for_variant["S5_PROMISE"] = _stage_record(
            "S5_PROMISE",
            s5_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s4_ids,
            numerator_ids=s5_ids,
            eligibility_codes=[
                code
                for line_id in s4_ids
                if line_id not in s5_ids
                for code in line_codes[line_id]
                if code.startswith("FROZEN_PROMISE") or code == "TARGET_MILESTONE_UNSUPPORTED"
            ],
            status="passed" if s5_ids else "failed",
        )
        stages_for_variant["S6_MATURE"] = _stage_record(
            "S6_MATURE",
            s6_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s5_ids,
            numerator_ids=s6_ids,
            eligibility_codes=[
                code
                for line_id in s5_ids
                if line_id not in s6_ids
                for code in line_codes[line_id]
                if code in {"FOLLOW_UP_IMMATURE", "FOLLOW_UP_UNRESOLVABLE"}
            ],
            status="passed" if s6_ids else "failed",
        )
        stages_for_variant["S7_COVARIATE"] = _stage_record(
            "S7_COVARIATE",
            s7_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s6_ids,
            numerator_ids=s7_ids,
            eligibility_codes=[
                code
                for line_id in s6_ids
                if line_id not in s7_ids
                for code in line_codes[line_id]
                if code in {"COVARIATE_TEMPORAL_LEAKAGE", "REQUIRED_COVARIATE_UNUSABLE"}
            ],
            status="passed" if s7_ids else "failed",
        )
        stages_for_variant["S8_OUTCOME"] = _stage_record(
            "S8_OUTCOME",
            s8_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s7_ids,
            numerator_ids=s8_ids,
            eligibility_codes=[
                code
                for line_id in s7_ids
                if line_id not in s8_ids
                for code in line_codes[line_id]
                if code
                in {
                    "OUTCOME_UNOBSERVED",
                    "OUTCOME_TEMPORALLY_INVALID",
                    "CANCELLED_BEFORE_MILESTONE",
                    "SLIPPAGE_DURATION_BASIS_MIXED",
                }
            ],
            status="passed" if s8_ids else "failed",
        )

        line_rows_s8 = [
            {
                "id": line_id,
                "supplier_id": records[line_id].get("supplier_id"),
                "exposure": bool(
                    records[line_id].get("exposure_by_variant", {})
                    .get(variant_id, records[line_id].get("exposure_by_variant", {}).get("primary", {}))
                    .get("high_load_exposure")
                ),
                "inputs": records[line_id].get("inputs", {}),
                "outcome": outcome_map.get(line_id, {}),
                "load_percentile": records[line_id].get("exposure_by_variant", {})
                .get(variant_id, {})
                .get("load_percentile"),
            }
            for line_id in s8_ids
        ]
        for row in line_rows_s8:
            records[row["id"]]["exposure"] = row["exposure"]

        exposure_measurement = _coverage(
            s2_warmed_ids,
            s2_snapshot_ids,
            records,
            overall_minimum=0.95,
        )
        warm_suppliers = {
            records[line_id].get("supplier_id")
            for line_id in s2_warmed_ids
            if records[line_id].get("supplier_id")
        }
        covered_suppliers = 0
        supplier_coverage: dict[str, Any] = {}
        for supplier in sorted(str(value) for value in warm_suppliers):
            supplier_warm = [
                line_id for line_id in s2_warmed_ids if records[line_id].get("supplier_id") == supplier
            ]
            supplier_snapshot = [line_id for line_id in s2_snapshot_ids if line_id in supplier_warm]
            rate = len(supplier_snapshot) / len(supplier_warm) if supplier_warm else None
            supplier_coverage[supplier] = {
                "warmed_count": len(supplier_warm),
                "snapshot_ok_count": len(supplier_snapshot),
                "rate": rate,
                "threshold": 0.90,
            }
            if rate is not None and rate >= 0.90:
                covered_suppliers += 1
        supplier_rate = covered_suppliers / len(warm_suppliers) if warm_suppliers else None
        exposure_gate_ok = (
            exposure_measurement["state"] == "passed"
            and bool(warm_suppliers)
            and supplier_rate is not None
            and supplier_rate >= 0.90
        )
        if not exposure_gate_ok:
            exposure_gate_code = "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT"
        else:
            exposure_gate_code = None
        exposure_gate = {
            "gate": "exposure_measurement_coverage",
            "code": exposure_gate_code,
            "state": "passed" if exposure_gate_ok else "failed",
            "denominator_count": len(s2_warmed_ids),
            "numerator_count": len(s2_snapshot_ids),
            "overall_rate": exposure_measurement["overall_rate"],
            "supplier_denominator_count": len(warm_suppliers),
            "supplier_numerator_count": covered_suppliers,
            "supplier_rate": supplier_rate,
            "threshold": {"overall": 0.95, "supplier": 0.90, "per_supplier": 0.90},
            "supplier_coverage": supplier_coverage,
        }

        commitment_gate = _coverage(
            s0_ids,
            s1_ids,
            records,
            overall_minimum=0.95,
        )
        promise_gate = _coverage(
            s4_ids,
            s5_ids,
            records,
            overall_minimum=0.95,
            arm_minimum=0.90,
            gap_maximum=0.05,
        )
        temporal_gate_ok = commitment_gate["state"] == "passed" and promise_gate["state"] == "passed"
        core_temporal_gate = {
            "gate": "core_temporal_coverage",
            "code": None if temporal_gate_ok else "CORE_TEMPORAL_COVERAGE_INSUFFICIENT",
            "state": "passed" if temporal_gate_ok else "failed",
            "commitment": commitment_gate,
            "promise": promise_gate,
        }

        covariate_missingness: dict[str, Any] = {}
        covariate_ok = True
        for name in ADJUSTMENT_SET_FIELDS:
            denominator = [line_id for line_id in s6_ids]
            nonpresent = [
                line_id
                for line_id in denominator
                if records[line_id].get("inputs", {}).get(name, {}).get("state") != "present"
            ]
            arm_rates: dict[str, float | None] = {}
            for arm, value in (("exposed", True), ("unexposed", False)):
                arm_denominator = [line_id for line_id in denominator if records[line_id].get("exposure") is value]
                arm_nonpresent = [line_id for line_id in nonpresent if line_id in arm_denominator]
                arm_rates[arm] = len(arm_nonpresent) / len(arm_denominator) if arm_denominator else None
            gap = (
                abs(arm_rates["exposed"] - arm_rates["unexposed"])
                if arm_rates["exposed"] is not None and arm_rates["unexposed"] is not None
                else None
            )
            field_ok = bool(denominator) and len(nonpresent) / len(denominator) <= 0.20 and all(
                rate is not None and rate <= 0.30 for rate in arm_rates.values()
            ) and gap is not None and gap <= 0.10
            covariate_ok = covariate_ok and field_ok
            covariate_missingness[name] = {
                "denominator_count": len(denominator),
                "nonpresent_count": len(nonpresent),
                "overall_rate": len(nonpresent) / len(denominator) if denominator else None,
                "arm_rates": arm_rates,
                "arm_gap": gap,
                "thresholds": {"overall": 0.20, "arm": 0.30, "gap": 0.10},
                "state": "passed" if field_ok else "failed",
            }
        retention = _coverage(
            s6_ids,
            s7_ids,
            records,
            overall_minimum=0.80,
            gap_maximum=0.10,
        )
        covariate_gate_ok = covariate_ok and retention["state"] == "passed"
        covariate_gate = {
            "gate": "covariate_coverage",
            "code": None if covariate_gate_ok else "COVARIATE_COVERAGE_INSUFFICIENT",
            "state": "passed" if covariate_gate_ok else "failed",
            "missingness": covariate_missingness,
            "retention": retention,
        }

        outcome_gate_data = _coverage(
            s7_ids,
            s8_ids,
            records,
            overall_minimum=0.95,
            arm_minimum=0.90,
            gap_maximum=0.05,
        )
        cancellation_gate = {
            "gate": "cancellation_competing_event",
            "code": "CANCELLATION_COMPETING_EVENT_PRESENT" if cancellation_ids else None,
            "state": "failed" if cancellation_ids else "passed",
            "count": len(cancellation_ids),
            "identity_hash": _identity_hash(cancellation_ids),
        }
        outcome_gate_ok = outcome_gate_data["state"] == "passed" and not cancellation_ids
        outcome_gate = {
            "gate": "outcome_coverage",
            "code": None if outcome_gate_ok else (
                "CANCELLATION_COMPETING_EVENT_PRESENT" if cancellation_ids else "OUTCOME_COVERAGE_INSUFFICIENT"
            ),
            "state": "passed" if outcome_gate_ok else "failed",
            "coverage": outcome_gate_data,
            "cancellation": cancellation_gate,
        }

        duration_values = {
            outcome.get("supplier_milestone_slippage_duration_basis")
            for outcome in outcome_map.values()
            if outcome.get("state") == "present"
            and outcome.get("supplier_milestone_slippage_duration_basis")
        }
        mixed_outcome_ids = [
            line_id
            for line_id, outcome in outcome_map.items()
            if outcome.get("outcome_code") == "SLIPPAGE_DURATION_BASIS_MIXED"
        ]
        duration_gate_ok = not mixed_outcome_ids and len(duration_values) <= 1 and (
            not duration_values or duration_basis in duration_values
        )
        duration_gate = {
            "gate": "duration_basis",
            "code": None if duration_gate_ok else "SLIPPAGE_DURATION_BASIS_MIXED",
            "state": "passed" if duration_gate_ok else "failed",
            "request_basis": duration_basis,
            "releasable_bases": sorted(str(value) for value in duration_values),
            "mixed_outcome_count": len(mixed_outcome_ids),
            "mixed_outcome_identity_hash": _identity_hash(mixed_outcome_ids),
        }

        support_s8 = _treatment_support(line_rows_s8)
        support_gate_s8 = {
            "gate": "treatment_support_pre_trim",
            "code": None if support_s8["state"] == "supported" else "COHORT_SUPPORT_INSUFFICIENT",
            "state": support_s8["state"],
            **support_s8,
        }
        outcome_values = [
            outcome_map[line_id].get("supplier_milestone_slippage_days")
            for line_id in s8_ids
            if _finite_number(outcome_map[line_id].get("supplier_milestone_slippage_days"))
        ]
        distinct_values = {float(value) for value in outcome_values}
        mean = sum(float(value) for value in outcome_values) / len(outcome_values) if outcome_values else None
        variance = (
            sum((float(value) - mean) ** 2 for value in outcome_values) / len(outcome_values)
            if outcome_values and mean is not None
            else None
        )
        variation_ok = len(distinct_values) >= 2 and variance is not None and variance > 0
        variation_gate = {
            "gate": "outcome_variation",
            "code": None if variation_ok else "OUTCOME_DEGENERATE",
            "state": "passed" if variation_ok else "failed",
            "distinct_count": len(distinct_values),
            "variance": variance,
            "threshold": {"minimum_distinct": 2, "variance_strictly_greater_than": 0},
        }
        late_count = sum(
            bool(outcome_map[line_id].get("supplier_milestone_late")) for line_id in s8_ids
        )
        late_support = {
            "state": "supported" if late_count >= 50 and len(s8_ids) - late_count >= 50 else "unavailable",
            "late_count": late_count,
            "not_late_count": len(s8_ids) - late_count,
            "threshold_per_arm": 50,
            "eligibility_codes": [] if late_count >= 50 and len(s8_ids) - late_count >= 50 else ["COHORT_SUPPORT_INSUFFICIENT"],
        }

        pre_overlap_gates = [
            source["state"] == "eligible",
            exposure_gate_ok,
            design_identity_gate["state"] == "passed",
            temporal_gate_ok,
            covariate_gate_ok,
            outcome_gate_ok,
            duration_gate_ok,
            support_s8["state"] == "supported",
            variation_ok,
        ]
        propensity_mapping: Mapping[str, Any] | None = propensity_scores or historical_propensity_scores
        overlap_result: dict[str, Any]
        s9_ids: list[str] = []
        if not all(pre_overlap_gates):
            overlap_result = {
                "state": "not_run",
                "eligibility_codes": ["PRECEDING_ELIGIBILITY_GATE_FAILED"],
                "reason_code": "PRECEDING_ELIGIBILITY_GATE_FAILED",
                "reason": _reason_details("PRECEDING_ELIGIBILITY_GATE_FAILED")[0],
                "next_step": _reason_details("PRECEDING_ELIGIBILITY_GATE_FAILED")[1],
            }
            overlap_gate = {
                "gate": "propensity_overlap",
                "code": "PRECEDING_ELIGIBILITY_GATE_FAILED",
                "state": "not_run",
            }
        elif not isinstance(propensity_mapping, Mapping):
            overlap_result = {
                "state": "unavailable",
                "eligibility_codes": ["PROPENSITY_SCORES_UNAVAILABLE"],
                "reason_code": "PROPENSITY_SCORES_UNAVAILABLE",
                "reason": _reason_details("PROPENSITY_SCORES_UNAVAILABLE")[0],
                "next_step": _reason_details("PROPENSITY_SCORES_UNAVAILABLE")[1],
            }
            overlap_gate = {
                "gate": "propensity_overlap",
                "code": "PROPENSITY_SCORES_UNAVAILABLE",
                "state": "unavailable",
            }
        else:
            overlap_rows = []
            for row in line_rows_s8:
                score = propensity_mapping.get(row["id"])
                overlap_rows.append(
                    {
                        **row,
                        "propensity": score,
                    }
                )
            overlap_result = evaluate_propensity_overlap(overlap_rows)
            s9_ids = list(overlap_result.get("retained_ids", []))
            overlap_gate = {
                "gate": "propensity_overlap",
                "code": None if overlap_result.get("state") == "supported" else (
                    overlap_result.get("reason_code") or "OVERLAP_COHORT_INSUFFICIENT"
                ),
                "state": "passed" if overlap_result.get("state") == "supported" else "failed",
                **{
                    key: overlap_result.get(key)
                    for key in (
                        "scored_count",
                        "retained_count",
                        "trimmed_count",
                        "overall_trim_rate",
                        "arm_trim_rates",
                        "support_interval",
                    )
                },
            }
        stages_for_variant["S9_OVERLAP"] = _stage_record(
            "S9_OVERLAP",
            s9_ids,
            trigger_mode=trigger_mode,
            denominator_ids=s8_ids,
            numerator_ids=s9_ids,
            eligibility_codes=overlap_result.get("eligibility_codes", []),
            status=(
                "passed"
                if overlap_result.get("state") == "supported"
                else str(overlap_result.get("state", "failed"))
            ),
            extra={"overlap": overlap_result},
        )

        support_s9: dict[str, Any] | None = None
        support_gate_s9: dict[str, Any] | None = None
        if s9_ids:
            line_rows_s9 = [row for row in line_rows_s8 if row["id"] in set(s9_ids)]
            support_s9 = _treatment_support(line_rows_s9)
            support_gate_s9 = {
                "gate": "treatment_support_post_trim",
                "code": None if support_s9["state"] == "supported" else "OVERLAP_COHORT_INSUFFICIENT",
                "state": support_s9["state"],
                **support_s9,
            }
        else:
            support_gate_s9 = {
                "gate": "treatment_support_post_trim",
                "code": "OVERLAP_COHORT_INSUFFICIENT",
                "state": "failed",
                "count": 0,
                "eligibility_codes": ["OVERLAP_COHORT_INSUFFICIENT"],
            }

        gates = [
            {
                "gate": "source_semantics",
                "code": None if source["state"] == "eligible" else "SOURCE_SEMANTICS_INELIGIBLE",
                "state": "passed" if source["state"] == "eligible" else "failed",
            },
            exposure_gate,
            design_identity_gate,
            core_temporal_gate,
            covariate_gate,
            outcome_gate,
            duration_gate,
            support_gate_s8,
            variation_gate,
            overlap_gate,
            support_gate_s9,
        ]
        for gate in gates:
            if gate.get("state") != "passed":
                code = gate.get("code")
                if not isinstance(code, str) or not code:
                    code = {
                        "source_semantics": "SOURCE_SEMANTICS_INELIGIBLE",
                        "exposure_measurement_coverage": "EXPOSURE_MEASUREMENT_COVERAGE_INSUFFICIENT",
                        "design_identity": "SOURCE_SEMANTICS_INELIGIBLE",
                        "core_temporal_coverage": "CORE_TEMPORAL_COVERAGE_INSUFFICIENT",
                        "covariate_coverage": "COVARIATE_COVERAGE_INSUFFICIENT",
                        "outcome_coverage": "OUTCOME_COVERAGE_INSUFFICIENT",
                        "duration_basis": "SLIPPAGE_DURATION_BASIS_MIXED",
                        "treatment_support_pre_trim": "COHORT_SUPPORT_INSUFFICIENT",
                        "outcome_variation": "OUTCOME_DEGENERATE",
                        "propensity_overlap": "OVERLAP_COHORT_INSUFFICIENT",
                        "treatment_support_post_trim": "OVERLAP_COHORT_INSUFFICIENT",
                    }.get(str(gate.get("gate")))
                    if code:
                        gate["code"] = code
                reason, next_step = _reason_details(code if isinstance(code, str) else None)
                gate["reason"] = reason
                gate["next_step"] = next_step
        cohort_codes = [
            str(gate["code"])
            for gate in gates
            if isinstance(gate.get("code"), str) and gate.get("code")
        ]
        variant_cohort_eligible = all(gate.get("state") == "passed" for gate in gates)
        stages_for_variant["S2_WARMED"]["coverage_gate"] = exposure_gate
        stages_for_variant["S5_PROMISE"]["coverage_gate"] = core_temporal_gate
        stages_for_variant["S7_COVARIATE"]["coverage_gate"] = covariate_gate
        stages_for_variant["S8_OUTCOME"]["coverage_gate"] = outcome_gate
        variant = {
            "variant_id": variant_id,
            "percentile": percentile,
            "minimum_history": minimum_history,
            "state": "eligible" if variant_cohort_eligible else "scientifically_unavailable",
            "stages": {
                **{
                    stage_name: deepcopy(stages[stage_name])
                    for stage_name in (
                        "H0_HISTORY_SOURCE",
                        "H1_HISTORY_COMMITMENT",
                        "S0_SOURCE",
                        "S1_COMMITMENT",
                    )
                },
                **stages_for_variant,
            },
            "gates": gates,
            "eligibility_codes": _ordered_unique(cohort_codes),
            "reason_code": cohort_codes[0] if cohort_codes else None,
            "reason": _reason_details(cohort_codes[0])[0] if cohort_codes else None,
            "next_step": _reason_details(cohort_codes[0])[1] if cohort_codes else None,
            "late_risk": late_support,
            "continuous_load": {
                "state": "available" if variant_id == "continuous_load" and variant_cohort_eligible else "unavailable",
                "exposure_field": "load_percentile",
            },
            "s2_warmed_ids": s2_warmed_ids,
            "s2_snapshot_ids": s2_snapshot_ids,
            "s3_ids": s3_ids,
            "s4_ids": s4_ids,
            "s5_ids": s5_ids,
            "s6_ids": s6_ids,
            "s7_ids": s7_ids,
            "s8_ids": s8_ids,
            "s9_ids": s9_ids,
            "records": records,
            "estimator_input": None,
        }
        built_variants[variant_id] = variant

        stages.update({
            stage_name: stage_value
            for stage_name, stage_value in stages_for_variant.items()
            if stage_name not in stages
        })

    primary_variant = built_variants["primary"]
    primary_late_support = primary_variant.get("late_risk", {})
    late_variant_codes: list[str] = []
    if primary_variant.get("state") != "eligible":
        late_variant_codes.append("PRECEDING_ELIGIBILITY_GATE_FAILED")
    if primary_late_support.get("state") != "supported":
        late_variant_codes.append("COHORT_SUPPORT_INSUFFICIENT")
    built_variants["late_risk"] = {
        "variant_id": "late_risk",
        "state": "eligible" if not late_variant_codes else "scientifically_unavailable",
        "stages": deepcopy(primary_variant.get("stages", {})),
        "gates": deepcopy(primary_variant.get("gates", [])),
        "eligibility_codes": _ordered_unique(late_variant_codes),
        "reason_code": late_variant_codes[0] if late_variant_codes else None,
        "reason": _reason_details(late_variant_codes[0])[0] if late_variant_codes else None,
        "next_step": _reason_details(late_variant_codes[0])[1] if late_variant_codes else None,
        "late_risk": deepcopy(primary_late_support),
        "continuous_load": {"state": "not_applicable", "exposure_field": "high_load_exposure"},
        "s2_warmed_ids": list(primary_variant.get("s2_warmed_ids", [])),
        "s2_snapshot_ids": list(primary_variant.get("s2_snapshot_ids", [])),
        "s3_ids": list(primary_variant.get("s3_ids", [])),
        "s4_ids": list(primary_variant.get("s4_ids", [])),
        "s5_ids": list(primary_variant.get("s5_ids", [])),
        "s6_ids": list(primary_variant.get("s6_ids", [])),
        "s7_ids": list(primary_variant.get("s7_ids", [])),
        "s8_ids": list(primary_variant.get("s8_ids", [])),
        "s9_ids": list(primary_variant.get("s9_ids", [])),
        "estimator_input": (
            _variant_input(
                "late_risk",
                primary_variant.get("s9_ids", []),
                records,
                trigger_mode=trigger_mode,
            )
            if not late_variant_codes
            else None
        ),
    }
    if trigger_mode == "proactive":
        subject_input_fields = {
            name: _record_field((subject_inputs or {}).get(name, {"state": "missing"}))
            for name in ADJUSTMENT_SET_FIELDS
        }
    else:
        subject_line = line_by_id.get(subject_id)
        subject_input_fields = {
            name: _line_field(
                lineage,
                subject_line,
                subject_id,
                name,
                decision,
            )
            if subject_line is not None
            else {"state": "missing"}
            for name in ADJUSTMENT_SET_FIELDS
        }
    subject_codes: list[str] = []
    subject_load: dict[str, Any] | None = None
    if not subject_supplier_id:
        subject_codes.append(
            "PROACTIVE_SUBJECT_INPUT_UNUSABLE"
            if trigger_mode == "proactive"
            else "LOAD_SNAPSHOT_UNRESOLVABLE"
        )
    if target_milestone_kind not in _SUPPORTED_TARGETS:
        subject_codes.append("TARGET_MILESTONE_UNSUPPORTED")

    if trigger_mode == "proactive" and subject_target_milestone is not None:
        target_record = _record_field(subject_target_milestone)
        target_known = target_record.get("known_at")
        if (
            target_record.get("state") != "present"
            or target_record.get("value") != target_milestone_kind
            or target_known is None
            or _compare(target_known, decision) not in {-1, 0}
        ):
            subject_codes.append("PROACTIVE_SUBJECT_INPUT_UNUSABLE")

    if trigger_mode == "proactive":
        for value in subject_input_fields.values():
            if value.get("state") == "present":
                known_at = value.get("known_at")
                if known_at is None or _compare(known_at, decision) not in {-1, 0}:
                    subject_codes.append("PROACTIVE_SUBJECT_INPUT_UNUSABLE")
                    break
    else:
        for value in subject_input_fields.values():
            if value.get("state") in {"invalid", "unresolved"}:
                subject_codes.append("REQUIRED_COVARIATE_UNUSABLE")
                break

    subject_promise_field: dict[str, Any] = {"state": "unresolved"}
    if trigger_mode == "reactive" and subject_id in records:
        subject_record = records[subject_id]
        subject_cutoff = subject_record.get("commitment_cutoff") or decision
        from .risk import resolve_frozen_promise

        subject_promise = resolve_frozen_promise(
            subject_record["events"],
            target_milestone_kind=target_milestone_kind,
            commitment_cutoff=subject_cutoff,
        ) if isinstance(subject_cutoff, CanonicalTemporal) else None
        if subject_promise is None or subject_promise.code is not None or subject_promise.value is None:
            subject_codes.append(
                (subject_promise.code if subject_promise is not None else None)
                or "FROZEN_PROMISE_UNAVAILABLE"
            )
        else:
            subject_promise_field = deepcopy(subject_promise.value.field)
    else:
        subject_promise_record = _record_field(subject_original_promise)
        subject_promise_temporal = (
            _temporal(subject_original_promise)
            if subject_original_promise is not None
            else CanonicalTemporal(canonical_field("missing"), None)
        )
        promise_known = True
        if trigger_mode == "proactive" and subject_original_promise is not None:
            known_at = subject_promise_record.get("known_at")
            promise_known = (
                isinstance(subject_original_promise, CanonicalTemporal)
                or (
                    known_at is not None
                    and _compare(known_at, decision) in {-1, 0}
                )
            )
        if (
            subject_promise_temporal.field.get("state") != "present"
            or subject_promise_temporal.comparable is None
            or not promise_known
            or decision.comparable is None
            or _compare(subject_promise_temporal, decision) not in {-1, 0, 1}
            or _compare(subject_promise_temporal, decision) == -1
        ):
            subject_codes.append("PROACTIVE_SUBJECT_INPUT_UNUSABLE")
        else:
            subject_promise_field = deepcopy(subject_promise_temporal.field)

    if subject_supplier_id and target_milestone_kind in _SUPPORTED_TARGETS and decision.field.get("state") == "present":
        try:
            from .risk import derive_supplier_load_exposure

            subject_load = derive_supplier_load_exposure(
                lineage,
                subject_id=subject_id,
                subject_supplier_id=subject_supplier_id,
                decision_cutoff=decision,
                target_milestone_kind=target_milestone_kind,
                duration_basis=duration_basis,
                trigger_mode=trigger_mode,
            )
        except (TypeError, ValueError, KeyError):
            subject_load = {
                "state": "unresolved",
                "eligibility_codes": ["LOAD_SNAPSHOT_UNRESOLVABLE"],
            }
        subject_codes.extend(
            str(code)
            for code in subject_load.get("eligibility_codes", [])
            if isinstance(code, str)
        )

    post_trim_rows = [
        {
            "id": line_id,
            "exposure": bool(
                records[line_id].get("exposure_by_variant", {})
                .get("primary", {})
                .get("high_load_exposure")
            ),
            "supplier_id": records[line_id].get("supplier_id"),
            "inputs": records[line_id].get("inputs", {}),
        }
        for line_id in primary_variant["s9_ids"]
    ]
    subject_propensity_value = (
        subject_propensity.get("value")
        if isinstance(subject_propensity, Mapping)
        and subject_propensity.get("state") == "present"
        else subject_propensity
    )
    subject_propensity_available = _finite_number(subject_propensity_value)
    if primary_variant["state"] == "eligible" and not subject_propensity_available:
        subject_codes.append("SUBJECT_PROPENSITY_UNAVAILABLE")
    elif primary_variant["state"] != "eligible":
        subject_codes.append("COHORT_GATE_FAILED")
    elif subject_propensity_available and not (
        _COMMON_SUPPORT_LOWER
        <= float(subject_propensity_value)
        <= _COMMON_SUPPORT_UPPER
    ):
        subject_codes.append("SUBJECT_OVERLAP_INSUFFICIENT")
    elif subject_propensity_available and post_trim_rows:
        distribution = evaluate_subject_distribution_support(subject_input_fields, post_trim_rows)
        subject_codes.extend(
            str(code) for code in distribution.get("eligibility_codes", []) if isinstance(code, str)
        )
    else:
        distribution = {
            "state": "unavailable",
            "eligibility_codes": ["SUBJECT_DISTRIBUTION_UNSUPPORTED"],
            "reason_code": "SUBJECT_DISTRIBUTION_UNSUPPORTED",
            "reason": _reason_details("SUBJECT_DISTRIBUTION_UNSUPPORTED")[0],
            "next_step": _reason_details("SUBJECT_DISTRIBUTION_UNSUPPORTED")[1],
        }
        subject_codes.extend(["SUBJECT_DISTRIBUTION_UNSUPPORTED"])

    subject_codes = _ordered_unique(subject_codes)
    subject_reason_code = subject_codes[0] if subject_codes else None
    subject_reason, subject_next_step = _reason_details(subject_reason_code)
    subject_state = "eligible" if not subject_codes else (
        "ineligible"
        if any(code in {"SUBJECT_OVERLAP_INSUFFICIENT", "SUBJECT_DISTRIBUTION_UNSUPPORTED"} for code in subject_codes)
        else "unavailable"
    )
    subject_output: dict[str, Any] = {
        "state": subject_state,
        "inputs": subject_input_fields,
        "eligibility_codes": subject_codes,
        "reason_code": subject_reason_code,
        "reason": subject_reason,
        "next_step": subject_next_step,
        "promise": {
            "state": subject_promise_field.get("state", "unresolved"),
            "role": "SUBJECT_LINE",
            "field": subject_promise_field,
            "preview_only": trigger_mode == "proactive",
        },
        "propensity": {
            "state": "present" if subject_propensity_available else "unavailable",
            "value": float(subject_propensity_value) if subject_propensity_available else None,
            "support_interval": {
                "lower": _COMMON_SUPPORT_LOWER,
                "upper": _COMMON_SUPPORT_UPPER,
                "inclusive": True,
            },
        },
        "load": subject_load,
    }
    if trigger_mode == "reactive":
        subject_output["subject_id"] = subject_id
    else:
        subject_output["subject_digest"] = subject_id
    if "distribution" in locals():
        subject_output["distribution_support"] = distribution

    cohort_reason_codes = _ordered_unique(
        code
        for code in primary_variant.get("eligibility_codes", [])
        if isinstance(code, str)
    )
    cohort_eligible = primary_variant["state"] == "eligible"
    subject_eligible = subject_state == "eligible"
    for variant in built_variants.values():
        variant["estimator_input"] = (
            _variant_input(
                variant["variant_id"],
                variant["s9_ids"],
                records,
                trigger_mode=trigger_mode,
            )
            if variant["state"] == "eligible"
            else None
        )

    top_codes = _ordered_unique([*cohort_reason_codes, *subject_codes])
    top_reason_code = top_codes[0] if top_codes else None
    top_reason, top_next_step = _reason_details(top_reason_code)
    estimator_input = primary_variant.get("estimator_input") if cohort_eligible else None
    subject_input = (
        {
            "schema_version": "pre-estimation-subject-input.v1",
            "state": "eligible",
            "adjustment_inputs": deepcopy(subject_input_fields),
            "propensity": deepcopy(subject_output["propensity"]),
            "load": deepcopy(subject_load),
            "subject_identity": subject_id if trigger_mode == "reactive" else None,
        }
        if subject_eligible
        else None
    )
    result = {
        "schema_version": "pre-estimation-eligibility.v1",
        "state": (
            "eligible"
            if estimator_input is not None and subject_eligible
            else "scientifically_unavailable"
        ),
        "scope": (
            "ELIGIBLE_FOR_ESTIMATION"
            if estimator_input is not None and subject_eligible
            else "SUBJECT_INELIGIBLE"
            if cohort_eligible and not subject_eligible
            else "COHORT_INELIGIBLE"
        ),
        "trigger_mode": trigger_mode,
        "cutoff_source": (
            "proactive_decision"
            if trigger_mode == "proactive"
            else "canonical_commitment"
        ),
        "subject_id": subject_id if trigger_mode == "reactive" else None,
        "subject_supplier_id": subject_supplier_id if trigger_mode == "reactive" else None,
        "decision_cutoff": _cutoff_field(decision),
        "observation_cutoff": _cutoff_field(observation),
        "target_milestone_kind": target_milestone_kind,
        "canonical_slippage_duration_basis": duration_basis,
        "follow_up_horizon_days": follow_up_horizon_days,
        "adjustment_set": {
            "schema_version": "adjustment-set.v1",
            "fields": list(ADJUSTMENT_SET_FIELDS),
            "missingness_encoding": {
                "missing": "explicit_category",
                "not_applicable": "explicit_category",
            },
            "source_role": "pre_decision_canonical_or_proactive_input",
        },
        "source_semantics": source,
        "selectors": {
            "history_lookback": {
                "selector_version": "history-lookback.v1",
                "selected_count": len(history_selector_ids),
                "selected_identity_hash": _identity_hash(history_selector_ids),
                "known_at_upper": _cutoff_field(observation),
            },
            "estimator_window": {
                "selector_version": "estimator-window.v1",
                "selected_count": len(estimator_selector_ids),
                "selected_identity_hash": _identity_hash(estimator_selector_ids),
                "known_at_upper": _cutoff_field(observation),
                "subject_removed_before_denominators": trigger_mode == "reactive",
            },
        },
        "line_eligibility": {},
        "stage_order": list(STAGE_ORDER),
        "stages": stages,
        "variants": {},
        "subject": subject_output,
        "eligibility_codes": top_codes,
        "reason_code": top_reason_code,
        "reason": top_reason,
        "next_step": top_next_step,
        "cohort": {
            "state": "eligible" if cohort_eligible else "ineligible",
            "primary_variant": "primary",
            "reason_code": primary_variant.get("reason_code"),
            "reason": primary_variant.get("reason"),
            "next_step": primary_variant.get("next_step"),
            "gate_order": [gate.get("gate") for gate in primary_variant.get("gates", [])],
        },
        "estimator_input": estimator_input,
        "subject_input": subject_input,
        "sensitivity_inputs": {},
    }
    for line_id in h0_ids:
        codes = _ordered_unique(line_codes.get(line_id, []))
        line_reason_code = codes[0] if codes else None
        line_reason, line_next_step = _reason_details(line_reason_code)
        item = {
            "state": "eligible" if not codes else "ineligible",
            "eligibility_codes": codes,
            "reason_code": line_reason_code,
            "reason": line_reason,
            "next_step": line_next_step,
            "lineage_refs": records[line_id].get("lineage_refs", []),
        }
        if trigger_mode == "reactive":
            result["line_eligibility"][line_id] = item
        else:
            result["line_eligibility"].setdefault("items", []).append(
                {
                    "identity_hash": _identity_hash([line_id]),
                    **item,
                }
            )
    if trigger_mode == "proactive":
        result["line_eligibility"].update(
            {
                "selected_count": len(h0_ids),
                "selected_identity_hash": _identity_hash(h0_ids),
            }
        )
    for variant_id, variant in built_variants.items():
        public_variant = {
            key: value
            for key, value in variant.items()
            if key
            not in {
                "records",
                "s2_warmed_ids",
                "s2_snapshot_ids",
                "s3_ids",
                "s4_ids",
                "s5_ids",
                "s6_ids",
                "s7_ids",
                "s8_ids",
                "s9_ids",
            }
        }
        for key in (
            "s2_warmed_ids",
            "s2_snapshot_ids",
            "s3_ids",
            "s4_ids",
            "s5_ids",
            "s6_ids",
            "s7_ids",
            "s8_ids",
            "s9_ids",
        ):
            public_variant[f"{key}_count"] = len(variant[key])
            public_variant[f"{key}_identity_hash"] = _identity_hash(variant[key])
            if trigger_mode == "reactive":
                public_variant[key] = sorted(variant[key])
        result["variants"][variant_id] = public_variant
        if variant_id != "primary" and variant.get("estimator_input") is not None:
            result["sensitivity_inputs"][variant_id] = variant["estimator_input"]
    return _sanitize_proactive(result) if trigger_mode == "proactive" else result
