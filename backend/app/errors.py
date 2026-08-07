from __future__ import annotations

from enum import StrEnum


class SafeErrorCode(StrEnum):
    """Registered redacted errors for the Core's public failure boundary."""

    CONFIGURATION_INVALID = "CORE_CONFIGURATION_INVALID"
    STATE_CORRUPT = "CORE_STATE_CORRUPT"
    STATE_INITIALIZATION_FAILED = "CORE_STATE_INITIALIZATION_FAILED"
    STATE_RELEASE_MISMATCH = "CORE_STATE_RELEASE_MISMATCH"
    DEMO_WORKSPACE_UNAVAILABLE = "DEMO_WORKSPACE_UNAVAILABLE"
    DEMO_WORKSPACE_CAPACITY_EXCEEDED = "DEMO_WORKSPACE_CAPACITY_EXCEEDED"
    DEMO_WORKSPACE_MUTATION_LIMIT_REACHED = "DEMO_WORKSPACE_MUTATION_LIMIT_REACHED"
    DEMO_WORKSPACE_RATE_LIMITED = "DEMO_WORKSPACE_RATE_LIMITED"
    DEMO_WORKSPACE_FRESH_BUNDLE_LIMIT_REACHED = (
        "DEMO_WORKSPACE_FRESH_BUNDLE_LIMIT_REACHED"
    )
    DEMO_WORKSPACE_IDEMPOTENCY_CONFLICT = "DEMO_WORKSPACE_IDEMPOTENCY_CONFLICT"
    DEMO_WORKSPACE_RESOURCE_UNAVAILABLE = "DEMO_WORKSPACE_RESOURCE_UNAVAILABLE"
    INGESTION_IDEMPOTENCY_CONFLICT = "INGESTION_IDEMPOTENCY_CONFLICT"
    DATASET_VERSION_UNAVAILABLE = "DATASET_VERSION_UNAVAILABLE"
    INGESTION_REJECTED = "INGESTION_REJECTED"


REGISTERED_SAFE_ERROR_CODES = frozenset(code.value for code in SafeErrorCode)


class CoreSafeError(RuntimeError):
    """A fail-closed error whose public representation contains no internals."""

    def __init__(self, code: SafeErrorCode, recovery_action: str) -> None:
        self.code = code
        self.recovery_action = recovery_action
        super().__init__(code.value)


class WorkspaceRequestError(RuntimeError):
    """A safe, redacted failure while resolving or mutating a Demo Workspace."""

    def __init__(
        self,
        code: SafeErrorCode,
        recovery_action: str,
        status_code: int,
    ) -> None:
        self.code = code
        self.recovery_action = recovery_action
        self.status_code = status_code
        super().__init__(code.value)
