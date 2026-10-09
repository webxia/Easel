"""25 explicit risk rows. Run this file explicitly; default pytest is unaffected.

Original historical fixtures are immutable. Every variant below is test-only.
Existing high-value assertions are reused rather than copied into new tests.
"""
from __future__ import annotations
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import pytest
from pydantic import ValidationError
from PIL import Image
from tests import test_material_control_contracts as control
from tests import test_creation_preparation as previous
from tests.test_creation_preparation import prep_env, web, prep, creation, handoff, service
from easel.materials.domain import (
    MaterialPlan, MaterialNeed, NeedIntent, NeedScope, NeedScopeType, NeedImportance,
    MediaType, ImageNeedSpec, VideoNeedSpec, VoiceNeedSpec, VoiceIdentityRef,
    VoiceIdentitySource, BgmNeedSpec, SfxNeedSpec,
)
from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.visual_contract import (
    planning_contracts, normalize_planning_requirements, sources_for,
    compilation_input, requirements_cache_key, validate_compilation, batches, QUERY_FIELDS,
)
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.store import AttemptMaterialStore
from easel.integrations.material_layer import PlanningIntegration
from easel.creator_proposal import parse_video_plan

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
FIRST = FIXTURES / 'planning-material-contract-2026-10-06'
SECOND = FIXTURES / 'planning-modality-contract-2026-10-06'
THIRD = FIXTURES / 'planning-truth-contract-2026-10-06'


def historical(folder):
    return MaterialPlan.model_validate_json((folder / 'MATERIAL_PLAN.json').read_bytes()), json.loads((folder / 'MATERIAL_REQUIREMENTS.json').read_text())


def refs():
    return {k: c * 64 for k, c in zip(('content_core_sha256', 'truth_packet_sha256',
        'creator_context_sha256', 'production_brief_sha256', 'creative_mode_sha256'), 'abcde')}


def visual(kind='image', id='image', importance=NeedImportance.REQUIRED):
    return MaterialNeed(need_id=id, scope=NeedScope(type=NeedScopeType.SCENE, ref=id),
        media_type=MediaType(kind), role='visual', importance=importance,
        intent=NeedIntent(description='两张纸，放在桌上；没有标志。', function='呈现停顿与选择。'),
        constraints={'preferred_visual_details': '低机位'},
        modality_spec=ImageNeedSpec(visual_style='自然光') if kind == 'image' else VideoNeedSpec())


def audio(kind):
    spec = {'voice': VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource.DIRECTOR_INTENT,
                           reference='测试预置声音，不是实际调用')),
            'bgm': BgmNeedSpec(mood='calm', instruments=('piano',)),
            'sfx': SfxNeedSpec(event_description='杯水轻晃')}[kind]
    return MaterialNeed(need_id=kind, scope=NeedScope(type=NeedScopeType.EVENT if kind == 'sfx' else NeedScopeType.GLOBAL,
        ref=kind), media_type=MediaType.AUDIO, role=kind, importance=NeedImportance.REQUIRED,
        intent=NeedIntent(description='隔离测试声音 ' + kind), modality_spec=spec,
        constraints={'voice_delivery': {'pace_ratio': .9, 'pitch_semitones': 0, 'tone': 'neutral'}} if kind == 'voice' else {})


def plan_with(needs):
    return MaterialPlan(plan_id='plan-matrix', creation_id='matrix', attempt_id='matrix', context_refs=refs(), needs=tuple(needs))


def sidecar(plan):
    # Test fixture classifications are explicit, not an inference or production
    # repair. Each whole source is kept literal; semantics are tested separately.
    return {n.need_id: {'clauses': [{'path': s['path'], 'text': s['text'],
        'kind': 'preference' if s['preference'] else 'postproduction' if s['path'] == 'intent/function' else 'required',
        'preference_path': None} for s in sources_for(n)],
        'queries': ['paper on desk', 'two sheets table', 'paper documents room']}
        for n in plan.needs if n.media_type in {MediaType.IMAGE, MediaType.VIDEO}}


def compare(plan, trace):
    before = plan.to_json()
    contracts = planning_contracts(plan, {}, sidecar(plan))
    for n in plan.needs:
        NeedCompiler().compile(n)
    assert len(contracts) == sum(n.media_type in {MediaType.IMAGE, MediaType.VIDEO} for n in plan.needs)
    assert plan.to_json() == before
    trace.note('need types / importance', [(n.need_id, n.media_type.value, n.importance.value) for n in plan.needs])
    trace.note('visual contracts', len(contracts))
    return contracts


def test_01_canonical_wrapper(trace):
    trace.define('历史 wrapper 与 canonical 合同等价；7视觉与4声音完整保留', '第一轮原字节 fixture；正式 visual sidecar 合同')
    control.test_real_failed_planning_sidecar_is_bound_without_changing_needs(None)
    plan, raw = historical(FIRST)
    canonical = normalize_planning_requirements(plan, raw)
    trace.note('contracts / all needs', {'visual': len(planning_contracts(plan, {}, canonical)), 'all': len(plan.needs)})


def test_02_missing_visual_clause(tmp_path, monkeypatch, trace):
    trace.define('required 原文漏项与 optional 视觉 ID 漏项均拒绝', '全部视觉 ID 与原文完整覆盖，不降低 required')
    for variant in ('missing_visual', 'missing_required', 'partial_preference'):
        control.test_real_failed_planning_sidecar_is_bound_without_changing_needs(variant)
        trace.note(variant, 'rejected; source unchanged')
    p, raw = historical(FIRST)
    missing = deepcopy(raw)
    missing['visual_requirements'].pop(0)
    with pytest.raises(ValueError): planning_contracts(p, {}, missing)
    trace.note('whole required visual ID missing', 'rejected')
    p, attempt, _ = third_workspace(tmp_path, monkeypatch)
    optional = p.model_copy(update={'needs': tuple(n.model_copy(update={'importance': NeedImportance.OPTIONAL}) for n in p.needs)})
    (tmp_path / 'planning/MATERIAL_PLAN.json').write_text(optional.model_dump_json())
    repairs = []
    monkeypatch.setattr(web, 'run_agent_sync', lambda *_a, **_k: repairs.append('fixture repair does not alter invalid Plan'))
    with pytest.raises(prep.PreparationError, match='at least one required Need'):
        web._material_planning_executor(attempt, {'context_refs': p.context_refs})
    assert len(repairs) == 1
    trace.note('no required Need in Plan', 'rejected after one bounded fixture repair')


def test_03_duplicate_unknown(trace):
    trace.define('重复/未知 Need ID、重复 JSON 键、重复 Plan ID 拒绝', 'MaterialPlan.unique_need_ids；sidecar exact ID set')
    for variant in ('duplicate', 'unknown_need'):
        control.test_real_failed_planning_sidecar_is_bound_without_changing_needs(variant)
        trace.note(variant, 'rejected')
    from easel.materials.application.visual_contract import read_planning_requirements
    with pytest.raises(ValueError, match='对象键重复'):
        read_planning_requirements('{"a":{},"a":{}}')
    n = visual()
    with pytest.raises(ValidationError): plan_with([n, n])
    trace.note('duplicate JSON / Plan ID', 'rejected')


def test_04_source_binding(trace):
    trace.define('错误 Attempt/冻结 refs/source path 拒绝', 'wrapper identity equality；literal source binding')
    for variant in ('wrong_identity', 'wrong_context', 'unknown_path'):
        control.test_real_failed_planning_sidecar_is_bound_without_changing_needs(variant)
        trace.note(variant, 'rejected')


def test_05_unicode_literal(trace):
    trace.define('中文标点逐字绑定；兼容具名引号漂移不允许真实改词或漏引号', '第一轮 wrapper 单向等长兼容；canonical literal spans')
    for variant in (None, 'wrong_text', 'missing_quote'):
        control.test_real_failed_planning_sidecar_is_bound_without_changing_needs(variant)
    n = visual().model_copy(update={'intent': NeedIntent(description='窗外“光”落下，杯中水面；静止。🙂')})
    p = plan_with([n]); result = compare(p, trace)
    assert result[0][1]['contract']['clauses'][0]['text'] == n.intent.description
    changed = sidecar(p); changed[n.need_id]['clauses'][0]['text'] = n.intent.description.replace('“', '"')
    with pytest.raises(ValueError, match='原文'): planning_contracts(p, {}, changed)
    trace.note('canonical punctuation mutation', 'rejected')


def test_06_path_alias_null(trace):
    trace.define('已定义 wrapper path/空引用适配；canonical 非法 alias、空/未知引用拒绝', 'normalize_planning_requirements 的具名兼容范围')
    p, raw = historical(FIRST); canonical = normalize_planning_requirements(p, raw)
    assert all(c['preference_path'] is None or c['preference_path'] for row in canonical.values() for c in row['clauses'])
    for field, value in [('path', 'modality_spec/visual_style'), ('preference_path', ''), ('preference_path', 'unknown')]:
        changed = deepcopy(canonical)
        row = next(c for v in changed.values() for c in v['clauses'] if c['path'] == 'modality/visual_style')
        row[field] = value
        with pytest.raises(ValueError): planning_contracts(p, {}, changed)
        trace.note(field + ':' + value, 'rejected canonical variant')


def test_07_visual_only(trace):
    trace.define('纯视觉 Plan 可编译，原 Need 不变', 'MaterialPlan / NeedCompiler / planning_contracts')
    compare(plan_with([visual()]), trace)


def test_08_visual_voice(trace):
    trace.define('visual + Voice 合法；Voice 参数不进入检索 filter 或 visual sidecar', 'canonical voice_delivery；模态职责')
    p = plan_with([visual(), audio('voice')]); compare(p, trace)
    assert 'voice_delivery' not in NeedCompiler().compile(p.needs[1]).filters


def test_09_visual_bgm(trace):
    trace.define('visual + BGM 合法；BGM 保留自身偏好及 no-vocals 检索语义', 'BgmNeedSpec / NeedCompiler')
    p = plan_with([visual(), audio('bgm')]); compare(p, trace)
    assert 'vocals' in NeedCompiler().compile(p.needs[1]).negative_terms


def test_10_mixed_modalities(trace):
    trace.define('image/video/Voice/BGM/SFX 与 required/optional 完整保留；audio 不进 canonical visual map', 'Material V1.3 模态边界；optional 不删除')
    p = plan_with([visual(), visual('video', 'video', NeedImportance.OPTIONAL), audio('voice'), audio('bgm'), audio('sfx')])
    compare(p, trace)
    bad = sidecar(p); bad['voice'] = deepcopy(bad['image'])
    with pytest.raises(ValueError): planning_contracts(p, {}, bad)
    trace.note('audio ID in canonical visual map', 'rejected')


def test_11_clause_kinds(trace):
    trace.define('四类职责分离；明确源动作不得交后期；unresolved 不提交观察', 'visual_contract.validate_compilation / batches')
    p = plan_with([visual()]); raw = sidecar(p)
    compiled = planning_contracts(p, {}, raw)[0][1]['contract']
    assert {c['kind'] for c in compiled['clauses']} == {'required', 'preference', 'postproduction'}
    unresolved = deepcopy(raw); unresolved['image']['clauses'][-1]['kind'] = 'unresolved'
    pending = planning_contracts(p, {}, unresolved)[0][1]['contract']
    with pytest.raises(ValueError, match='歧义'): batches({'frames': [{'index': 0}]}, pending)
    dynamic = p.needs[0].model_copy(update={'constraints': {**p.needs[0].constraints, 'requires_dynamic_action': True}})
    with pytest.raises(ValueError, match='必要源动作'): planning_contracts(plan_with([dynamic]), {}, sidecar(plan_with([dynamic])))
    control.test_real_failed_planning_sidecar_is_bound_without_changing_needs('preference_promoted')
    trace.note('explicit preference promoted to required', 'rejected')
    trace.note('unresolved / dynamic action', 'blocked before observation')


from tests.test_material_integration import material_integration_env


def test_12_query_metadata(material_integration_env, tmp_path, monkeypatch, trace):
    trace.define('查询元数据不进入视觉原文；已定义查询对象不进入硬 filters；未知 provider/ranking 协议单列', 'QUERY_FIELDS / canonical retrieval metadata contract')
    constraints = {'search_query_en': 'paper table', 'search_query_variants_en': {
        'primary': 'paper on desk', 'alternate': 'two pages table', 'relaxed': 'paper documents'},
        'search_query_variants_primary': 'paper daylight', 'search_query_variants_alternate': 'pages room',
        'search_query_variants_relaxed': 'documents indoors', 'required_source_kind': 'stock', 'usage': 'internal'}
    n = visual().model_copy(update={'constraints': {**visual().constraints, **constraints}})
    assert not any(s['path'].split('/')[-1] in QUERY_FIELDS | {'required_source_kind', 'usage'} for s in sources_for(n))
    filters = dict(NeedCompiler().compile(n).filters)
    trace.note('retrieval filters', filters)
    assert not QUERY_FIELDS & set(filters)
    from tests.test_model_output_contracts import test_query_metadata_is_discovery_only_and_legacy_priority_is_explicit
    test_query_metadata_is_discovery_only_and_legacy_priority_is_explicit()
    from tests.test_model_output_contracts import test_query_as_filter_cache_is_not_claimed_and_valid_supply_reuses
    test_query_as_filter_cache_is_not_claimed_and_valid_supply_reuses(material_integration_env, tmp_path, monkeypatch)
    trace.note('actual source receipt reuse', 'old query-as-filter receipt not selected; one native Supply search; valid new receipt reuses with zero extra Provider calls')
    trace.note('legacy query compatibility', 'discovery only; priority, invalid values and final sorting checked')
    raw = n.model_dump(mode='json'); raw['provider'] = 'pexels'; raw['ranking'] = 1
    with pytest.raises(ValidationError) as invalid:
        MaterialNeed.model_validate_json(json.dumps(raw))
    assert {e['loc'][0] for e in invalid.value.errors()} == {'provider', 'ranking'}
    trace.note('top-level provider/ranking', 'rejected; structured unknown constraints rejected')
    for key in ('provider_metadata', 'ranking_metadata'):
        candidate = n.model_copy(update={'constraints': {**n.constraints, key: {'source': 'fixture'}}})
        with pytest.raises(ValueError): NeedCompiler().compile(candidate)


def test_13_mode_defaults(tmp_path, monkeypatch, trace):
    trace.define('仅视觉/仅声音/混合 Mode 的默认值在真实 persist 后按模态保留，与 producer cache 一致', 'PlanningIntegration.persist 的冻结 Mode 绑定')
    from easel.integrations import material_layer
    monkeypatch.setattr(creation, 'get_creation', lambda *_: {})
    monkeypatch.setattr(material_layer, '_update_attempt', lambda a, **values: {**a, **values})
    for i, mode in enumerate([{'visual_material_style': '测试自然光'},
         {'voice_delivery': {'pace_ratio': .8, 'pitch_semitones': -1, 'tone': 'neutral'}},
         {'visual_material_style': '测试自然光', 'voice_delivery': {'pace_ratio': .8, 'pitch_semitones': -1, 'tone': 'neutral'}}]):
        monkeypatch.setattr(handoff, 'load_frozen_creative_mode', lambda *_: (mode, refs()['creative_mode_sha256']))
        root = tmp_path / str(i); (root / 'handoff').mkdir(parents=True)
        (root / 'handoff/truth-packet.json').write_text(json.dumps({'schema': 'easel-truth-packet@2', 'claims': [], 'personal_facts': []}))
        n = visual().model_copy(update={'modality_spec': ImageNeedSpec(), 'constraints': {}})
        v = audio('voice').model_copy(update={'constraints': {}})
        p = plan_with([n, v, audio('bgm'), audio('sfx')])
        result = PlanningIntegration().persist({'creation_id': p.creation_id, 'attempt_id': p.attempt_id,
            'workspace': {'path': str(root)}}, p, treatment='测试', script='假设停下来。', scenes='测试')
        needs = result['plan'].needs
        assert bool(needs[0].constraints.get('preferred_style')) == bool(mode.get('visual_material_style'))
        assert bool(needs[1].constraints.get('voice_delivery')) == bool(mode.get('voice_delivery'))
        assert not any('voice_delivery' in x.constraints for x in (needs[0], needs[2], needs[3]))
        assert not any('preferred_style' in x.constraints for x in needs[1:])
        producer = planning_contracts(p, mode, sidecar(p))[0][0]
        consumer = requirements_cache_key(compilation_input(needs[0], p.context_refs, mode))
        assert producer == consumer
        trace.note('mode ' + str(i), {'need_ids': [x.need_id for x in needs], 'producer_consumer_key_equal': True})


def test_14_cache_consumer(tmp_path, monkeypatch, trace):
    trace.define('同轮合同零额外分类；legacy 重验可用；坏新 cache 不绕过', '第一轮真实产物 producer→实际 observation consumer')
    for state in ('current', 'legacy', 'corrupt_current'):
        with monkeypatch.context() as scoped:
            previous.test_real_planning_contract_reaches_visual_consumer_without_reclassification(tmp_path / state, scoped, state)
        trace.note(state, '7 visual consumer checked; corrupt new cache rejected')


def test_15_revision_identity(tmp_path, monkeypatch, trace):
    trace.define('相关 Need/refs/Mode 输入变化使 cache 与正式 Plan revision 失效；不强制无关局部缓存失效', 'compilation_input / requirements_cache_key / plan_revision')
    p = plan_with([visual()]); n = p.needs[0]
    baseline = requirements_cache_key(compilation_input(n, p.context_refs, {}))
    changed_need = n.model_copy(update={'intent': NeedIntent(description='三张纸放在桌上。')})
    changed_refs = {**p.context_refs, 'production_brief_sha256': 'f' * 64}
    for label, need, bindings, mode in [('Need', changed_need, p.context_refs, {}),
        ('refs', n, changed_refs, {}), ('Mode', n, p.context_refs, {'visual_material_style': '别的风格'})]:
        changed = requirements_cache_key(compilation_input(need, bindings, mode))
        assert changed != baseline
        trace.note(label, 'new cache identity; old key not selected')
    old_revision = MaterialReadinessCalculator.plan_revision(p)
    policy_plan = p.model_copy(update={'policy': {'strategy': 'changed'}})
    assert MaterialReadinessCalculator.plan_revision(policy_plan) != old_revision
    assert requirements_cache_key(compilation_input(n, policy_plan.context_refs, {})) == baseline
    from easel.materials.application.visual_observation import need_identity
    assert need_identity(changed_need) != need_identity(n)
    trace.note('policy-only revision', 'formal revision changes; unchanged local source contract may reuse')
    from easel.integrations import material_layer
    from easel.integrations.material_layer import MaterialIntegrationError
    monkeypatch.setattr(creation, 'get_creation', lambda *_: {})
    monkeypatch.setattr(material_layer, '_update_attempt', lambda a, **values: {**a, **values})
    monkeypatch.setattr(handoff, 'load_frozen_creative_mode', lambda *_: ({}, p.context_refs['creative_mode_sha256']))
    (tmp_path / 'handoff').mkdir()
    (tmp_path / 'handoff/truth-packet.json').write_text(json.dumps({'schema': 'easel-truth-packet@2', 'claims': [], 'personal_facts': []}))
    result = PlanningIntegration().persist({'creation_id': p.creation_id, 'attempt_id': p.attempt_id,
        'workspace': {'path': str(tmp_path)}}, p, treatment='测试', script='假设停下来。', scenes='测试')
    store = AttemptMaterialStore(tmp_path)
    store.write_plan(policy_plan)
    with pytest.raises(MaterialIntegrationError): PlanningIntegration().load(result['attempt'])
    store.write_plan(result['plan'])
    (tmp_path / 'planning/SCRIPT.md').write_text('假设改变旁白。')
    with pytest.raises(MaterialIntegrationError): PlanningIntegration().load(result['attempt'])
    trace.note('actual persisted Planning load', 'changed Plan revision and changed SCRIPT bytes both rejected')


def test_16_schema_modality(trace):
    trace.define('未知 modality、类型错配与额外 schema 包装拒绝', 'MaterialPlan / MaterialNeed canonical schema')
    n = visual().model_dump(mode='json')
    for spec in ({'kind': 'unknown'}, {'kind': 'voice'}):
        candidate = {**n, 'modality_spec': spec}
        with pytest.raises(ValidationError) as invalid:
            MaterialNeed.model_validate_json(json.dumps(candidate))
        assert any(e['type'] in {'union_tag_invalid', 'value_error'} for e in invalid.value.errors())
    p = plan_with([visual()]).model_dump(mode='json')
    with pytest.raises(ValidationError) as invalid:
        MaterialPlan.model_validate_json(json.dumps({**p, 'schema': 'invented'}))
    assert [(e['loc'], e['type']) for e in invalid.value.errors()] == [(('schema',), 'extra_forbidden')]
    with pytest.raises(ValidationError): NeedIntent(description='visual', source_ref='invented')
    trace.note('unknown / mismatch / wrapper', 'all rejected')


def test_17_historical_voice_object(trace):
    trace.define('第二轮真实跨模态对象提前拒绝，原件不变；合法 Voice 独立编译', '第二轮 object 原字节及 canonical voice_delivery')
    control.test_real_second_failure_rejects_misplaced_sound_without_mutating_needs('MATERIAL_PLAN_OBJECT.json')
    trace.note('historical object plan', 'rejected before visual contract; canonical Voice accepted')


def test_18_historical_voice_alias(trace):
    trace.define('第二轮真实扁平别名全模态拒绝，原件不变', '第二轮 final 原字节及 VOICE_ALIASES')
    control.test_real_second_failure_rejects_misplaced_sound_without_mutating_needs('MATERIAL_PLAN.json')
    trace.note('historical alias plan', 'rejected before consumer')


def test_19_voice_script_binding(tmp_path, monkeypatch, trace):
    trace.define('Voice 文稿引用/摘要必须配对；persist 绑定当前 SCRIPT、保持声音身份', 'VoiceNeedSpec pair validator / PlanningIntegration.persist')
    for fields in ({'text_ref': 'planning/SCRIPT.md'}, {'text_sha256': 'a' * 64}):
        with pytest.raises(ValidationError): VoiceNeedSpec(**fields)
    raw = (SECOND / 'MATERIAL_PLAN_INITIAL.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '5de346684687fd007b0ea7ec4d4c5c41d8dc8adfe63834e4b70420e91c6db096'
    with pytest.raises(ValidationError) as invalid:
        MaterialPlan.model_validate_json(raw)
    assert any('provided together' in e['msg'] for e in invalid.value.errors())
    trace.note('second-run initial Planning archived JSON (serialized representation)', 'Voice text_ref without text_sha256 rejected by actual JSON Domain validator')
    from easel.integrations import material_layer
    monkeypatch.setattr(creation, 'get_creation', lambda *_: {})
    monkeypatch.setattr(material_layer, '_update_attempt', lambda a, **values: {**a, **values})
    monkeypatch.setattr(handoff, 'load_frozen_creative_mode', lambda *_: ({}, refs()['creative_mode_sha256']))
    (tmp_path / 'handoff').mkdir()
    (tmp_path / 'handoff/truth-packet.json').write_text(json.dumps({'schema': 'easel-truth-packet@2', 'claims': [], 'personal_facts': []}))
    p = plan_with([audio('voice')]); script = '假设停下来。\r\n再观察一下。'
    result = PlanningIntegration().persist({'creation_id': p.creation_id, 'attempt_id': p.attempt_id,
        'workspace': {'path': str(tmp_path)}}, p, treatment='测试', script=script, scenes='测试')
    spec = result['plan'].needs[0].modality_spec
    assert spec.identity == p.needs[0].modality_spec.identity
    assert spec.text_ref == 'planning/SCRIPT.md' and spec.text_sha256 == hashlib.sha256(script.encode()).hexdigest()
    assert PlanningIntegration().load(result['attempt'])['script'] == script
    trace.note('frozen Voice binding', spec.model_dump(mode='json'))


def third_workspace(tmp_path, monkeypatch, *, managed=False):
    manifest = json.loads((THIRD / 'manifest.json').read_text())
    for name, row in manifest.items(): assert hashlib.sha256((THIRD / name).read_bytes()).hexdigest() == row['sha256']
    p, _ = historical(THIRD)
    directory = tmp_path / 'planning'; directory.mkdir(parents=True)
    for name in ('MATERIAL_PLAN.json', 'MATERIAL_REQUIREMENTS.json', 'SCRIPT.md', 'SCENES.md', 'TREATMENT.md'):
        (directory / name).write_bytes((THIRD / name).read_bytes())
    (tmp_path / 'handoff').mkdir()
    (tmp_path / 'handoff/truth-packet.json').write_bytes((THIRD / 'truth-packet.json').read_bytes())
    confirmed = json.loads((THIRD / 'confirmed-video-plan.json').read_text())
    monkeypatch.setattr(web, 'get_creation', lambda *_: {'delivery': {'video_plan': confirmed,
        **({'schema': 'easel-creation-delivery@1'} if managed else {})}})
    monkeypatch.setattr(handoff, 'load_frozen_creative_mode', lambda *_: ({}, p.context_refs['creative_mode_sha256']))
    attempt = {'creation_id': p.creation_id, 'attempt_id': p.attempt_id, 'workspace': {'path': str(tmp_path)}}
    return p, attempt, confirmed


def test_20_missing_sidecar(tmp_path, monkeypatch, trace):
    trace.define('新Planning缺sidecar单次修复，耗尽停止，不进入Supply', 'approved G2 product contract; old frozen compatibility covered by load')
    p, attempt, _ = third_workspace(tmp_path, monkeypatch)
    (tmp_path / 'planning/MATERIAL_REQUIREMENTS.json').unlink()
    calls = []
    monkeypatch.setattr(web, 'run_agent_sync', lambda *_a, **_k: calls.append('repair_without_sidecar') or 'fixture')
    with pytest.raises(prep.PreparationError):
        web._material_planning_executor(attempt, {'context_refs': p.context_refs})
    assert calls == ['repair_without_sidecar']
    with pytest.raises(prep.PreparationError):
        web._material_planning_executor(attempt, {'context_refs': p.context_refs})
    assert len(calls) == 1
    trace.note('missing sidecar', 'one durable repair; re-entry stops without another call; no supply')


def test_21_third_proposal_parse(prep_env, trace):
    trace.define('合法容器保留逐字正文，历史混排在容器内外均拒绝，合法台词不误拒', 'approved F1 @2 container and unchanged confirmed legacy contract')
    from tests.test_model_output_contracts import test_proposal_container_preserves_literal_and_rejects_real_instruction_mix
    test_proposal_container_preserves_literal_and_rejects_real_instruction_mix()
    from tests.test_model_output_contracts import test_legacy_proposal_requires_revision_only_before_confirmation
    test_legacy_proposal_requires_revision_only_before_confirmation(prep_env)
    trace.note('proposal controls', 'voice/screen/no-copy/Unicode/CRLF and historical instruction variants checked')


def test_22_third_truth_freeze(tmp_path, monkeypatch, trace):
    trace.define('原 Truth 报告仅绑定原脚本，冻结稿需重写时停止；不冒充人工放行', '第三轮真实 SHA-bound report / confirmed-plan protection')
    p, attempt, _ = third_workspace(tmp_path, monkeypatch, managed=True)
    report_name = next(name for name in json.loads((THIRD / 'manifest.json').read_text()) if name.startswith('script-assessment'))
    report = json.loads((THIRD / report_name).read_text())
    calls = []
    def gateway(message, *_args, **_kwargs):
        assert message.startswith('〔Easel Script 系统审阅〕')
        target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
        target.write_bytes((THIRD / report_name).read_bytes()); calls.append('truth_fixture_replay')
        return 'fixture completed'
    monkeypatch.setattr(web, 'run_agent_sync', gateway)
    with pytest.raises(prep.PreparationError, match='已确认文案存在待核实事实'):
        web._material_planning_executor(attempt, {'context_refs': p.context_refs})
    assert calls == ['truth_fixture_replay']
    from easel.integrations.script_truth import create_script_claim_ledger, apply_system_script_review, ScriptTruthError
    script = (THIRD / 'SCRIPT.md').read_text(); truth = tmp_path / 'handoff/truth-packet.json'
    with pytest.raises(ScriptTruthError): apply_system_script_review(script + '变更。', truth, create_script_claim_ledger(script + '变更。', truth), report)
    trace.note('actual stop', {'rewrite_required': sum(x['kind'] == 'rewrite_required' for x in report['decisions']),
        'unresolved': sum(x['kind'] == 'unresolved' for x in report['decisions']), 'supply_calls': 0, 'fixture_gateway_calls': len(calls)})


def test_23_frozen_prose(tmp_path, trace):
    trace.define('未冻结错误草稿可归档恢复；冻结后任何真实改字必须拒绝，不覆盖现场', '_restore_confirmed_planning frozen flag and atomic archive')
    directory = tmp_path / 'planning'; directory.mkdir()
    path = directory / 'SCRIPT.md'; path.write_text('未确认错误草稿')
    canonical = {'SCRIPT.md': '确认旁白。'}
    web._restore_confirmed_planning(directory, canonical, frozen=False)
    assert path.read_text() == canonical['SCRIPT.md']
    assert len(list((directory / 'rejected-confirmed-drafts').iterdir())) == 1
    web._restore_confirmed_planning(directory, canonical, frozen=True)
    path.write_text('冻结后改字')
    with pytest.raises(prep.PreparationError, match='已冻结规划'):
        web._restore_confirmed_planning(directory, canonical, frozen=True)
    assert path.read_text() == '冻结后改字'
    trace.note('unfrozen restore / frozen tamper', 'archived then restored / rejected without overwrite')


def test_24_owner_supply_observation(prep_env, tmp_path, monkeypatch, trace, planning_version=2):
    trace.define('正常新测试 Creation 经真实确认、Owner、Preparation、Planning、persist、Supply、首轮 observation；无 Authoring', '实际 web delivery dispatcher 与 MaterialProductOrchestrator；仅外部结果为 fixture')
    from easel.creation_delivery import advance_creation, next_operation, set_material_endpoint
    from easel.integrations.material_supply import ProductMaterialSupply
    from easel.materials.providers import LocalProvider
    from easel.materials.application.acquisition import MaterialAcquirer
    monkeypatch.setattr(web._material_planning_executor, 'planning_contract_version', planning_version)
    source = tmp_path / 'local-fixture'; source.mkdir()
    Image.new('RGB', (32, 48), color='white').save(source / 'paper.png')
    monkeypatch.setenv('EASEL_MATERIAL_LOCAL_ROOTS', str(source))
    work = creation.create_creation('隔离矩阵：暂停一下，先看问题。', profile='个人经营实践',
        creative_mode='clear_memo_video', route='hypit_video', origin={'type': 'chat', 'session_hash': 'd' * 64})
    creation.begin_video_proposal(work['id'], 'proposal-fixture')
    creation.save_video_proposal(work['id'], 'proposal-fixture', previous.VIDEO_PROPOSAL.replace('先看问题，再做决定。', '先看问题，\r\n再做决定。'))
    selected = creation.get_creation(work['id'])['chat_workflow']['video_plan']
    set_material_endpoint(work['id'])
    creation.confirm_chat_proposal(work['id'], 'confirm-fixture', video_plan_sha256=selected['sha256'],
        delivery_proposal='隔离测试确认，无真实采购', proposal_sha256=hashlib.sha256('隔离测试确认，无真实采购'.encode()).hexdigest(),
        production_specs=selected['specs'])
    gateway_calls, supply_calls, observation_calls, operations = [], [], [], []
    provider_searches, acquisitions = [], []
    native_search, native_acquire = LocalProvider.search, MaterialAcquirer.acquire
    def search(self, intent, continuation=None):
        provider_searches.append(intent.model_dump(mode='json'))
        assert not QUERY_FIELDS.intersection(intent.filters)
        assert intent.semantic_queries[0] == 'paper'
        return native_search(self, intent, continuation)
    def acquire(self, candidate):
        acquisitions.append(candidate.candidate_id)
        return native_acquire(self, candidate)
    monkeypatch.setattr(LocalProvider, 'search', search)
    monkeypatch.setattr(MaterialAcquirer, 'acquire', acquire)
    def gateway(message, *_args, **_kwargs):
        if message.startswith('〔Easel Semantic Planning V3〕'):
            gateway_calls.append('planning')
            target = Path(re.search(r'只写 (.+\.json)', message)[1])
            draft = {'schema':'semantic-planning-draft@1','needs':[{
                'scope':{'type':'scene','ref':'scene-1'}, 'role':'visual','importance':'required',
                'intent':{'description':'white paper'}, 'modality_spec':{'kind':'image'},
                'queries':['paper','white paper','paper desk']}]}
            target.write_text(json.dumps(draft))
        elif message.startswith('〔Easel Planning V3 单元分类〕'):
            gateway_calls.append('classification')
            data = json.loads(message.splitlines()[-1])
            assert [u['text'] for u in data['units']] == ['white paper']
            target = Path(re.search(r'只写 (.+\.json)', message)[1])
            response=semantic._authority_fixed_response(data,kinds=['required']) if 'controls' in data else {
                'classifications':[{'id':data['units'][0]['id'],'kind':'required','preference_source':None}]}
            target.write_text(json.dumps(response))
        elif message.startswith('〔Easel Material Creative Planning V1〕'):
            gateway_calls.append('planning')
            root = Path(re.search(r'^Attempt workspace: (.+)$', message, re.M)[1])
            aid = re.search(r'^Attempt ID: (.+)$', message, re.M)[1]
            bindings = json.loads(re.search(r'^context_refs: (.+)$', message, re.M)[1])
            n = MaterialNeed(need_id='paper', scope=NeedScope(type=NeedScopeType.SCENE, ref='scene-1'),
                media_type=MediaType.IMAGE, role='visual', importance=NeedImportance.REQUIRED,
                intent=NeedIntent(description='white paper'), constraints={
                    'search_query_variants_primary': 'paper', 'search_query_variants_alternate': 'white paper',
                    'search_query_variants_relaxed': 'paper desk'})
            p = MaterialPlan(plan_id='plan-' + aid[-20:], creation_id=work['id'], attempt_id=aid,
                context_refs=bindings, needs=(n,))
            (root / 'planning/MATERIAL_PLAN.json').write_text(p.model_dump_json())
            (root / 'planning/MATERIAL_REQUIREMENTS.json').write_text(json.dumps(sidecar(p), ensure_ascii=False))
        elif message.startswith('〔Easel Script 系统审阅〕'):
            gateway_calls.append('truth')
            target = Path(re.search(r'只写 (.+\.json)，JSON 结构', message)[1])
            response = json.loads(message.split('（逐项替换判断，不增加字段）：\n', 1)[1].split('\n写入后停止。', 1)[0])
            for row in response['decisions']: row.update(kind='creative_expression', reason='隔离 fixture：不声称事实或亲历。')
            target.write_text(json.dumps(response, ensure_ascii=False))
        else:
            gateway_calls.append('preparation')
            current = creation.get_creation(work['id'])
            paths = prep.preparation_paths(work['id'], current['preparation']['operation_key'])
            previous.write_drafts(current, paths['draft'])
        return 'deterministic external fixture completed'
    monkeypatch.setattr(web, 'run_agent_sync', gateway)
    native_supply = ProductMaterialSupply.run
    def supply(self, plan, attempt, **kwargs):
        supply_calls.append(plan.plan_id)
        assert PlanningIntegration().load(attempt)['truth_ledger']['status'] == 'PASSED'
        return native_supply(self, plan, attempt, **kwargs)
    monkeypatch.setattr(ProductMaterialSupply, 'run', supply)
    def compact(_attempt, payload, _prompt, *, attachments=None):
        assert payload['protocol'] == 'material-compact-observation@4', 'same-turn contract must prevent reclassification'
        assert attachments
        observation_calls.append(payload['input_sha256'])
        return {'frame': payload['frame']['index'], 'observed': True, 'description': 'white test fixture pixels',
            'style': 'test fixture', 'logo': None, 'text': None,
            'checks': [{'id': c['id'], 'status': 'unknown', 'basis': 'fixture cannot establish material suitability'} for c in payload['clauses']],
            'preference_notes': 'no real semantic acceptance'}
    monkeypatch.setattr(web, '_material_compact_result', compact)
    async def execute(operation, current):
        operations.append(operation)
        assert operation in {'prepare', 'observe_material'}, 'test endpoint forbids later operations'
        await web._execute_creation_delivery(operation, current)
    for _ in range(4):
        selected_operation = next_operation(creation.get_creation(work['id']))
        operation = selected_operation[0] if selected_operation else None
        assert operation in {'prepare', 'observe_material'}, f'expected material boundary, got {operation}'
        assert asyncio.run(advance_creation(work['id'], execute))
        if observation_calls: break
    current = creation.get_creation(work['id']); attempt = current['hypit_attempts'][-1]
    current_attempt = creation.get_creation(work['id'])['hypit_attempts'][-1]
    assert current_attempt.get('planning_contract_version') == planning_version
    assert (Path(current_attempt['workspace']['path']) / 'planning/SCRIPT.md').read_bytes() == selected['script'].encode()
    saved_manifest = json.loads((Path(current_attempt['workspace']['path']) / 'planning/manifest.json').read_text())
    assert saved_manifest['schema'] == f'easel-material-planning@{planning_version}' and saved_manifest['requirements']['sha256']
    from easel.integrations.material_layer import MaterialIntegrationError
    planning_root = Path(current_attempt['workspace']['path']) / 'planning'
    req_path = planning_root / 'MATERIAL_REQUIREMENTS.json'
    original_req = req_path.read_bytes()
    from easel.materials.application.visual_observation import prepare_observation
    observed_store = AttemptMaterialStore(planning_root.parent)
    observed_plan = observed_store.read_plan()
    observed_asset = observed_store.read_asset(observed_store.read_bundle().assets[0].asset_id)
    observed_manifest, observed_attachments = prepare_observation(observed_plan.needs[0], observed_asset,
        observed_store.resolve_asset_locator(observed_asset.file.path))
    calls_before = len(observation_calls)
    web._observe_material_frames(current_attempt, observed_manifest, observed_attachments)
    assert len(observation_calls) == calls_before, 'valid finished report must reuse without model'
    for bad in (None, b'{}', original_req + b' '):
        if bad is None: req_path.unlink()
        else: req_path.write_bytes(bad)
        with pytest.raises(MaterialIntegrationError): PlanningIntegration().load(current_attempt)
        # Existing completed observation must not bypass the changed contract.
        current_work = creation.get_creation(work['id'])
        with pytest.raises((MaterialIntegrationError, prep.PreparationError)):
            asyncio.run(web._execute_creation_delivery('observe_material', current_work))
        with pytest.raises(MaterialIntegrationError):
            web._observe_material_frames(current_attempt, observed_manifest, observed_attachments)
        req_path.write_bytes(original_req)
    for change in ({'planning_contract_version': 1}, {'planning_contract_version': None},
                   *({'material_planning': {**current_attempt['material_planning'], key: value}}
                     for key, value in [('manifest_sha256', '0' * 64), ('status', 'DRAFT'),
                                        ('plan_id', 'another-plan'), ('plan_revision', '0' * 64)])):
        with pytest.raises(MaterialIntegrationError): PlanningIntegration().load({**current_attempt, **change})
    original_manifest = (planning_root / 'manifest.json').read_bytes()
    downgraded = {**saved_manifest, 'schema': 'easel-material-planning@1'}
    downgraded.pop('requirements')
    (planning_root / 'manifest.json').write_text(json.dumps(downgraded))
    stripped = deepcopy(current_attempt)
    stripped.pop('planning_contract_version')
    stripped['material_planning'].pop('contract_version')
    stripped['material_planning'].pop('manifest_sha256')
    with pytest.raises(MaterialIntegrationError): PlanningIntegration().load(stripped)
    with pytest.raises(MaterialIntegrationError):
        web._observe_material_frames(stripped, observed_manifest, observed_attachments)
    (planning_root / 'manifest.json').write_bytes(original_manifest)
    changed = observed_plan.needs[0].model_copy(update={'intent': NeedIntent(description='different paper')})
    bad_manifest, bad_attachments = prepare_observation(changed, observed_asset,
        observed_store.resolve_asset_locator(observed_asset.file.path))
    with pytest.raises(prep.PreparationError, match='不属于'):
        web._observe_material_frames(current_attempt, bad_manifest, bad_attachments)
    # Lost derived cache can be rebuilt from valid sidecar with zero model calls;
    # corrupted current records cannot fall back to the legacy key.
    store = AttemptMaterialStore(planning_root.parent)
    contract_key = next(iter(saved_manifest['requirements']['cache_keys'].values()))
    original_cache = store.read_recovery_record(contract_key)
    cache_path = store.materials_root / 'recoveries' / (contract_key + '.json')
    cache_path.unlink()
    PlanningIntegration().load(current_attempt)
    assert store.read_recovery_record(contract_key) == original_cache
    store.write_recovery_record(contract_key, {**original_cache, 'contract': {}})
    with pytest.raises(MaterialIntegrationError): PlanningIntegration().load(current_attempt)
    store.write_recovery_record(contract_key, original_cache)
    trace.note('v2 integrity and recovery', 'sidecar missing/tampered, downgrade and corrupt cache reject; missing cache rebuilds without model')
    trace.note('actual pipeline', {'operations': operations, 'gateway_fixture_calls': gateway_calls,
        'supply_calls': len(supply_calls), 'observation_calls': len(observation_calls),
        'planning': attempt.get('material_planning'), 'gate': attempt.get('material_gate', {}).get('status')})
    assert gateway_calls == (['preparation', 'planning', 'classification', 'truth'] if planning_version==3
                             else ['preparation', 'planning', 'truth'])
    assert supply_calls and observation_calls
    assert len(current['hypit_attempts']) == 1
    assert 'production_authoring' not in attempt and not attempt.get('outputs')
    assert attempt['material_gate']['status'] == 'MATERIAL_NOT_READY'
    searches_before, acquisitions_before = len(provider_searches), len(acquisitions)
    assert searches_before and acquisitions_before
    # Re-entry consumes persisted Planning and Supply, not another external call.
    awaitable = web._execute_creation_delivery('prepare', current)
    asyncio.run(awaitable)
    trace.note('completed prepare re-entry', {'supply_service_entries': len(supply_calls),
        'provider_searches_before_after': [searches_before, len(provider_searches)],
        'acquisitions_before_after': [acquisitions_before, len(acquisitions)],
        'gateway_fixture_calls': gateway_calls})
    trace.note('actual Provider query/filter boundary', provider_searches)
    assert gateway_calls == (['preparation', 'planning', 'classification', 'truth'] if planning_version==3
                             else ['preparation', 'planning', 'truth'])
    assert len(provider_searches) == searches_before and len(acquisitions) == acquisitions_before


def test_25_structure_reentry(prep_env, tmp_path, monkeypatch, trace):
    trace.define('pending/timeout/complete/failed 重入只恢复原请求；错误或草稿变化不新增额度', '第二轮持久单次结构修复；同 run 对账边界')
    for outcome in ('valid', 'invalid', 'pending_valid', 'timeout', 'failed'):
        (tmp_path / outcome).mkdir()
        with monkeypatch.context() as scoped:
            previous.test_planning_structure_repair_reentry_uses_one_durable_request(tmp_path / outcome, scoped, outcome)
        trace.note(outcome, 'same durable request observed twice; complete/failed do not redispatch')
    previous.test_gateway_submission_timeout_reconciles_same_run_without_resubmitting(prep_env)
    from tests.test_model_output_contracts import test_legacy_pending_planning_observes_original_run_before_validation
    test_legacy_pending_planning_observes_original_run_before_validation(prep_env, monkeypatch)
    from tests.test_model_output_contracts import test_valid_v1_checkpoint_resumes_but_bad_query_never_replans
    test_valid_v1_checkpoint_resumes_but_bad_query_never_replans(prep_env)
    trace.note('native durable Gateway adapter + Owner next_operation',
        'one agent submit; same-run waits; unrelated run/profile rejected; completed result reused; runtime released')


def test_26_semantic_owner_supply(prep_env, tmp_path, monkeypatch, trace):
    from tests.test_creation_preparation import web
    # Preserve the original @7 Supply/Observation fixture's exact contract.
    monkeypatch.setattr(web, 'PLANNING_COMPILER_POLICY', 'semantic-planning-compiler@7')
    trace.define('v3真实Owner/确认/Preparation/语义编译/分类/Truth/Supply/Observation及重入',
                 'R批单一语义源；外部响应独立fixture')
    test_24_owner_supply_observation(prep_env, tmp_path, monkeypatch, trace, planning_version=3)


from tests import test_semantic_planning as semantic
from tests.test_semantic_planning import semantic_runtime, authority_runtime, material_integration_env


def test_27_semantic_independent_oracle_and_history(trace):
    trace.define('四轮历史错误保留；新协议无损来源及分类由独立答案核对', 'R0真实失败原件及人工固定预期，不由sources_for生成答案')
    semantic.test_real_fourth_failure_replays_before_any_supply()
    semantic.test_semantic_draft_compiles_identity_and_lossless_independent_contract()
    semantic.test_semantic_identity_key_order_crlf_and_required_source_action_protection()
    semantic.test_repair_preserves_optional_model_and_voice_delivery_valid_children()
    for variant in ('derived_id','wrong_modality','voice_text','unknown_scope','duplicate_json','bad_query','query_copy','missing_required','voice_on_visual'):
        semantic.test_semantic_transport_rejects_independent_bad_inputs(variant)
    for variant in ('unknown','missing','duplicate','preference','unresolved','empty_required','metadata'):
        semantic.test_classification_binding_rejects_independent_relational_errors(variant)
    trace.note('independent oracle', '原文/required/preference/postproduction固定核对；16运输/关系负例拒绝，无供应副作用')


def test_28_semantic_native_commit_and_copy(semantic_runtime,trace):
    trace.define('v3正式持久化/load、重入零调用、草稿/快照损坏拒绝、副本绑定新身份', '真实PlanningIntegration与checkpoint复制工具')
    semantic.test_native_semantic_checkpoint_persistence_reentry_and_tamper(semantic_runtime)
    semantic.test_native_semantic_checkpoint_copy_binds_new_attempt_without_replanning(semantic_runtime)
    trace.note('model boundary calls', len(semantic_runtime['calls']))


@pytest.mark.parametrize('stage',['A','B'])
def test_29_semantic_one_shared_repair(semantic_runtime,trace,stage):
    trace.define('A或B单次修复；完成响应重入不新增请求', '同一Attempt共享持久修复预算')
    semantic.test_native_semantic_shared_repair_once_and_repeat_uses_original_request(semantic_runtime,stage)
    trace.note('stage/session identities', semantic_runtime['calls'])


@pytest.mark.parametrize('field',['intent','importance','constraints','modality_spec','queries','duration_hint'])
def test_30_semantic_repair_cannot_rewrite(semantic_runtime,trace,field):
    trace.define('修复不能改写有效语义，首次和重入持续拒绝', 'Astra具名重入绕过回归；独立合法字段对照')
    semantic.test_native_repair_cannot_change_valid_semantics_on_first_or_resumed_run(semantic_runtime,field)
    trace.note('calls',len(semantic_runtime['calls']))


def test_31_semantic_pure_audio_and_mixed(semantic_runtime,trace):
    trace.define('Voice/BGM/SFX正式持久化；纯声音B=0；混合保留模态且仅视觉sidecar', '真实编译/默认绑定/persist/load；Voice来源与原字节摘要保护')
    semantic.test_native_pure_audio_and_mixed_plan_keep_all_modalities_and_voice_byte_binding(semantic_runtime)
    trace.note('pure audio calls',len(semantic_runtime['calls']))


def test_32_semantic_exhausted_repair(semantic_runtime,trace):
    trace.define('A已修复后B失败，不允许二次repair或半产物准入', '整次Planning唯一持久额度，重入不刷新')
    semantic.test_native_semantic_a_repair_then_b_error_does_not_buy_second_repair(semantic_runtime)
    trace.note('calls',len(semantic_runtime['calls']))


@pytest.mark.parametrize('outcome',['timeout','release_pending'])
def test_33_semantic_durable_gateway(semantic_runtime,trace,outcome):
    trace.define('v3实际Gateway适配器中断保留原run/request，终态释放恢复；提交不重复', '仅RPC边界替身，内部幂等/调用账本真实')
    semantic.test_native_v3_gateway_adapter_recovers_original_run_without_resubmission(semantic_runtime,outcome)
    trace.note('boundary',outcome+' recovered with exactly A/B two submits, same run SHA, runtime released')


def test_34_semantic_multibatch(semantic_runtime,trace):
    trace.define('跨批先完整汇合，optional保留；仅修失败批，成功批不改不重派', '40+1固定原文单元，完整Need上下文及既有bind/validate')
    semantic.test_semantic_multibatch_merges_whole_need_and_optional_without_dropping_units()
    semantic.test_native_multibatch_repairs_only_affected_batch_and_keeps_successful_response(semantic_runtime)
    trace.note('calls',len(semantic_runtime['calls']))


@pytest.mark.parametrize('legacy',['ok','error','release_pending','artifact','repair'])
def test_35_semantic_legacy_registration(prep_env,monkeypatch,trace,legacy):
    trace.define('已有旧执行/产物/repair不登记v3，不刷新额度或认领旧结果', '真实Preparation版本登记和旧Attempt隔离状态')
    semantic.test_native_preparation_does_not_upgrade_existing_legacy_planning(prep_env,monkeypatch,legacy)
    trace.note('legacy preserved',legacy)


@pytest.mark.parametrize('risk',['valid_child','misplaced_audio','invalid_importance','tamper','unknown','optional_duration','voice_parameter'])
def test_36_semantic_repair_and_snapshot_protection(semantic_runtime,trace,risk):
    trace.define('修复合法子字段受保护，坏字段可修；冻结篡改和输入变化不复用旧响应', '真实持久两阶段规划，修复与重入组合')
    if risk in {'optional_duration','voice_parameter'}:
        semantic.test_native_repair_valid_children_remain_protected_after_reentry(semantic_runtime,risk)
        trace.note('calls',len(semantic_runtime['calls']))
        return
    {
        'valid_child':semantic.test_native_repair_protects_valid_child_while_fixing_invalid_sibling,
        'misplaced_audio':semantic.test_native_repair_can_remove_misplaced_audio_control_and_preserve_visual,
        'invalid_importance':semantic.test_native_repair_can_correct_invalid_importance_without_changing_valid_intent,
        'tamper':semantic.test_native_classifier_tamper_freezes_failure_and_partial_outputs_never_commit,
        'unknown':semantic.test_native_semantic_unknown_execution_recovers_same_stage_and_snapshot_change_stops,
    }[risk](semantic_runtime)
    trace.note('calls',len(semantic_runtime['calls']))


@pytest.mark.parametrize('risk', ['success', 'truth_reject', 'repair_failed', 'uncertain'])
def test_37_r4_eval_native_stop_boundary(prep_env, monkeypatch, trace, risk):
    trace.define('正常确认与真实内部 Preparation/A/B/Truth/persist/load 后在 Supply 构造之前停止；失败不推进，重入无新增调用',
                 'R4 eval adapter AST-bound native Supply entry; only external model response fixture')
    semantic.test_r4_native_eval_stops_before_supply(prep_env, monkeypatch, risk)
    trace.note('scenario', risk)
    trace.note('Supply / Provider / generation / TTS / Build native entries', 0)


def test_38_r4_frozen_legal_samples(prep_env, trace):
    trace.define('16 份独立正常方案、8/8 划分、各两次独立确认；正文 SHA 保持，未创建 Attempt 或授权生成',
                 'hand-written normal proposal and independent semantic expectations')
    semantic.test_r4_frozen_samples_are_legal_normal_proposals(prep_env)
    trace.note('normal confirmations / independent identities', 32)
    trace.note('real models / real Eval runs', 0)


@pytest.mark.parametrize('risk', ['skip_predecessors', 'tool_drift', 'scene_drift', 'quota_unknown', 'quota_low', 'end_scene_drift'])
def test_39_r4_batch_and_fee_guards(prep_env, tmp_path, monkeypatch, trace, risk):
    trace.define('批次基线不可吸收新变化，工具/版本固定，前序语义通过才可推进；套餐未知或不足时不提交模型；收尾变化强制FAIL',
                 'R4 runner plus native confirmation/Owner; only read-only metadata/HTTP and model results are fixtures')
    semantic.test_r4_runner_preflight_refuses_unsafe_submission(prep_env, tmp_path, monkeypatch, risk)
    trace.note('preflight/reconciliation scenario', risk)
    trace.note('real model / native Supply calls', 0)


@pytest.mark.parametrize('risk', ['accepted', 'wait_timeout', 'release_pending', 'restart', 'lost', 'terminal_error', 'repair_A', 'repair_B'])
def test_40_r4_native_async_lifecycle(prep_env, monkeypatch, trace, risk):
    trace.define('原生Owner/Gateway accepted→pending→原run终态→释放→继续Preparation/A/B/Truth；未知不重提交，终态错误停止',
                 'native state and RPC protocol; only external RPC transport uses fixed responses')
    semantic.test_r4_native_async_owner_checkpoints(prep_env, monkeypatch, risk, evidence=trace)
    trace.note('lifecycle', risk)
    trace.note('Supply / generation / Build calls', 0)


@pytest.mark.parametrize('risk', ['aggregate_history', 'constraint_erasure', 'policy_child',
    'schema_constraints', 'schema_continuity', 'legal_policy', 'legal_reference', 'legal_audio'])
def test_41_a_compiler_contract_alignment(semantic_runtime, trace, risk):
    trace.define('真实A多层错误完整诊断；容器/合法policy子项不能删改；发布Schema与实际编译接受条件一致',
                 'batch03真实原件；真实两阶段持久编译；仅模型边界响应替身；不调用Supply')
    semantic.test_a_compiler_contract_alignment(semantic_runtime, risk, evidence=trace)
    trace.note('real Provider / generation / Supply', 0)


@pytest.mark.parametrize('risk', ['history_quotes', 'nested_quotes', 'unclosed_quote',
                                  'apostrophe_dimensions', 'semantic_limit', 'native_confirmed_basis',
                                  'legacy_policy', 'policy_identity_caps'])
def test_42_semantic_relation_boundary(semantic_runtime, trace, risk):
    trace.define('完整引用/嵌套关系无损；普通apostrophe/尺寸合法；B收到冻结确认依据且稳定重入；历史结构PASS不冒充语义PASS',
                 'batch04真实原A/B/请求/冻结文本及独立oracle；真实内部编译/persist/load；仅模型响应替身')
    semantic.test_semantic_relation_units_and_independent_failure(semantic_runtime, risk, evidence=trace)
    trace.note('real Provider / generation / Supply', 0)


@pytest.mark.parametrize('risk', ['history_review_target', 'observable_contrasts', 'native_target',
                                  'repair_target', 'repair_A_target', 'old_v2_checkpoint', 'target_identity', 'old_v2_pending'])
def test_43_semantic_review_target(semantic_runtime, trace, risk):
    trace.define('素材可观察条件与叙事/事实义务分开；真实wrong-kind不冒充PASS；旧@2按原身份和校验恢复，新目标进入真实请求/修复/批次',
                 'batch05原件及独立反事实；真实compile/原生A/B/persist/load/reentry，仅模型外部响应替身')
    semantic.test_semantic_review_target_contract(semantic_runtime, risk, evidence=trace)
    trace.note('real Supply / Provider / generation / Build', 0)


@pytest.mark.parametrize('risk', ['history_purpose', 'purpose_contrasts', 'native_purpose',
                                  'purpose_repair', 'old_v3_checkpoint', 'purpose_identity', 'old_v3_pending'])
def test_44_semantic_predicate_purpose(semantic_runtime, trace, risk):
    trace.define('原素材属性不因制作用途整体变后期；明确soft/hard及源动作职责保持；旧@3原批次精确恢复，新@4隔离',
                 'batch06真实原件/实际请求/独立语义oracle；真实compile/A/B/persist/load/reentry，仅模型外部替身')
    semantic.test_semantic_predicate_purpose_contract(semantic_runtime, risk, evidence=trace)
    trace.note('real Supply / Provider / generation / Build', 0)


@pytest.mark.parametrize('risk', ['history_diagnostic', 'bad_shapes', 'schema_and_preferences',
                                  'native_schema_repair', 'old_v4_checkpoint', 'output_identity', 'old_v4_pending'])
def test_45_b_output_contract(semantic_runtime, trace, risk):
    trace.define('B与唯一repair使用同一完整输出Schema；非法kind精确拒绝，wrapper/ID/偏好不放宽；旧@4精确恢复且pending不重派',
                 'batch07实际错误A/B/repair请求与回复、合法@4原checkpoint；真实内部编译/持久/重入，仅外部模型替身')
    semantic.test_b_output_contract(semantic_runtime, risk, evidence=trace)
    trace.note('real Supply / Provider / generation / Build', 0)


@pytest.mark.parametrize('risk', ['history_use', 'use_contrasts', 'native_use_repair',
                                  'old_v5_checkpoint', 'use_identity_pending'])
def test_46_asset_versus_use(semantic_runtime, trace, risk):
    trace.define('成片使用/表达不因复述素材主体而变硬采购条件；真正源条件不因后期可改变而消失；旧@5完整Schema身份保持',
                 'batch08实际合法结构但unresolved回复及独立用途反事实；真实内部编译/持久重载，仅外部固定语义回答')
    semantic.test_asset_versus_use_task(semantic_runtime, risk, evidence=trace)
    trace.note('real Supply / Provider / generation / Build', 0)


@pytest.mark.parametrize('risk', ['history', 'basis_transport', 'scalar_controls', 'catalog_eligibility',
                                'operational_origin', 'control_guard', 'creative_contrast', 'verified_loader'])
def test_47_hard_authority_baseline(semantic_runtime, trace, risk):
    trace.define('A候选不是自身上游授权；B依据绑定与标量硬过滤入口必须完整审查，旧@6实际原件仍精确回放且语义FAIL保留',
                 'batch09真实A/B/正式Plan/Requirements/确认/Preparation/Creator/Truth/Mode原件与独立预期；新保护修前应失败')
    semantic.test_batch09_hard_authority_baseline(semantic_runtime, risk, evidence=trace)
    trace.note('real Supply / Provider / generation / Build', 0)


@pytest.mark.parametrize('risk',['persist_reentry','repair','pending','source_tamper','catalog_tamper','missing_basis','control_missing','copy',
                                'multibatch','pure_audio','mixed_audio','capacity'])
def test_48_native_authority_contract(authority_runtime,trace,risk):
    trace.define('新@7合同使用实际冻结来源；完整审查basis和control，重入/修复/复制不刷新身份额度',
                 '真实Handoff/编译/单次修复/正式persist-load；只在外部模型边界提供声明固定回复')
    semantic.test_native_authority_contract(authority_runtime,risk)
    trace.note('external fixture calls',len(authority_runtime['calls']))
    trace.note('real Supply / Provider / generation / Build',0)


@pytest.mark.parametrize('risk', ['entities', 'aliases', 'duration', 'scope_integrity'])
def test_49_vnext_canonical_facts(trace, risk):
    trace.define('成片/源素材/展示事实分别建权威；一个语义选择确定派生技术表示，不推断silence=image或静图源时长',
                 'batch09冻结原件的离线派生输入，历史原件及FAIL不改；只执行程序投影')
    semantic.test_vnext_canonical_facts(risk)
    trace.note('proof scope', 'DETERMINISTIC_CONTRACT / REJECTION')
    trace.note('real model / Supply', 0)


@pytest.mark.parametrize('risk', ['complete', 'length', 'no_result', 'invalid', 'persist_failure', 'pending'])
def test_50_vnext_capture_transport(prep_env, tmp_path, trace, risk):
    trace.define('原Gateway run捕获；截断/无结果不误算语义repair，本地保存失败不重派',
                 '真实Delivery适配器及Harness，仅Gateway RPC固定替身；无文件工具代写结果')
    semantic.test_vnext_capture_transport(prep_env, tmp_path, risk)
    trace.note('proof scope', 'ARTIFACT_TRANSPORT / REJECTION')
    trace.note('real model / Supply', 0)


@pytest.mark.parametrize('risk', ['A', 'B', 'repair_capacity', 'preview', 'length',
    'identity', 'late', 'missing', 'lost_terminal', 'duplicate_json', 'persist_failure', 'input_os_capacity', 'escaped_secret', 'sensitive_key', 'tool_valid', 'tool_wrong_name', 'tool_wrong_schema', 'tool_wrong_terminal', 'tool_runtime_upgrade', 'tool_runtime_readback'])
def test_51_vnext_full_capture(prep_env, tmp_path, trace, risk):
    trace.define('完整合法A/B及repair envelope无损捕获；不认领preview/别的run/未知终态；同原请求恢复',
                 '真实Delivery/Harness/有界响应Schema；仅Gateway和Runtime外部边界固定替身，安装Runtime另有具名离线回放')
    semantic.test_vnext_full_capture(prep_env, tmp_path, risk)
    trace.note('proof scope', 'FULL_RESULT_TRANSPORT / IDENTITY / RECOVERY')
    trace.note('real model / Supply', 0)


@pytest.mark.parametrize('risk', ['mixed_projection', 'source_frame', 'identity_cache', 'forbidden_aliases', 'real_audio_postproduction'])
def test_52_vnext_semantic_projection(trace, risk):
    trace.define('窄A不维护正式ID/别名/sidecar；确定派生保留素材required、偏好、后期/叙事及音频隔离，旧策略无回归',
                 'batch09脱敏冻结输入的具名派生对照；真实MaterialNeed/NeedCompiler/visual contract模块')
    semantic.test_vnext_semantic_projection(risk)
    trace.note('proof scope', 'SEMANTIC_PROJECTION / CANONICAL_CONTRACT / CACHE_IDENTITY')
    trace.note('real model / Supply', 0)


@pytest.mark.parametrize('origin', ['batch03', 'batch10'])
def test_53_vnext_historical_projection(trace, origin):
    trace.define('历史混合输出保持FAIL；脱敏原语义的显式派生对照消除policy/array/alias重复，未知连续性整轮拒绝',
                 'batch03真实A/catalog和batch10真实scope/A提取；仅首Need结构风险验证，不冒充原全Plan覆盖或B语义通过')
    semantic.test_vnext_historical_projection(origin)
    trace.note('real model / Supply',0)


@pytest.mark.parametrize('risk', ['reentry', 'audio_omission', 'structural_repair', 'semantic_repair',
    'exhausted', 'answer_repair', 'pending', 'persist_failure', 'tamper', 'unknown_question', 'multibatch', 'legacy_resume',
    'legacy_carrier_pending', 'legacy_tool_pending', 'carrier_removed', 'carrier_changed',
    'missing_slot', 'forged_support', 'derived_authority', 'real_wrapper', 'real_full_creation', 'real_full_creation2', 'repair_invalid', 'legacy_supported_pending',
    'legacy_supported_current', 'legacy_wire_current', 'xml_roundtrip', 'xml_answer_repair', 'wire_tamper', 'frame_header_repair',
    'staged_reentry', 'staged_structure', 'staged_semantic', 'staged_selection_captured',
    'staged_details_registered', 'staged_details_unknown', 'staged_tamper'])
def test_54_vnext_bounded_review(authority_runtime, monkeypatch, trace, risk):
    trace.define('新视频入口全audio仍查冻结视觉遗漏；有界B保留完整义务和原件，局部patch不改已接受语义；一次额度重入不刷新',
                 '真实Handoff、Harness capture、问题/修复、正式合同persist/load；仅模型执行边界返回明确固定判断')
    staged = {'staged_reentry': ('reentry', None), 'staged_structure': ('structural_repair', None),
              'staged_semantic': ('semantic_repair', None),
              'staged_selection_captured': ('frame_header_repair', 'selection_captured'),
              'staged_details_registered': ('frame_header_repair', 'details_registered'),
              'staged_details_unknown': ('frame_header_repair', 'details_unknown')}
    if risk == 'staged_tamper':
        semantic.test_vnext_staged_capture_replay_identity(authority_runtime, monkeypatch)
    elif risk in staged:
        semantic.test_vnext_staged_request_recovery(authority_runtime, monkeypatch, *staged[risk])
    else:
        semantic.test_vnext_bounded_review_runtime(authority_runtime, monkeypatch, risk)
    trace.note('real model / Supply / service operations', 0)


@pytest.mark.parametrize('risk', ['immutable_patch', 'whole_context', 'capacity', 'false_accept_risk', 'xml_codec', 'atomic_frame'])
def test_55_vnext_review_protection(trace, risk):
    trace.define('query不当视觉义务；完整原文/上下文不裁剪；已接受部分不可改，非法证据拒绝；错误ACCEPT仍由独立语义预期检出',
                 'batch10冻结输入的离线派生对照；实际问题构造、patch合同、formal projection，不冒充模型能力')
    semantic.test_vnext_review_contract_protection(risk)
    trace.note('semantic guarantee', 'NOT_CLAIMED: incorrect B ACCEPT remains model risk')
    trace.note('real model / Supply', 0)


@pytest.mark.parametrize('risk', ['success', 'semantic_reject', 'truth_reject', 'capture_truncated', 'source_tamper', 'async_tamper', 'between_resume', 'output_as_source',
    *['preset:' + risk for risk in ['match', 'script_auto_pass', 'old_script_cache', 'conflict',
    'unresolved', 'unknown_handle', 'empty_script', 'missing_binding', 'duplicate_voice', 'capacity',
    'report_format', 'repair_changes_decision', 'fake_quote', 'missing_report', 'scope_drift', 'profile_drift',
    'material_match', 'material_preset', 'material_bundle_swap', 'material_forged_rights',
    'material_forged_record', 'material_bytes', 'material_cache',
    'conflict_missing_script', 'unresolved_extra_outer', 'match_outer_repair_changes',
    'material_fork', 'material_fork_report', 'material_fork_plan', 'material_fork_record',
    'material_fork_fingerprint', 'material_fork_creation', 'material_fork_cycle', 'material_fork_copy']]])
def test_56_vnext_continuous_owner(prep_env, monkeypatch, trace, risk):
    if risk.startswith('preset:'):
        trace.define('正常入口绑定已展示身份；程序派生唯一required Voice；SCRIPT自动PASS不跳过独立Truth；正式Supply/记录/Rights/Gate验证当前批准资产并保护恢复',
                     '真实内部提案/确认/Owner/Preparation/Handoff/A/B/Truth/persist/load；material变体继续正式Supply/TTS记录/独立ASR/Rights/Match/Gate，仅模型/Provider/识别边界固定替身')
        semantic.test_vnext_confirmed_preset_truth_boundary(prep_env, monkeypatch, risk.split(':', 1)[1])
        trace.note('live external execution / Build / fees', 0)
        return
    trace.define('正常确认/Owner/Preparation/新A完整capture/有界B/Truth/真实persist-load连续执行；Supply前停止，失败不放行或重派',
                 '默认新版产品入口，脱敏正常d01固定主题；仅外部模型响应替身，原Eval切点及内部模块真实执行')
    semantic.test_vnext_continuous_owner_boundary(prep_env, monkeypatch, risk)
    trace.note('real Supply / Provider / generation / Build', 0)


@pytest.mark.parametrize('risk', ['submissions', 'deadline_observation', 'round2_gate', 'roster',
                               'goal_identity', 'stopped_observation', 'native_submit_cut', 'completed_seal'])
def test_57_vnext_development_bounds(tmp_path, prep_env, monkeypatch, trace, risk):
    trace.define('Development最多两轮/6样本/32提交/60分钟、单样本8分钟；已知原请求仅观察不重扣，第二轮一次软件Gate且账本不清零',
                 '同一真实评测器的隔离持久账本；无网络或模型调用，保持held-out不用')
    if risk in {'submissions', 'deadline_observation', 'round2_gate', 'roster'}:
        semantic.test_vnext_development_bounds(tmp_path, risk)
    else:
        semantic.test_vnext_development_recovery(prep_env, tmp_path, monkeypatch, risk)
    trace.note('real model / fees', 0)


@pytest.mark.parametrize('risk', ['schema', 'native_guard', 'slots', 'final_source', 'derived',
    'forged_quote', 'unknown_field', 'legitimate_native', 'postproduction', 'whole_obligation', 'capacity'])
def test_58_structured_carrier_contract(tmp_path, trace, risk, request):
    trace.define('完整动态Schema与冻结目录/既有模态一致；原生持久化前安全检查、8MiB容量、原请求并发占额和协议恢复拒绝',
                 '真实schema/parser和原生支持模块；隔离进程/本地存储，无Provider网络')
    if risk == 'schema':
        semantic.test_vnext_tool_schema_matches_frozen_choices_and_existing_modality_rules()
    elif risk != 'native_guard':
        semantic.test_supported_review_frozen_references(risk)
    else:
        request.getfixturevalue('native_guard_process')
        from tests.test_openclaw_structured_result import test_native_structured_storage_and_concurrent_submission_guard
        test_native_structured_storage_and_concurrent_submission_guard(tmp_path)
    trace.note('external submissions / fees', 0)
