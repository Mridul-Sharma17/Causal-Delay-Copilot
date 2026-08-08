from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 3:
        return 64
    operation_kind = sys.argv[1]
    temporary_root = Path(sys.argv[2])
    if operation_kind != "BOUNDED_WORK":
        # The durable boundary exists before the scientific executor ticket; do
        # not manufacture an analysis result while that executor is unavailable.
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
