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
    AuditOccurrenceListResponse,
    AuditOccurrenceResponse,
    AuditOccurrenceViewResponse,
    DemoWorkspaceResponse,
    ErrorResponse,
    HealthProbe,
    HealthResponse,
    ValidatedReferenceListResponse,
    ValidatedReferenceResponse,
    WorkspaceSelectionRequest,
    WorkspaceSelectionResponse,
    WorkspaceSelectionViewResponse,
    WorkspaceResultViewResponse,
)
from .errors import WorkspaceRequestError
from .security import apply_public_response_headers
from .settings import Settings
from .state import StateRoot
from .workspace import DEMO_WORKSPACE_COOKIE_NAME, WorkspaceResolution


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
    audit_store = AuditStore(
        resolved_settings.database_path,
        release_candidate_id=resolved_settings.release_candidate_id,
        quotas=resolved_settings.quotas,
    )

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

    @app.exception_handler(WorkspaceRequestError)
    async def handle_workspace_error(
        _: Request,
        error: WorkspaceRequestError,
    ) -> JSONResponse:
        return _error_response(error.status_code, error.code.value, error.recovery_action)

    def resolve_workspace(request: Request) -> WorkspaceResolution:
        resolution = audit_store.resolve_workspace(
            request.cookies.get(DEMO_WORKSPACE_COOKIE_NAME)
        )
        request.state.workspace_resolution = resolution
        return resolution

    def attach_workspace_cookie(
        response: JSONResponse,
        resolution: WorkspaceResolution,
    ) -> JSONResponse:
        if resolution.new_capability is not None:
            response.set_cookie(
                key=DEMO_WORKSPACE_COOKIE_NAME,
                value=resolution.new_capability,
                httponly=True,
                secure=resolved_settings.profile.value == "HOSTED",
                samesite="lax",
                path="/",
            )
        return response

    @app.middleware("http")
    async def preserve_workspace_cookie(request: Request, call_next):
        response = await call_next(request)
        apply_public_response_headers(
            response,
            path=request.url.path,
            profile=resolved_settings.profile,
        )
        resolution = getattr(request.state, "workspace_resolution", None)
        if (
            isinstance(resolution, WorkspaceResolution)
            and resolution.new_capability is not None
            and "set-cookie" not in response.headers
        ):
            attach_workspace_cookie(response, resolution)
        return response

    def workspace_response(resolution: WorkspaceResolution) -> DemoWorkspaceResponse:
        snapshot = resolution.snapshot
        return DemoWorkspaceResponse(
            workspace_id=snapshot.workspace_id,
            status="ACTIVE",
            created_at=snapshot.created_at,
            last_seen_at=snapshot.last_seen_at,
            mutation_count=snapshot.mutation_count,
            remaining_mutations=max(
                0,
                resolved_settings.quotas.max_workspace_mutations
                - snapshot.mutation_count,
            ),
            terminal_fresh_bundle_count=snapshot.terminal_fresh_bundle_count,
            remaining_terminal_fresh_bundles=max(
                0,
                resolved_settings.quotas.max_workspace_terminal_fresh_bundles
                - snapshot.terminal_fresh_bundle_count,
            ),
        )

    def workspace_resource_unavailable() -> JSONResponse:
        return _error_response(
            404,
            "DEMO_WORKSPACE_RESOURCE_UNAVAILABLE",
            "CHECK_WORKSPACE_AND_RETRY",
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

    @app.get("/api/workspace", response_model=DemoWorkspaceResponse)
    async def get_workspace(request: Request) -> JSONResponse:
        resolution = resolve_workspace(request)
        response = JSONResponse(
            status_code=200,
            content=workspace_response(resolution).model_dump(mode="json"),
        )
        return attach_workspace_cookie(response, resolution)

    @app.post(
        "/api/audit/occurrences",
        response_model=AuditOccurrenceResponse,
        status_code=201,
    )
    async def create_audit_occurrence(
        request_context: Request,
        request: AuditOccurrenceRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = audit_store.append_occurrence(
            request,
            resolution.snapshot.workspace_id,
        )
        response = AuditOccurrenceResponse(
            result="IDEMPOTENT_REPLAY" if stored.replayed else "CREATED",
            occurrence_id=stored.occurrence_id,
            event_seq=stored.event_seq,
        )
        return attach_workspace_cookie(JSONResponse(
            status_code=200 if stored.replayed else 201,
            content=response.model_dump(),
        ), resolution)

    @app.get(
        "/api/audit/occurrences",
        response_model=AuditOccurrenceListResponse,
    )
    async def list_audit_occurrences(request: Request) -> JSONResponse:
        resolution = resolve_workspace(request)
        items = [
            AuditOccurrenceViewResponse(
                occurrence_id=item.occurrence_id,
                event_seq=item.event_seq,
                occurrence_kind=item.occurrence_kind,
                outcome_code=item.outcome_code,
                created_at=item.created_at,
            )
            for item in audit_store.list_occurrences(resolution.snapshot.workspace_id)
        ]
        response = JSONResponse(
            status_code=200,
            content=AuditOccurrenceListResponse(items=items).model_dump(mode="json"),
        )
        return attach_workspace_cookie(response, resolution)

    @app.get(
        "/api/audit/occurrences/{occurrence_id}",
        response_model=AuditOccurrenceViewResponse,
    )
    async def get_audit_occurrence(
        request: Request,
        occurrence_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        occurrence = audit_store.get_occurrence(
            resolution.snapshot.workspace_id,
            occurrence_id,
        )
        if occurrence is None:
            return workspace_resource_unavailable()
        response = AuditOccurrenceViewResponse(
            occurrence_id=occurrence.occurrence_id,
            event_seq=occurrence.event_seq,
            occurrence_kind=occurrence.occurrence_kind,
            outcome_code=occurrence.outcome_code,
            created_at=occurrence.created_at,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.post(
        "/api/workspace/selections",
        response_model=WorkspaceSelectionResponse,
        status_code=201,
    )
    async def create_workspace_selection(
        request_context: Request,
        request: WorkspaceSelectionRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        receipt = audit_store.create_workspace_selection(
            resolution.snapshot.workspace_id,
            selection_id=request.selection_id,
            reference_id=request.reference_id,
            idempotency_key=request.idempotency_key,
        )
        response = WorkspaceSelectionResponse(
            result="IDEMPOTENT_REPLAY" if receipt.replayed else "CREATED",
            selection_id=request.selection_id,
            reference_id=request.reference_id,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if receipt.replayed else 201,
                content=response.model_dump(),
            ),
            resolution,
        )

    @app.get(
        "/api/workspace/selections/{selection_id}",
        response_model=WorkspaceSelectionViewResponse,
    )
    async def get_workspace_selection(
        request: Request,
        selection_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        selection = audit_store.get_workspace_selection(
            resolution.snapshot.workspace_id,
            selection_id,
        )
        if selection is None:
            return workspace_resource_unavailable()
        response = WorkspaceSelectionViewResponse(
            selection_id=selection.selection_id,
            reference_id=selection.reference_id,
            selected_at=selection.selected_at,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.get(
        "/api/workspace/results/{result_id}",
        response_model=WorkspaceResultViewResponse,
    )
    async def get_workspace_result(
        request: Request,
        result_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        result = audit_store.get_workspace_result(
            resolution.snapshot.workspace_id,
            result_id,
        )
        if result is None:
            return workspace_resource_unavailable()
        response = WorkspaceResultViewResponse(
            result_id=result.result_id,
            operation_id=result.operation_id,
            result_ref=result.result_ref,
            created_at=result.created_at,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.get(
        "/api/validated-references",
        response_model=ValidatedReferenceListResponse,
    )
    async def list_validated_references() -> JSONResponse:
        items = [
            ValidatedReferenceResponse(
                reference_id=item.reference_id,
                bundle_ref=item.bundle_ref,
                validation_attestation_ref=item.validation_attestation_ref,
                release_candidate_id=item.release_candidate_id,
            )
            for item in audit_store.list_validated_references()
        ]
        return JSONResponse(
            status_code=200,
            content=ValidatedReferenceListResponse(items=items).model_dump(mode="json"),
        )

    @app.get(
        "/api/validated-references/{reference_id}",
        response_model=ValidatedReferenceResponse,
    )
    async def get_validated_reference(reference_id: str) -> JSONResponse:
        reference = audit_store.get_validated_reference(reference_id)
        if reference is None:
            return workspace_resource_unavailable()
        response = ValidatedReferenceResponse(
            reference_id=reference.reference_id,
            bundle_ref=reference.bundle_ref,
            validation_attestation_ref=reference.validation_attestation_ref,
            release_candidate_id=reference.release_candidate_id,
        )
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

    if resolved_settings.spa_dist_dir is not None and resolved_settings.spa_dist_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=resolved_settings.spa_dist_dir, html=True),
            name="spa",
        )

    return app


app = create_app()
