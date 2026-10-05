from __future__ import annotations

from pathlib import Path

from PIL import Image

from easel.materials.application.intelligence import BasicMaterialIntelligence
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    IntelligenceStatus,
    MaterialAsset,
    MediaType,
    RightsInfo,
    RightsStatus,
    SemanticAnnotation,
    SemanticField,
    SemanticInfo,
    TechnicalInfo,
    TechnicalStatus,
)
from easel.materials.store import AttemptMaterialStore


def _asset(store: AttemptMaterialStore, name: str = "asset-1") -> MaterialAsset:
    path = store.attempt_root / "input.png"
    Image.new("RGB", (12, 8), "navy").save(path)
    data = path.read_bytes()
    locator = store.write_asset_bytes(name, "original.png", data)
    asset = MaterialAsset(
        asset_id=name,
        media_type=MediaType.IMAGE,
        file=FileInfo(path=locator, sha256=__import__("hashlib").sha256(data).hexdigest(), size=len(data), mime="image/png"),
        source=CandidateSource(kind="stock", provider="fixture", provider_asset_id="native-1", source_page="https://example.test/item", creator="Creator"),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=12, height=8, facts={"provider_codec_hint": "still-image"}),
        semantic=SemanticInfo(caption="Provider supplied alt", tags=("provider-tag",), attributes={"origin": "provider"}),
    )
    store.write_asset(asset)
    return asset


def test_related_subject_with_hard_conflict_is_durable_negative_evidence(tmp_path):
    import pytest
    from easel.materials.application.visual_observation import (
        SCHEMA, apply_observation, observed_match, prepare_observation, read_observation_report, requires_reassessment,
    )
    from easel.materials.domain import MaterialNeed, NeedScope, NeedScopeType, NeedIntent, NeedImportance
    store = AttemptMaterialStore(tmp_path)
    asset = _asset(store)
    need = MaterialNeed(need_id='desk', scope=NeedScope(type=NeedScopeType.SCENE, ref='s'),
        media_type=MediaType.IMAGE, role='primary', intent=NeedIntent(description='desk without logo'),
        importance=NeedImportance.REQUIRED, constraints={'logo': False, 'preferred_style': 'warm'})
    manifest, _ = prepare_observation(need, asset, store.resolve_asset_locator(asset.file.path))
    report = {'schema': SCHEMA, 'input_sha256': manifest['input_sha256'], 'verdict': 'unsuitable',
        'caption': 'desk with logo', 'style': 'cold', 'reason': 'logo violates explicit prohibition',
        'failure_kind': 'hard_constraint', 'logo_present': True,
        'frames': [{'index': 0, 'observed': True, 'related': True, 'meets_requirements': False,
                    'description': 'visible desk and logo'}]}
    store.write_observation_record(manifest['input_sha256'], report)
    path = store.materials_root / 'observations' / (manifest['input_sha256'] + '.json')
    assert read_observation_report(path, need, asset, manifest) == report
    assert observed_match(need, apply_observation(need, asset, manifest, report)) is False
    assert not requires_reassessment(need, report, asset.media_type)
    assert requires_reassessment(need, {**report, 'failure_kind': 'preference_only', 'reason': '仅色调不符'}, asset.media_type)
    from easel.materials.application.visual_observation import ASSESSMENT_REVISION
    assert not requires_reassessment(need, {**report, 'failure_kind': 'none',
        'assessment_revision': ASSESSMENT_REVISION}, asset.media_type)
    with pytest.raises(ValueError, match='逐帧证据矛盾'):
        apply_observation(need, asset, manifest, {**report, 'frames': [{**report['frames'][0], 'meets_requirements': None}]})
    with pytest.raises(ValueError, match='一般偏好'):
        apply_observation(need, asset, manifest, {**report, 'failure_kind': 'preference_only'})


class _FakeAnalyzer:
    analyzer_id = "fixture-florence"

    def __init__(self, *, fail_for: set[str] | None = None):
        self.fail_for = fail_for or set()
        self.calls: list[str] = []

    def analyze(self, path: Path, media_type: MediaType) -> dict[str, object]:
        self.calls.append(path.name)
        if path.parent.name in self.fail_for:
            raise RuntimeError("provider credential=must-not-leak")
        return {
            "partial": True,
            "annotations": [
                {"field": "caption", "value": "A person working at a desk", "confidence": 0.91},
                {"field": "objects", "value": ["person", "desk", "computer"], "confidence": 0.88},
                {"field": "environment", "value": "office", "confidence": 0.84},
                {"field": "action", "value": "working", "confidence": 0.81},
                {"field": "shot_type", "value": "medium shot", "confidence": 0.67},
                {"field": "visible_text", "value": ["EASEL"], "confidence": 0.92, "evidence": "OCR: EASEL"},
                {"field": "logo", "value": False, "confidence": 0.76, "evidence": "no logo detected"},
            ],
        }


def test_disabled_intelligence_is_explicit_and_does_not_touch_asset_facts(tmp_path: Path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = _asset(store)
    result = BasicMaterialIntelligence(store).enrich(asset)

    assert result.semantic.intelligence_status is IntelligenceStatus.DISABLED
    assert result.semantic.intelligence_error == "analyzer_disabled"
    assert result.technical == asset.technical
    assert result.rights == asset.rights
    assert result.source == asset.source
    assert result.semantic.caption == "Provider supplied alt"
    assert result.semantic.tags == ("provider-tag",)
    assert result.semantic.attributes == {"origin": "provider"}
    assert store.read_asset(asset.asset_id).semantic.intelligence_status is IntelligenceStatus.DISABLED


def test_fake_analyzer_writes_typed_semantic_inferences_without_replacing_facts(tmp_path: Path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = _asset(store)
    analyzer = _FakeAnalyzer()
    intelligence = BasicMaterialIntelligence(store, analyzer, enabled=True)

    result = intelligence.enrich(asset)
    inference = result.semantic.inferences[0]
    by_field = {item.field: item for item in inference.annotations}

    assert result.semantic.intelligence_status is IntelligenceStatus.PARTIAL
    assert by_field[SemanticField.CAPTION].value == "A person working at a desk"
    assert by_field[SemanticField.VISIBLE_TEXT].evidence == "OCR: EASEL"
    assert by_field[SemanticField.LOGO].value is False
    assert all(item.confidence is None or 0 <= item.confidence <= 1 for item in inference.annotations)
    assert result.technical == asset.technical
    assert result.rights == asset.rights
    assert result.source == asset.source
    assert store.read_asset(asset.asset_id).semantic.inferences == result.semantic.inferences
    assert analyzer.calls == ["original.png"]


def test_failed_analyzer_keeps_asset_usable_and_does_not_abort_other_assets(tmp_path: Path) -> None:
    store = AttemptMaterialStore(tmp_path)
    failed_asset = _asset(store, "asset-fail")
    successful_asset = _asset(store, "asset-ok")
    analyzer = _FakeAnalyzer(fail_for={"asset-fail"})
    intelligence = BasicMaterialIntelligence(store, analyzer, enabled=True)

    failed, successful = intelligence.enrich_many([failed_asset, successful_asset])

    assert failed.semantic.intelligence_status is IntelligenceStatus.FAILED
    assert failed.semantic.intelligence_error == "analyzer_failed"
    assert failed.technical == failed_asset.technical
    assert failed.rights == failed_asset.rights
    assert failed.source == failed_asset.source
    assert successful.semantic.intelligence_status is IntelligenceStatus.PARTIAL
    assert len(successful.semantic.inferences) == 1
    assert len(analyzer.calls) == 2


def test_invalid_analyzer_payload_is_partial_failure_not_an_asset_failure(tmp_path: Path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = _asset(store)

    class InvalidAnalyzer:
        analyzer_id = "invalid-fixture"

        def analyze(self, path: Path, media_type: MediaType) -> dict[str, object]:
            return {"annotations": [{"field": "caption", "value": "caption", "confidence": 1.1}]}

    result = BasicMaterialIntelligence(store, InvalidAnalyzer(), enabled=True).enrich(asset)

    assert result.semantic.intelligence_status is IntelligenceStatus.FAILED
    assert result.semantic.intelligence_error == "analyzer_output_invalid"
    assert result.technical.status is TechnicalStatus.PASSED
    assert result.rights.status is RightsStatus.UNKNOWN


def test_audio_asset_is_explicitly_skipped_by_visual_intelligence(tmp_path: Path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset = _asset(store)
    audio = asset.model_copy(update={"media_type": MediaType.AUDIO})

    result = BasicMaterialIntelligence(store, _FakeAnalyzer(), enabled=True).enrich(audio, persist=False)

    assert result.semantic.intelligence_status is IntelligenceStatus.DISABLED
    assert result.semantic.intelligence_error == "media_type_not_supported"


def test_video_observation_retains_actual_sample_times_and_does_not_extrapolate(tmp_path, monkeypatch):
    import hashlib
    import subprocess
    import pytest
    from easel.materials.application.matching import MaterialMatcher
    from easel.materials.application.visual_observation import prepare_observation, apply_observation, observed_match, observed_interval, SCHEMA
    from easel.materials.domain import MaterialNeed, NeedScope, NeedScopeType, NeedIntent, NeedImportance

    store = AttemptMaterialStore(tmp_path)
    base = _asset(store)
    video = tmp_path / 'sample.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:r=10:d=1',
                    '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=10:d=1',
                    '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True, timeout=30, capture_output=True)
    data = video.read_bytes()
    asset = base.model_copy(update={'media_type': MediaType.VIDEO,
        'file': FileInfo(path=store.write_asset_bytes(base.asset_id, 'original.mp4', data),
                         sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='video/mp4'),
        'technical': TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=2, width=64, height=64)})
    need = MaterialNeed(need_id='late-subject', scope=NeedScope(type=NeedScopeType.SCENE, ref='s1'),
        media_type=MediaType.VIDEO, role='primary_visual', intent=NeedIntent(description='blue field'),
        importance=NeedImportance.REQUIRED, constraints={'logo': False})
    decode_calls = []
    run = subprocess.run
    def track_decode(*args, **kwargs):
        decode_calls.append(args[0])
        return run(*args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', track_decode)
    preview_cache = {}
    manifest, attachments = prepare_observation(need, asset, video, preview_cache=preview_cache)
    assert len(decode_calls) == 5
    assert manifest['coverage'] == 'sampled_frames'
    assert len(attachments) == 5
    assert [frame['seek_seconds'] for frame in manifest['frames']] == [0, .475, .95, 1.425, 1.9]
    assert manifest['frames'][0]['sha256'] != manifest['frames'][-1]['sha256']
    report = {'schema': SCHEMA, 'input_sha256': manifest['input_sha256'], 'verdict': 'partial',
              'caption': 'blue appears in the second half', 'style': 'quiet color', 'reason': 'late subject',
              'logo_present': False, 'visible_text_present': False,
              'frames': [{'index': i, 'observed': True, 'related': i >= 3,
                          'description': 'blue' if i >= 3 else 'red'} for i in range(5)]}
    observed = apply_observation(need, asset, manifest, report)
    assert observed_match(need, observed) is True
    assert observed_interval(need, observed) == (1.425, 1.9)  # only the related source span
    assert not MaterialMatcher().match(need, [observed]).matches
    assert all(a.field not in {SemanticField.LOGO, SemanticField.VISIBLE_TEXT}
               for a in observed.semantic.inferences[-1].annotations)  # absence not proven
    with pytest.raises(ValueError, match='部分采样'):
        apply_observation(need, asset, manifest, {**report, 'verdict': 'suitable'})
    with pytest.raises(ValueError, match='逐帧证据矛盾'):
        apply_observation(need, asset, manifest, {**report, 'verdict': 'unsuitable'})
    unknown = {**report, 'verdict': 'uncertain', 'frames': [
        {**row, 'observed': False, 'related': None} for row in report['frames']]}
    assert observed_match(need, apply_observation(need, asset, manifest, unknown)) is False
    with pytest.raises(ValueError, match='关联未知'):
        apply_observation(need, asset, manifest, {**unknown, 'verdict': 'unsuitable'})
    with pytest.raises(ValueError, match='逐张'):
        apply_observation(need, asset, manifest, {**report, 'frames': report['frames'][1:]})
    with pytest.raises(ValueError, match='不一致'):
        apply_observation(need, asset, manifest, {**report, 'input_sha256': '0' * 64})

    # Same source, two independent scene judgments, and actual native uses.
    # Explicit fixture Rights remove that separate blocker; the original logo
    # constraint above remains unknown and cannot be bypassed by an interval.
    from types import SimpleNamespace
    from easel.materials.domain import RightsEvidence
    from easel.integrations.material_layer import ProductionAuthoringIntegration
    from easel.integrations.hypit.revision import assert_observed_video_uses
    from easel.integrations.hypit.errors import HypitIntegrationError
    free_need = need.model_copy(update={'constraints': {}})
    red_need = free_need.model_copy(update={'need_id': 'early-subject', 'intent': NeedIntent(description='red field')})
    evidence = asset.model_copy(update={'rights': RightsInfo(status=RightsStatus.KNOWN, license_name='Fixture license',
        evidence=(RightsEvidence(kind='asset_license', reference='fixture-rights'),))})
    for current_need, related in ((free_need, lambda i: i >= 3), (red_need, lambda i: i <= 2)):
        current_manifest, current_attachments = prepare_observation(current_need, evidence, video, preview_cache=preview_cache)
        assert current_manifest['input_sha256'] != manifest['input_sha256']
        assert current_manifest['frames'] == manifest['frames']
        assert current_attachments == attachments
        current_report = {**report, 'caption': current_need.intent.description,
                          'input_sha256': current_manifest['input_sha256'],
                          'frames': [{**r, 'related': related(r['index'])} for r in report['frames']]}
        evidence = apply_observation(current_need, evidence, current_manifest, current_report)
    matches = tuple(m for n in (free_need, red_need) for m in MaterialMatcher().match(n, [evidence]).matches)
    assert len(matches) == 2
    assert observed_interval(red_need, evidence) == (0, .95)
    longer = free_need.model_copy(update={'constraints': {'min_duration_seconds': .5}})
    longer_manifest, _ = prepare_observation(longer, evidence, video, preview_cache=preview_cache)
    assert len(decode_calls) == 5  # Four Needs reuse pixels, never the matching verdict.
    # Even a warm cache must reject changed source bytes before any reuse.
    video.write_bytes(data + b'changed')
    with pytest.raises(ValueError, match='字节已变化'):
        prepare_observation(longer, evidence, video, preview_cache=preview_cache)
    video.write_bytes(data)
    assert prepare_observation(longer, evidence, video) == (longer_manifest, attachments)
    assert len(decode_calls) == 10  # A new pass reconstructs the same evidence.
    limited = apply_observation(longer, evidence, longer_manifest,
                                {**report, 'input_sha256': longer_manifest['input_sha256']})
    assert not MaterialMatcher().match(longer, [limited]).matches  # .475 s, not the two-second source
    gate = SimpleNamespace(assert_ready=lambda a: (SimpleNamespace(needs=(free_need, red_need)),
                                                   SimpleNamespace(assets=(evidence,), matches=matches), None))
    options = ProductionAuthoringIntegration(gate).qualified_authoring_assets({'workspace': {'path': str(tmp_path)}})
    blue_use, red_use = options[0]['observed_video_uses']
    source = f'''<?svml using="@hypit/markup@1"?>
    <svml>
      <import as="v" from="@hypit/media-track@1"/><import as="p" from="@hypit/media-pipeline@1"/>
      <import as="m" from="@hypit/media@1"/><import as="t" from="@hypit/timeline-author@1"/>
      <import as="f" from="@hypit/film@1"/><import as="r" from="@hypit/render-hyperframes@1"/>
      <import as="space" from="@hypit/spatial@1"/>
      <import as="recipes" source="./recipes.svs"/><t:Clock id="clock" frame-rate="10"/>
      <t:Timeline id="program" clock={{clock}} end="1.3s"/>
      <space:Canvas id="canvas" width="64" height="64"/>
      <space:Frame id="full" within={{canvas}} left="0px" top="0px" right="64px" bottom="64px"/>
      <m:Video id="source" src="{options[0]['src']}"/>
      <p:Normalize id="normalized" source={{source}} clock={{clock}} video="primary-moving" audio="none" span-authority="video"/>
      <v:Track id="pictures" timeline={{program.timeline}} canvas={{canvas}}>
        <v:Item id="{blue_use['element_id_prefix']}1" media={{normalized.media}} frame={{full}} appearance={{recipes.media.blue}} at="0f" for="4f"/>
        <v:Item id="{red_use['element_id_prefix']}1" media={{normalized.media}} frame={{full}} appearance={{recipes.media.red}} at="4f" for="9f"/>
      </v:Track>
      <f:Film id="movie" canvas={{canvas}} timeline={{program.timeline}} appearance={{recipes.film.base}}><f:Track source={{pictures.visual}}/></f:Film>
      <r:Video id="final" composition={{movie.composition}} timeline={{program.timeline}}/>
    </svml>'''
    author = tmp_path / 'productions/easel-authoring/authors/main.svml'
    author.parent.mkdir(parents=True)
    styles = author.with_name('recipes.svs')
    style_header = '<?svml using="@hypit/svs@1"?>\n<sheet version="1">\nfilm.base { background: #000000; }\n'
    author.write_text(source)
    styles.write_text(style_header + 'media.blue { stack-order: 0; trim-start: 15; trim-end: 19; }\nmedia.red { stack-order: 0; trim-start: 0; trim-end: 9; }\n</sheet>')
    assert_observed_video_uses(author, options)
    styles.write_text(style_header + 'media.blue { stack-order: 0; trim-start: 0; trim-end: 19; }\nmedia.red { stack-order: 0; trim-start: 0; trim-end: 9; }\n</sheet>')
    with pytest.raises(HypitIntegrationError, match='越过') as trim_error:
        assert_observed_video_uses(author, options)
    # A real Authoring repair needs the failing use and exact Clock-domain
    # limits, rather than guessing which of several admitted scenes is wrong.
    assert blue_use['need_id'] in str(trim_error.value)
    assert blue_use['element_id_prefix'] + '1' in str(trim_error.value)
    assert 'appearance=recipes.media.blue' in str(trim_error.value)
    assert 'Clock=10 fps' in str(trim_error.value)
    assert '15 <= trim-start < trim-end <= 19' in str(trim_error.value)
    assert 'trim-start=0 / trim-end=19' in str(trim_error.value)
    styles.write_text(style_header + 'media.blue { stack-order: 0; trim-start: 15; trim-end: 19; }\nmedia.red { stack-order: 0; trim-start: 0; trim-end: 9; }\n</sheet>')
    author.write_text(source.replace('<f:Track source={pictures.visual}/>', ''))
    with pytest.raises(HypitIntegrationError, match='必要视频场景'):
        assert_observed_video_uses(author, options)
    author.write_text(source.replace(blue_use['element_id_prefix'], 'unbound-'))
    with pytest.raises(HypitIntegrationError, match='场景标识'):
        assert_observed_video_uses(author, options)
    # An additional indirect use cannot borrow the valid direct shots' coverage.
    indirect = '<p:Transform id="indirect" source={normalized.media}/>'
    extra = '<v:Item id="extra" media={indirect.media} frame={full} appearance={recipes.media.blue} at="0f" for="4f"/>'
    author.write_text(source.replace('<v:Track', indirect + '<v:Track').replace('</v:Track>', extra + '</v:Track>'))
    with pytest.raises(HypitIntegrationError, match='中间变换'):
        assert_observed_video_uses(author, options)
    author.write_text(source)
    def timed_out(*a, **k):
        raise subprocess.TimeoutExpired('local-ffmpeg', 30)
    monkeypatch.setattr(subprocess, 'run', timed_out)
    with pytest.raises(ValueError, match='本地素材预览解码超时'):
        prepare_observation(need, asset, video)
