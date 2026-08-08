from __future__ import annotations


ADJUSTMENT_SET_FIELDS = (
    "material_class",
    "complexity_class",
    "quantity",
    "value",
    "project_id",
    "project_phase",
    "urgency_class",
    "geography_code",
    "contract_form",
)

SUPPORTED_TARGET_MILESTONE_KINDS = frozenset(
    {"supplier_completion", "supplier_handoff"}
)

LOAD_EXPOSURE_VARIANTS = (
    ("primary", 0.67, 10, "nearest-rank-percentile-0.67.v1"),
    ("stricter_threshold", 0.75, 10, "nearest-rank-percentile-0.75.v1"),
    ("short_history", 0.67, 5, "nearest-rank-percentile-0.67.v1"),
    ("long_history", 0.67, 20, "nearest-rank-percentile-0.67.v1"),
)
