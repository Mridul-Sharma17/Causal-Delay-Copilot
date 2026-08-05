from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .audit import (
    AuditIdempotencyConflict,
    AuditStore,
    AuditStoreUnavailable,
)
from .contracts import (
    AuditOccurrenceRequest,
    AuditOccurrenceResponse,
    ErrorResponse,
    HealthProbe,
    HealthResponse,
)
from .settings import Settings
from .state import StateRoot


def _error_response(status_code: int, code: str, recovery_action: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            code=code,
            recovery_action=recovery_action,
        ).model_dump(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    state_root = StateRoot(resolved_settings)
    audit_store = AuditStore(resolved_settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state_layout = state_root.initialize()
        audit_store.initialize()
        app.state.state_layout = state_layout
        try:
            yield
        finally:
            audit_store.close()

    app = FastAPI(
        title="Causal Delay Copilot Core",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.audit_store = audit_store

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        _: Request,
        __: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            422,
            "REQUEST_SCHEMA_INVALID",
            "CORRECT_REQUEST_AND_RETRY",
        )

    @app.exception_handler(AuditIdempotencyConflict)
    async def handle_idempotency_conflict(
        _: Request,
        __: AuditIdempotencyConflict,
    ) -> JSONResponse:
        return _error_response(
            409,
            "AUDIT_IDEMPOTENCY_CONFLICT",
            "USE_NEW_IDEMPOTENCY_KEY",
        )

    @app.exception_handler(AuditStoreUnavailable)
    async def handle_store_unavailable(
        _: Request,
        __: AuditStoreUnavailable,
    ) -> JSONResponse:
        return _error_response(
            503,
            "CORE_STORE_UNAVAILABLE",
            "RESTORE_CORE_STATE_AND_RETRY",
        )

    def liveness_probe() -> HealthProbe:
        return HealthProbe(state="live", code="CORE_LIVE")

    def readiness_probe() -> HealthProbe:
        if not audit_store.check_ready():
            return HealthProbe(
                state="unavailable",
                code="CORE_STORE_UNAVAILABLE",
            )
        if resolved_settings.gemini_enabled:
            return HealthProbe(state="ready", code="CORE_READY")
        return HealthProbe(
            state="degraded",
            code="CORE_READY_GEMINI_DEGRADED",
        )

    @app.get("/api/health/live", response_model=HealthProbe)
    async def get_liveness() -> HealthProbe:
        return liveness_probe()

    @app.get("/api/health/ready", response_model=HealthProbe)
    async def get_readiness() -> JSONResponse | HealthProbe:
        probe = readiness_probe()
        if probe.state == "unavailable":
            return JSONResponse(status_code=503, content=probe.model_dump())
        return probe

    @app.get("/api/health", response_model=HealthResponse)
    async def get_health() -> JSONResponse:
        liveness = liveness_probe()
        readiness = readiness_probe()
        degraded_capabilities = (
            [] if readiness.state != "degraded" else ["GEMINI_DRAFTING"]
        )
        response = HealthResponse(
            service="causal-delay-copilot",
            state=readiness.state,
            code=readiness.code,
            liveness=liveness,
            readiness=readiness,
            degraded_capabilities=degraded_capabilities,
            observed_at=datetime.now(timezone.utc),
        )
        status_code = 503 if readiness.state == "unavailable" else 200
        return JSONResponse(
            status_code=status_code,
            content=response.model_dump(mode="json"),
        )

    @app.post(
        "/api/audit/occurrences",
        response_model=AuditOccurrenceResponse,
        status_code=201,
    )
    async def create_audit_occurrence(
        request: AuditOccurrenceRequest,
    ) -> JSONResponse:
        stored = audit_store.append_occurrence(request)
        response = AuditOccurrenceResponse(
            result="IDEMPOTENT_REPLAY" if stored.replayed else "CREATED",
            occurrence_id=stored.occurrence_id,
            event_seq=stored.event_seq,
        )
        return JSONResponse(
            status_code=200 if stored.replayed else 201,
            content=response.model_dump(),
        )

    if resolved_settings.spa_dist_dir is not None and resolved_settings.spa_dist_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=resolved_settings.spa_dist_dir, html=True),
            name="spa",
        )

    return app


app = create_app()
