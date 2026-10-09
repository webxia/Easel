"""Application-owned preset choice and source-bound Truth evidence.

An official label is an identity, not proof of gender, range or audible quality.
Provider IDs stay in the existing execution scope; the Material contract is neutral.
"""
from __future__ import annotations

import hashlib
import json

from easel.integrations.planning_authority import digest

PROFILE_POLICY = 'confirmed-preset-profile@1'
BINDING_POLICY = 'confirmed-preset-binding@1'
REVIEW_POLICY = 'voice-identity-review@1'
CHECKPOINT_POLICY = 'voice-identity-checkpoint@1'
REFERENCE = 'confirmed.voice_profile'
HANDLE = 'preset-cmn-youth'
_PRESET = 'male-qn-qingse'
_DOCUMENT_SHA = 'e522acb13f9c1b6d76daeb424f60eb8d150d184a8fcc1e44dbb9270878162d6e'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def verified_profile():
    from easel.materials.providers.minimax_pricing import VOICE_URL
    from easel.materials.application.voice_delivery import voice_delivery_schema
    return {'schema': PROFILE_POLICY, 'handle': HANDLE, 'label': '青涩青年音色',
            'language': 'zh-CN', 'official_language': '中文 (普通话)',
            'evidence': {'url': VOICE_URL, 'document_sha256': _DOCUMENT_SHA,
                         'label_quote': '青涩青年音色', 'language_quote': '中文 (普通话)'},
            'execution_controls_schema': voice_delivery_schema(),
            'limits': '官方名称和语言不证明性别、音域或听感；只执行已冻结的语速、音调和支持的情绪控制。'}


def available_profile():
    """Read the existing runtime configuration, without network or credentials."""
    from easel.integrations.material_generation import generation_budget_preview
    preview = generation_budget_preview()
    if preview.get('available') and preview['scope'].get('speech_voice_id') == _PRESET:
        return verified_profile()
    return None


def validate_profile(value):
    if value != verified_profile():
        raise ValueError('预置旁白身份或官方能力版本未核实')


def render_sound(source, profile):
    validate_profile(profile)
    return source + '\n\n已选择预置旁白：' + profile['label'] + '（' + profile['official_language'] + '）。'


def binding_for(work):
    delivery = work.get('delivery') or {}
    proposal = delivery.get('video_plan') or {}
    if proposal.get('schema') != 'easel-video-proposal@3':
        return None
    from easel.creator_proposal import validate_video_plan
    if not validate_video_plan(proposal) or proposal['specs']['audio_mode'] not in {'voice', 'mixed'}:
        raise ValueError('确认旁白方案不完整')
    profile = proposal['voice_profile']
    grant = delivery.get('authorization', {}).get('material_generation') or {}
    from easel.integrations.material_generation import authorized_generation_modalities
    if ('voice' not in authorized_generation_modalities(grant)
            or not grant.get('scope_sha256') or grant.get('scope', {}).get('speech_voice_id') != _PRESET
            or not delivery.get('confirmed_at') or not delivery.get('proposal_sha256')
            or (work.get('chat_workflow') or {}).get('video_plan', {}).get('sha256') != proposal['sha256']):
        raise ValueError('已确认旁白缺少对应的技术身份和预算授权')
    value = {'schema': BINDING_POLICY, 'creation_id': work['id'],
             'proposal_sha256': delivery['proposal_sha256'], 'plan_sha256': proposal['sha256'],
             'confirmed_at': delivery['confirmed_at'], 'profile_sha256': digest(profile),
             'sound_source_sha256': sha(proposal['sound_source']), 'sound_sha256': sha(proposal['sound']),
             'script_sha256': sha(proposal['script']), 'scope_sha256': grant['scope_sha256'],
             'scope_content_sha256': digest(grant['scope'])}
    return {**value, 'binding_sha256': digest(value)}


def require_binding(work, plan=None, script=None):
    expected = binding_for(work)
    recorded = (work.get('delivery') or {}).get('voice_binding')
    if expected is None:
        if recorded is not None:
            raise ValueError('旧方案不能取得新旁白绑定')
        return None
    if recorded != expected:
        raise ValueError('已确认旁白绑定缺失或变化')
    if script is not None and sha(script) != expected['script_sha256']:
        raise ValueError('旁白绑定SCRIPT已变化')
    if plan is not None:
        voices = [n for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'voice']
        if (plan.creation_id != work['id'] or len(voices) != 1
                or voices[0].importance.value != 'required'
                or voices[0].modality_spec.identity is None
                or voices[0].modality_spec.identity.reference != REFERENCE
                or voices[0].modality_spec.identity.source.value != 'explicit_user'
                or voices[0].modality_spec.text_sha256 != expected['script_sha256']):
            raise ValueError('正式旁白Need与确认身份不一致')
    return expected


def derived_catalog(proposal, script):
    if not proposal or proposal.get('schema') != 'easel-video-proposal@3':
        return None
    from easel.creator_proposal import validate_video_plan
    if (not validate_video_plan(proposal) or proposal['script'] != script or not script.strip()
            or proposal['specs']['audio_mode'] not in {'voice', 'mixed'}):
        raise ValueError('程序旁白义务缺少完整确认选择')
    return {'profile': proposal['voice_profile'], 'plan_sha256': proposal['sha256'],
            'script_sha256': sha(script), 'sound_source_sha256': sha(proposal['sound_source'])}


def derived_need(catalog):
    from easel.integrations.planning_result_contract import NeedProposal
    row = catalog['derived_voice']
    profile = row['profile']
    validate_profile(profile)
    return NeedProposal(scope='global', role='旁白', modality='voice', necessity='required',
        conditions=({'text': '以已确认预置身份“' + profile['label'] + '”逐字朗读完整确认SCRIPT，语言为' + profile['official_language'],
                     'strength': 'required', 'responsibility': 'material'},),
        voice_choice=REFERENCE, voice_expression='已确认预置身份：' + profile['label'],
        purpose='完整声音表达保留在确认方案与独立Truth审阅；身份绑定不替代听审。')


def review_context(work, plan, script, ledger):
    binding = require_binding(work, plan, script)
    if binding is None:
        return None
    need = next(n for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'voice')
    from easel.materials.application.voice_delivery import validate_voice_delivery
    controls = validate_voice_delivery(need.constraints.get('voice_delivery', {}))
    proposal = work['delivery']['video_plan']
    sources = {'sound_source': proposal['sound_source'],
               'voice_profile': json.dumps(proposal['voice_profile'], ensure_ascii=False, sort_keys=True),
               'execution_controls': json.dumps(controls, ensure_ascii=False, sort_keys=True)}
    # Reapplying the same Script assessment stamps a fresh reviewed_at. Bind
    # its complete semantic content, while keeping audit timestamps in the
    # original ledger. No decision, quote or source identity is excluded.
    script_review = json.loads(json.dumps(ledger))
    script_review.pop('ledger_sha256', None)
    for row in script_review['claims']:
        if isinstance(row.get('review'), dict): row['review'].pop('reviewed_at', None)
    identity = {'schema': REVIEW_POLICY, 'binding_sha256': binding['binding_sha256'],
                'plan_sha256': binding['plan_sha256'], 'profile_sha256': binding['profile_sha256'],
                'sound_source_sha256': binding['sound_source_sha256'],
                'script_sha256': binding['script_sha256'],
                'script_review_sha256': digest(script_review),
                'truth_packet_sha256': ledger['truth_packet_sha256'],
                'material_plan_sha256': sha(plan.to_json()), 'need_sha256': sha(need.to_json()),
                'controls_sha256': digest(controls)}
    return {'identity': identity, 'sources': sources}


def validate_decision(decision, context):
    from easel.integrations.hypit.secrets import SecretRedactor
    if (not isinstance(decision, dict) or set(decision) != {'decision', 'reason', 'sources'}
            or decision['decision'] not in {'MATCH', 'CONFLICT', 'UNRESOLVED'}
            or not isinstance(decision['reason'], str) or not 8 <= len(decision['reason']) <= 2000
            or not isinstance(decision['sources'], list) or len(decision['sources']) > 12
            or SecretRedactor.contains_secret(decision)):
        raise ValueError('旁白身份Truth报告格式不合法')
    cited = set()
    for source in decision['sources']:
        if (not isinstance(source, dict) or set(source) != {'ref', 'quote'}
                or source['ref'] not in context['sources'] or not isinstance(source['quote'], str)
                or not source['quote'].strip() or source['quote'] not in context['sources'][source['ref']]):
            raise ValueError('旁白身份Truth报告引用不是冻结原文')
        cited.add(source['ref'])
    if decision['decision'] == 'MATCH' and cited != set(context['sources']):
        raise ValueError('旁白身份MATCH缺少完整来源和实际执行能力核对')
    value = {**context['identity'], 'result': decision}
    return {**value, 'report_sha256': digest(value)}


def validate_report(report, context):
    expected = validate_decision(report.get('result') if isinstance(report, dict) else None, context)
    if report != expected or report['result']['decision'] != 'MATCH':
        raise ValueError('旁白身份Truth未通过或已过期')
    return expected


def read_checkpoint_report(attempt, manifest):
    from pathlib import Path
    from easel.integrations.material_layer import _has_symlink_components
    from easel.integrations.planning_reply_safety import safe_structured_text
    root = Path(attempt['workspace']['path']).resolve()
    path = root / 'planning/voice-identity-review.json'
    if (_has_symlink_components(root, path) or not path.is_file() or path.stat().st_size > 512 * 1024
            or manifest.get('voice_identity') != {'path': 'planning/voice-identity-review.json',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}):
        raise ValueError('冻结旁白身份Truth项缺失或变化，不能复用旧SCRIPT报告')
    raw = path.read_text(encoding='utf-8')
    if not safe_structured_text(raw):
        raise ValueError('冻结旁白身份报告不安全')
    return json.loads(raw)


def validate_checkpoint(work, attempt, plan, script, ledger, report, *,
                        manifest=None, allow_inheritance=False):
    """Verify existing fork lineage once, without recursive load/Gate calls.

    A checkpoint maps identities; it never changes the original semantic
    decision, generation record or commission receipt. All source contracts,
    gates, bytes and submission fingerprints remain live evidence.
    """
    from pathlib import Path
    from easel.integrations.hypit import service
    from easel.integrations.material_layer import PlanningIntegration
    from easel.materials.store import AttemptMaterialStore
    from easel.materials.application.readiness import MaterialReadinessCalculator
    from easel.materials.domain import ReadinessStatus
    root = Path(attempt['workspace']['path']).resolve()
    current = {'attempt': attempt, 'plan': plan, 'script': script, 'truth_ledger': ledger,
               'manifest': manifest or {}, 'voice_report': report,
               'treatment': (root / 'planning/TREATMENT.md').read_text(encoding='utf-8'),
               'scenes': (root / 'planning/SCENES.md').read_text(encoding='utf-8')}
    nodes, visited = [current], {plan.attempt_id}
    while nodes[-1]['attempt'].get('retry_source'):
        child = nodes[-1]
        edge = child['attempt']['retry_source']
        source_id = edge.get('attempt_id')
        if (not source_id or source_id in visited
                or edge.get('status') not in {'COPYING', 'READY', 'AUTHORING_REPAIR_REQUIRED'}):
            raise ValueError('旁白checkpoint来源断裂或循环')
        visited.add(source_id)
        source = service.get_film_attempt(source_id)
        if (source['creation_id'] != work['id'] or source['handoff'] != child['attempt']['handoff']
                or source.get('build', {}).get('build_id') != edge.get('build_id')):
            raise ValueError('旁白checkpoint跨作品或冻结Handoff身份变化')
        fingerprint = service._execution_fingerprint(source)['sha256']
        if (fingerprint != edge.get('fingerprint') or fingerprint != source.get('build', {}).get(
                'operation', {}).get('execution_fingerprint', {}).get('sha256')):
            raise ValueError('旁白checkpoint源提交fingerprint变化')
        parent = PlanningIntegration()._load_contract(source)
        parent['voice_report'] = read_checkpoint_report(source, parent['manifest'])
        left, right = child['plan'].model_dump(mode='json'), parent['plan'].model_dump(mode='json')
        for key in ('plan_id', 'attempt_id'):
            left.pop(key); right.pop(key)
        origin = parent['manifest'].get('requirements', {}).get('origin') or {
            'creation_id': work['id'], 'attempt_id': source_id, 'plan_id': parent['plan'].plan_id}
        if (left != right or any(child[key] != parent[key] for key in ('script', 'treatment', 'scenes', 'truth_ledger'))
                or child['manifest'].get('requirements', {}).get('origin') != origin
                or child['manifest'].get('semantic', {}).get('origin') != origin):
            raise ValueError('旁白checkpoint完整Plan、Truth或Planning origin变化')
        store = AttemptMaterialStore(source['workspace']['path'])
        bundle = store.read_bundle()
        ready, gaps = MaterialReadinessCalculator(store=store).calculate(parent['plan'], bundle)
        gate = source.get('material_gate', {})
        if (ready.status is not ReadinessStatus.READY or gaps or gate.get('status') != 'MATERIAL_READY'
                or gate.get('plan_revision') != ready.plan_revision or gate.get('bundle_revision') != bundle.revision):
            raise ValueError('旁白checkpoint源Gate已失效')
        parent['bundle'] = bundle
        nodes.append(parent)
    for index in range(len(nodes) - 1, -1, -1):
        node = nodes[index]
        context = review_context(work, node['plan'], node['script'], node['truth_ledger'])
        if index == len(nodes) - 1:
            expected = validate_report(node['voice_report'], context)
        else:
            parent = nodes[index + 1]
            source_context = review_context(work, parent['plan'], parent['script'], parent['truth_ledger'])
            if ({k: v for k, v in context['identity'].items() if k != 'material_plan_sha256'} !=
                    {k: v for k, v in source_context['identity'].items() if k != 'material_plan_sha256'}):
                raise ValueError('旁白checkpoint冻结语义来源变化')
            value = {'schema': CHECKPOINT_POLICY, 'context_sha256': digest(context['identity']),
                     'source_attempt_id': parent['attempt']['attempt_id'],
                     'source_plan_sha256': sha(parent['plan'].to_json()),
                     'target_plan_sha256': sha(node['plan'].to_json()),
                     'source_report_sha256': digest(parent['voice_report']),
                     'source_fingerprint': node['attempt']['retry_source']['fingerprint']}
            expected = {**value, 'report_sha256': digest(value)}
            if node['voice_report'] != expected and not (
                    index == 0 and allow_inheritance and node['voice_report'] is None):
                raise ValueError('旁白checkpoint继承包装缺失或变化')
        node['voice_report'] = expected
        if index > 0:
            source_store = AttemptMaterialStore(node['attempt']['workspace']['path'])
            evidence = covered_asset_evidence(work, node['plan'], node['bundle'], source_store,
                node['script'], checkpoint={'chain': nodes[index:], 'report': expected})
            if node['attempt']['material_gate'].get('voice_identity_evidence') != evidence:
                raise ValueError('旁白checkpoint源身份Gate证据已失效')
    return {'report': nodes[0]['voice_report'], 'chain': nodes}


def covered_asset_evidence(work, plan, bundle, store, script, *, checkpoint):
    """Recheck every currently approved Voice relationship, including bytes.

    A correct unused candidate cannot legitimize another approved asset. The
    resulting identity participates in both Gate writes and consumer recovery.
    """
    binding = require_binding(work, plan, script)
    if binding is None:
        return None
    need = next(n for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'voice')
    from easel.materials.application.voice_delivery import validate_voice_delivery
    from easel.materials.domain import RightsStatus
    from easel.integrations.material_generation import commission_generated_rights
    assets = {a.asset_id: a for a in bundle.assets}
    approved = sorted({m.asset_id for m in bundle.matches if m.need_id == need.need_id and m.qualified})
    records = store.list_generation_records()
    proofs = []
    for asset_id in approved:
        asset = assets[asset_id]
        path = store.resolve_asset_locator(asset.file.path)
        if (not path.is_file() or path.stat().st_size != asset.file.size
                or hashlib.sha256(path.read_bytes()).hexdigest() != asset.file.sha256
                or store.read_asset(asset_id) != asset or asset.rights.status is not RightsStatus.KNOWN
                or asset.rights.reviewed_at is not None):
            raise ValueError('获准旁白资产字节或正式Rights已变化')
        matches = [r for r in records if r.get('asset_id') == asset_id and r.get('status') == 'COMPLETE'
                   and r.get('need_id') == need.need_id]
        if len(matches) != 1:
            raise ValueError('获准旁白缺少唯一正式生成记录，ASR同文不证明身份')
        record = matches[0]
        origin_plan = plan
        if record.get('plan_id') != plan.plan_id:
            from easel.materials.store import AttemptMaterialStore
            origin = next((n for n in checkpoint['chain'][1:] if n['plan'].plan_id == record.get('plan_id')), None)
            if origin is None:
                raise ValueError('获准旁白生成记录没有可信checkpoint来源')
            original_store = AttemptMaterialStore(origin['attempt']['workspace']['path'])
            if (original_store.read_generation_record(record['generation_id']) != record
                    or original_store.read_asset(asset_id) != asset
                    or not any(m.need_id == need.need_id and m.asset_id == asset_id and m.qualified
                               for m in origin['bundle'].matches)):
                raise ValueError('获准旁白不是可信源批准资产与记录的原样复制')
            origin_plan = origin['plan']
        if record.get('speech_settings') != validate_voice_delivery(need.constraints.get('voice_delivery', {})):
            raise ValueError('旁白生成的实际执行参数与冻结Need不一致')
        # Re-run the existing formal Rights claim against its original base.
        # This verifies evidence; it never writes or invents a missing claim.
        base_rights = asset.rights.model_copy(update={'status': RightsStatus.UNKNOWN,
            'license_name': None, 'license_url': None, 'usage_constraints': (),
            'evidence': tuple(e for e in asset.rights.evidence if e.kind != 'asset_commission_use')})
        reconstructed = commission_generated_rights(work, origin_plan, need,
            asset.model_copy(update={'rights': base_rights}), record, script)
        if reconstructed is None or reconstructed != asset.rights:
            raise ValueError('获准旁白身份没有对应同一生成记录的正式Rights认领')
        proofs.append({'asset_id': asset_id, 'asset_sha256': asset.file.sha256,
                       'record_sha256': digest(record), 'rights_sha256': digest(asset.rights.model_dump(mode='json'))})
    return {'binding_sha256': binding['binding_sha256'], 'need_sha256': sha(need.to_json()),
            'voice_report_sha256': digest(checkpoint['report']),
            'bundle_revision': bundle.revision, 'approved': proofs}
