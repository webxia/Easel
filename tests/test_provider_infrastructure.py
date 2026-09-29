from __future__ import annotations

from datetime import datetime, timezone

import pytest

from easel.materials.domain import (
    Availability,
    CandidateSource,
    MediaType,
    RetrievalIntent,
    SupplyCandidate,
)
from easel.materials.providers import (
    AccessMode,
    PaginationMode,
    ProviderCapability,
    ProviderContinuation,
    ProviderErrorCategory,
    ProviderFailure,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderInfo,
    ProviderNetworkError,
    ProviderPage,
    ProviderRateLimitError,
    ProviderRegistry,
    ProviderTemporaryError,
    RetryPolicy,
    error_from_failure,
)


def provider_info(
    provider_id: str,
    *,
    media_types: tuple[MediaType, ...] = (MediaType.VIDEO,),
    pagination: PaginationMode = PaginationMode.NONE,
) -> ProviderInfo:
    capabilities = [ProviderCapability.SEARCH, ProviderCapability.HEALTH_CHECK]
    if pagination != PaginationMode.NONE:
        capabilities.append(ProviderCapability.PAGINATION)
    return ProviderInfo(
        provider_id=provider_id,
        display_name=provider_id.title(),
        media_types=media_types,
        access_mode=AccessMode.OFFICIAL_API,
        capabilities=tuple(capabilities),
        pagination_mode=pagination,
        auth_mode="api_key",
    )


def intent(media_type: MediaType = MediaType.VIDEO) -> RetrievalIntent:
    return RetrievalIntent(
        need_id="need-1",
        semantic_queries=("person walking in a city", "walking street"),
        filters={"media_type": media_type.value},
    )


def candidate(candidate_id: str, need_id: str = "need-1") -> SupplyCandidate:
    return SupplyCandidate(
        candidate_id=candidate_id,
        need_id=need_id,
        media_type=MediaType.VIDEO,
        source=CandidateSource(kind="stock", provider="fixture"),
        availability=Availability.DISCOVERED,
    )


class FakeProvider:
    def __init__(self, info: ProviderInfo, response=None, errors=()):
        self._info = info
        self.response = response or ProviderPage()
        self.errors = list(errors)
        self.calls = []

    def info(self) -> ProviderInfo:
        return self._info

    def search(self, retrieval_intent, continuation=None) -> ProviderPage:
        self.calls.append((retrieval_intent, continuation))
        if self.errors:
            raise self.errors.pop(0)
        return self.response

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self._info.provider_id,
            status=ProviderHealthStatus.HEALTHY,
            last_success_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
        )


def test_registry_registers_and_queries_fake_provider() -> None:
    provider = FakeProvider(provider_info("fixture"), ProviderPage(candidates=(candidate("c1"),)))
    registry = ProviderRegistry()
    registered = registry.register(provider)

    assert registered.provider_id == "fixture"
    assert registry.available_for(MediaType.VIDEO, ProviderCapability.SEARCH) == (registered,)
    assert registry.health("fixture").status is ProviderHealthStatus.HEALTHY
    results = registry.search_all(intent())
    assert results[0].page.candidates[0].candidate_id == "c1"
    assert len(provider.calls) == 1


def test_provider_failure_is_isolated_and_does_not_hide_success() -> None:
    failed = FakeProvider(
        provider_info("failed"),
        errors=(ProviderNetworkError("failed", "connection timed out", retryable=False),),
    )
    good = FakeProvider(provider_info("good"), ProviderPage(candidates=(candidate("c2"),)))
    registry = ProviderRegistry()
    registry.register(failed)
    registry.register(good)

    results = registry.search_all(intent(), retry_policy=RetryPolicy(max_attempts=1))

    assert results[0].failure.category is ProviderErrorCategory.NETWORK
    assert results[1].page.candidates[0].candidate_id == "c2"


def test_capability_gate_skips_unsupported_provider_before_invocation() -> None:
    image_only = FakeProvider(provider_info("image-only", media_types=(MediaType.IMAGE,)))
    registry = ProviderRegistry()
    registry.register(image_only)

    result = registry.search_all(intent(MediaType.VIDEO))[0]

    assert result.failure.category is ProviderErrorCategory.UNSUPPORTED
    assert image_only.calls == []


def test_provider_continuation_is_provider_owned_and_round_trips() -> None:
    continuation = ProviderContinuation(
        provider_id="fixture",
        mode=PaginationMode.CURSOR,
        token="opaque-next-cursor",
    )
    assert ProviderContinuation.from_json(continuation.to_json()) == continuation
    provider = FakeProvider(
        provider_info("fixture", pagination=PaginationMode.CURSOR),
        ProviderPage(continuation=continuation),
    )
    registry = ProviderRegistry()
    registry.register(provider)
    result = registry.search_all(intent(), continuations={"fixture": continuation})[0]

    assert result.page.continuation == continuation
    assert provider.calls[0][1] == continuation


def test_mismatched_continuation_is_rejected_before_provider_invocation() -> None:
    provider = FakeProvider(provider_info("fixture", pagination=PaginationMode.CURSOR))
    registry = ProviderRegistry()
    registry.register(provider)
    foreign = ProviderContinuation(provider_id="other", mode=PaginationMode.CURSOR, token="x")

    result = registry.search_all(intent(), continuations={"fixture": foreign})[0]

    assert result.failure.category is ProviderErrorCategory.UNSUPPORTED
    assert provider.calls == []


def test_retry_is_bounded_and_provider_local() -> None:
    provider = FakeProvider(
        provider_info("fixture"),
        ProviderPage(candidates=(candidate("after-retry"),)),
        errors=(ProviderTemporaryError("fixture", "temporary"),),
    )
    registry = ProviderRegistry()
    registry.register(provider)
    delays: list[float] = []

    results = registry.search_all(
        intent(),
        retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.1, max_delay_seconds=1),
        sleep=delays.append,
    )

    assert results[0].page.candidates[0].candidate_id == "after-retry"
    assert len(provider.calls) == 2
    assert delays == [0.1]


def test_typed_error_failure_round_trip_preserves_retry_boundary() -> None:
    error = ProviderRateLimitError(
        "fixture",
        "rate limit reached",
        retry_after_seconds=3,
    )
    failure = ProviderFailure.from_json(error.to_failure().to_json())
    restored = error_from_failure(failure)

    assert isinstance(restored, ProviderRateLimitError)
    assert restored.provider_id == "fixture"
    assert restored.retryable is True
    assert restored.retry_after_seconds == 3


def test_invalid_provider_page_is_isolated_as_typed_failure() -> None:
    provider = FakeProvider(
        provider_info("fixture"),
        ProviderPage(candidates=(candidate("wrong-need", need_id="other-need"),)),
    )
    registry = ProviderRegistry()
    registry.register(provider)

    result = registry.search_all(intent())[0]

    assert result.failure.category is ProviderErrorCategory.INVALID_RESPONSE


def test_provider_cannot_return_a_media_type_outside_its_declared_capability() -> None:
    image_candidate = SupplyCandidate(
        candidate_id="image-candidate",
        need_id="need-1",
        media_type=MediaType.IMAGE,
        source=CandidateSource(kind="stock", provider="fixture"),
        availability=Availability.DISCOVERED,
    )
    provider = FakeProvider(provider_info("fixture"), ProviderPage(candidates=(image_candidate,)))
    registry = ProviderRegistry()
    registry.register(provider)

    result = registry.search_all(intent())[0]

    assert result.failure.category is ProviderErrorCategory.INVALID_RESPONSE
