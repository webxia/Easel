"""Failure-shape contracts; no real gateway, provider or model inference."""
from copy import deepcopy
import hashlib

import pytest
from easel.materials.domain import (
    MaterialNeed, NeedIntent, NeedScope, NeedScopeType, NeedImportance, MediaType,
    MaterialAsset, CandidateSource, FileInfo, TechnicalInfo, TechnicalStatus, RightsInfo,
    RightsStatus, RightsEvidence, VoiceNeedSpec, VoiceIdentityRef, VoiceIdentitySource,
)
from easel.materials.application.visual_contract import (
    compilation_input, validate_compilation, classification_units, bind_classifications, batches, assemble_report,
)
from easel.materials.application.visual_observation import apply_observation, need_identity, requires_reassessment
from easel.materials.providers.minimax_speech import MiniMaxSpeechAdapter


def visual_need():
    return MaterialNeed(need_id='paper', scope=NeedScope(type=NeedScopeType.SCENE, ref='paper'),
        media_type=MediaType.IMAGE, role='visual', importance=NeedImportance.REQUIRED,
        intent=NeedIntent(description='two visible paper sheets'),
        constraints={'preferred_visual_details': 'low angle'})


@pytest.mark.parametrize('fault', [None, 'missing', 'unknown_status', 'duplicated', 'wrong_need', 'preference_promoted', 'quoted', 'quote_gap', 'units', 'unit_missing', 'unit_duplicate', 'long_fields', 'oversize_report', 'old_camera'])
def test_required_paper_and_optional_angle_have_distinct_admission_contracts(fault):
    need = visual_need()
    if fault in {'units', 'unit_missing', 'unit_duplicate'}:
        need = need.model_copy(update={'intent': NeedIntent(description='two visible paper sheets, no hand; no logo',
                                                               function='Hold the idea that pages remain, not removed.')})
    frozen = compilation_input(need, {'brief_sha256': 'a' * 64}, {})
    response = {'clauses': [[0, 0, len(frozen['sources'][0]['text']), 'required', None],
                             [1, 0, len(frozen['sources'][1]['text']), 'preference', None]]}
    if fault in {'quoted', 'quote_gap'}:
        canonical = validate_compilation(frozen, response)
        response['clauses'] = [[i, row['text'], 'preference' if row['preference'] else 'required', None]
                               for i, row in enumerate(frozen['sources'])]
        if fault == 'quote_gap':
            response['clauses'][0][1] = response['clauses'][0][1].replace(' ', '', 1)
            with pytest.raises(ValueError, match='逐段逐字'):
                validate_compilation(frozen, response)
            return
        assert validate_compilation(frozen, response) == canonical
        fault = None
    if fault in {'units', 'unit_missing', 'unit_duplicate'}:
        units = classification_units(frozen)
        assert ''.join(u['text'] for u in units if u['source'] == 0) == frozen['sources'][0]['text']
        assert len([u for u in units if u['source'] == 1]) == 1
        labels = {'classifications': [{'id': u['id'], 'kind': 'postproduction' if u['source'] == 1 else 'required', 'preference_source': None} for u in units]}
        if fault == 'unit_missing':
            labels['classifications'].pop()
        elif fault == 'unit_duplicate':
            labels['classifications'][-1]['id'] = 0
        if fault != 'units':
            with pytest.raises(ValueError, match='unit编号'):
                bind_classifications(frozen, labels)
            return
        response = bind_classifications(frozen, labels)
        fault = None
    if fault == 'preference_promoted':
        response['clauses'][1][3] = 'required'
        with pytest.raises(ValueError, match='显式偏好'):
            validate_compilation(frozen, response)
        return
    contract = validate_compilation(frozen, response)
    asset = MaterialAsset(asset_id='image', media_type=MediaType.IMAGE,
        file=FileInfo(path='materials/assets/image/original.png', sha256='b' * 64, size=1, mime='image/png'),
        source=CandidateSource(kind='fixture'), rights=RightsInfo(status=RightsStatus.UNKNOWN), technical=TechnicalInfo(status=TechnicalStatus.PASSED))
    manifest = {'need_sha256': need_identity(need), 'asset_sha256': asset.file.sha256, 'asset_id': asset.asset_id,
                'input_sha256': 'c' * 64, 'media_type': 'image', 'frames': [{'index': 0, 'sha256': 'd' * 64}]}
    result = {'frame': 0, 'observed': True, 'description': 'two sheets, frontal', 'style': 'daylight',
              'logo': False, 'text': False, 'preference_notes': 'angle differs',
              'checks': [{'id': c['id'], 'status': 'met', 'basis': 'actual visible sheets, no hand or logo'}
                         for c in contract['clauses'] if c['kind'] == 'required']}
    if fault in {'long_fields', 'oversize_report'}:
        result['preference_notes'] = '偏好记录较长但不构成必要检查。' * (4 if fault == 'long_fields' else 300)
        if fault == 'oversize_report':
            with pytest.raises(ValueError, match='总容量'):
                assemble_report(manifest, contract, [result])
            return
        fault = None
    good = assemble_report(manifest, contract, [result])
    if fault == 'old_camera':
        old = deepcopy(good)
        old['assessment_revision'] = 'requirements-v1'
        old['verdict'] = 'unsuitable'
        old['compact_results'][0]['checks'][0].update(status='not_met', basis='缺少向上揭示镜头运动')
        assert requires_reassessment(need, old, MediaType.IMAGE)
        assert not requires_reassessment(need.model_copy(update={'constraints': {'requires_dynamic_action': True}}), old, MediaType.IMAGE)
        assert not requires_reassessment(need, {**old, 'assessment_revision': good['assessment_revision']}, MediaType.IMAGE)
        fault = None
    assert good['verdict'] == 'suitable'  # The explicit angle preference cannot refuse it.
    apply_observation(need, asset, manifest, good)
    missing_paper = deepcopy(result)
    missing_paper['checks'][0].update(status='not_met', basis='only one sheet visible')
    assert assemble_report(manifest, contract, [missing_paper])['verdict'] == 'unsuitable'
    if fault == 'missing': result['checks'] = []
    elif fault == 'unknown_status': result['checks'][0]['status'] = 'looks fine'
    elif fault == 'duplicated': result['checks'] += deepcopy(result['checks'])
    elif fault == 'wrong_need': contract['need_sha256'] = 'e' * 64
    if fault:
        with pytest.raises(ValueError):
            if fault == 'wrong_need':
                apply_observation(need, asset, manifest, {**good, 'requirements_contract': contract})
            else:
                assemble_report(manifest, contract, [result])
    else:
        # Capacity is planned for escaped Unicode, with no omitted clauses.
        for group in batches(manifest, contract):
            assert group['clauses']


@pytest.mark.parametrize('fault', [None, 'missing', 'extra', 'reordered', 'overlap', 'wrong_offset'])
def test_subtitle_mapping_proves_whole_script_without_guessing_newline_counts(fault):
    script = '第一句。\n第二句。\n第一句。'
    texts = ['第一句。', '第二句。', '第一句。']
    cues = tuple({'text': text, 'start_character': i * 4, 'end_character': (i + 1) * 4,
                  'start_seconds': float(i), 'end_seconds': i + .8} for i, text in enumerate(texts))
    rows = list(deepcopy(cues))
    if fault == 'missing': rows.pop(1)
    elif fault == 'extra': rows[-1]['text'] += '啊'
    elif fault == 'reordered': rows[0]['text'], rows[1]['text'] = rows[1]['text'], rows[0]['text']
    elif fault == 'overlap': rows[1]['start_seconds'] = .4
    elif fault == 'wrong_offset': rows[1]['start_character'] = 5
    if fault:
        with pytest.raises(ValueError):
            MiniMaxSpeechAdapter.map_timings(script, tuple(rows))
    else:
        mapped = MiniMaxSpeechAdapter.map_timings(script, cues)
        assert [(r['start_character'], r['end_character']) for r in mapped] == [(0, 4), (5, 9), (10, 14)]
        assert [(r['start_seconds'], r['end_seconds']) for r in mapped] == [(i, i + .8) for i in range(3)]
        assert cues[1]['start_character'] == 4  # Original Provider evidence is unchanged.


@pytest.mark.parametrize('fault', [None, 'same_model', 'different_audio', 'stale_primary', 'missing_interval', 'disagreement', 'bad_capability'])
def test_independent_interval_closes_low_confidence_without_rewriting_probabilities(fault):
    from easel.materials.application.voice_delivery import (
        apply_voice_content, timing_from_recognition, voice_content_observed, recognition_digest,
    )
    from easel.materials.application.voice_supplement import primary_digest, REVISION
    from easel.materials.application.matching import MaterialMatcher
    script = '假设清晨。'
    need = MaterialNeed(need_id='voice', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
        media_type=MediaType.AUDIO, role='voice', intent=NeedIntent(description='clear narration'),
        importance=NeedImportance.REQUIRED, modality_spec=VoiceNeedSpec(text_ref='artifacts/SCRIPT.md', text_sha256=hashlib.sha256(script.encode()).hexdigest(),
            identity=VoiceIdentityRef(source=VoiceIdentitySource.EXPLICIT_USER, reference='preset Mandarin')))
    asset = MaterialAsset(asset_id='voice', media_type=MediaType.AUDIO,
        file=FileInfo(path='materials/assets/voice/audio.mp3', sha256='a' * 64, size=1, mime='audio/mpeg'),
        source=CandidateSource(kind='generative', provider='minimax'),
        rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=2., mime='audio/mpeg'))
    words = [{'text': '假设', 'start_seconds': .1, 'end_seconds': .6, 'probability': .2},
             {'text': '清晨。', 'start_seconds': .6, 'end_seconds': 1.2, 'probability': .95}]
    primary = {'words': words, 'model_sha256': 'b' * 64, 'audio_sha256': asset.file.sha256,
               'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
               'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
    descriptor = {'model_sha256': 'c' * 64, 'rules': 'complete-voice-and-independent-interval@2', 'version': 'fixture'}
    independent = {'words': [{**w, 'probability': .95} for w in words],
                   'model_sha256': descriptor['model_sha256'], 'verification_config': descriptor}
    cases = []
    for name in ('complete', 'wrong_word', 'missing_word', 'extra_word'):
        report = deepcopy(independent)
        if name == 'wrong_word': report['words'][0]['text'] = '真的'
        elif name == 'missing_word': report['words'].pop()
        elif name == 'extra_word': report['words'][-1]['text'] += '啊'
        cases.append({'id': name, 'expected_acceptance': name == 'complete', 'script': script,
                      'audio_sha256': hashlib.sha256(name.encode()).hexdigest(), 'duration_seconds': 2., 'recognition': report})
    capability = {'schema': 'local-voice-capability@1', 'verification': descriptor, 'cases': cases}
    capability['identity'] = recognition_digest(capability)
    proof = {'schema': REVISION, 'primary_sha256': primary_digest(primary), 'audio_sha256': asset.file.sha256,
             'script_sha256': primary['script_sha256'], 'need_sha256': primary['need_sha256'], 'word_index': 0,
             'context_words': [0, 2], 'interval': [0., 1.5], 'recognition': independent,
             'verification': descriptor, 'capability': capability, 'capability_sha256': capability['identity']}
    if fault == 'same_model': descriptor['model_sha256'] = 'b' * 64
    elif fault == 'different_audio': proof['audio_sha256'] = 'e' * 64
    elif fault == 'stale_primary': proof['primary_sha256'] = 'e' * 64
    elif fault == 'missing_interval': proof['interval'] = [.3, 1.5]
    elif fault == 'disagreement': independent['words'][0]['text'] = '真的'
    elif fault == 'bad_capability': capability['cases'][1]['recognition'] = deepcopy(independent)
    combined = {**primary, 'supplements': [proof]}
    if fault:
        with pytest.raises(ValueError):
            timing_from_recognition(script, asset, combined)
        assert not voice_content_observed(need, asset)
    else:
        observed = apply_voice_content(need, asset, script, combined)
        assert words[0]['probability'] == .2
        assert observed.semantic.inferences[-1].annotations[0].confidence is None
        assert voice_content_observed(need, observed)
        assert not MaterialMatcher().match(need, (observed,)).matches  # No automatic generated Rights.
        licensed = observed.model_copy(update={'rights': RightsInfo(status=RightsStatus.KNOWN, license_name='Fixture',
            evidence=(RightsEvidence(kind='asset_license', reference='fixture://voice'),))})
        assert MaterialMatcher().match(need, (licensed,)).matches


def test_same_planning_turn_binds_requirements_and_queries_to_the_canonical_need():
    from easel.materials.domain import MaterialPlan
    from easel.materials.application.visual_contract import planning_contracts, requirements_cache_key
    need = visual_need()
    mode = {'visual_material_style': 'restrained daylight'}
    plan = MaterialPlan(plan_id='plan', creation_id='creation', attempt_id='attempt', needs=(need,))
    response = {need.need_id: {'clauses': [
        {'path': 'intent/description', 'text': need.intent.description, 'kind': 'required', 'preference_path': None},
        {'path': 'constraints/preferred_visual_details', 'text': 'low angle', 'kind': 'preference', 'preference_path': None}],
        'queries': ['two paper sheets', 'paper pages on desk', 'paper documents']}}
    identity, saved = planning_contracts(plan, mode, response)[0]
    assert identity == requirements_cache_key(saved['input'])
    assert saved['contract']['queries'][0] == 'two paper sheets'
    assert saved['input']['need']['constraints']['preferred_style'] == mode['visual_material_style']
    assert saved['contract']['clauses'][-1]['kind'] == 'preference'
    changed = deepcopy(response)
    changed[need.need_id]['clauses'][0]['text'] = 'one paper sheet'
    with pytest.raises(ValueError, match='引用不等于原文'):
        planning_contracts(plan, mode, changed)


@pytest.mark.parametrize('fault', [None, 'below_floor', 'dense_low', 'too_many', 'weak_average',
                                   'wrong_word', 'missing_word', 'extra_word', 'overlap'])
def test_sparse_voice_uncertainty_keeps_exact_text_time_and_rights_boundaries(fault):
    from easel.materials.application.voice_delivery import apply_voice_content, timing_from_recognition, voice_content_observed
    from easel.materials.application.matching import MaterialMatcher
    script = '每次整理重要的纸面记录' * 10
    need = MaterialNeed(need_id='voice', scope=NeedScope(type=NeedScopeType.GLOBAL, ref='film'),
        media_type=MediaType.AUDIO, role='voice', intent=NeedIntent(description='clear narration'),
        importance=NeedImportance.REQUIRED, modality_spec=VoiceNeedSpec(text_ref='artifacts/SCRIPT.md',
            text_sha256=hashlib.sha256(script.encode()).hexdigest(),
            identity=VoiceIdentityRef(source=VoiceIdentitySource.EXPLICIT_USER, reference='preset Mandarin')))
    asset = MaterialAsset(asset_id='voice', media_type=MediaType.AUDIO,
        file=FileInfo(path='materials/assets/voice/audio.mp3', sha256='a' * 64, size=1, mime='audio/mpeg'),
        source=CandidateSource(kind='generative', provider='minimax'), rights=RightsInfo(status=RightsStatus.UNKNOWN),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, duration_seconds=len(script) + 1., mime='audio/mpeg'))
    words = [{'text': c, 'start_seconds': float(i), 'end_seconds': i + .8,
              'probability': .282 if i == 0 else .97} for i, c in enumerate(script)]
    if fault == 'below_floor': words[0]['probability'] = .249
    elif fault == 'dense_low':
        words = words[:10]  # One word in a short text is not <=5%.
        script = script[:10]
    elif fault == 'too_many':
        for w in words[:4]: w['probability'] = .3  # Only 3.6%, but above the absolute cap.
    elif fault == 'weak_average':
        for w in words[1:]: w['probability'] = .8
    elif fault == 'wrong_word': words[0]['text'] = '美'
    elif fault == 'missing_word': words.pop()
    elif fault == 'extra_word': words[-1]['text'] += '啊'
    elif fault == 'overlap': words[1]['start_seconds'] = .1
    report = {'words': words, 'audio_sha256': asset.file.sha256,
              'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
              'need_sha256': hashlib.sha256(need.to_json().encode()).hexdigest()}
    original = deepcopy(report)
    if fault:
        with pytest.raises(ValueError): timing_from_recognition(script, asset, report)
    else:
        timing = timing_from_recognition(script, asset, report)
        assert timing['confidence_acceptance']['low_confidence_characters'] == 1
        observed = apply_voice_content(need, asset, script, report)
        assert observed.semantic.inferences[-1].annotations[0].confidence == .282
        assert voice_content_observed(need, observed)
        assert not MaterialMatcher().match(need, (observed,)).matches
        licensed = observed.model_copy(update={'rights': RightsInfo(status=RightsStatus.KNOWN, license_name='Fixture',
            evidence=(RightsEvidence(kind='asset_license', reference='fixture://voice'),))})
        assert MaterialMatcher().match(need, (licensed,)).matches
        unbound = observed.model_copy(update={'file': observed.file.model_copy(update={'sha256': 'b' * 64})})
        assert not voice_content_observed(need, unbound)
    assert report == original  # Scores, text and times are evidence, not editable gates.


@pytest.mark.parametrize('fault', [None, 'missing_visual', 'duplicate', 'unknown_need',
    'wrong_identity', 'wrong_context', 'missing_required', 'wrong_text', 'unknown_path', 'preference_promoted',
    'partial_preference', 'missing_quote'])
def test_real_failed_planning_sidecar_is_bound_without_changing_needs(fault):
    import json
    from pathlib import Path
    from easel.materials.domain import MaterialPlan
    from easel.materials.application.visual_contract import planning_contracts, normalize_planning_requirements, sources_for, requirements_cache_key
    fixture = Path(__file__).parent / 'fixtures/planning-material-contract-2026-10-06'
    raw_plan = (fixture / 'MATERIAL_PLAN.json').read_bytes()
    raw_response = (fixture / 'MATERIAL_REQUIREMENTS.json').read_bytes()
    assert hashlib.sha256(raw_plan).hexdigest() == '13085a5d247f4a7f128abdfdf813201016d070e96e08c5b43fa370067a3b1516'
    assert hashlib.sha256(raw_response).hexdigest() == 'c40e165d0c30d9177dcaa8fe08552e4d2b74b91dfde9b4a8ebe2c81e4c402f59'
    plan = MaterialPlan.model_validate_json(raw_plan)
    response = json.loads(raw_response)
    before = plan.model_dump(mode='json')
    if fault == 'missing_visual': response['visual_requirements'].pop(6)  # optional still mandatory in contract
    elif fault == 'duplicate': response['visual_requirements'].append(deepcopy(response['visual_requirements'][0]))
    elif fault == 'unknown_need': response['visual_requirements'][-1]['need_id'] = 'unknown'
    elif fault == 'wrong_identity': response['attempt_id'] = 'other-attempt'
    elif fault == 'wrong_context': response['context_refs']['production_brief_sha256'] = 'other'
    elif fault == 'missing_required': response['visual_requirements'][0]['clauses'].pop(0)
    elif fault == 'wrong_text': response['visual_requirements'][0]['clauses'][0]['text'] = response['visual_requirements'][0]['clauses'][0]['text'].replace('quiet desk', 'quiet disk')
    elif fault == 'unknown_path': response['visual_requirements'][0]['clauses'][0]['path'] = 'intent/unknown'
    elif fault == 'preference_promoted': response['visual_requirements'][0]['clauses'][-1]['kind'] = 'required'
    elif fault == 'partial_preference': response['visual_requirements'][0]['clauses'].append({
        'path': 'constraints/preferred_visual_details', 'text': 'warm', 'kind': 'preference', 'preference_path': ''})
    elif fault == 'missing_quote': response['visual_requirements'][2]['clauses'][0]['text'] = response['visual_requirements'][2]['clauses'][0]['text'].replace("'", '', 1)
    original = deepcopy(response)
    if fault:
        with pytest.raises(ValueError): planning_contracts(plan, {}, response)
    else:
        canonical = normalize_planning_requirements(plan, response)
        visual = [n for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}]
        assert set(canonical) == {n.need_id for n in visual}
        assert len(visual) == 7
        assert [n.importance.value for n in plan.needs] == ['required'] * 6 + ['optional', 'required', 'required', 'optional', 'optional']
        contracts = planning_contracts(plan, {}, response)
        assert contracts == planning_contracts(plan, {}, canonical)
        quoted = deepcopy(canonical)
        need_id = visual[2].need_id
        quoted[need_id]['clauses'][0]['text'] = quoted[need_id]['clauses'][0]['text'].replace('\u2018', "'").replace('\u2019', "'")
        with pytest.raises(ValueError, match='引用不等于原文'):
            planning_contracts(plan, {}, quoted)
        assert len(contracts) == 7
        for need, (key, saved) in zip(visual, contracts):
            assert key == requirements_cache_key(saved['input'])
            assert validate_compilation(saved['input'], saved['response']) == saved['contract']
            assert saved['input']['need']['importance'] == need.importance.value
            clauses = saved['contract']['clauses']
            for source in sources_for(need):
                assert ''.join(c['text'] for c in clauses if saved['input']['sources'][c['source']]['path'] == source['path']) == source['text']
            assert all(c['kind'] == 'preference' for c in clauses if c['text'] == need.constraints['preferred_visual_details'])
            assert not any(c['text'] in [need.constraints[k] for k in ('search_query_variants_primary', 'search_query_variants_alternate', 'search_query_variants_relaxed')] for c in clauses)
        # Canonical map never accepts audio IDs or extra wrappers.
        canonical[plan.needs[-1].need_id] = {'clauses': [], 'queries': []}
        with pytest.raises(ValueError): planning_contracts(plan, {}, canonical)
        from easel.materials.application.visual_contract import read_planning_requirements
        with pytest.raises(ValueError, match='对象键重复'):
            read_planning_requirements('{"visual":{},"visual":{}}')
    assert plan.model_dump(mode='json') == before
    assert response == original


@pytest.mark.parametrize('filename', ['MATERIAL_PLAN_OBJECT.json', 'MATERIAL_PLAN.json'])
def test_real_second_failure_rejects_misplaced_sound_without_mutating_needs(filename):
    from pathlib import Path
    from easel.materials.domain import MaterialPlan
    from easel.materials.application.compiler import NeedCompiler, NeedCompilationError
    from easel.materials.application.need_constraints import validate_modality_constraints
    from easel.materials.application.visual_contract import sources_for
    folder = Path(__file__).parent / 'fixtures/planning-modality-contract-2026-10-06'
    raw = (folder / filename).read_bytes()
    expected = {'MATERIAL_PLAN_OBJECT.json': 'b347ba43209dafb9b04b0420aae4317dac04cca1a5b27739f6f70b730b102b3e',
                'MATERIAL_PLAN.json': 'eacacfca9ed6a8d68f470f48c5812b0c32960cbb4bcce39174561f649432fd8f'}
    assert hashlib.sha256(raw).hexdigest() == expected[filename]
    plan = MaterialPlan.model_validate_json(raw)
    before = plan.to_json()
    assert len(plan.needs) == 10
    assert sum(n.importance is NeedImportance.REQUIRED for n in plan.needs) == 9
    with pytest.raises(ValueError, match='constraints.voice_'):
        validate_modality_constraints(plan.needs)
    for need in plan.needs:
        if filename.endswith('OBJECT.json') and isinstance(need.modality_spec, VoiceNeedSpec):
            intent = NeedCompiler().compile(need)
            assert not {'voice_delivery', 'voice_pace_ratio', 'voice_pitch_semitones', 'voice_tone'}.intersection(intent.filters)
        else:
            with pytest.raises(NeedCompilationError, match=need.need_id):
                NeedCompiler().compile(need)
        if need.media_type in {MediaType.IMAGE, MediaType.VIDEO}:
            with pytest.raises(ValueError, match=need.need_id):
                sources_for(need)
    assert plan.to_json() == before
