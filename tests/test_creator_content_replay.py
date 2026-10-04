"""Different Content, one frozen Creator/Mode, through real local boundaries.

The model/ASR/TTS answers are fixed fixtures. This checks execution and evidence
isolation, not whether synthetic tones or colored panels are watchable films.
"""
from __future__ import annotations

import hashlib
import asyncio
import base64
import io
import json
import os
import shutil
import subprocess
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tests.test_material_integration import material_integration_env
from tests.test_minimax_image_speech_generation import MINIMAX_TERMS_FIXTURE
from tests.test_hypit_integration import measured_narration_fixture
from tests.test_creation_preparation import web
from easel import creation, creative_mode, creation_preparation as prep, persona
from easel.integrations.hypit import handoff, service, quality
from easel.integrations.material_layer import MaterialGateIntegration, MaterialProductOrchestrator, PlanningIntegration, ProductionAuthoringIntegration
from easel.integrations import material_supply
from easel.integrations.material_supply import ProviderRegistry
from easel.runtime_config import EaselRuntimeConfig
from easel.integrations.material_generation import generation_budget_preview
from easel.integrations import material_generation
from easel.materials import providers
from easel.materials.providers import minimax_pricing
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application import voice_delivery
from easel.materials.application.visual_observation import SCHEMA as OBSERVATION_SCHEMA
from easel.materials.domain import MaterialPlan, MaterialNeed, NeedScope, NeedScopeType, MediaType, NeedIntent, NeedImportance, VoiceNeedSpec, VoiceIdentityRef, VoiceIdentitySource, RightsInfo, RightsEvidence, RightsStatus
from easel.materials.providers import LocalProvider
from easel.materials.providers.minimax_speech import MiniMaxSpeechResult
from easel.materials.store import AttemptMaterialStore
from easel.materials.domain import BgmNeedSpec, SemanticInfo


def test_same_creator_mode_three_contents_reach_reviewable_first_cut(material_integration_env, tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):
        pytest.skip('Local deterministic audio fixture requires ffmpeg')
    source_mode = Path(__file__).resolve().parents[1] / 'creative_modes/clear_memo_video'
    for source in source_mode.iterdir():
        if source.is_file():
            shutil.copyfile(source, creative_mode.CREATIVE_MODES_DIR / 'clear_memo_video' / source.name)
    previous = Path(material_integration_env['workspace']['path']) / 'handoff'
    creator = json.loads((previous / 'creator-context.json').read_text())
    truth = json.loads((previous / 'truth-packet.json').read_text())
    profiles = tmp_path / 'profiles'
    (profiles / '测试').mkdir(parents=True)
    (profiles / '测试' / 'identity.md').write_text('测试创作者：记录日常观察，不编造亲身经历。')
    (profiles / '测试' / 'style.md').write_text('克制、平等地提出问题，保留不确定性。')
    monkeypatch.setattr(persona, 'PROFILES_DIR', profiles)
    cases = [
        ('通勤等待', ('假设站在公交站。', '此刻可以先观察。'), ('bus stop',)),
        ('学习新工具', ('假设尝试新工具。', '也许先记录问题。', '再决定下一步。'), ('notebook', 'keyboard')),
        ('安排工作间歇', ('假设暂停手头工作。', '看看窗外。', '也许不必立刻回答。', '再回到当前任务。'), ('desk', 'window', 'clock')),
    ]
    mode_hashes, creator_hashes, script_hashes, native_sources = set(), set(), set(), []
    output_hashes, quality_hashes, profile_hashes, content_hashes = set(), set(), set(), set()
    runtime = tmp_path / 'fixture-runtime.json'
    runtime.write_text(json.dumps({'format': 'hypit.runtime-local@1', 'dataRoot': '.fixture-runtime'}))
    prior_voice = None
    base_settings = EaselRuntimeConfig.load()
    base_settings = replace(base_settings, minimax=replace(base_settings.minimax,
        api_key='fixture-key', speech_voice_id='fixture-stable-preset'))
    monkeypatch.setattr(EaselRuntimeConfig, 'load', lambda: base_settings)
    for index, (topic, sentences, subjects) in enumerate(cases):
        script = ''.join(sentences)
        work = creation.create_creation(topic, profile='测试', creative_mode='clear_memo_video',
            route='hypit_video', origin={'type': 'chat', 'session_hash': hashlib.sha256(topic.encode()).hexdigest()})
        creation.mark_chat_proposal_ready(work['id'])
        proposal = topic + '；30 秒，9:16，普通话旁白与配乐。'
        creation.confirm_chat_proposal(work['id'], 'fixture-confirm', delivery_proposal=proposal,
            proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), production_specs={
                'duration_seconds': 30, 'aspect_ratio': '9:16', 'language': 'zh-CN', 'audio_mode': 'mixed'},
            generation_budget={'maxCostCny': 1, 'scopeSha256': generation_budget_preview()['scope_sha256']},
            input_use_statement_sha256=creation.input_use_preview()['statement_sha256'])
        voice_need = MaterialNeed(need_id='narration', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
            media_type=MediaType.AUDIO, role='旁白', importance=NeedImportance.REQUIRED,
            intent=NeedIntent(description='克制的观察旁白'), constraints={'allow_generation': True},
            modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource.DIRECTOR_INTENT,
                reference='同一预置普通话声音'), delivery_description='自然、平静'))
        visuals = tuple(MaterialNeed(need_id=f'visual-{n}', scope=NeedScope(type=NeedScopeType.SCENE, ref=f'scene-{n}'),
            media_type=MediaType.IMAGE, role='主视觉', intent=NeedIntent(description=subject),
            importance=NeedImportance.REQUIRED,
            constraints={'preferred_visual_details': '安静的环境细节与低饱和背景'}) for n, subject in enumerate(subjects))
        music_need = MaterialNeed(need_id='music', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
            media_type=MediaType.AUDIO, role='bgm', importance=NeedImportance.REQUIRED,
            intent=NeedIntent(description='calm background music'), modality_spec=BgmNeedSpec(mood='calm'))
        local = tmp_path / f'sources-{index}'
        local.mkdir()
        for n, subject in enumerate(subjects):
            Image.new('RGB', (64, 96), (55 + index * 20, 60 + n * 25, 80)).save(local / f'{subject}.png')
        if index == 0:
            alternative = Image.new('RGB', (64, 96), (95, 60, 80))
            ImageDraw.Draw(alternative).rectangle((20, 20, 50, 80), fill=(110, 80, 120))
            alternative.save(local / f'{subjects[0]} alternative.png')
        music_file = local / 'calm background music.wav'
        music_duration = 11 + index * 7
        playback = ('loop-start', 'loop-end', 'once-end')[index]
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
            f'aevalsrc=0.1*sin(2*PI*({170 + index * 40}*t+0.6*t*t)):s=16000:d={music_duration}', str(music_file)],
            check=True, capture_output=True, timeout=20)
        rights = RightsInfo(status=RightsStatus.KNOWN, license_name='Owned deterministic test fixture',
            evidence=(RightsEvidence(kind='asset_license', reference='fixture://owned-replay-media'),))
        provider = LocalProvider((local,))
        search, requests = provider.search, []
        def observe_search(intent, continuation=None):
            requests.append(intent)
            return search(intent, continuation)
        monkeypatch.setattr(provider, 'search', observe_search)
        registry = ProviderRegistry()
        registry.register(provider)
        for path in tuple(local.iterdir()):
            path.with_name(path.name + '.rights.json').write_text(json.dumps({
                'schema': 'easel-local-rights@1', 'asset_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'rights': rights.model_dump(mode='json')}))
        settings = replace(base_settings, material=replace(base_settings.material,
            local_roots=(str(local),), library_root=tmp_path / 'shared-library'))
        monkeypatch.setattr(EaselRuntimeConfig, 'load', lambda: settings)
        monkeypatch.setattr(material_supply, 'product_provider_registry', lambda roots: (registry, ()))
        monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: None)
        preparation_calls = []
        recovery_queries = []
        root = None
        def agent(message, *args):
            nonlocal root
            if message.startswith('〔Easel 自动补料〕'):
                assert index == 1 and '首版画面错配后的备选补充' in message
                path = Path(re.search(r'仅写 (.+\.json)，格式：', message)[1])
                answer = json.loads(message.split('，格式：', 1)[1].split('\n', 1)[0])
                recovery_queries.append(answer['request_id'])
                for need_id in answer['search_terms']:
                    n = int(need_id.split('-')[-1])
                    answer['search_terms'][need_id] = [subjects[n] + ' alternative']
                    if need_id in answer.get('shot_choices', {}):
                        answer['shot_choices'][need_id] = {
                            'expression': subjects[n] + '主体可辨，背景细节可替代',
                            'reason': '已有画面观察不适配，保留主体并取舍环境细节'}
                    # Newly available, licensed local source stands in for a
                    # retrieval response. Supply/receipt/observation remain real.
                    picture = Image.new('RGB', (64, 96), (120, 60 + n * 25, 80))
                    ImageDraw.Draw(picture).rectangle((20, 20, 50, 80), fill=(110, 130, 120))
                    media = local / (subjects[n] + ' alternative.png')
                    picture.save(media)
                    media.with_name(media.name + '.rights.json').write_text(json.dumps({
                        'schema': 'easel-local-rights@1', 'asset_sha256': hashlib.sha256(media.read_bytes()).hexdigest(),
                        'rights': rights.model_dump(mode='json')}))
                path.write_text(json.dumps(answer))
            elif message.startswith('〔Easel Material Creative Planning V1〕'):
                preparation_calls.append('planning')
                root = Path(re.search(r'^Attempt workspace: (.+)$', message, re.MULTILINE)[1])
                identity = re.search(r'^Attempt ID: (.+)$', message, re.MULTILINE)[1]
                refs = json.loads(re.search(r'^context_refs: (.+)$', message, re.MULTILINE)[1])
                drafted = MaterialPlan(plan_id='plan-' + identity[-20:], creation_id=work['id'], attempt_id=identity,
                    context_refs=refs, needs=(*visuals, music_need, voice_need))
                for name, value in {'MATERIAL_PLAN.json': drafted.model_dump_json(), 'SCRIPT.md': script,
                    'TREATMENT.md': f'通过{len(subjects)}个观察表达{topic}', 'SCENES.md': ' → '.join(subjects)}.items():
                    (root / 'planning' / name).write_text(value)
            elif message.startswith('〔Easel Script 系统审阅〕'):
                preparation_calls.append('truth')
                path = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
                assessment = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
                for decision in assessment['decisions']:
                    decision.update(kind='creative_expression', reason='假设情境与保留疑问，不声称实际经历或效果。', sources=[])
                path.write_text(json.dumps(assessment))
            else:
                preparation_calls.append('prepare')
                assert len(preparation_calls) == 1 and 'CONFIRMED_PROPOSAL_SHA256' in message
                current = creation.get_creation(work['id'])
                draft = prep.preparation_paths(work['id'], current['preparation']['operation_key'])['draft']
                draft.mkdir(parents=True, exist_ok=True)
                core = {'schema': 'easel-content-core@1', 'topic': topic, 'core_idea': script,
                    'tension': '日常节奏与观察之间的选择。', 'why_worth_telling': '给当前日常场景一个观察角度。',
                    'audience': '测试观众', 'intended_takeaway': '先观察再决定。', 'claim_types': ['hypothesis'],
                    'boundaries': ['假设场景不写成亲身经历。']}
                brief = {'schema': 'easel-production-brief@1', 'language': 'zh-CN', 'duration_seconds': 30,
                    'aspect_ratio': '9:16', 'audio_mode': 'mixed', 'beats': [], 'text_overlays': [],
                    'visual_constraints': [], 'material_sources': [], 'ai_generation_allowed': True,
                    'publication_allowed': False}
                for name, value in {'content-core.json': core, 'truth-packet.json': truth,
                    'creator-context.json': creator, 'production-brief.json': brief}.items():
                    (draft / name).write_text(json.dumps(value, ensure_ascii=False))
            return ''
        monkeypatch.setattr(web, 'run_agent_sync', agent)
        from easel.creation_delivery import advance_creation, next_operation
        assert asyncio.run(advance_creation(work['id'], web._execute_creation_delivery)), creation.get_creation(work['id'])['delivery'].get('last_error')
        prepared_work = creation.get_creation(work['id'])
        assert preparation_calls == ['prepare', 'planning', 'truth']
        assert prepared_work['preparation']['status'] == 'MATERIAL_NOT_READY'
        assert len(prepared_work['hypit_attempts']) == 1
        attempt = service.get_film_attempt(prepared_work['hypit_attempts'][0]['attempt_id'])
        root = Path(attempt['workspace']['path'])
        store = AttemptMaterialStore(root)
        planned = PlanningIntegration().load(attempt)
        plan = planned['plan']
        assert planned['truth_ledger']['status'] == 'PASSED'
        mode, mode_hash = handoff.load_frozen_creative_mode(attempt)
        manifest = json.loads((root / 'handoff/handoff.json').read_text())
        profile_hashes.add(manifest['creator_context']['profile_source_sha256'])
        assert manifest['creator_context']['profile_source_sha256'] == prep._profile_source_hash('测试')
        content_hashes.add(plan.context_refs['content_core_sha256'])
        mode_hashes.add(mode_hash)
        creator_hashes.add(hashlib.sha256((root / 'handoff/creator-context.json').read_bytes()).hexdigest())
        voice_need = plan.needs[-1]
        script_hashes.add(voice_need.modality_spec.text_sha256)
        assert voice_need.constraints['voice_delivery'] == mode['voice_delivery']
        assert all(n.constraints['preferred_style'] == mode['visual_material_style'] for n in plan.needs if n.media_type is MediaType.IMAGE)
        if prior_voice:
            assert not MaterialMatcher().match(voice_need, (prior_voice,)).matches
        assert requests and all(any(mode['visual_material_style'] in q for q in r.semantic_queries)
                                and mode['visual_material_style'] not in r.semantic_queries[0]
                                for r in requests if r.need_id.startswith('visual-'))
        # The actual owner now invokes acoustic observation. Replace only the
        # local classifier, not Asset semantics or a Creator listening decision.
        from tests.test_material_audio_supply import acoustic_fixture
        from easel.materials.application import music_observation
        acoustic_calls = []
        def classify(path):
            acoustic_calls.append(path)
            assert path.read_bytes() == music_file.read_bytes()
            return acoustic_fixture(hashlib.sha256(path.read_bytes()).hexdigest(), music_duration)
        monkeypatch.setattr(music_observation, 'read_local_music', classify)
        music_preflights = []
        monkeypatch.setattr(music_observation, 'require_local_music_model', lambda: music_preflights.append(True))
        write_asset = AttemptMaterialStore.write_asset
        acoustic_interrupted = []
        def persist_asset(self, asset):
            if (index == 2 and not acoustic_interrupted
                    and any(i.analyzer_id.startswith(music_observation.PREFIX) for i in asset.semantic.inferences)):
                acoustic_interrupted.append(asset.asset_id)
                raise OSError('fixture interruption after acoustic report, before Asset registration')
            return write_asset(self, asset)
        monkeypatch.setattr(AttemptMaterialStore, 'write_asset', persist_asset)

        # Fixture TTS output passes the real receive/inspection/generation path.
        duration = 28 if index == 0 else 2 * len(sentences) + 1
        mp3 = tmp_path / f'voice-{index}.mp3'
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
            f'sine=frequency={300 + index * 70}:sample_rate=16000:duration={duration}', str(mp3)],
            check=True, capture_output=True, timeout=20)
        cues, offset = [], 0
        sentence_step = (duration - 1) / len(sentences)
        for n, sentence in enumerate(sentences):
            cues.append({'text': sentence, 'start_character': offset, 'end_character': offset + len(sentence),
                         'start_seconds': n * sentence_step + .2,
                         'end_seconds': (n + 1) * sentence_step - .4})
            offset += len(sentence)
        calls = []
        class SpeechFixture:
            model = 'speech-2.8-hd'
            voice_id = 'fixture-stable-preset'
            def __init__(self, *args, **kwargs):
                assert kwargs['voice_id'] == self.voice_id
            def generate(self, text, **settings):
                calls.append((text, settings))
                return MiniMaxSpeechResult(self.model, self.voice_id, mp3.read_bytes(), 'mp3', tuple(cues), None)
        monkeypatch.setattr(providers, 'MiniMaxSpeechAdapter', SpeechFixture)
        quote_reads = []
        def quoted_contract(url):
            quote_reads.append(url)
            if url == minimax_pricing.TERMS_URL:
                return MINIMAX_TERMS_FIXTURE
            if url == minimax_pricing.VOICE_URL:
                return '| Fixture 普通话 | `fixture-stable-preset` |'
            assert url == minimax_pricing.PRICE_URL
            return '## 语音\n单价：元/万字符。1 个汉字算 2 个字符\n| 同步语音合成 | speech-2.8-hd | 3.5 |\n'
        monkeypatch.setattr(minimax_pricing, 'read_public_contract', quoted_contract)
        # Replace only the externally reviewed agreement version with the
        # synthetic agreement used by this deterministic execution fixture.
        fixture_terms = minimax_pricing.usage_terms_evidence(lambda _: MINIMAX_TERMS_FIXTURE)
        monkeypatch.setattr(material_generation, 'MINIMAX_INTERNAL_TERMS_SHA256', fixture_terms['sha256'])
        monkeypatch.setattr(voice_delivery, 'require_local_voice_model', lambda: None)  # Fixed offline recognizer below.
        monkeypatch.setattr(voice_delivery, 'voice_verification_identity', lambda *a: {
            'model_sha256': 'a' * 64, 'engine': 'fixed-replay-ASR', 'rules': 'fixture-v1'})
        orchestrator = MaterialProductOrchestrator()
        recognition_calls = []
        def recognize(path, language):
            recognition_calls.append(path)
            return {'engine': 'fixed-replay-ASR', 'words': [
                {'text': c['text'], 'start_seconds': c['start_seconds'], 'end_seconds': c['end_seconds'],
                 'probability': .99} for c in cues]}
        monkeypatch.setattr(voice_delivery, 'read_local_voice', recognize)
        observations = []
        def observe(a, manifest, attachments):
            observations.append(manifest)
            assert attachments and manifest['need']['constraints']['preferred_style'] == mode['visual_material_style']
            # Deterministic model boundary: each Need has a different expected
            # panel color. A title or another Need's positive result won't do.
            expected_green = 60 + int(manifest['need']['need_id'].split('-')[-1]) * 25
            with Image.open(io.BytesIO(base64.b64decode(attachments[0]['content']))) as preview:
                related = abs(preview.convert('RGB').getpixel((10, 10))[1] - expected_green) <= 4
            return {'schema': OBSERVATION_SCHEMA, 'input_sha256': manifest['input_sha256'],
                'verdict': 'suitable' if related else 'unsuitable', 'caption': 'deterministic colored fixture panel',
                'style': mode['visual_material_style'], 'reason': 'fixed model response for boundary replay',
                'logo_present': False, 'visible_text_present': False,
                'frames': [{'index': f['index'], 'observed': True, 'related': related,
                            'description': 'colored fixture panel'} for f in manifest['frames']]}
        from easel.creation_delivery import advance_creation, next_operation
        monkeypatch.setattr(web, '_observe_material_frames', observe)
        from easel.materials.application.visual_observation import GROUP_SCHEMA
        monkeypatch.setattr(web, '_observe_material_group', lambda a, group, attachments: {
            'schema': GROUP_SCHEMA, 'input_sha256': group['input_sha256'],
            'reports': {item['need']['need_id']: observe(a, item, attachments) for item in group['observations']}})
        material_operations = []
        async def execute_material(operation, current):
            material_operations.append(operation)
            await web._execute_creation_delivery(operation, current)
        voice_asset_id = None
        for _ in range(10):
            asyncio.run(advance_creation(work['id'], execute_material))
            if material_operations[-1:] == ['generate_material']:
                receipts = store.list_generation_records()
                assert len(receipts) == 1 and receipts[0]['status'] == 'COMPLETE'
                voice_asset_id = receipts[0]['asset_id']
                asset = store.read_asset(voice_asset_id)
                assert asset.rights.status is RightsStatus.UNKNOWN
                assert receipts[0]['commission_authorization']['source'] == 'commission_budget'
                terms = receipts[0]['commission_authorization']['quote']['terms_evidence']
                assert receipts[0]['commission_authorization']['input_use']['creation_id'] == work['id']
                assert asset.rights.evidence[0].reference.endswith(terms['sha256'])
                assert asset.rights.evidence[1].reference.endswith(asset.file.sha256)
                assert not receipts[0]['operator_confirmed_paid']
            if next_operation(creation.get_creation(work['id']))[0] == 'author':
                break
        monkeypatch.setattr(AttemptMaterialStore, 'write_asset', write_asset)
        assert bool(acoustic_interrupted) is (index == 2)
        assert material_operations.count('recover_material') == 1
        assert material_operations.count('generate_material') == 1
        assert material_operations.count('recover_voice_timing') == 1
        assert 1 <= material_operations.count('observe_material') <= 2 * len(sentences) + 1
        assert calls == [(script, mode['voice_delivery'])]
        assert len(acoustic_calls) == 1
        assert music_preflights == [True]
        assert quote_reads == [minimax_pricing.PRICE_URL, minimax_pricing.VOICE_URL, minimax_pricing.TERMS_URL]
        ledger = creation.get_creation(work['id'])['delivery']['material_generations']
        assert len(ledger) == 1 and next(iter(ledger.values()))['status'] == 'complete'
        ready = {'attempt': service.get_film_attempt(attempt['attempt_id'])}
        assert ready['attempt']['material_gate']['status'] == 'MATERIAL_READY'
        before_calls = (len(calls), len(recognition_calls), len(observations))
        orchestrator.recover_voice_timing(attempt['attempt_id'])
        ready = orchestrator.observe_visual_materials(attempt['attempt_id'], executor=observe)
        assert before_calls == (len(calls), len(recognition_calls), len(observations))
        bundle = store.read_bundle()
        prior_voice = store.read_asset(voice_asset_id)
        assert prior_voice.rights.status is RightsStatus.KNOWN
        assert set(prior_voice.rights.usage_constraints) == {'internal_production_only', 'current_creation_only'}
        assert any(e.kind == 'asset_commission_use' for e in prior_voice.rights.evidence)
        assert any(e.kind == 'provider_terms' and fixture_terms['sha256'] in e.reference for e in prior_voice.rights.evidence)
        if index == 0:
            unassessed = prior_voice.model_copy(update={'rights': RightsInfo(status=RightsStatus.UNKNOWN,
                evidence=tuple(e for e in prior_voice.rights.evidence if e.kind != 'asset_commission_use'))})
            committed_work = creation.get_creation(work['id'])
            committed_record = store.list_generation_records()[0]
            assert material_generation.commission_generated_rights(committed_work, plan, voice_need,
                unassessed, committed_record, script) is not None
            old_work, old_record = deepcopy(committed_work), deepcopy(committed_record)
            old_work['delivery']['authorization']['input_use'].update(creation.input_use_preview(version=1))
            old_record['commission_authorization']['input_use'] = deepcopy(old_work['delivery']['authorization']['input_use'])
            assert material_generation.commission_generated_rights(old_work, plan, voice_need,
                unassessed, old_record, script) is not None  # Existing voice permission is not revoked or widened.
            restricted = unassessed.model_copy(update={'rights': unassessed.rights.model_copy(update={'status': RightsStatus.RESTRICTED})})
            assert material_generation.commission_generated_rights(committed_work, plan, voice_need,
                restricted, committed_record, script) is None
            for fault in ('input_grant', 'terms', 'preset', 'creation', 'recognition'):
                altered_work, altered_record = deepcopy(committed_work), deepcopy(committed_record)
                if fault == 'input_grant':
                    altered_work['delivery']['authorization']['input_use'] = None
                elif fault == 'terms':
                    proof = altered_record['commission_authorization']['quote']['terms_evidence']
                    proof['document'] += '<p>未评估的新条款</p>'
                    proof['sha256'] = hashlib.sha256(proof['document'].encode()).hexdigest()
                    request = altered_record['commission_authorization']['request_id']
                    altered_work['delivery']['material_generations'][request]['quote'] = deepcopy(altered_record['commission_authorization']['quote'])
                elif fault == 'preset':
                    altered_record['voice_id'] = 'unverified-voice'
                elif fault == 'creation':
                    altered_work['id'] = 'another-creation'
                else:
                    altered_record['voice_recognition']['words'][0]['text'] = '不符合冻结脚本的另一句话。'
                assert material_generation.commission_generated_rights(altered_work, plan, voice_need,
                    unassessed, altered_record, script) is None, fault

        # Same native authoring fixture, with content-specific pictures and
        # measured captions. No second production representation or real Build.
        source, _, _ = measured_narration_fixture()
        source = source.replace('end="4s"', 'end="30s"')
        source = source.replace('<render:Video id="output"', '<render:Video id="final"')
        source = source.replace('<import as="media"', '<import as="media-track" from="@hypit/media-track@1"/><import as="media"')
        author_path = 'productions/easel-authoring/authors/main.svml'
        source = source.replace('./voice.wav', store.hypit_source_path(prior_voice, author_path))
        music_match = next(m for m in bundle.matches if m.need_id == 'music' and m.qualified)
        music_asset = store.read_asset(music_match.asset_id)
        source = source.replace('./music.wav', store.hypit_source_path(music_asset, author_path))
        source = source.replace('playback="loop"', f'playback="{playback}" fade-in="600ms" fade-out="800ms"')
        if index == 0:
            source = source.replace('playback="loop-start"', 'playback="loop-start" trim-start="500ms" trim-end="9500ms"')
        declarations = ['<space:Frame id="picture-frame" within={canvas} left="0px" top="0px" right="1080px" bottom="1920px"/>']
        items, selected = [], [prior_voice.asset_id, music_asset.asset_id]
        for n, need in enumerate(n for n in plan.needs if n.media_type is MediaType.IMAGE):
            match = next(m for m in bundle.matches if m.need_id == need.need_id and m.qualified)
            asset = store.read_asset(match.asset_id)
            declarations.append(f'<media:Image id="image-{n}" src="{store.hypit_source_path(asset, author_path)}"/>'
                f'<space:Extent id="extent-{n}" width="64" height="96"/>')
            items.append(f'<media-track:Item image={{image-{n}}} extent={{extent-{n}}} frame={{picture-frame}} '
                         f'appearance={{recipes.media.still}} at="{n * (30 // len(subjects))}s" for="{30 // len(subjects)}s"/>')
            selected.append(asset.asset_id)
        source = source.replace('<film:Film', '\n'.join(declarations)
            + '<media-track:Track id="pictures" canvas={canvas} timeline={program.timeline}>' + ''.join(items) + '</media-track:Track><film:Film')
        source = source.replace('<film:Track source={voice-track.audio}/>',
            '<film:Track source={pictures.visual}/><film:Track source={voice-track.audio}/>')
        production = ProductionAuthoringIntegration()
        prepared = production.prepare(ready['attempt'], selected_asset_ids=selected)
        compiled = production.compile_narration(prepared['attempt'], source)
        assert production.compile_narration(prepared['attempt'], compiled) == compiled
        assert all(sentence in compiled for sentence in sentences)
        assert compiled.count('<media-track:Item ') == len(subjects)
        assert 'font={caption-font}' in compiled and 'gain="0.9"' in compiled
        assert compiled.count('<film:Track source={easel-duck-music-track.audio}/>') == 1
        assert '<film:Track source={music-track.audio}/>' not in compiled
        native_sources.append(compiled)
        assert json.loads((root / 'productions/easel-authoring/VOICE_TIMING.json').read_text())['assets'][0]['script_sha256'] == voice_need.modality_spec.text_sha256
        author = root / author_path
        author.parent.mkdir(parents=True, exist_ok=True)
        author.write_text(compiled)
        author.with_name('recipes.svs').write_text('<?svml using="@hypit/svs@1"?>\n<sheet version="1">\n'
            'media.still { stack-order: 10; fit: cover; }\nfilm.memo { background: #101820; }\n'
            'text.caption { stack-order: 20; size: 48; fill: #FFFFFF; }\n</sheet>\n')
        _, current_bundle, readiness = MaterialGateIntegration().assert_ready(prepared['attempt'])
        run = root / 'productions/easel-authoring/runs/main.svrun'
        run.parent.mkdir(parents=True, exist_ok=True)
        run.write_text(json.dumps({'schema': 'easel-authoring-svrun@1', 'creation_id': work['id'],
            'attempt_id': attempt['attempt_id'], 'plan_id': plan.plan_id, 'plan_revision': readiness.plan_revision,
            'bundle_id': current_bundle.bundle_id, 'bundle_revision': current_bundle.revision,
            'readiness_revision': readiness.bundle_revision, 'authoring_source': '../authors/main.svml',
            'material_selection': '../material-selection.json', 'status': 'AUTHORING_READY',
            'publication_allowed': False, 'build': {'enabled': False}}))
        production.validate_authored_selection(prepared['attempt'], run.relative_to(root).as_posix())
        if os.environ.get('EASEL_TEST_HYPIT_CHECK') == '1':
            # Opt-in local contract check; never plan, price, execute or Build.
            checked = subprocess.run(['hypit', 'check', str(run), '--workspace', str(root), '--json'],
                check=False, capture_output=True, text=True, timeout=45)
            assert checked.returncode == 0, checked.stdout + checked.stderr
            result = json.loads(checked.stdout)
            assert result['ok'] is True and result['targets'] == ['final.video']
        # Substitute only the renderer result, not Gate/Planning/Quality or
        # Delivery state. This MP4 is deterministic test media, not a Hypit
        # render of the SVML above and not a perceptual style-quality proof.
        rendered = tmp_path / f'rendered-{index}.mp4'
        voice_path = store.resolve_asset_locator(prior_voice.file.path)
        phase = (music_duration - 30 % music_duration) % music_duration if playback == 'loop-end' else 0
        music_filter = (f'atrim=start={phase},asetpts=PTS-STARTPTS' if playback != 'once-end'
                        else f'atrim=duration={music_duration},asetpts=PTS-STARTPTS,adelay={(30 - music_duration) * 1000}:all=1')
        if index == 0:
            music_filter = 'atrim=start=0.5:end=9.5,asetpts=PTS-STARTPTS,aloop=loop=-1:size=144000:start=0'
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
            f'color=c=0x{60 + index * 20:02x}6070:s=144x256:r=12:d=30', '-i', str(voice_path),
            '-stream_loop', '-1', '-i', str(music_file), '-filter_complex',
            f'[1:a]volume=0.9,adelay=500:all=1[v];[2:a]{music_filter},volume=0.01[m];[v][m]amix=inputs=2:normalize=0:duration=longest[a]',
            '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac', '-t', '30', str(rendered)], check=True, capture_output=True, timeout=30)
        # Fake only the renderer CLI and model invocation. The backend's real
        # Authoring/Runtime/Plan/Pricing/approval/Build/export services own state.
        renderer_calls, author_calls, builds = [], [], {}
        class RendererFixture:
            def check(self, *args, **kwargs):
                renderer_calls.append('check')
                return {'format': 'hypit.cli-check@1', 'ok': True}
            def plan(self, workspace, source, **kwargs):
                renderer_calls.append('plan')
                return {'format': 'hypit.cli-plan@1', 'ok': True, 'run': str(source)}
            def pricing(self, *args, **kwargs):
                renderer_calls.append('pricing')
                return {'format': 'hypit.cli-pricing@1', 'requestCount': 1,
                        'noChargeRequestCount': 1, 'groups': []}
            def build(self, workspace, *args, **kwargs):
                renderer_calls.append('build')
                assert str(workspace) not in builds  # No duplicate submission per Attempt.
                builds[str(workspace)] = f'bld_fixture_{index}_{len(builds)}'
                return {'format': 'hypit.cli-build@1', 'build': {'id': builds[str(workspace)]}}
            def status(self, workspace, build_id, **kwargs):
                renderer_calls.append('status')
                assert build_id == builds[str(workspace)]
                if index == 1 and renderer_calls.count('status') == 1:
                    raise service.HypitIntegrationError('fixture temporary status disconnection')
                return {'format': 'hypit.cli-status@1', 'build': {'id': build_id,
                    'work': {'state': 'done', 'outcome': 'complete'}, 'result': {'state': 'complete', 'outputCount': 1}}}
            def inspect(self, workspace, build_id, **kwargs):
                renderer_calls.append('inspect')
                assert build_id == builds[str(workspace)]
                return {'format': 'hypit.cli-inspect@1', 'build': {'id': build_id,
                    'outputs': [{'name': 'final.video', 'target': True, 'mediaType': 'video/mp4'}]}}
            def get(self, workspace, build_id, output_name, destination):
                renderer_calls.append('get')
                assert build_id == builds[str(workspace)] and output_name == 'final.video'
                shutil.copyfile(rendered, destination)
                return {'format': 'hypit.cli-get@1', 'build': build_id, 'output': output_name}
        def authored_fixture(**kwargs):
            author_calls.append(kwargs['attempt_id'])
            current_root = Path(kwargs['attempt_workspace'])
            assert (current_root / author_path).read_text() == compiled
            if current_root != root:
                current_attempt = service.get_film_attempt(kwargs['attempt_id'])
                expected_scope = ['audio', 'visual', 'visual_material'] if index < 2 else ['audio', 'visual']
                assert current_attempt['revision_feedback']['allowed_changes'] == expected_scope
                if index < 2:
                    alternatives = service.quality_visual_replacements(current_attempt)
                    assert alternatives, 'repair must observe an existing alternative before authoring'
                    replaced = compiled
                    for old_src, options in alternatives.items():
                        replaced = replaced.replace(old_src, sorted(options)[0])
                    assert replaced != compiled
                    (current_root / author_path).write_text(replaced)
                new_plan, new_bundle, new_ready = MaterialGateIntegration().assert_ready(current_attempt)
                from easel.integrations.material_recovery import director_shot_choices
                author_choices = director_shot_choices(current_attempt, new_plan)
                author_manifest = json.loads((current_root / 'productions/easel-authoring/material-selection.json').read_text())
                assert author_manifest.get('director_shot_choices', {}) == author_choices
                if index == 1:
                    assert set(author_choices) == {n.need_id for n in visuals}
                # Fixed model answer only. Forking, checkpoint reuse, authoring
                # admission and all ensuing state transitions run in product code.
                new_run = current_root / run.relative_to(root)
                new_run.parent.mkdir(parents=True, exist_ok=True)
                new_run.write_text(json.dumps({
                    'schema': 'easel-authoring-svrun@1', 'creation_id': work['id'],
                    'attempt_id': current_attempt['attempt_id'], 'plan_id': new_plan.plan_id,
                    'plan_revision': new_ready.plan_revision, 'bundle_id': new_bundle.bundle_id,
                    'bundle_revision': new_bundle.revision, 'readiness_revision': new_ready.bundle_revision,
                    'authoring_source': '../authors/main.svml', 'material_selection': '../material-selection.json',
                    'status': 'AUTHORING_READY', 'publication_allowed': False, 'build': {'enabled': False}}))
            return ''  # Fixed native model output was authored above, never a live Agent.
        monkeypatch.setattr(service, 'HypitCLI', RendererFixture)
        monkeypatch.setattr(web, '_hypit_runtime_profile', lambda: str(runtime))
        monkeypatch.setattr(web, 'run_attempt_scoped_authoring', authored_fixture)
        reviews = []
        def review_output(a, manifest, attachments):
            reviews.append(manifest)
            assert manifest['creator_context'] == creator and manifest['mode'] == mode
            assert manifest['content_core']['topic'] == topic and manifest['script'] == script
            from easel.integrations.material_recovery import director_shot_choices
            current_plan = PlanningIntegration().load(a)['plan']
            expected_choices = director_shot_choices(a, current_plan)
            assert manifest.get('director_shot_choices', {}) == expected_choices
            if index == 1 and a['attempt_id'] != attempt['attempt_id']:
                assert set(expected_choices) == {n.need_id for n in visuals}
                assert all(expected_choices[n.need_id]['expression'].startswith(subjects[j])
                           for j, n in enumerate(visuals))
            assert manifest['measurements']['audio']['voice_windows']
            assert manifest['measurements']['music']['assets'][0]['sha256'] == music_asset.file.sha256
            assert attachments and all(x['mimeType'] == 'image/jpeg' for x in attachments)
            result = {'schema': quality.SCHEMA, 'input_sha256': manifest['input_sha256'],
                'frames': [{'index': f['index'], 'observed': True, 'description': 'fixture colored panel'} for f in manifest['frames']],
                'checks': {k: {'status': 'pass', 'reason': 'fixed model fixture, not real aesthetic judgement',
                              'frame_indices': [0]} for k in quality.VISUAL_CHECKS}}
            if manifest['binding']['sha256'] != service._file_sha256(rendered):
                key = ('truth_expression', 'creator', 'narrative')[index]
                result['checks'][key].update(status='fail',
                    reason='fixed presentation defect; preserve the frozen script, voice and timing',
                    repair_target='visual_material' if index < 2 else 'visual')
                if index == 0 and manifest['observation_round'] == 1:
                    result['checks'][key]['repair_target'] = 'unknown'
                elif index == 0:
                    assert key in manifest['review_focus']
            return result
        from easel.creation_delivery import advance_creation, next_operation
        operations = []
        monkeypatch.setattr(web, '_review_output_frames', review_output)
        async def execute(operation, current):
            operations.append(operation)
            await web._execute_creation_delivery(operation, current)
        for _ in range(16):
            asyncio.run(advance_creation(work['id'], execute))
            current = creation.get_creation(work['id'])
            if operations[-1:] == ['refresh'] and index == 1 and operations.count('refresh') == 1:
                assert current['delivery']['status'] == 'observation_failed'
                assert current['hypit_attempts'][-1]['execution_status'] == 'SUBMITTED'
            if next_operation(current) == (None, 'first_cut_ready'):
                break
        expected_operations = ['author', 'runtime', 'validate', 'price', 'approve_free', 'submit', 'refresh']
        if index == 1:
            expected_operations.append('refresh')
        expected_operations += ['export', 'quality']
        assert operations == expected_operations, creation.get_creation(work['id'])['delivery']
        assert author_calls == [attempt['attempt_id']]
        assert renderer_calls.count('build') == renderer_calls.count('get') == 1
        saved = creation.get_creation(work['id'])
        assert saved['delivery']['status'] == 'first_cut_ready', saved['delivery']
        assert next_operation(saved) == (None, 'first_cut_ready')
        exported = service.get_film_attempt(attempt['attempt_id'])
        assert exported['outputs']['final.video']['material_usage'] == [{
            'asset_id': prior_voice.asset_id, 'sha256': prior_voice.file.sha256,
            'constraints': ['internal_production_only', 'current_creation_only'],
        }]
        output = creation.OUTPUTS_DIR / exported['outputs']['final.video']['path']
        assert exported['cost']['approved'] is True and exported['cost']['approved_budget_usd'] == 0
        assert exported['cost']['approval_kind'] == 'confirmed_commission_no_charge'
        assert output.read_bytes() == rendered.read_bytes()
        report = exported['review']
        assert report['system']['status'] == 'READY'
        if index == 0:
            windows = report['system']['measurements']['music']['assets'][0]['windows']
            assert windows and all(w['voice_projected'] and w['correlation'] > .9 for w in windows)
        assert report['human']['status'] != 'accepted'
        assert not saved.get('selected_output_name')
        assert preparation_calls == ['prepare', 'planning', 'truth']
        output_hashes.add(report['system']['binding']['sha256'])
        quality_hashes.add(report['system']['input_sha256'])
        review_count, renderer_count = len(reviews), len(renderer_calls)
        asyncio.run(advance_creation(work['id'], execute))
        quality.inspect_output(attempt['attempt_id'], executor=review_output)
        assert len(reviews) == review_count and operations == expected_operations
        assert len(renderer_calls) == renderer_count and author_calls == [attempt['attempt_id']]
        assert before_calls == (len(calls), len(recognition_calls), len(observations))
        # Renderer regressions: BGM or the last spoken sentence is absent
        # from actual MP4 despite valid source/timing/SVML.
        # The existing owner must route an audio repair, not repurchase
        # narration or trust the previous positive output report.
        damaged = output.with_name('missing-music.mp4' if index < 2 else 'missing-tail.mp4')
        if index < 2:
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(output), '-i', str(voice_path),
                '-map', '0:v', '-map', '1:a', '-af', 'volume=0.9,adelay=500:all=1,apad',
                '-c:v', 'copy', '-c:a', 'aac', '-t', '30', str(damaged)],
                check=True, capture_output=True, timeout=20)
        else:
            begin, end = .5 + cues[-1]['start_seconds'], .5 + cues[-1]['end_seconds']
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(output),
                '-af', f"volume=0:enable='between(t,{begin},{end})'", '-c:v', 'copy', '-c:a', 'aac', str(damaged)],
                check=True, capture_output=True, timeout=20)
        def receive_damaged_output(item):
            item['outputs']['final.video'].update(
                path=damaged.relative_to(creation.OUTPUTS_DIR).as_posix(), sha256=service._file_sha256(damaged))
            return item
        service._save_attempt(attempt['attempt_id'], receive_damaged_output)
        assert next_operation(creation.get_creation(work['id'])) == ('quality', 'checking_quality')
        asyncio.run(advance_creation(work['id'], execute))
        damaged_attempt = service.get_film_attempt(attempt['attempt_id'])
        if index == 0:
            assert next_operation(creation.get_creation(work['id'])) == ('quality', 'checking_quality')
            assert quality.repair_request(damaged_attempt) is None
            asyncio.run(advance_creation(work['id'], execute))
            damaged_attempt = service.get_film_attempt(attempt['attempt_id'])
            assert damaged_attempt['review']['system']['observation_round'] == 2
        assert damaged_attempt['review']['system']['status'] == 'REPAIR_REQUIRED'
        defects = damaged_attempt['review']['system']['measurements']['defects']
        assert any(d['kind'] == ('music_missing' if index < 2 else 'voice_missing') for d in defects)
        if index < 2:
            assert not damaged_attempt['review']['system']['measurements']['audio']['defects']
            assert {d['kind'] for d in defects} == {'music_missing'}  # Prior voice-only QC missed this.
        assert quality.repair_request(damaged_attempt)['allowed_changes'] == (
            ['audio', 'visual', 'visual_material'] if index < 2 else ['audio', 'visual'])
        assert next_operation(creation.get_creation(work['id'])) == ('repair_quality', 'repairing_quality')
        assert before_calls == (len(calls), len(recognition_calls), len(observations))
        assert not creation.get_creation(work['id']).get('selected_output_name')
        if index == 0:
            # Without the admitted narration reference, an overlapping probe
            # must still report a gap, never fabricate a separated signal.
            unmeasurable = quality.measure_music(output, 30, compiled, plan, bundle, store, (0., 30.))
            assert {d['kind'] for d in unmeasurable['defects']} == {'music_unverifiable'}
            transformed = quality.measure_music(output, 30, compiled.replace('playback="loop-start"',
                'playback="stretch" min-rate="0.1" max-rate="2"'), plan, bundle, store, None)
            assert {d['kind'] for d in transformed['defects']} == {'music_unverifiable'}
            admitted_music = store.resolve_asset_locator(music_asset.file.path)
            original_bytes = admitted_music.read_bytes()
            try:
                admitted_music.write_bytes(b'changed admitted soundtrack')
                with pytest.raises(service.HypitIntegrationError, match='编排输入'):
                    quality.inspect_output(attempt['attempt_id'], executor=review_output)
            finally:
                admitted_music.write_bytes(original_bytes)
        # Continue the actual owner past defect routing. A repaired output must
        # arrive without a second TTS, manual approval or engineering state edit.
        repair_start = len(operations)
        copy_file = service._copy_retry_checkpoint_file
        interrupted = []
        from easel.integrations import material_layer
        update_attempt = material_layer._update_attempt
        observation_interrupted = []
        def update_observation(item, **fields):
            if index == 0 and fields.get('material_observation', {}).get('quality_report_sha256') and not observation_interrupted:
                observation_interrupted.append(item['attempt_id'])
                raise OSError('fixture interrupted after observed material checkpoint')
            return update_attempt(item, **fields)
        monkeypatch.setattr(material_layer, '_update_attempt', update_observation)
        record_gate = MaterialGateIntegration.record
        supply_interrupted = []
        def record_supply(self, current_attempt, current_plan, current_bundle, *args, **kwargs):
            if index == 1 and current_bundle.supply_run_id.startswith('supplement-') and not supply_interrupted:
                supply_interrupted.append((current_attempt['attempt_id'], len(requests)))
                raise OSError('fixture supply saved before Gate update')
            return record_gate(self, current_attempt, current_plan, current_bundle, *args, **kwargs)
        monkeypatch.setattr(MaterialGateIntegration, 'record', record_supply)
        source_bundle_revision = store.read_bundle().revision
        supply_calls = len(requests)
        def copy_checkpoint(source_root, target_root, relative):
            copy_file(source_root, target_root, relative)
            if index == 1 and not interrupted and relative.parts[:2] == ('materials', 'assets'):
                interrupted.append(str(target_root))
                raise OSError('fixture interrupted after durable asset copy')
        monkeypatch.setattr(service, '_copy_retry_checkpoint_file', copy_checkpoint)
        for _ in range(16):
            asyncio.run(advance_creation(work['id'], execute))
            current = creation.get_creation(work['id'])
            if operations[-1] == 'repair_quality':
                target = current['hypit_attempts'][-1]
                assert target['cost']['approved'] is False and target['cost']['status'] == 'not_estimated'
                assert target['outputs'] == {}
                if current['delivery']['status'] == 'retrying':
                    assert index == 1 and interrupted == [target['workspace']['path']]
                    assert current['delivery']['recovering_quality_from'] == attempt['attempt_id']
                    assert target['retry_source']['status'] == 'COPYING'
            if next_operation(current) == (None, 'first_cut_ready'):
                break
        monkeypatch.setattr(service, '_copy_retry_checkpoint_file', copy_file)
        monkeypatch.setattr(material_layer, '_update_attempt', update_attempt)
        monkeypatch.setattr(MaterialGateIntegration, 'record', record_gate)
        assert current['delivery']['status'] == 'first_cut_ready', current['delivery'].get('last_error')
        repaired = current['hypit_attempts'][-1]
        assert repaired['attempt_id'] != attempt['attempt_id']
        assert len(current['hypit_attempts']) == 2
        repair_operations = ['repair_quality'] * (2 if index == 1 else 1)
        if index == 0:
            repair_operations.extend(['observe_material', 'observe_material'])
        elif index == 1:
            repair_operations.extend(['observe_material', 'recover_material', 'recover_material', 'observe_material'])
        suffix = ['author', 'validate', 'price', 'approve_free', 'submit', 'refresh', 'export', 'quality']
        assert operations[-len(suffix):] == suffix
        material_prefix = operations[repair_start:-len(suffix)]
        assert material_prefix[:2 if index == 1 else 1] == ['repair_quality'] * (2 if index == 1 else 1)
        assert material_prefix.count('recover_material') == (2 if index == 1 else 0)
        assert material_prefix.count('observe_material') >= repair_operations.count('observe_material')
        assert set(material_prefix) <= {'repair_quality', 'observe_material', 'recover_material'}
        assert current['delivery']['quality_repairs'] == [attempt['attempt_id']]
        assert current['delivery']['material_generations'] == ledger
        assert renderer_calls.count('build') == renderer_calls.count('get') == 2
        assert renderer_calls.count('pricing') == 2
        assert before_calls[:2] == (len(calls), len(recognition_calls))
        assert store.read_bundle().revision == source_bundle_revision
        if index != 1:
            assert len(observations) == before_calls[2] + int(index == 0)
            assert len(requests) == supply_calls and not recovery_queries
        else:
            assert len(recovery_queries) == 1
            assert len(requests) > supply_calls and all(r.need_id.startswith('visual-') for r in requests[supply_calls:])
            assert supply_interrupted == [(repaired['attempt_id'], len(requests))]
            assert repaired['autonomous_material_recovery']['status'] == 'COMPLETE'
            assert {r['need']['need_id'] for r in observations[before_calls[2]:]} == {n.need_id for n in visuals}
            from easel.integrations.material_recovery import recover_managed_materials
            with pytest.raises(ValueError, match='Owner'):
                recover_managed_materials(repaired['attempt_id'], executor=lambda *_: pytest.fail('unauthorized query'))
        if index == 0:
            old_images = set(exported['production_authoring']['selected_asset_ids']) - {prior_voice.asset_id, music_asset.asset_id}
            new_images = set(repaired['production_authoring']['selected_asset_ids']) - {prior_voice.asset_id, music_asset.asset_id}
            assert old_images.isdisjoint(new_images) and len(old_images) == len(new_images) == 1
            assert observations[-1]['asset_id'] in new_images
            assert observation_interrupted == [repaired['attempt_id']]
            assert repaired['material_observation']['quality_report_sha256'] == repaired['revision_feedback']['quality_report_sha256']
        assert preparation_calls == ['prepare', 'planning', 'truth']
        assert author_calls == [attempt['attempt_id'], repaired['attempt_id']]
        assert repaired['cost']['approval_kind'] == 'confirmed_commission_no_charge'
        assert repaired['review']['system']['binding']['sha256'] == service._file_sha256(rendered)
        assert repaired['outputs']['final.video']['material_usage'] == exported['outputs']['final.video']['material_usage']
        assert repaired['review']['human']['status'] != 'accepted' and not current.get('selected_output_name')
        assert service.get_film_attempt(attempt['attempt_id'])['review']['system']['status'] == 'REPAIR_REQUIRED'
        completed_calls = (len(renderer_calls), len(author_calls), len(reviews))
        asyncio.run(advance_creation(work['id'], execute))
        assert completed_calls == (len(renderer_calls), len(author_calls), len(reviews))
    assert len(output_hashes) == len(quality_hashes) == 3
    assert len(mode_hashes) == len(creator_hashes) == 1
    assert len(profile_hashes) == 1 and len(content_hashes) == 3
    assert len(script_hashes) == len(set(native_sources)) == 3
