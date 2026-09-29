"""Provider capability, continuation, and health contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator, model_validator

from easel.materials.domain import MediaType
from easel.materials.domain.models import ContractModel


class AccessMode(str, Enum):
    OFFICIAL_API = "OFFICIAL_API"
    PUBLIC_API = "PUBLIC_API"
    DIRECT_SEARCH = "DIRECT_SEARCH"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    LOCAL = "LOCAL"


class ProviderCapability(str, Enum):
    SEARCH = "SEARCH"
    PREVIEW = "PREVIEW"
    DETAIL = "DETAIL"
    RIGHTS_METADATA = "RIGHTS_METADATA"
    ATTRIBUTION_METADATA = "ATTRIBUTION_METADATA"
    DIRECT_DOWNLOAD = "DIRECT_DOWNLOAD"
    DOWNLOAD_TRACKING = "DOWNLOAD_TRACKING"
    PAGINATION = "PAGINATION"
    HEALTH_CHECK = "HEALTH_CHECK"


class PaginationMode(str, Enum):
    NONE = "NONE"
    PAGE = "PAGE"
    OFFSET = "OFFSET"
    TOKEN = "TOKEN"
    CURSOR = "CURSOR"
    NEXT_URL = "NEXT_URL"


class ProviderHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ProviderInfo(ContractModel):
    provider_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    media_types: tuple[MediaType, ...] = Field(min_length=1)
    access_mode: AccessMode
    capabilities: tuple[ProviderCapability, ...] = ()
    pagination_mode: PaginationMode = PaginationMode.NONE
    auth_mode: str = "none"
    quota_policy: str | None = None
    cache_policy: str | None = None
    attribution_policy: str | None = None
    acquisition_policy: str | None = None

    @model_validator(mode="after")
    def validate_capability_declarations(self) -> ProviderInfo:
        if len(self.media_types) != len(set(self.media_types)):
            raise ValueError("ProviderInfo media_types must be unique")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("ProviderInfo capabilities must be unique")
        has_pagination = ProviderCapability.PAGINATION in self.capabilities
        if has_pagination != (self.pagination_mode != PaginationMode.NONE):
            raise ValueError("pagination_mode and PAGINATION capability must agree")
        if (
            self.access_mode == AccessMode.DISCOVERY_ONLY
            and ProviderCapability.DIRECT_DOWNLOAD in self.capabilities
        ):
            raise ValueError("DISCOVERY_ONLY providers cannot claim DIRECT_DOWNLOAD")
        return self

    def supports(self, media_type: MediaType, capability: ProviderCapability) -> bool:
        return media_type in self.media_types and capability in self.capabilities


class ProviderContinuation(ContractModel):
    """Opaque, provider-owned paging state; Easel does not interpret token."""

    provider_id: str = Field(min_length=1)
    mode: PaginationMode
    token: str = Field(min_length=1)

    @field_validator("token")
    @classmethod
    def nonblank_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("continuation token must not be blank")
        return value


class ProviderFailureRecord(ContractModel):
    provider_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    retry_after_seconds: float | None = Field(default=None, ge=0)


class ProviderHealth(ContractModel):
    provider_id: str = Field(min_length=1)
    status: ProviderHealthStatus
    last_success_at: datetime | None = None
    last_error: ProviderFailureRecord | None = None
    quota_remaining: int | None = Field(default=None, ge=0)
    retry_after_seconds: float | None = Field(default=None, ge=0)
    degraded_reason: str | None = None

    @field_validator("last_success_at")
    @classmethod
    def timezone_aware_success(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("last_success_at must include a timezone")
        return value

    @model_validator(mode="after")
    def matching_error_owner(self) -> ProviderHealth:
        if self.last_error and self.last_error.provider_id != self.provider_id:
            raise ValueError("ProviderHealth last_error belongs to another provider")
        return self
