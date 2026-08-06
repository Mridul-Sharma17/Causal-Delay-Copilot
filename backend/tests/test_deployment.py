from __future__ import annotations

import json
from pathlib import Path
import tomllib


ROOT = Path(__file__).parents[2]


def test_hosted_deployment_contract_keeps_api_proxy_and_stateful_runtime_explicit() -> None:
    vercel_template = json.loads(
        (ROOT / "vercel.json.template").read_text(encoding="utf-8")
    )
    api_rewrite = next(
        rewrite
        for rewrite in vercel_template["rewrites"]
        if rewrite["source"] == "/api/:path*"
    )
    assert api_rewrite["destination"] == (
        "__RAILWAY_PUBLIC_ORIGIN__/api/:path*"
    )
    assert vercel_template["outputDirectory"] == "frontend/dist"
    assert vercel_template["buildCommand"] == "npm run build"

    railway = tomllib.loads((ROOT / "railway.toml").read_text(encoding="utf-8"))
    assert railway["build"] == {
        "builder": "DOCKERFILE",
        "dockerfilePath": "Dockerfile",
    }
    deploy = railway["deploy"]
    assert "--workers 1" in deploy["startCommand"]
    assert deploy["healthcheckPath"] == "/api/health/ready"
    assert deploy["numReplicas"] == 1

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "CORE_STATE_ROOT=/data/core" in dockerfile
    assert "CORE_RAILWAY_VOLUME_PATH=/data" in dockerfile
    assert "CORE_WEB_WORKER_COUNT=1" in dockerfile
    assert "--workers 1" in dockerfile
    assert "VOLUME [\"/data\"]" not in dockerfile


def test_public_frontend_uses_only_relative_api_requests() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").glob("*.ts*")
    )

    assert '"/api/health"' in source
    assert '"/api/workspace"' in source
    assert '"/api/audit/occurrences"' in source
    assert "railway" not in source.lower()
    assert "serviceWorker" not in source
