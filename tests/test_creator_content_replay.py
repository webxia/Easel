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
from pathlib import Path

import pytest
from PIL import Image

from tests.test_material_integration import material_integration_env
from tests.test_hypit_integration import measured_narration_fixture
from easel import creation, creative_mode
from easel.integrations.hypit import handoff, service, quality
from easel.integrations.material_layer import MaterialGateIntegration, MaterialProductOrchestrator, PlanningIntegration, ProductionAuthoringIntegration
from easel.integrations.material_supply import ProductMaterialSupply, ProviderRegistry
from easel.integrations.script_truth import create_script_claim_ledger
from easel.materials.application.generation_modalities import MiniMaxImageSpeechGeneration
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application import voice_delivery
from easel.materials.application.visual_observation import SCHEMA as OBSERVATION_SCHEMA
from easel.materials.application.rights import RightsService
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
    cases = [
        ('通勤等待', ('假设站在公交站。', '此刻可以先观察。'), ('bus stop',)),
        ('学习新工具', ('假设尝试新工具。', '也许先记录问题。', '再决定下一步。'), ('notebook', 'keyboard')),
        ('安排工作间歇', ('假设暂停手头工作。', '看看窗外。', '也许不必立刻回答。', '再回到当前任务。'), ('desk', 'window', 'clock')),
    ]
    mode_hashes, creator_hashes, script_hashes, native_sources = set(), set(), set(), []
    output_hashes, quality_hashes = set(), set()
    runtime = tmp_path / 'fixture-runtime.json'
    runtime.write_text(json.dumps({'format': 'hypit.runtime-local@1', 'dataRoot': '.fixture-runtime'}))
    prior_voice = None
    for index, (topic, sentences, subjects) in enumerate(cases):
        script = ''.join(sentences)
        work = creation.create_creation(topic, profile='测试', creative_mode='clear_memo_video',
            route='hypit_video', origin={'type': 'chat', 'session_hash': hashlib.sha256(topic.encode()).hexdigest()})
        creation.mark_chat_proposal_ready(work['id'])
        creation.confirm_chat_proposal(work['id'], 'fixture-confirm', delivery_proposal=topic,
            proposal_sha256=hashlib.sha256(topic.encode()).hexdigest())
        package = service.create_creation_handoff(work['id'],
            content_core={'schema': 'content-core@1', 'question': topic}, truth_packet=truth,
            creator_context=creator, production_request={'media_type': 'video', 'orientation': '9:16',
                'language': 'zh-CN', 'preferred_duration_seconds': {'min': 25, 'max': 35}}, max_budget_usd=0)
        attempt = service.create_film_attempt(work['id'], package['handoff_id'],
            preparation_key=hashlib.sha256(topic.encode()).hexdigest(), runtime_status='NOT_CONFIGURED')
        root = Path(attempt['workspace']['path'])
        store = AttemptMaterialStore(root)
        mode, mode_hash = handoff.load_frozen_creative_mode(attempt)
        mode_hashes.add(mode_hash)
        creator_hashes.add(hashlib.sha256((root / 'handoff/creator-context.json').read_bytes()).hexdigest())
        voice_need = MaterialNeed(need_id='narration', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
            media_type=MediaType.AUDIO, role='旁白', importance=NeedImportance.REQUIRED,
            intent=NeedIntent(description='克制的观察旁白'), constraints={'allow_generation': True},
            modality_spec=VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource.DIRECTOR_INTENT,
                reference='同一预置普通话声音'), delivery_description='自然、平静'))
        visuals = tuple(MaterialNeed(need_id=f'visual-{n}', scope=NeedScope(type=NeedScopeType.SCENE, ref=f'scene-{n}'),
            media_type=MediaType.IMAGE, role='主视觉', intent=NeedIntent(description=subject),
            importance=NeedImportance.REQUIRED) for n, subject in enumerate(subjects))
        music_need = MaterialNeed(need_id='music', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
            media_type=MediaType.AUDIO, role='bgm', importance=NeedImportance.REQUIRED,
            intent=NeedIntent(description='calm background music'), modality_spec=BgmNeedSpec(mood='calm'))
        plan = MaterialPlan(plan_id='content-replay', creation_id=work['id'], attempt_id=attempt['attempt_id'],
            context_refs={'creative_mode_sha256': mode_hash}, needs=(*visuals, music_need, voice_need))
        ledger = create_script_claim_ledger(script, root / 'handoff/truth-packet.json')
        assessment = {'schema': 'easel-script-assessment@1',
            'script_sha256': ledger['script_sha256'], 'truth_packet_sha256': ledger['truth_packet_sha256'],
            'decisions': [{'claim_id': row['claim_id'], 'kind': 'creative_expression',
                'reason': '假设情境、建议与保留疑问，不声称实际经历或效果。', 'sources': []}
                for row in ledger['claims'] if row['status'] == 'REVIEW_REQUIRED']}
        planned = PlanningIntegration().persist(attempt, plan, treatment=f'通过{len(subjects)}个观察表达{topic}',
            script=script, scenes=' → '.join(subjects), script_assessment=assessment)
        plan, attempt = planned['plan'], planned['attempt']
        voice_need = plan.needs[-1]
        script_hashes.add(voice_need.modality_spec.text_sha256)
        assert voice_need.constraints['voice_delivery'] == mode['voice_delivery']
        assert all(n.constraints['preferred_style'] == mode['visual_material_style'] for n in plan.needs if n.media_type is MediaType.IMAGE)
        if prior_voice:
            assert not MaterialMatcher().match(voice_need, (prior_voice,)).matches

        local = tmp_path / f'sources-{index}'
        local.mkdir()
        for n, subject in enumerate(subjects):
            Image.new('RGB', (64, 96), (55 + index * 20, 60 + n * 25, 80)).save(local / f'{subject}.png')
        music_file = local / 'calm background music.wav'
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
            f'sine=frequency={170 + index * 40}:sample_rate=16000:duration=30', str(music_file)],
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
        supply = ProductMaterialSupply(registry=registry, library_root=tmp_path / 'shared-library',
                                       rights_facts=lambda *_: rights)
        supplied = supply.run(plan, attempt, local_roots=(local,), supply_run_id='fixture-supply', bundle_id='fixture-bundle')
        assert supplied.readiness.status.value == 'NOT_READY'
        assert all(mode['visual_material_style'] in r.semantic_queries[0] for r in requests if r.need_id.startswith('visual-'))
        assert not any(row['failures'] for row in supplied.routing_trace)
        attempt = MaterialGateIntegration().record(attempt, plan, supplied.bundle, supplied.supply_run,
            supplied.readiness, supplied.gaps)['attempt']
        # Fixed BGM semantics at the observation boundary. The product still
        # lacks automatic BGM listening; do not simulate a Creator approval.
        music_asset = next(a for a in supplied.bundle.assets if a.media_type is MediaType.AUDIO)
        store.write_asset(music_asset.model_copy(update={'semantic': SemanticInfo(caption='calm background music')}))
        MaterialProductOrchestrator._recalculate_observed_materials(attempt, plan, supplied.bundle, store)

        # Fixture TTS output passes the real receive/inspection/generation path.
        duration = 2 * len(sentences) + 1
        mp3 = tmp_path / f'voice-{index}.mp3'
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
            f'sine=frequency={300 + index * 70}:sample_rate=16000:duration={duration}', str(mp3)],
            check=True, capture_output=True, timeout=20)
        cues, offset = [], 0
        for n, sentence in enumerate(sentences):
            cues.append({'text': sentence, 'start_character': offset, 'end_character': offset + len(sentence),
                         'start_seconds': n * 2 + .2, 'end_seconds': n * 2 + 1.6})
            offset += len(sentence)
        calls = []
        class SpeechFixture:
            model = 'speech-2.8-hd'
            voice_id = 'fixture-stable-preset'
            def generate(self, text, **settings):
                calls.append((text, settings))
                return MiniMaxSpeechResult(self.model, self.voice_id, mp3.read_bytes(), 'mp3', tuple(cues), None)
        generated = MiniMaxImageSpeechGeneration(speech_adapter=SpeechFixture()).generate(
            plan, voice_need, store, request_id=f'voice-{index}', confirmed_paid=True, speech_text=script)
        assert calls == [(script, mode['voice_delivery'])]
        # Fixture ownership is explicit test evidence, not inferred Provider rights.
        RightsService(store).record(generated.asset, rights)
        orchestrator = MaterialProductOrchestrator()
        orchestrator._record_generated_asset(attempt, plan, store, store.read_bundle(), generated,
                                              f'voice-{index}', 'speech-2.8-hd')
        recognition_calls = []
        def recognize(path, language):
            recognition_calls.append(path)
            return {'engine': 'fixed-replay-ASR', 'words': [
                {'text': c['text'], 'start_seconds': c['start_seconds'], 'end_seconds': c['end_seconds'],
                 'probability': .99} for c in cues]}
        monkeypatch.setattr(voice_delivery, 'read_local_voice', recognize)
        orchestrator.recover_voice_timing(attempt['attempt_id'])
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
        ready = orchestrator.observe_visual_materials(attempt['attempt_id'], executor=observe)
        assert ready['material_status'] == 'MATERIAL_READY'
        before_calls = (len(calls), len(recognition_calls), len(observations))
        orchestrator.recover_voice_timing(attempt['attempt_id'])
        ready = orchestrator.observe_visual_materials(attempt['attempt_id'], executor=observe)
        assert before_calls == (len(calls), len(recognition_calls), len(observations))
        bundle = store.read_bundle()
        prior_voice = store.read_asset(generated.asset.asset_id)

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
        output = creation.OUTPUTS_DIR / '_creations' / work['id'] / 'attempts' / attempt['attempt_id'] / 'replay.mp4'
        output.parent.mkdir(parents=True, exist_ok=True)
        voice_path = store.resolve_asset_locator(prior_voice.file.path)
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i',
            f'color=c=0x{60 + index * 20:02x}6070:s=160x240:r=12:d=30', '-i', str(voice_path),
            '-i', str(music_file), '-filter_complex',
            '[1:a]volume=0.9,adelay=500:all=1[v];[2:a]volume=0.01[m];[v][m]amix=inputs=2:normalize=0:duration=longest[a]',
            '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac', '-t', '30', str(output)], check=True, capture_output=True, timeout=30)
        def receive_fixture_output(item):
            item['runtime_profile'] = {'path': str(runtime)}
            item['authoring'] = {**item.get('authoring', {}), 'run_path': run.relative_to(root).as_posix()}
            item['execution_status'] = 'BUILD_COMPLETE'
            item['build'] = {'operation': {'execution_fingerprint': service._execution_fingerprint(item)}}
            item['outputs'] = {'final.video': {'path': output.relative_to(creation.OUTPUTS_DIR).as_posix(),
                'sha256': service._file_sha256(output), 'metadata': {'duration_seconds': 30, 'audio_present': True}}}
            return item
        service._save_attempt(attempt['attempt_id'], receive_fixture_output)
        reviews = []
        def review_output(a, manifest, attachments):
            reviews.append(manifest)
            assert manifest['creator_context'] == creator and manifest['mode'] == mode
            assert manifest['content_core']['question'] == topic and manifest['script'] == script
            assert manifest['measurements']['audio']['voice_windows']
            assert attachments and all(x['mimeType'] == 'image/jpeg' for x in attachments)
            return {'schema': quality.SCHEMA, 'input_sha256': manifest['input_sha256'],
                'frames': [{'index': f['index'], 'observed': True, 'description': 'fixture colored panel'} for f in manifest['frames']],
                'checks': {k: {'status': 'pass', 'reason': 'fixed model fixture, not real aesthetic judgement',
                              'frame_indices': [0]} for k in quality.VISUAL_CHECKS}}
        from easel.creation_delivery import advance_creation, next_operation
        operations = []
        async def execute(operation, current):
            operations.append(operation)
            assert operation == 'quality'  # No Provider, Build or manual advancement.
            quality.inspect_output(attempt['attempt_id'], executor=review_output)
        assert next_operation(creation.get_creation(work['id'])) == ('quality', 'checking_quality')
        asyncio.run(advance_creation(work['id'], execute))
        saved = creation.get_creation(work['id'])
        assert saved['delivery']['status'] == 'first_cut_ready', saved['delivery']
        assert next_operation(saved) == (None, 'first_cut_ready')
        report = service.get_film_attempt(attempt['attempt_id'])['review']
        assert report['system']['status'] == 'READY'
        assert report['human']['status'] != 'accepted'
        assert not saved.get('selected_output_name')
        output_hashes.add(report['system']['binding']['sha256'])
        quality_hashes.add(report['system']['input_sha256'])
        review_count = len(reviews)
        asyncio.run(advance_creation(work['id'], execute))
        quality.inspect_output(attempt['attempt_id'], executor=review_output)
        assert len(reviews) == review_count and operations == ['quality']
        assert before_calls == (len(calls), len(recognition_calls), len(observations))
        if index == 2:
            # A plausible renderer regression: the last spoken sentence is
            # absent from the actual MP4, despite valid source/timing/SVML.
            # The existing owner must route an audio repair, not repurchase
            # narration or trust the previous positive output report.
            damaged = output.with_name('missing-tail.mp4')
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
            assert damaged_attempt['review']['system']['status'] == 'REPAIR_REQUIRED'
            assert quality.repair_request(damaged_attempt)['allowed_changes'] == ['audio']
            assert next_operation(creation.get_creation(work['id'])) == ('repair_quality', 'repairing_quality')
            assert before_calls == (len(calls), len(recognition_calls), len(observations))
            assert not creation.get_creation(work['id']).get('selected_output_name')
    assert len(output_hashes) == len(quality_hashes) == 3
    assert len(mode_hashes) == len(creator_hashes) == 1
    assert len(script_hashes) == len(set(native_sources)) == 3
