from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.hosted_qualification import (
    REQUIRED_HOSTED_CHECK_IDS,
    HostedQualificationError,
    build_hosted_attestation,
    verify_hosted_attestation,
    write_hosted_attestation,
)
from scripts.hosted_qualification import _write_failure_evidence


def _checks(*, blocked: str | None = None) -> list[dict[str, object]]:
    return [
        {
            "check_id": check_id,
            "status": "BLOCKED" if check_id == blocked else "VERIFIED",
            "code": "CHECK_BLOCKED" if check_id == blocked else "CHECK_PASSED",
            "evidence": {"source": "test"},
        }
        for check_id in REQUIRED_HOSTED_CHECK_IDS
    ]


def _attestation(*, checks: list[dict[str, object]] | None = None) -> dict[str, object]:
    return build_hosted_attestation(
        source_commit="a" * 40,
        release_candidate_id="rc-test",
        build_manifest_id="build-test",
        target={
            "profile": "HOSTED",
            "vercel_origin": "https://vercel.example.com",
            "railway_origin": "https://railway.example.com",
            "railway_project_id": "project-test",
            "railway_service_id": "service-test",
            "railway_environment_id": "environment-test",
        },
        checks=checks or _checks(),
        commands=[
            {
                "command": "gh api repos/example/project/commits/<sha>",
                "cli": "gh",
                "version": "2.0.0",
                "target": "github",
                "exit_status": 0,
                "redacted_output_digest": "sha256:" + "b" * 64,
            }
        ],
        platform={
            "budget_alert": {
                "state": "RECORDED",
                "threshold_usd": 4,
                "hard_cap": False,
                "external_verification": "UNAVAILABLE",
                "record_ref": "railway-alert-test",
                "actor": "test-operator",
                "observed_at": "2026-08-12T00:00:00+00:00",
                "source": "operator-recorded-Railway-billing-alert",
                "cli_gap": "Railway CLI 5.37.4 exposes no budget-alert resource",
            }
        },
        observed_at="2026-08-12T00:00:00+00:00",
    )


def test_hosted_attestation_is_qualified_only_when_every_required_check_passes() -> None:
    passed = _attestation()
    blocked = _attestation(checks=_checks(blocked="browser_reference_journey"))

    assert passed["qualification_status"] == "QUALIFIED"
    assert blocked["qualification_status"] == "BLOCKED"
    assert passed["content_hash"].startswith("sha256:")
    assert blocked["checks"][0]["status"] == "BLOCKED"


def test_hosted_attestation_round_trips_as_canonical_immutable_file(tmp_path: Path) -> None:
    payload = _attestation()
    written = write_hosted_attestation(tmp_path, payload)

    verified = verify_hosted_attestation(written)
    assert verified == payload
    assert written.name == "hosted-delivery-attestation.json"
    assert (tmp_path / "hosted-delivery-attestation.sha256").read_text(
        encoding="utf-8"
    ).startswith("sha256:")
    assert written.read_text(encoding="utf-8") == (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )

    with pytest.raises(HostedQualificationError, match="ATTESTATION_ALREADY_EXISTS"):
        write_hosted_attestation(tmp_path, _attestation(checks=_checks(blocked="queue_saturation")))

    (tmp_path / "hosted-delivery-attestation.sha256").unlink()
    with pytest.raises(HostedQualificationError, match="ATTESTATION_DIGEST_UNAVAILABLE"):
        verify_hosted_attestation(written)


def test_hosted_attestation_rejects_local_or_fallback_claims() -> None:
    with pytest.raises(HostedQualificationError, match="HOSTED_TARGET_REQUIRED"):
        build_hosted_attestation(
            source_commit="a" * 40,
            release_candidate_id="rc-test",
            build_manifest_id="build-test",
            target={"profile": "LOCAL_FALLBACK"},
            checks=_checks(),
            commands=[],
            platform={},
            observed_at="2026-08-12T00:00:00+00:00",
        )

    invalid = _attestation()
    invalid["target"] = {
        **invalid["target"],
        "fallback_used": True,
    }
    with pytest.raises(HostedQualificationError, match="FALLBACK_EVIDENCE_FORBIDDEN"):
        verify_hosted_attestation_payload(invalid)


def test_hosted_attestation_binds_budget_check_to_verified_platform_evidence() -> None:
    invalid = _attestation()
    invalid["platform"] = {"budget_alert": {"state": "UNAVAILABLE", "hard_cap": False}}

    with pytest.raises(HostedQualificationError, match="BUDGET_ALERT_CHECK_MISMATCH"):
        verify_hosted_attestation_payload(invalid)


def test_qualification_failure_has_typed_immutable_evidence(tmp_path: Path) -> None:
    path = _write_failure_evidence(tmp_path, "RELEASE_MANIFEST_INVALID")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "hosted-qualification-failure.v1"
    assert payload["status"] == "BLOCKED"
    assert payload["code"] == "RELEASE_MANIFEST_INVALID"
    assert (tmp_path / "hosted-qualification-failure.sha256").is_file()


def verify_hosted_attestation_payload(payload: dict[str, object]) -> None:
    """Exercise the public payload verifier without writing a second artifact."""

    from backend.app.hosted_qualification import validate_hosted_attestation

    validate_hosted_attestation(payload)
