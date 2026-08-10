from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime
import json
from typing import Any, Mapping, Protocol
from uuid import uuid4

import httpx

from .canonical import sha256
from .draft_context import (
    DraftContextUnavailable,
    check_deterministic_draft,
    check_gemini_draft_response,
    prepare_draft_from_current_advice,
    render_checked_gemini_draft,
    render_deterministic_draft,
    validate_draft_context,
)
from .errors import WorkspaceRequestError
from .settings import GeminiDraftingPolicy, Settings
from .workspace import WorkspaceStore


GEMINI_PROVIDER_ID = "gemini-httpx-rest"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.6-flash:generateContent"
)
GEMINI_DRAFTING_SCHEMA_IDENTIFIER = "gemini-drafting-result"
GEMINI_DRAFTING_SCHEMA_VERSION = "1"
_PROMPT_PREFIX = (
    "Return only JSON with the exact fields opening, connectiveBody, and closing. "
    "Write connective prose only. Do not add facts, numbers, dates, entities, "
    "actions, causal claims, authorization, or privacy-sensitive content. "
    "The supplied DraftContext is authoritative and must not be repeated.\n"
    "DraftContext:\n"
)
_SAFE_PROVIDER_FAILURE_CODES = frozenset(
    {
        "PROVIDER_CONFIGURATION_UNAVAILABLE",
        "PROVIDER_REQUEST_FAILED",
        "PROVIDER_TIMEOUT",
        "PROVIDER_HTTP_FAILURE",
        "PROVIDER_RESPONSE_MALFORMED",
        "PROVIDER_REFUSED",
    }
)


class GeminiProviderFailure(Exception):
    """A redacted provider failure that is safe to retry or audit."""

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if isinstance(code, str) and code in _SAFE_PROVIDER_FAILURE_CODES
            else "PROVIDER_REQUEST_FAILED"
        )
        super().__init__(self.code)


class GeminiResponseProvider(Protocol):
    async def generate(self, context: dict[str, Any]) -> object:
        """Return only the provider's structured response candidate."""


def _configuration_payload(policy: GeminiDraftingPolicy) -> dict[str, object]:
    return {
        "provider": GEMINI_PROVIDER_ID,
        "model": policy.model,
        "temperature": policy.temperature,
        "max_output_tokens": policy.max_output_tokens,
        "timeout_seconds": policy.timeout_seconds,
        "max_retries": policy.max_retries,
        "max_global_calls": policy.max_global_calls,
        "response_fields": list(policy.response_fields),
        "tools": False,
        "grounding": False,
        "history": False,
        "cache": False,
    }


class GeminiProvider:
    """One uncached HTTPX request boundary for Gemini structured prose."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return self._settings.gemini_configured

    async def generate(self, context: dict[str, Any]) -> object:
        validated_context = validate_draft_context(context)
        api_key = self._settings.gemini_api_key
        if api_key is None or not api_key.get_secret_value():
            raise GeminiProviderFailure("PROVIDER_CONFIGURATION_UNAVAILABLE")

        policy = self._settings.gemini_policy
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "opening": {"type": "STRING"},
                "connectiveBody": {"type": "STRING"},
                "closing": {"type": "STRING"},
            },
            "required": list(policy.response_fields),
        }
        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": _PROMPT_PREFIX + json.dumps(
                                validated_context,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": policy.temperature,
                "maxOutputTokens": policy.max_output_tokens,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=policy.timeout_seconds) as client:
                response = await client.post(
                    GEMINI_ENDPOINT,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                        "x-goog-api-key": api_key.get_secret_value(),
                    },
                    json=request_body,
                )
        except (httpx.HTTPError, TimeoutError, asyncio.TimeoutError) as error:
            raise GeminiProviderFailure("PROVIDER_REQUEST_FAILED") from error

        if response.status_code < 200 or response.status_code >= 300:
            raise GeminiProviderFailure("PROVIDER_HTTP_FAILURE")
        try:
            envelope = response.json()
        except ValueError as error:
            raise GeminiProviderFailure("PROVIDER_RESPONSE_MALFORMED") from error

        if not isinstance(envelope, Mapping):
            raise GeminiProviderFailure("PROVIDER_RESPONSE_MALFORMED")
        candidates = envelope.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise GeminiProviderFailure("PROVIDER_REFUSED")
        candidate = candidates[0]
        if not isinstance(candidate, Mapping):
            raise GeminiProviderFailure("PROVIDER_RESPONSE_MALFORMED")
        content = candidate.get("content")
        if not isinstance(content, Mapping):
            raise GeminiProviderFailure("PROVIDER_REFUSED")
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise GeminiProviderFailure("PROVIDER_REFUSED")
        part = parts[0]
        if not isinstance(part, Mapping) or not isinstance(part.get("text"), str):
            raise GeminiProviderFailure("PROVIDER_RESPONSE_MALFORMED")
        try:
            parsed = json.loads(str(part["text"]))
        except ValueError as error:
            raise GeminiProviderFailure("PROVIDER_RESPONSE_MALFORMED") from error
        if not isinstance(parsed, Mapping):
            raise GeminiProviderFailure("PROVIDER_RESPONSE_MALFORMED")
        return dict(parsed)


def _configuration_identity(policy: GeminiDraftingPolicy) -> str:
    return sha256(_configuration_payload(policy))


def _provider_metadata(
    policy: GeminiDraftingPolicy,
    *,
    attempts: list[dict[str, object]],
    source: str,
    fallback_reason: str | None,
    draft_operation_identity: str | None,
) -> dict[str, object]:
    configuration_identity = _configuration_identity(policy)
    fallback_identity = None
    if source == "DETERMINISTIC_ZERO_LLM":
        fallback_identity = sha256(
            {
                "renderer": "DETERMINISTIC_ZERO_LLM",
                "reason": fallback_reason,
                "draft_operation_identity": draft_operation_identity,
                "attempts": [attempt["attempt_identity"] for attempt in attempts],
            }
        )
    return {
        "schema_identifier": GEMINI_DRAFTING_SCHEMA_IDENTIFIER,
        "schema_version": GEMINI_DRAFTING_SCHEMA_VERSION,
        "state": "CHECKED" if source == "GEMINI_CHECKED" else "FALLBACK",
        "source": source,
        "provider": GEMINI_PROVIDER_ID,
        "model": policy.model,
        "configuration_identity": configuration_identity,
        "cache": "DISABLED",
        "attempts": deepcopy(attempts),
        "fallback": {
            "used": source != "GEMINI_CHECKED",
            "identity": fallback_identity,
            "reason_code": fallback_reason,
            "renderer": "DETERMINISTIC_ZERO_LLM",
        },
        "draft_operation_identity": draft_operation_identity,
    }


class GeminiDraftingService:
    """Prepare a current DraftContext with bounded checked prose or fallback."""

    def __init__(
        self,
        settings: Settings,
        workspace_store: WorkspaceStore,
        *,
        provider: GeminiResponseProvider | None = None,
    ) -> None:
        self._settings = settings
        self._workspace_store = workspace_store
        self._provider = provider or GeminiProvider(settings)
        self._global_call_gate = asyncio.Semaphore(
            settings.gemini_policy.max_global_calls
        )

    async def prepare(
        self,
        current_advice: object,
        *,
        workspace_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        # This validation is intentionally before provider admission: stale or invalid
        # evidence is unavailable and may never reach either Gemini or fallback.
        deterministic = prepare_draft_from_current_advice(current_advice)
        context = deterministic["draft_context"]
        policy = self._settings.gemini_policy

        if not self._settings.gemini_enabled:
            return self._fallback(
                deterministic,
                policy=policy,
                attempts=[],
                reason_code="GEMINI_DISABLED",
                draft_operation_identity=None,
            )
        if isinstance(self._provider, GeminiProvider) and not self._provider.configured:
            return self._fallback(
                deterministic,
                policy=policy,
                attempts=[],
                reason_code="PROVIDER_CONFIGURATION_UNAVAILABLE",
                draft_operation_identity=None,
            )

        draft_operation_identity = sha256(
            {
                "kind": "GEMINI_DRAFT_OPERATION",
                "context_hash": context["content_hash"],
                "nonce": uuid4().hex,
            }
        )
        try:
            self._workspace_store.admit_gemini_draft_operation(
                workspace_id,
                idempotency_key=f"gemini-draft:{uuid4().hex}",
                content_hash=sha256(
                    {
                        "operation": draft_operation_identity,
                        "context_hash": context["content_hash"],
                        "configuration": _configuration_identity(policy),
                    }
                ),
                now=now,
            )
        except WorkspaceRequestError:
            return self._fallback(
                deterministic,
                policy=policy,
                attempts=[],
                reason_code="GEMINI_DRAFT_QUOTA_REJECTED",
                draft_operation_identity=draft_operation_identity,
            )

        attempts: list[dict[str, object]] = []
        max_attempts = 1 + policy.max_retries
        for attempt_number in range(1, max_attempts + 1):
            attempt_identity = sha256(
                {
                    "kind": "GEMINI_DRAFT_ATTEMPT",
                    "draft_operation_identity": draft_operation_identity,
                    "attempt_number": attempt_number,
                }
            )
            try:
                self._workspace_store.record_gemini_attempt(
                    workspace_id,
                    idempotency_key=f"gemini-attempt:{uuid4().hex}",
                    content_hash=sha256(
                        {
                            "attempt": attempt_identity,
                            "context_hash": context["content_hash"],
                        }
                    ),
                    now=now,
                )
            except WorkspaceRequestError:
                attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "attempt_identity": attempt_identity,
                        "provider": GEMINI_PROVIDER_ID,
                        "model": policy.model,
                        "configuration_identity": _configuration_identity(policy),
                        "outcome": "QUOTA_REJECTED",
                        "failure_codes": ["GEMINI_ATTEMPT_QUOTA_REJECTED"],
                    }
                )
                return self._fallback(
                    deterministic,
                    policy=policy,
                    attempts=attempts,
                    reason_code="GEMINI_ATTEMPT_QUOTA_REJECTED",
                    draft_operation_identity=draft_operation_identity,
                )

            try:
                async with self._global_call_gate:
                    candidate = await self._provider.generate(deepcopy(context))
            except GeminiProviderFailure as error:
                attempts.append(
                    self._attempt_record(
                        attempt_number,
                        attempt_identity,
                        policy,
                        outcome="PROVIDER_FAILURE",
                        failure_codes=[error.code],
                    )
                )
                if attempt_number == max_attempts:
                    return self._fallback(
                        deterministic,
                        policy=policy,
                        attempts=attempts,
                        reason_code="PROVIDER_FAILURE",
                        draft_operation_identity=draft_operation_identity,
                    )
                continue
            except Exception:
                attempts.append(
                    self._attempt_record(
                        attempt_number,
                        attempt_identity,
                        policy,
                        outcome="PROVIDER_FAILURE",
                        failure_codes=["PROVIDER_REQUEST_FAILED"],
                    )
                )
                if attempt_number == max_attempts:
                    return self._fallback(
                        deterministic,
                        policy=policy,
                        attempts=attempts,
                        reason_code="PROVIDER_FAILURE",
                        draft_operation_identity=draft_operation_identity,
                    )
                continue

            checker = check_gemini_draft_response(context, candidate)
            checker_identity = sha256(
                {
                    "checker": checker.get("schema_identifier"),
                    "context_hash": context["content_hash"],
                    "response_identity": checker.get("response_identity"),
                    "state": checker["state"],
                    "failure_codes": checker["failure_codes"],
                }
            )
            if checker["state"] == "PASS":
                attempt = self._attempt_record(
                    attempt_number,
                    attempt_identity,
                    policy,
                    outcome="CHECKED",
                    checker_identity=checker_identity,
                    response_identity=checker.get("response_identity"),
                )
                attempts.append(attempt)
                drafting = _provider_metadata(
                    policy,
                    attempts=attempts,
                    source="GEMINI_CHECKED",
                    fallback_reason=None,
                    draft_operation_identity=draft_operation_identity,
                )
                artifact = render_checked_gemini_draft(
                    context,
                    candidate,
                    drafting_provenance=drafting,
                )
                checker_result = deepcopy(deterministic["checker"])
                checker_result["provider"] = checker
                checker_result["provider_checker_identity"] = checker_identity
                prepared = deepcopy(deterministic)
                prepared["artifact"] = artifact
                prepared["checker"] = checker_result
                prepared["drafting"] = drafting
                return prepared

            attempts.append(
                self._attempt_record(
                    attempt_number,
                    attempt_identity,
                    policy,
                    outcome="CHECKER_REJECTED",
                    checker_identity=checker_identity,
                    failure_codes=list(checker["failure_codes"]),
                    response_identity=checker.get("response_identity"),
                )
            )
            if attempt_number == max_attempts:
                return self._fallback(
                    deterministic,
                    policy=policy,
                    attempts=attempts,
                    reason_code="CHECKER_REJECTED",
                    draft_operation_identity=draft_operation_identity,
                )

        return self._fallback(
            deterministic,
            policy=policy,
            attempts=attempts,
            reason_code="PROVIDER_FAILURE",
            draft_operation_identity=draft_operation_identity,
        )

    @staticmethod
    def _attempt_record(
        attempt_number: int,
        attempt_identity: str,
        policy: GeminiDraftingPolicy,
        *,
        outcome: str,
        checker_identity: str | None = None,
        failure_codes: list[str] | None = None,
        response_identity: object | None = None,
    ) -> dict[str, object]:
        record: dict[str, object] = {
            "attempt_number": attempt_number,
            "attempt_identity": attempt_identity,
            "provider": GEMINI_PROVIDER_ID,
            "model": policy.model,
            "configuration_identity": _configuration_identity(policy),
            "outcome": outcome,
            "failure_codes": failure_codes or [],
        }
        if checker_identity is not None:
            record["checker_identity"] = checker_identity
        if isinstance(response_identity, str):
            record["response_identity"] = response_identity
        return record

    def _fallback(
        self,
        deterministic: dict[str, Any],
        *,
        policy: GeminiDraftingPolicy,
        attempts: list[dict[str, object]],
        reason_code: str,
        draft_operation_identity: str | None,
    ) -> dict[str, Any]:
        drafting = _provider_metadata(
            policy,
            attempts=attempts,
            source="DETERMINISTIC_ZERO_LLM",
            fallback_reason=reason_code,
            draft_operation_identity=draft_operation_identity,
        )
        prepared = deepcopy(deterministic)
        prepared["artifact"] = render_deterministic_draft(
            prepared["draft_context"],
            drafting_provenance=drafting,
        )
        prepared["checker"] = check_deterministic_draft(
            prepared["draft_context"], prepared["artifact"]
        )
        if prepared["checker"]["state"] != "PASS":
            raise DraftContextUnavailable("deterministic fallback failed its checker")
        prepared["drafting"] = drafting
        return prepared
