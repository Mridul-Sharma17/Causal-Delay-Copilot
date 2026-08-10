from __future__ import annotations

from enum import StrEnum
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import CoreSafeError, SafeErrorCode


class DeliveryProfile(StrEnum):
    HOSTED = "HOSTED"
    LOCAL_DEVELOPMENT = "LOCAL_DEVELOPMENT"
    LOCAL_FALLBACK = "LOCAL_FALLBACK"


class GeminiDraftingPolicy(BaseModel):
    """The immutable provider boundary for optional checked drafting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Literal["gemini-3.6-flash"] = "gemini-3.6-flash"
    temperature: Literal[0.0] = 0.0
    max_output_tokens: Literal[256] = 256
    timeout_seconds: Literal[15.0] = 15.0
    max_retries: Literal[1] = 1
    max_global_calls: Literal[1] = 1
    response_fields: tuple[
        Literal["opening"],
        Literal["connectiveBody"],
        Literal["closing"],
    ] = (
        "opening",
        "connectiveBody",
        "closing",
    )


class QuotaPolicy(BaseModel):
    """The bounded capacity contract persisted with one sealed state root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_workspaces: int = Field(default=100, ge=1)
    max_workspace_mutations: int = Field(default=200, ge=1)
    max_workspace_terminal_fresh_bundles: int = Field(default=4, ge=1)
    workspace_inactive_days: int = Field(default=7, ge=1)
    max_workspace_mutations_per_minute: int = Field(default=30, ge=1)
    max_global_mutations_per_minute: int = Field(default=120, ge=1)
    max_running_operations: int = Field(default=1, ge=1)
    max_waiting_operations: int = Field(default=2, ge=0)
    max_outstanding_operations_per_workspace: int = Field(default=1, ge=1)
    compute_timeout_seconds: float = Field(default=300.0, gt=0, le=300)
    compute_memory_request_bytes: int = Field(default=256 * 1024 * 1024, ge=1)
    memory_headroom_fraction: float = Field(default=0.25, ge=0, le=1)
    disk_warning_bytes: int = Field(default=1024 * 1024 * 1024, ge=1)
    disk_block_bytes: int = Field(default=512 * 1024 * 1024, ge=1)
    max_gemini_draft_operations_per_workspace_hour: int = Field(
        default=3,
        ge=1,
        le=3,
    )
    max_gemini_attempts_per_24h: int = Field(default=100, ge=1, le=100)


class RuntimeFingerprint(BaseModel):
    """Release/runtime identity kept separate from scientific request identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["runtime-fingerprint.v1"] = "runtime-fingerprint.v1"
    profile: DeliveryProfile
    release_candidate_id: str
    build_manifest_id: str

    @property
    def delivery_profile(self) -> DeliveryProfile:
        return self.profile


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _valid_origin(value: str, *, hosted: bool) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        return False

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or hostname is None
    ):
        return False
    if hosted:
        return parsed.scheme == "https" and hostname not in _LOOPBACK_HOSTS
    return parsed.scheme == "http" and hostname in _LOOPBACK_HOSTS


class Settings(BaseSettings):
    """One typed contract for hosted and both local delivery profiles."""

    model_config = SettingsConfigDict(
        env_prefix="CORE_",
        extra="ignore",
    )

    profile: DeliveryProfile | None = None
    delivery_profile: DeliveryProfile | None = None
    state_root: Path = Field(default=Path("state"))
    database_path: Path | None = None
    artifact_root: Path | None = None
    validated_reference_root: Path | None = None
    railway_volume_path: Path | None = None
    public_origin: str | None = None
    api_proxy_prefix: Literal["/api"] = "/api"
    bind_host: str | None = None
    offline_startup: bool = True
    web_worker_count: int = Field(default=1, ge=1)
    sqlite_writer_count: int = Field(default=1, ge=1)
    compute_subprocess_count: int = Field(default=1, ge=1)
    release_candidate_id: str | None = Field(default=None, min_length=1, max_length=128)
    build_manifest_id: str | None = Field(default=None, min_length=1, max_length=128)
    quotas: QuotaPolicy = Field(default_factory=QuotaPolicy)
    gemini_enabled: bool = False
    gemini_api_key: SecretStr | None = None
    gemini_policy: GeminiDraftingPolicy = Field(default_factory=GeminiDraftingPolicy)
    spa_dist_dir: Path | None = None

    def __init__(self, **values: Any) -> None:
        try:
            super().__init__(**values)
        except ValidationError as error:
            raise CoreSafeError(
                SafeErrorCode.CONFIGURATION_INVALID,
                "CORRECT_CONFIGURATION_AND_RETRY",
            ) from error

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_paths_and_profile_aliases(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        if normalized.get("profile") is None and "delivery_profile" in normalized:
            normalized["profile"] = normalized["delivery_profile"]
        if normalized.get("delivery_profile") is None and "profile" in normalized:
            normalized["delivery_profile"] = normalized["profile"]
        if "state_root" not in normalized and normalized.get("database_path") is not None:
            normalized["state_root"] = Path(normalized["database_path"]).parent
        return normalized

    @model_validator(mode="after")
    def validate_delivery_contract(self) -> Settings:
        if self.profile is None and self.delivery_profile is None:
            selected_profile = DeliveryProfile.LOCAL_DEVELOPMENT
        elif self.profile is None:
            selected_profile = self.delivery_profile
        elif self.delivery_profile is None:
            selected_profile = self.profile
        elif self.profile is not self.delivery_profile:
            raise ValueError("profile aliases disagree")
        else:
            selected_profile = self.profile

        if selected_profile is None:
            raise ValueError("profile is missing")
        self.profile = selected_profile
        self.delivery_profile = selected_profile

        expected_database_path = self.state_root / "core.sqlite3"
        if self.database_path is None:
            self.database_path = expected_database_path
        elif self.database_path != expected_database_path:
            raise ValueError("database path must belong to the state root")

        expected_artifact_root = self.state_root / "artifacts"
        if self.artifact_root is None:
            self.artifact_root = expected_artifact_root
        elif self.artifact_root != expected_artifact_root:
            raise ValueError("artifact path must belong to the state root")

        expected_reference_root = expected_artifact_root / "validated-references"
        if self.validated_reference_root is None:
            self.validated_reference_root = expected_reference_root
        elif self.validated_reference_root != expected_reference_root:
            raise ValueError("validated reference path must belong to the artifact root")

        if self.api_proxy_prefix != "/api":
            raise ValueError("the browser API proxy must be relative /api")
        if self.web_worker_count != 1 or self.sqlite_writer_count != 1:
            raise ValueError("Core requires one web worker and one SQLite writer")
        if self.compute_subprocess_count != 1:
            raise ValueError("Core requires one compute subprocess")

        if selected_profile is DeliveryProfile.HOSTED:
            self._validate_hosted_contract()
        else:
            self._validate_local_contract()

        return self

    def _validate_hosted_contract(self) -> None:
        if self.railway_volume_path is None or not self.railway_volume_path.is_absolute():
            raise ValueError("hosted state requires an absolute Railway volume path")
        if not self.state_root.is_absolute() or not _is_within(
            self.state_root,
            self.railway_volume_path,
        ):
            raise ValueError("hosted state must remain below the Railway volume")
        if not _valid_origin(self.public_origin or "", hosted=True):
            raise ValueError("hosted delivery requires an HTTPS public origin")
        if self.bind_host is None:
            self.bind_host = "0.0.0.0"
        elif self.bind_host != "0.0.0.0":
            raise ValueError("hosted delivery must bind the Railway interface")
        if self.release_candidate_id is None or self.build_manifest_id is None:
            raise ValueError("hosted delivery requires release and build identities")
        if not _IDENTIFIER_PATTERN.fullmatch(self.release_candidate_id):
            raise ValueError("release identity is invalid")
        if not _IDENTIFIER_PATTERN.fullmatch(self.build_manifest_id):
            raise ValueError("build identity is invalid")

    def _validate_local_contract(self) -> None:
        if self.railway_volume_path is not None:
            raise ValueError("local delivery cannot use a Railway volume contract")
        if self.public_origin is not None and not _valid_origin(
            self.public_origin,
            hosted=False,
        ):
            raise ValueError("local delivery requires a loopback HTTP origin")
        if self.bind_host is None:
            self.bind_host = "127.0.0.1"
        elif self.bind_host not in _LOOPBACK_HOSTS:
            raise ValueError("local delivery must bind loopback")
        if not self.offline_startup:
            raise ValueError("local delivery requires offline startup")
        profile_name = self.profile.value.lower()
        if self.release_candidate_id is None:
            self.release_candidate_id = f"local-{profile_name}"
        if self.build_manifest_id is None:
            self.build_manifest_id = f"local-{profile_name}"

        if not _IDENTIFIER_PATTERN.fullmatch(self.release_candidate_id):
            raise ValueError("release identity is invalid")
        if not _IDENTIFIER_PATTERN.fullmatch(self.build_manifest_id):
            raise ValueError("build identity is invalid")

    @property
    def runtime_fingerprint(self) -> RuntimeFingerprint:
        return RuntimeFingerprint(
            profile=self.profile,
            release_candidate_id=self.release_candidate_id,
            build_manifest_id=self.build_manifest_id,
        )

    @property
    def quota_policy(self) -> QuotaPolicy:
        return self.quotas

    @property
    def gemini_configured(self) -> bool:
        return self.gemini_enabled and self.gemini_api_key is not None and bool(
            self.gemini_api_key.get_secret_value()
        )
