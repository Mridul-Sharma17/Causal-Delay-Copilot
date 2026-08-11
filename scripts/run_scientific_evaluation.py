"""Run the frozen Core scientific evaluation and optionally publish its pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.evaluation import (  # noqa: E402
    build_frozen_evaluation_manifest,
    run_scientific_evaluation,
    verify_evidence_pack,
    write_evidence_pack,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the hash-bound Core scientific evaluation campaign."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Publish the offline evidence pack at this directory.",
    )
    parser.add_argument(
        "--verify-pack",
        type=Path,
        help="Verify an existing evidence pack instead of running the campaign.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.verify_pack is not None:
        verification = verify_evidence_pack(args.verify_pack)
        print(json.dumps(verification, sort_keys=True))
        return 0 if verification["state"] == "ACCEPTED" else 1
    manifest = build_frozen_evaluation_manifest()
    result = run_scientific_evaluation(
        manifest=manifest,
    )
    publication = None
    if args.output is not None:
        publication = write_evidence_pack(args.output, manifest=manifest, result=result)
    print(
        json.dumps(
            {
                "overall_status": result["overall_status"],
                "scope": result["scope"],
                "content_hash": result["content_hash"],
                "publication": publication,
            },
            sort_keys=True,
        )
    )
    return 0 if result["overall_status"] == "CORE_EVALUATION_ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
