from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backend.app.canonical import sha256
from backend.app.decision_support import evaluate_decision_support
from backend.app.settings import DeliveryProfile, RuntimeFingerprint


FIXTURE_ROOT = (
    Path(__file__).parents[2] / "tests" / "fixtures" / "decision_support" / "v1"
)
SYNTHETIC_NAMESPACE = "synthetic:core-decision-support-v1:"
SYNTHETIC_STORAGE_NAMESPACE = "synthetic://core-decision-support/v1"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _record_hash(record: Mapping[str, Any]) -> str:
    content = deepcopy(dict(record))
    content.pop("content_hash", None)
    return sha256(content)


def _records() -> dict[str, Any]:
    manifest = _read_json(FIXTURE_ROOT / "manifest.json")
    return _read_json(FIXTURE_ROOT / str(manifest["records_path"]))


def _cases() -> dict[str, Any]:
    manifest = _read_json(FIXTURE_ROOT / "manifest.json")
    return _read_json(FIXTURE_ROOT / str(manifest["cases_path"]))


def _request(*, dataset_version_id: str, order_line_id: str) -> dict[str, Any]:
    return {
        "investigation_request_id": "synthetic://core-decision-support/v1/request/ordinary-path",
        "schema_version": "investigation-request.v1",
        "trigger_mode": "reactive",
        "dataset_version_id": dataset_version_id,
        "subject": {"order_line_id": order_line_id},
        "decision_cutoff": {"state": "present", "value": "2026-08-01T00:00:00Z"},
        "causal_engine_input": {
            "supplier_load_exposure": {"primary": {"high_load_exposure": True}}
        },
    }


def test_synthetic_fixture_pack_is_explicitly_test_only_and_snapshot_bound() -> None:
    manifest = _read_json(FIXTURE_ROOT / "manifest.json")

    assert manifest["fixture_pack_schema_version"] == (
        "decision-support-conformance-fixtures.v1"
    )
    assert manifest["fixture_pack_id"] == "core-decision-support-conformance"
    assert manifest["fixture_pack_version"] == "v1"
    assert manifest["storage_namespace"] == SYNTHETIC_STORAGE_NAMESPACE
    assert manifest["source_kind"] == "synthetic_conformance"
    assert manifest["intended_role"] == "synthetic_conformance"
    assert manifest["contract_status"] == "SYNTHETIC_CONFORMANCE_ONLY"
    assert set(manifest["delivery_binding"]["profiles"]) == {
        profile.value for profile in DeliveryProfile
    }
    assert {
        RuntimeFingerprint.model_validate(fingerprint).profile.value
        for fingerprint in manifest["delivery_binding"]["runtime_fingerprints"]
    } == {profile.value for profile in DeliveryProfile}
    assert manifest["delivery_binding"]["demo_workspace"]["ownership"] == "NONE"
    assert manifest["delivery_binding"]["demo_workspace"]["selection"] == "PROHIBITED"
    assert manifest["synthetic_disclosure"]["is_synthetic"] is True
    assert manifest["synthetic_disclosure"]["practitioner_validation"] == (
        "NOT_PERFORMED"
    )
    assert manifest["release_metadata"]["release_binding_state"] == (
        "TEST_ONLY_NOT_SHIPPED"
    )
    assert manifest["release_metadata"]["reference_promotion"] == "PROHIBITED"
    assert manifest["release_metadata"]["external_evaluation"] == "PROHIBITED"
    assert manifest["release_metadata"]["release_copy"] == "PROHIBITED"
    assert manifest["presentation"]["test_only"] is True
    assert manifest["presentation"]["display_in_shipped_demo"] is False
    assert "SYNTHETIC" in manifest["labels"]
    assert "TEST_ONLY" in manifest["labels"]

    records_path = FIXTURE_ROOT / str(manifest["records_path"])
    cases_path = FIXTURE_ROOT / str(manifest["cases_path"])
    assert manifest["records_sha256"] == (
        "sha256:" + hashlib.sha256(records_path.read_bytes()).hexdigest()
    )
    assert manifest["cases_sha256"] == (
        "sha256:" + hashlib.sha256(cases_path.read_bytes()).hexdigest()
    )
    assert records_path.is_relative_to(FIXTURE_ROOT)
    assert cases_path.is_relative_to(FIXTURE_ROOT)


def test_synthetic_fixture_pack_contains_approved_records_and_lifecycle_variants() -> (
    None
):
    manifest = _read_json(FIXTURE_ROOT / "manifest.json")
    records = _records()
    cases = _cases()

    assert records["schema_version"] == "synthetic-governed-records.v1"
    assert cases["schema_version"] == "synthetic-decision-support-cases.v1"
    assert records["fixture_pack_id"] == manifest["fixture_pack_id"]
    assert cases["fixture_pack_id"] == manifest["fixture_pack_id"]

    all_records: list[Mapping[str, Any]] = []
    for collection_name in (
        "intervention_libraries",
        "driver_action_links",
        "advisory_rubrics",
        "monitoring_triggers",
        "composite_reviews",
        "lifecycle_variants",
    ):
        collection = records[collection_name]
        assert isinstance(collection, list)
        all_records.extend(collection)

    assert all(record["content_hash"] == _record_hash(record) for record in all_records)
    assert all(
        record["published_at"] == "2026-08-01T00:00:00+00:00"
        and record["contract_status"] == "SYNTHETIC_CONFORMANCE_ONLY"
        and record["delivery_binding"]["demo_workspace"]["selection"] == "PROHIBITED"
        for record in all_records
    )
    record_ids = [str(record["record_id"]) for record in all_records]
    assert len(record_ids) == len(set(record_ids))
    assert all(record_id.startswith(SYNTHETIC_NAMESPACE) for record_id in record_ids)

    library = records["intervention_libraries"][0]
    assert library["state"] == "BUNDLED_CLOSED"
    assert library["lifecycle_status"] == "ACTIVE"
    assert {option["lifecycle_status"] for option in library["options"]} == {"ACTIVE"}
    library_options = library["options"]
    assert all(
        option["content_hash"] == _record_hash(option)
        and option["provenance"]["practitioner_validation"] == "NOT_PERFORMED"
        and option["release_binding"]["state"] == "TEST_ONLY_NOT_SHIPPED"
        for option in library_options
    )

    assert any(
        record["review_status"] == "APPROVED"
        and record["approval_scope"] == "SYNTHETIC_CONFORMANCE_ONLY"
        for record in records["driver_action_links"]
    )
    assert any(
        record["state"] == "APPROVED"
        and record["approval_scope"] == "SYNTHETIC_CONFORMANCE_ONLY"
        for record in records["advisory_rubrics"]
    )
    assert any(
        record["state"] == "APPROVED"
        and record["approval_scope"] == "SYNTHETIC_CONFORMANCE_ONLY"
        for record in records["monitoring_triggers"]
    )
    assert any(
        record["state"] == "APPROVED"
        and record["approval_scope"] == "SYNTHETIC_CONFORMANCE_ONLY"
        for record in records["composite_reviews"]
    )
    assert all(
        link["registry_identifier"] == "supplier-congestion-driver-action-links"
        and link["source_refs"]
        and link["review_evidence_refs"]
        and link["review_date"]
        and link["mechanism_class"]
        for link in records["driver_action_links"]
    )
    assert all(
        rubric["applicability"]
        and rubric["typed_input_declarations"]
        and rubric["rules"]
        and rubric["source_refs"]
        and rubric["review_date"]
        for rubric in records["advisory_rubrics"]
    )
    assert all(
        trigger["registry_identifier"]
        and trigger["observation_registry"]
        and trigger["operator"] in {"LT", "LTE", "EQ", "NEQ", "GTE", "GT", "IN_SET"}
        and trigger["response_code"] == "REQUEST_MANAGER_REVIEW"
        and trigger["source_refs"]
        for trigger in records["monitoring_triggers"]
    )
    assert all(
        len(review["attestations"]) == 4
        and review["criteria_schema_identifier"] == "composite-compatibility-criteria"
        and review["outcome"] == "COMPATIBLE"
        for review in records["composite_reviews"]
    )
    assert {record["lifecycle_state"] for record in records["lifecycle_variants"]} >= {
        "APPROVED",
        "REJECTED",
        "RETIRED",
        "SUPERSEDED",
        "EXPIRED",
    }

    fixture_ids = [str(fixture["fixture_id"]) for fixture in cases["fixtures"]]
    assert fixture_ids == manifest["fixture_ids"]
    assert len(fixture_ids) == len(set(fixture_ids))
    assert all(fixture_id.startswith(SYNTHETIC_NAMESPACE) for fixture_id in fixture_ids)
    assert {fixture["trigger_mode"] for fixture in cases["fixtures"]} == {
        "reactive",
        "proactive",
    }
    assert {fixture["expected_branch"] for fixture in cases["fixtures"]} >= {
        "ACTIVE_APPROVED_REACTIVE",
        "ACTIVE_APPROVED_PROACTIVE",
        "INACTIVE_DRIVER",
        "PERMISSION_DENIED",
        "LIFECYCLE_SUPERSEDED",
        "OPERATIONAL_FACT_EXPIRED",
    }
    assert all(
        fixture["presentation"]["display_in_shipped_demo"] is False
        and fixture["presentation"]["test_only"] is True
        for fixture in cases["fixtures"]
    )
    assert all(
        fixture["provenance"]["practitioner_validation"] == "NOT_PERFORMED"
        and fixture["provenance"]["production_authority"] == "PROHIBITED"
        for fixture in cases["fixtures"]
    )
    record_ids_set = set(record_ids)
    records_by_id = {str(record["record_id"]): record for record in all_records}
    for fixture in cases["fixtures"]:
        assert fixture["content_hash"] == _record_hash(fixture)
        references = fixture["governed_record_refs"]
        assert references["intervention_library"] in record_ids_set
        assert all(
            reference in record_ids_set
            for key in (
                "driver_action_links",
                "advisory_rubrics",
                "monitoring_triggers",
                "composite_reviews",
            )
            for reference in references[key]
        )
        if fixture["expected_branch"] in {
            "ACTIVE_APPROVED_REACTIVE",
            "ACTIVE_APPROVED_PROACTIVE",
            "LIFECYCLE_SUPERSEDED",
            "OPERATIONAL_FACT_EXPIRED",
            "LINK_REJECTED",
        }:
            snapshot = fixture["operational_inputs"]["case_constraint_snapshot"]
            assert snapshot is not None
            assert snapshot["snapshot_id"].startswith(SYNTHETIC_NAMESPACE)
            assert snapshot["content_hash"] == _record_hash(snapshot)
            assert snapshot["constraints_as_of"] >= snapshot["causal_decision_at"]
            assert all(
                fact["source_type"] == "VERIFIED_UPSTREAM_RECORD"
                and fact["known_at"] <= snapshot["constraints_as_of"]
                and fact["source_available_at"] <= snapshot["constraints_as_of"]
                and fact["recorded_at"]
                for fact in snapshot["facts"]
            )
            for fact in snapshot["facts"]:
                if fact["fact_code"] not in {
                    "MONITORING_ESCALATION_TRIGGER_REF",
                    "COMPOSITE_COMPATIBILITY_REVIEW_REF",
                }:
                    continue
                referenced = fact["value"]
                assert referenced["reference"] in records_by_id
                assert (
                    referenced["content_hash"]
                    == records_by_id[referenced["reference"]]["content_hash"]
                )
            composite_fact = next(
                fact
                for fact in snapshot["facts"]
                if fact["fact_code"] == "COMPOSITE_COMPATIBILITY_REVIEW_REF"
            )
            composite = records_by_id[composite_fact["value"]["reference"]]
            if fixture["expected_branch"].startswith("ACTIVE_APPROVED_"):
                expected_digest = sha256(
                    {
                        "snapshot_id": snapshot["snapshot_id"],
                        "subject_identity": snapshot["subject_identity"],
                        "causal_decision_at": snapshot["causal_decision_at"],
                        "constraints_as_of": snapshot["constraints_as_of"],
                        "ordered_snapshot_facts_excluding_COMPOSITE_COMPATIBILITY_REVIEW_REF": [
                            fact
                            for fact in snapshot["facts"]
                            if fact["fact_code"] != "COMPOSITE_COMPATIBILITY_REVIEW_REF"
                        ],
                    }
                )
                assert (
                    composite["composite_compatibility_input_digest"] == expected_digest
                )
        if fixture["trigger_mode"] == "proactive":
            preview = fixture["operational_inputs"]["release_timing_preview"]
            assert preview is not None
            assert preview["content_hash"] == _record_hash(preview)
            assert preview["base_proactive_proposal_identity"][
                "dataset_version_id"
            ].startswith(SYNTHETIC_NAMESPACE)


def test_synthetic_fixture_pack_is_outside_shipped_and_external_evidence_paths() -> (
    None
):
    manifest = _read_json(FIXTURE_ROOT / "manifest.json")
    cases = _cases()

    assert FIXTURE_ROOT.as_posix().endswith("tests/fixtures/decision_support/v1")
    assert not (
        Path(__file__).parents[2] / "backend" / "app" / "data" / "synthetic"
    ).exists()
    assert "tests" in (Path(__file__).parents[2] / ".dockerignore").read_text(
        encoding="utf-8"
    )
    assert "backend/tests" in (Path(__file__).parents[2] / ".dockerignore").read_text(
        encoding="utf-8"
    )
    assert all(
        fixture["release_metadata"]["shipped_selection"] == "PROHIBITED"
        and fixture["release_metadata"]["reference_promotion"] == "PROHIBITED"
        and fixture["release_metadata"]["external_evaluation"] == "PROHIBITED"
        and fixture["release_metadata"]["production_recommendation"] == "PROHIBITED"
        for fixture in cases["fixtures"]
    )
    assert manifest["presentation"]["production_route"] is None


def test_ordinary_decision_support_path_rejects_a_synthetic_identity() -> None:
    ordinary_dataset = "dataset:ordinary-demo-v1"
    ordinary_order_line = "order-line:ordinary-demo-active-reactive"
    result = evaluate_decision_support(
        investigation_request=_request(
            dataset_version_id=ordinary_dataset,
            order_line_id=ordinary_order_line,
        ),
        subject_applicability={
            "state": "applicable",
            "subject_identity": ordinary_order_line,
            "reason": "synthetic fixture subject",
            "next_step": "Run the synthetic conformance harness.",
        },
        subject_verdict={
            "schema_version": "evidence-verdict.v2",
            "scope": "subject",
            "subject_identity": ordinary_order_line,
            "verdict_code": "SUPPORTED_UNDER_ASSUMPTIONS",
            "effect_display": "CAUSAL_ESTIMATE",
            "decision_support_role_permitted": True,
            "decision_support_evaluation_permitted": True,
        },
        population_verdict={
            "schema_version": "evidence-verdict.v2",
            "scope": "population",
        },
        intended_role="semi_synthetic_hero",
        release_candidate_id="local-local_fallback",
        runtime_fingerprint_digest="sha256:runtime",
    )

    assert result["outcome"] == "NOT_PERMITTED"
    assert result["state"] == "not_permitted"
    assert result["permission"]["denial_reason_code"] == (
        "SYNTHETIC_FIXTURE_NOT_SHIPPED"
    )
    assert result["options"] == []
    assert result["action_recommendation"] is None


def test_fixture_cases_cross_the_public_seam_only_as_not_shipped_inputs() -> None:
    for fixture in _cases()["fixtures"]:
        identity = fixture["identity"]
        subject_identity = identity.get("order_line_id") or identity.get(
            "preview_subject_digest"
        )
        assert isinstance(subject_identity, str)
        subject_verdict = fixture["evidence"]["subject_verdict"]
        result = evaluate_decision_support(
            investigation_request=_request(
                dataset_version_id=str(identity["dataset_version_id"]),
                order_line_id=subject_identity,
            ),
            subject_applicability={
                "state": "applicable",
                "subject_identity": subject_identity,
                "reason": "synthetic fixture subject",
                "next_step": "Run the synthetic conformance harness.",
            },
            subject_verdict=subject_verdict,
            population_verdict={"schema_version": "evidence-verdict.v2"},
            intended_role="semi_synthetic_hero",
            release_candidate_id="local-local_fallback",
            runtime_fingerprint_digest="sha256:runtime",
        )

        assert result["outcome"] == "NOT_PERMITTED"
        assert result["permission"]["denial_reason_code"] == (
            "SYNTHETIC_FIXTURE_NOT_SHIPPED"
        )
        assert result["options"] == []
        assert result["action_recommendation"] is None
