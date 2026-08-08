from __future__ import annotations

import pytest

from backend.app.diagnostics import evaluate_primary_interval
from backend.app.validity import (
    ValidityIntegrityError,
    derive_evidence_verdict,
    evaluate_comparison_triangulation,
    evaluate_cross_form_direction,
    evaluate_complete_validity,
    evaluate_repeat_stability,
    evaluate_robustness_grade,
    evaluate_specification_stability,
    render_evidence_verdict,
)


IDENTITY = {
    "analysis_run_id": "analysis-run-00000000-0000-4000-8000-000000000030",
    "bundle_manifest_hash": "sha256:" + "a" * 64,
    "evidence_refs": ["engine_result:primary"],
    "input_refs": ["engine_result:primary"],
}


def _effect(
    estimate: float,
    standard_error: float = 0.25,
    lower: float | None = None,
    upper: float | None = None,
) -> dict[str, object]:
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "ci_lower": estimate - 1.96 * standard_error if lower is None else lower,
        "ci_upper": estimate + 1.96 * standard_error if upper is None else upper,
        "ci_level": 0.95,
        "unit": "days",
        "duration_basis": "CALENDAR_DAY",
    }


def test_specification_stability_uses_positive_direction_and_compatibility_boundary() -> None:
    result = evaluate_specification_stability(
        _effect(1.0, standard_error=1.0),
        {
            "sensitivity_stricter_atte_slippage": _effect(1.0, standard_error=1.0),
            "sensitivity_short_history_atte_slippage": _effect(1.0, standard_error=1.0),
            "sensitivity_long_history_atte_slippage": _effect(1.0, standard_error=1.0),
        },
        **IDENTITY,
    )

    assert result["status"] == "PASS"
    assert result["trigger_codes"] == []
    assert result["observed"]["variants"][0]["compatibility_z"] == 0.0

    reversed_result = evaluate_specification_stability(
        _effect(1.0),
        {
            "sensitivity_stricter_atte_slippage": _effect(0.0),
            "sensitivity_short_history_atte_slippage": _effect(1.0),
            "sensitivity_long_history_atte_slippage": _effect(1.0),
        },
        **IDENTITY,
    )
    assert reversed_result["status"] == "FAIL"
    assert reversed_result["verdict_effect"] == "VETO"
    assert reversed_result["trigger_codes"] == ["SPECIFICATION_DIRECTION_REVERSED"]


def test_cross_form_and_comparison_policies_keep_fragility_distinct_from_veto() -> None:
    cross_form = evaluate_cross_form_direction(
        {
            "sensitivity_late_risk_atte": _effect(0.2, lower=0.1, upper=0.3),
            "sensitivity_continuous_load_slope": _effect(0.1, lower=-0.1, upper=0.3),
        },
        **IDENTITY,
    )
    assert cross_form["status"] == "FAIL"
    assert cross_form["verdict_effect"] == "FRAGILITY"
    assert cross_form["trigger_codes"] == ["CROSS_FORM_INTERVAL_INCLUDES_NULL"]

    comparison = evaluate_comparison_triangulation(
        {
            "covariate_ols": _effect(0.2),
            "normalized_ipw_atte": _effect(-0.1),
            "supplier_fe_ols": _effect(0.3),
        },
        primary_effect=_effect(1.0),
        **IDENTITY,
    )
    assert comparison["status"] == "FAIL"
    assert comparison["verdict_effect"] == "FRAGILITY"
    assert comparison["trigger_codes"] == ["COMPARISON_DIRECTION_MIXED"]


def test_robustness_grade_uses_more_adverse_even_median_and_is_separate_record() -> None:
    grade = evaluate_robustness_grade(
        _effect(1.0),
        [
            {"group_ref": "material_class", "adjusted_ci_lower": 0.2},
            {"group_ref": "supplier_history", "adjusted_ci_lower": -0.4},
            {"group_ref": "seasonality", "adjusted_ci_lower": 0.1},
            {"group_ref": "order_size", "adjusted_ci_lower": 0.3},
        ],
        **IDENTITY,
    )

    assert grade["grade"] == "MODERATE"
    assert grade["strongest_group_ref"] == "supplier_history"
    assert grade["median_group_ref"] == "seasonality"
    assert grade["schema_version"] == "robustness-grade.v1"
    assert grade["content_hash"].startswith("sha256:")


def test_verdict_precedence_exposes_only_allowed_effect_and_closed_language() -> None:
    primary_effect = _effect(1.5, standard_error=0.1, lower=1.2, upper=1.8)
    diagnostics = [
        evaluate_primary_interval(primary_effect, **IDENTITY),
        evaluate_specification_stability(
            primary_effect,
            {
                "sensitivity_stricter_atte_slippage": _effect(0.0),
                "sensitivity_short_history_atte_slippage": _effect(1.5),
                "sensitivity_long_history_atte_slippage": _effect(1.5),
            },
            **IDENTITY,
        ),
        evaluate_repeat_stability(
            {
                "repeat_1": _effect(1.5, standard_error=0.1),
                "repeat_2": _effect(2.5, standard_error=0.1),
            },
            **IDENTITY,
        ),
    ]
    verdict = derive_evidence_verdict(
        {
            "status": "estimated",
            "primary_effect": primary_effect,
            "effect_result_ref": "engine_result:primary",
        },
        diagnostics,
        intended_role="semi_synthetic_hero",
        scope="population",
        **IDENTITY,
    )

    assert verdict is not None
    assert verdict["verdict_code"] == "ASSOCIATION_ONLY"
    assert verdict["effect_display"] == "ADJUSTED_ASSOCIATION"
    assert verdict["decision_support_evaluation_permitted"] is False
    assert verdict["trigger_codes"] == [
        "SPECIFICATION_DIRECTION_REVERSED",
        "REPEAT_MAGNITUDE_DIVERGENT",
    ]
    rendered = render_evidence_verdict(verdict)
    assert "causal interpretation is not supported" in rendered["language"]
    assert rendered["next_step"]


def test_verdict_rejects_execution_failure_and_basis_mismatch() -> None:
    assert (
        derive_evidence_verdict(
            {"status": "failed"},
            [],
            intended_role="semi_synthetic_hero",
            scope="population",
            **IDENTITY,
        )
        is None
    )

    with pytest.raises(ValidityIntegrityError):
        derive_evidence_verdict(
            {
                "status": "estimated",
                "primary_effect": _effect(1.0),
                "effect_result_ref": "engine_result:primary",
            },
            [evaluate_primary_interval(_effect(1.0), **IDENTITY)],
            intended_role="semi_synthetic_hero",
            scope="population",
            canonical_slippage_duration_basis="ELAPSED_86400_SECOND_DAY",
            **IDENTITY,
        )


def test_population_verdict_handles_scientific_abstention_and_out_of_domain_ceiling() -> None:
    abstained = derive_evidence_verdict(
        {"status": "abstained", "primary_effect": {"status": "abstained"}},
        [],
        intended_role="semi_synthetic_hero",
        scope="population",
        **IDENTITY,
    )
    assert abstained is not None
    assert abstained["verdict_code"] == "INSUFFICIENT"
    assert abstained["insufficient_evidence_reason_class"] == "NOT_ESTIMABLE"
    assert abstained["effect_display"] == "NONE"
    assert abstained["effect"] is None

    effect = _effect(1.5, standard_error=0.1, lower=1.2, upper=1.8)
    validation = derive_evidence_verdict(
        {
            "status": "estimated",
            "primary_effect": effect,
            "effect_result_ref": "engine_result:primary",
            "dataset_display_name": "Olist validation",
        },
        [evaluate_primary_interval(effect, **IDENTITY)],
        intended_role="out_of_domain_validation",
        scope="population",
        **IDENTITY,
    )
    assert validation is not None
    assert validation["verdict_code"] == "SUPPORTED_UNDER_ASSUMPTIONS"
    assert validation["subject_application_role_permitted"] is False
    assert validation["decision_support_evaluation_permitted"] is False
    assert render_evidence_verdict(validation)["language"].startswith(
        "Out-of-domain validation only"
    )


def test_population_verdict_keeps_inconclusive_and_fragile_states_distinct() -> None:
    inconclusive_effect = _effect(0.4, standard_error=0.1, lower=-0.1, upper=0.9)
    insufficient = derive_evidence_verdict(
        {
            "status": "estimated",
            "primary_effect": inconclusive_effect,
            "effect_result_ref": "engine_result:primary",
        },
        [evaluate_primary_interval(inconclusive_effect, **IDENTITY)],
        intended_role="semi_synthetic_hero",
        scope="population",
        **IDENTITY,
    )
    assert insufficient is not None
    assert insufficient["verdict_code"] == "INSUFFICIENT"
    assert insufficient["effect_display"] == "INCONCLUSIVE_ESTIMATE"
    assert "inconclusive" in render_evidence_verdict(insufficient)["language"]

    primary = _effect(1.0, standard_error=0.1, lower=0.8, upper=1.2)
    fragile = evaluate_specification_stability(
        primary,
        {
            "sensitivity_stricter_atte_slippage": _effect(3.0, standard_error=0.1),
            "sensitivity_short_history_atte_slippage": primary,
            "sensitivity_long_history_atte_slippage": primary,
        },
        **IDENTITY,
    )
    tentative = derive_evidence_verdict(
        {
            "status": "estimated",
            "primary_effect": primary,
            "effect_result_ref": "engine_result:primary",
        },
        [evaluate_primary_interval(primary, **IDENTITY), fragile],
        intended_role="semi_synthetic_hero",
        scope="population",
        **IDENTITY,
    )
    assert tentative is not None
    assert tentative["verdict_code"] == "TENTATIVE"
    assert tentative["effect_display"] == "NONE"
    assert tentative["effect"] is None


def test_complete_validity_composes_the_new_diagnostics_and_verdict() -> None:
    effect = _effect(1.5, standard_error=0.1, lower=1.2, upper=1.8)
    complete = evaluate_complete_validity(
        base_diagnostics=[evaluate_primary_interval(effect, **IDENTITY)],
        primary_effect=effect,
        specification_variants={
            "sensitivity_stricter_atte_slippage": effect,
            "sensitivity_short_history_atte_slippage": effect,
            "sensitivity_long_history_atte_slippage": effect,
        },
        cross_form_variants={
            "sensitivity_late_risk_atte": {**effect, "estimate": 0.2, "ci_lower": 0.1, "ci_upper": 0.3},
            "sensitivity_continuous_load_slope": {**effect, "estimate": 0.4, "ci_lower": 0.2, "ci_upper": 0.6},
        },
        comparison_results={
            "covariate_ols": effect,
            "normalized_ipw_atte": effect,
            "supplier_fe_ols": effect,
        },
        benchmark_groups=[{"group_ref": "supplier_history", "adjusted_ci_lower": 0.2}],
        repeat_results={"repeat_1": effect, "repeat_2": effect},
        engine_result={
            "status": "estimated",
            "primary_effect": effect,
            "effect_result_ref": "engine_result:primary",
        },
        intended_role="semi_synthetic_hero",
        **IDENTITY,
    )

    assert len(complete["diagnostics"]) == 6
    assert complete["robustness_grade"]["grade"] == "STRONG"
    assert complete["evidence_verdict"]["verdict_code"] == "SUPPORTED_UNDER_ASSUMPTIONS"
