"""Rebuild the checked-in issue #37 causal-engine input snapshots.

The conformance tests consume the snapshot files directly. This builder is
review tooling only; it is never called by the application or by a pass/fail
test path.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from copy import deepcopy

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.analysis_runs import (  # noqa: E402
    CATEGORICAL_ADJUSTMENT_VOCABULARIES,
    scientific_sha256,
)
from backend.tests.test_analysis_runs import (  # noqa: E402
    _released_supported_primary_request,
    _released_supported_variants_request,
)


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "causal_engine" / "v1"
INPUT_ROOT = FIXTURE_ROOT / "inputs"


def _refresh_content_hash(variant: dict[str, object]) -> None:
    variant["s8_content_hash"] = scientific_sha256(
        {
            key: value
            for key, value in variant.items()
            if key not in {"s8_identity_hash", "s8_content_hash"}
        }
    )


def _declare_fixed_vocabularies(request: dict[str, object]) -> None:
    adjustment_set = request["adjustment_set"]
    assert isinstance(adjustment_set, dict)
    fields = adjustment_set["fields"]
    assert isinstance(fields, list)
    adjustment_set["field_definitions"] = [
        {
            "name": field,
            "logical_type": "typed_value",
            "estimation_encoding": "explicit_state_preserving",
            "pre_treatment": True,
            **(
                {"categories": deepcopy(CATEGORICAL_ADJUSTMENT_VOCABULARIES[field])}
                if field in CATEGORICAL_ADJUSTMENT_VOCABULARIES
                else {}
            ),
        }
        for field in fields
    ]


def _write_jsonl(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
        encoding="utf-8",
        newline="",
    )


def _extend_to_full_fit(request: dict[str, object]) -> dict[str, object]:
    variants = request["variant_inputs"]
    assert isinstance(variants, list)
    primary = variants[0]
    assert isinstance(primary, dict)
    rows = primary["rows"]
    assert isinstance(rows, list)
    fields = request["adjustment_set"]["fields"]
    categorical_values = {
        "material_class": ("class-a", "class-b"),
        "complexity_class": ("standard", "complex"),
        "project_id": ("project-a", "project-b"),
        "project_phase": ("substructure", "fitout"),
        "urgency_class": ("normal", "urgent"),
        "geography_code": ("north", "south"),
        "contract_form": ("lump-sum", "remeasure"),
    }
    for supplier_index in range(50):
        for extra_index in range(10):
            within_supplier = 20 + extra_index
            logical_index = supplier_index * 30 + within_supplier
            exposed = within_supplier % 2 == 1
            covariates = {
                field: {
                    "state": "present",
                    "value": (
                        float((supplier_index * 7 + (field == "value")) % 19)
                        if field in {"quantity", "value"}
                        else categorical_values[field][supplier_index % 2]
                    ),
                }
                for field in fields
            }
            rows.append(
                {
                    "order_line_id": f"line-supported-{1000 + supplier_index * 10 + extra_index:04d}",
                    "supplier_id": f"supplier-supported-{supplier_index:03d}",
                    "high_load_exposure": exposed,
                    "supplier_milestone_slippage_days": float(
                        (1.5 + (supplier_index % 5) * 0.03) * exposed
                        + (supplier_index % 5) * 0.1
                        + (within_supplier % 7) * 0.07
                    ),
                    "supplier_milestone_slippage_duration_basis": "CALENDAR_DAY",
                    "supplier_milestone_late": bool(
                        (logical_index + supplier_index * 7) % 7 == 0
                    ),
                    "load_percentile": 0.25 + (supplier_index % 10) / 20,
                    "covariates": covariates,
                    "lineage_refs": [
                        f"lineage:line-supported-{1000 + supplier_index * 10 + extra_index:04d}"
                    ],
                }
            )
    rows.sort(key=lambda row: str(row["order_line_id"]).encode("utf-8"))
    for variant in variants:
        if variant is not primary and variant.get("upstream_status") == "released":
            variant["rows"] = deepcopy(rows)
        elif variant is not primary:
            continue
        row_ids = [str(row["order_line_id"]) for row in variant["rows"]]
        variant["cohort_stage_summaries"] = {
            "S8_OUTCOME": {
                "status": "passed",
                "selected_count": len(row_ids),
                "selected_identity_hash": scientific_sha256(row_ids),
            }
        }
        variant["s8_identity_hash"] = scientific_sha256(row_ids)
        _refresh_content_hash(variant)
    return request


def _refresh_released_variants(request: dict[str, object]) -> None:
    variants = request["variant_inputs"]
    assert isinstance(variants, list)
    for variant in variants:
        assert isinstance(variant, dict)
        if variant.get("upstream_status") != "released":
            continue
        rows = variant["rows"]
        assert isinstance(rows, list)
        row_ids = [str(row["order_line_id"]) for row in rows]
        variant["s8_identity_hash"] = scientific_sha256(row_ids)
        _refresh_content_hash(variant)


def main() -> None:
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)

    full_fit = _released_supported_variants_request()
    full_fit["root_seed"] = 160016
    _declare_fixed_vocabularies(full_fit)
    _extend_to_full_fit(full_fit)
    _write_jsonl(INPUT_ROOT / "fixture_full_fit.jsonl", full_fit)

    constant_effect = deepcopy(full_fit)
    for variant in constant_effect["variant_inputs"]:
        if variant.get("upstream_status") != "released":
            continue
        for row in variant["rows"]:
            suffix = int(str(row["order_line_id"]).rsplit("-", 1)[-1])
            row["supplier_milestone_slippage_days"] = float(
                (suffix % 17) * 0.10 + (2.0 if row["high_load_exposure"] else 0.0)
            )
    _refresh_released_variants(constant_effect)
    _write_jsonl(INPUT_ROOT / "fixture_constant_effect.jsonl", constant_effect)

    atte_differs = deepcopy(full_fit)
    rows_by_supplier: dict[str, list[dict[str, object]]] = {}
    primary_rows = atte_differs["variant_inputs"][0]["rows"]
    for row in primary_rows:
        rows_by_supplier.setdefault(str(row["supplier_id"]), []).append(row)
    for supplier_id, supplier_rows in rows_by_supplier.items():
        supplier_index = int(supplier_id.rsplit("-", 1)[-1])
        high_effect_group = supplier_index < 25
        categorical_values = {
            "material_class": ("class-a", "class-b"),
            "complexity_class": ("standard", "complex"),
            "project_id": ("project-a", "project-b"),
            "project_phase": ("substructure", "fitout"),
            "urgency_class": ("normal", "urgent"),
            "geography_code": ("north", "south"),
            "contract_form": ("lump-sum", "remeasure"),
        }
        for local_index, row in enumerate(supplier_rows):
            row["high_load_exposure"] = (
                local_index < 24 if high_effect_group else local_index < 6
            )
            for field, values in categorical_values.items():
                row["covariates"][field]["value"] = values[0 if high_effect_group else 1]
            row["covariates"]["quantity"]["value"] = float(
                1.0 if high_effect_group else 18.0
            )
            row["covariates"]["value"]["value"] = float(
                (local_index % 5) + (0.0 if high_effect_group else 10.0)
            )
            row["supplier_milestone_slippage_days"] = float(
                (local_index % 11) * 0.08
                + (8.0 if high_effect_group else 1.0) * row["high_load_exposure"]
            )
    for variant in atte_differs["variant_inputs"][1:]:
        if variant.get("upstream_status") == "released":
            variant["rows"] = deepcopy(primary_rows)
    _refresh_released_variants(atte_differs)
    _write_jsonl(
        INPUT_ROOT / "fixture_atte_differs_from_ate.jsonl",
        atte_differs,
    )

    overlap_and_subject = deepcopy(full_fit)
    subject_row = overlap_and_subject["variant_inputs"][0]["rows"][0]
    subject_id = "fixture-current-subject"
    overlap_and_subject["subject"] = {
        "state": "eligible",
        "subject_id": subject_id,
        "profile": {
            "supplier_id": str(subject_row["supplier_id"]),
            "canonical_exposure": {
                "high_load_exposure": bool(subject_row["high_load_exposure"]),
                "load_percentile": float(subject_row["load_percentile"]),
            },
            "adjustment_inputs": deepcopy(subject_row["covariates"]),
            "decision_cutoff": "2026-01-01T00:00:00Z",
            "observation_cutoff": "2026-02-01T00:00:00Z",
            "target_milestone_kind": "supplier_completion",
            "subject_exclusion_identity": subject_id,
        },
        "eligibility_codes": [],
        "evidence_refs": ["fixture:overlap-and-subject"],
    }
    _write_jsonl(
        INPUT_ROOT / "fixture_overlap_and_subject.jsonl",
        overlap_and_subject,
    )

    unsupported = _released_supported_primary_request()
    unsupported["root_seed"] = 160016
    _declare_fixed_vocabularies(unsupported)
    _extend_to_full_fit(unsupported)
    primary = unsupported["variant_inputs"][0]
    assert isinstance(primary, dict)
    rows = primary["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["supplier_milestone_late"] = False
    _refresh_content_hash(primary)
    _write_jsonl(INPUT_ROOT / "fixture_unsupported_sensitivity.jsonl", unsupported)


if __name__ == "__main__":
    main()
