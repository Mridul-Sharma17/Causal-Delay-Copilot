from __future__ import annotations

import pytest

from backend.app.diagnostics import (
    COVARIATE_BALANCE_DIAGNOSTIC_ID,
    DiagnosticIntegrityError,
    INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
    OVERLAP_DIAGNOSTIC_ID,
    PRIMARY_INTERVAL_DIAGNOSTIC_ID,
    evaluate_core_diagnostics,
    evaluate_covariate_balance,
    evaluate_inherited_eligibility,
    evaluate_overlap,
    evaluate_primary_interval,
    publish_diagnostic_results,
    verify_diagnostic_result,
)


IDENTITY = {
    "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000028",
    "bundle_manifest_hash": "sha256:" + "a" * 64,
    "evidence_refs": ["engine_result:primary", "feature_matrix:primary"],
}


def test_positive_primary_interval_is_a_hashed_pass_result() -> None:
    result = evaluate_primary_interval(
        {"estimate": 1.5, "ci_lower": 0.2, "ci_upper": 2.8, "ci_level": 0.95},
        **IDENTITY,
    )

    assert result["diagnostic_id"] == PRIMARY_INTERVAL_DIAGNOSTIC_ID
    assert result["status"] == "PASS"
    assert result["verdict_effect"] == "NONE"
    assert result["trigger_codes"] == []
    assert result["analysis_run_id"] == IDENTITY["analysis_run_id"]
    assert result["bundle_manifest_hash"] == IDENTITY["bundle_manifest_hash"]
    assert result["content_hash"].startswith("sha256:")
    assert result["diagnostic_identity"].startswith("sha256:")


def test_primary_interval_zero_endpoint_and_opposite_direction_fail_distinctly() -> None:
    includes_null = evaluate_primary_interval(
        {"estimate": 0.4, "ci_lower": 0.0, "ci_upper": 0.8},
        **IDENTITY,
    )
    opposite = evaluate_primary_interval(
        {"estimate": -0.4, "ci_lower": -0.8, "ci_upper": -0.1},
        **IDENTITY,
    )

    assert includes_null["status"] == "FAIL"
    assert includes_null["verdict_effect"] == "INSUFFICIENT"
    assert includes_null["trigger_codes"] == ["PRIMARY_INTERVAL_INCLUDES_NULL"]
    assert opposite["status"] == "FAIL"
    assert opposite["trigger_codes"] == ["PRIMARY_EFFECT_OPPOSITE_DIRECTION"]


def test_atte_balance_uses_normalized_unexposed_weights_and_inclusive_boundary() -> None:
    rows = [
        {"id": "e-1", "exposure": True, "propensity": 0.5, "features": {"x": 0.0}},
        {"id": "e-2", "exposure": True, "propensity": 0.5, "features": {"x": 0.0}},
        {"id": "u-1", "exposure": False, "propensity": 0.5, "features": {"x": 0.0}},
        {"id": "u-2", "exposure": False, "propensity": 0.05, "features": {"x": 1.0}},
    ]

    result = evaluate_covariate_balance(rows, feature_order=["x"], **IDENTITY)

    assert result["diagnostic_id"] == COVARIATE_BALANCE_DIAGNOSTIC_ID
    assert result["status"] == "PASS"
    assert result["threshold"]["absolute_weighted_smd_max"] == 0.10
    assert result["observed"]["unexposed_weight_sum"] == 2.0
    assert result["observed"]["maximum_absolute_weighted_smd"] == 0.10
    assert result["observed"]["offending_features"] == []


def test_atte_balance_encodes_zero_pooled_variance_as_a_hashed_failure() -> None:
    rows = [
        {"exposure": True, "propensity": 0.5, "features": {"x": 0.0}},
        {"exposure": True, "propensity": 0.5, "features": {"x": 0.0}},
        {"exposure": False, "propensity": 0.5, "features": {"x": 1.0}},
        {"exposure": False, "propensity": 0.5, "features": {"x": 1.0}},
    ]

    result = evaluate_covariate_balance(rows, feature_order=["x"], **IDENTITY)

    assert result["status"] == "FAIL"
    assert result["verdict_effect"] == "VETO"
    assert result["observed"]["features"][0]["absolute_weighted_smd"] == {
        "state": "positive_infinity"
    }
    assert result["content_hash"].startswith("sha256:")


def test_diagnostic_hashes_bind_reason_and_result() -> None:
    result = evaluate_primary_interval(
        {"estimate": 1.5, "ci_lower": 0.2, "ci_upper": 2.8},
        **IDENTITY,
    )

    tampered = {**result, "reason": "changed"}
    with pytest.raises(DiagnosticIntegrityError):
        verify_diagnostic_result(
            tampered,
            analysis_run_id=IDENTITY["analysis_run_id"],
            bundle_manifest_hash=IDENTITY["bundle_manifest_hash"],
        )


def test_overlap_keeps_common_support_endpoints_and_reports_trim_failure() -> None:
    supported = evaluate_overlap(
        {
            "schema_version": "overlap-diagnostic-input.v1",
            "state": "supported",
            "support_interval": {"lower": 0.10, "upper": 0.90, "inclusive": True},
            "scored_count": 500,
            "retained_count": 500,
            "trimmed_count": 0,
            "eligibility_codes": [],
        },
        **IDENTITY,
    )
    unsupported = evaluate_overlap(
        {
            "schema_version": "overlap-diagnostic-input.v1",
            "state": "unsupported",
            "support_interval": {"lower": 0.10, "upper": 0.90, "inclusive": True},
            "scored_count": 500,
            "retained_count": 390,
            "trimmed_count": 110,
            "eligibility_codes": ["OVERLAP_COHORT_INSUFFICIENT"],
        },
        **IDENTITY,
    )

    assert supported["diagnostic_id"] == OVERLAP_DIAGNOSTIC_ID
    assert supported["status"] == "PASS"
    assert supported["threshold"]["lower"] == 0.10
    assert supported["threshold"]["upper"] == 0.90
    assert supported["threshold"]["inclusive"] is True
    assert unsupported["status"] == "FAIL"
    assert unsupported["verdict_effect"] == "INSUFFICIENT"
    assert unsupported["trigger_codes"] == ["OVERLAP_COHORT_INSUFFICIENT"]


def test_overlap_preserves_a_verified_stage_short_circuit() -> None:
    result = evaluate_overlap(
        {
            "state": "scientifically_unavailable",
            "status": "not_run",
            "overlap": {
                "state": "not_run",
                "eligibility_codes": ["PRECEDING_ELIGIBILITY_GATE_FAILED"],
                "reason_code": "PRECEDING_ELIGIBILITY_GATE_FAILED",
            },
        },
        **IDENTITY,
    )

    assert result["status"] == "NOT_RUN"
    assert result["upstream_trigger"] == "PRECEDING_ELIGIBILITY_GATE_FAILED"


def test_inherited_population_eligibility_preserves_registry_order_and_scope() -> None:
    result = evaluate_inherited_eligibility(
        {
            "schema_version": "pre-estimation-eligibility.v1",
            "state": "scientifically_unavailable",
            "eligibility_codes": [
                "OVERLAP_COHORT_INSUFFICIENT",
                "SOURCE_SEMANTICS_INELIGIBLE",
            ],
        },
        **IDENTITY,
    )

    assert result["diagnostic_id"] == INHERITED_ELIGIBILITY_DIAGNOSTIC_ID
    assert result["status"] == "FAIL"
    assert result["scope"] == "population"
    assert result["verdict_effect"] == "INSUFFICIENT"
    assert result["trigger_codes"] == [
        "SOURCE_SEMANTICS_INELIGIBLE",
        "OVERLAP_COHORT_INSUFFICIENT",
    ]


def test_core_diagnostics_short_circuits_post_estimation_checks_after_inherited_abstention() -> None:
    results = evaluate_core_diagnostics(
        engine_result={"status": "abstained"},
        eligibility={
            "state": "scientifically_unavailable",
            "eligibility_codes": ["COHORT_SUPPORT_INSUFFICIENT"],
        },
        **IDENTITY,
    )

    by_id = {item["diagnostic_id"]: item for item in results}
    assert set(by_id) == {
        PRIMARY_INTERVAL_DIAGNOSTIC_ID,
        COVARIATE_BALANCE_DIAGNOSTIC_ID,
        OVERLAP_DIAGNOSTIC_ID,
        INHERITED_ELIGIBILITY_DIAGNOSTIC_ID,
    }
    assert by_id[INHERITED_ELIGIBILITY_DIAGNOSTIC_ID]["status"] == "FAIL"
    assert by_id[PRIMARY_INTERVAL_DIAGNOSTIC_ID]["status"] == "NOT_RUN"
    assert by_id[COVARIATE_BALANCE_DIAGNOSTIC_ID]["status"] == "NOT_RUN"


def test_reference_payload_publishes_four_unavailable_immutable_results_when_details_are_absent() -> None:
    payload = {"schema_version": "diagnostic_artifacts.v1"}

    published = publish_diagnostic_results(
        payload,
        analysis_run_id=IDENTITY["analysis_run_id"],
        bundle_manifest_hash=IDENTITY["bundle_manifest_hash"],
        evidence_refs=IDENTITY["evidence_refs"],
    )

    assert len(published) == 4
    assert all(item["status"] == "UNAVAILABLE" for item in published)
    assert all(item["content_hash"].startswith("sha256:") for item in published)
