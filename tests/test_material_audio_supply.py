from __future__ import annotations


def acoustic_fixture(audio_sha256, duration, *, vocal_score=0.001, music_score=0.95):
    """Fixed classifier boundary, never a claimed listening result."""
    from easel.materials.application import music_observation as music
    starts = sorted(set(range(0, max(1, int(duration - 10) + 1), 5)) | {max(0, duration - 10)})
    return {'schema': music.SCHEMA, 'model': music.MODEL_ID, 'model_revision': music.MODEL_REVISION,
        'model_sha256': music.MODEL_FILES['model.safetensors'], 'audio_sha256': audio_sha256,
        'duration_seconds': duration, 'windows': [
            {'start_seconds': start, 'end_seconds': min(duration, start + 10), 'rms': .1,
             'scores': {**{label: vocal_score for label in music.VOCAL_LABELS},
                        'Music': music_score, 'Piano': .75, 'Ambient music': .4}} for start in starts]}

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


def test_bgm_matching_reuses_material_matcher_without_timeline_decisions(monkeypatch):
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
    assert first_query == 'music'
    assert all(term in intent.semantic_queries[1] for term in
               ('calm', 'ambient', 'piano', 'pad', 'low', '60-80 bpm', 'instrumental'))
    assert len(intent.semantic_queries) <= 4
    assert 'vocals' in intent.negative_terms
    allowed = compiler.compile(need.model_copy(update={'modality_spec': BgmNeedSpec(vocals_allowed=True)}))
    assert 'instrumental' not in ' '.join(allowed.semantic_queries)
    assert 'vocals' not in allowed.negative_terms

    def candidate(asset_id, **attributes):
        return _licensed_asset().model_copy(update={'asset_id': asset_id,
            'semantic': SemanticInfo(caption='background music', attributes=attributes)})
    calm = candidate('z-calm', mood='calm', genre='ambient', instruments=['piano', 'pad'], energy='low', tempo_bpm=70)
    # Misleading Provider metadata claims piano/ambient for actual guitar/rock.
    loud = candidate('a-loud', mood='calm', genre='ambient', instruments=['piano', 'pad'], energy='low', tempo_bpm=70)
    unknown = candidate('b-unknown')
    from easel.materials.application.music_observation import apply_music_observation
    assert not BgmMaterialSupply().match(need, [calm]).matches  # A title cannot prove no vocals.
    report = acoustic_fixture(calm.file.sha256, 30)
    from copy import deepcopy
    rock_report = deepcopy(report)
    for row in rock_report['windows']:
        row['scores'].update({'Piano': 0., 'Ambient music': 0., 'Electric guitar': .7, 'Rock music': .8})
    calm, loud, unknown = (apply_music_observation(need, a, r) for a, r in
                          ((calm, report), (loud, rock_report), (unknown, report)))
    assert apply_music_observation(need, calm, report) == calm  # Replay does not create new timestamps.
    ranked = BgmMaterialSupply().match(need, [loud, unknown, calm]).matches
    assert ranked[0].asset_id == calm.asset_id
    assert 0 < ranked[0].scores.director < 1  # No acoustic pad evidence; missing preferences stay soft.
    assert any(reason.startswith('bgm_preference_acoustic_and_metadata_overlap=') for reason in ranked[0].reasons)
    assert len(ranked) == 3  # Missing/contrary soft preferences are not new gates.
    assert all('system_music=acoustically_observed' in match.reasons for match in ranked)
    different = need.model_copy(update={'modality_spec': BgmNeedSpec(mood='exciting', genre='rock',
        instruments=('guitar',), energy='high', tempo_bpm=(140, 160), vocals_allowed=True)})
    assert not BgmMaterialSupply().match(different, [calm, loud]).matches  # Every Need keeps its own evidence.
    rebound = [apply_music_observation(different, a, r) for a, r in ((calm, report), (loud, rock_report))]
    assert BgmMaterialSupply().match(different, rebound).matches[0].asset_id == loud.asset_id
    for vocal, music in ((.9, .95), (.05, .95), (.001, .1)):
        unfit = apply_music_observation(need, calm, acoustic_fixture(calm.file.sha256, 30,
            vocal_score=vocal, music_score=music))
        assert not BgmMaterialSupply().match(need, [unfit]).matches
        assert unfit.rights == calm.rights and unfit.file == calm.file
    # The practical policy permits modest music evidence and a small vocal
    # classifier response; detected speech and clearly nonmusic still veto.
    practical = apply_music_observation(need, calm, acoustic_fixture(calm.file.sha256, 30,
        music_score=.55, vocal_score=.015))
    assert BgmMaterialSupply().match(need, [practical]).matches
    long_asset = calm.model_copy(update={'technical': calm.technical.model_copy(update={'duration_seconds': 100})})
    long_report = acoustic_fixture(calm.file.sha256, 100)
    # A manually bounded transition protects time integration, not a claim
    # that the actual ten-second AST observer localizes five-second events.
    template = deepcopy(long_report['windows'][0])
    for gap, score, rms, vocal, accepted in ((5, .4, .1, .001, True), (7, .4, .1, .001, False),
            (5, .19, .1, .001, False), (5, .4, 0., .001, False), (5, .4, .1, .9, False)):
        transition = deepcopy(long_report)
        transition['windows'] = []
        for start in range(0, 90, 10):
            row = deepcopy(template)
            row.update(start_seconds=start, end_seconds=start + 10)
            transition['windows'].append(row)
        for start, stop, uncertain in ((90, 100-gap, False), (100-gap, 100, True)):
            row = deepcopy(template)
            row.update(start_seconds=start, end_seconds=stop)
            if uncertain:
                row['rms'] = rms
                row['scores'].update(Music=score, Speech=vocal)
            transition['windows'].append(row)
        assessed = apply_music_observation(need, long_asset, transition)
        assert bool(BgmMaterialSupply().match(need, [assessed]).matches) is accepted
    overlapping = deepcopy(long_report)
    overlapping['windows'][0]['scores']['Music'] = .4
    assert not BgmMaterialSupply().match(need, [apply_music_observation(need, long_asset, overlapping)]).matches
    import pytest
    from copy import deepcopy
    missing_tail = deepcopy(report)
    missing_tail['windows'].pop()
    with pytest.raises(ValueError, match='尾部'):
        apply_music_observation(need, calm, missing_tail)
    with pytest.raises(ValueError, match='身份'):
        apply_music_observation(need, calm, {**report, 'audio_sha256': '0' * 64})
    # Malformed persisted evidence must fail before deriving a usable inference.
    for invalid_duration in (float('nan'), float('inf'), -float('inf'), True, None, 10**400):
        with pytest.raises(ValueError, match='身份'):
            apply_music_observation(need, calm, {**report, 'duration_seconds': invalid_duration})
    with pytest.raises(ValueError, match='窗口'):
        apply_music_observation(need, calm, {**report, 'windows': [None]})
    # The model's vocal subcategories are hard evidence, not soft preferences.
    # Singing bowl remains an instrument and must not veto instrumental music.
    for label in ('Choir', 'A capella', 'Yodeling', 'Mantra'):
        vocal_report = deepcopy(report)
        vocal_report['windows'][0]['scores'][label] = .99
        unfit = apply_music_observation(need, calm, vocal_report)
        assert not BgmMaterialSupply().match(need, [unfit]).matches
        missing_label = deepcopy(report)
        del missing_label['windows'][0]['scores'][label]
        with pytest.raises(ValueError, match='分类分数'):
            apply_music_observation(need, calm, missing_label)
    bowl_report = deepcopy(report)
    bowl_report['windows'][0]['scores']['Singing bowl'] = .99
    assert BgmMaterialSupply().match(need, [apply_music_observation(need, calm, bowl_report)]).matches
    # A persisted legacy verdict must not bypass the current policy. Keep it
    # available for audit while deriving the current result from the same raw.
    from easel.materials.application import music_observation as observation
    legacy = calm.semantic.inferences[0].model_copy(update={'analyzer_id': observation.PREFIX + need.need_id,
        'annotations': tuple(a.model_copy(update={'evidence': observation.PREFIX + 'legacy:'})
                             for a in calm.semantic.inferences[0].annotations)})
    old = calm.model_copy(update={'semantic': calm.semantic.model_copy(update={'inferences': (legacy,)})})
    assert not BgmMaterialSupply().match(need, [old]).matches
    migrated = apply_music_observation(need, old, report)
    assert migrated.semantic.inferences[0] == legacy
    assert BgmMaterialSupply().match(need, [migrated]).matches
    assert MaterialAsset.model_validate_json(migrated.to_json()) == migrated
    prior_policy = observation.POLICY_DIGEST
    # Simulate a future policy's unknown conclusion for the exact same raw
    # report: idempotency must not reuse the preceding policy's pass.
    with monkeypatch.context() as patch:
        patch.setattr(observation, 'POLICY_DIGEST', 'f' * 64)
        patch.setattr(observation, 'assess_music', lambda asset, raw: ('unknown', []))
        assert not BgmMaterialSupply().match(need, [migrated]).matches
        upgraded = apply_music_observation(need, migrated, report)
        assert not BgmMaterialSupply().match(need, [upgraded]).matches
        assert len(upgraded.semantic.inferences) == 3
        assert MaterialAsset.model_validate_json(upgraded.to_json()) == upgraded
        assert apply_music_observation(need, upgraded, report) == upgraded
    assert observation.POLICY_DIGEST == prior_policy
    assert BgmMaterialSupply().match(need, [upgraded]).matches  # Explicit rollback uses its own record.
    rejected = apply_music_observation(need, upgraded, acoustic_fixture(calm.file.sha256, 30, vocal_score=.9))
    assert not BgmMaterialSupply().match(need, [rejected]).matches  # Latest same-policy failure supersedes pass.
    assert len(rejected.semantic.inferences) == 3


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
