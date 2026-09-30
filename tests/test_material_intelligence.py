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
    from easel.materials.application.visual_observation import prepare_observation, apply_observation, observed_match, SCHEMA
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
        'file': FileInfo(path='sample.mp4', sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='video/mp4'),
        'technical': TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=2, width=64, height=64)})
    need = MaterialNeed(need_id='late-subject', scope=NeedScope(type=NeedScopeType.SCENE, ref='s1'),
        media_type=MediaType.VIDEO, role='primary_visual', intent=NeedIntent(description='blue field'),
        importance=NeedImportance.REQUIRED, constraints={'logo': False})
    manifest, attachments = prepare_observation(need, asset, video)
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
    assert observed_match(need, observed) is False  # no whole-clip qualification from a late subject
    assert not MaterialMatcher().match(need, [observed]).matches
    assert all(a.field not in {SemanticField.LOGO, SemanticField.VISIBLE_TEXT}
               for a in observed.semantic.inferences[-1].annotations)  # absence not proven
    with pytest.raises(ValueError, match='部分采样'):
        apply_observation(need, asset, manifest, {**report, 'verdict': 'suitable'})
    with pytest.raises(ValueError, match='逐张'):
        apply_observation(need, asset, manifest, {**report, 'frames': report['frames'][1:]})
    with pytest.raises(ValueError, match='不一致'):
        apply_observation(need, asset, manifest, {**report, 'input_sha256': '0' * 64})
    def timed_out(*a, **k):
        raise subprocess.TimeoutExpired('local-ffmpeg', 30)
    monkeypatch.setattr(subprocess, 'run', timed_out)
    with pytest.raises(ValueError, match='本地素材预览解码超时'):
        prepare_observation(need, asset, video)
