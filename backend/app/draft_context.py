from __future__ import annotations

from copy import deepcopy
import json
import math
import re
from typing import Any, Mapping

from .canonical import canonical_json, safe_sha256, sha256


DRAFT_CONTEXT_SCHEMA_IDENTIFIER = "draft-context"
DRAFT_CONTEXT_SCHEMA_VERSION = "1"
DRAFT_PREVIEW_SCHEMA_IDENTIFIER = "deterministic-draft-preview"
DRAFTED_ARTEFACT_SCHEMA_IDENTIFIER = "drafted-artefact"
DRAFTED_ARTEFACT_SCHEMA_VERSION = "1"
DRAFT_CHECK_SCHEMA_IDENTIFIER = "draft-context-check"
DRAFT_TEMPLATE_IDENTIFIER = "deterministic-zero-llm-draft"
DRAFT_TEMPLATE_VERSION = "1"
CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER = "current-advice-render-result"
CURRENT_ADVICE_RENDER_RESULT_SCHEMA_VERSION = "1"
GEMINI_DRAFT_RESPONSE_CHECK_SCHEMA_IDENTIFIER = "gemini-draft-response-check"
GEMINI_DRAFT_RESPONSE_CHECK_SCHEMA_VERSION = "1"
GEMINI_CHECKED_SOURCE = "GEMINI_CHECKED"

_ALLOWED_SELECTION_BASES = frozenset(
    {
        "SOLE_ELIGIBLE_OPTION",
        "UNIVERSAL_PARETO_DOMINANCE",
        "MANAGER_TRADEOFF_SELECTION",
        "MONITORING_FALLBACK_NO_POSITIVE_ACTIVE_OPTION",
    }
)
_ALLOWED_AUTHORIZATION_STATES = frozenset(
    {
        "NOT_RECORDED",
        "NOT_AUTHORIZED",
        "NOT_APPLICABLE",
        "PENDING_MANAGER_REVIEW",
    }
)
_REQUIRED_EVIDENCE_TAGS = (
    "DRIVER_EVIDENCE",
    "MECHANISTIC_LINK",
    "RULE_BASED_ELIGIBILITY",
    "ASSUMPTION_BASED_BENEFIT",
)
_FACT_FIELDS = (
    "benefit_projection",
    "costs",
    "assumptions",
    "calculations",
    "comparison_dimensions",
    "value_status",
)
_SOURCE_ONLY_FACT_KEYS = frozenset(
    {
        "record",
        "provenance",
        "source_record",
        "source_observation",
    }
)
_DATE_FIELDS = (
    "causal_decision_at",
    "constraints_as_of",
    "evaluation_published_at",
    "advice_valid_through",
)
_BLOCKED_KEY_PARTS = (
    "raw",
    "secret",
    "password",
    "token",
    "credential",
    "private",
    "confidential",
    "contract",
    "supplier_data",
    "contractor_data",
    "internal_id",
    "internal_identifier",
    "subject_identity",
    "record_id",
    "row_id",
)
_BLOCKED_TEXT_PATTERNS = (
    re.compile(r"\bconfidential\b", re.IGNORECASE),
    re.compile(
        r"\b(?:password|secret|api[ _-]?key|private[ _-]?key|access[ _-]?token)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:supplier|contractor)[ _-]?private\b", re.IGNORECASE),
    re.compile(r"\b(?:supplier|contractor)[ _-]?data\b", re.IGNORECASE),
    re.compile(
        r"\bcontract(?:or)?[ _-]?(?:data|details|number|id|terms)\b", re.IGNORECASE
    ),
    re.compile(r"\braw[ _-]?rows?\b", re.IGNORECASE),
    re.compile(r"\bunsafe[ _-]?internal\b", re.IGNORECASE),
    re.compile(r"\binternal[ _-]?(?:id|identifier|order|row|system)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:email|e-mail|phone|mobile)[ _-]?(?:address|number)?\s*[:=]",
        re.IGNORECASE,
    ),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
)
_UNSUPPORTED_MARKERS = frozenset(
    {
        "ABSTAINED",
        "INVALID",
        "NON_HEAD",
        "NOT_AUTHORIZED",
        "NOT_EVALUATED",
        "NOT_PERMITTED",
        "PROVISIONAL",
        "REJECTED",
        "STALE",
        "TENTATIVE",
        "UNAVAILABLE",
        "UNKNOWN",
        "UNSUPPORTED",
    }
)
_DATE_TOKEN_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)
_NUMBER_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z_])[+-]?(?:\d+(?:\.\d+)?)(?![A-Za-z_])")
_WORD_TOKEN_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b")
_ENTITY_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_-]{2,}\b")
_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_GEMINI_RESPONSE_FIELDS = ("opening", "connectiveBody", "closing")
_GEMINI_ALLOWED_ENTITY_TOKENS = frozenset({"MANAGER_NAME", "APPROVED_RECIPIENT"})
_GEMINI_TEMPLATE_MARKERS = (
    "subject:",
    "to:",
    "recorded facts:",
    "evidence tags:",
    "dates:",
    "allow-listed numeric tokens:",
)
_GEMINI_BLOCKED_ACTION_PATTERN = re.compile(
    r"\b(?:send|approve|approval|authorize|authorization|execute|reroute|expedite|switch)\b",
    re.IGNORECASE,
)
_GEMINI_STRONG_CAUSAL_PHRASES = (
    "proves the cause",
    "proves causation",
    "causes the delay",
    "caused by",
    "cause of the delay",
    "guarantees recovery",
    "guarantees that",
    "will recover",
    "establishes the individual cause",
    "the effect of this action",
    "the action will recover",
)


class DraftContextUnavailable(ValueError):
    """Raised when no safe deterministic draft context can be created."""


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH_PATTERN.fullmatch(value) is not None


def _ref_and_hash(value: object) -> dict[str, str] | None:
    mapped = _mapping(value)
    if mapped is None:
        return None
    reference = mapped.get("reference")
    content_hash = mapped.get("content_hash")
    if (
        not isinstance(reference, str)
        or not reference
        or len(reference) > 512
        or not _is_hash(content_hash)
    ):
        return None
    return {"reference": reference, "content_hash": str(content_hash)}


def _safe_binding(value: object, label: str) -> dict[str, str] | None:
    binding = _ref_and_hash(value)
    if binding is None:
        return None
    _safe_text(binding["reference"], f"{label}.reference")
    return binding


def _hash_without_content_hash(value: Mapping[str, Any]) -> str:
    content = deepcopy(dict(value))
    content.pop("content_hash", None)
    return sha256(content)


def _require_hash_bound_record(value: object, label: str) -> dict[str, Any]:
    mapped = _mapping(value)
    if mapped is None or not _is_hash(mapped.get("content_hash")):
        raise DraftContextUnavailable(f"{label} is not hash bound")
    if _hash_without_content_hash(mapped) != mapped.get("content_hash"):
        raise DraftContextUnavailable(f"{label} failed integrity")
    return deepcopy(dict(mapped))


def _safe_text(value: str, label: str) -> str:
    if (
        not value
        or len(value) > 4096
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise DraftContextUnavailable(f"{label} contains unsafe text")
    for pattern in _BLOCKED_TEXT_PATTERNS:
        if pattern.search(value):
            raise DraftContextUnavailable(f"{label} contains blocked content")
    return value


def _safe_key(key: object, label: str) -> str:
    if not isinstance(key, str) or not key or len(key) > 128:
        raise DraftContextUnavailable(f"{label} has an invalid field name")
    folded = key.casefold().replace("-", "_")
    if any(part in folded for part in _BLOCKED_KEY_PARTS):
        raise DraftContextUnavailable(f"{label} contains a blocked field")
    return key


def _assert_not_unsupported(value: object, label: str) -> None:
    if not isinstance(value, str):
        return
    tokens = set(re.findall(r"[A-Z][A-Z0-9_-]+", value.upper()))
    if tokens.intersection(_UNSUPPORTED_MARKERS):
        raise DraftContextUnavailable(f"{label} is not authoritative")


def _sanitize_value(
    value: object,
    label: str,
    *,
    omit_source_only_fields: bool = False,
) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key in sorted(value, key=str):
            key = _safe_key(raw_key, label)
            if omit_source_only_fields and key in _SOURCE_ONLY_FACT_KEYS:
                continue
            sanitized[key] = _sanitize_value(
                value[raw_key],
                f"{label}.{key}",
                omit_source_only_fields=omit_source_only_fields,
            )
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_value(
                item,
                f"{label}[{index}]",
                omit_source_only_fields=omit_source_only_fields,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return [
            _sanitize_value(
                item,
                f"{label}[{index}]",
                omit_source_only_fields=omit_source_only_fields,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DraftContextUnavailable(f"{label} contains a non-finite number")
        return value
    if isinstance(value, str):
        safe_value = _safe_text(value, label)
        _assert_not_unsupported(safe_value, label)
        return safe_value
    raise DraftContextUnavailable(f"{label} has an unsupported value")


def _sanitize_fact_value(value: object, label: str) -> Any:
    return _sanitize_value(value, label, omit_source_only_fields=True)


def _date_text(value: object, label: str) -> str | None:
    if isinstance(value, str):
        return _safe_text(value, label)
    mapped = _mapping(value)
    if mapped is None:
        return None
    for key in ("normalized_value", "value", "source_value"):
        candidate = mapped.get(key)
        if isinstance(candidate, str):
            return _safe_text(candidate, label)
    return None


def _numeric_tokens(value: object) -> list[str]:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    text = _DATE_TOKEN_PATTERN.sub(" ", text)
    return sorted(set(_NUMBER_TOKEN_PATTERN.findall(text)))


def _date_tokens(value: object) -> list[str]:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sorted(set(_DATE_TOKEN_PATTERN.findall(text)))


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        result: list[str] = []
        for child in value.values():
            result.extend(_string_values(child))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for child in value:
            result.extend(_string_values(child))
        return result
    return []


def _entity_tokens(values: object) -> list[str]:
    tokens: set[str] = set()
    for value in _string_values(values):
        for token in _ENTITY_TOKEN_PATTERN.findall(value):
            tokens.add(token)
        if value.startswith("[") and value.endswith("]"):
            tokens.add(value)
    return sorted(tokens)


def _collect_bindings(value: object, path: str = "") -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    mapped = _mapping(value)
    if mapped is not None:
        for raw_key in sorted(mapped, key=str):
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            child = mapped[raw_key]
            if key.endswith("ref_and_hash") or key.endswith("ref_and_hash_or_null"):
                _safe_key(key, child_path)
                if child is None:
                    continue
                binding = _safe_binding(child, child_path)
                if binding is None:
                    raise DraftContextUnavailable(
                        f"{child_path} is not a valid provenance binding"
                    )
                bindings.append({"field_path": child_path, **binding})
            else:
                bindings.extend(_collect_bindings(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            bindings.extend(_collect_bindings(child, f"{path}[{index}]"))
    return bindings


def _validate_current_advice(
    current_advice: object,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    envelope = _mapping(current_advice)
    if envelope is None:
        raise DraftContextUnavailable("current advice envelope is unavailable")
    if envelope.get("result") not in {"CREATED", "IDEMPOTENT_REPLAY"}:
        raise DraftContextUnavailable("current advice result is not published")

    currentness = _mapping(envelope.get("currentness"))
    terminal_claim = _mapping(envelope.get("terminal_claim"))
    head = _mapping(envelope.get("head"))
    operation = _mapping(envelope.get("operation"))
    render = _require_hash_bound_record(envelope.get("render"), "current advice render")
    if (
        currentness is None
        or terminal_claim is None
        or head is None
        or operation is None
    ):
        raise DraftContextUnavailable("current advice currentness proof is incomplete")
    if currentness.get("currentness_outcome") != "CURRENTNESS_PROVEN_AT_CHECK":
        raise DraftContextUnavailable("current advice is not current")
    if terminal_claim.get("currentness_outcome") != "CURRENTNESS_PROVEN_AT_CHECK":
        raise DraftContextUnavailable("current advice terminal claim is not current")
    head_binding = _safe_binding(
        head.get("head_record_ref_and_hash"), "current advice head"
    )
    if head.get("head_kind") != "EVALUATION" or head_binding is None:
        raise DraftContextUnavailable(
            "current advice is not bound to the evaluation head"
        )
    if (
        render.get("schema_identifier")
        != CURRENT_ADVICE_RENDER_RESULT_SCHEMA_IDENTIFIER
    ):
        raise DraftContextUnavailable("current advice render schema is unsupported")
    if render.get("schema_version") != CURRENT_ADVICE_RENDER_RESULT_SCHEMA_VERSION:
        raise DraftContextUnavailable(
            "current advice render schema version is unsupported"
        )
    render_operation_binding = _safe_binding(
        render.get("currentness_operation_ref_and_hash"),
        "current advice operation",
    )
    render_check_binding = _safe_binding(
        render.get("currentness_check_ref_and_hash"),
        "current advice check",
    )
    if render_operation_binding is None:
        raise DraftContextUnavailable("current advice operation binding is unavailable")
    if render_check_binding is None:
        raise DraftContextUnavailable("current advice check binding is unavailable")
    operation_binding = _safe_binding(
        operation.get("currentness_operation_ref_and_hash"),
        "currentness operation",
    )
    if (
        operation.get("currentness_operation_ref_and_hash") is not None
        and operation_binding is None
    ):
        raise DraftContextUnavailable("currentness operation binding is malformed")
    operation_occurrence_id = operation.get("operation_occurrence_id")
    operation_content_hash = operation.get("content_hash")
    derived_operation_binding = None
    if isinstance(operation_occurrence_id, str) and _is_hash(operation_content_hash):
        derived_operation_binding = {
            "reference": f"currentness-operation:{operation_occurrence_id}",
            "content_hash": str(operation_content_hash),
        }
    if (
        operation_binding is not None
        and derived_operation_binding is not None
        and operation_binding != derived_operation_binding
    ):
        raise DraftContextUnavailable("currentness operation bindings disagree")
    operation_binding = operation_binding or derived_operation_binding
    if operation_binding is None or operation_binding != render_operation_binding:
        raise DraftContextUnavailable(
            "current advice render is not bound to its operation"
        )

    for operation_field, render_field in (
        ("terminal_result_ref_and_hash", "evaluation_result_ref_and_hash"),
        ("recommendation_ref_and_hash_or_null", "recommendation_ref_and_hash_or_null"),
        ("recommendation_ref_and_hash", "recommendation_ref_and_hash_or_null"),
        (
            "accepted_selection_claim_ref_and_hash_or_null",
            "accepted_selection_claim_ref_and_hash_or_null",
        ),
        (
            "accepted_selection_claim_ref_and_hash",
            "accepted_selection_claim_ref_and_hash_or_null",
        ),
    ):
        if operation_field not in operation:
            continue
        operation_value = operation.get(operation_field)
        if (
            operation_value is not None
            and _safe_binding(operation_value, f"operation.{operation_field}") is None
        ):
            raise DraftContextUnavailable(f"operation.{operation_field} is invalid")
        render_value = render.get(render_field)
        expected = None if operation_value is None else _ref_and_hash(operation_value)
        actual = None if render_value is None else _ref_and_hash(render_value)
        if expected != actual:
            raise DraftContextUnavailable(
                f"current advice {operation_field} is not bound to its render result"
            )

    currentness_operation_binding = _safe_binding(
        currentness.get("currentness_operation_ref_and_hash"),
        "currentness operation check",
    )
    if (
        currentness.get("currentness_operation_ref_and_hash") is not None
        and currentness_operation_binding is None
    ):
        raise DraftContextUnavailable(
            "currentness check operation binding is malformed"
        )
    if (
        currentness_operation_binding is not None
        and currentness_operation_binding != render_operation_binding
    ):
        raise DraftContextUnavailable("currentness check is not bound to its operation")
    currentness_check_occurrence_id = currentness.get("currentness_check_occurrence_id")
    currentness_content_hash = currentness.get("content_hash")
    if (
        currentness_check_occurrence_id is not None
        or currentness_content_hash is not None
    ):
        if not isinstance(currentness_check_occurrence_id, str) or not _is_hash(
            currentness_content_hash
        ):
            raise DraftContextUnavailable("currentness check identity is incomplete")
        if {
            "reference": f"currentness-check:{currentness_check_occurrence_id}",
            "content_hash": str(currentness_content_hash),
        } != render_check_binding:
            raise DraftContextUnavailable(
                "currentness check is not bound to its render result"
            )
    evaluation_head_binding = _safe_binding(
        currentness.get("evaluation_head_ref_and_hash"),
        "currentness evaluation head",
    )
    if (
        currentness.get("evaluation_head_ref_and_hash") is not None
        and evaluation_head_binding is None
    ):
        raise DraftContextUnavailable(
            "currentness evaluation head binding is malformed"
        )
    if evaluation_head_binding is not None and evaluation_head_binding != head_binding:
        raise DraftContextUnavailable(
            "currentness check is not bound to the evaluation head"
        )
    observed_head_binding = _safe_binding(
        currentness.get("observed_authoritative_head_ref_and_hash"),
        "currentness observed head",
    )
    if (
        currentness.get("observed_authoritative_head_ref_and_hash") is not None
        and observed_head_binding is None
    ):
        raise DraftContextUnavailable("currentness observed head binding is malformed")
    if observed_head_binding is not None and observed_head_binding != head_binding:
        raise DraftContextUnavailable("currentness observed head is not authoritative")
    if currentness.get(
        "observed_authoritative_head_kind"
    ) is not None and currentness.get("observed_authoritative_head_kind") != head.get(
        "head_kind"
    ):
        raise DraftContextUnavailable("currentness observed head kind is inconsistent")
    head_occurrence_id = head.get("head_occurrence_id")
    if not isinstance(head_occurrence_id, str) or not head_occurrence_id:
        head_occurrence_id = head_binding["reference"]
    if (
        currentness.get("evaluation_occurrence_id") is not None
        and currentness.get("evaluation_occurrence_id") != head_occurrence_id
    ):
        raise DraftContextUnavailable(
            "currentness evaluation is not the authoritative head"
        )
    terminal_head = _mapping(terminal_claim.get("terminal_head"))
    if terminal_head is None:
        raise DraftContextUnavailable(
            "current advice terminal claim head is unavailable"
        )
    terminal_head_binding = _safe_binding(
        terminal_head.get("head_record_ref_and_hash"),
        "terminal claim head",
    )
    if (
        terminal_head.get("head_kind") != head.get("head_kind")
        or terminal_head_binding != head_binding
        or (
            terminal_head.get("head_occurrence_id") is not None
            and terminal_head.get("head_occurrence_id") != head_occurrence_id
        )
    ):
        raise DraftContextUnavailable(
            "terminal claim is not bound to the authoritative head"
        )
    if (
        _safe_binding(
            terminal_claim.get("terminal_currentness_ref_and_hash"),
            "terminal claim check",
        )
        != render_check_binding
    ):
        raise DraftContextUnavailable(
            "current advice terminal claim is not bound to its check"
        )
    chain = _mapping(render.get("advice_chain"))
    if chain is None:
        raise DraftContextUnavailable("current advice chain is unavailable")
    recommendation = _mapping(chain.get("action_recommendation"))
    if recommendation is None:
        raise DraftContextUnavailable("current advice has no published recommendation")
    recommendation_record = _require_hash_bound_record(
        recommendation,
        "action recommendation",
    )
    if recommendation_record.get("schema_identifier") != "action-recommendation":
        raise DraftContextUnavailable("action recommendation schema is unsupported")
    if recommendation_record.get("schema_version") != "1":
        raise DraftContextUnavailable(
            "action recommendation schema version is unsupported"
        )
    recommendation_binding = _ref_and_hash(
        render.get("recommendation_ref_and_hash_or_null")
    )
    if recommendation_binding is None or recommendation_binding != {
        "reference": recommendation_record.get("occurrence_id"),
        "content_hash": recommendation_record.get("content_hash"),
    }:
        raise DraftContextUnavailable("action recommendation binding is inconsistent")
    selection_basis = recommendation_record.get("selection_basis")
    if selection_basis not in _ALLOWED_SELECTION_BASES:
        raise DraftContextUnavailable(
            "action recommendation selection basis is not governed"
        )
    _assert_not_unsupported(selection_basis, "action recommendation selection basis")
    if (
        recommendation_record.get("action_effect_evidence")
        != "INTERVENTION_EFFECT_NOT_ESTIMATED"
    ):
        raise DraftContextUnavailable(
            "action recommendation effect evidence is invalid"
        )
    if recommendation_record.get("selection_is_not_authorization") is False:
        raise DraftContextUnavailable(
            "action recommendation carries an authorization claim"
        )
    authorization = _mapping(recommendation_record.get("authorization"))
    if authorization is not None:
        authorization_state = authorization.get("state")
        if authorization_state not in _ALLOWED_AUTHORIZATION_STATES:
            raise DraftContextUnavailable("action recommendation is already authorized")
        _assert_not_unsupported(
            authorization_state, "action recommendation authorization"
        )
    if selection_basis == "MANAGER_TRADEOFF_SELECTION":
        if render.get("advice_chain_kind") != "ACCEPTED_TRADEOFF_SELECTION":
            raise DraftContextUnavailable(
                "trade-off recommendation is not an accepted selection"
            )
        if (
            _ref_and_hash(render.get("accepted_selection_claim_ref_and_hash_or_null"))
            is None
        ):
            raise DraftContextUnavailable(
                "accepted trade-off selection claim is unavailable"
            )
    elif render.get("advice_chain_kind") == "ACCEPTED_TRADEOFF_SELECTION":
        raise DraftContextUnavailable(
            "non-trade-off recommendation has a selection claim"
        )
    if render.get("advice_chain_kind") not in {
        "IMMEDIATE_EVALUATION_RECOMMENDATION",
        "ACCEPTED_TRADEOFF_SELECTION",
    }:
        raise DraftContextUnavailable("current advice chain is not draftable")

    selected_option = _mapping(recommendation_record.get("selected_option"))
    if selected_option is None:
        raise DraftContextUnavailable("selected option is unavailable")
    option_code = recommendation_record.get("selected_option_code")
    option_version = recommendation_record.get("selected_option_version")
    if (
        not isinstance(option_code, str)
        or not option_code
        or selected_option.get("option_code") != option_code
        or not isinstance(option_version, str)
        or not option_version
        or selected_option.get("option_version") != option_version
    ):
        raise DraftContextUnavailable("selected action identity is inconsistent")
    _safe_text(option_code, "selected option code")
    _safe_text(option_version, "selected option version")
    option_label = selected_option.get("label")
    if not isinstance(option_label, str) or not option_label:
        raise DraftContextUnavailable("selected action label is unavailable")
    _safe_text(option_label, "selected option label")
    if selected_option.get("evaluation_state") != "ACTIVE":
        raise DraftContextUnavailable("selected option is not active")
    if selected_option.get("recommendation_eligible") is not True:
        raise DraftContextUnavailable("selected option is not recommendation eligible")

    evidence_tags = _mapping(recommendation_record.get("evidence_tags"))
    if evidence_tags is None:
        evidence_tags = _mapping(selected_option.get("evidence_tags"))
    if evidence_tags is None:
        raise DraftContextUnavailable("recommendation evidence tags are unavailable")
    safe_evidence_tags: dict[str, str] = {}
    for field in _REQUIRED_EVIDENCE_TAGS:
        value = evidence_tags.get(field)
        if not isinstance(value, str) or not value:
            raise DraftContextUnavailable(
                f"recommendation evidence tag {field} is unavailable"
            )
        _safe_text(value, f"recommendation evidence tag {field}")
        _assert_not_unsupported(value, f"recommendation evidence tag {field}")
        safe_evidence_tags[field] = value

    for source_label, source in (
        ("subject verdict", recommendation_record.get("subject_verdict")),
        ("population verdict", recommendation_record.get("population_verdict")),
    ):
        source_mapping = _mapping(source)
        if source_mapping is None:
            continue
        _assert_not_unsupported(source_mapping.get("verdict_code"), source_label)
        if source_mapping.get("decision_support_evaluation_permitted") is False:
            raise DraftContextUnavailable(
                f"{source_label} does not authorize Decision Support"
            )

    template_identifiers = recommendation_record.get("explanation_template_identifiers")
    if not isinstance(template_identifiers, list) or not template_identifiers:
        raise DraftContextUnavailable(
            "deterministic explanation template integrity failed"
        )
    for index, template in enumerate(template_identifiers):
        template_mapping = _mapping(template)
        if (
            template_mapping is None
            or not isinstance(template_mapping.get("identifier"), str)
            or not template_mapping.get("identifier")
            or not isinstance(template_mapping.get("version"), str)
            or not template_mapping.get("version")
        ):
            raise DraftContextUnavailable(
                f"deterministic explanation template {index} is invalid"
            )
        _safe_text(
            template_mapping["identifier"], f"explanation template {index}.identifier"
        )
        _safe_text(template_mapping["version"], f"explanation template {index}.version")

    return (
        render,
        recommendation_record,
        {
            "currentness": deepcopy(dict(currentness)),
            "terminal_claim": deepcopy(dict(terminal_claim)),
            "head": deepcopy(dict(head)),
            "chain": deepcopy(dict(chain)),
            "evidence_tags": safe_evidence_tags,
        },
    )


def _fact_lines(label: str, value: object) -> list[str]:
    if isinstance(value, Mapping):
        lines: list[str] = []
        for key in sorted(value, key=str):
            lines.extend(_fact_lines(f"{label}.{key}", value[key]))
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            lines.extend(_fact_lines(label, item))
        return lines
    if value is None:
        return [f"{label}: None"]
    return [f"{label}: {value}"]


def _build_context_payload(
    render: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    selected_option = _mapping(recommendation.get("selected_option"))
    if selected_option is None:
        raise DraftContextUnavailable("selected option is unavailable")
    option_code = str(recommendation["selected_option_code"])
    option_version = str(recommendation["selected_option_version"])
    option_label = str(selected_option["label"])

    recommendation_binding = {
        "reference": recommendation["occurrence_id"],
        "content_hash": recommendation["content_hash"],
    }
    fact_authorization = {
        "source": "action_recommendation.selected_option",
        "recommendation_ref_and_hash": recommendation_binding,
        "evidence_tags": deepcopy(dict(metadata["evidence_tags"])),
    }
    facts: list[dict[str, Any]] = []
    for field in _FACT_FIELDS:
        if field not in selected_option:
            continue
        facts.append(
            {
                "field": field,
                "value": _sanitize_fact_value(
                    selected_option[field],
                    f"selected_option.{field}",
                ),
            }
        )
    if not facts:
        raise DraftContextUnavailable("recommendation has no allow-listed facts")

    dates: list[dict[str, str]] = []
    for field in _DATE_FIELDS:
        value = _date_text(recommendation.get(field), f"recommendation.{field}")
        if value is not None:
            dates.append({"field_path": f"recommendation.{field}", "value": value})
    current_as_of = _date_text(render.get("current_as_of"), "render.current_as_of")
    if current_as_of is not None:
        dates.append({"field_path": "render.current_as_of", "value": current_as_of})
    dates = sorted(
        {(item["field_path"], item["value"]): item for item in dates}.values(),
        key=lambda item: item["field_path"],
    )

    evidence_tags = deepcopy(dict(metadata["evidence_tags"]))
    causal_language = (
        "The recorded population relationship is supported under stated assumptions; "
        "it does not establish an individual delay cause or an effect of the proposed action."
    )
    caveats = [
        "This is an assumption-based projection, not an estimated effect of the proposed action.",
        "Supplier-milestone evidence is not a claim about project recovery.",
        "No individual delay cause is asserted.",
        "Manager review is required.",
    ]
    authorization_language = [
        "Manager review is required.",
        "This is an unsent preview; it does not approve, authorize, send, or execute anything.",
    ]
    action = {
        "option_code": option_code,
        "option_version": option_version,
        "label": option_label,
        "selection_basis": str(recommendation["selection_basis"]),
    }
    entities = [
        {"kind": "ACTION_OPTION", "value": option_code},
        {"kind": "ACTION_LABEL", "value": option_label},
        {"kind": "RECIPIENT_PLACEHOLDER", "value": "[APPROVED_RECIPIENT]"},
        {"kind": "MANAGER_PLACEHOLDER", "value": "[MANAGER_NAME]"},
    ]
    provenance: dict[str, Any] = {
        "action_recommendation": recommendation_binding,
        "current_advice_render_result": {
            "reference": f"current-advice-render-result:{render['render_result_occurrence_id']}",
            "content_hash": render["content_hash"],
        },
        "currentness_operation": deepcopy(
            dict(render["currentness_operation_ref_and_hash"])
        ),
        "currentness_check": deepcopy(dict(render["currentness_check_ref_and_hash"])),
        "evaluation_result": deepcopy(dict(render["evaluation_result_ref_and_hash"])),
        "accepted_selection_claim": deepcopy(
            _ref_and_hash(render.get("accepted_selection_claim_ref_and_hash_or_null"))
        ),
        "source_bindings": _collect_bindings(recommendation),
    }
    provenance["currentness"] = {
        "outcome": metadata["currentness"].get("currentness_outcome"),
        "terminal_claim": deepcopy(dict(metadata["terminal_claim"])),
        "head": deepcopy(dict(metadata["head"])),
    }
    context: dict[str, Any] = {
        "schema_identifier": DRAFT_CONTEXT_SCHEMA_IDENTIFIER,
        "schema_version": DRAFT_CONTEXT_SCHEMA_VERSION,
        "state": "READY",
        "source": "DETERMINISTIC_CURRENT_ADVICE",
        "template": {
            "identifier": DRAFT_TEMPLATE_IDENTIFIER,
            "version": DRAFT_TEMPLATE_VERSION,
            "renderer": "DETERMINISTIC_ZERO_LLM",
        },
        "subject": f"Review request: {option_label}",
        "recipient": "[APPROVED_RECIPIENT]",
        "action": action,
        "facts": facts,
        "fact_authorization": [
            {"field": fact["field"], **deepcopy(fact_authorization)} for fact in facts
        ],
        "entities": entities,
        "dates": dates,
        "numbers": _numeric_tokens(
            [{"field": fact["field"], "value": fact["value"]} for fact in facts]
        ),
        "causal_language": [causal_language],
        "evidence_tags": evidence_tags,
        "caveats": caveats,
        "authorization_language": authorization_language,
        "deterministic_ownership": [
            "subject",
            "recipient",
            "action",
            "facts",
            "fact_authorization",
            "entities",
            "dates",
            "numbers",
            "causal_language",
            "evidence_tags",
            "caveats",
            "authorization_language",
        ],
        "allow_list": {
            "entity_tokens": _entity_tokens(
                {
                    "action": action,
                    "facts": facts,
                    "evidence_tags": evidence_tags,
                    "evidence_tag_names": list(_REQUIRED_EVIDENCE_TAGS),
                    "placeholders": ["[APPROVED_RECIPIENT]", "[MANAGER_NAME]"],
                }
            ),
            "date_tokens": _date_tokens(dates),
            "number_tokens": _numeric_tokens(
                [{"field": fact["field"], "value": fact["value"]} for fact in facts]
            ),
            "blocked_actions": [
                "send this automatically",
                "approve this on your behalf",
                "authorize this automatically",
                "execute this automatically",
            ],
            "redacted_fields": [
                "UNSAFE_SOURCE_RECORDS",
                "CONFIDENTIAL_PARTY_CONTENT",
                "SECRET_MATERIAL",
                "UNSAFE_INTERNAL_IDENTIFIERS",
                "SUBJECT_IDENTITY",
            ],
        },
        "provenance": provenance,
    }
    context_key = sha256(
        {
            "action_recommendation": provenance["action_recommendation"],
            "current_advice_render_result": provenance["current_advice_render_result"],
            "currentness": provenance["currentness"],
            "action": action,
            "facts": facts,
            "fact_authorization": context["fact_authorization"],
            "dates": dates,
        }
    )
    context["draft_context_key"] = context_key
    context["occurrence_id"] = f"draft-context:{context_key}"
    context["content_hash"] = _hash_without_content_hash(context)
    return context


def _validate_context(context: object) -> dict[str, Any]:
    mapped = _mapping(context)
    if mapped is None:
        raise DraftContextUnavailable("DraftContext is unavailable")
    record = deepcopy(dict(mapped))
    if record.get("schema_identifier") != DRAFT_CONTEXT_SCHEMA_IDENTIFIER:
        raise DraftContextUnavailable("DraftContext schema is unsupported")
    if record.get("schema_version") != DRAFT_CONTEXT_SCHEMA_VERSION:
        raise DraftContextUnavailable("DraftContext schema version is unsupported")
    if (
        record.get("state") != "READY"
        or record.get("source") != "DETERMINISTIC_CURRENT_ADVICE"
    ):
        raise DraftContextUnavailable("DraftContext is not ready")
    if not _is_hash(record.get("content_hash")) or _hash_without_content_hash(
        record
    ) != record.get("content_hash"):
        raise DraftContextUnavailable("DraftContext failed integrity")
    if not isinstance(record.get("draft_context_key"), str) or not _is_hash(
        record["draft_context_key"]
    ):
        raise DraftContextUnavailable("DraftContext key is invalid")
    if record.get("occurrence_id") != f"draft-context:{record['draft_context_key']}":
        raise DraftContextUnavailable("DraftContext occurrence is invalid")
    template = _mapping(record.get("template"))
    if (
        template is None
        or template.get("identifier") != DRAFT_TEMPLATE_IDENTIFIER
        or template.get("version") != DRAFT_TEMPLATE_VERSION
        or template.get("renderer") != "DETERMINISTIC_ZERO_LLM"
    ):
        raise DraftContextUnavailable("DraftContext template integrity failed")
    for field in (
        "subject",
        "recipient",
        "action",
        "facts",
        "fact_authorization",
        "entities",
        "dates",
        "numbers",
        "causal_language",
        "evidence_tags",
        "caveats",
        "authorization_language",
        "provenance",
        "allow_list",
    ):
        if field not in record:
            raise DraftContextUnavailable(f"DraftContext is missing {field}")
    _safe_text(str(record["subject"]), "DraftContext subject")
    if record.get("recipient") != "[APPROVED_RECIPIENT]":
        raise DraftContextUnavailable(
            "DraftContext recipient is not an approved placeholder"
        )
    action = _mapping(record.get("action"))
    if action is None:
        raise DraftContextUnavailable("DraftContext action is unavailable")
    for field in ("option_code", "option_version", "label", "selection_basis"):
        if not isinstance(action.get(field), str) or not action[field]:
            raise DraftContextUnavailable("DraftContext action identity is incomplete")
        _safe_text(action[field], f"DraftContext action {field}")
    if action.get("selection_basis") not in _ALLOWED_SELECTION_BASES:
        raise DraftContextUnavailable("DraftContext action basis is not governed")
    if not isinstance(record.get("facts"), list) or not record["facts"]:
        raise DraftContextUnavailable("DraftContext facts are unavailable")
    fact_authorization = record.get("fact_authorization")
    if not isinstance(fact_authorization, list) or len(fact_authorization) != len(
        record["facts"]
    ):
        raise DraftContextUnavailable("DraftContext fact authorization is unavailable")
    if not isinstance(record.get("dates"), list) or not isinstance(
        record.get("numbers"), list
    ):
        raise DraftContextUnavailable("DraftContext dates or numbers are invalid")
    if (
        not isinstance(record.get("causal_language"), list)
        or not record["causal_language"]
    ):
        raise DraftContextUnavailable("DraftContext causal language is unavailable")
    if not isinstance(record.get("caveats"), list) or not record["caveats"]:
        raise DraftContextUnavailable("DraftContext caveats are unavailable")
    if (
        not isinstance(record.get("authorization_language"), list)
        or not record["authorization_language"]
    ):
        raise DraftContextUnavailable(
            "DraftContext authorization language is unavailable"
        )
    for value in (
        record["subject"],
        record["recipient"],
        record["causal_language"],
        record["caveats"],
        record["authorization_language"],
        record["facts"],
        record["fact_authorization"],
        record["entities"],
        record["dates"],
        record["provenance"],
    ):
        _sanitize_value(value, "DraftContext")
    evidence_tags = _mapping(record.get("evidence_tags"))
    if evidence_tags is None or any(
        not isinstance(evidence_tags.get(field), str) or not evidence_tags.get(field)
        for field in _REQUIRED_EVIDENCE_TAGS
    ):
        raise DraftContextUnavailable("DraftContext evidence tags are incomplete")
    allow_list = _mapping(record.get("allow_list"))
    if allow_list is None or not all(
        isinstance(allow_list.get(field), list)
        for field in (
            "entity_tokens",
            "date_tokens",
            "number_tokens",
            "blocked_actions",
            "redacted_fields",
        )
    ):
        raise DraftContextUnavailable("DraftContext allow-list is incomplete")
    for field in (
        "entity_tokens",
        "date_tokens",
        "number_tokens",
        "blocked_actions",
        "redacted_fields",
    ):
        _sanitize_value(allow_list[field], f"DraftContext allow-list.{field}")
    provenance = _mapping(record.get("provenance"))
    if provenance is None:
        raise DraftContextUnavailable("DraftContext provenance is unavailable")
    for field in (
        "action_recommendation",
        "current_advice_render_result",
        "currentness_operation",
        "currentness_check",
        "evaluation_result",
    ):
        if (
            _safe_binding(provenance.get(field), f"DraftContext provenance {field}")
            is None
        ):
            raise DraftContextUnavailable(f"DraftContext provenance {field} is invalid")
    if (
        provenance.get("accepted_selection_claim") is not None
        and _safe_binding(
            provenance.get("accepted_selection_claim"),
            "DraftContext selection provenance",
        )
        is None
    ):
        raise DraftContextUnavailable("DraftContext selection provenance is invalid")
    expected_fact_binding = _safe_binding(
        provenance.get("action_recommendation"),
        "DraftContext fact recommendation provenance",
    )
    expected_evidence_tags = _mapping(record.get("evidence_tags"))
    fact_fields: set[str] = set()
    for fact in record["facts"]:
        fact_mapping = _mapping(fact)
        if fact_mapping is None or not isinstance(fact_mapping.get("field"), str):
            raise DraftContextUnavailable("DraftContext fact identity is malformed")
        fact_fields.add(fact_mapping["field"])
    authorized_fields: set[object] = set()
    for authorization in fact_authorization:
        authorization_mapping = _mapping(authorization)
        if authorization_mapping is None:
            raise DraftContextUnavailable(
                "DraftContext fact authorization is malformed"
            )
        field = authorization_mapping.get("field")
        source = authorization_mapping.get("source")
        binding = _safe_binding(
            authorization_mapping.get("recommendation_ref_and_hash"),
            "DraftContext fact authorization",
        )
        evidence = _mapping(authorization_mapping.get("evidence_tags"))
        if (
            not isinstance(field, str)
            or field not in fact_fields
            or field in authorized_fields
            or source != "action_recommendation.selected_option"
            or binding != expected_fact_binding
            or evidence is None
            or expected_evidence_tags is None
            or dict(evidence) != dict(expected_evidence_tags)
        ):
            raise DraftContextUnavailable(
                "DraftContext fact authorization is inconsistent"
            )
        authorized_fields.add(field)
    if authorized_fields != fact_fields:
        raise DraftContextUnavailable("DraftContext facts are not fully authorized")
    return record


def validate_draft_context(context: object) -> dict[str, Any]:
    """Validate and return the only DraftContext shape allowed at provider egress."""

    return _validate_context(context)


def build_draft_context(current_advice: object) -> dict[str, Any]:
    """Create one immutable, sanitized DraftContext from proven current advice."""

    render, recommendation, metadata = _validate_current_advice(current_advice)
    return _build_context_payload(render, recommendation, metadata)


def _render_body(context: Mapping[str, Any]) -> str:
    action = context["action"]
    lines = [
        f"Subject: {context['subject']}",
        f"To: {context['recipient']}",
        "",
        "Hello,",
        "",
        f"Please review the governed action {action['option_code']} ({action['label']}).",
        f"Selection basis: {action['selection_basis']}.",
        "",
        "Recorded facts:",
    ]
    for fact in context["facts"]:
        lines.extend(
            f"- {line}" for line in _fact_lines(str(fact["field"]), fact["value"])
        )
    lines.extend(["", "Evidence tags:"])
    for field in _REQUIRED_EVIDENCE_TAGS:
        lines.append(f"- {field}: {context['evidence_tags'][field]}")
    if context["dates"]:
        lines.extend(["", "Dates:"])
        for date_value in context["dates"]:
            lines.append(f"- {date_value['field_path']}: {date_value['value']}")
    if context["numbers"]:
        lines.extend(
            ["", f"Allow-listed numeric tokens: {', '.join(context['numbers'])}."]
        )
    lines.extend(["", *context["causal_language"], ""])
    lines.extend(context["caveats"])
    lines.extend(
        ["", *context["authorization_language"], "", "Thank you,", "[MANAGER_NAME]"]
    )
    return "\n".join(lines)


def _artifact_payload(
    context: Mapping[str, Any],
    *,
    drafting_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body = _render_body(context)
    artifact: dict[str, Any] = {
        "schema_identifier": DRAFTED_ARTEFACT_SCHEMA_IDENTIFIER,
        "schema_version": DRAFTED_ARTEFACT_SCHEMA_VERSION,
        "state": "UNSENT_PREVIEW",
        "source": "DETERMINISTIC_ZERO_LLM",
        "draft_context_ref_and_hash": {
            "reference": context["occurrence_id"],
            "content_hash": context["content_hash"],
        },
        "recommendation_ref_and_hash": deepcopy(
            context["provenance"]["action_recommendation"]
        ),
        "subject": context["subject"],
        "recipient": context["recipient"],
        "body": body,
        "deterministic_sections": {
            "opening": "Hello,",
            "connective_body": body.split("\n\nHello,\n\n", 1)[1].rsplit(
                "\n\nThank you,\n[MANAGER_NAME]", 1
            )[0],
            "closing": "Thank you,\n[MANAGER_NAME]",
        },
        "authorization_state": "NOT_AUTHORIZED",
        "provenance": deepcopy(context["provenance"]),
    }
    if drafting_provenance is not None:
        artifact["provenance"]["drafting"] = deepcopy(dict(drafting_provenance))
    artifact_key = sha256(
        {
            "draft_context_ref_and_hash": artifact["draft_context_ref_and_hash"],
            "recommendation_ref_and_hash": artifact["recommendation_ref_and_hash"],
            "source": artifact["source"],
            "provider_sections": artifact.get("provider_sections"),
            "drafting": artifact["provenance"].get("drafting"),
            "body": body,
        }
    )
    artifact["drafted_artefact_key"] = artifact_key
    artifact["occurrence_id"] = f"drafted-artefact:{artifact_key}"
    artifact["content_hash"] = _hash_without_content_hash(artifact)
    return artifact


def render_deterministic_draft(
    context: object,
    *,
    drafting_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Render the DraftContext without a provider or free-form generated text."""

    validated_context = _validate_context(context)
    return _artifact_payload(
        validated_context,
        drafting_provenance=drafting_provenance,
    )


def _add_failure(failures: list[str], code: str) -> None:
    if code not in failures:
        failures.append(code)


def _privacy_failure_codes(value: object) -> list[str]:
    serialized = canonical_json(value)
    codes: list[str] = []
    if any(pattern.search(serialized) for pattern in _BLOCKED_TEXT_PATTERNS):
        codes.append("UNSAFE_PRIVATE_CONTENT")
    return codes


def _gemini_forbidden_facts(context: Mapping[str, Any]) -> list[str]:
    phrases: set[str] = set()
    action = _mapping(context.get("action"))
    if action is not None:
        for field in ("option_code", "label"):
            value = action.get(field)
            if isinstance(value, str) and len(value) >= 3:
                phrases.add(value)
    for fact in context.get("facts", []):
        fact_mapping = _mapping(fact)
        if fact_mapping is not None:
            for value in _string_values(fact_mapping.get("value")):
                if len(value) >= 3:
                    phrases.add(value)
    evidence_tags = _mapping(context.get("evidence_tags"))
    if evidence_tags is not None:
        for value in _string_values(evidence_tags):
            if len(value) >= 3:
                phrases.add(value)
    return sorted(phrases, key=lambda value: (-len(value), value.casefold()))


def check_gemini_draft_response(
    context: object,
    response: object,
) -> dict[str, Any]:
    """Check provider prose without allowing it to become evidence or authority."""

    failures: list[str] = []
    checks: dict[str, str] = {}
    try:
        validated_context = _validate_context(context)
        checks["context_schema"] = "PASS"
        checks["context_integrity"] = "PASS"
    except DraftContextUnavailable:
        checks["context_schema"] = "FAIL"
        checks["context_integrity"] = "FAIL"
        _add_failure(failures, "INVALID_DRAFT_CONTEXT")
        return {
            "schema_identifier": GEMINI_DRAFT_RESPONSE_CHECK_SCHEMA_IDENTIFIER,
            "schema_version": GEMINI_DRAFT_RESPONSE_CHECK_SCHEMA_VERSION,
            "state": "FAIL",
            "failure_codes": failures,
            "checks": checks,
        }

    try:
        response_identity = safe_sha256(response)
    except (TypeError, ValueError, OverflowError):
        response_identity = sha256({"response_type": type(response).__name__})
    mapped = _mapping(response)
    normalized: dict[str, str] = {}
    if mapped is None or set(mapped) != set(_GEMINI_RESPONSE_FIELDS):
        _add_failure(failures, "PROVIDER_RESPONSE_SCHEMA_INVALID")
    else:
        for field in _GEMINI_RESPONSE_FIELDS:
            value = mapped.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 4096:
                _add_failure(failures, "PROVIDER_RESPONSE_SCHEMA_INVALID")
                continue
            try:
                normalized[field] = _safe_text(value, f"provider.{field}")
            except DraftContextUnavailable:
                _add_failure(failures, "PROVIDER_UNSAFE_PRIVATE_CONTENT")

    checks["response_schema"] = (
        "FAIL"
        if "PROVIDER_RESPONSE_SCHEMA_INVALID" in failures
        else "PASS"
    )
    serialized = canonical_json(normalized)
    if any(pattern.search(serialized) for pattern in _BLOCKED_TEXT_PATTERNS):
        _add_failure(failures, "PROVIDER_UNSAFE_PRIVATE_CONTENT")
    checks["privacy_redaction"] = (
        "FAIL"
        if "PROVIDER_UNSAFE_PRIVATE_CONTENT" in failures
        else "PASS"
    )

    text = "\n".join(normalized.values())
    if _numeric_tokens(normalized):
        _add_failure(failures, "PROVIDER_UNAUTHORIZED_NUMERIC_TOKEN")
    checks["numbers"] = (
        "FAIL" if "PROVIDER_UNAUTHORIZED_NUMERIC_TOKEN" in failures else "PASS"
    )
    if _date_tokens(normalized):
        _add_failure(failures, "PROVIDER_UNAUTHORIZED_DATE_TOKEN")
    checks["dates"] = (
        "FAIL" if "PROVIDER_UNAUTHORIZED_DATE_TOKEN" in failures else "PASS"
    )

    entity_tokens = set(_ENTITY_TOKEN_PATTERN.findall(text))
    unauthorized_entities = sorted(
        token
        for token in entity_tokens
        if token not in _GEMINI_ALLOWED_ENTITY_TOKENS
    )
    if unauthorized_entities:
        _add_failure(failures, "PROVIDER_UNAUTHORIZED_ENTITY")
    checks["entities"] = (
        "FAIL" if "PROVIDER_UNAUTHORIZED_ENTITY" in failures else "PASS"
    )

    folded_text = text.casefold()
    if any(
        phrase.casefold() in folded_text for phrase in _gemini_forbidden_facts(validated_context)
    ):
        _add_failure(failures, "PROVIDER_FORBIDDEN_FACT")
    checks["facts"] = "FAIL" if "PROVIDER_FORBIDDEN_FACT" in failures else "PASS"

    if _GEMINI_BLOCKED_ACTION_PATTERN.search(text):
        _add_failure(failures, "PROVIDER_BLOCKED_ACTION")
    checks["blocked_actions"] = (
        "FAIL" if "PROVIDER_BLOCKED_ACTION" in failures else "PASS"
    )

    if any(marker in folded_text for marker in _GEMINI_TEMPLATE_MARKERS):
        _add_failure(failures, "PROVIDER_TEMPLATE_INTEGRITY_FAILED")
    checks["template_integrity"] = (
        "FAIL"
        if "PROVIDER_TEMPLATE_INTEGRITY_FAILED" in failures
        else "PASS"
    )

    if any(phrase in folded_text for phrase in _GEMINI_STRONG_CAUSAL_PHRASES):
        _add_failure(failures, "PROVIDER_CAUSAL_LANGUAGE_TOO_STRONG")
    checks["causal_language"] = (
        "FAIL"
        if "PROVIDER_CAUSAL_LANGUAGE_TOO_STRONG" in failures
        else "PASS"
    )

    return {
        "schema_identifier": GEMINI_DRAFT_RESPONSE_CHECK_SCHEMA_IDENTIFIER,
        "schema_version": GEMINI_DRAFT_RESPONSE_CHECK_SCHEMA_VERSION,
        "state": "FAIL" if failures else "PASS",
        "failure_codes": failures,
        "checks": checks,
        "response_identity": response_identity,
        "allow_list_digest": sha256(validated_context["allow_list"]),
    }


def render_checked_gemini_draft(
    context: object,
    response: object,
    *,
    drafting_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose checked provider prose around deterministic evidence sections."""

    validated_context = _validate_context(context)
    provider_check = check_gemini_draft_response(validated_context, response)
    if provider_check["state"] != "PASS":
        raise DraftContextUnavailable("Gemini draft response failed its checker")
    provider_response = {
        field: str(_mapping(response)[field])  # type: ignore[index]
        for field in _GEMINI_RESPONSE_FIELDS
    }
    deterministic_artifact = _artifact_payload(validated_context)
    deterministic_sections = deterministic_artifact["deterministic_sections"]
    body = "\n".join(
        [
            f"Subject: {validated_context['subject']}",
            f"To: {validated_context['recipient']}",
            "",
            provider_response["opening"],
            "",
            provider_response["connectiveBody"],
            "",
            deterministic_sections["connective_body"],
            "",
            provider_response["closing"],
        ]
    )
    artifact: dict[str, Any] = {
        "schema_identifier": DRAFTED_ARTEFACT_SCHEMA_IDENTIFIER,
        "schema_version": DRAFTED_ARTEFACT_SCHEMA_VERSION,
        "state": "UNSENT_PREVIEW",
        "source": GEMINI_CHECKED_SOURCE,
        "draft_context_ref_and_hash": {
            "reference": validated_context["occurrence_id"],
            "content_hash": validated_context["content_hash"],
        },
        "recommendation_ref_and_hash": deepcopy(
            validated_context["provenance"]["action_recommendation"]
        ),
        "subject": validated_context["subject"],
        "recipient": validated_context["recipient"],
        "body": body,
        "deterministic_sections": deepcopy(deterministic_sections),
        "provider_sections": provider_response,
        "authorization_state": "NOT_AUTHORIZED",
        "provenance": deepcopy(validated_context["provenance"]),
    }
    if drafting_provenance is not None:
        artifact["provenance"]["drafting"] = deepcopy(dict(drafting_provenance))
    artifact_key = sha256(
        {
            "draft_context_ref_and_hash": artifact["draft_context_ref_and_hash"],
            "recommendation_ref_and_hash": artifact["recommendation_ref_and_hash"],
            "source": artifact["source"],
            "provider_sections": provider_response,
            "drafting": artifact["provenance"].get("drafting"),
            "body": body,
        }
    )
    artifact["drafted_artefact_key"] = artifact_key
    artifact["occurrence_id"] = f"drafted-artefact:{artifact_key}"
    artifact["content_hash"] = _hash_without_content_hash(artifact)
    return artifact


def check_deterministic_draft(
    context: object,
    artifact: object | None = None,
) -> dict[str, Any]:
    """Check context and rendered content against the deterministic contract."""

    failures: list[str] = []
    checks: dict[str, str] = {}
    validated_context: dict[str, Any] | None = None
    try:
        validated_context = _validate_context(context)
        checks["context_schema"] = "PASS"
        checks["context_integrity"] = "PASS"
    except DraftContextUnavailable:
        checks["context_schema"] = "FAIL"
        checks["context_integrity"] = "FAIL"
        _add_failure(failures, "INVALID_DRAFT_CONTEXT")

    if validated_context is None:
        return {
            "schema_identifier": DRAFT_CHECK_SCHEMA_IDENTIFIER,
            "schema_version": DRAFT_CONTEXT_SCHEMA_VERSION,
            "state": "FAIL",
            "failure_codes": failures,
            "checks": checks,
        }

    for value in (validated_context, artifact):
        if value is not None:
            for code in _privacy_failure_codes(value):
                _add_failure(failures, code)
    checks["privacy_redaction"] = (
        "FAIL" if "UNSAFE_PRIVATE_CONTENT" in failures else "PASS"
    )

    if not isinstance(artifact, Mapping):
        _add_failure(failures, "ARTIFACT_SCHEMA_INVALID")
        checks["artifact_schema"] = "FAIL"
        return {
            "schema_identifier": DRAFT_CHECK_SCHEMA_IDENTIFIER,
            "schema_version": DRAFT_CONTEXT_SCHEMA_VERSION,
            "state": "FAIL",
            "failure_codes": failures,
            "checks": checks,
        }
    candidate = deepcopy(dict(artifact))
    if (
        candidate.get("schema_identifier") != DRAFTED_ARTEFACT_SCHEMA_IDENTIFIER
        or candidate.get("schema_version") != DRAFTED_ARTEFACT_SCHEMA_VERSION
        or candidate.get("state") != "UNSENT_PREVIEW"
        or candidate.get("source") != "DETERMINISTIC_ZERO_LLM"
        or candidate.get("authorization_state") != "NOT_AUTHORIZED"
    ):
        _add_failure(failures, "ARTIFACT_SCHEMA_INVALID")
    checks["artifact_schema"] = (
        "FAIL" if "ARTIFACT_SCHEMA_INVALID" in failures else "PASS"
    )
    if not _is_hash(candidate.get("content_hash")) or _hash_without_content_hash(
        candidate
    ) != candidate.get("content_hash"):
        _add_failure(failures, "ARTIFACT_INTEGRITY_FAILED")
    checks["artifact_integrity"] = (
        "FAIL" if "ARTIFACT_INTEGRITY_FAILED" in failures else "PASS"
    )

    expected = _artifact_payload(validated_context)
    if (
        candidate.get("body") != expected["body"]
        or candidate.get("deterministic_sections") != expected["deterministic_sections"]
        or candidate.get("subject") != expected["subject"]
        or candidate.get("recipient") != expected["recipient"]
    ):
        _add_failure(failures, "TEMPLATE_INTEGRITY_FAILED")
    if (
        candidate.get("draft_context_ref_and_hash")
        != expected["draft_context_ref_and_hash"]
    ):
        _add_failure(failures, "DRAFT_CONTEXT_BINDING_FAILED")
    if (
        candidate.get("recommendation_ref_and_hash")
        != expected["recommendation_ref_and_hash"]
    ):
        _add_failure(failures, "RECOMMENDATION_BINDING_FAILED")
    checks["template_integrity"] = (
        "FAIL" if "TEMPLATE_INTEGRITY_FAILED" in failures else "PASS"
    )

    body = candidate.get("body") if isinstance(candidate.get("body"), str) else ""
    folded_body = body.casefold()
    allow_list = _mapping(validated_context["allow_list"]) or {}
    allowed_numbers = {str(value) for value in allow_list.get("number_tokens", [])}
    body_without_dates = _DATE_TOKEN_PATTERN.sub(" ", body)
    unauthorized_numbers = sorted(
        set(_NUMBER_TOKEN_PATTERN.findall(body_without_dates)).difference(
            allowed_numbers
        )
    )
    if unauthorized_numbers:
        _add_failure(failures, "UNAUTHORIZED_NUMERIC_TOKEN")
    checks["numbers"] = "FAIL" if unauthorized_numbers else "PASS"
    allowed_dates = {str(value) for value in allow_list.get("date_tokens", [])}
    unauthorized_dates = sorted(
        set(_DATE_TOKEN_PATTERN.findall(body)).difference(allowed_dates)
    )
    if unauthorized_dates:
        _add_failure(failures, "UNAUTHORIZED_DATE_TOKEN")
    checks["dates"] = "FAIL" if unauthorized_dates else "PASS"

    allowed_entities = {str(value) for value in allow_list.get("entity_tokens", [])}
    generic_entities = {
        "SUBJECT",
        "TO",
        "HELLO",
        "SELECTION",
        "BASIS",
        "RECORDED",
        "FACTS",
        "EVIDENCE",
        "TAGS",
        "DATES",
        "ALLOW",
        "LISTED",
        "NUMERIC",
        "TOKENS",
        "NONE",
        "MANAGER",
        "REVIEW",
        "REQUIRED",
        "THANK",
        "YOU",
    }
    unauthorized_entities = sorted(
        token
        for token in set(_ENTITY_TOKEN_PATTERN.findall(body))
        if token not in allowed_entities and token not in generic_entities
    )
    expected_words = set(_WORD_TOKEN_PATTERN.findall(expected["body"]))
    unexpected_words = sorted(
        set(_WORD_TOKEN_PATTERN.findall(body)).difference(expected_words)
    )
    if unexpected_words:
        _add_failure(failures, "UNAUTHORIZED_ENTITY")
    if unauthorized_entities:
        _add_failure(failures, "UNAUTHORIZED_ENTITY")
    checks["entities"] = "FAIL" if "UNAUTHORIZED_ENTITY" in failures else "PASS"

    required_phrases = [
        *validated_context["causal_language"],
        *validated_context["caveats"],
        *validated_context["authorization_language"],
    ]
    missing_phrases = [
        phrase for phrase in required_phrases if phrase.casefold() not in folded_body
    ]
    if missing_phrases:
        _add_failure(failures, "REQUIRED_CAVEAT_MISSING")
    checks["required_caveats"] = "FAIL" if missing_phrases else "PASS"

    blocked_action_phrases = [
        str(value).casefold() for value in allow_list.get("blocked_actions", [])
    ]
    blocked_action_phrases.extend(
        [
            "send this automatically",
            "approve this on your behalf",
            "authorize this automatically",
            "execute this automatically",
        ]
    )
    if any(phrase in folded_body for phrase in blocked_action_phrases):
        _add_failure(failures, "BLOCKED_ACTION")
    checks["blocked_actions"] = "FAIL" if "BLOCKED_ACTION" in failures else "PASS"

    if any(
        phrase in folded_body
        for phrase in (
            "proves the cause",
            "causes the delay",
            "caused by",
            "cause of the delay",
            "guarantees recovery",
            "guarantees that",
            "will recover",
            "establishes the individual cause",
        )
    ):
        _add_failure(failures, "CAUSAL_LANGUAGE_TOO_STRONG")
    checks["causal_language"] = (
        "FAIL" if "CAUSAL_LANGUAGE_TOO_STRONG" in failures else "PASS"
    )

    return {
        "schema_identifier": DRAFT_CHECK_SCHEMA_IDENTIFIER,
        "schema_version": DRAFT_CONTEXT_SCHEMA_VERSION,
        "state": "FAIL" if failures else "PASS",
        "failure_codes": failures,
        "checks": checks,
        "allow_list_digest": sha256(allow_list),
    }


def check_draft_context(
    context: object, artifact: object | None = None
) -> dict[str, Any]:
    return check_deterministic_draft(context, artifact)


def prepare_draft_from_current_advice(current_advice: object) -> dict[str, Any]:
    """Build, render, and check one unsent deterministic preview."""

    context = build_draft_context(current_advice)
    artifact = render_deterministic_draft(context)
    checker = check_deterministic_draft(context, artifact)
    if checker["state"] != "PASS":
        raise DraftContextUnavailable("deterministic draft check failed")
    return {
        "schema_identifier": DRAFT_PREVIEW_SCHEMA_IDENTIFIER,
        "schema_version": DRAFT_CONTEXT_SCHEMA_VERSION,
        "state": "UNSENT_PREVIEW",
        "currentness": deepcopy(context["provenance"]["currentness"]),
        "draft_context": context,
        "artifact": artifact,
        "checker": checker,
    }
