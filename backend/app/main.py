from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Message, Receive, Scope, Send

from .audit import (
    AuditIdempotencyConflict,
    AuditStoreUnavailable,
)
from .contracts import (
    AuditOccurrenceRequest,
    AuditOccurrenceListResponse,
    AuditOccurrenceResponse,
    AuditOccurrenceViewResponse,
    AnalysisRunStatusResponse,
    DecisionBriefRequest,
    DecisionBriefResponse,
    DecisionBriefSnapshotResponse,
    DemoWorkspaceResponse,
    DatasetVersionListResponse,
    ErrorResponse,
    HealthProbe,
    HealthResponse,
    IngestionRunRequest,
    IngestionRunResponse,
    LineageSnapshotResponse,
    OperationAdmissionRequest,
    OperationActionRequest,
    OperationMutationResponse,
    OperationResponse,
    ProactiveInvestigationResponse,
    ProactiveFixtureRequest,
    ProactiveProposalListResponse,
    ProactiveProposalRequest,
    ReactiveInvestigationResponse,
    ReactiveFixtureRequest,
    ReplayResponse,
    RiskSignalListResponse,
    RiskSignalRequest,
    ValidatedReferenceDeliveryResponse,
    ValidatedReferenceListResponse,
    ValidatedReferenceResponse,
    WorkspaceSelectionRequest,
    WorkspaceSelectionResponse,
    WorkspaceSelectionViewResponse,
    WorkspaceResultViewResponse,
)
from .errors import SafeErrorCode, WorkspaceRequestError
from .analysis_runs import (
    AnalysisRunRequestError,
    analysis_run_id_for_operation,
    analysis_run_status,
    build_fresh_analysis_payload,
    is_strict_fresh_analysis_request,
    load_fresh_analysis_result,
)
from .governance import (
    DecisionBriefUnavailable,
    InvestigationRequestUnavailable,
)
from .ingestion import (
    DatasetVersionUnavailable,
    IngestionIdempotencyConflict,
    IngestionRejected,
    LineageStore,
)
from .risk import (
    ProactiveProposalFixtureUnavailable,
    RiskSignalFixtureUnavailable,
)
from .security import apply_public_response_headers
from .settings import Settings
from .state import StateRoot
from .operations import DurableOperation, OperationRunner
from .references import (
    DEFAULT_REFERENCE_INTENDED_ROLE,
    DEFAULT_REFERENCE_SLOT_ID,
    ValidatedReferenceStore,
)
from .diagnostics import diagnostic_summary as build_diagnostic_summary
from .validity import render_evidence_verdict
from .workspace import DEMO_WORKSPACE_COOKIE_NAME, WorkspaceResolution

MAX_REACTIVE_REQUEST_BYTES = 64 * 1024
MAX_REACTIVE_REQUEST_MESSAGES = 4096
MAX_PROACTIVE_REQUEST_BYTES = 64 * 1024
MAX_PROACTIVE_REQUEST_MESSAGES = 4096


class ReactiveRequestTooLarge(Exception):
    def __init__(self, observed_bytes: int) -> None:
        self.observed_bytes = observed_bytes
        super().__init__("reactive request body exceeds the bounded ingress limit")


def _error_response(status_code: int, code: str, recovery_action: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            code=code,
            recovery_action=recovery_action,
        ).model_dump(),
    )


def _attach_workspace_cookie(
    response: JSONResponse,
    resolution: WorkspaceResolution,
    *,
    secure: bool,
) -> JSONResponse:
    if resolution.new_capability is not None:
        response.set_cookie(
            key=DEMO_WORKSPACE_COOKIE_NAME,
            value=resolution.new_capability,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )
    return response


class ReactiveBodyLimitMiddleware:
    """Bound reactive body reads at the ASGI receive boundary."""

    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        *,
        core_store: LineageStore,
        secure_cookie: bool,
    ) -> None:
        self.app = app
        self.core_store = core_store
        self.secure_cookie = secure_cookie

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        error: ReactiveRequestTooLarge,
    ) -> None:
        request = Request(scope, receive)
        try:
            resolution = self.core_store.resolve_workspace(
                request.cookies.get(DEMO_WORKSPACE_COOKIE_NAME)
            )
            proactive = scope.get("path") == "/api/investigations/proactive"
            if proactive:
                self.core_store.record_proactive_schema_failure(
                    resolution.snapshot.workspace_id,
                    request_body=f"proactive-body-too-large:{error.observed_bytes}".encode(
                        "ascii"
                    ),
                )
            else:
                self.core_store.record_reactive_schema_failure(
                    resolution.snapshot.workspace_id,
                    request_body=f"reactive-body-too-large:{error.observed_bytes}".encode(
                        "ascii"
                    ),
                )
            response = _attach_workspace_cookie(
                _error_response(
                    413,
                    "PROACTIVE_SCHEMA_UNSUPPORTED"
                    if proactive
                    else "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
                    "USE_SUPPORTED_PROACTIVE_PROPOSAL_SCHEMA"
                    if proactive
                    else "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
                ),
                resolution,
                secure=self.secure_cookie,
            )
        except WorkspaceRequestError as workspace_error:
            response = _error_response(
                workspace_error.status_code,
                workspace_error.code.value,
                workspace_error.recovery_action,
            )
        except AuditStoreUnavailable:
            response = _error_response(
                503,
                "CORE_STORE_UNAVAILABLE",
                "RESTORE_CORE_STATE_AND_RETRY",
            )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path")
        if scope.get("type") != "http" or path not in {
            "/api/investigations/reactive",
            "/api/investigations/proactive",
        }:
            await self.app(scope, receive, send)
            return
        proactive = path == "/api/investigations/proactive"
        max_bytes = (
            MAX_PROACTIVE_REQUEST_BYTES if proactive else MAX_REACTIVE_REQUEST_BYTES
        )
        max_messages = (
            MAX_PROACTIVE_REQUEST_MESSAGES
            if proactive
            else MAX_REACTIVE_REQUEST_MESSAGES
        )

        content_length = next(
            (
                value
                for key, value in scope.get("headers", [])
                if key.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except (TypeError, ValueError):
                declared_length = 0
            if declared_length > max_bytes:
                await self._reject(
                    scope,
                    receive,
                    send,
                    ReactiveRequestTooLarge(declared_length),
                )
                return

        observed_bytes = 0
        received_messages = 0
        buffered_body = bytearray()
        disconnected = False
        while True:
            message = await receive()
            received_messages += 1
            if received_messages > max_messages:
                await self._reject(
                    scope,
                    receive,
                    send,
                    ReactiveRequestTooLarge(
                        max(observed_bytes, max_bytes + 1)
                    ),
                )
                return
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                observed_bytes += len(body) if isinstance(body, bytes) else 0
                if observed_bytes > max_bytes:
                    await self._reject(
                        scope,
                        receive,
                        send,
                        ReactiveRequestTooLarge(observed_bytes),
                    )
                    return
                if isinstance(body, bytes):
                    buffered_body.extend(body)
                if not message.get("more_body", False):
                    break
            else:
                disconnected = True
                break

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed and not disconnected:
                replayed = True
                return {
                    "type": "http.request",
                    "body": bytes(buffered_body),
                    "more_body": False,
                }
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)


def create_app(
    settings: Settings | None = None,
    *,
    start_operation_runner: bool = True,
) -> FastAPI:
    resolved_settings = settings or Settings()
    state_root = StateRoot(resolved_settings)
    core_store = LineageStore(
        resolved_settings.database_path,
        release_candidate_id=resolved_settings.release_candidate_id,
        quotas=resolved_settings.quotas,
    )
    reference_store = ValidatedReferenceStore(
        resolved_settings.artifact_root,
        release_candidate_id=resolved_settings.release_candidate_id,
        runtime_fingerprint=resolved_settings.runtime_fingerprint.model_dump(mode="json"),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state_layout = state_root.initialize()
        core_store.initialize()
        core_store.recover_interrupted_operations(state_layout)
        app.state.state_layout = state_layout
        operation_runner = (
            OperationRunner(core_store, state_layout)
            if start_operation_runner
            else None
        )
        app.state.operation_runner = operation_runner
        if operation_runner is not None:
            operation_runner.start()
        try:
            yield
        finally:
            if operation_runner is not None:
                operation_runner.stop()
            core_store.close()

    app = FastAPI(
        title="Causal Delay Copilot Core",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.audit_store = core_store
    app.state.reference_store = reference_store
    app.state.operation_runner = None

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request,
        __: RequestValidationError,
    ) -> JSONResponse:
        if request.url.path in {
            "/api/investigations/reactive",
            "/api/investigations/proactive",
        }:
            try:
                resolution = resolve_workspace(request)
                if request.url.path == "/api/investigations/proactive":
                    core_store.record_proactive_schema_failure(
                        resolution.snapshot.workspace_id,
                        request_body=await request.body(),
                    )
                    code = "PROACTIVE_SCHEMA_UNSUPPORTED"
                    recovery = "USE_SUPPORTED_PROACTIVE_PROPOSAL_SCHEMA"
                else:
                    core_store.record_reactive_schema_failure(
                        resolution.snapshot.workspace_id,
                        request_body=await request.body(),
                    )
                    code = "RISK_SIGNAL_SCHEMA_UNSUPPORTED"
                    recovery = "USE_SUPPORTED_RISK_SIGNAL_SCHEMA"
                return attach_workspace_cookie(
                    _error_response(
                        422,
                        code,
                        recovery,
                    ),
                    resolution,
                )
            except WorkspaceRequestError as error:
                return _error_response(
                    error.status_code,
                    error.code.value,
                    error.recovery_action,
                )
            except AuditStoreUnavailable:
                return _error_response(
                    503,
                    "CORE_STORE_UNAVAILABLE",
                    "RESTORE_CORE_STATE_AND_RETRY",
                )
            return _error_response(
                422,
                "RISK_SIGNAL_SCHEMA_UNSUPPORTED",
                "USE_SUPPORTED_RISK_SIGNAL_SCHEMA",
            )
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

    @app.exception_handler(DecisionBriefUnavailable)
    async def handle_decision_brief_unavailable(
        _: Request,
        __: DecisionBriefUnavailable,
    ) -> JSONResponse:
        return _error_response(
            503,
            "DECISION_BRIEF_UNAVAILABLE",
            "SELECT_A_VERIFIED_REFERENCE_FOR_THIS_DATASET_AND_RETRY",
        )

    @app.exception_handler(InvestigationRequestUnavailable)
    async def handle_investigation_request_unavailable(
        _: Request,
        __: InvestigationRequestUnavailable,
    ) -> JSONResponse:
        return _error_response(
            404,
            "INVESTIGATION_REQUEST_UNAVAILABLE",
            "SUBMIT_AN_ACCEPTED_INVESTIGATION_REQUEST_AND_RETRY",
        )

    @app.exception_handler(WorkspaceRequestError)
    async def handle_workspace_error(
        _: Request,
        error: WorkspaceRequestError,
    ) -> JSONResponse:
        return _error_response(error.status_code, error.code.value, error.recovery_action)

    @app.exception_handler(IngestionIdempotencyConflict)
    async def handle_ingestion_idempotency_conflict(
        _: Request,
        __: IngestionIdempotencyConflict,
    ) -> JSONResponse:
        return _error_response(
            409,
            "INGESTION_IDEMPOTENCY_CONFLICT",
            "USE_NEW_IDEMPOTENCY_KEY",
        )

    @app.exception_handler(DatasetVersionUnavailable)
    async def handle_dataset_version_unavailable(
        _: Request,
        __: DatasetVersionUnavailable,
    ) -> JSONResponse:
        return _error_response(
            404,
            "DATASET_VERSION_UNAVAILABLE",
            "SELECT_A_PUBLISHED_DATASET_VERSION_AND_RETRY",
        )

    @app.exception_handler(RiskSignalFixtureUnavailable)
    async def handle_risk_signal_fixture_unavailable(
        _: Request,
        __: RiskSignalFixtureUnavailable,
    ) -> JSONResponse:
        return _error_response(
            404,
            "DATASET_VERSION_UNAVAILABLE",
            "SELECT_A_PUBLISHED_DATASET_VERSION_AND_RETRY",
        )

    @app.exception_handler(ProactiveProposalFixtureUnavailable)
    async def handle_proactive_proposal_fixture_unavailable(
        _: Request,
        __: ProactiveProposalFixtureUnavailable,
    ) -> JSONResponse:
        return _error_response(
            404,
            "DATASET_VERSION_UNAVAILABLE",
            "SELECT_A_PUBLISHED_DATASET_VERSION_AND_RETRY",
        )

    @app.exception_handler(IngestionRejected)
    async def handle_ingestion_rejected(
        _: Request,
        __: IngestionRejected,
    ) -> JSONResponse:
        return _error_response(
            422,
            "INGESTION_REJECTED",
            "REPAIR_THE_REVIEWED_MAPPING_AND_RETRY",
        )

    def resolve_workspace(request: Request) -> WorkspaceResolution:
        resolution = core_store.resolve_workspace(
            request.cookies.get(DEMO_WORKSPACE_COOKIE_NAME)
        )
        request.state.workspace_resolution = resolution
        return resolution

    def attach_workspace_cookie(
        response: JSONResponse,
        resolution: WorkspaceResolution,
    ) -> JSONResponse:
        return _attach_workspace_cookie(
            response,
            resolution,
            secure=resolved_settings.profile.value == "HOSTED",
        )

    app.add_middleware(
        ReactiveBodyLimitMiddleware,
        core_store=core_store,
        secure_cookie=resolved_settings.profile.value == "HOSTED",
    )

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

    def operation_response(operation: DurableOperation) -> OperationResponse:
        operation_request = core_store.get_operation_request(
            operation.workspace_id,
            operation.operation_id,
        )
        analysis_run = None
        if (
            operation.operation_kind == "FRESH_ANALYSIS"
            and isinstance(operation_request, dict)
            and operation_request.get("schema_version") == "analysis-run-admission.v1"
        ):
            analysis_run = AnalysisRunStatusResponse(
                **analysis_run_status(
                    operation,
                    operation_request,
                    load_fresh_analysis_result(
                        getattr(app.state, "state_layout", None),
                        operation.operation_id,
                    ),
                )
            )
        return OperationResponse(
            schema_version="durable-operation.v1",
            operation_id=operation.operation_id,
            operation_kind=operation.operation_kind,
            state=operation.state,
            status=operation.state,
            queue_position=operation.queue_position,
            created_at=operation.created_at,
            queued_at=operation.queued_at,
            started_at=operation.started_at,
            finished_at=operation.finished_at,
            cancel_requested_at=operation.cancel_requested_at,
            retry_of_operation_id=operation.retry_of_operation_id,
            failure_code=operation.failure_code,
            recovery_action=operation.recovery_action,
            resource_warnings=list(operation.resource_warnings),
            artifact_state=operation.artifact_state,
            retryable=operation.state
            in {"INTERRUPTED", "FAILED", "TIMED_OUT", "CANCELLED"},
            timeout_seconds=operation.timeout_seconds,
            thread_cap=operation.thread_cap,
            memory_required_bytes=operation.memory_required_bytes,
            memory_available_bytes=operation.memory_available_bytes,
            disk_free_bytes=operation.disk_free_bytes,
            analysis_run=analysis_run,
        )

    def liveness_probe() -> HealthProbe:
        return HealthProbe(state="live", code="CORE_LIVE")

    def readiness_probe() -> HealthProbe:
        if not core_store.check_ready():
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
        "/api/operations",
        response_model=OperationMutationResponse,
        status_code=202,
    )
    async def admit_operation(
        request_context: Request,
        request: OperationAdmissionRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        memory_required_bytes = (
            request.memory_required_bytes
            if "memory_required_bytes" in request.model_fields_set
            else resolved_settings.quotas.compute_memory_request_bytes
        )
        stored_request = request.request
        if request.operation_kind == "FRESH_ANALYSIS" and is_strict_fresh_analysis_request(
            request.request
        ):
            try:
                stored_request = build_fresh_analysis_payload(
                    core_store,
                    resolution.snapshot.workspace_id,
                    request.request,
                    resolved_settings,
                )
            except AnalysisRunRequestError as error:
                raise WorkspaceRequestError(
                    SafeErrorCode(error.code),
                    error.recovery_action,
                    error.status_code,
                ) from error
        stored = core_store.admit_operation(
            resolution.snapshot.workspace_id,
            operation_kind=request.operation_kind,
            idempotency_key=request.idempotency_key,
            request=stored_request,
            memory_required_bytes=memory_required_bytes,
            state_root=resolved_settings.state_root,
        )
        response = OperationMutationResponse(
            result="IDEMPOTENT_REPLAY" if stored.replayed else "CREATED",
            operation=operation_response(stored.operation),
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.replayed else 202,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.get(
        "/api/analysis-runs/{analysis_run_id}",
        response_model=AnalysisRunStatusResponse,
    )
    async def get_analysis_run(
        request: Request,
        analysis_run_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        try:
            if not analysis_run_id.startswith("analysis-run-"):
                raise ValueError("analysis run identity is invalid")
            operation_id = "operation-" + analysis_run_id.removeprefix("analysis-run-")
            if analysis_run_id != analysis_run_id_for_operation(operation_id):
                raise ValueError("analysis run identity is invalid")
        except ValueError:
            return attach_workspace_cookie(workspace_resource_unavailable(), resolution)
        operation = core_store.get_operation(
            resolution.snapshot.workspace_id,
            operation_id,
        )
        operation_request = core_store.get_operation_request(
            resolution.snapshot.workspace_id,
            operation_id,
        )
        if (
            operation is None
            or not isinstance(operation_request, dict)
            or operation_request.get("schema_version") != "analysis-run-admission.v1"
        ):
            return attach_workspace_cookie(workspace_resource_unavailable(), resolution)
        response = AnalysisRunStatusResponse(
            **analysis_run_status(
                operation,
                operation_request,
                load_fresh_analysis_result(
                    getattr(app.state, "state_layout", None),
                    operation.operation_id,
                ),
            )
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.get(
        "/api/operations/{operation_id}",
        response_model=OperationResponse,
    )
    async def get_operation(
        request: Request,
        operation_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        operation = core_store.get_operation(
            resolution.snapshot.workspace_id,
            operation_id,
        )
        if operation is None:
            return attach_workspace_cookie(
                workspace_resource_unavailable(),
                resolution,
            )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200,
                content=operation_response(operation).model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/operations/{operation_id}/cancel",
        response_model=OperationMutationResponse,
        status_code=202,
    )
    async def cancel_operation(
        request_context: Request,
        operation_id: str,
        request: OperationActionRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.cancel_operation(
            resolution.snapshot.workspace_id,
            operation_id,
            idempotency_key=request.idempotency_key,
        )
        if stored is None:
            return attach_workspace_cookie(
                workspace_resource_unavailable(),
                resolution,
            )
        response = OperationMutationResponse(
            result="IDEMPOTENT_REPLAY" if stored.replayed else "CREATED",
            operation=operation_response(stored.operation),
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.replayed else 202,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/operations/{operation_id}/retry",
        response_model=OperationMutationResponse,
        status_code=202,
    )
    async def retry_operation(
        request_context: Request,
        operation_id: str,
        request: OperationActionRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.retry_operation(
            resolution.snapshot.workspace_id,
            operation_id,
            idempotency_key=request.idempotency_key,
            state_root=resolved_settings.state_root,
        )
        if stored is None:
            return attach_workspace_cookie(
                workspace_resource_unavailable(),
                resolution,
            )
        response = OperationMutationResponse(
            result="IDEMPOTENT_REPLAY" if stored.replayed else "CREATED",
            operation=operation_response(stored.operation),
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.replayed else 202,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

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
        stored = core_store.append_occurrence(
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
                source_role_ceiling=core_store.get_source_role_ceiling_for_occurrence(
                    workspace_id=resolution.snapshot.workspace_id,
                    occurrence_id=item.occurrence_id,
                ),
            )
            for item in core_store.list_occurrences(resolution.snapshot.workspace_id)
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
        occurrence = core_store.get_occurrence(
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
            source_role_ceiling=core_store.get_source_role_ceiling_for_occurrence(
                workspace_id=resolution.snapshot.workspace_id,
                occurrence_id=occurrence.occurrence_id,
            ),
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.post(
        "/api/investigations/{investigation_request_id}/decision-brief",
        response_model=DecisionBriefResponse,
        status_code=201,
    )
    async def publish_decision_brief(
        request_context: Request,
        investigation_request_id: str,
        request: DecisionBriefRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        existing = core_store.get_decision_brief_by_idempotency(
            resolution.snapshot.workspace_id,
            request.idempotency_key,
        )
        if existing is not None:
            if (
                existing["investigation_request_id"] != investigation_request_id
                or existing["reference_id"] != request.reference_id
            ):
                raise AuditIdempotencyConflict
            stored_result = "IDEMPOTENT_REPLAY"
            snapshot = existing
        else:
            reference = reference_store.read_model(request.reference_id)
            if reference is None:
                return attach_workspace_cookie(
                    workspace_resource_unavailable(),
                    resolution,
                )
            stored = core_store.publish_decision_brief(
                resolution.snapshot.workspace_id,
                investigation_request_id=investigation_request_id,
                idempotency_key=request.idempotency_key,
                reference_id=request.reference_id,
                reference=reference,
            )
            stored_result = stored.result
            snapshot = stored.snapshot
        response = DecisionBriefResponse(
            result=stored_result,
            snapshot=DecisionBriefSnapshotResponse.model_validate(snapshot),
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored_result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.get(
        "/api/investigations/{investigation_request_id}/decision-brief",
        response_model=DecisionBriefSnapshotResponse,
    )
    async def get_decision_brief(
        request: Request,
        investigation_request_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        snapshot = core_store.get_decision_brief(
            resolution.snapshot.workspace_id,
            investigation_request_id,
        )
        if snapshot is None:
            return attach_workspace_cookie(
                workspace_resource_unavailable(),
                resolution,
            )
        response = DecisionBriefSnapshotResponse.model_validate(snapshot)
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.get("/api/audit/replay", response_model=ReplayResponse)
    async def replay_audit(
        request: Request,
        investigation_request_id: str,
        event_seq: int = Query(gt=0),
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        replay = core_store.replay_decision_brief(
            resolution.snapshot.workspace_id,
            investigation_request_id,
            event_seq,
        )
        response = ReplayResponse(
            schema_version="replay.v1",
            status=replay.status,
            investigation_request_id=replay.investigation_request_id,
            requested_event_seq=replay.requested_event_seq,
            last_verified_event_seq=replay.last_verified_event_seq,
            snapshot=(
                None
                if replay.snapshot is None
                else DecisionBriefSnapshotResponse.model_validate(replay.snapshot)
            ),
            unresolved_references=replay.unresolved_references,
            recovery_action=replay.recovery_action,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.post(
        "/api/ingestion-runs",
        response_model=IngestionRunResponse,
        status_code=201,
    )
    async def create_ingestion_run(request: IngestionRunRequest) -> JSONResponse:
        stored = core_store.import_dataset(
            idempotency_key=request.idempotency_key,
            dataset_key=request.dataset_key,
            mapping_manifest_id=request.mapping_manifest_id,
        )
        response = IngestionRunResponse(
            result=stored.result,
            ingestion_run_id=stored.ingestion_run_id,
            dataset_version_id=stored.dataset_version_id or "",
            status=stored.status,
        )
        return JSONResponse(
            status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
            content=response.model_dump(),
        )

    @app.get(
        "/api/datasets",
        response_model=DatasetVersionListResponse,
    )
    async def list_dataset_versions() -> JSONResponse:
        response = DatasetVersionListResponse(items=core_store.list_dataset_versions())
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

    @app.get(
        "/api/datasets/{dataset_version_id}/lineage",
        response_model=LineageSnapshotResponse,
    )
    async def get_dataset_lineage(
        request: Request,
        dataset_version_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        lineage = core_store.get_lineage(dataset_version_id)
        binding = core_store.bind_lineage_snapshot(
            workspace_id=resolution.snapshot.workspace_id,
            dataset_version_id=dataset_version_id,
        )
        response = LineageSnapshotResponse(
            **lineage,
            audit_binding={
                "snapshot_id": binding.snapshot_id,
                "dataset_version_id": binding.dataset_version_id,
                "occurrence_id": binding.occurrence_id,
                "event_seq": binding.event_seq,
                "content_hash": binding.content_hash,
                "created_at": binding.created_at,
                "source_role_ceiling": lineage["dataset_version"]["source_role_ceiling"],
            },
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.get(
        "/api/risk-signals",
        response_model=RiskSignalListResponse,
    )
    async def list_risk_signals(dataset_version_id: str) -> JSONResponse:
        items = core_store.list_risk_signal_fixtures(dataset_version_id)
        response = RiskSignalListResponse(
            items=items,
            predictive_status=core_store.predictive_risk_status(),
        )
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

    @app.get(
        "/api/proactive-proposals",
        response_model=ProactiveProposalListResponse,
    )
    async def list_proactive_proposals(dataset_version_id: str) -> JSONResponse:
        response = ProactiveProposalListResponse(
            items=core_store.list_proactive_proposal_fixtures(dataset_version_id)
        )
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

    @app.post(
        "/api/investigations/reactive/fixtures",
        response_model=ReactiveInvestigationResponse,
        status_code=201,
    )
    async def create_reactive_fixture_investigation(
        request_context: Request,
        request: ReactiveFixtureRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.create_reactive_fixture_investigation(
            request.fixture_id,
            request.dataset_version_id,
            resolution.snapshot.workspace_id,
        )
        response = ReactiveInvestigationResponse(
            result=stored.result,
            attempt=stored.attempt,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/investigations/reactive",
        response_model=ReactiveInvestigationResponse,
        status_code=201,
    )
    async def create_reactive_investigation(
        request_context: Request,
        request: RiskSignalRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.create_reactive_investigation(
            request,
            resolution.snapshot.workspace_id,
        )
        response = ReactiveInvestigationResponse(
            result=stored.result,
            attempt=stored.attempt,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/investigations/proactive/fixtures",
        response_model=ProactiveInvestigationResponse,
        status_code=201,
    )
    async def create_proactive_fixture_investigation(
        request_context: Request,
        request: ProactiveFixtureRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.create_proactive_fixture_investigation(
            request.fixture_id,
            request.dataset_version_id,
            resolution.snapshot.workspace_id,
        )
        response = ProactiveInvestigationResponse(
            result=stored.result,
            attempt=stored.attempt,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/investigations/proactive",
        response_model=ProactiveInvestigationResponse,
        status_code=201,
    )
    async def create_proactive_investigation(
        request_context: Request,
        request: ProactiveProposalRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.create_proactive_investigation(
            request,
            resolution.snapshot.workspace_id,
        )
        response = ProactiveInvestigationResponse(
            result=stored.result,
            attempt=stored.attempt,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
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
        receipt = core_store.create_workspace_selection(
            resolution.snapshot.workspace_id,
            selection_id=request.selection_id,
            reference_id=request.reference_id,
            idempotency_key=request.idempotency_key,
            reference_exists=reference_store.is_verified,
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
        selection = core_store.get_workspace_selection(
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
        result = core_store.get_workspace_result(
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
                reference_id=item.reference_slot_id,
                bundle_ref=item.bundle_manifest_hash,
                validation_attestation_ref=item.validation_attestation_ref,
                release_candidate_id=item.release_candidate_id,
            )
            for item in reference_store.list_verified_references()
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
        verified = reference_store.select_reference(reference_id)
        if verified is None:
            return workspace_resource_unavailable()
        response = ValidatedReferenceResponse(
            reference_id=verified.reference_slot_id,
            bundle_ref=verified.bundle_manifest_hash,
            validation_attestation_ref=verified.validation_attestation_ref,
            release_candidate_id=verified.release_candidate_id,
        )
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

    @app.get(
        "/api/evidence/reference",
        response_model=ValidatedReferenceDeliveryResponse,
    )
    async def get_ordinary_reference() -> JSONResponse:
        reference = reference_store.read_model(
            DEFAULT_REFERENCE_SLOT_ID,
            intended_role=DEFAULT_REFERENCE_INTENDED_ROLE,
        )
        if reference is None:
            return workspace_resource_unavailable()
        response = ValidatedReferenceDeliveryResponse(
            schema_version="analysis-run-read-model.v1",
            delivery_mode=reference.delivery_mode,
            delivery_badge="Validated reference",
            verification_state=reference.verification_state,
            reference_slot_id=reference.reference_slot_id,
            reference_id=reference.reference_slot_id,
            analysis_run_id=reference.analysis_run_id,
            bundle_manifest_hash=reference.bundle_manifest_hash,
            bundle_ref=reference.bundle_manifest_hash,
            validation_attestation_id=reference.validation_attestation_id,
            validation_attestation_ref=reference.validation_attestation_ref,
            release_candidate_id=reference.release_candidate_id,
            intended_role=reference.intended_role,
            engine_result_status=reference.engine_result_status,
            scientific_request_digest=reference.scientific_request_digest,
            dataset_version_id=reference.dataset_version_id,
            runtime_fingerprint_digest=reference.runtime_fingerprint_digest,
            validation_policy_version=reference.validation_policy_version,
            validated_at=reference.validated_at,
            diagnostics=[dict(item) for item in reference.diagnostic_results],
            diagnostic_summary=build_diagnostic_summary(reference.diagnostic_results),
            robustness_grade=(
                None if reference.robustness_grade is None else dict(reference.robustness_grade)
            ),
            evidence_verdict=(
                None if reference.evidence_verdict is None else dict(reference.evidence_verdict)
            ),
            rendered_verdict=(
                None
                if reference.evidence_verdict is None
                else render_evidence_verdict(reference.evidence_verdict)
            ),
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
