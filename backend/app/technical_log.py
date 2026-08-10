from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from threading import RLock

from .canonical import canonical_json


TECHNICAL_LOG_MAX_BYTES = 256 * 1024
TECHNICAL_LOG_BACKUP_COUNT = 3
_ALLOWED_FIELDS = frozenset(
    {"timestamp", "component", "correlation_id", "lifecycle_code", "recovery_action"}
)
_ALLOWED_COMPONENTS = frozenset({"lifecycle", "operation_runner", "operation_store"})
_ALLOWED_CODES = frozenset(
    {
        "STOP_REQUESTED",
        "STOP_ALREADY_REQUESTED",
        "STOPPED",
        "STOP_TIMEOUT",
        "STOP_FAILED",
        "NO_PROCESS",
        "OPERATION_INTERRUPTED",
        "OPERATION_CANCEL_REQUESTED",
        "OPERATION_CANCELLED",
        "OPERATION_CANCELLATION_TIMEOUT",
        "OPERATION_ARTIFACT_QUARANTINE_FAILED",
        "FRESH_OPERATION_REFUSED_STOPPING",
        "LEDGER_FLUSHED",
        "TECHNICAL_LOG_FLUSHED",
    }
)
_ALLOWED_RECOVERY_ACTIONS = frozenset(
    {
        "NONE",
        "WAIT_FOR_STOP_TO_FINISH",
        "EXPLICIT_RETRY_AS_NEW_OPERATION",
        "RESTORE_CORE_STATE_AND_RETRY",
        "NO_PROCESS_TO_STOP",
        "CANCEL_ACTIVE_OPERATION_THROUGH_API",
    }
)
_CORRELATION_PATTERN = re.compile(r"^(?:operation|stop)-[0-9a-f-]{8,64}$")


class TechnicalLogError(RuntimeError):
    """The allow-listed technical log could not be written safely."""


class TechnicalLog:
    """A rotating, allow-listed technical lifecycle log with durable writes."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = TECHNICAL_LOG_MAX_BYTES,
        backup_count: int = TECHNICAL_LOG_BACKUP_COUNT,
    ) -> None:
        if max_bytes < 1 or backup_count < 1:
            raise ValueError("technical log rotation policy is invalid")
        self._path = Path(path)
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._lock = RLock()
        self._write_failed = False

    @property
    def path(self) -> Path:
        return self._path

    def emit(
        self,
        *,
        component: str,
        correlation_id: str,
        lifecycle_code: str,
        recovery_action: str,
        now: datetime | None = None,
    ) -> None:
        if component not in _ALLOWED_COMPONENTS:
            raise TechnicalLogError("technical log component is not allow-listed")
        if not _CORRELATION_PATTERN.fullmatch(correlation_id):
            raise TechnicalLogError("technical log correlation identity is invalid")
        if lifecycle_code not in _ALLOWED_CODES:
            raise TechnicalLogError("technical log lifecycle code is not allow-listed")
        if recovery_action not in _ALLOWED_RECOVERY_ACTIONS:
            raise TechnicalLogError("technical log recovery action is not allow-listed")
        timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        record = {
            "timestamp": timestamp,
            "component": component,
            "correlation_id": correlation_id,
            "lifecycle_code": lifecycle_code,
            "recovery_action": recovery_action,
        }
        if set(record) != _ALLOWED_FIELDS:
            raise TechnicalLogError("technical log record shape is invalid")
        line = (canonical_json(record) + "\n").encode("utf-8")
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_if_needed(len(line))
                with self._path.open("ab") as handle:
                    handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
            except (OSError, TypeError, ValueError) as error:
                self._write_failed = True
                raise TechnicalLogError("technical log is unavailable") from error

    def flush(self) -> None:
        with self._lock:
            try:
                if self._write_failed:
                    raise OSError("technical log write previously failed")
                if not self._path.exists():
                    return
                with self._path.open("ab") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as error:
                raise TechnicalLogError("technical log is unavailable") from error

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self._path.exists() or self._path.stat().st_size + incoming_bytes <= self._max_bytes:
            return
        oldest = self._path.with_name(f"{self._path.name}.{self._backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self._backup_count - 1, 0, -1):
            source = self._path.with_name(f"{self._path.name}.{index}")
            target = self._path.with_name(f"{self._path.name}.{index + 1}")
            if source.exists():
                os.replace(source, target)
        os.replace(self._path, self._path.with_name(f"{self._path.name}.1"))
