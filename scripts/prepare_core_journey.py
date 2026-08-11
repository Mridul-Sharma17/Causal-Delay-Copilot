from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.settings import DeliveryProfile
from backend.tests.core_journey_support import (
    core_journey_settings,
    prepare_core_journey,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the issue-64 real API/SQLite/artifact browser journey."
    )
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument(
        "--profile",
        required=True,
        choices=[profile.value for profile in DeliveryProfile],
    )
    parser.add_argument("--public-origin")
    parser.add_argument("--spa-dist-dir", type=Path)
    args = parser.parse_args()

    profile = DeliveryProfile(args.profile)
    settings = core_journey_settings(
        args.state_root,
        profile,
        public_origin=args.public_origin,
        spa_dist_dir=args.spa_dist_dir,
    )
    prepared = prepare_core_journey(
        settings.state_root,
        profile,
        public_origin=settings.public_origin,
        spa_dist_dir=settings.spa_dist_dir,
    )
    print(
        "CORE_JOURNEY_PREPARED "
        + json.dumps(
            {
                "profile": prepared.profile.value,
                "state_root": str(prepared.state_root),
                "dataset_version_id": prepared.dataset_version_id,
                "investigation_request_id": prepared.investigation_request_id,
                "analysis_run_id": prepared.analysis_run_id,
                "reproduction_run_id": prepared.reproduction_run_id,
                "reference_slot_id": prepared.reference_slot_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
