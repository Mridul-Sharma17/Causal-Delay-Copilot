from __future__ import annotations

import json
from pathlib import Path
import sys

from .analysis_runs import materialize_propensity_and_s9


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
        try:
            stage_result = materialize_propensity_and_s9(request["suite_request"])
            result = {
                "schema_version": "analysis-run-execution-result.v1",
                "scientific_request_digest": request["scientific_request_digest"],
                "status": stage_result["status"],
                "reason_code": stage_result["reason_code"],
                "failure_code": (
                    stage_result["reason_code"]
                    if stage_result["status"] == "failed"
                    else None
                ),
                "estimator_executed": False,
                "safe_detail": stage_result["safe_detail"],
            }
        except Exception:
            result = {
                "schema_version": "analysis-run-execution-result.v1",
                "scientific_request_digest": request.get("scientific_request_digest"),
                "status": "failed",
                "reason_code": "ENGINE_INTERNAL_ERROR",
                "failure_code": "ENGINE_INTERNAL_ERROR",
                "estimator_executed": False,
                "safe_detail": {
                    "schema_version": "analysis-run-safe-detail.v1",
                    "execution_state": "failed",
                    "last_completed_stage": "S8_OUTCOME",
                    "variants": [],
                    "component_failures": [
                        {
                            "component": "propensity_ensemble",
                            "variant_id": None,
                            "code": "ENGINE_INTERNAL_ERROR",
                        }
                    ],
                    "estimator_executed": False,
                    "scope": "propensity_and_overlap_only",
                },
            }
        (temporary_root / "analysis-run-result.json").write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
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
