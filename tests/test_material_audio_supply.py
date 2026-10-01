from __future__ import annotations

import json

from easel.materials.application.audio_supply import BgmMaterialSupply, SfxEventMaterialSupply
from easel.materials.domain import (
    BgmNeedSpec,
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialNeed,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    SemanticInfo,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.providers import OpenverseProvider, ProviderRegistry
from easel.materials.providers.http_support import HttpResponse


class FixtureTransport:
    def __init__(self, result: dict[str, object]):
        self.result = result
        self.url: str | None = None

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> HttpResponse:
        self.url = url
        payload = {"results": [self.result], "page": 1, "page_count": 1}
        return HttpResponse(200, {}, json.dumps(payload).encode())


def _search(transport: FixtureTransport, need: MaterialNeed, supply):
    registry = ProviderRegistry()
    registry.register(OpenverseProvider(transport=transport))
    return supply.discover(need, registry)


def _audio_need(*, role: str, description: str, function: str, scope: NeedScopeType) -> MaterialNeed:
    return MaterialNeed(
        need_id=f"{role}-need",
        scope=NeedScope(type=scope, ref="event-door-close" if scope is NeedScopeType.EVENT else "creation"),
        media_type=MediaType.AUDIO,
        role=role,
        intent=NeedIntent(description=description, function=function),
        importance=NeedImportance.REQUIRED,
    )


def _openverse_result(*, title: str, item_id: str, license_id: str, attribution: str, tags: tuple[str, ...]):
    license_url = (
        "https://creativecommons.org/publicdomain/zero/1.0/"
        if license_id == "cc0"
        else "https://creativecommons.org/licenses/by/4.0/"
    )
    return {
        "id": item_id,
        "title": title,
        "foreign_landing_url": f"https://source.test/{item_id}",
        "url": f"https://media.test/{item_id}.wav",
        "creator": "Fixture Creator",
        "license": license_id,
        "license_version": "4.0",
        "license_url": license_url,
        "attribution": attribution,
        "filetype": "audio/wav",
        "filesize": 1000,
        "duration": 30,
        "tags": [{"name": tag} for tag in tags],
    }


def _licensed_asset() -> MaterialAsset:
    return MaterialAsset(
        asset_id="music-local",
        media_type=MediaType.AUDIO,
        file=FileInfo(path="materials/assets/music-local/music.wav", sha256="b" * 64, size=1000, mime="audio/wav"),
        source=CandidateSource(
            kind="fixture", provider="openverse", source_page="https://source.test/music-1", creator="Composer",
        ),
        rights=RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="CC BY 4.0",
            evidence=(RightsEvidence(kind="asset_license", reference="https://creativecommons.org/licenses/by/4.0/"),),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=30, mime="audio/wav"),
        semantic=SemanticInfo(caption="calm piano background music"),
    )


def _sfx_asset() -> MaterialAsset:
    return MaterialAsset(
        asset_id="door-sfx",
        media_type=MediaType.AUDIO,
        file=FileInfo(path="materials/assets/door-sfx/sfx.wav", sha256="c" * 64, size=512, mime="audio/wav"),
        source=CandidateSource(kind="fixture", provider="openverse", source_page="https://source.test/sfx-1"),
        rights=RightsInfo(
            status=RightsStatus.PUBLIC_DOMAIN,
            evidence=(RightsEvidence(kind="asset_license", reference="https://creativecommons.org/publicdomain/zero/1.0/"),),
        ),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=1.2, mime="audio/wav"),
        semantic=SemanticInfo(caption="wooden door closes with latch click", tags=("door", "close")),
    )


def test_bgm_search_uses_openverse_audio_and_preserves_item_rights():
    transport = FixtureTransport(_openverse_result(
        title="Soft piano background", item_id="music-1", license_id="by",
        attribution="Composer, CC BY", tags=("piano", "calm"),
    ))
    result = _search(
        transport,
        _audio_need(
            role="bgm", description="calm piano under narration", function="background music",
            scope=NeedScopeType.GLOBAL,
        ),
        BgmMaterialSupply(),
    )
    candidate = result.providers[0].page.candidates[0]

    assert result.intent.filters["media_type"] == "audio"
    assert candidate.source.provider == "openverse"
    assert candidate.rights_hint.status is RightsStatus.ATTRIBUTION_REQUIRED
    assert candidate.metadata["license_id"] == "by"
    assert not hasattr(result, "track") and not hasattr(result, "placement")


def test_bgm_matching_reuses_material_matcher_without_timeline_decisions():
    need = _audio_need(
        role="bgm", description="calm piano under narration", function="background music",
        scope=NeedScopeType.GLOBAL,
    )
    result = BgmMaterialSupply().match(need, [_licensed_asset()])

    assert result.matches[0].asset_id == "music-local"
    assert result.matches[0].qualified

    # Director decisions live in the typed Need, not necessarily in its short
    # description. Source metadata is a ranking hint, never a listening result.
    from easel.materials.application.compiler import NeedCompiler
    need = need.model_copy(update={'intent': NeedIntent(description='background music'),
        'modality_spec': BgmNeedSpec(mood='calm', genre='ambient',
            instruments=('piano', 'pad'), energy='low', tempo_bpm=(60, 80))})
    compiler = NeedCompiler(search_terms={need.need_id: ('music', 'background', 'soundtrack', 'score')})
    transport = FixtureTransport(_openverse_result(title='Music', item_id='music-2',
        license_id='cc0', attribution='', tags=('piano',)))
    intent = _search(transport, need, BgmMaterialSupply(compiler=compiler)).intent
    from urllib.parse import parse_qs, urlparse
    assert parse_qs(urlparse(transport.url).query)['q'] == [intent.semantic_queries[0]]
    first_query = intent.semantic_queries[0]
    assert all(term in first_query for term in ('calm', 'ambient', 'piano', 'pad', 'low', '60-80 bpm', 'instrumental'))
    assert len(intent.semantic_queries) <= 4
    assert 'vocals' in intent.negative_terms
    allowed = compiler.compile(need.model_copy(update={'modality_spec': BgmNeedSpec(vocals_allowed=True)}))
    assert 'instrumental' not in ' '.join(allowed.semantic_queries)
    assert 'vocals' not in allowed.negative_terms

    def candidate(asset_id, **attributes):
        return _licensed_asset().model_copy(update={'asset_id': asset_id,
            'semantic': SemanticInfo(caption='background music', attributes=attributes)})
    calm = candidate('z-calm', mood='calm', genre='ambient', instruments=['piano', 'pad'], energy='low', tempo_bpm=70)
    loud = candidate('a-loud', mood='exciting', genre='rock', instruments=['guitar'], energy='high', tempo_bpm=150)
    unknown = candidate('b-unknown')
    ranked = BgmMaterialSupply().match(need, [loud, unknown, calm]).matches
    assert ranked[0].asset_id == calm.asset_id
    assert ranked[0].scores.director == 1
    assert any(reason.startswith('bgm_preference_metadata_overlap=') for reason in ranked[0].reasons)
    assert len(ranked) == 3  # Missing/contrary soft preferences are not new gates.
    assert not any('observed' in reason or 'vocals=absent' in reason for match in ranked for reason in match.reasons)
    different = need.model_copy(update={'modality_spec': BgmNeedSpec(mood='exciting', genre='rock',
        instruments=('guitar',), energy='high', tempo_bpm=(140, 160), vocals_allowed=True)})
    assert BgmMaterialSupply().match(different, [calm, loud]).matches[0].asset_id == loud.asset_id


def test_sfx_discovery_compiles_event_semantics_and_retains_license_facts():
    transport = FixtureTransport(_openverse_result(
        title="Door closes", item_id="sfx-1", license_id="cc0", attribution="",
        tags=("door", "close"),
    ))
    need = _audio_need(
        role="sfx_event", description="wooden door closes with a short latch click",
        function="door close event", scope=NeedScopeType.EVENT,
    )
    result = _search(transport, need, SfxEventMaterialSupply())
    candidate = result.providers[0].page.candidates[0]

    assert "wooden door closes with a short latch click" in result.intent.semantic_queries
    assert candidate.rights_hint.status is RightsStatus.PUBLIC_DOMAIN
    assert "door" in candidate.metadata["tags"]
    assert transport.url is not None
    assert not hasattr(result, "timestamp") and not hasattr(result, "audio_track")


def test_sfx_matching_returns_evidence_rank_without_event_placement():
    need = _audio_need(
        role="sfx_event", description="wooden door closes with a short latch click",
        function="door close event", scope=NeedScopeType.EVENT,
    )
    result = SfxEventMaterialSupply().match(need, [_sfx_asset()])

    assert result.matches[0].asset_id == "door-sfx"
    assert result.matches[0].rank == 1
    assert "hard_filter=passed" in result.matches[0].reasons
