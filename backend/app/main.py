from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import sqlite3
import threading
from typing import AsyncIterator, Awaitable, Callable
from uuid import uuid4

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
    DecisionSupportEvaluationSeriesResponse,
    DecisionSupportCurrentAdviceRenderRequest,
    DecisionSupportCurrentnessRequest,
    DecisionSupportCurrentnessResponse,
    DraftContextPreviewResponse,
    DraftContextRequest,
    DraftDispositionRequest,
    DraftEditRequest,
    ManagerDecisionRequest,
    ManagerDecisionResponse,
    DecisionSupportMonitoringMatchRequest,
    DecisionSupportMonitoringObservationRequest,
    DecisionSupportMonitoringObservationResponse,
    DecisionSupportInvalidationRequest,
    DecisionSupportInvalidationResponse,
    DemoWorkspaceResponse,
    DatasetVersionListResponse,
    ErrorResponse,
    HealthProbe,
    HealthResponse,
    IngestionRunRequest,
    IngestionRunResponse,
    LifecycleStopResponse,
    LineageSnapshotResponse,
    OperationAdmissionRequest,
    OperationActionRequest,
    OperationMutationResponse,
    OperationResponse,
    ProactiveInvestigationResponse,
    ProactiveFixtureRequest,
    ProactiveProposalListResponse,
    ProactiveProposalRequest,
    RefreshInvestigationRequest,
    RefreshInvestigationResponse,
    RefreshInvestigationSnapshotResponse,
    ReactiveInvestigationResponse,
    ReactiveFixtureRequest,
    ReplayResponse,
    ReleaseIdentityResponse,
    RiskSignalListResponse,
    RiskSignalRequest,
    TradeoffSelectionAcceptanceRequest,
    TradeoffSelectionAcceptanceResponse,
    TradeoffSelectionPublishRequest,
    TradeoffSelectionPublishResponse,
    ValidatedReferenceDeliveryResponse,
    ValidatedReferenceListResponse,
    ValidatedReferenceResponse,
    WorkspaceSelectionRequest,
    WorkspaceSelectionResponse,
    WorkspaceSelectionViewResponse,
    WorkspaceResultViewResponse,
)
from .errors import CoreSafeError, SafeErrorCode, WorkspaceRequestError
from .canonical import sha256
from .analysis_runs import (
    AnalysisRunRequestError,
    analysis_run_id_for_operation,
    analysis_run_status,
    build_fresh_analysis_payload,
    build_fresh_reproduction_payload,
    is_strict_fresh_analysis_request,
    load_fresh_analysis_result,
)
from .governance import (
    DecisionBriefUnavailable,
    InvestigationRequestUnavailable,
)
from .decision_support_heads import (
    DecisionSupportEvaluationConflict,
    DecisionSupportEvaluationSeriesUnavailable,
    DecisionSupportEvaluationUnavailable,
    DecisionSupportHeadRaceLost,
)
from .decision_support_currentness import (
    DecisionSupportCurrentnessConflict,
    DecisionSupportCurrentnessOperationMismatch,
    DecisionSupportCurrentnessUnavailable,
)
from .draft_context import DraftContextUnavailable
from .drafts import (
    DraftHeadRace,
    DraftIdempotencyConflict,
    DraftStoreUnavailable,
)
from .manager_decisions import (
    ManagerDecisionConflict,
    ManagerDecisionHeadRace,
    ManagerDecisionUnavailable,
)
from .gemini_drafting import GeminiDraftingService, GeminiResponseProvider
from .monitoring import MonitoringContractError, monitoring_observation_key_for
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
from .settings import DeliveryProfile, Settings
from .state import StateRoot
from .recovery import StateRecovery, StateRecoveryError
from .operations import DurableOperation, OperationRunner, OperationStopReceipt
from .technical_log import TechnicalLog, TechnicalLogError
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
        is_refresh = (
            isinstance(path, str)
            and path.startswith("/api/investigations/")
            and path.endswith("/refresh")
        )
        if scope.get("type") != "http" or (
            path not in {
                "/api/investigations/reactive",
                "/api/investigations/proactive",
            }
            and not is_refresh
        ):
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
    gemini_provider: GeminiResponseProvider | None = None,
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
    state_recovery = StateRecovery(resolved_settings)
    stop_lock = threading.RLock()
    stop_response: LifecycleStopResponse | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            state_layout = state_root.initialize()
            if resolved_settings.profile is not DeliveryProfile.HOSTED:
                state_recovery.verify_current_state()
                state_recovery.ensure_baseline()
        except StateRecoveryError as error:
            try:
                safe_code = SafeErrorCode(error.code)
            except ValueError:
                safe_code = SafeErrorCode.STATE_CORRUPT
            raise CoreSafeError(safe_code, error.recovery_action) from error
        except CoreSafeError as error:
            if (
                error.code is SafeErrorCode.STATE_CORRUPT
                and resolved_settings.profile is not DeliveryProfile.HOSTED
            ):
                try:
                    state_recovery.verify_current_state()
                except StateRecoveryError as recovery_error:
                    raise CoreSafeError(
                        SafeErrorCode.STATE_CORRUPT,
                        recovery_error.recovery_action,
                    ) from recovery_error
            raise
        core_store.initialize()
        core_store.recover_interrupted_operations(state_layout)
        technical_log = TechnicalLog(state_layout.runtime_root / "technical.log")
        app.state.technical_log = technical_log
        app.state.state_layout = state_layout
        operation_runner = (
            OperationRunner(core_store, state_layout, technical_log=technical_log)
            if start_operation_runner
            else None
        )
        app.state.operation_runner = operation_runner
        if operation_runner is not None:
            operation_runner.start()
        try:
            yield
        finally:
            try:
                if operation_runner is not None:
                    operation_runner.stop()
            finally:
                try:
                    core_store.flush()
                finally:
                    core_store.close()
                    try:
                        technical_log.flush()
                    except TechnicalLogError:
                        pass

    app = FastAPI(
        title="Causal Delay Copilot Core",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.audit_store = core_store
    app.state.reference_store = reference_store
    app.state.gemini_drafting = GeminiDraftingService(
        resolved_settings,
        core_store,
        provider=gemini_provider,
    )
    app.state.operation_runner = None
    app.state.technical_log = None

    def _stop_response_from_receipt(
        receipt: OperationStopReceipt,
        *,
        ledger_flush_state: str,
        technical_log_flush_state: str,
    ) -> LifecycleStopResponse:
        outcome = receipt.outcome
        if (
            receipt.quarantine_failed_operation_ids
            or ledger_flush_state != "FLUSHED"
            or technical_log_flush_state != "FLUSHED"
        ):
            outcome = "STOP_FAILED"
        if outcome in {"STOP_TIMEOUT", "STOP_FAILED"}:
            recovery_action = "RESTORE_CORE_STATE_AND_RETRY"
        elif receipt.interrupted_operation_ids:
            recovery_action = "EXPLICIT_RETRY_AS_NEW_OPERATION"
        else:
            recovery_action = "NONE"
        return LifecycleStopResponse(
            schema_version="lifecycle-stop.v1",
            stop_id=receipt.stop_id,
            outcome=outcome,
            fresh_admission_state="CLOSED",
            interrupted_operation_ids=list(receipt.interrupted_operation_ids),
            cancellation_timeout_operation_ids=list(
                receipt.cancellation_timeout_operation_ids
            ),
            quarantine_failed_operation_ids=list(
                receipt.quarantine_failed_operation_ids
            ),
            ledger_flush_state=ledger_flush_state,
            technical_log_flush_state=technical_log_flush_state,
            recovery_action=recovery_action,
        )

    def _perform_lifecycle_stop() -> LifecycleStopResponse:
        nonlocal stop_response
        with stop_lock:
            if stop_response is not None:
                return stop_response.model_copy(update={"outcome": "ALREADY_STOPPED"})

            stop_id = f"stop-{uuid4()}"
            technical_log = getattr(app.state, "technical_log", None)
            if isinstance(technical_log, TechnicalLog):
                try:
                    technical_log.emit(
                        component="lifecycle",
                        correlation_id=stop_id,
                        lifecycle_code="STOP_REQUESTED",
                        recovery_action="WAIT_FOR_STOP_TO_FINISH",
                    )
                except TechnicalLogError:
                    pass

            operation_runner = getattr(app.state, "operation_runner", None)
            if isinstance(operation_runner, OperationRunner):
                receipt = operation_runner.stop(stop_id=stop_id)
            else:
                core_store.close_fresh_admission()
                interrupted = core_store.interrupt_queued_operations()
                recovered = core_store.recover_interrupted_operations(
                    app.state.state_layout
                )
                interrupted.extend(recovered)
                failed_quarantine = tuple(
                    operation_id
                    for operation_id in dict.fromkeys(recovered)
                    if (
                        (operation := core_store.get_operation_for_stop(operation_id))
                        is not None
                        and operation.artifact_state == "QUARANTINE_UNAVAILABLE"
                    )
                )
                receipt = OperationStopReceipt(
                    stop_id=stop_id,
                    outcome="STOPPED",
                    interrupted_operation_ids=tuple(dict.fromkeys(interrupted)),
                    cancellation_timeout_operation_ids=(),
                    quarantine_failed_operation_ids=failed_quarantine,
                )

            if isinstance(technical_log, TechnicalLog):
                for operation_id in receipt.interrupted_operation_ids:
                    try:
                        technical_log.emit(
                            component="operation_runner",
                            correlation_id=operation_id,
                            lifecycle_code="OPERATION_INTERRUPTED",
                            recovery_action="EXPLICIT_RETRY_AS_NEW_OPERATION",
                        )
                    except TechnicalLogError:
                        pass
                for operation_id in receipt.quarantine_failed_operation_ids:
                    try:
                        technical_log.emit(
                            component="operation_runner",
                            correlation_id=operation_id,
                            lifecycle_code="OPERATION_ARTIFACT_QUARANTINE_FAILED",
                            recovery_action="RESTORE_CORE_STATE_AND_RETRY",
                        )
                    except TechnicalLogError:
                        pass

            ledger_flush_state = "FLUSHED"
            try:
                core_store.flush()
            except (OSError, RuntimeError, sqlite3.Error):
                ledger_flush_state = "UNAVAILABLE"
            if isinstance(technical_log, TechnicalLog):
                if ledger_flush_state == "FLUSHED":
                    try:
                        technical_log.emit(
                            component="lifecycle",
                            correlation_id=stop_id,
                            lifecycle_code="LEDGER_FLUSHED",
                            recovery_action="NONE",
                        )
                    except TechnicalLogError:
                        pass
                try:
                    technical_log.emit(
                        component="lifecycle",
                        correlation_id=stop_id,
                        lifecycle_code=receipt.outcome,
                        recovery_action=(
                            "RESTORE_CORE_STATE_AND_RETRY"
                            if receipt.outcome == "STOP_TIMEOUT"
                            else "NONE"
                        ),
                    )
                    technical_log.emit(
                        component="lifecycle",
                        correlation_id=stop_id,
                        lifecycle_code="TECHNICAL_LOG_FLUSHED",
                        recovery_action="NONE",
                    )
                except TechnicalLogError:
                    pass
            technical_log_flush_state = "FLUSHED"
            if isinstance(technical_log, TechnicalLog):
                try:
                    technical_log.flush()
                except TechnicalLogError:
                    technical_log_flush_state = "UNAVAILABLE"
            stop_response = _stop_response_from_receipt(
                receipt,
                ledger_flush_state=ledger_flush_state,
                technical_log_flush_state=technical_log_flush_state,
            )
            return stop_response

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

    @app.exception_handler(DecisionSupportHeadRaceLost)
    async def handle_decision_support_head_race(
        _: Request,
        __: DecisionSupportHeadRaceLost,
    ) -> JSONResponse:
        return _error_response(
            409,
            SafeErrorCode.DECISION_SUPPORT_HEAD_RACE.value,
            "READ_THE_CURRENT_DECISION_SUPPORT_HEAD_AND_RETRY",
        )

    @app.exception_handler(DecisionSupportCurrentnessConflict)
    async def handle_decision_support_currentness_conflict(
        _: Request,
        __: DecisionSupportCurrentnessConflict,
    ) -> JSONResponse:
        return _error_response(
            409,
            "CURRENTNESS_OPERATION_CONFLICT",
            "USE_THE_EXACT_BOUND_CURRENTNESS_OPERATION_OR_CREATE_A_NEW_ONE",
        )

    @app.exception_handler(DecisionSupportCurrentnessOperationMismatch)
    async def handle_decision_support_currentness_mismatch(
        _: Request,
        __: DecisionSupportCurrentnessOperationMismatch,
    ) -> JSONResponse:
        return _error_response(
            409,
            "CURRENTNESS_OPERATION_MISMATCH",
            "PRESENT_THE_OPERATION_THROUGH_ITS_EXACT_BOUND_CONSUMER",
        )

    @app.exception_handler(DecisionSupportCurrentnessUnavailable)
    async def handle_decision_support_currentness_unavailable(
        _: Request,
        __: DecisionSupportCurrentnessUnavailable,
    ) -> JSONResponse:
        return _error_response(
            422,
            "CURRENTNESS_OPERATION_INVALID",
            "CORRECT_THE_HASH_BOUND_CURRENTNESS_ENVELOPE_AND_RETRY",
        )

    @app.exception_handler(DraftContextUnavailable)
    async def handle_draft_context_unavailable(
        _: Request,
        __: DraftContextUnavailable,
    ) -> JSONResponse:
        return _error_response(
            422,
            "DRAFT_CONTEXT_UNAVAILABLE",
            "RESTORE_A_CURRENT_APPROVED_ACTION_RECOMMENDATION_AND_RETRY",
        )

    @app.exception_handler(DraftIdempotencyConflict)
    async def handle_draft_idempotency_conflict(
        _: Request,
        __: DraftIdempotencyConflict,
    ) -> JSONResponse:
        return _error_response(
            409,
            SafeErrorCode.DRAFT_IDEMPOTENCY_CONFLICT.value,
            "USE_A_NEW_DRAFT_IDEMPOTENCY_KEY",
        )

    @app.exception_handler(DraftHeadRace)
    async def handle_draft_head_race(
        _: Request,
        __: DraftHeadRace,
    ) -> JSONResponse:
        return _error_response(
            409,
            SafeErrorCode.DRAFT_HEAD_RACE.value,
            "READ_THE_CURRENT_DRAFT_HEAD_AND_RETRY",
        )

    @app.exception_handler(DraftStoreUnavailable)
    async def handle_draft_store_unavailable(
        _: Request,
        __: DraftStoreUnavailable,
    ) -> JSONResponse:
        return _error_response(
            503,
            SafeErrorCode.DRAFT_UNAVAILABLE.value,
            "RESTORE_CORE_STATE_AND_RETRY",
        )

    @app.exception_handler(ManagerDecisionConflict)
    async def handle_manager_decision_conflict(
        _: Request,
        __: ManagerDecisionConflict,
    ) -> JSONResponse:
        return _error_response(
            409,
            SafeErrorCode.MANAGER_DECISION_IDEMPOTENCY_CONFLICT.value,
            "USE_A_NEW_MANAGER_DECISION_IDEMPOTENCY_KEY",
        )

    @app.exception_handler(ManagerDecisionHeadRace)
    async def handle_manager_decision_head_race(
        _: Request,
        __: ManagerDecisionHeadRace,
    ) -> JSONResponse:
        return _error_response(
            409,
            SafeErrorCode.MANAGER_DECISION_HEAD_RACE.value,
            "READ_THE_CURRENT_DRAFT_HEAD_AND_RETRY",
        )

    @app.exception_handler(ManagerDecisionUnavailable)
    async def handle_manager_decision_unavailable(
        _: Request,
        __: ManagerDecisionUnavailable,
    ) -> JSONResponse:
        return _error_response(
            422,
            SafeErrorCode.MANAGER_DECISION_UNAVAILABLE.value,
            "RESTORE_THE_EXACT_DRAFT_AND_CURRENTNESS_CHAIN_AND_RETRY",
        )

    @app.exception_handler(DecisionSupportEvaluationConflict)
    async def handle_decision_support_conflict(
        _: Request,
        __: DecisionSupportEvaluationConflict,
    ) -> JSONResponse:
        return _error_response(
            409,
            SafeErrorCode.DECISION_SUPPORT_EVALUATION_CONFLICT.value,
            "USE_A_NEW_DECISION_SUPPORT_IDEMPOTENCY_KEY",
        )

    @app.exception_handler(DecisionSupportEvaluationSeriesUnavailable)
    async def handle_decision_support_series_unavailable(
        _: Request,
        __: DecisionSupportEvaluationSeriesUnavailable,
    ) -> JSONResponse:
        return _error_response(
            404,
            SafeErrorCode.DECISION_SUPPORT_SERIES_UNAVAILABLE.value,
            "CHECK_THE_DECISION_SUPPORT_EVALUATION_SERIES_AND_RETRY",
        )

    @app.exception_handler(DecisionSupportEvaluationUnavailable)
    async def handle_decision_support_unavailable(
        _: Request,
        __: DecisionSupportEvaluationUnavailable,
    ) -> JSONResponse:
        return _error_response(
            503,
            SafeErrorCode.DECISION_SUPPORT_EVALUATION_UNAVAILABLE.value,
            "RESTORE_DECISION_SUPPORT_STATE_AND_RETRY",
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
        if error.code == SafeErrorCode.CORE_STOPPING:
            technical_log = getattr(app.state, "technical_log", None)
            if isinstance(technical_log, TechnicalLog):
                try:
                    technical_log.emit(
                        component="operation_store",
                        correlation_id=f"stop-{uuid4()}",
                        lifecycle_code="FRESH_OPERATION_REFUSED_STOPPING",
                        recovery_action="WAIT_FOR_STOP_TO_FINISH",
                    )
                except TechnicalLogError:
                    pass
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
            operation.operation_kind in {"FRESH_ANALYSIS", "FRESH_REPRODUCTION"}
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
        artifact_state = operation.artifact_state
        failure_code = operation.failure_code
        recovery_action = operation.recovery_action
        if analysis_run is not None and analysis_run.lifecycle == "quarantined":
            artifact_state = "QUARANTINED"
            failure_code = failure_code or analysis_run.failure_code
            recovery_action = recovery_action or analysis_run.recovery_action
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
            failure_code=failure_code,
            recovery_action=recovery_action,
            resource_warnings=list(operation.resource_warnings),
            artifact_state=artifact_state,
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
        if resolved_settings.gemini_configured:
            return HealthProbe(state="ready", code="CORE_READY")
        return HealthProbe(
            state="degraded",
            code="CORE_READY_GEMINI_DEGRADED",
        )

    @app.get("/api/health/live", response_model=HealthProbe)
    async def get_liveness() -> HealthProbe:
        return liveness_probe()

    @app.get("/api/release", response_model=ReleaseIdentityResponse)
    async def get_release_identity() -> JSONResponse:
        response = ReleaseIdentityResponse(
            schema_version="release-identity.v1",
            profile=resolved_settings.profile.value,
            release_candidate_id=resolved_settings.release_candidate_id,
            build_manifest_id=resolved_settings.build_manifest_id,
        )
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

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
        "/api/lifecycle/stop",
        response_model=LifecycleStopResponse,
    )
    async def stop_lifecycle() -> JSONResponse:
        if resolved_settings.profile is DeliveryProfile.HOSTED:
            return _error_response(
                405,
                SafeErrorCode.LIFECYCLE_STOP_UNAVAILABLE.value,
                "CANCEL_ACTIVE_OPERATION_THROUGH_API",
            )
        response = await asyncio.to_thread(_perform_lifecycle_stop)
        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode="json"),
        )

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
        elif request.operation_kind == "FRESH_REPRODUCTION":
            try:
                stored_request = build_fresh_reproduction_payload(
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
        if request.operation_kind in {"FRESH_ANALYSIS", "FRESH_REPRODUCTION"}:
            core_store.append_occurrence(
                AuditOccurrenceRequest(
                    idempotency_key=f"analysis-run-request:{stored.operation.operation_id}",
                    occurrence_kind="ANALYSIS_RUN_DELIVERY",
                    outcome_code=(
                        "FRESH_REPRODUCTION_REQUESTED"
                        if request.operation_kind == "FRESH_REPRODUCTION"
                        else "FRESH_ANALYSIS_REQUESTED"
                    ),
                ),
                resolution.snapshot.workspace_id,
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
        technical_log = getattr(app.state, "technical_log", None)
        if not stored.replayed and isinstance(technical_log, TechnicalLog):
            try:
                technical_log.emit(
                    component="operation_store",
                    correlation_id=operation_id,
                    lifecycle_code=(
                        "OPERATION_CANCEL_REQUESTED"
                        if stored.operation.state == "CANCELLING"
                        else "OPERATION_CANCELLED"
                    ),
                    recovery_action="EXPLICIT_RETRY_AS_NEW_OPERATION",
                )
            except TechnicalLogError:
                pass
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

    @app.get(
        "/api/decision-support/evaluation-series/{evaluation_series_id}",
        response_model=DecisionSupportEvaluationSeriesResponse,
    )
    async def get_decision_support_evaluation_series(
        request: Request,
        evaluation_series_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        series = core_store.get_decision_support_evaluation_series(
            resolution.snapshot.workspace_id,
            evaluation_series_id,
        )
        if series is None:
            return attach_workspace_cookie(workspace_resource_unavailable(), resolution)
        response = DecisionSupportEvaluationSeriesResponse.model_validate(series)
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=response.model_dump(mode="json")),
            resolution,
        )

    @app.post(
        "/api/decision-support/tradeoff-selections",
        response_model=TradeoffSelectionPublishResponse,
    )
    async def publish_tradeoff_selection(
        request_context: Request,
        request: TradeoffSelectionPublishRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.publish_tradeoff_selection(
            resolution.snapshot.workspace_id,
            selection=request.selection.model_dump(mode="python"),
        )
        response = TradeoffSelectionPublishResponse(
            result=stored.result,
            selection=stored.selection,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/decision-support/tradeoff-selections/accept",
        response_model=TradeoffSelectionAcceptanceResponse,
    )
    @app.post(
        "/api/decision-support/evaluation-series/{evaluation_series_id}/tradeoff-selection/accept",
        response_model=TradeoffSelectionAcceptanceResponse,
    )
    async def accept_tradeoff_selection(
        request_context: Request,
        request: TradeoffSelectionAcceptanceRequest,
        evaluation_series_id: str | None = None,
    ) -> JSONResponse:
        delivery_attempt = request.delivery_attempt.model_dump(
            mode="python",
            exclude_none=True,
        )
        selection = (
            None
            if request.selection is None
            else request.selection.model_dump(mode="python")
        )
        attempt_series_id = delivery_attempt.get("evaluation_series_id")
        if (
            evaluation_series_id is not None
            and attempt_series_id != evaluation_series_id
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "trade-off delivery attempt series does not match its route"
            )
        resolution = resolve_workspace(request_context)
        stored = core_store.accept_tradeoff_selection(
            resolution.snapshot.workspace_id,
            delivery_attempt=delivery_attempt,
            selection=selection,
        )
        response = TradeoffSelectionAcceptanceResponse(
            result=stored.result,
            selection_result=stored.selection_result,
            validation_result=stored.validation_result,
            delivery_attempt=stored.delivery_attempt,
            operation=stored.operation,
            currentness=stored.currentness,
            terminal_claim=stored.terminal_claim,
            selection_claim=stored.selection_claim,
            action_recommendation=stored.action_recommendation,
            head=stored.head,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/decision-support/currentness/check",
        response_model=DecisionSupportCurrentnessResponse,
    )
    async def check_decision_support_currentness(
        request_context: Request,
        request: DecisionSupportCurrentnessRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.check_decision_support_currentness(
            resolution.snapshot.workspace_id,
            operation=request.operation,
        )
        response = DecisionSupportCurrentnessResponse(
            result=stored.result,
            operation=stored.operation,
            currentness=stored.currentness,
            terminal_claim=stored.terminal_claim,
            render=stored.render,
            consuming_result=stored.consuming_result,
            head=stored.head,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/decision-support/monitoring-observations",
        response_model=DecisionSupportMonitoringObservationResponse,
    )
    async def register_decision_support_monitoring_observation(
        request_context: Request,
        request: DecisionSupportMonitoringObservationRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        existing_observation = None
        try:
            observation_key = monitoring_observation_key_for(request.observation)
        except MonitoringContractError:
            observation_key = None
        if observation_key is not None:
            existing_observation = next(
                (
                    item
                    for item in core_store.list_decision_support_monitoring_observations(
                        resolution.snapshot.workspace_id
                    )
                    if item.get("monitoring_observation_key") == observation_key
                ),
                None,
            )
        observation = core_store.register_monitoring_observation(
            resolution.snapshot.workspace_id,
            observation=request.observation,
        )
        result = "IDEMPOTENT_REPLAY" if existing_observation is not None else "CREATED"
        response = DecisionSupportMonitoringObservationResponse(
            result=result,
            observation=observation,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/decision-support/monitoring/match",
        response_model=DecisionSupportCurrentnessResponse,
    )
    @app.post(
        "/api/decision-support/monitoring-observations/match",
        response_model=DecisionSupportCurrentnessResponse,
    )
    @app.post(
        "/api/decision-support/evaluation-series/{evaluation_series_id}/monitoring/match",
        response_model=DecisionSupportCurrentnessResponse,
    )
    async def match_decision_support_monitoring_observation(
        request_context: Request,
        request: DecisionSupportMonitoringMatchRequest,
        evaluation_series_id: str | None = None,
    ) -> JSONResponse:
        if (
            evaluation_series_id is not None
            and request.evaluation_series_id is not None
            and evaluation_series_id != request.evaluation_series_id
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "monitoring match series does not match its route"
            )
        resolution = resolve_workspace(request_context)
        stored = core_store.match_monitoring_observation(
            resolution.snapshot.workspace_id,
            observation=request.observation,
            evaluation_series_id=evaluation_series_id or request.evaluation_series_id,
            accepted_selection_claim=request.accepted_selection_claim,
        )
        response = DecisionSupportCurrentnessResponse(
            result=stored.result,
            operation=stored.operation,
            currentness=stored.currentness,
            terminal_claim=stored.terminal_claim,
            render=stored.render,
            consuming_result=stored.consuming_result,
            head=stored.head,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.get(
        "/api/decision-support/monitoring-observations",
        response_model=list[dict[str, object]],
    )
    async def list_decision_support_monitoring_observations(
        request: Request,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        observations = core_store.list_decision_support_monitoring_observations(
            resolution.snapshot.workspace_id
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=observations),
            resolution,
        )

    @app.get(
        "/api/decision-support/monitoring-review-requests",
        response_model=list[dict[str, object]],
    )
    async def list_decision_support_monitoring_review_requests(
        request: Request,
    ) -> JSONResponse:
        resolution = resolve_workspace(request)
        requests = core_store.list_decision_support_monitoring_review_requests(
            resolution.snapshot.workspace_id
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=requests),
            resolution,
        )

    @app.post(
        "/api/decision-support/current-advice/render",
        response_model=DecisionSupportCurrentnessResponse,
    )
    @app.post(
        "/api/decision-support/evaluation-series/{evaluation_series_id}/current-advice/render",
        response_model=DecisionSupportCurrentnessResponse,
    )
    async def render_current_decision_support_advice(
        request_context: Request,
        render_request: DecisionSupportCurrentAdviceRenderRequest,
        evaluation_series_id: str | None = None,
    ) -> JSONResponse:
        if (
            evaluation_series_id is not None
            and evaluation_series_id != render_request.evaluation_series_id
        ):
            raise DecisionSupportCurrentnessUnavailable(
                "render request series does not match its route"
            )
        resolution = resolve_workspace(request_context)
        stored = core_store.render_current_advice(
            resolution.snapshot.workspace_id,
            render_request=render_request.model_dump(mode="json"),
        )
        response = DecisionSupportCurrentnessResponse(
            result=stored.result,
            operation=stored.operation,
            currentness=stored.currentness,
            terminal_claim=stored.terminal_claim,
            render=stored.render,
            consuming_result=stored.consuming_result,
            head=stored.head,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.post(
        "/api/decision-support/draft-context",
        response_model=DraftContextPreviewResponse,
    )
    async def prepare_decision_support_draft_context(
        request_context: Request,
        request: DraftContextRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        request_payload = request.current_advice.model_dump(mode="json")
        request_hash = sha256(
            {
                "kind": "DRAFT_CREATE",
                "manager_actor_ref": request.manager_actor_ref,
                "current_advice": request_payload,
            }
        )
        if request.idempotency_key is not None:
            existing = core_store.find_draft_idempotency(
                resolution.snapshot.workspace_id,
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
            )
            if existing is not None:
                response = DraftContextPreviewResponse(
                    schema_identifier="deterministic-draft-preview",
                    schema_version="1",
                    state="UNSENT_PREVIEW",
                    currentness=existing["currentness"],
                    draft_context=existing["source_context"],
                    artifact=existing["source_artifact"],
                    checker=existing["checker"],
                    drafting=existing["drafting"],
                    draft=existing,
                )
                return attach_workspace_cookie(
                    JSONResponse(status_code=200, content=response.model_dump(mode="json")),
                    resolution,
                )
        stored = core_store.render_current_advice(
            resolution.snapshot.workspace_id,
            render_request=request_payload,
        )
        current_advice = {
            "result": stored.result,
            "operation": stored.operation,
            "currentness": stored.currentness,
            "terminal_claim": stored.terminal_claim,
            "render": stored.render,
            "consuming_result": getattr(stored, "consuming_result", None),
            "head": stored.head,
        }
        prepared = await app.state.gemini_drafting.prepare(
            current_advice,
            workspace_id=resolution.snapshot.workspace_id,
        )
        draft = None
        if request.idempotency_key is not None:
            draft, _ = core_store.persist_prepared_draft(
                resolution.snapshot.workspace_id,
                idempotency_key=request.idempotency_key,
                request_hash=request_hash,
                manager_actor_ref=request.manager_actor_ref,
                available_at=request.current_advice.available_at,
                prepared=prepared,
            )
        response = DraftContextPreviewResponse(
            schema_identifier="deterministic-draft-preview",
            schema_version="1",
            state="UNSENT_PREVIEW",
            currentness=prepared["currentness"],
            draft_context=prepared["draft_context"],
            artifact=prepared["artifact"],
            checker=prepared["checker"],
            drafting=prepared["drafting"],
            draft=draft,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200,
                content=response.model_dump(mode="json", exclude_none=True),
            ),
            resolution,
        )

    @app.get(
        "/api/decision-support/drafts/{draft_id}",
        response_model=dict[str, object],
    )
    async def read_decision_support_draft(
        request_context: Request,
        draft_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        history = core_store.get_draft_history(
            resolution.snapshot.workspace_id,
            draft_id,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=history),
            resolution,
        )

    @app.post(
        "/api/decision-support/drafts/{draft_id}/edits",
        response_model=dict[str, object],
        status_code=201,
    )
    async def edit_decision_support_draft(
        request_context: Request,
        draft_id: str,
        request: DraftEditRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        draft, _ = core_store.edit_draft(
            resolution.snapshot.workspace_id,
            draft_id,
            idempotency_key=request.idempotency_key,
            manager_actor_ref=request.manager_actor_ref,
            expected_head=request.expected_head_ref_and_hash.model_dump(),
            subject=request.subject,
            body=request.body,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=201, content={"draft": draft}),
            resolution,
        )

    @app.post(
        "/api/decision-support/drafts/{draft_id}/dispositions",
        response_model=dict[str, object],
        status_code=201,
    )
    async def dispose_decision_support_draft(
        request_context: Request,
        draft_id: str,
        request: DraftDispositionRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        draft, _ = core_store.dispose_draft(
            resolution.snapshot.workspace_id,
            draft_id,
            idempotency_key=request.idempotency_key,
            manager_actor_ref=request.manager_actor_ref,
            expected_head=request.expected_head_ref_and_hash.model_dump(),
            disposition=request.disposition,
            rejection_reason=(
                request.rejection_reason.model_dump()
                if request.rejection_reason is not None
                else None
            ),
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=201, content={"draft": draft}),
            resolution,
        )

    @app.post(
        "/api/decision-support/drafts/{draft_id}/decisions",
        response_model=ManagerDecisionResponse,
    )
    @app.post(
        "/api/decision-support/drafts/{draft_id}/authorize",
        response_model=ManagerDecisionResponse,
    )
    async def record_decision_support_manager_decision(
        request_context: Request,
        draft_id: str,
        request: ManagerDecisionRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.record_manager_decision(
            resolution.snapshot.workspace_id,
            draft_id,
            idempotency_key=request.idempotency_key,
            manager_actor_ref=request.manager_actor_ref,
            expected_head=request.expected_head_ref_and_hash.model_dump(),
            disposition=request.disposition,
        )
        response = ManagerDecisionResponse(
            result=stored.result,
            decision=stored.decision,
            snapshot=stored.snapshot,
            draft=stored.draft,
            authorization_attempt=stored.authorization_attempt,
            authorization_currentness=stored.authorization_currentness,
            operation=stored.operation,
            currentness=stored.currentness,
            terminal_claim=stored.terminal_claim,
        )
        status_code = (
            200
            if stored.result == "IDEMPOTENT_REPLAY"
            else 409
            if stored.result == "CURRENTNESS_REFUSED"
            else 201
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=status_code,
                content=response.model_dump(mode="json"),
            ),
            resolution,
        )

    @app.get(
        "/api/decision-support/drafts/{draft_id}/decisions",
        response_model=dict[str, object],
    )
    async def list_decision_support_manager_decisions(
        request_context: Request,
        draft_id: str,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        decisions = core_store.get_manager_decisions(
            resolution.snapshot.workspace_id,
            draft_id,
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=decisions),
            resolution,
        )

    @app.get(
        "/api/decision-support/currentness",
        response_model=list[dict[str, object]],
    )
    async def list_decision_support_currentness(request: Request) -> JSONResponse:
        resolution = resolve_workspace(request)
        items = core_store.list_decision_support_currentness(
            resolution.snapshot.workspace_id
        )
        return attach_workspace_cookie(
            JSONResponse(status_code=200, content=items),
            resolution,
        )

    @app.post(
        "/api/decision-support/evaluation-series/{evaluation_series_id}/invalidations",
        response_model=DecisionSupportInvalidationResponse,
        status_code=201,
    )
    async def invalidate_decision_support_evaluation(
        request_context: Request,
        evaluation_series_id: str,
        request: DecisionSupportInvalidationRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        stored = core_store.invalidate_decision_support_evaluation(
            resolution.snapshot.workspace_id,
            idempotency_key=request.idempotency_key,
            evaluation_series_id=evaluation_series_id,
            expected_head_occurrence_id=request.expected_head_occurrence_id,
            expected_head_digest=request.expected_head_digest,
            expected_head_result_hash=request.expected_head_result_hash,
            invalidation_kind=request.invalidation_kind,
            invalidated_artifact_ref_and_hash=(
                request.invalidated_artifact_ref_and_hash.model_dump()
            ),
            authoritative_invalidation_ref_and_hash=(
                request.authoritative_invalidation_ref_and_hash.model_dump()
            ),
            reason_code=request.reason_code,
        )
        response = DecisionSupportInvalidationResponse(
            result=stored.result,
            invalidation=stored.invalidation,
            head=stored.head,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 201,
                content=response.model_dump(mode="json"),
            ),
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
            historical_state=replay.historical_state,
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
        "/api/investigations/{investigation_request_id}/refresh",
        response_model=RefreshInvestigationResponse,
        status_code=202,
    )
    async def refresh_investigation(
        request_context: Request,
        investigation_request_id: str,
        request: RefreshInvestigationRequest,
    ) -> JSONResponse:
        resolution = resolve_workspace(request_context)
        try:
            if request.trigger_mode == "reactive":
                source_request = RiskSignalRequest.model_validate(request.request)
                if source_request.trigger_mode != "reactive":
                    raise ValueError
                stored = core_store.create_reactive_investigation(
                    source_request,
                    resolution.snapshot.workspace_id,
                    idempotency_key=request.idempotency_key,
                    rerun_of_request_id=investigation_request_id,
                    refresh_observation_cutoff=request.observation_cutoff,
                )
            else:
                source_request = ProactiveProposalRequest.model_validate(request.request)
                if source_request.trigger_mode != "proactive":
                    raise ValueError
                stored = core_store.create_proactive_investigation(
                    source_request,
                    resolution.snapshot.workspace_id,
                    idempotency_key=request.idempotency_key,
                    rerun_of_request_id=investigation_request_id,
                    refresh_observation_cutoff=request.observation_cutoff,
                )
        except ValueError as error:
            raise WorkspaceRequestError(
                SafeErrorCode(
                    "RISK_SIGNAL_SCHEMA_UNSUPPORTED"
                    if request.trigger_mode == "reactive"
                    else "PROACTIVE_SCHEMA_UNSUPPORTED"
                ),
                "USE_THE_TYPED_REFRESH_SOURCE_REQUEST_AND_RETRY",
                422,
            ) from error

        operation = None
        refreshed_request_id = stored.attempt.get("investigation_request_id")
        if (
            stored.attempt.get("status")
            in {"accepted", "accepted_with_warning"}
            and isinstance(refreshed_request_id, str)
        ):
            try:
                stored_operation_request = build_fresh_analysis_payload(
                    core_store,
                    resolution.snapshot.workspace_id,
                    {
                        "investigation_request_id": refreshed_request_id,
                        "root_seed": request.root_seed,
                    },
                    resolved_settings,
                )
            except AnalysisRunRequestError as error:
                raise WorkspaceRequestError(
                    SafeErrorCode(error.code),
                    error.recovery_action,
                    error.status_code,
                ) from error
            stored_operation_request["run_relationship"] = "refresh"
            stored_operation_request["refresh_of_request_id"] = investigation_request_id
            stored_operation = core_store.admit_operation(
                resolution.snapshot.workspace_id,
                operation_kind="FRESH_ANALYSIS",
                idempotency_key=f"refresh-analysis:{request.idempotency_key}",
                request=stored_operation_request,
                memory_required_bytes=resolved_settings.quotas.compute_memory_request_bytes,
                state_root=resolved_settings.state_root,
            )
            operation = operation_response(stored_operation.operation)
            core_store.append_occurrence(
                AuditOccurrenceRequest(
                    idempotency_key=f"analysis-run-request:{stored_operation.operation.operation_id}",
                    occurrence_kind="ANALYSIS_RUN_DELIVERY",
                    outcome_code="REFRESH_ANALYSIS_REQUESTED",
                ),
                resolution.snapshot.workspace_id,
            )
        elif stored.result == "IDEMPOTENT_REPLAY":
            replayed_operation = core_store.get_operation_by_idempotency_key(
                resolution.snapshot.workspace_id,
                f"refresh-analysis:{request.idempotency_key}",
            )
            if replayed_operation is not None:
                operation = operation_response(replayed_operation)

        snapshot = (
            core_store.get_refresh_investigation_snapshot(
                resolution.snapshot.workspace_id,
                refreshed_request_id,
            )
            if isinstance(refreshed_request_id, str)
            else None
        )
        response = RefreshInvestigationResponse(
            result="IDEMPOTENT_REPLAY" if stored.result == "IDEMPOTENT_REPLAY" else "CREATED",
            trigger_mode=request.trigger_mode,
            attempt=stored.attempt,
            snapshot=(
                RefreshInvestigationSnapshotResponse(**snapshot)
                if isinstance(snapshot, dict)
                else None
            ),
            operation=operation,
        )
        return attach_workspace_cookie(
            JSONResponse(
                status_code=200 if stored.result == "IDEMPOTENT_REPLAY" else 202,
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
