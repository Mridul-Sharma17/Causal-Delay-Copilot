from __future__ import annotations

from collections.abc import Mapping


SYNTHETIC_FIXTURE_NAMESPACE = "synthetic://core-decision-support/v1"
SYNTHETIC_FIXTURE_ID_PREFIX = "synthetic:core-decision-support-v1:"
SYNTHETIC_FIXTURE_ROLE = "synthetic_conformance"
SYNTHETIC_FIXTURE_SOURCE_KIND = "synthetic_conformance"

_IDENTITY_KEYS = frozenset(
    {
        "analysis_run_id",
        "bundle_manifest_hash",
        "dataset_id",
        "dataset_key",
        "dataset_version_id",
        "fixture_id",
        "fixture_pack_id",
        "investigation_request_id",
        "logical_id",
        "order_line_id",
        "pack_id",
        "preview_subject_digest",
        "reference_id",
        "reference_slot_id",
        "record_id",
        "review_reference",
        "source_namespace",
        "source_dataset_version_id",
        "subject_identity",
        "storage_namespace",
    }
)


def _synthetic_marker(value: object) -> bool:
    return isinstance(value, str) and (
        value == SYNTHETIC_FIXTURE_ROLE
        or value == SYNTHETIC_FIXTURE_SOURCE_KIND
        or value == SYNTHETIC_FIXTURE_NAMESPACE
        or value.startswith(SYNTHETIC_FIXTURE_NAMESPACE + "/")
        or value.startswith(SYNTHETIC_FIXTURE_ID_PREFIX)
    )


def is_synthetic_fixture_identity(value: object) -> bool:
    """Return whether an identity-bearing envelope uses the test-only namespace."""

    if isinstance(value, Mapping):
        for key, member in value.items():
            key_name = str(key)
            if key_name in {"intended_role", "source_kind"} and _synthetic_marker(
                member
            ):
                return True
            if key_name in _IDENTITY_KEYS and _synthetic_marker(member):
                return True
            if _synthetic_marker(member):
                return True
            if isinstance(
                member, (Mapping, list, tuple)
            ) and is_synthetic_fixture_identity(member):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(is_synthetic_fixture_identity(member) for member in value)
    return _synthetic_marker(value)
