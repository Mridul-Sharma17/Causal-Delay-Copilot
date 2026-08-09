import hashlib
import json
from pathlib import Path

from backend.app import analysis_runs as analysis_runs_module
from backend.app.analysis_runs import (
    estimate_primary_atte_and_context,
    validate_suite_request,
)


FIXTURE_ROOT = (
    Path(__file__).parents[2] / "tests" / "fixtures" / "causal_engine" / "v1"
)
EXPECTED_FIXTURE_ORDER = (
    "fixture_constant_effect",
    "fixture_atte_differs_from_ate",
    "fixture_continuous_load",
    "fixture_binary_late",
    "fixture_overlap_and_subject",
    "fixture_comparisons",
    "fixture_unsupported_sensitivity",
    "fixture_engine_errors",
)


def test_issue_37_fixture_pack_is_closed_and_snapshot_backed() -> None:
    manifest = json.loads(
        (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    fixtures = manifest["fixtures"]

    assert manifest["fixture_pack_id"] == "core-causal-engine-conformance"
    assert manifest["fixture_pack_version"] == "v2"
    assert [fixture["fixture_id"] for fixture in fixtures] == list(
        EXPECTED_FIXTURE_ORDER
    )
    assert all(fixture["fixture_kind"] == "full_fit" for fixture in fixtures)

    validated_inputs: set[Path] = set()
    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        input_path = FIXTURE_ROOT / fixture["input_paths"][0]
        expected_path = FIXTURE_ROOT / fixture["expected_path"]
        assert fixture["input_sha256"] == "sha256:" + hashlib.sha256(
            input_path.read_bytes()
        ).hexdigest()
        assert fixture["expected_sha256"] == "sha256:" + hashlib.sha256(
            expected_path.read_bytes()
        ).hexdigest()
        input_records = [
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        assert len(input_records) == 1
        suite_request = input_records[0]
        assert suite_request["engine_input_schema_version"] == (
            "causal-engine-suite-request.v2"
        )
        assert suite_request["root_seed"] == 160016
        if input_path not in validated_inputs:
            validate_suite_request(suite_request)
            validated_inputs.add(input_path)
        released_rows = [
            len(variant.get("rows", []))
            for variant in suite_request["variant_inputs"]
            if variant.get("upstream_status") == "released"
        ]
        primary_rows = next(
            variant["rows"]
            for variant in suite_request["variant_inputs"]
            if variant["variant_id"] == "primary"
            and variant.get("upstream_status") == "released"
        )
        supplier_arms: dict[str, set[bool]] = {}
        for row in primary_rows:
            supplier_arms.setdefault(str(row["supplier_id"]), set()).add(
                bool(row["high_load_exposure"])
            )
        assert fixture["row_count"] == 1500
        assert all(count == 1500 for count in released_rows)
        assert fixture["supplier_count"] == 50
        assert len(primary_rows) == fixture["row_count"]
        assert sum(bool(row["high_load_exposure"]) for row in primary_rows) == fixture[
            "exposed_count"
        ]
        assert sum(not bool(row["high_load_exposure"]) for row in primary_rows) == fixture[
            "unexposed_count"
        ]
        assert len(supplier_arms) == fixture["supplier_count"]
        assert sum(len(arms) == 2 for arms in supplier_arms.values()) == fixture[
            "mixed_arm_supplier_count"
        ]
        assert fixture["variant_count"] == len(suite_request["variant_inputs"])
        assert fixture["released_variant_count"] == len(released_rows)
        if fixture["subject"] is not None:
            assert suite_request.get("subject") == fixture["subject"]
            assert suite_request["subject"]["subject_id"] not in {
                str(row["order_line_id"]) for row in primary_rows
            }
        else:
            assert "subject" not in suite_request
        assert expected["fixture_id"] == fixture_id
        assert expected["expected_branch"] == fixture["expected_branch"]
        assert expected["expected_facts"] == fixture["expected_facts"]
        assert fixture["numeric_tolerances"] == {"abs": 1e-10, "rel": 1e-8}


def test_full_fit_snapshot_executes_the_real_closed_suite() -> None:
    input_path = FIXTURE_ROOT / "inputs" / "fixture_full_fit.jsonl"
    request = json.loads(input_path.read_text(encoding="utf-8").splitlines()[0])

    result = estimate_primary_atte_and_context(request)

    assert result["status"] == "estimated"
    assert result["primary_atte"]["estimand_id"] == "primary_atte_slippage"
    assert result["context_ate"]["estimand_id"] == "context_ate_slippage"
    assert set(result["comparison_results"]) == {
        "naive_mean_difference",
        "covariate_ols",
        "normalized_ipw_atte",
        "supplier_fe_ols",
    }
    assert result["sensitivity_results"]["sensitivity_late_risk_atte"]["status"] == (
        "estimated"
    )
    assert result["sensitivity_results"]["sensitivity_continuous_load_slope"][
        "label"
    ] == "linear_average_slope"


def test_declared_engine_error_fixture_executes_its_injected_branch(monkeypatch) -> None:
    manifest = json.loads(
        (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    fixture = next(
        item for item in manifest["fixtures"] if item["fixture_id"] == "fixture_engine_errors"
    )
    input_path = FIXTURE_ROOT / fixture["input_paths"][0]
    request = json.loads(input_path.read_text(encoding="utf-8").splitlines()[0])

    def fail_comparisons(request, nuisances):
        raise analysis_runs_module.EstimatorStageError(
            fixture["injected_fault"]
        )

    monkeypatch.setattr(analysis_runs_module, "_comparison_suite", fail_comparisons)
    result = estimate_primary_atte_and_context(request)

    assert result["status"] == fixture["expected_branch"]
    assert result["reason_code"] == fixture["expected_primary_code"]
    assert "primary_atte" not in result
