from __future__ import annotations

from enum import StrEnum


class SafeErrorCode(StrEnum):
    """Registered redacted errors for configuration and sealed state."""

    CONFIGURATION_INVALID = "CORE_CONFIGURATION_INVALID"
    STATE_CORRUPT = "CORE_STATE_CORRUPT"
    STATE_INITIALIZATION_FAILED = "CORE_STATE_INITIALIZATION_FAILED"
    STATE_RELEASE_MISMATCH = "CORE_STATE_RELEASE_MISMATCH"


REGISTERED_SAFE_ERROR_CODES = frozenset(code.value for code in SafeErrorCode)


class CoreSafeError(RuntimeError):
    """A fail-closed error whose public representation contains no internals."""

    def __init__(self, code: SafeErrorCode, recovery_action: str) -> None:
        self.code = code
        self.recovery_action = recovery_action
        super().__init__(code.value)
