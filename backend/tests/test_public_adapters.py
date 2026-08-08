from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import ingestion
from backend.app.canonical import normalise_temporal
from backend.app.eligibility import (
    _source_semantics,
    evaluate_pre_estimation_eligibility,
)
from backend.app.main import create_app
from backend.app.settings import Settings


def make_client(database_path: Path) -> TestClient:
    return TestClient(create_app(Settings(database_path=database_path)))


def import_dataset(client: TestClient, dataset_key: str, mapping_manifest_id: str):
    return client.post(
        "/api/ingestion-runs",
        json={
            "idempotency_key": f"{dataset_key}-test-v1",
            "dataset_key": dataset_key,
            "mapping_manifest_id": mapping_manifest_id,
        },
    )


def test_olist_publishes_only_an_out_of_domain_validation_lineage(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        imported = import_dataset(
            client,
            "olist-validation",
            "olist-validation.mapping.v1",
        )
        lineage = client.get(
            f"/api/datasets/{imported.json()['dataset_version_id']}/lineage"
        )
        audit = client.get(
            f"/api/audit/occurrences/{lineage.json()['audit_binding']['occurrence_id']}"
        )

    assert imported.status_code == 201
    assert imported.json()["status"] == "SUCCEEDED"
    assert lineage.status_code == 200
    assert audit.status_code == 200
    body = lineage.json()
    dataset = body["dataset_version"]
    assert dataset["source_kind"] == "olist"
    assert dataset["intended_role"] == "out_of_domain_validation"
    assert dataset["source_role_ceiling"] == {
        "label": "Out-of-domain validation only",
        "permitted_claim_scope": "out_of_domain_validation",
        "subject_application_role_permitted": False,
        "decision_support_evaluation_permitted": False,
    }
    assert body["mapping_manifest"]["identity_mappings"]["order_line_id"][
        "source_paths"
    ] == ["order_id", "order_item_id"]
    assert body["mapping_manifest"]["event_mappings"]["transport_timing"] == {
        "committed": "order_purchase_timestamp",
        "promised": "shipping_limit_date",
        "reached": "order_delivered_carrier_date",
        "assumed_timezone": "America/Sao_Paulo",
        "promise_known_at": "committed",
    }
    assert body["audit_binding"]["source_role_ceiling"] == dataset["source_role_ceiling"]
    assert audit.json()["source_role_ceiling"] == dataset["source_role_ceiling"]
    assert len(body["order_lines"]) == 3
    assert any(
        event["kind"] == "milestone_reached"
        and event["milestone_kind"]["value"] == "supplier_handoff"
        for event in body["order_line_events"]
    )
    assert all(
        observation["origin"] == "observed"
        for observation in body["source_observations"]
    )
    assert all(
        observation["calibration"] == "none"
        for observation in body["source_observations"]
    )
    assert all(
        observation["source_field_path"]["state"] == "redacted"
        and observation["source_value_fingerprint"]["state"] == "redacted"
        for observation in body["source_observations"]
    )
    assert all(
        field.get("source_value") is None
        for line in body["order_lines"]
        for field in line["fields"].values()
    )
    assert {
        observation["target_record_id"]
        for observation in body["source_observations"]
        if observation["target_record_type"] == "OrderLine"
        and observation["target_field_path"] == "fields.quantity"
    } == {line["order_line_id"] for line in body["order_lines"]}
    assert all(
        event["clocks"][clock]["value"].get("source_value") is None
        for event in body["order_line_events"]
        for clock in ("occurred_at", "known_at", "available_at")
        if event["clocks"][clock]["state"] == "present"
    )
    assert "TIMEZONE_ASSUMED" in {
        finding["code"] for finding in body["validation_findings"]
    }


def test_scms_preserves_rejection_vignette_semantics_and_safe_missingness(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path / "core.sqlite3") as client:
        imported = import_dataset(
            client,
            "scms-rejection-vignette",
            "scms-rejection-vignette.mapping.v1",
        )
        lineage = client.get(
            f"/api/datasets/{imported.json()['dataset_version_id']}/lineage"
        )

    assert imported.status_code == 201
    assert lineage.status_code == 200
    body = lineage.json()
    dataset = body["dataset_version"]
    assert dataset["source_kind"] == "scms"
    assert dataset["intended_role"] == "rejection_vignette"
    assert dataset["source_role_ceiling"]["decision_support_evaluation_permitted"] is False
    semantics = _source_semantics(body, "supplier_handoff")
    assert semantics["state"] == "ineligible"
    assert semantics["reason_code"] == "SOURCE_SEMANTICS_INELIGIBLE"
    manifest = body["mapping_manifest"]
    assert manifest["event_mappings"]["scheduled_delivery"] == (
        "Scheduled Delivery Date"
    )
    assert manifest["event_mappings"]["delivered_to_client"] == (
        "Delivered to Client Date"
    )
    assert manifest["event_mappings"]["rejection_mapping"]["missingness_tokens"] == {
        "Date Not Captured": "unknown",
        "N/A - From RDC": "not_applicable",
    }
    assert sum(event["kind"] == "committed" for event in body["order_line_events"]) == 1
    assert sum(event["kind"] == "promise_recorded" for event in body["order_line_events"]) == 3
    assert sum(event["kind"] == "milestone_reached" for event in body["order_line_events"]) == 3
    scheduled = next(
        event
        for event in body["order_line_events"]
        if event["kind"] == "promise_recorded"
    )
    assert scheduled["milestone_kind"]["value"] == "customer_delivery"
    assert scheduled["clocks"]["occurred_at"]["state"] == "unknown"
    assert scheduled["clocks"]["known_at"]["state"] == "unknown"
    assert scheduled["promised_for"]["state"] == "present"
    assert {
        "PROMISE_ACTUAL_EQUALITY_SUSPICIOUS",
        "KNOWN_AT_UNKNOWN",
    } <= {finding["code"] for finding in body["validation_findings"]}
    assert any(
        line["fields"]["quantity"]["state"] == "missing"
        for line in body["order_lines"]
    )
    assert any(
        line["fields"]["project_id"]["state"] == "not_applicable"
        for line in body["order_lines"]
    )
    first_line = body["order_lines"][0]
    first_event = next(
        event
        for event in body["order_line_events"]
        if event["order_line_id"] == first_line["order_line_id"]
    )
    cutoff = normalise_temporal(first_event["clocks"]["occurred_at"]["value"])
    eligibility = evaluate_pre_estimation_eligibility(
        body,
        subject_id=first_line["order_line_id"],
        subject_supplier_id=first_line["supplier_id"],
        decision_cutoff=cutoff,
        observation_cutoff=cutoff,
        target_milestone_kind="customer_delivery",
        duration_basis="CALENDAR_DAY",
        trigger_mode="reactive",
    )
    assert eligibility["source_semantics"]["state"] == "ineligible"
    assert eligibility["source_semantics"]["reason_code"] == (
        "SOURCE_SEMANTICS_INELIGIBLE"
    )
    assert eligibility["state"] == "scientifically_unavailable"
    assert eligibility["estimator_input"] is None


def test_public_adapter_rejects_a_tampered_mapping_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = json.loads(ingestion.OLIST_SOURCE_FILE.read_text(encoding="utf-8"))
    manifest = json.loads(
        ingestion.OLIST_MAPPING_FILE.read_text(encoding="utf-8")
    )
    manifest["event_mappings"]["transport_timing"]["promised"] = (
        "order_purchase_timestamp"
    )
    monkeypatch.setattr(
        ingestion,
        "_read_public_bundle",
        lambda dataset_key: (
            source,
            manifest,
            "sha256:tampered-source",
            "sha256:tampered-mapping",
        ),
    )

    with make_client(tmp_path / "core.sqlite3") as client:
        response = import_dataset(
            client,
            "olist-validation",
            "olist-validation.mapping.v1",
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": "INGESTION_REJECTED",
        "recovery_action": "REPAIR_THE_REVIEWED_MAPPING_AND_RETRY",
    }


def test_public_adapter_registers_invalid_temporal_tokens_and_preserves_blank_unknown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    olist_source = json.loads(ingestion.OLIST_SOURCE_FILE.read_text(encoding="utf-8"))
    olist_manifest = json.loads(
        ingestion.OLIST_MAPPING_FILE.read_text(encoding="utf-8")
    )
    olist_source["rows"][0]["order_delivered_carrier_date"] = "not-a-date"
    monkeypatch.setattr(
        ingestion,
        "_read_public_bundle",
        lambda dataset_key: (
            olist_source,
            olist_manifest,
            "sha256:invalid-temporal-source",
            "sha256:ccd9eb87387990abd90d13ea967dc62dc801c842835bf2cd2699c43e9e05fdb7",
        ),
    )
    with make_client(tmp_path / "core.sqlite3") as client:
        imported = import_dataset(
            client,
            "olist-validation",
            "olist-validation.mapping.v1",
        )
        lineage = client.get(
            f"/api/datasets/{imported.json()['dataset_version_id']}/lineage"
        )
    assert imported.status_code == 201
    assert "TIMESTAMP_INVALID" in {
        finding["code"] for finding in lineage.json()["validation_findings"]
    }

    scms_source = json.loads(ingestion.SCMS_SOURCE_FILE.read_text(encoding="utf-8"))
    scms_manifest = json.loads(
        ingestion.SCMS_MAPPING_FILE.read_text(encoding="utf-8")
    )
    scms_source["rows"][0]["Delivery Recorded Date"] = "Unknown date token"
    scms_source["rows"][1]["Delivery Recorded Date"] = ""
    monkeypatch.setattr(
        ingestion,
        "_read_public_bundle",
        lambda dataset_key: (
            scms_source,
            scms_manifest,
            "sha256:blank-temporal-source",
            "sha256:e9cfeda6fa099f28fae85eabf6375fc0f927982625e70321289e87686f11e4f8",
        ),
    )
    with make_client(tmp_path / "core.sqlite3") as client:
        imported = import_dataset(
            client,
            "scms-rejection-vignette",
            "scms-rejection-vignette.mapping.v1",
        )
        lineage = client.get(
            f"/api/datasets/{imported.json()['dataset_version_id']}/lineage"
        )
    assert imported.status_code == 201
    body = lineage.json()
    assert "MISSINGNESS_TOKEN_UNMAPPED" in {
        finding["code"] for finding in body["validation_findings"]
    }
    first_line = next(
        line
        for line in body["order_lines"]
        if line["fields"]["material_class"]["value"] == "lab supplies"
    )
    reached = next(
        event
        for event in body["order_line_events"]
        if event["order_line_id"] == first_line["order_line_id"]
        and event["kind"] == "milestone_reached"
    )
    assert reached["clocks"]["known_at"]["state"] == "unknown"
    assert "TIMESTAMP_INVALID" not in {
        finding["code"] for finding in body["validation_findings"]
    }


def test_public_adapter_rejects_an_unsupported_source_schema_without_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = json.loads(ingestion.OLIST_SOURCE_FILE.read_text(encoding="utf-8"))
    manifest = json.loads(
        ingestion.OLIST_MAPPING_FILE.read_text(encoding="utf-8")
    )
    source["source_schema_version"] = "unreviewed.v9"
    monkeypatch.setattr(
        ingestion,
        "_read_public_bundle",
        lambda dataset_key: (
            source,
            manifest,
            "sha256:test-olist-source",
            "sha256:ccd9eb87387990abd90d13ea967dc62dc801c842835bf2cd2699c43e9e05fdb7",
        ),
    )

    with make_client(tmp_path / "core.sqlite3") as client:
        response = import_dataset(
            client,
            "olist-validation",
            "olist-validation.mapping.v1",
        )
        versions = client.get("/api/datasets")

    assert response.status_code == 422
    assert response.json() == {
        "code": "INGESTION_REJECTED",
        "recovery_action": "REPAIR_THE_REVIEWED_MAPPING_AND_RETRY",
    }
    assert versions.json()["items"] == []


def test_olist_conflicting_composite_identity_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = json.loads(ingestion.OLIST_SOURCE_FILE.read_text(encoding="utf-8"))
    manifest = json.loads(
        ingestion.OLIST_MAPPING_FILE.read_text(encoding="utf-8")
    )
    conflicting = deepcopy(source["rows"][0])
    conflicting["price"] = 999.0
    source["rows"] = [source["rows"][0], conflicting]
    monkeypatch.setattr(
        ingestion,
        "_read_public_bundle",
        lambda dataset_key: (
            source,
            manifest,
            "sha256:test-olist-source-conflict",
            "sha256:ccd9eb87387990abd90d13ea967dc62dc801c842835bf2cd2699c43e9e05fdb7",
        ),
    )

    with make_client(tmp_path / "core.sqlite3") as client:
        response = import_dataset(
            client,
            "olist-validation",
            "olist-validation.mapping.v1",
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": "INGESTION_REJECTED",
        "recovery_action": "REPAIR_THE_REVIEWED_MAPPING_AND_RETRY",
    }


def test_public_adapter_rejects_an_unsupported_row_structure_without_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = json.loads(ingestion.OLIST_SOURCE_FILE.read_text(encoding="utf-8"))
    manifest = json.loads(
        ingestion.OLIST_MAPPING_FILE.read_text(encoding="utf-8")
    )
    source["rows"][0]["unreviewed_column"] = "unsupported"
    monkeypatch.setattr(
        ingestion,
        "_read_public_bundle",
        lambda dataset_key: (
            source,
            manifest,
            "sha256:test-olist-unsupported-structure",
            "sha256:ccd9eb87387990abd90d13ea967dc62dc801c842835bf2cd2699c43e9e05fdb7",
        ),
    )

    with make_client(tmp_path / "core.sqlite3") as client:
        response = import_dataset(
            client,
            "olist-validation",
            "olist-validation.mapping.v1",
        )
        versions = client.get("/api/datasets")

    assert response.status_code == 422
    assert response.json() == {
        "code": "INGESTION_REJECTED",
        "recovery_action": "REPAIR_THE_REVIEWED_MAPPING_AND_RETRY",
    }
    assert versions.json()["items"] == []
