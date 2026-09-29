"""Normalized Provider error boundary, without raw response payloads."""

from __future__ import annotations

from enum import Enum
from typing import ClassVar, Mapping

from pydantic import Field

from easel.materials.domain.models import ContractModel


class ProviderErrorCategory(str, Enum):
    AUTH = "AUTH"
    ACCESS_DENIED = "ACCESS_DENIED"
    EDGE_BLOCKED = "EDGE_BLOCKED"
    RATE_LIMIT = "RATE_LIMIT"
    TEMPORARY = "TEMPORARY"
    NETWORK = "NETWORK"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    CONTRACT = "CONTRACT"
    UNSUPPORTED = "UNSUPPORTED"
    RIGHTS_UNAVAILABLE = "RIGHTS_UNAVAILABLE"
    DOWNLOAD_UNAVAILABLE = "DOWNLOAD_UNAVAILABLE"


class ProviderFailure(ContractModel):
    provider_id: str = Field(min_length=1)
    category: ProviderErrorCategory
    message: str = Field(min_length=1)
    retryable: bool = False
    retry_after_seconds: float | None = Field(default=None, ge=0)


class ProviderError(Exception):
    category: ClassVar[ProviderErrorCategory] = ProviderErrorCategory.TEMPORARY
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        provider_id: str,
        message: str,
        *,
        retryable: bool | None = None,
        retry_after_seconds: float | None = None,
    ):
        if not provider_id or not message:
            raise ValueError("ProviderError requires provider_id and message")
        if retry_after_seconds is not None and retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must be non-negative")
        super().__init__(message)
        self.provider_id = provider_id
        self.message = message
        self.retryable = self.default_retryable if retryable is None else retryable
        self.retry_after_seconds = retry_after_seconds

    def to_failure(self) -> ProviderFailure:
        return ProviderFailure(
            provider_id=self.provider_id,
            category=self.category,
            message=self.message,
            retryable=self.retryable,
            retry_after_seconds=self.retry_after_seconds,
        )


class ProviderAuthError(ProviderError):
    category = ProviderErrorCategory.AUTH


class ProviderAccessDeniedError(ProviderError):
    category = ProviderErrorCategory.ACCESS_DENIED


class ProviderEdgeBlockedError(ProviderAccessDeniedError):
    category = ProviderErrorCategory.EDGE_BLOCKED


class ProviderContractError(ProviderError):
    category = ProviderErrorCategory.CONTRACT


class ProviderRateLimitError(ProviderError):
    category = ProviderErrorCategory.RATE_LIMIT
    default_retryable = True


class ProviderTemporaryError(ProviderError):
    category = ProviderErrorCategory.TEMPORARY
    default_retryable = True


class ProviderNetworkError(ProviderError):
    category = ProviderErrorCategory.NETWORK
    default_retryable = True


class ProviderInvalidResponseError(ProviderError):
    category = ProviderErrorCategory.INVALID_RESPONSE


class ProviderUnsupportedError(ProviderError):
    category = ProviderErrorCategory.UNSUPPORTED


class ProviderRightsUnavailableError(ProviderError):
    category = ProviderErrorCategory.RIGHTS_UNAVAILABLE


class ProviderDownloadUnavailableError(ProviderError):
    category = ProviderErrorCategory.DOWNLOAD_UNAVAILABLE


def classify_http_error(
    provider_id: str,
    status_code: int,
    headers: Mapping[str, str],
    body: bytes,
    *,
    retry_after_seconds: float | None = None,
) -> ProviderError:
    """Classify an HTTP failure without exposing provider response text."""
    if status_code == 401:
        return ProviderAuthError(provider_id, f"{provider_id} rejected authentication (HTTP 401)")
    if status_code in (400, 403):
        text = body[:16_384].decode("utf-8", errors="replace").casefold()
        edge_markers = (
            "blocked access based on your browser's signature",
            "blocked access based on your browser signature",
            "browser's signature",
            "browser signature",
            "cloudflare ray id",
            "cf-chl-",
        )
        auth_markers = (
            "invalid token", "invalid bearer", "invalid api key", "invalid access token",
            "authentication credentials were not provided", "credentials are invalid",
            "invalid_client", "invalid client credentials", "client authentication failed",
            "invalid_grant",
        )
        if any(marker in text for marker in auth_markers):
            return ProviderAuthError(provider_id, f"{provider_id} rejected authentication (HTTP {status_code})")
        if status_code == 403:
            lowered_headers = {str(key).casefold(): str(value).casefold() for key, value in headers.items()}
            cloudflare_edge = (
                "cf-ray" in lowered_headers
                and "text/html" in lowered_headers.get("content-type", "")
            )
            if any(marker in text for marker in edge_markers) or cloudflare_edge:
                return ProviderEdgeBlockedError(provider_id, f"{provider_id} request was blocked by provider edge protection")
            return ProviderAccessDeniedError(provider_id, f"{provider_id} denied access (HTTP 403)")
    if status_code == 429:
        return ProviderRateLimitError(
            provider_id,
            f"{provider_id} API rate limit reached",
            retry_after_seconds=retry_after_seconds,
        )
    if status_code >= 500:
        return ProviderTemporaryError(provider_id, f"{provider_id} API temporarily unavailable (HTTP {status_code})")
    return ProviderContractError(provider_id, f"{provider_id} API rejected the request contract (HTTP {status_code})")


_ERROR_TYPES: dict[ProviderErrorCategory, type[ProviderError]] = {
    ProviderErrorCategory.AUTH: ProviderAuthError,
    ProviderErrorCategory.ACCESS_DENIED: ProviderAccessDeniedError,
    ProviderErrorCategory.EDGE_BLOCKED: ProviderEdgeBlockedError,
    ProviderErrorCategory.RATE_LIMIT: ProviderRateLimitError,
    ProviderErrorCategory.TEMPORARY: ProviderTemporaryError,
    ProviderErrorCategory.NETWORK: ProviderNetworkError,
    ProviderErrorCategory.INVALID_RESPONSE: ProviderInvalidResponseError,
    ProviderErrorCategory.CONTRACT: ProviderContractError,
    ProviderErrorCategory.UNSUPPORTED: ProviderUnsupportedError,
    ProviderErrorCategory.RIGHTS_UNAVAILABLE: ProviderRightsUnavailableError,
    ProviderErrorCategory.DOWNLOAD_UNAVAILABLE: ProviderDownloadUnavailableError,
}


def error_from_failure(failure: ProviderFailure) -> ProviderError:
    """Rehydrate the normalized typed failure without provider payload details."""
    error_type = _ERROR_TYPES[failure.category]
    return error_type(
        failure.provider_id,
        failure.message,
        retryable=failure.retryable,
        retry_after_seconds=failure.retry_after_seconds,
    )
