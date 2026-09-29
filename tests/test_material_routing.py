from __future__ import annotations

from datetime import datetime, timezone

from easel.materials.application.routing import (
    MaterialSourceRouter,
    ProviderPerformance,
    ProviderRoutingPolicy,
    SourceKind,
)
from easel.materials.domain import (
    Availability,
    CandidateSource,
    ContinuityRef,
    MaterialNeed,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RetrievalIntent,
    RightsStatus,
    SupplyCandidate,
)
from easel.materials.domain.models import PreviewInfo, RightsHint
from easel.materials.providers import (
    AccessMode,
    PaginationMode,
    ProviderCapability,
    ProviderContinuation,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderInfo,
    ProviderPage,
    ProviderRegistry,
    ProviderTemporaryError,
    RetryPolicy,
)


class FakeProvider:
    def __init__(self, provider_id: str, *, fail: bool = False):
        self.provider_id = provider_id
        self.fail = fail
        self.calls = 0

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.provider_id,
            media_types=(MediaType.VIDEO,),
            access_mode=AccessMode.OFFICIAL_API,
            capabilities=(ProviderCapability.SEARCH,),
        )

    def search(self, intent, continuation: ProviderContinuation | None = None) -> ProviderPage:
        self.calls += 1
        if self.fail:
            raise ProviderTemporaryError(self.provider_id, "fixture down")
        return ProviderPage(candidates=(SupplyCandidate(
            candidate_id=f"{self.provider_id}:candidate",
            need_id=intent.need_id,
            media_type=MediaType.VIDEO,
            source=CandidateSource(kind="fixture", provider=self.provider_id, provider_asset_id="fixture-1"),
            preview=PreviewInfo(url="https://fixture.example/preview.jpg"),
            availability=Availability.PREVIEWABLE,
            rights_hint=RightsHint(status=RightsStatus.UNKNOWN),
        ),))

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider_id=self.provider_id, status=ProviderHealthStatus.HEALTHY)


def _intent() -> RetrievalIntent:
    return RetrievalIntent(need_id="need-route", semantic_queries=("city night",), filters={"media_type": "video"})


def _material_need(*, allow_generation: bool = False, continuity: tuple[ContinuityRef, ...] = ()) -> MaterialNeed:
    return MaterialNeed(
        need_id="need-route", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.VIDEO, role="supporting_visual",
        intent=NeedIntent(description="a quiet city street"),
        importance=NeedImportance.REQUIRED,
        constraints={"allow_generation": allow_generation}, continuity_refs=continuity,
    )


def test_router_prefers_library_then_local_then_reliable_external_deterministically() -> None:
    local = ProviderInfo(
        provider_id="local", display_name="Local", media_types=(MediaType.VIDEO,),
        access_mode=AccessMode.LOCAL, capabilities=(ProviderCapability.SEARCH,),
    )
    external_a = FakeProvider("external-a").info()
    external_b = FakeProvider("external-b").info()
    healthy = {provider_id: ProviderHealth(provider_id=provider_id, status=ProviderHealthStatus.HEALTHY)
               for provider_id in ("local", "external-a", "external-b")}
    history = {
        "external-a": ProviderPerformance(provider_id="external-a", success_count=8, failure_count=2, average_latency_ms=500),
        "external-b": ProviderPerformance(provider_id="external-b", success_count=9, failure_count=1, average_latency_ms=1200),
    }
    router = MaterialSourceRouter()
    decision = router.plan(
        MediaType.VIDEO, (external_a, external_b, local), library_candidate_count=2,
        provider_health=healthy, performance=history,
    )
    assert [(r.source_id, r.kind, r.order) for r in decision.routes] == [
        ("material-library", SourceKind.LIBRARY, 1),
        ("local", SourceKind.LOCAL, 2),
        ("external-b", SourceKind.EXTERNAL, 3),
        ("external-a", SourceKind.EXTERNAL, 4),
    ]
    assert "historical_behavior=success:9,failure:1,success_rate:0.900" in decision.routes[2].reasons
    assert "Rights Admission" in decision.rights_policy


def test_router_skips_disabled_unavailable_and_incapable_sources_and_enforces_external_ceiling() -> None:
    infos = (
        FakeProvider("disabled").info(),
        FakeProvider("unavailable").info(),
        ProviderInfo(provider_id="image-only", display_name="Image", media_types=(MediaType.IMAGE,), access_mode=AccessMode.PUBLIC_API, capabilities=(ProviderCapability.SEARCH,)),
        FakeProvider("external-a").info(),
        FakeProvider("external-b").info(),
    )
    health = {"unavailable": ProviderHealth(provider_id="unavailable", status=ProviderHealthStatus.UNAVAILABLE)}
    decision = MaterialSourceRouter().plan(
        MediaType.VIDEO,
        infos,
        provider_health=health,
        policy=ProviderRoutingPolicy(
            disabled_provider_ids=("disabled",), max_external_providers=1,
        ),
    )
    assert [route.source_id for route in decision.routes] == ["external-a"]
    assert {skip.reason for skip in decision.skipped} == {
        "disabled_by_policy", "provider_unavailable", "required_capability_or_media_type_unsupported", "external_provider_limit_reached",
    }


def test_generation_is_need_gated_and_follows_existing_sources() -> None:
    provider = ProviderInfo(
        provider_id="stock", display_name="Stock", media_types=(MediaType.VIDEO,),
        access_mode=AccessMode.PUBLIC_API,
        capabilities=(ProviderCapability.SEARCH, ProviderCapability.DIRECT_DOWNLOAD),
    )
    decision = MaterialSourceRouter().plan(
        MediaType.VIDEO, (provider,), need=_material_need(allow_generation=True),
        required_capability=ProviderCapability.DIRECT_DOWNLOAD,
    )
    assert [(route.source_id, route.kind) for route in decision.routes] == [
        ("stock", SourceKind.EXTERNAL), ("material-ai-generation", SourceKind.GENERATIVE),
    ]
    assert "material provider" in " ".join(decision.routes[-1].reasons)


def test_generation_requires_source_policy_or_matching_continuity_and_supported_modality() -> None:
    router = MaterialSourceRouter()
    without_policy = router.plan(MediaType.VIDEO, (), need=_material_need())
    with_identity = router.plan(
        MediaType.VIDEO, (),
        need=_material_need(continuity=(ContinuityRef(kind="character", ref="creator-avatar"),)),
    )
    unsupported_audio = router.plan(
        MediaType.AUDIO, (),
        need=MaterialNeed(
            need_id="bgm", scope=NeedScope(type=NeedScopeType.GLOBAL, ref="creation"),
            media_type=MediaType.AUDIO, role="bgm", intent=NeedIntent(description="calm music"),
            importance=NeedImportance.REQUIRED, constraints={"allow_generation": True},
        ),
    )
    assert without_policy.routes == ()
    assert [route.kind for route in with_identity.routes] == [SourceKind.GENERATIVE]
    assert unsupported_audio.routes == ()


def test_routed_search_isolates_each_provider_failure_without_rights_promotion() -> None:
    bad = FakeProvider("external-bad", fail=True)
    good = FakeProvider("external-good")
    registry = ProviderRegistry()
    registry.register(bad)
    registry.register(good)
    router = MaterialSourceRouter()
    decision = router.plan(
        MediaType.VIDEO,
        registry.infos(),
        performance={
            "external-bad": ProviderPerformance(provider_id="external-bad", success_count=0, failure_count=3),
            "external-good": ProviderPerformance(provider_id="external-good", success_count=4, failure_count=0),
        },
    )
    result = router.search_routed(
        registry,
        _intent(),
        decision,
        retry_policy=RetryPolicy(max_attempts=1),
        sleep=lambda _: None,
    )
    by_id = {item.provider_id: item for item in result.provider_results}
    assert by_id["external-bad"].failure is not None
    assert by_id["external-good"].page is not None
    assert good.calls == 1
    assert bad.calls == 1
    assert by_id["external-good"].page.candidates[0].rights_hint.status is RightsStatus.UNKNOWN
