from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import shutil

import pytest

from backend.app.evaluation import (
    CLAIM_STATES,
    CORE_SCENARIO_IDS,
    EvaluationIntegrityError,
    POLICY_IDS,
    build_frozen_evaluation_manifest,
    evaluate_evaluation_replicate,
    evaluate_policy_replicate,
    generate_evaluation_replicate,
    render_evidence_pack_summary,
    run_scientific_evaluation,
    verify_evidence_pack,
    verify_evaluation_manifest,
    write_evidence_pack,
)
from backend.app.canonical import sha256


def test_frozen_evaluation_manifest_is_closed_and_content_addressed() -> None:
    manifest = build_frozen_evaluation_manifest()

    assert manifest["schema_version"] == "scientific-evaluation-manifest.v1"
    assert manifest["base_dgp"]["line_count"] == 5_000
    assert manifest["base_dgp"]["supplier_count"] == 100
    assert manifest["repetitions"] == {
        "seed_policy_id": "sha256-coordinate-seeds",
        "seed_policy_version": "v1",
        "seed_start": 160016,
        "seed_count": 100,
        "paired_by_seed": True,
    }
    assert tuple(item["scenario_id"] for item in manifest["scenarios"]) == CORE_SCENARIO_IDS
    assert tuple(item["policy_id"] for item in manifest["policies"]) == POLICY_IDS
    assert manifest["claim_states"] == list(CLAIM_STATES)
    assert manifest["content_hash"].startswith("sha256:")
    assert manifest["evaluation_estimator"]["cluster_key"] == "supplier_id"
    assert verify_evaluation_manifest(manifest)["state"] == "ACCEPTED"


def test_manifest_tampering_is_invalid_and_does_not_repair_the_input() -> None:
    manifest = build_frozen_evaluation_manifest()
    tampered = deepcopy(manifest)
    tampered["base_dgp"]["line_count"] = 4_999

    report = verify_evaluation_manifest(tampered)

    assert report["state"] == "INVALID"
    assert report["reason_code"] == "EVALUATION_MANIFEST_HASH_MISMATCH"
    assert tampered["base_dgp"]["line_count"] == 4_999


def test_rehashed_manifest_tampering_is_not_accepted_as_the_frozen_campaign() -> None:
    manifest = build_frozen_evaluation_manifest()
    tampered = deepcopy(manifest)
    tampered["base_dgp"]["supplier_count"] = 99
    tampered["content_hash"] = sha256(
        {key: value for key, value in tampered.items() if key != "content_hash"}
    )

    report = verify_evaluation_manifest(tampered)

    assert report["state"] == "INVALID"
    assert report["reason_code"] == "EVALUATION_MANIFEST_NOT_CANONICAL"


def test_malformed_manifest_returns_typed_invalid_state() -> None:
    manifest = build_frozen_evaluation_manifest()
    manifest["base_dgp"]["malformed_number"] = math.nan

    report = verify_evaluation_manifest(manifest)

    assert report["state"] == "INVALID"
    assert report["reason_code"] == "EVALUATION_MANIFEST_SCHEMA_UNSUPPORTED"


def test_replicate_preserves_public_rows_and_separates_evaluator_truth() -> None:
    manifest = build_frozen_evaluation_manifest()

    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160016,
    )

    observations = replicate["observations"]
    truth = replicate["evaluator_only_truth"]
    assert len(observations) == 5_000
    assert len(truth["potential_outcomes"]) == 5_000
    assert replicate["observation_summary"] == {
        "line_count": 5_000,
        "supplier_count": 100,
        "exposed_count": 1_350,
        "unexposed_count": 3_650,
        "mixed_arm_supplier_count": 100,
        "exposure_share": 0.27,
    }
    assert all("potential_outcome" not in row for row in observations)
    assert all("action_response" not in row for row in observations)
    assert observations[0]["static_load_threshold"] == manifest["base_dgp"][
        "static_load_rule"
    ]["thresholds"][0]
    assert "negative_control_interval" not in observations[0]
    assert "sensitivity_benchmark_lower_bound" not in observations[0]
    assert "concurrent_load" in observations[0]
    assert "supplier_milestone_late" in observations[0]
    assert truth["action_responses"][0]["capacity_material_multiplier"] in {
        0.5,
        1.0,
        1.5,
    }
    generation = manifest["base_dgp"]["generation"]
    expected_risk = 1.0 / (
        1.0
        + math.exp(
            -(
                (
                    observations[0]["load_percentile"]
                    - generation["risk_load_intercept_percentile"]
                )
                / generation["risk_load_scale_percentile"]
                + generation["exposure_risk_lift"]
            )
        )
    )
    assert observations[0]["risk_score"] == round(expected_risk, 10)
    assert truth["namespace"] == "evaluation-only://core-scientific-evaluation/v1"
    assert truth["primary_atte_days"] == 1.5
    assert truth["content_hash"].startswith("sha256:")
    assert replicate["content_hash"].startswith("sha256:")


def test_replicate_evaluation_is_seed_bound_and_bootstrap_replayable() -> None:
    manifest = build_frozen_evaluation_manifest()
    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160016,
    )

    first = evaluate_evaluation_replicate(manifest, replicate)
    second = evaluate_evaluation_replicate(manifest, replicate)

    assert first == second
    assert first["seed"] == 160016
    assert first["estimation"]["numerator"] == 1_350
    assert first["estimation"]["denominator"] == 5_000
    assert first["estimation"]["state"] == "ACCEPTED"
    assert first["estimation"]["estimate_days"] > 0
    assert first["estimation"]["interval"]["lower"] < first["estimation"]["interval"]["upper"]
    assert first["failure_identity"] is None
    assert first["evidence_verdict"]["verdict_code"] == "SUPPORTED_UNDER_ASSUMPTIONS"
    assert first["abstention"]["state"] == "NOT_APPLICABLE"


def test_rehashed_replicate_tampering_is_rejected_by_deterministic_regeneration() -> None:
    manifest = build_frozen_evaluation_manifest()
    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160016,
    )
    tampered = deepcopy(replicate)
    tampered["observations"][0]["risk_score"] = 0.0
    tampered["content_hash"] = sha256(
        {key: value for key, value in tampered.items() if key != "content_hash"}
    )

    result = evaluate_evaluation_replicate(manifest, tampered)

    assert result["state"] == "INVALID"
    assert result["failure_identity"]["code"] == "EVALUATION_REPLICATE_NOT_REGENERATED"


def test_policy_definitions_are_isolated_and_oracle_is_evaluator_only() -> None:
    manifest = build_frozen_evaluation_manifest()
    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="PLANTED_CORRELATE",
        seed=160016,
    )
    estimation = evaluate_evaluation_replicate(manifest, replicate)

    policies = evaluate_policy_replicate(manifest, replicate, estimation)

    assert tuple(policies["policies"]) == POLICY_IDS
    assert policies["policy_input_boundaries"]["ORACLE"]["truth_access"] is True
    for policy_id in POLICY_IDS[:-1]:
        assert policies["policy_input_boundaries"][policy_id]["truth_access"] is False
    assert policies["policies"]["CORRELATION_ONLY"]["action_rate"] == 1.0
    assert policies["policies"]["COPILOT"]["driver_recommendation"] is False


def test_policy_metrics_preserve_denominators_and_manager_authority_boundary() -> None:
    manifest = build_frozen_evaluation_manifest()
    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160016,
    )
    estimation = evaluate_evaluation_replicate(manifest, replicate)

    policies = evaluate_policy_replicate(manifest, replicate, estimation)
    copilot = policies["policies"]["COPILOT"]

    assert copilot["total_subject_count"] == 5_000
    assert copilot["eligible_subject_count"] > 0
    assert copilot["ineligible_subject_count"] == (
        copilot["total_subject_count"] - copilot["eligible_subject_count"]
    )
    assert copilot["monitoring_count"] == (
        copilot["eligible_subject_count"] - copilot["action_count"]
    )
    assert copilot["selection_count"] == copilot["eligible_subject_count"]
    assert copilot["recommendation_count"] == copilot["action_count"]
    assert copilot["authorization_count"] == 0
    assert copilot["authorization_state"] == "NOT_AUTHORIZED"
    assert copilot["policy_utility"] == copilot["realized_net_value"]
    assert copilot["regret_denominator"] == (
        copilot["oracle_net_value"] - copilot["monitoring_net_value"]
    )
    assert copilot["metric_denominators"]["false_action_rate"] == {
        "numerator": copilot["false_action_count"],
        "denominator": copilot["eligible_subject_count"],
        "state": "AVAILABLE",
    }
    assert policies["policy_input_boundaries"]["COPILOT"][
        "selection_truth_access"
    ] is False
    assert policies["policy_input_boundaries"]["ORACLE"][
        "selection_truth_access"
    ] is True


def test_zero_opportunity_preserves_unavailable_regret_denominator() -> None:
    manifest = build_frozen_evaluation_manifest()
    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="NULL_EFFECT",
        seed=160016,
    )
    estimation = evaluate_evaluation_replicate(manifest, replicate)

    policies = evaluate_policy_replicate(manifest, replicate, estimation)
    prediction_only = policies["policies"]["PREDICTION_ONLY"]

    assert prediction_only["regret_denominator"] == 0.0
    assert prediction_only["normalized_regret"] is None
    assert prediction_only["normalized_regret_state"] == "UNAVAILABLE"
    assert prediction_only["metric_denominators"]["normalized_regret"] == {
        "numerator": prediction_only["raw_oracle_regret"],
        "denominator": 0.0,
        "state": "UNAVAILABLE",
    }


def test_campaign_compares_every_policy_on_paired_seed_rows() -> None:
    manifest = build_frozen_evaluation_manifest()

    result = run_scientific_evaluation(
        manifest=manifest,
        scenario_ids=("TRUE_EFFECT", "PLANTED_CORRELATE"),
        seeds=(160016, 160017),
    )

    challenger_ids = (
        "PREDICTION_ONLY",
        "CORRELATION_ONLY",
        "ALWAYS_EXPEDITE",
        "STATIC_LOAD_RULE",
        "ORACLE",
    )
    for scenario in result["scenario_results"].values():
        assert tuple(scenario["paired_policy_comparisons"]) == challenger_ids
        assert all(
            comparison["paired_seed_count"] == 2
            for comparison in scenario["paired_policy_comparisons"].values()
        )
    aggregate = result["scenario_results"]["TRUE_EFFECT"]["aggregate"]
    assert aggregate["policy_metrics"]["COPILOT"]["eligible_subject_denominator"] == (
        2 * 4_338
    )
    assert aggregate["policy_metrics"]["COPILOT"]["state"] == "AVAILABLE"


def test_campaign_keeps_external_scopes_and_unavailable_domain_claims_explicit() -> None:
    manifest = build_frozen_evaluation_manifest()

    result = run_scientific_evaluation(
        manifest=manifest,
        scenario_ids=("TRUE_EFFECT",),
        seeds=(160016,),
    )
    claims = {claim["claim_id"]: claim for claim in result["claims"]}

    assert claims["OLIST_ADAPTER_TRANSPORT_TIMING_VALIDATION"]["state"] == "ACCEPTED"
    assert claims["SCMS_REJECTION_ABSTENTION"]["state"] == "ACCEPTED"
    for claim_id in (
        "CONSTRUCTION_CAUSAL_MAGNITUDE",
        "ACTION_REALISM",
        "MANAGER_COMPREHENSION",
        "PRACTITIONER_DOMAIN_VALIDATION",
    ):
        assert claims[claim_id]["state"] == "UNAVAILABLE"
        assert claims[claim_id]["observed"] is None
        assert claims[claim_id]["evidence_refs"] == []

    boundary = result["synthetic_fixture_boundary"]
    assert boundary["state"] == "TEST_ONLY_NOT_SHIPPED"
    assert boundary["domain_validation_claim"] is False
    assert boundary["shipped_demo_claim"] is False


def test_policy_scoring_rejects_cross_replicate_estimation() -> None:
    manifest = build_frozen_evaluation_manifest()
    first_replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160016,
    )
    second_replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160017,
    )
    estimation = evaluate_evaluation_replicate(manifest, first_replicate)

    try:
        evaluate_policy_replicate(manifest, second_replicate, estimation)
    except ValueError as error:
        assert str(error) == "EVALUATION_ESTIMATION_BINDING_INVALID"
    else:
        raise AssertionError("cross-replicate estimation was accepted")


def test_policy_scoring_rejects_rehashed_truth_tampering() -> None:
    manifest = build_frozen_evaluation_manifest()
    replicate = generate_evaluation_replicate(
        manifest,
        scenario_id="TRUE_EFFECT",
        seed=160016,
    )
    estimation = evaluate_evaluation_replicate(manifest, replicate)
    tampered = deepcopy(replicate)
    tampered["evaluator_only_truth"]["action_responses"][0][
        "direct_action_cost"
    ] = 0.0
    tampered["evaluator_only_truth"]["content_hash"] = sha256(
        {
            key: value
            for key, value in tampered["evaluator_only_truth"].items()
            if key != "content_hash"
        }
    )
    tampered["content_hash"] = sha256(
        {key: value for key, value in tampered.items() if key != "content_hash"}
    )
    tampered_estimation = deepcopy(estimation)
    tampered_estimation["replicate_hash"] = tampered["content_hash"]
    tampered_estimation["content_hash"] = sha256(
        {
            key: value
            for key, value in tampered_estimation.items()
            if key != "content_hash"
        }
    )

    with pytest.raises(ValueError, match="EVALUATION_REPLICATE_NOT_REGENERATED"):
        evaluate_policy_replicate(manifest, tampered, tampered_estimation)


def test_scientific_evaluation_retains_paired_seed_rows_and_typed_claims() -> None:
    manifest = build_frozen_evaluation_manifest()

    first = run_scientific_evaluation(
        manifest=manifest,
        scenario_ids=("TRUE_EFFECT", "PLANTED_CORRELATE"),
        seeds=(160016, 160017),
    )
    second = run_scientific_evaluation(
        manifest=manifest,
        scenario_ids=("TRUE_EFFECT", "PLANTED_CORRELATE"),
        seeds=(160016, 160017),
    )

    assert first == second
    assert first["scope"] == "FOCUSED_SUBSET"
    assert tuple(first["scenarios"]) == ("TRUE_EFFECT", "PLANTED_CORRELATE")
    assert all(
        claim["state"] in CLAIM_STATES for claim in first["claims"]
    )
    for scenario in first["scenario_results"].values():
        assert [row["seed"] for row in scenario["seed_rows"]] == [160016, 160017]
        assert all("failure_identity" in row for row in scenario["seed_rows"])
        assert "paired_policy_comparisons" in scenario
    assert first["reproducibility"]["state"] == "ACCEPTED"
    assert first["integrity"]["state"] == "ACCEPTED"
    assert first["content_hash"].startswith("sha256:")


def test_replay_regenerates_the_public_replicate(monkeypatch) -> None:
    import backend.app.evaluation as evaluation

    manifest = build_frozen_evaluation_manifest()
    original = evaluation.generate_evaluation_replicate
    calls: list[tuple[str, int]] = []

    def count_generation(manifest, *, scenario_id, seed):
        calls.append((scenario_id, seed))
        return original(manifest, scenario_id=scenario_id, seed=seed)

    monkeypatch.setattr(evaluation, "generate_evaluation_replicate", count_generation)
    result = run_scientific_evaluation(
        manifest=manifest,
        scenario_ids=("TRUE_EFFECT",),
        seeds=(160016,),
    )

    assert calls == [("TRUE_EFFECT", 160016), ("TRUE_EFFECT", 160016)]
    assert result["reproducibility"]["state"] == "ACCEPTED"


def test_evidence_pack_is_manifest_last_and_tamper_detectable(tmp_path) -> None:
    pack_root = tmp_path / "scientific-evidence-pack"
    checked_in_pack = (
        Path(__file__).parents[2]
        / "tests"
        / "fixtures"
        / "scientific_evaluation"
        / "v1"
    )
    shutil.copytree(checked_in_pack, pack_root)

    assert (pack_root / "manifest.json").is_file()
    assert verify_evidence_pack(pack_root)["state"] == "ACCEPTED"
    result_path = pack_root / "evaluation-result.json"
    tampered = json.loads(result_path.read_text(encoding="utf-8"))
    tampered["overall_status"] = "CORE_EVALUATION_ACCEPTED"
    result_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert verify_evidence_pack(pack_root)["reason_code"] == "EVIDENCE_PACK_MEMBER_HASH_MISMATCH"


def test_evidence_pack_publication_replays_the_checked_in_typed_result(tmp_path) -> None:
    fixture_root = Path(__file__).parents[2] / "tests" / "fixtures" / "scientific_evaluation" / "v1"
    manifest = json.loads((fixture_root / "evaluation-manifest.json").read_text(encoding="utf-8"))
    result = json.loads((fixture_root / "evaluation-result.json").read_text(encoding="utf-8"))

    publication = write_evidence_pack(
        tmp_path / "published-pack",
        manifest=manifest,
        result=result,
    )

    assert publication["state"] == "ACCEPTED"
    assert publication["member_count"] == 7
    assert verify_evidence_pack(tmp_path / "published-pack")["state"] == "ACCEPTED"


def test_checked_in_scientific_evidence_pack_is_verified() -> None:
    pack_root = Path(__file__).parents[2] / "tests" / "fixtures" / "scientific_evaluation" / "v1"

    report = verify_evidence_pack(pack_root)

    assert report["state"] == "ACCEPTED"


def test_execution_error_preserves_the_seed_as_invalid_evidence(monkeypatch) -> None:
    import backend.app.evaluation as evaluation

    manifest = build_frozen_evaluation_manifest()
    original = evaluation.generate_evaluation_replicate

    def fail_one_seed(manifest, *, scenario_id, seed):
        if seed == 160016:
            raise RuntimeError("simulated evaluator failure")
        return original(manifest, scenario_id=scenario_id, seed=seed)

    monkeypatch.setattr(evaluation, "generate_evaluation_replicate", fail_one_seed)
    result = run_scientific_evaluation(
        manifest=manifest,
        scenario_ids=("TRUE_EFFECT",),
        seeds=(160016, 160017),
    )

    rows = result["scenario_results"]["TRUE_EFFECT"]["seed_rows"]
    assert [row["seed"] for row in rows] == [160016, 160017]
    assert rows[0]["failure_identity"]["code"] == "EVALUATION_EXECUTION_ERROR"
    assert rows[1]["failure_identity"] is None
    assert result["integrity"]["state"] == "INVALID"


def test_evidence_pack_contains_provenance_summary_and_retention_metadata() -> None:
    pack_root = Path(__file__).parents[2] / "tests" / "fixtures" / "scientific_evaluation" / "v1"

    descriptor = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))
    member_paths = {member["path"] for member in descriptor["members"]}

    assert {"provenance.json", "summary.md"}.issubset(member_paths)
    assert descriptor["schema_versions"]["evaluation_manifest"] == (
        "scientific-evaluation-manifest.v1"
    )
    assert descriptor["schema_versions"]["evaluation_result"] == (
        "scientific-evaluation-result.v1"
    )
    assert descriptor["schema_versions"]["policy"] == "scientific-policy-evaluation.v1"
    assert descriptor["provenance"]["source_identity_hash"].startswith("sha256:")
    assert descriptor["provenance"]["environment_identity_hash"].startswith("sha256:")
    assert descriptor["audit_reference"]["schema_version"] == (
        "core-evaluation-audit-reference.v1"
    )
    assert descriptor["retention_pin"]["state"] == "PINNED"
    assert set(descriptor["retention_pin"]["scope"].split(",")) == {
        "manifest.json",
        "evaluation-manifest.json",
        "evaluation-result.json",
        "policy-config.json",
        "runtime-lock.json",
        "provenance.json",
        "summary.md",
        "verification-command.txt",
    }

    summary = (pack_root / "summary.md").read_text(encoding="utf-8")
    assert "CORE_EVALUATION_ACCEPTED" in summary
    assert "UNAVAILABLE" in summary
    assert "| TRUE_EFFECT | 100 | 0 | 1.4729447695 | 1.0 | UNAVAILABLE |" in summary
    assert "| TRUE_EFFECT | 100 | 0 | 1.4729447695 | 1.0 | None |" not in summary
    assert "PRACTITIONER_DOMAIN_VALIDATION" in summary
    assert "Kaya" not in summary
    assert "transferability" not in summary.lower()


def test_human_summary_preserves_nonaccepted_claim_states() -> None:
    pack_root = Path(__file__).parents[2] / "tests" / "fixtures" / "scientific_evaluation" / "v1"
    manifest = json.loads((pack_root / "evaluation-manifest.json").read_text(encoding="utf-8"))
    result = json.loads((pack_root / "evaluation-result.json").read_text(encoding="utf-8"))
    claim = next(item for item in result["claims"] if item["claim_id"] == "TRUE_EFFECT_ESTIMATION_QUALITY")
    claim["state"] = "REJECTED"
    claim["reason_code"] = "TEST_REJECTION_PRESERVED"
    result["overall_status"] = "CORE_EVALUATION_REJECTED"
    result["content_hash"] = sha256(
        {key: value for key, value in result.items() if key != "content_hash"}
    )

    summary = render_evidence_pack_summary(manifest, result)

    assert "| TRUE_EFFECT_ESTIMATION_QUALITY | REJECTED | TEST_REJECTION_PRESERVED |" in summary
    assert "| TRUE_EFFECT_ESTIMATION_QUALITY | ACCEPTED |" not in summary


def test_pack_publication_rejects_rehashed_claim_registry_tampering(tmp_path) -> None:
    pack_root = Path(__file__).parents[2] / "tests" / "fixtures" / "scientific_evaluation" / "v1"
    manifest = json.loads((pack_root / "evaluation-manifest.json").read_text(encoding="utf-8"))
    result = json.loads((pack_root / "evaluation-result.json").read_text(encoding="utf-8"))
    claim = next(
        item
        for item in result["claims"]
        if item["claim_id"] == "PRACTITIONER_DOMAIN_VALIDATION"
    )
    claim["state"] = "ACCEPTED"
    result["content_hash"] = sha256(
        {key: value for key, value in result.items() if key != "content_hash"}
    )

    with pytest.raises(
        EvaluationIntegrityError,
        match="EVIDENCE_PACK_CLAIM_REGISTRY_INVALID",
    ):
        write_evidence_pack(tmp_path / "tampered-pack", manifest=manifest, result=result)
