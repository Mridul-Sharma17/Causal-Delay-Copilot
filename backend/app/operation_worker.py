from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 3:
        return 64
    operation_kind = sys.argv[1]
    temporary_root = Path(sys.argv[2])
    if operation_kind == "FRESH_ANALYSIS":
        request_path = temporary_root / "analysis-run-request.json"
        if not request_path.is_file():
            # Preserve the legacy durable-boundary behavior for untyped callers.
            return 78
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict) or request.get("schema_version") != "analysis-run-admission.v1":
            return 78
        (temporary_root / "analysis-run-result.json").write_text(
            json.dumps(
                {
                    "schema_version": "analysis-run-validation-result.v1",
                    "scientific_request_digest": request["scientific_request_digest"],
                    "status": "ABSTAINED",
                    "reason_code": "ENGINE_EXECUTION_DEFERRED",
                    "estimator_executed": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return 0
    if operation_kind != "BOUNDED_WORK":
        return 78
    (temporary_root / "bounded-work-result.json").write_text(
        json.dumps(
            {
                "schema_version": "bounded-work-result.v1",
                "operation_kind": operation_kind,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
