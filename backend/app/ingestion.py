from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo

from .audit import AuditStore
from .canonical import canonical_json as _canonical_json
from .canonical import field as _canonical_field
from .canonical import sha256 as _sha256
from .governance import GovernanceMixin, ensure_governance_schema
from .operations import DurableOperationsMixin, ensure_operation_schema
from .risk import ReactiveInvestigationMixin, ensure_risk_schema


INGESTION_SCHEMA_VERSION = "intake-lineage.v1"
CANONICAL_SCHEMA_VERSION = "canonical-lineage.v1"
HERO_DATASET_KEY = "semi-synthetic-hero"
HERO_MAPPING_MANIFEST_ID = "semi-synthetic-hero.mapping.v1"
HERO_SOURCE_FILE = Path(__file__).with_name("data") / "semi_synthetic_hero.json"
HERO_MAPPING_FILE = Path(__file__).with_name("data") / "semi_synthetic_hero.mapping.json"
OLIST_DATASET_KEY = "olist-validation"
OLIST_MAPPING_MANIFEST_ID = "olist-validation.mapping.v1"
OLIST_SOURCE_FILE = Path(__file__).with_name("data") / "olist_validation.json"
OLIST_MAPPING_FILE = Path(__file__).with_name("data") / "olist_validation.mapping.json"
SCMS_DATASET_KEY = "scms-rejection-vignette"
SCMS_MAPPING_MANIFEST_ID = "scms-rejection-vignette.mapping.v1"
SCMS_SOURCE_FILE = Path(__file__).with_name("data") / "scms_rejection_vignette.json"
SCMS_MAPPING_FILE = Path(__file__).with_name("data") / "scms_rejection_vignette.mapping.json"


@dataclass(frozen=True, slots=True)
class PublicAdapterSpec:
    dataset_key: str
    mapping_manifest_id: str
    source_file: Path
    mapping_file: Path
    source_kind: str
    intended_role: str
    source_schema_id: str
    source_schema_version: str
    reviewed_source_fields: frozenset[str]
    raw_redistribution_policy: str
    derived_redistribution_policy: str
    mapping_sha256: str


PUBLIC_ADAPTER_SPECS = {
    OLIST_DATASET_KEY: PublicAdapterSpec(
        dataset_key=OLIST_DATASET_KEY,
        mapping_manifest_id=OLIST_MAPPING_MANIFEST_ID,
        source_file=OLIST_SOURCE_FILE,
        mapping_file=OLIST_MAPPING_FILE,
        source_kind="olist",
        intended_role="out_of_domain_validation",
        source_schema_id="olist-public-order-items",
        source_schema_version="olist-public-order-items.v1",
        reviewed_source_fields=frozenset(
            {
                "order_id",
                "order_item_id",
                "seller_id",
                "order_purchase_timestamp",
                "shipping_limit_date",
                "order_delivered_carrier_date",
                "product_category_name",
                "price",
                "customer_state",
            }
        ),
        raw_redistribution_policy="prohibited",
        derived_redistribution_policy="prohibited",
        mapping_sha256="sha256:ccd9eb87387990abd90d13ea967dc62dc801c842835bf2cd2699c43e9e05fdb7",
    ),
    SCMS_DATASET_KEY: PublicAdapterSpec(
        dataset_key=SCMS_DATASET_KEY,
        mapping_manifest_id=SCMS_MAPPING_MANIFEST_ID,
        source_file=SCMS_SOURCE_FILE,
        mapping_file=SCMS_MAPPING_FILE,
        source_kind="scms",
        intended_role="rejection_vignette",
        source_schema_id="scms-delivery-history",
        source_schema_version="scms-delivery-history.v1",
        reviewed_source_fields=frozenset(
            {
                "ID",
                "Vendor",
                "Product Group",
                "PO Sent to Vendor Date",
                "Scheduled Delivery Date",
                "Delivered to Client Date",
                "Delivery Recorded Date",
            }
        ),
        raw_redistribution_policy="prohibited",
        derived_redistribution_policy="unknown",
        mapping_sha256="sha256:e9cfeda6fa099f28fae85eabf6375fc0f927982625e70321289e87686f11e4f8",
    ),
}

_SOURCE_ROLE_CEILINGS = {
    "semi_synthetic_hero": {
        "label": "Construction demonstration",
        "permitted_claim_scope": "construction_demonstration",
        "subject_application_role_permitted": True,
        "decision_support_evaluation_permitted": True,
    },
    "out_of_domain_validation": {
        "label": "Out-of-domain validation only",
        "permitted_claim_scope": "out_of_domain_validation",
        "subject_application_role_permitted": False,
        "decision_support_evaluation_permitted": False,
    },
    "rejection_vignette": {
        "label": "Rejection vignette only",
        "permitted_claim_scope": "rejection_vignette",
        "subject_application_role_permitted": False,
        "decision_support_evaluation_permitted": False,
    },
}

_REVIEWED_PUBLIC_MAPPING_RULE_IDS = frozenset(
    {
        "uuid5.dataset.order-line.olist-order-item.v1",
        "uuid5.dataset.order-group.olist-order.v1",
        "uuid5.dataset.supplier.olist-seller.v1",
        "olist.category-preserving.v1",
        "olist.complexity-not-mapped.v1",
        "olist.one-order-item-row.v1",
        "olist.price-brl-preserving.v1",
        "olist.project-not-mapped.v1",
        "olist.project-phase-not-mapped.v1",
        "olist.urgency-not-mapped.v1",
        "olist.customer-state-preserving.v1",
        "olist.contract-form-not-mapped.v1",
        "uuid5.dataset.order-line.scms-shipment.v1",
        "uuid5.dataset.order-group.scms-shipment.v1",
        "uuid5.dataset.supplier.scms-vendor.v1",
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

_VALUE_STATES = frozenset(
    {
        "present",
        "missing",
        "unknown",
        "not_applicable",
        "invalid",
        "unresolved",
        "redacted",
    }
)
_EVENT_KINDS = frozenset(
    {"committed", "promise_recorded", "promise_revised", "milestone_reached", "cancelled"}
)
_MILESTONE_KINDS = frozenset(
    {"supplier_completion", "supplier_handoff", "customer_delivery", "other"}
)
_MISSING = object()

INGESTION_RUNS_TABLE = """
    CREATE TABLE IF NOT EXISTS ingestion_runs (
        ingestion_run_id TEXT PRIMARY KEY,
        idempotency_key TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL,
        dataset_key TEXT NOT NULL,
        mapping_manifest_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
        dataset_version_id TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        payload_json TEXT NOT NULL
    )
"""
INGESTION_RUNS_COLUMNS = [
    "ingestion_run_id",
    "idempotency_key",
    "request_hash",
    "dataset_key",
    "mapping_manifest_id",
    "status",
    "dataset_version_id",
    "started_at",
    "completed_at",
    "payload_json",
]

DATASET_VERSIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS dataset_versions (
        dataset_version_id TEXT PRIMARY KEY,
        dataset_id TEXT NOT NULL,
        semantic_content_hash TEXT NOT NULL UNIQUE,
        first_published_at TEXT NOT NULL,
        first_published_by_run_id TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
"""
DATASET_VERSIONS_COLUMNS = [
    "dataset_version_id",
    "dataset_id",
    "semantic_content_hash",
    "first_published_at",
    "first_published_by_run_id",
    "payload_json",
]

LINEAGE_RECORDS_TABLE = """
    CREATE TABLE IF NOT EXISTS lineage_records (
        dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(dataset_version_id),
        record_type TEXT NOT NULL,
        record_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        PRIMARY KEY (dataset_version_id, record_type, record_id)
    )
"""
LINEAGE_RECORDS_COLUMNS = [
    "dataset_version_id",
    "record_type",
    "record_id",
    "payload_json",
]

LINEAGE_SNAPSHOTS_TABLE = """
    CREATE TABLE IF NOT EXISTS lineage_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL REFERENCES demo_workspaces(workspace_id),
        dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(dataset_version_id),
        content_hash TEXT NOT NULL,
        occurrence_id TEXT NOT NULL,
        event_seq INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (workspace_id, dataset_version_id)
    )
"""
LINEAGE_SNAPSHOTS_COLUMNS = [
    "snapshot_id",
    "workspace_id",
    "dataset_version_id",
    "content_hash",
    "occurrence_id",
    "event_seq",
    "created_at",
]

_IMMUTABLE_TABLES = (
    "ingestion_runs",
    "dataset_versions",
    "lineage_records",
    "lineage_snapshots",
)


def _ensure_table(
    connection: sqlite3.Connection,
    table_name: str,
    create_sql: str,
    expected_columns: list[str],
    *,
    create: bool,
) -> None:
    if create:
        connection.execute(create_sql)
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if [str(column[1]) for column in columns] != expected_columns:
        raise sqlite3.DatabaseError(f"{table_name} schema is not the locked intake schema")


def ensure_ingestion_schema(connection: sqlite3.Connection, *, create: bool) -> None:
    _ensure_table(
        connection,
        "ingestion_runs",
        INGESTION_RUNS_TABLE,
        INGESTION_RUNS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "dataset_versions",
        DATASET_VERSIONS_TABLE,
        DATASET_VERSIONS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "lineage_records",
        LINEAGE_RECORDS_TABLE,
        LINEAGE_RECORDS_COLUMNS,
        create=create,
    )
    _ensure_table(
        connection,
        "lineage_snapshots",
        LINEAGE_SNAPSHOTS_TABLE,
        LINEAGE_SNAPSHOTS_COLUMNS,
        create=create,
    )
    if create:
        for table_name in _IMMUTABLE_TABLES:
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'intake lineage records are immutable');
                END
                """
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table_name}_immutable_delete
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'intake lineage records are immutable');
                END
                """
            )


class IngestionIdempotencyConflict(Exception):
    """The same import key was submitted with different closed content."""


class DatasetVersionUnavailable(Exception):
    """A requested immutable dataset version does not exist."""


class IngestionRejected(Exception):
    """A source could not be published under the closed canonical contract."""

    def __init__(self, run: dict[str, Any]) -> None:
        self.run = run
        super().__init__("ingestion run rejected")


@dataclass(frozen=True, slots=True)
class IngestionResult:
    result: str
    ingestion_run_id: str
    dataset_version_id: str | None
    status: str
    run: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LineageSnapshotBinding:
    snapshot_id: str
    dataset_version_id: str
    occurrence_id: str
    event_seq: int
    content_hash: str
    created_at: str


def _json_load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise IngestionRejected({"status": "FAILED"})
    return value


def _read_bundle() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    source_bytes = HERO_SOURCE_FILE.read_bytes()
    mapping_bytes = HERO_MAPPING_FILE.read_bytes()
    return (
        _json_load(HERO_SOURCE_FILE),
        _json_load(HERO_MAPPING_FILE),
        _sha256(source_bytes),
        _sha256(mapping_bytes),
    )


def _read_public_bundle(
    dataset_key: str,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    spec = PUBLIC_ADAPTER_SPECS[dataset_key]
    source_bytes = spec.source_file.read_bytes()
    mapping_bytes = spec.mapping_file.read_bytes()
    return (
        _json_load(spec.source_file),
        _json_load(spec.mapping_file),
        _sha256(source_bytes),
        _sha256(mapping_bytes),
    )


def _field(state: str, value: object = None) -> dict[str, Any]:
    if state not in _VALUE_STATES:
        raise IngestionRejected({"status": "FAILED"})
    return _canonical_field(state, value)


def _temporal(raw: object, *, include_source_value: bool = True) -> dict[str, Any]:
    if raw is _MISSING:
        return _field("missing")
    if raw is None:
        return _field("unresolved")
    if not isinstance(raw, Mapping):
        return _field("invalid")
    value = raw.get("value")
    source_value = raw.get("source_value", value)
    if not isinstance(value, str) or (
        include_source_value and not isinstance(source_value, str)
    ):
        return _field("invalid")
    kind = str(raw.get("kind", ""))
    precision = str(raw.get("precision", ""))
    timezone_status = str(raw.get("timezone_status", ""))
    if kind not in {"date", "local_datetime", "instant"}:
        return _field("invalid")
    if timezone_status not in {"known", "assumed", "unknown", "not_applicable"}:
        return _field("invalid")

    normalized_value = value
    if kind == "instant" and timezone_status in {"known", "assumed"}:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return _field("unresolved")
            normalized_value = parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return _field("invalid")

    source_timezone = raw.get("source_timezone")
    if timezone_status in {"known", "assumed"}:
        if not isinstance(source_timezone, str) or not source_timezone:
            return _field("unresolved")
        timezone_field = _field("present", source_timezone)
    else:
        timezone_field = _field("not_applicable" if timezone_status == "not_applicable" else "unresolved")

    return _field(
        "present",
        {
            "kind": kind,
            "source_value": source_value if include_source_value else None,
            "normalized_value": normalized_value,
            "precision": precision,
            "timezone_status": timezone_status,
            "source_timezone": timezone_field,
        },
    )


def _typed_field(
    raw: object,
    canonical_type: str,
) -> dict[str, Any]:
    if raw is _MISSING:
        return _field("missing")
    if raw is None:
        return _field("unresolved")
    if not isinstance(raw, Mapping):
        return {**_field("invalid"), "source_value": raw}
    state = str(raw.get("state", "unresolved"))
    if state != "present":
        resolved_state = state if state in _VALUE_STATES else "unresolved"
        return {
            **_field(resolved_state),
            "source_value": raw.get("raw"),
        }
    if "value" not in raw:
        return _field("unresolved")
    value = raw["value"]
    if canonical_type == "quantity":
        return {
            **_field("present", {"amount": value, "unit": raw.get("unit", "")}),
            "source_value": raw.get("value"),
        }
    if canonical_type == "money":
        return {
            **_field("present", {"amount": value, "currency": raw.get("currency", "")}),
            "source_value": raw.get("value"),
        }
    return {**_field("present", value), "source_value": value}


def _mapped_value(source: object, path: str) -> object:
    current = source
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _mapping_source_paths(mapping: Mapping[str, Any]) -> list[str]:
    if "source_paths" in mapping:
        source_paths = mapping.get("source_paths")
        if isinstance(source_paths, list) and all(
            isinstance(path, str) and path for path in source_paths
        ):
            return list(source_paths)
        return []
    source_path = mapping.get("source_path")
    return [source_path] if isinstance(source_path, str) and source_path else []


def _public_identity_value(
    row: Mapping[str, Any],
    mapping: Mapping[str, Any],
) -> tuple[str, list[object]] | object:
    paths = _mapping_source_paths(mapping)
    values = [_mapped_value(row, path) for path in paths]
    if not values or any(
        value is _MISSING
        or value is None
        or (isinstance(value, str) and not value.strip())
        for value in values
    ):
        return _MISSING
    return _canonical_json(values), values


def _public_state(raw: object, mapping: Mapping[str, Any]) -> str:
    fixed_state = mapping.get("fixed_state")
    if isinstance(fixed_state, str):
        return fixed_state if fixed_state in _VALUE_STATES else "invalid"
    if raw is _MISSING:
        return "missing"
    if raw is None:
        return "unknown"
    if isinstance(raw, str):
        tokens = mapping.get("missingness_tokens")
        if isinstance(tokens, Mapping) and raw in tokens:
            state = tokens[raw]
            if isinstance(state, str) and state in _VALUE_STATES:
                return state
        if not raw.strip():
            return "missing"
    return "present"


def _public_field(
    raw: object,
    mapping: Mapping[str, Any],
) -> dict[str, Any]:
    state = _public_state(raw, mapping)
    if state != "present":
        return _field(state)
    if "fixed_value" in mapping:
        return _field(
            "present",
            {
                "amount": mapping["fixed_value"],
                "unit": mapping.get("fixed_unit", ""),
            },
        )
    canonical_type = mapping.get("canonical_type")
    if canonical_type == "quantity":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)):
            return _field("invalid")
        return _field(
            "present",
            {"amount": raw, "unit": mapping.get("unit", "")},
        )
    if canonical_type == "money":
        currency = mapping.get("currency")
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(float(raw))
            or not isinstance(currency, str)
            or not currency
        ):
            return _field("invalid")
        return _field("present", {"amount": raw, "currency": currency})
    if canonical_type in {"classification", "identifier"} and not isinstance(raw, str):
        return _field("invalid")
    return _field("present", raw)


def _public_temporal(
    raw: object,
    *,
    missingness_tokens: Mapping[str, str] | None = None,
    assumed_timezone: str | None = None,
) -> dict[str, Any]:
    if raw is _MISSING:
        return _field("missing")
    if raw is None:
        return _field("unknown")
    if not isinstance(raw, str):
        return _field("invalid")
    if not raw.strip():
        return _field("unknown")
    if missingness_tokens is not None and raw in missingness_tokens:
        state = missingness_tokens[raw]
        return _field(state if state in _VALUE_STATES else "invalid")
    value = raw.strip()
    if len(value) == 10:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return _field("invalid")
        return _temporal(
            {
                "value": value,
                "kind": "date",
                "precision": "date",
                "timezone_status": "not_applicable",
                "source_timezone": None,
            },
            include_source_value=False,
        )
    try:
        parsed = datetime.fromisoformat(value.replace(" ", "T"))
    except ValueError:
        return _field("invalid")
    if parsed.tzinfo is not None:
        timezone_status = "known"
        source_timezone = "source-offset"
    elif assumed_timezone is not None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(assumed_timezone))
        except Exception:
            return _field("unresolved")
        timezone_status = "assumed"
        source_timezone = assumed_timezone
    else:
        timezone_status = "unknown"
        source_timezone = None
    normalized_input = parsed.isoformat() if timezone_status in {"known", "assumed"} else value
    return _temporal(
        {
            "value": normalized_input,
            "source_value": value,
            "kind": "instant" if timezone_status in {"known", "assumed"} else "local_datetime",
            "precision": "second",
            "timezone_status": timezone_status,
            "source_timezone": source_timezone,
        },
        include_source_value=False,
    )


def _public_temporal_failure_code(
    raw: object,
    *,
    missingness_tokens: Mapping[str, str] | None,
) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    if missingness_tokens is None:
        return "TIMESTAMP_INVALID"
    value = raw.strip()
    return (
        "TIMESTAMP_INVALID"
        if len(value) >= 5 and value[:4].isdigit() and value[4] == "-"
        else "MISSINGNESS_TOKEN_UNMAPPED"
    )


def _role_ceiling(intended_role: str) -> dict[str, Any]:
    ceiling = _SOURCE_ROLE_CEILINGS.get(intended_role)
    if ceiling is None:
        raise IngestionRejected({"status": "FAILED"})
    return dict(ceiling)


def _source_locator(dataset_id: str, source_key: str, field_path: str) -> str:
    return "loc_" + hashlib.sha256(
        f"{dataset_id}|{source_key}|{field_path}".encode("utf-8")
    ).hexdigest()[:24]


def _source_observation(
    *,
    dataset_id: str,
    source_object_hash: str,
    ingestion_run_id: str,
    target_record_type: str,
    target_record_id: str,
    target_field_path: str,
    source_key: str,
    source_field_path: str,
    source_value: object,
    known_at: dict[str, Any],
    available_at: dict[str, Any],
    transformation_rule_id: str,
    transformation_rule_version: str = "1",
    origin: str = "simulated",
    derivation: str | None = None,
    calibration: str = "none",
    redistribution_permitted: bool = True,
) -> dict[str, Any]:
    locator = _source_locator(dataset_id, source_key, source_field_path)
    observation_id = _sha256(
        {
            "dataset_id": dataset_id,
            "target_record_type": target_record_type,
            "target_record_id": target_record_id,
            "target_field_path": target_field_path,
            "source_object_hash": source_object_hash,
            "source_locator_token": locator,
            "transformation_rule_id": transformation_rule_id,
        }
    )
    return {
        "source_observation_id": observation_id,
        "ingestion_run_id": ingestion_run_id,
        "target_record_type": target_record_type,
        "target_record_id": target_record_id,
        "target_field_path": target_field_path,
        "source_object_hash": source_object_hash,
        "source_locator_token": locator,
        "source_field_path": (
            _field("present", source_field_path)
            if redistribution_permitted
            else _field("redacted")
        ),
        "known_at": known_at,
        "available_at": available_at,
        "origin": origin,
        "derivation": derivation
        or ("normalized" if transformation_rule_id != "direct" else "direct"),
        "calibration": calibration,
        "transformation_rule_id": _field(
            "not_applicable" if transformation_rule_id == "direct" else "present",
            transformation_rule_id,
        )
        if transformation_rule_id != "direct"
        else _field("not_applicable"),
        "transformation_rule_version": _field(
            "not_applicable" if transformation_rule_id == "direct" else "present",
            transformation_rule_version,
        )
        if transformation_rule_id != "direct"
        else _field("not_applicable"),
        "evidence_refs": (
            [
                f"source-locator:{locator}",
                f"mapping-rule:{transformation_rule_id}:{transformation_rule_version}",
            ]
            if redistribution_permitted
            else []
        ),
        "source_value_fingerprint": (
            _field("present", _sha256(source_value))
            if redistribution_permitted
            else _field("redacted")
        ),
    }


def _finding(
    *,
    ingestion_run_id: str,
    code: str,
    severity: str,
    disposition: str,
    scope: str,
    affected_refs: list[str],
    affected_count: int,
    rule_id: str,
    message: str,
    remediation: str,
) -> dict[str, Any]:
    finding_id = _sha256(
        {
            "code": code,
            "scope": scope,
            "affected_refs": affected_refs,
        }
    )
    return {
        "validation_finding_id": finding_id,
        "ingestion_run_id": ingestion_run_id,
        "code": code,
        "code_registry_version": "canonical-lineage.validation.v1",
        "severity": severity,
        "disposition": disposition,
        "scope": scope,
        "affected_refs": affected_refs[:10],
        "affected_count": affected_count,
        "rule_id": rule_id,
        "rule_version": "1",
        "message": message,
        "remediation": remediation,
    }


def _summary(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_disposition: dict[str, int] = {}
    for finding in findings:
        code = str(finding["code"])
        disposition = str(finding["disposition"])
        by_code[code] = by_code.get(code, 0) + int(finding["affected_count"])
        by_disposition[disposition] = by_disposition.get(disposition, 0) + 1
    return {
        "total": len(findings),
        "by_code": dict(sorted(by_code.items())),
        "by_disposition": dict(sorted(by_disposition.items())),
    }


def _with_dataset_version(
    record: dict[str, Any],
    dataset_version_id: str,
) -> dict[str, Any]:
    return {**record, "dataset_version_id": dataset_version_id}


def _build_bundle(
    *,
    ingestion_run_id: str,
    started_at: str,
) -> dict[str, Any]:
    source, manifest, source_hash, mapping_hash = _read_bundle()
    if source.get("dataset_key") != HERO_DATASET_KEY:
        raise IngestionRejected({"status": "FAILED"})
    if manifest.get("mapping_manifest_id") != HERO_MAPPING_MANIFEST_ID:
        raise IngestionRejected({"status": "FAILED"})
    if manifest.get("source_schema_id") != source.get("source_schema_id"):
        raise IngestionRejected({"status": "FAILED"})
    if manifest.get("source_schema_version") != source.get("source_schema_version"):
        raise IngestionRejected({"status": "FAILED"})

    identity_mappings = manifest.get("identity_mappings")
    field_mappings = manifest.get("field_mappings")
    event_mappings = manifest.get("event_mappings")
    if not all(
        isinstance(value, dict) and value
        for value in (identity_mappings, field_mappings, event_mappings)
    ):
        raise IngestionRejected({"status": "FAILED"})
    required_identity_mappings = {"order_line_id", "order_group_id", "supplier_id"}
    if set(identity_mappings) != required_identity_mappings:
        raise IngestionRejected({"status": "FAILED"})
    required_field_mappings = {
        "material_class",
        "complexity_class",
        "quantity",
        "value",
        "project_id",
        "project_phase",
        "urgency_class",
        "geography_code",
        "contract_form",
    }
    if set(field_mappings) != required_field_mappings:
        raise IngestionRejected({"status": "FAILED"})
    for mapping in identity_mappings.values():
        if not isinstance(mapping, dict) or not all(
            isinstance(mapping.get(key), str) and mapping[key]
            for key in ("source_path", "rule_id", "rule_version")
        ):
            raise IngestionRejected({"status": "FAILED"})
    for mapping in field_mappings.values():
        if not isinstance(mapping, dict) or not all(
            isinstance(mapping.get(key), str) and mapping[key]
            for key in ("source_path", "canonical_type", "rule_id", "rule_version")
        ):
            raise IngestionRejected({"status": "FAILED"})
    required_event_mappings = {
        "collection_path",
        "source_event_key",
        "kind",
        "milestone_kind",
        "occurred_at",
        "known_at",
        "available_at",
        "promised_for",
        "reason",
        "revises_promise_source_event_key",
    }
    if set(event_mappings) != required_event_mappings or not all(
        isinstance(value, str) and value for value in event_mappings.values()
    ):
        raise IngestionRejected({"status": "FAILED"})

    dataset_id = HERO_DATASET_KEY
    namespace = uuid5(NAMESPACE_URL, f"causal-delay-copilot:dataset:{dataset_id}")
    rows = source.get("rows")
    if not isinstance(rows, list):
        raise IngestionRejected({"status": "FAILED"})

    semantic_lines: dict[str, dict[str, Any]] = {}
    semantic_events: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    source_event_ids: dict[str, str] = {}
    publication_time = started_at

    for row in rows:
        if not isinstance(row, dict):
            findings.append(
                _finding(
                    ingestion_run_id=ingestion_run_id,
                    code="REQUIRED_ID_MISSING",
                    severity="error",
                    disposition="quarantine_record",
                    scope="record",
                    affected_refs=[],
                    affected_count=1,
                    rule_id="hero-row-shape.v1",
                    message="A bundled source row has no usable canonical identity.",
                    remediation="Repair the reviewed bundled mapping before importing.",
                )
            )
            continue

        source_key = _mapped_value(row, identity_mappings["order_line_id"]["source_path"])
        group_key = _mapped_value(row, identity_mappings["order_group_id"]["source_path"])
        supplier_key = _mapped_value(row, identity_mappings["supplier_id"]["source_path"])
        if not all(isinstance(value, str) and value for value in (source_key, group_key, supplier_key)):
            findings.append(
                _finding(
                    ingestion_run_id=ingestion_run_id,
                    code="REQUIRED_ID_MISSING",
                    severity="error",
                    disposition="quarantine_record",
                    scope="record",
                    affected_refs=[],
                    affected_count=1,
                    rule_id="hero-row-identity.v1",
                    message="A bundled source row is missing a reviewed source identity.",
                    remediation="Repair the source key mapping before importing.",
                )
            )
            continue

        order_line_id = uuid5(namespace, f"order-line:{source_key}").hex
        order_group_id = uuid5(namespace, f"order-group:{group_key}").hex
        supplier_id = uuid5(namespace, f"supplier:{supplier_key}").hex
        fields: dict[str, dict[str, Any]] = {}
        for field_name, mapping in field_mappings.items():
            raw_field = _mapped_value(row, mapping["source_path"])
            fields[field_name] = _typed_field(
                raw_field,
                mapping["canonical_type"],
            )
            if fields[field_name]["state"] == "invalid":
                findings.append(
                    _finding(
                        ingestion_run_id=ingestion_run_id,
                        code="VALUE_OUT_OF_RANGE",
                        severity="error",
                        disposition="invalidate_field",
                        scope="field",
                        affected_refs=[f"{order_line_id}.fields.{field_name}"],
                        affected_count=1,
                        rule_id=mapping["rule_id"],
                        message="A bundled source value cannot be used as the declared canonical type.",
                        remediation="Review the source value before using this field in downstream analysis.",
                    )
                )

        candidate_line = {
            "order_line_id": order_line_id,
            "order_group_id": order_group_id,
            "supplier_id": supplier_id,
            "fields": fields,
        }
        existing_line = semantic_lines.get(order_line_id)
        if existing_line is None:
            semantic_lines[order_line_id] = candidate_line
        elif existing_line != candidate_line:
            findings.append(
                _finding(
                    ingestion_run_id=ingestion_run_id,
                    code="IDENTITY_COLLISION",
                    severity="error",
                    disposition="reject_run",
                    scope="record",
                    affected_refs=[order_line_id],
                    affected_count=1,
                    rule_id="uuid5.dataset.order-line.v1",
                    message="Distinct source content maps to one dataset-scoped Order Line identity.",
                    remediation="Correct the reviewed source-key mapping before importing.",
                )
            )
        else:
            findings.append(
                _finding(
                    ingestion_run_id=ingestion_run_id,
                    code="SOURCE_DUPLICATE_DEDUPED",
                    severity="info",
                    disposition="advisory",
                    scope="record",
                    affected_refs=[order_line_id],
                    affected_count=1,
                    rule_id="exact-source-row-deduplication.v1",
                    message="An exact repeated bundled observation was deduplicated.",
                    remediation="No action is required; the first canonical observation remains authoritative.",
                )
            )

        commitment_known_at: dict[str, Any] = _field("unresolved")
        commitment_available_at: dict[str, Any] = _field("unresolved")
        raw_events = _mapped_value(row, event_mappings["collection_path"])
        if not isinstance(raw_events, list):
            raw_events = []
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            source_event_key = _mapped_value(raw_event, event_mappings["source_event_key"])
            kind = _mapped_value(raw_event, event_mappings["kind"])
            if (
                not isinstance(source_event_key, str)
                or not isinstance(kind, str)
                or kind not in _EVENT_KINDS
            ):
                findings.append(
                    _finding(
                        ingestion_run_id=ingestion_run_id,
                        code="ADAPTER_CONTRACT_VIOLATION",
                        severity="error",
                        disposition="reject_run",
                        scope="run",
                        affected_refs=[order_line_id],
                        affected_count=1,
                        rule_id="hero-event-shape.v1",
                        message="A bundled event is outside the reviewed canonical event mapping.",
                        remediation="Repair the bundled mapping before importing.",
                    )
                )
                continue
            event_id = uuid5(namespace, f"event:{source_event_key}").hex
            source_event_ids[source_event_key] = event_id
            occurred_at = _temporal(_mapped_value(raw_event, event_mappings["occurred_at"]))
            known_at = _temporal(_mapped_value(raw_event, event_mappings["known_at"]))
            available_at = _temporal(_mapped_value(raw_event, event_mappings["available_at"]))
            if kind == "committed":
                commitment_known_at = known_at
                commitment_available_at = available_at
            if known_at["state"] == "unresolved":
                findings.append(
                    _finding(
                        ingestion_run_id=ingestion_run_id,
                        code="KNOWN_AT_UNKNOWN",
                        severity="warning",
                        disposition="advisory",
                        scope="record",
                        affected_refs=[event_id],
                        affected_count=1,
                        rule_id="event-known-at-preserved.v1",
                        message="The source does not establish when this event became known.",
                        remediation="Keep the event visible but exclude it where a decision-time clock is required.",
                    )
                )
            temporal_value = occurred_at.get("value")
            if isinstance(temporal_value, dict) and temporal_value.get("timezone_status") == "unknown":
                findings.append(
                    _finding(
                        ingestion_run_id=ingestion_run_id,
                        code="TIMEZONE_UNKNOWN",
                        severity="warning",
                        disposition="advisory",
                        scope="field",
                        affected_refs=[f"{event_id}.occurred_at"],
                        affected_count=1,
                        rule_id="event-timezone-preserved.v1",
                        message="The source timestamp has no trustworthy timezone.",
                        remediation="Retain the local value and resolve timezone semantics before temporal comparison.",
                    )
                )

            milestone_kind = _mapped_value(raw_event, event_mappings["milestone_kind"])
            if kind in {"promise_recorded", "promise_revised", "milestone_reached"}:
                if (
                    not isinstance(milestone_kind, str)
                    or milestone_kind not in _MILESTONE_KINDS
                ):
                    milestone_kind = "other"
                    findings.append(
                        _finding(
                            ingestion_run_id=ingestion_run_id,
                            code="MILESTONE_KIND_UNSUPPORTED",
                            severity="warning",
                            disposition="advisory",
                            scope="field",
                            affected_refs=[f"{event_id}.milestone_kind"],
                            affected_count=1,
                            rule_id="event-milestone-kind.v1",
                            message="The source milestone is retained as the explicit other category.",
                            remediation="Review the milestone role before using it as a supplier-controlled outcome.",
                        )
                    )
                milestone_field = _field("present", milestone_kind)
            else:
                milestone_field = _field("not_applicable")

            promised_for = (
                _temporal(_mapped_value(raw_event, event_mappings["promised_for"]))
                if kind in {"promise_recorded", "promise_revised"}
                else _field("not_applicable")
            )
            reason = (
                _field("present", _mapped_value(raw_event, event_mappings["reason"]))
                if isinstance(_mapped_value(raw_event, event_mappings["reason"]), str)
                else _field("missing")
            )
            revises_source_key = _mapped_value(
                raw_event,
                event_mappings["revises_promise_source_event_key"],
            )
            revises_promise = (
                _field("present", source_event_ids[revises_source_key])
                if isinstance(revises_source_key, str) and revises_source_key in source_event_ids
                else _field("not_applicable" if kind != "promise_revised" else "unresolved")
            )
            candidate_event = {
                "event_id": event_id,
                "order_line_id": order_line_id,
                "kind": kind,
                "milestone_kind": milestone_field,
                "clocks": {
                    "occurred_at": occurred_at,
                    "known_at": known_at,
                    "available_at": available_at,
                },
                "ingested_at": publication_time,
                "promised_for": promised_for,
                "reason": reason,
                "revises_promise_event_id": revises_promise,
                "supersedes_event_id": _field("missing"),
            }
            existing_event = semantic_events.get(event_id)
            if existing_event is None:
                semantic_events[event_id] = candidate_event
            elif {
                key: value for key, value in existing_event.items() if key != "ingested_at"
            } != {
                key: value for key, value in candidate_event.items() if key != "ingested_at"
            }:
                findings.append(
                    _finding(
                        ingestion_run_id=ingestion_run_id,
                        code="EVENT_ID_CONTENT_CONFLICT",
                        severity="error",
                        disposition="reject_run",
                        scope="run",
                        affected_refs=[event_id],
                        affected_count=1,
                        rule_id="event-id-content.v1",
                        message="One deterministic event identity has conflicting canonical content.",
                        remediation="Repair the source revision mapping before importing.",
                    )
                )
            else:
                findings.append(
                    _finding(
                        ingestion_run_id=ingestion_run_id,
                        code="SOURCE_DUPLICATE_DEDUPED",
                        severity="info",
                        disposition="advisory",
                        scope="record",
                        affected_refs=[event_id],
                        affected_count=1,
                        rule_id="exact-source-observation-deduplication.v1",
                        message="An exact repeated event observation was deduplicated.",
                        remediation="No action is required; the first event remains authoritative.",
                    )
                )

            event_source_values = {
                "source_event_key": source_event_key,
                "kind": kind,
                "milestone_kind": _mapped_value(
                    raw_event,
                    event_mappings["milestone_kind"],
                ),
                "occurred_at": _mapped_value(
                    raw_event,
                    event_mappings["occurred_at"],
                ),
                "known_at": _mapped_value(raw_event, event_mappings["known_at"]),
                "available_at": _mapped_value(
                    raw_event,
                    event_mappings["available_at"],
                ),
                "promised_for": _mapped_value(
                    raw_event,
                    event_mappings["promised_for"],
                ),
                "reason": _mapped_value(raw_event, event_mappings["reason"]),
                "revises_promise_source_event_key": _mapped_value(
                    raw_event,
                    event_mappings["revises_promise_source_event_key"],
                ),
            }
            event_target_paths = {
                "source_event_key": "event_id",
                "kind": "kind",
                "milestone_kind": "milestone_kind",
                "occurred_at": "clocks.occurred_at",
                "known_at": "clocks.known_at",
                "available_at": "clocks.available_at",
                "promised_for": "promised_for",
                "reason": "reason",
                "revises_promise_source_event_key": "revises_promise_event_id",
            }
            for event_field_name, source_value in event_source_values.items():
                source_path = event_mappings[event_field_name]
                observation = _source_observation(
                    dataset_id=dataset_id,
                    source_object_hash=source_hash,
                    ingestion_run_id=ingestion_run_id,
                    target_record_type="OrderLineEvent",
                    target_record_id=event_id,
                    target_field_path=event_target_paths[event_field_name],
                    source_key=source_key,
                    source_field_path=f"{event_mappings['collection_path']}[{source_event_key}].{source_path}",
                    source_value=None if source_value is _MISSING else source_value,
                    known_at=known_at,
                    available_at=available_at,
                    transformation_rule_id="event-mapping-preserving.v1",
                )
                observations.setdefault(observation["source_observation_id"], observation)

        identity_values = {
            "order_line_id": source_key,
            "order_group_id": group_key,
            "supplier_id": supplier_key,
        }
        for identity_name, mapping in identity_mappings.items():
            observation = _source_observation(
                dataset_id=dataset_id,
                source_object_hash=source_hash,
                ingestion_run_id=ingestion_run_id,
                target_record_type="OrderLine",
                target_record_id=order_line_id,
                target_field_path=identity_name,
                source_key=source_key,
                source_field_path=mapping["source_path"],
                source_value=identity_values[identity_name],
                known_at=commitment_known_at,
                available_at=commitment_available_at,
                transformation_rule_id=mapping["rule_id"],
                transformation_rule_version=mapping["rule_version"],
            )
            observations.setdefault(observation["source_observation_id"], observation)

        for field_name, mapping in field_mappings.items():
            raw_field = _mapped_value(row, mapping["source_path"])
            if raw_field is _MISSING:
                continue
            observation = _source_observation(
                dataset_id=dataset_id,
                source_object_hash=source_hash,
                ingestion_run_id=ingestion_run_id,
                target_record_type="OrderLine",
                target_record_id=order_line_id,
                target_field_path=f"fields.{field_name}",
                source_key=source_key,
                source_field_path=mapping["source_path"],
                source_value=raw_field,
                known_at=commitment_known_at,
                available_at=commitment_available_at,
                transformation_rule_id=mapping["rule_id"],
                transformation_rule_version=mapping["rule_version"],
            )
            observations.setdefault(observation["source_observation_id"], observation)

    unique_findings = {
        finding["validation_finding_id"]: finding for finding in findings
    }
    findings = list(unique_findings.values())
    semantic_records = {
        "OrderLine": sorted(semantic_lines.values(), key=lambda item: item["order_line_id"]),
        "OrderLineEvent": sorted(semantic_events.values(), key=lambda item: item["event_id"]),
        "SourceObservation": sorted(observations.values(), key=lambda item: item["source_observation_id"]),
        "ValidationFinding": sorted(
            [
                {key: value for key, value in finding.items() if key != "ingestion_run_id"}
                for finding in findings
            ],
            key=lambda item: item["validation_finding_id"],
        ),
    }
    semantic_hashes = {
        record_type: _sha256(
            [
                {
                    key: value
                    for key, value in record.items()
                    if key not in {"ingestion_run_id", "ingested_at"}
                }
                for record in records
            ]
        )
        for record_type, records in sorted(semantic_records.items())
    }
    semantic_content = {
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "mapping_manifest_id": HERO_MAPPING_MANIFEST_ID,
        "mapping_manifest_hash": mapping_hash,
        "input_hashes": [source_hash, mapping_hash],
        "semantic_payload_hashes": semantic_hashes,
    }
    dataset_version_id = _sha256(semantic_content)
    published_records = {
        record_type: [
            _with_dataset_version(record, dataset_version_id)
            for record in records
        ]
        for record_type, records in semantic_records.items()
    }

    for record in published_records["SourceObservation"]:
        record["ingestion_run_id"] = ingestion_run_id
    for record in published_records["ValidationFinding"]:
        record["ingestion_run_id"] = ingestion_run_id
    for record in published_records["OrderLineEvent"]:
        record["ingested_at"] = publication_time

    validation_summary = _summary(findings)
    output_hashes = {
        record_type: _sha256(records)
        for record_type, records in sorted(published_records.items())
    }
    dataset_version = {
        "dataset_id": dataset_id,
        "dataset_version_id": dataset_version_id,
        "predecessor_dataset_version_id": _field("missing"),
        "source_kind": manifest["source_kind"],
        "intended_role": manifest["intended_role"],
        "source_role_ceiling": _role_ceiling(str(manifest["intended_role"])),
        "canonical_schema_version": manifest["canonical_schema_version"],
        "adapter_id": manifest["adapter_id"],
        "adapter_version": manifest["adapter_version"],
        "source_schema_id": manifest["source_schema_id"],
        "source_schema_version": manifest["source_schema_version"],
        "mapping_manifest_id": manifest["mapping_manifest_id"],
        "input_hashes": [source_hash, mapping_hash],
        "semantic_payload_hashes": list(semantic_hashes.values()),
        "output_hashes": list(output_hashes.values()),
        "first_published_at": publication_time,
        "first_published_by_run_id": ingestion_run_id,
        "record_counts": {
            "order_lines": len(published_records["OrderLine"]),
            "order_line_events": len(published_records["OrderLineEvent"]),
            "source_observations": len(published_records["SourceObservation"]),
            "validation_findings": len(published_records["ValidationFinding"]),
            "quarantine_records": 0,
        },
        "mapping_assumptions": manifest["mapping_assumptions"],
        "validation_summary": validation_summary,
        "license_and_attribution_ref": _field("present", manifest["license_and_attribution_ref"]),
        "data_classification": manifest["data_classification"],
        "raw_redistribution_policy": {
            "policy": manifest["raw_redistribution_policy"],
            "explanation": "The bundled generated source is distributable with the repository.",
        },
        "derived_redistribution_policy": {
            "policy": manifest["derived_redistribution_policy"],
            "explanation": "Canonical generated lineage is distributable with the repository.",
        },
        "provenance_summary": {
            "origin": {"simulated": len(published_records["SourceObservation"])},
            "derivation": {"direct": 0, "normalized": len(published_records["SourceObservation"])},
            "calibration": {"none": len(published_records["SourceObservation"])},
        },
        "generator_metadata": _field("present", manifest["generator_metadata"]),
        "mapping_manifest": manifest,
    }
    return {
        "dataset_version": dataset_version,
        "records": published_records,
        "findings": findings,
        "source_hash": source_hash,
        "mapping_hash": mapping_hash,
        "semantic_content_hash": _sha256(semantic_content),
    }


def _build_public_bundle(
    *,
    dataset_key: str,
    ingestion_run_id: str,
    started_at: str,
) -> dict[str, Any]:
    spec = PUBLIC_ADAPTER_SPECS.get(dataset_key)
    if spec is None:
        raise IngestionRejected({"status": "FAILED"})
    source, manifest, source_hash, mapping_hash = _read_public_bundle(dataset_key)
    if (
        source.get("dataset_key") != spec.dataset_key
        or manifest.get("dataset_key") != spec.dataset_key
        or manifest.get("mapping_manifest_id") != spec.mapping_manifest_id
        or source.get("source_schema_id") != manifest.get("source_schema_id")
        or source.get("source_schema_version") != manifest.get("source_schema_version")
        or source.get("source_schema_id") != spec.source_schema_id
        or source.get("source_schema_version") != spec.source_schema_version
        or manifest.get("source_schema_id") != spec.source_schema_id
        or manifest.get("source_schema_version") != spec.source_schema_version
        or mapping_hash != spec.mapping_sha256
        or manifest.get("source_kind") != spec.source_kind
        or manifest.get("intended_role") != spec.intended_role
        or manifest.get("raw_redistribution_policy") != spec.raw_redistribution_policy
        or manifest.get("derived_redistribution_policy")
        != spec.derived_redistribution_policy
    ):
        raise IngestionRejected({"status": "FAILED"})

    identity_mappings = manifest.get("identity_mappings")
    field_mappings = manifest.get("field_mappings")
    event_mappings = manifest.get("event_mappings")
    if not isinstance(identity_mappings, Mapping) or not isinstance(field_mappings, Mapping):
        raise IngestionRejected({"status": "FAILED"})
    if set(identity_mappings) != {"order_line_id", "order_group_id", "supplier_id"}:
        raise IngestionRejected({"status": "FAILED"})
    if set(field_mappings) != {
        "material_class",
        "complexity_class",
        "quantity",
        "value",
        "project_id",
        "project_phase",
        "urgency_class",
        "geography_code",
        "contract_form",
    }:
        raise IngestionRejected({"status": "FAILED"})
    if not isinstance(event_mappings, Mapping) or not {
        "kind",
        "milestone_kind",
        "occurred_at",
        "known_at",
        "available_at",
        "promised_for",
    }.issubset(event_mappings):
        raise IngestionRejected({"status": "FAILED"})
    reviewed_source_fields = manifest.get("reviewed_source_fields")
    if not isinstance(reviewed_source_fields, list) or any(
        not isinstance(field, str) or not field for field in reviewed_source_fields
    ) or set(reviewed_source_fields) != spec.reviewed_source_fields:
        raise IngestionRejected({"status": "FAILED"})
    for mapping in identity_mappings.values():
        if (
            not isinstance(mapping, Mapping)
            or mapping.get("rule_id") not in _REVIEWED_PUBLIC_MAPPING_RULE_IDS
            or mapping.get("rule_version") != "1"
            or not _mapping_source_paths(mapping)
            or any(
                path not in spec.reviewed_source_fields
                for path in _mapping_source_paths(mapping)
            )
        ):
            raise IngestionRejected({"status": "FAILED"})
    for mapping in field_mappings.values():
        if (
            not isinstance(mapping, Mapping)
            or mapping.get("rule_id") not in _REVIEWED_PUBLIC_MAPPING_RULE_IDS
            or mapping.get("rule_version") != "1"
            or any(
                path not in spec.reviewed_source_fields
                for path in _mapping_source_paths(mapping)
            )
        ):
            raise IngestionRejected({"status": "FAILED"})
    rows = source.get("rows")
    if not isinstance(rows, list) or not rows or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise IngestionRejected({"status": "FAILED"})
    if {key for row in rows for key in row if isinstance(key, str)} != spec.reviewed_source_fields:
        raise IngestionRejected({"status": "FAILED"})

    transport_timing: Mapping[str, Any] | None = None
    rejection_mapping: Mapping[str, Any] | None = None
    canonical_events = event_mappings.get("canonical_events")
    if not isinstance(canonical_events, Mapping) or set(canonical_events) != {
        "committed",
        "promise_recorded",
        "milestone_reached",
    }:
        raise IngestionRejected({"status": "FAILED"})
    for descriptor in canonical_events.values():
        if (
            not isinstance(descriptor, Mapping)
            or descriptor.get("kind") not in _EVENT_KINDS
            or (
                descriptor.get("milestone_kind") != "not_applicable"
                and descriptor.get("milestone_kind") not in _MILESTONE_KINDS
            )
        ):
            raise IngestionRejected({"status": "FAILED"})
    if spec.source_kind == "olist":
        candidate = event_mappings.get("transport_timing")
        required = {
            "committed",
            "promised",
            "reached",
            "assumed_timezone",
            "promise_known_at",
        }
        if not isinstance(candidate, Mapping) or not required.issubset(candidate):
            raise IngestionRejected({"status": "FAILED"})
        if any(
            not isinstance(candidate.get(key), str)
            or (
                key not in {"assumed_timezone", "promise_known_at"}
                and candidate[key] not in spec.reviewed_source_fields
            )
            for key in required
        ) or candidate["promise_known_at"] not in {"committed", "unknown"}:
            raise IngestionRejected({"status": "FAILED"})
        transport_timing = candidate
    else:
        candidate = event_mappings.get("rejection_mapping")
        required = {
            "po_sent_to_vendor",
            "scheduled_delivery",
            "delivered_to_client",
            "delivery_recorded",
            "promise_known_at",
            "missingness_tokens",
        }
        if not isinstance(candidate, Mapping) or not required.issubset(candidate):
            raise IngestionRejected({"status": "FAILED"})
        if any(
            not isinstance(candidate.get(key), str)
            or candidate[key] not in spec.reviewed_source_fields
            for key in (
                "po_sent_to_vendor",
                "scheduled_delivery",
                "delivered_to_client",
                "delivery_recorded",
            )
        ):
            raise IngestionRejected({"status": "FAILED"})
        tokens = candidate["missingness_tokens"]
        if not isinstance(tokens, Mapping) or tokens != {
            "Date Not Captured": "unknown",
            "N/A - From RDC": "not_applicable",
        }:
            raise IngestionRejected({"status": "FAILED"})
        if candidate["promise_known_at"] != "unknown":
            raise IngestionRejected({"status": "FAILED"})
        rejection_mapping = candidate
    redistribution_permitted = (
        manifest["raw_redistribution_policy"] in {"allowed", "attribution_required"}
        and manifest["derived_redistribution_policy"]
        in {"allowed", "attribution_required"}
    )

    dataset_id = spec.dataset_key
    namespace = uuid5(NAMESPACE_URL, f"causal-delay-copilot:dataset:{dataset_id}")
    semantic_lines: dict[str, dict[str, Any]] = {}
    semantic_events: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    publication_time = started_at

    def add_finding(
        *,
        code: str,
        severity: str,
        disposition: str,
        scope: str,
        affected_refs: list[str],
        affected_count: int,
        rule_id: str,
        message: str,
        remediation: str,
    ) -> None:
        findings.append(
            _finding(
                ingestion_run_id=ingestion_run_id,
                code=code,
                severity=severity,
                disposition=disposition,
                scope=scope,
                affected_refs=affected_refs,
                affected_count=affected_count,
                rule_id=rule_id,
                message=message,
                remediation=remediation,
            )
        )

    for row in rows:
        if not isinstance(row, Mapping):
            add_finding(
                code="REQUIRED_ID_MISSING",
                severity="error",
                disposition="quarantine_record",
                scope="record",
                affected_refs=[],
                affected_count=1,
                rule_id=f"{spec.source_kind}.row-identity.v1",
                message="A public source row has no usable reviewed identity.",
                remediation="Repair the reviewed public mapping before importing.",
            )
            continue

        identity_values: dict[str, tuple[str, list[object]]] = {}
        for identity_name, mapping in identity_mappings.items():
            if not isinstance(mapping, Mapping):
                raise IngestionRejected({"status": "FAILED"})
            value = _public_identity_value(row, mapping)
            if value is _MISSING:
                identity_values = {}
                break
            identity_values[identity_name] = value
        if set(identity_values) != set(identity_mappings):
            add_finding(
                code="REQUIRED_ID_MISSING",
                severity="error",
                disposition="quarantine_record",
                scope="record",
                affected_refs=[],
                affected_count=1,
                rule_id=f"{spec.source_kind}.required-identities.v1",
                message="A public source row is missing a reviewed source identity.",
                remediation="Repair the source key mapping before importing.",
            )
            continue

        source_key = identity_values["order_line_id"][0]
        order_line_id = uuid5(namespace, f"order-line:{source_key}").hex
        order_group_id = uuid5(
            namespace, f"order-group:{identity_values['order_group_id'][0]}"
        ).hex
        supplier_id = uuid5(
            namespace, f"supplier:{identity_values['supplier_id'][0]}"
        ).hex
        fields: dict[str, dict[str, Any]] = {}
        for field_name, mapping in field_mappings.items():
            if not isinstance(mapping, Mapping):
                raise IngestionRejected({"status": "FAILED"})
            source_paths = _mapping_source_paths(mapping)
            raw_field = (
                _mapped_value(row, source_paths[0])
                if source_paths
                else _MISSING
            )
            fields[field_name] = _public_field(raw_field, mapping)
            if fields[field_name]["state"] == "invalid":
                add_finding(
                    code="VALUE_PARSE_FAILED",
                    severity="error",
                    disposition="invalidate_field",
                    scope="field",
                    affected_refs=[f"{order_line_id}.fields.{field_name}"],
                    affected_count=1,
                    rule_id=str(mapping["rule_id"]),
                    message="A public source value cannot be used as the declared canonical type.",
                    remediation="Keep the field unavailable until the reviewed mapping is repaired.",
                )

        candidate_line = {
            "order_line_id": order_line_id,
            "order_group_id": order_group_id,
            "supplier_id": supplier_id,
            "fields": fields,
        }
        existing_line = semantic_lines.get(order_line_id)
        if existing_line is None:
            semantic_lines[order_line_id] = candidate_line
        elif existing_line != candidate_line:
            add_finding(
                code="IDENTITY_COLLISION",
                severity="error",
                disposition="reject_run",
                scope="record",
                affected_refs=[order_line_id],
                affected_count=1,
                rule_id=f"uuid5.dataset.order-line.{spec.source_kind}.v1",
                message="Distinct public source content maps to one dataset-scoped Order Line identity.",
                remediation="Correct the reviewed source-key mapping before importing.",
            )
        else:
            add_finding(
                code="SOURCE_DUPLICATE_DEDUPED",
                severity="info",
                disposition="advisory",
                scope="record",
                affected_refs=[order_line_id],
                affected_count=1,
                rule_id=f"{spec.source_kind}.exact-row-deduplication.v1",
                message="An exact repeated public observation was deduplicated.",
                remediation="No action is required; the first canonical observation remains authoritative.",
            )

        events: list[dict[str, Any]] = []
        event_sources: list[dict[str, Any]] = []
        temporal_inputs: list[tuple[str, object, dict[str, Any], Mapping[str, str] | None]] = []
        commitment_known_at = _field("unresolved")
        commitment_available_at = _field("unresolved")
        committed_descriptor = canonical_events["committed"]
        promise_descriptor = canonical_events["promise_recorded"]
        reached_descriptor = canonical_events["milestone_reached"]
        if not all(
            isinstance(descriptor, Mapping)
            for descriptor in (
                committed_descriptor,
                promise_descriptor,
                reached_descriptor,
            )
        ):
            raise IngestionRejected({"status": "FAILED"})

        def descriptor_field(descriptor: Mapping[str, Any]) -> dict[str, Any]:
            milestone_kind = str(descriptor["milestone_kind"])
            return (
                _field("not_applicable")
                if milestone_kind == "not_applicable"
                else _field("present", milestone_kind)
            )

        if spec.source_kind == "olist":
            if transport_timing is None:
                raise IngestionRejected({"status": "FAILED"})
            committed_path = str(transport_timing["committed"])
            promised_path = str(transport_timing["promised"])
            reached_path = str(transport_timing["reached"])
            assumed_timezone = str(transport_timing["assumed_timezone"])
            committed_raw = _mapped_value(row, committed_path)
            promised_raw = _mapped_value(row, promised_path)
            reached_raw = _mapped_value(row, reached_path)
            purchase = _public_temporal(
                committed_raw,
                assumed_timezone=assumed_timezone,
            )
            promised = _public_temporal(
                promised_raw,
                assumed_timezone=assumed_timezone,
            )
            reached = _public_temporal(
                reached_raw,
                assumed_timezone=assumed_timezone,
            )
            temporal_inputs = [
                ("committed", committed_raw, purchase, None),
                ("promised", promised_raw, promised, None),
                ("reached", reached_raw, reached, None),
            ]
            promise_clock = (
                purchase
                if transport_timing["promise_known_at"] == "committed"
                else _field("unknown")
            )
            if purchase["state"] == "present":
                commitment_known_at = purchase
                commitment_available_at = purchase
                events.append(
                    {
                        "kind": committed_descriptor["kind"],
                        "milestone_kind": descriptor_field(committed_descriptor),
                        "occurred_at": purchase,
                        "known_at": purchase,
                        "available_at": purchase,
                        "promised_for": _field("not_applicable"),
                        "reason": _field("not_applicable"),
                        "revises_promise_event_id": _field("not_applicable"),
                    }
                )
                event_sources.append(
                    {
                        "kind": "committed",
                        "source_event_key": "committed",
                        "paths": {"occurred_at": committed_path},
                        "values": {"occurred_at": _mapped_value(row, committed_path)},
                    }
                )
            if promised["state"] in {"present", "unknown", "unresolved"}:
                events.append(
                    {
                        "kind": promise_descriptor["kind"],
                        "milestone_kind": descriptor_field(promise_descriptor),
                        "occurred_at": promise_clock,
                        "known_at": promise_clock,
                        "available_at": promise_clock,
                        "promised_for": promised,
                        "reason": _field("not_applicable"),
                        "revises_promise_event_id": _field("not_applicable"),
                    }
                )
                promise_paths = {"promised_for": promised_path}
                promise_values = {
                    "promised_for": _mapped_value(row, promised_path),
                }
                if transport_timing["promise_known_at"] == "committed":
                    promise_paths["occurred_at"] = committed_path
                    promise_values["occurred_at"] = _mapped_value(row, committed_path)
                event_sources.append(
                    {
                        "kind": promise_descriptor["kind"],
                        "source_event_key": "promise_recorded",
                        "paths": promise_paths,
                        "values": promise_values,
                    }
                )
            if reached["state"] == "present":
                events.append(
                    {
                        "kind": reached_descriptor["kind"],
                        "milestone_kind": descriptor_field(reached_descriptor),
                        "occurred_at": reached,
                        "known_at": _field("unknown"),
                        "available_at": _field("unknown"),
                        "promised_for": _field("not_applicable"),
                        "reason": _field("not_applicable"),
                        "revises_promise_event_id": _field("not_applicable"),
                    }
                )
                event_sources.append(
                    {
                        "kind": "milestone_reached",
                        "source_event_key": "milestone_reached",
                        "paths": {"occurred_at": reached_path},
                        "values": {
                            "occurred_at": _mapped_value(row, reached_path)
                        },
                    }
                )
        else:
            if rejection_mapping is None:
                raise IngestionRejected({"status": "FAILED"})
            po_path = str(rejection_mapping["po_sent_to_vendor"])
            scheduled_path = str(rejection_mapping["scheduled_delivery"])
            delivered_path = str(rejection_mapping["delivered_to_client"])
            recorded_path = str(rejection_mapping["delivery_recorded"])
            missingness_tokens = rejection_mapping["missingness_tokens"]
            po_raw = _mapped_value(row, po_path)
            scheduled_raw = _mapped_value(row, scheduled_path)
            delivered_raw = _mapped_value(row, delivered_path)
            recorded_raw = _mapped_value(row, recorded_path)
            po = _public_temporal(
                po_raw,
                missingness_tokens=missingness_tokens,
            )
            scheduled = _public_temporal(
                scheduled_raw,
                missingness_tokens=missingness_tokens,
            )
            delivered = _public_temporal(
                delivered_raw,
                missingness_tokens=missingness_tokens,
            )
            recorded = _public_temporal(
                recorded_raw,
                missingness_tokens=missingness_tokens,
            )
            temporal_inputs = [
                ("po_sent_to_vendor", po_raw, po, missingness_tokens),
                ("scheduled_delivery", scheduled_raw, scheduled, missingness_tokens),
                ("delivered_to_client", delivered_raw, delivered, missingness_tokens),
                ("delivery_recorded", recorded_raw, recorded, missingness_tokens),
            ]
            promise_known_at = _field(str(rejection_mapping["promise_known_at"]))
            if po["state"] == "present":
                events.append(
                    {
                        "kind": committed_descriptor["kind"],
                        "milestone_kind": descriptor_field(committed_descriptor),
                        "occurred_at": po,
                        "known_at": _field("unresolved"),
                        "available_at": _field("unresolved"),
                        "promised_for": _field("not_applicable"),
                        "reason": _field("not_applicable"),
                        "revises_promise_event_id": _field("not_applicable"),
                    }
                )
                event_sources.append(
                    {
                        "kind": "committed",
                        "source_event_key": "committed",
                        "paths": {"occurred_at": po_path},
                        "values": {"occurred_at": _mapped_value(row, po_path)},
                    }
                )
            if scheduled["state"] == "present":
                events.append(
                    {
                        "kind": promise_descriptor["kind"],
                        "milestone_kind": descriptor_field(promise_descriptor),
                        "occurred_at": _field("unknown"),
                        "known_at": promise_known_at,
                        "available_at": promise_known_at,
                        "promised_for": scheduled,
                        "reason": _field("not_applicable"),
                        "revises_promise_event_id": _field("not_applicable"),
                    }
                )
                event_sources.append(
                    {
                        "kind": "promise_recorded",
                        "source_event_key": "promise_recorded",
                        "paths": {"promised_for": scheduled_path},
                        "values": {
                            "promised_for": _mapped_value(row, scheduled_path),
                        },
                    }
                )
            if delivered["state"] == "present":
                known_at = recorded if recorded["state"] == "present" else _field("unknown")
                events.append(
                    {
                        "kind": reached_descriptor["kind"],
                        "milestone_kind": descriptor_field(reached_descriptor),
                        "occurred_at": delivered,
                        "known_at": known_at,
                        "available_at": known_at,
                        "promised_for": _field("not_applicable"),
                        "reason": _field("not_applicable"),
                        "revises_promise_event_id": _field("not_applicable"),
                    }
                )
                event_sources.append(
                    {
                        "kind": "milestone_reached",
                        "source_event_key": "milestone_reached",
                        "paths": {
                            "occurred_at": delivered_path,
                            "known_at": recorded_path,
                            "available_at": recorded_path,
                        },
                        "values": {
                            "occurred_at": _mapped_value(row, delivered_path),
                            "known_at": _mapped_value(row, recorded_path),
                            "available_at": _mapped_value(row, recorded_path),
                        },
                    }
                )
            if scheduled["state"] == "present":
                scheduled_value = scheduled.get("value")
                delivered_value = delivered.get("value")
                if (
                    isinstance(scheduled_value, Mapping)
                    and isinstance(delivered_value, Mapping)
                    and scheduled_value.get("normalized_value")
                    == delivered_value.get("normalized_value")
                ):
                    add_finding(
                        code="PROMISE_ACTUAL_EQUALITY_SUSPICIOUS",
                        severity="warning",
                        disposition="advisory",
                        scope="record",
                        affected_refs=[order_line_id],
                        affected_count=1,
                        rule_id="scms.scheduled-delivered-equality.v1",
                        message="The scheduled and delivered client dates are identical; the source promise may be backfilled.",
                        remediation="Retain this row as a rejection vignette and do not treat the client date as a supplier-controlled outcome.",
                    )

        for temporal_name, raw_temporal, temporal_value, missingness_tokens in temporal_inputs:
            if temporal_value["state"] != "invalid":
                continue
            failure_code = _public_temporal_failure_code(
                raw_temporal,
                missingness_tokens=missingness_tokens,
            )
            if failure_code is None:
                continue
            add_finding(
                code=failure_code,
                severity="error",
                disposition="invalidate_field",
                scope="field",
                affected_refs=[f"{order_line_id}.events.{temporal_name}"],
                affected_count=1,
                rule_id=f"{spec.source_kind}.temporal-mapping.v1",
                message=(
                    "A public temporal token is not a reviewed timestamp."
                    if failure_code == "TIMESTAMP_INVALID"
                    else "A public missingness token has no reviewed mapping."
                ),
                remediation="Keep the temporal field unavailable until the reviewed mapping is repaired.",
            )

        if not events:
            add_finding(
                code="ADAPTER_CONTRACT_VIOLATION",
                severity="error",
                disposition="quarantine_record",
                scope="record",
                affected_refs=[order_line_id],
                affected_count=1,
                rule_id=f"{spec.source_kind}.event-presence.v1",
                message="The public source row has no mapped canonical event.",
                remediation="Retain the row only after a reviewed event mapping is available.",
            )

        for event, source_info in zip(events, event_sources, strict=True):
            event_key = f"{source_key}|{source_info['source_event_key']}"
            event_id = uuid5(namespace, f"event:{event_key}").hex
            candidate_event = {
                "event_id": event_id,
                "order_line_id": order_line_id,
                "kind": event["kind"],
                "milestone_kind": event["milestone_kind"],
                "clocks": {
                    "occurred_at": event["occurred_at"],
                    "known_at": event["known_at"],
                    "available_at": event["available_at"],
                },
                "ingested_at": publication_time,
                "promised_for": event["promised_for"],
                "reason": event["reason"],
                "revises_promise_event_id": event["revises_promise_event_id"],
                "supersedes_event_id": _field("missing"),
            }
            existing_event = semantic_events.get(event_id)
            if existing_event is None:
                semantic_events[event_id] = candidate_event
            elif {
                key: value for key, value in existing_event.items() if key != "ingested_at"
            } != {
                key: value for key, value in candidate_event.items() if key != "ingested_at"
            }:
                add_finding(
                    code="EVENT_ID_CONTENT_CONFLICT",
                    severity="error",
                    disposition="reject_run",
                    scope="run",
                    affected_refs=[event_id],
                    affected_count=1,
                    rule_id=f"{spec.source_kind}.event-content.v1",
                    message="One deterministic public event identity has conflicting canonical content.",
                    remediation="Repair the reviewed source event mapping before importing.",
                )
            else:
                add_finding(
                    code="SOURCE_DUPLICATE_DEDUPED",
                    severity="info",
                    disposition="advisory",
                    scope="record",
                    affected_refs=[event_id],
                    affected_count=1,
                    rule_id=f"{spec.source_kind}.exact-event-deduplication.v1",
                    message="An exact repeated public event observation was deduplicated.",
                    remediation="No action is required; the first event remains authoritative.",
                )

            if event["known_at"]["state"] != "present":
                add_finding(
                    code="KNOWN_AT_UNKNOWN",
                    severity="warning",
                    disposition="advisory",
                    scope="record",
                    affected_refs=[event_id],
                    affected_count=1,
                    rule_id=f"{spec.source_kind}.known-at-preserved.v1",
                    message="The public source does not establish when this event became known.",
                    remediation="Keep the event visible but exclude it where decision-time knowledge is required.",
                )
            occurred_value = event["occurred_at"].get("value")
            if (
                isinstance(occurred_value, Mapping)
                and occurred_value.get("timezone_status") == "assumed"
            ):
                add_finding(
                    code="TIMEZONE_ASSUMED",
                    severity="warning",
                    disposition="advisory",
                    scope="field",
                    affected_refs=[f"{event_id}.occurred_at"],
                    affected_count=1,
                    rule_id="olist.timestamps-assume-brt.v1",
                    message="The public timestamp was normalized with the manifest's declared timezone assumption.",
                    remediation="Keep the assumption visible and do not treat it as source-provided timezone evidence.",
                )

            for field_name, source_path in source_info["paths"].items():
                source_value = source_info["values"].get(field_name, _MISSING)
                observation = _source_observation(
                    dataset_id=dataset_id,
                    source_object_hash=source_hash,
                    ingestion_run_id=ingestion_run_id,
                    target_record_type="OrderLineEvent",
                    target_record_id=event_id,
                    target_field_path=(
                        "clocks." + field_name
                        if field_name in {"occurred_at", "known_at", "available_at"}
                        else field_name
                    ),
                    source_key=source_key,
                    source_field_path=source_path,
                    source_value=None if source_value is _MISSING else source_value,
                    known_at=event["known_at"],
                    available_at=event["available_at"],
                    transformation_rule_id=f"{spec.source_kind}.transport-mapping.v1",
                    origin="observed",
                    derivation="normalized",
                    redistribution_permitted=redistribution_permitted,
                )
                observations.setdefault(observation["source_observation_id"], observation)

        identity_known_at = commitment_known_at
        identity_available_at = commitment_available_at
        for identity_name, mapping in identity_mappings.items():
            values = identity_values[identity_name]
            observation = _source_observation(
                dataset_id=dataset_id,
                source_object_hash=source_hash,
                ingestion_run_id=ingestion_run_id,
                target_record_type="OrderLine",
                target_record_id=order_line_id,
                target_field_path=identity_name,
                source_key=source_key,
                source_field_path=" + ".join(_mapping_source_paths(mapping)),
                source_value=values[1],
                known_at=identity_known_at,
                available_at=identity_available_at,
                transformation_rule_id=str(mapping["rule_id"]),
                transformation_rule_version=str(mapping.get("rule_version", "1")),
                origin="observed",
                derivation="normalized",
                redistribution_permitted=redistribution_permitted,
            )
            observations.setdefault(observation["source_observation_id"], observation)

        for field_name, mapping in field_mappings.items():
            if not isinstance(mapping, Mapping):
                continue
            source_paths = _mapping_source_paths(mapping)
            raw_field = _mapped_value(row, source_paths[0]) if source_paths else _MISSING
            if fields[field_name]["state"] != "present" or raw_field is _MISSING:
                if fields[field_name]["state"] != "present":
                    continue
                if "fixed_value" not in mapping or source_paths:
                    continue
                observation_source_hash = mapping_hash
                observation_source_field_path = f"mapping.{field_name}.fixed_value"
                observation_source_value = mapping["fixed_value"]
            else:
                observation_source_hash = source_hash
                observation_source_field_path = source_paths[0]
                observation_source_value = raw_field
            observation = _source_observation(
                dataset_id=dataset_id,
                source_object_hash=observation_source_hash,
                ingestion_run_id=ingestion_run_id,
                target_record_type="OrderLine",
                target_record_id=order_line_id,
                target_field_path=f"fields.{field_name}",
                source_key=source_key,
                source_field_path=observation_source_field_path,
                source_value=observation_source_value,
                known_at=identity_known_at,
                available_at=identity_available_at,
                transformation_rule_id=str(mapping["rule_id"]),
                transformation_rule_version=str(mapping.get("rule_version", "1")),
                origin="observed",
                derivation="normalized",
                redistribution_permitted=redistribution_permitted,
            )
            observations.setdefault(observation["source_observation_id"], observation)

    unique_findings = {finding["validation_finding_id"]: finding for finding in findings}
    findings = list(unique_findings.values())
    semantic_records = {
        "OrderLine": sorted(semantic_lines.values(), key=lambda item: item["order_line_id"]),
        "OrderLineEvent": sorted(semantic_events.values(), key=lambda item: item["event_id"]),
        "SourceObservation": sorted(
            observations.values(), key=lambda item: item["source_observation_id"]
        ),
        "ValidationFinding": sorted(
            [
                {key: value for key, value in finding.items() if key != "ingestion_run_id"}
                for finding in findings
            ],
            key=lambda item: item["validation_finding_id"],
        ),
    }
    semantic_hashes = {
        record_type: _sha256(
            [
                {
                    key: value
                    for key, value in record.items()
                    if key not in {"ingestion_run_id", "ingested_at"}
                }
                for record in records
            ]
        )
        for record_type, records in sorted(semantic_records.items())
    }
    semantic_content = {
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "source_schema_id": manifest["source_schema_id"],
        "source_schema_version": manifest["source_schema_version"],
        "adapter_id": manifest["adapter_id"],
        "adapter_version": manifest["adapter_version"],
        "mapping_manifest_id": manifest["mapping_manifest_id"],
        "mapping_manifest_hash": mapping_hash,
        "input_hashes": [source_hash, mapping_hash],
        "mapping_assumptions": manifest["mapping_assumptions"],
        "semantic_payload_hashes": semantic_hashes,
    }
    dataset_version_id = _sha256(semantic_content)
    published_records = {
        record_type: [_with_dataset_version(record, dataset_version_id) for record in records]
        for record_type, records in semantic_records.items()
    }
    for record in published_records["SourceObservation"]:
        record["ingestion_run_id"] = ingestion_run_id
    for record in published_records["ValidationFinding"]:
        record["ingestion_run_id"] = ingestion_run_id
    for record in published_records["OrderLineEvent"]:
        record["ingested_at"] = publication_time

    validation_summary = _summary(findings)
    output_hashes = {
        record_type: _sha256(records)
        for record_type, records in sorted(published_records.items())
    }
    source_object = source.get("source_object")
    if not isinstance(source_object, Mapping):
        raise IngestionRejected({"status": "FAILED"})
    source_objects = [
        {
            "logical_name": source_object.get("logical_name", spec.source_file.name),
            "sha256": source_hash,
            "size": spec.source_file.stat().st_size,
            "protected_locator": source_object.get(
                "protected_locator", f"bundled://{dataset_id}/source"
            ),
        },
        {
            "logical_name": spec.mapping_file.name,
            "sha256": mapping_hash,
            "size": spec.mapping_file.stat().st_size,
            "protected_locator": f"bundled://{dataset_id}/mapping",
        },
    ]
    dataset_version = {
        "dataset_id": dataset_id,
        "dataset_version_id": dataset_version_id,
        "predecessor_dataset_version_id": _field("missing"),
        "source_kind": manifest["source_kind"],
        "intended_role": manifest["intended_role"],
        "source_role_ceiling": _role_ceiling(str(manifest["intended_role"])),
        "canonical_schema_version": manifest["canonical_schema_version"],
        "adapter_id": manifest["adapter_id"],
        "adapter_version": manifest["adapter_version"],
        "source_schema_id": manifest["source_schema_id"],
        "source_schema_version": manifest["source_schema_version"],
        "mapping_manifest_id": manifest["mapping_manifest_id"],
        "input_hashes": [source_hash, mapping_hash],
        "semantic_payload_hashes": list(semantic_hashes.values()),
        "output_hashes": list(output_hashes.values()),
        "first_published_at": publication_time,
        "first_published_by_run_id": ingestion_run_id,
        "record_counts": {
            "order_lines": len(published_records["OrderLine"]),
            "order_line_events": len(published_records["OrderLineEvent"]),
            "source_observations": len(published_records["SourceObservation"]),
            "validation_findings": len(published_records["ValidationFinding"]),
            "quarantine_records": sum(
                int(finding["affected_count"])
                for finding in findings
                if finding["disposition"] == "quarantine_record"
            ),
        },
        "mapping_assumptions": manifest["mapping_assumptions"],
        "validation_summary": validation_summary,
        "license_and_attribution_ref": _field(
            "present", manifest["license_and_attribution_ref"]
        ),
        "data_classification": manifest["data_classification"],
        "raw_redistribution_policy": {
            "policy": manifest["raw_redistribution_policy"],
            "explanation": "Raw public source content remains protected; only the registered read model is exposed.",
        },
        "derived_redistribution_policy": {
            "policy": manifest["derived_redistribution_policy"],
            "explanation": "Derived lineage is limited to the declared public-data role and attribution policy.",
        },
        "provenance_summary": {
            "origin": {"observed": len(published_records["SourceObservation"])},
            "derivation": {"normalized": len(published_records["SourceObservation"])},
            "calibration": {"none": len(published_records["SourceObservation"])},
        },
        "generator_metadata": _field("not_applicable"),
        "mapping_manifest": manifest,
    }
    return {
        "dataset_version": dataset_version,
        "records": published_records,
        "findings": findings,
        "source_hash": source_hash,
        "mapping_hash": mapping_hash,
        "source_objects": source_objects,
        "semantic_content_hash": _sha256(semantic_content),
    }


def _run_payload(
    *,
    run_id: str,
    idempotency_key: str,
    dataset_key: str,
    started_at: str,
    completed_at: str,
    status: str,
    dataset_version_id: str | None,
    bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    if bundle is None:
        public_spec = PUBLIC_ADAPTER_SPECS.get(dataset_key)
        if public_spec is None:
            adapter_id = "semi-synthetic-hero-adapter"
            adapter_version = "1.0.0"
            source_schema_id = "semi-synthetic-construction"
            source_schema_version = "semi-synthetic-construction.v1"
        else:
            adapter_id = f"{public_spec.source_kind}-adapter"
            adapter_version = "1.0.0"
            source_schema_id = public_spec.source_kind
            source_schema_version = f"{public_spec.source_kind}.v1"
        return {
            "ingestion_run_id": run_id,
            "idempotency_key": idempotency_key,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "source_schema_id": source_schema_id,
            "source_schema_version": source_schema_version,
            "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
            "source_objects": [],
            "mapping_assumptions": [],
            "started_at": started_at,
            "completed_at": _field("present", completed_at),
            "status": status,
            "published_dataset_version_id": _field("missing"),
            "validation_summary": _field("present", {"total": 1}),
            "validation_finding_ids": _field("present", []),
        }
    findings = bundle["findings"]
    dataset_version = bundle["dataset_version"]
    published_dataset_version = (
        _field("present", dataset_version_id)
        if status == "SUCCEEDED" and dataset_version_id is not None
        else _field("missing")
    )
    return {
        "ingestion_run_id": run_id,
        "idempotency_key": idempotency_key,
        "adapter_id": dataset_version["adapter_id"],
        "adapter_version": dataset_version["adapter_version"],
        "source_schema_id": dataset_version["source_schema_id"],
        "source_schema_version": dataset_version["source_schema_version"],
        "canonical_schema_version": dataset_version["canonical_schema_version"],
        "source_objects": [
            *bundle.get(
                "source_objects",
                [
                    {
                        "logical_name": "semi_synthetic_hero.json",
                        "sha256": bundle["source_hash"],
                        "size": HERO_SOURCE_FILE.stat().st_size,
                        "protected_locator": "bundled://semi-synthetic-hero/source",
                    },
                    {
                        "logical_name": "semi_synthetic_hero.mapping.json",
                        "sha256": bundle["mapping_hash"],
                        "size": HERO_MAPPING_FILE.stat().st_size,
                        "protected_locator": "bundled://semi-synthetic-hero/mapping",
                    },
                ],
            )
        ],
        "mapping_assumptions": dataset_version["mapping_assumptions"],
        "started_at": started_at,
        "completed_at": _field("present", completed_at),
        "status": status,
        "published_dataset_version_id": published_dataset_version,
        "validation_summary": _field("present", dataset_version["validation_summary"]),
        "validation_finding_ids": _field(
            "present",
            [finding["validation_finding_id"] for finding in findings],
        ),
    }


def _insert_ingestion_run(
    connection: sqlite3.Connection,
    *,
    run: dict[str, Any],
    request_hash: str,
    dataset_key: str,
    mapping_manifest_id: str,
    status: str,
    dataset_version_id: str | None,
    started_at: str,
    completed_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO ingestion_runs (
            ingestion_run_id, idempotency_key, request_hash, dataset_key,
            mapping_manifest_id, status, dataset_version_id, started_at,
            completed_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run["ingestion_run_id"],
            run["idempotency_key"],
            request_hash,
            dataset_key,
            mapping_manifest_id,
            status,
            dataset_version_id,
            started_at,
            completed_at,
            _canonical_json(run),
        ),
    )


class LineageStore(
    DurableOperationsMixin,
    ReactiveInvestigationMixin,
    GovernanceMixin,
    AuditStore,
):
    """The single SQLite writer for audit events and immutable intake records."""

    def initialize(self) -> None:
        super().initialize()
        try:
            connection = self._connection_or_raise()
            ensure_ingestion_schema(connection, create=False)
            ensure_risk_schema(connection, create=False)
            ensure_governance_schema(connection, create=False)
            ensure_operation_schema(connection, create=False)
        except sqlite3.Error:
            self.close()
            raise

    def import_dataset(
        self,
        *,
        idempotency_key: str,
        dataset_key: str,
        mapping_manifest_id: str,
        now: datetime | None = None,
    ) -> IngestionResult:
        public_spec = PUBLIC_ADAPTER_SPECS.get(dataset_key)
        if dataset_key == HERO_DATASET_KEY:
            expected_mapping_manifest_id = HERO_MAPPING_MANIFEST_ID
        elif public_spec is not None:
            expected_mapping_manifest_id = public_spec.mapping_manifest_id
        else:
            expected_mapping_manifest_id = ""
        if mapping_manifest_id != expected_mapping_manifest_id:
            raise IngestionRejected({"status": "FAILED"})
        request_hash = _sha256(
            {
                "dataset_key": dataset_key,
                "mapping_manifest_id": mapping_manifest_id,
            }
        )
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT ingestion_run_id, request_hash, status, dataset_version_id, payload_json
                    FROM ingestion_runs
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if str(existing["request_hash"]) != request_hash:
                        connection.rollback()
                        raise IngestionIdempotencyConflict
                    connection.commit()
                    run = json.loads(str(existing["payload_json"]))
                    return IngestionResult(
                        result="IDEMPOTENT_REPLAY",
                        ingestion_run_id=str(existing["ingestion_run_id"]),
                        dataset_version_id=(
                            str(existing["dataset_version_id"])
                            if existing["dataset_version_id"] is not None
                            else None
                        ),
                        status=str(existing["status"]),
                        run=run,
                    )

                started_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
                run_id = uuid4().hex
                completed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
                try:
                    bundle = (
                        _build_bundle(ingestion_run_id=run_id, started_at=started_at)
                        if dataset_key == HERO_DATASET_KEY
                        else _build_public_bundle(
                            dataset_key=dataset_key,
                            ingestion_run_id=run_id,
                            started_at=started_at,
                        )
                    )
                except (IngestionRejected, KeyError, OSError, TypeError, ValueError) as error:
                    run = _run_payload(
                        run_id=run_id,
                        idempotency_key=idempotency_key,
                        dataset_key=dataset_key,
                        started_at=started_at,
                        completed_at=completed_at,
                        status="FAILED",
                        dataset_version_id=None,
                        bundle=None,
                    )
                    _insert_ingestion_run(
                        connection,
                        run=run,
                        request_hash=request_hash,
                        dataset_key=dataset_key,
                        mapping_manifest_id=mapping_manifest_id,
                        status="FAILED",
                        dataset_version_id=None,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    connection.commit()
                    raise IngestionRejected(run) from error

                if any(
                    finding["disposition"] == "reject_run"
                    for finding in bundle["findings"]
                ):
                    run = _run_payload(
                        run_id=run_id,
                        idempotency_key=idempotency_key,
                        dataset_key=dataset_key,
                        started_at=started_at,
                        completed_at=completed_at,
                        status="FAILED",
                        dataset_version_id=None,
                        bundle=bundle,
                    )
                    _insert_ingestion_run(
                        connection,
                        run=run,
                        request_hash=request_hash,
                        dataset_key=dataset_key,
                        mapping_manifest_id=mapping_manifest_id,
                        status="FAILED",
                        dataset_version_id=None,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    connection.commit()
                    raise IngestionRejected(run)

                dataset_version = bundle["dataset_version"]
                dataset_version_id = str(dataset_version["dataset_version_id"])
                existing_version = connection.execute(
                    """
                    SELECT dataset_version_id, payload_json, first_published_at, first_published_by_run_id
                    FROM dataset_versions
                    WHERE semantic_content_hash = ?
                    """,
                    (bundle["semantic_content_hash"],),
                ).fetchone()
                if existing_version is None:
                    connection.execute(
                        """
                        INSERT INTO dataset_versions (
                            dataset_version_id, dataset_id, semantic_content_hash,
                            first_published_at, first_published_by_run_id, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dataset_version_id,
                            dataset_version["dataset_id"],
                            bundle["semantic_content_hash"],
                            dataset_version["first_published_at"],
                            run_id,
                            _canonical_json(dataset_version),
                        ),
                    )
                    for record_type, records in bundle["records"].items():
                        for record in records:
                            connection.execute(
                                """
                                INSERT INTO lineage_records (
                                    dataset_version_id, record_type, record_id, payload_json
                                ) VALUES (?, ?, ?, ?)
                                """,
                                (
                                    dataset_version_id,
                                    record_type,
                                    str(
                                        record.get(
                                            {
                                                "OrderLine": "order_line_id",
                                                "OrderLineEvent": "event_id",
                                                "SourceObservation": "source_observation_id",
                                                "ValidationFinding": "validation_finding_id",
                                            }[record_type]
                                        )
                                    ),
                                    _canonical_json(record),
                                ),
                            )
                else:
                    dataset_version_id = str(existing_version["dataset_version_id"])
                    dataset_version = json.loads(str(existing_version["payload_json"]))

                run = _run_payload(
                    run_id=run_id,
                    idempotency_key=idempotency_key,
                    dataset_key=dataset_key,
                    started_at=started_at,
                    completed_at=completed_at,
                    status="SUCCEEDED",
                    dataset_version_id=dataset_version_id,
                    bundle=bundle,
                )
                _insert_ingestion_run(
                    connection,
                    run=run,
                    request_hash=request_hash,
                    dataset_key=dataset_key,
                    mapping_manifest_id=mapping_manifest_id,
                    status="SUCCEEDED",
                    dataset_version_id=dataset_version_id,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                connection.commit()
                return IngestionResult(
                    result="CREATED",
                    ingestion_run_id=run_id,
                    dataset_version_id=dataset_version_id,
                    status="SUCCEEDED",
                    run=run,
                )
            except (IngestionIdempotencyConflict, IngestionRejected):
                connection.rollback()
                raise
            except Exception:
                connection.rollback()
                raise

    def import_hero(
        self,
        *,
        idempotency_key: str,
        dataset_key: str,
        mapping_manifest_id: str,
        now: datetime | None = None,
    ) -> IngestionResult:
        return self.import_dataset(
            idempotency_key=idempotency_key,
            dataset_key=dataset_key,
            mapping_manifest_id=mapping_manifest_id,
            now=now,
        )

    def list_dataset_versions(self) -> list[dict[str, Any]]:
        with self._lock:
            connection = self._connection_or_raise()
            rows = connection.execute(
                """
                SELECT payload_json FROM dataset_versions
                ORDER BY dataset_id, dataset_version_id
                """
            ).fetchall()
        return [json.loads(str(row["payload_json"])) for row in rows]

    def get_lineage(self, dataset_version_id: str) -> dict[str, Any]:
        with self._lock:
            connection = self._connection_or_raise()
            version_row = connection.execute(
                """
                SELECT payload_json FROM dataset_versions
                WHERE dataset_version_id = ?
                """,
                (dataset_version_id,),
            ).fetchone()
            if version_row is None:
                raise DatasetVersionUnavailable
            run_row = connection.execute(
                """
                SELECT payload_json FROM ingestion_runs
                WHERE dataset_version_id = ?
                ORDER BY started_at, ingestion_run_id
                LIMIT 1
                """,
                (dataset_version_id,),
            ).fetchone()
            records: dict[str, list[dict[str, Any]]] = {}
            for record_type in (
                "OrderLine",
                "OrderLineEvent",
                "SourceObservation",
                "ValidationFinding",
            ):
                rows = connection.execute(
                    """
                    SELECT payload_json FROM lineage_records
                    WHERE dataset_version_id = ? AND record_type = ?
                    ORDER BY record_id
                    """,
                    (dataset_version_id, record_type),
                ).fetchall()
                records[record_type] = [json.loads(str(row["payload_json"])) for row in rows]
        if run_row is None:
            raise DatasetVersionUnavailable
        return {
            "ingestion_run": json.loads(str(run_row["payload_json"])),
            "dataset_version": json.loads(str(version_row["payload_json"])),
            "mapping_manifest": json.loads(str(version_row["payload_json"])).get(
                "mapping_manifest", {}
            ),
            "order_lines": records["OrderLine"],
            "order_line_events": records["OrderLineEvent"],
            "source_observations": records["SourceObservation"],
            "validation_findings": records["ValidationFinding"],
        }

    def get_source_role_ceiling_for_occurrence(
        self,
        *,
        workspace_id: str,
        occurrence_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            connection = self._connection_or_raise()
            row = connection.execute(
                """
                SELECT dataset_versions.payload_json
                FROM lineage_snapshots
                JOIN dataset_versions
                  ON dataset_versions.dataset_version_id = lineage_snapshots.dataset_version_id
                WHERE lineage_snapshots.workspace_id = ?
                  AND lineage_snapshots.occurrence_id = ?
                """,
                (workspace_id, occurrence_id),
            ).fetchone()
        if row is None:
            return None
        dataset_version = json.loads(str(row["payload_json"]))
        ceiling = dataset_version.get("source_role_ceiling")
        return ceiling if isinstance(ceiling, dict) else None

    def bind_lineage_snapshot(
        self,
        *,
        workspace_id: str,
        dataset_version_id: str,
        now: datetime | None = None,
    ) -> LineageSnapshotBinding:
        current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._lock:
            connection = self._connection_or_raise()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT snapshot_id, dataset_version_id, occurrence_id, event_seq,
                           content_hash, created_at
                    FROM lineage_snapshots
                    WHERE workspace_id = ? AND dataset_version_id = ?
                    """,
                    (workspace_id, dataset_version_id),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return LineageSnapshotBinding(
                        snapshot_id=str(existing["snapshot_id"]),
                        dataset_version_id=str(existing["dataset_version_id"]),
                        occurrence_id=str(existing["occurrence_id"]),
                        event_seq=int(existing["event_seq"]),
                        content_hash=str(existing["content_hash"]),
                        created_at=str(existing["created_at"]),
                    )
                version = connection.execute(
                    """
                    SELECT payload_json FROM dataset_versions
                    WHERE dataset_version_id = ?
                    """,
                    (dataset_version_id,),
                ).fetchone()
                if version is None:
                    connection.rollback()
                    raise DatasetVersionUnavailable
                record_rows = connection.execute(
                    """
                    SELECT record_type, record_id, payload_json
                    FROM lineage_records
                    WHERE dataset_version_id = ?
                    ORDER BY record_type, record_id
                    """,
                    (dataset_version_id,),
                ).fetchall()
                snapshot_content = {
                    "dataset_version": json.loads(str(version["payload_json"])),
                    "records": [
                        {
                            "record_type": str(row["record_type"]),
                            "record_id": str(row["record_id"]),
                            "payload": json.loads(str(row["payload_json"])),
                        }
                        for row in record_rows
                    ],
                }
                content_hash = _sha256(snapshot_content)
                snapshot_id = _sha256(
                    {"workspace_id": workspace_id, "dataset_version_id": dataset_version_id, "content_hash": content_hash}
                )
                idempotency_key = f"lineage-snapshot-v1:{dataset_version_id}"
                mutation = self._record_mutation_locked(
                    workspace_id,
                    idempotency_key=idempotency_key,
                    mutation_kind="LINEAGE_SNAPSHOT",
                    content_hash=content_hash,
                    terminal_fresh_bundle=False,
                    now=current_time,
                )
                if mutation.replayed:
                    existing = connection.execute(
                        """
                        SELECT snapshot_id, dataset_version_id, occurrence_id, event_seq,
                               content_hash, created_at
                        FROM lineage_snapshots
                        WHERE workspace_id = ? AND dataset_version_id = ?
                        """,
                        (workspace_id, dataset_version_id),
                    ).fetchone()
                    if existing is None:
                        raise sqlite3.DatabaseError("lineage snapshot mutation has no snapshot row")
                    connection.commit()
                    return LineageSnapshotBinding(
                        snapshot_id=str(existing["snapshot_id"]),
                        dataset_version_id=str(existing["dataset_version_id"]),
                        occurrence_id=str(existing["occurrence_id"]),
                        event_seq=int(existing["event_seq"]),
                        content_hash=str(existing["content_hash"]),
                        created_at=str(existing["created_at"]),
                    )

                occurrence_id = uuid4().hex
                cursor = connection.execute(
                    """
                    INSERT INTO audit_events (
                        workspace_id, occurrence_id, idempotency_key,
                        occurrence_kind, outcome_code, content_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        occurrence_id,
                        idempotency_key,
                        "LINEAGE_SNAPSHOT_VIEW",
                        "LINEAGE_SNAPSHOT_BOUND",
                        content_hash,
                        current_time.isoformat(),
                    ),
                )
                if cursor.lastrowid is None:
                    raise sqlite3.DatabaseError("lineage snapshot event was not sequenced")
                event_seq = int(cursor.lastrowid)
                connection.execute(
                    """
                    INSERT INTO lineage_snapshots (
                        snapshot_id, workspace_id, dataset_version_id, content_hash,
                        occurrence_id, event_seq, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        workspace_id,
                        dataset_version_id,
                        content_hash,
                        occurrence_id,
                        event_seq,
                        current_time.isoformat(),
                    ),
                )
                connection.commit()
                return LineageSnapshotBinding(
                    snapshot_id=snapshot_id,
                    dataset_version_id=dataset_version_id,
                    occurrence_id=occurrence_id,
                    event_seq=event_seq,
                    content_hash=content_hash,
                    created_at=current_time.isoformat(),
                )
            except Exception:
                connection.rollback()
                raise
