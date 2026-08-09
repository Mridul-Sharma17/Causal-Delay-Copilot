from __future__ import annotations

import json
from pathlib import Path
import sys

from .analysis_runs import (
    FreshAnalysisFinalizationError,
    analysis_run_id_for_operation,
    estimate_primary_atte_and_context,
    finalize_fresh_analysis,
    materialize_propensity_and_s9,
)


def _write_typed_reproduction_failure(temporary_root: Path, code: str) -> None:
    (temporary_root / "analysis-run-failure.json").write_text(
        json.dumps(
            {
                "schema_version": "analysis-run-failure.v1",
                "failure_code": code,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        return 64
    operation_kind = sys.argv[1]
    temporary_root = Path(sys.argv[2])
    artifact_root = Path(sys.argv[3]) if len(sys.argv) == 4 else None
    if operation_kind in {"FRESH_ANALYSIS", "FRESH_REPRODUCTION"}:
        request_path = temporary_root / "analysis-run-request.json"
        if not request_path.is_file():
            # Preserve the legacy durable-boundary behavior for untyped callers.
            return 78
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict) or request.get("schema_version") != "analysis-run-admission.v1":
            return 78
        try:
            stage_result = materialize_propensity_and_s9(request["suite_request"])
            engine_result = estimate_primary_atte_and_context(
                request["suite_request"],
                stage_result,
            )
            if artifact_root is None:
                return 78
            result = finalize_fresh_analysis(
                artifact_root=artifact_root,
                analysis_run_id=analysis_run_id_for_operation(
                    temporary_root.name
                    if temporary_root.name.startswith("operation-")
                    else "operation-" + temporary_root.name
                ),
                admission=request,
                propensity_stage=stage_result,
                engine_result=engine_result,
            )
        except FreshAnalysisFinalizationError as error:
            if operation_kind == "FRESH_REPRODUCTION" and error.code in {
                "RUN_REPRODUCIBILITY_VIOLATION",
                "RUN_REPRODUCTION_TARGET_UNAVAILABLE",
            }:
                _write_typed_reproduction_failure(temporary_root, error.code)
                return 79
            result = {
                "schema_version": "analysis-run-execution-result.v1",
                "scientific_request_digest": request.get("scientific_request_digest"),
                "status": "failed",
                "reason_code": error.code,
                "failure_code": error.code,
                "estimator_executed": False,
                "primary_result": None,
                "safe_detail": {
                    "schema_version": "analysis-run-safe-detail.v1",
                    "execution_state": "failed",
                    "last_completed_stage": "S8_OUTCOME",
                    "variants": [],
                    "component_failures": [
                        {
                            "component": "fresh_analysis_finalization",
                            "variant_id": None,
                            "code": error.code,
                        }
                    ],
                    "estimator_executed": False,
                    "scope": "propensity_and_overlap_only",
                },
            }
        except Exception:
            result = {
                "schema_version": "analysis-run-execution-result.v1",
                "scientific_request_digest": request.get("scientific_request_digest"),
                "status": "failed",
                "reason_code": "ENGINE_INTERNAL_ERROR",
                "failure_code": "ENGINE_INTERNAL_ERROR",
                "estimator_executed": False,
                "primary_result": None,
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
