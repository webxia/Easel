"""Provider registry, capability gate, retry boundary, and failure isolation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from pydantic import Field, model_validator

from easel.materials.domain import MediaType
from easel.materials.domain.models import ContractModel, RetrievalIntent
from easel.materials.providers.base import MaterialProvider, ProviderPage
from easel.materials.providers.errors import (
    ProviderError,
    ProviderFailure,
    ProviderInvalidResponseError,
    ProviderNetworkError,
    ProviderTemporaryError,
    ProviderUnsupportedError,
    ProviderUnsupportedError,
)
from easel.materials.providers.models import (
    PaginationMode,
    ProviderCapability,
    ProviderContinuation,
    ProviderHealth,
    ProviderInfo,
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")


class ProviderSearchResult(ContractModel):
    provider_id: str = Field(min_length=1)
    page: ProviderPage | None = None
    failure: ProviderFailure | None = None

    @model_validator(mode="after")
    def exactly_one_result(self) -> ProviderSearchResult:
        if (self.page is None) == (self.failure is None):
            raise ValueError("ProviderSearchResult must contain exactly one of page or failure")
        if self.failure and self.failure.provider_id != self.provider_id:
            raise ValueError("ProviderSearchResult failure must belong to provider_id")
        if self.page and self.page.continuation and self.page.continuation.provider_id != self.provider_id:
            raise ValueError("ProviderSearchResult continuation must belong to provider_id")
        return self


class ProviderRegistry:
    """Registers neutral Provider adapters and isolates each search failure."""

    def __init__(self) -> None:
        self._providers: dict[str, MaterialProvider] = {}
        self._infos: dict[str, ProviderInfo] = {}

    def register(self, provider: MaterialProvider) -> ProviderInfo:
        info = provider.info()
        if info.provider_id in self._providers:
            raise ValueError(f"Provider already registered: {info.provider_id}")
        self._providers[info.provider_id] = provider
        self._infos[info.provider_id] = info
        return info

    def get(self, provider_id: str) -> MaterialProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"Provider not registered: {provider_id}") from exc

    def infos(self) -> tuple[ProviderInfo, ...]:
        return tuple(self._infos.values())

    def available_for(
        self,
        media_type: MediaType,
        capability: ProviderCapability = ProviderCapability.SEARCH,
    ) -> tuple[ProviderInfo, ...]:
        return tuple(info for info in self._infos.values() if info.supports(media_type, capability))

    def health(self, provider_id: str) -> ProviderHealth:
        """Read one adapter's current health without affecting other Providers."""
        provider = self.get(provider_id)
        info = self._infos[provider_id]
        if ProviderCapability.HEALTH_CHECK not in info.capabilities:
            raise ProviderUnsupportedError(provider_id, "Provider does not support HEALTH_CHECK")
        try:
            health = provider.health()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderTemporaryError(provider_id, f"Health check failed with {type(exc).__name__}") from exc
        if health.provider_id != provider_id:
            raise ProviderInvalidResponseError(provider_id, "Health record belongs to another Provider")
        return health

    def search_all(
        self,
        intent: RetrievalIntent,
        *,
        continuations: dict[str, ProviderContinuation] | None = None,
        retry_policy: RetryPolicy = RetryPolicy(),
        sleep: Callable[[float], None] = time.sleep,
    ) -> tuple[ProviderSearchResult, ...]:
        requested_type = intent.filters.get("media_type")
        try:
            media_type = MediaType(requested_type)
        except (TypeError, ValueError) as exc:
            raise ValueError("RetrievalIntent.filters.media_type must be a supported MediaType") from exc

        results: list[ProviderSearchResult] = []
        for info in self._infos.values():
            if not info.supports(media_type, ProviderCapability.SEARCH):
                failure = ProviderUnsupportedError(
                    info.provider_id,
                    f"Provider does not support SEARCH for media_type={media_type.value}",
                ).to_failure()
                results.append(ProviderSearchResult(provider_id=info.provider_id, failure=failure))
                continue
            continuation = (continuations or {}).get(info.provider_id)
            try:
                page = self._search_one(info, intent, continuation, retry_policy, sleep)
                results.append(ProviderSearchResult(provider_id=info.provider_id, page=page))
            except ProviderError as exc:
                results.append(ProviderSearchResult(provider_id=info.provider_id, failure=exc.to_failure()))
        return tuple(results)

    def _search_one(
        self,
        info: ProviderInfo,
        intent: RetrievalIntent,
        continuation: ProviderContinuation | None,
        retry_policy: RetryPolicy,
        sleep: Callable[[float], None],
    ) -> ProviderPage:
        if continuation is not None:
            if continuation.provider_id != info.provider_id:
                raise ProviderUnsupportedError(info.provider_id, "Continuation belongs to another Provider")
            if continuation.mode != info.pagination_mode or info.pagination_mode == PaginationMode.NONE:
                raise ProviderUnsupportedError(info.provider_id, "Continuation mode is unsupported by Provider")
        provider = self._providers[info.provider_id]
        for attempt in range(1, retry_policy.max_attempts + 1):
            try:
                page = provider.search(intent, continuation)
                if not isinstance(page, ProviderPage):
                    raise ProviderInvalidResponseError(info.provider_id, "Provider returned an invalid search page")
                if page.continuation is not None and (
                    page.continuation.provider_id != info.provider_id
                    or page.continuation.mode != info.pagination_mode
                    or info.pagination_mode == PaginationMode.NONE
                ):
                    raise ProviderInvalidResponseError(info.provider_id, "Provider returned invalid continuation state")
                for candidate in page.candidates:
                    if candidate.need_id is not None and candidate.need_id != intent.need_id:
                        raise ProviderInvalidResponseError(info.provider_id, "Candidate Need identity does not match request")
                    if candidate.media_type not in info.media_types:
                        raise ProviderInvalidResponseError(info.provider_id, "Candidate media_type exceeds declared capability")
                return page
            except ProviderError as exc:
                if exc.provider_id != info.provider_id:
                    raise ProviderInvalidResponseError(info.provider_id, "Provider raised an error for another Provider") from exc
                if not exc.retryable or attempt >= retry_policy.max_attempts:
                    raise
                delay = (
                    exc.retry_after_seconds
                    if exc.retry_after_seconds is not None
                    else retry_policy.initial_delay_seconds * (2 ** (attempt - 1))
                )
                if delay > retry_policy.max_delay_seconds:
                    raise
                if delay:
                    sleep(delay)
            except (TimeoutError, ConnectionError) as exc:
                if attempt >= retry_policy.max_attempts:
                    raise ProviderNetworkError(info.provider_id, type(exc).__name__) from exc
                delay = retry_policy.initial_delay_seconds * (2 ** (attempt - 1))
                if delay > retry_policy.max_delay_seconds:
                    raise ProviderNetworkError(info.provider_id, type(exc).__name__) from exc
                if delay:
                    sleep(delay)
            except Exception as exc:
                raise ProviderInvalidResponseError(
                    info.provider_id,
                    f"Provider adapter failed with {type(exc).__name__}",
                ) from exc
        raise ProviderError(info.provider_id, "Provider retry loop exhausted")
