"""vNext policy in the existing Planning request/recovery and publish boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from easel.integrations import planning_authority as authority
from easel.integrations import planning_semantic_review as review
from easel.integrations.planning_capture import capture
from easel.integrations.planning_result_contract import SemanticProposal, MAX_RESULT_BYTES
from easel.integrations.semantic_boundary import POLICY, parse_proposal, project_proposal
from easel.integrations.semantic_planning import source_catalog, write_file
from easel.materials.store import AttemptMaterialStore

STATE_KEY = 'semantic-planning-vnext'
CHECKPOINT = 'semantic-planning-frozen@2'
MAX_CHECKPOINT_BYTES = 32 * MAX_RESULT_BYTES
# A technical bound, never authorization to spend. The real evaluator's
# shared submission/time/subscription ledger remains independently binding.
MAX_PLANNING_CALLS = 30


def check_existing_sources(attempt):
    """Check a new-policy journal before any legacy restoration can hide edits."""
    store = AttemptMaterialStore(attempt['workspace']['path'])
    state = store.read_recovery_record(STATE_KEY)
    if state is None:
        return
    if state.get('terminal_failure'):
        raise ValueError('Original Planning frozen-source violation is reject-only')
    scope = state['scope']
    try:
        if authority.load_inputs(attempt, scope['canonical'],
                {'context_refs': scope['context_refs']}, scope['mode']) != scope['inputs']:
            raise ValueError('Frozen Planning sources changed before recovery')
    except ValueError:
        state['terminal_failure'] = 'FROZEN_SOURCE_CHANGED'
        store.write_recovery_record(STATE_KEY, state)
        raise


def policy_for(attempt, *, default=POLICY):
    """New entrance uses vNext; old pending journals retain their exact policy."""
    store = AttemptMaterialStore(attempt['workspace']['path'])
    old = store.read_recovery_record('semantic-planning-v3')
    new = store.read_recovery_record(STATE_KEY)
    if old is not None and new is not None:
        raise ValueError('Multiple Planning policies own this Attempt; no dispatch')
    if old is not None:
        from easel.integrations.semantic_planning import _compiler_policy
        policy = old.get('scope', {}).get('policy')
        if not policy: raise ValueError('Old pending policy missing; never assume the current default')
        return _compiler_policy(policy)
    if new is not None:
        if new.get('scope', {}).get('policy') != POLICY:
            raise ValueError('Unknown vNext journal policy; no downgrade')
        return POLICY
    if default != POLICY:
        from easel.integrations.semantic_planning import _compiler_policy
        return _compiler_policy(default)
    return POLICY


def a_message(scope):
    return review.checked_message('〔Easel Semantic Planning vNext〕\n'
        '只提出语义计划；正式ID、路径、hash、技术别名、sidecar、缓存及文件由程序负责。'
        '完整承接冻结要求，不省略required。条件逐项保留完整含义并区分强度与素材/后期/叙事责任；'
        '用途不改变源属性归属。源画幅/源时长是独立语义选择，不能自动继承成片规格。'
        '软风格不升级required，Preparation不创造作者新增授权。scope/continuity/voice只选目录。'
        'queries为可选检索提示，不是视觉原文或硬filter。未知含义写unresolved，不能猜测。'
        '只返回schema JSON；不写文件，不调用工具、供应、生成或制作。\n' + review.compact({
            'schema': SemanticProposal.model_json_schema(), 'inputs': scope['inputs'],
            'catalog': scope['catalog']}))


def descriptors(targets):
    return [{k: v for k, v in target.items() if k != 'annotation'} for target in targets]


def repair_message(scope, original, targets, context=None):
    return review.checked_message('〔Easel Planning vNext 单次局部修复〕\n'
        '仅修targets列出的未接受局部，target是程序提供的整数标签。原件、已接受语义、必要性、'
        '已接受答案及所有其他字段不可变。不能返回整个对象、删需求、扩授权或放宽准入。'
        'visual_choices的value交同一Need，仅修其header，conditions/queries/necessity须保持。'
        'coverage缺口只能补充有冻结支持的视觉Need，不能改掉原Need。改后再次独立复核。'
        '只返回schema JSON，不调用工具或写文件。\n' + review.compact({
            'schema': review.patch_schema(targets), 'targets': descriptors(targets),
            'original': original, 'inputs': scope['inputs'], 'review_context': context}))


def run(attempt, planning_context, canonical, mode, route, dispatch):
    store = AttemptMaterialStore(attempt['workspace']['path'])
    root = store.attempt_root
    inputs = authority.load_inputs(attempt, canonical, planning_context, mode)
    catalog = source_catalog(canonical, {'creator_context': inputs['creator_context']})
    scope = {'policy': POLICY, 'creation_id': attempt['creation_id'], 'attempt_id': attempt['attempt_id'],
             'context_refs': planning_context['context_refs'], 'canonical': canonical, 'mode': mode,
             'inputs': inputs, 'catalog': catalog}
    state = store.read_recovery_record(STATE_KEY)
    if state is None:
        if store.read_recovery_record('semantic-planning-v3') is not None or list(
                (root / 'materials/recoveries').glob('planning-structure-repair-*.json')):
            raise ValueError('Old Planning journal must resume its exact policy, not obtain new repair')
        state = {'schema': 'semantic-planning-checkpoint@2', 'scope': scope, 'route': route,
                 'calls': {}, 'repair_used': False}
        store.write_recovery_record(STATE_KEY, state)
    elif (state.get('schema') != 'semantic-planning-checkpoint@2'
          or state.get('scope') != scope or state.get('route') != route):
        raise ValueError('Frozen vNext input, policy or execution route changed; no refreshed allowance')
    if state.get('terminal_failure'):
        raise ValueError('Original Planning frozen-source violation is reject-only; no recovery dispatch')
    def save(): store.write_recovery_record(STATE_KEY, state)
    def frozen():
        try:
            if authority.load_inputs(attempt, canonical, planning_context, mode) != inputs:
                raise ValueError('Frozen Planning sources changed during execution')
        except ValueError:
            state['terminal_failure'] = 'FROZEN_SOURCE_CHANGED'
            save()
            raise
    def invoke(key, message):
        frozen()
        if key not in state['calls'] and len(state['calls']) >= MAX_PLANNING_CALLS:
            raise ValueError('Fixed Planning call range exhausted; no new dispatch')
        try:
            result = capture(state['calls'], key, review.checked_message(message),
                f"semantic-{attempt['attempt_id']}-vnext-{key}",
                lambda key, text, session: dispatch('structure_repair' if key == 'repair' else 'planning', text, session), save)
        finally:
            frozen()  # Async/uncertain results cannot skip source-integrity recording.
        return result
    def repair(stage, original, targets, context=None):
        message = repair_message(scope, original, targets, context)  # Capacity before consuming allowance.
        repair_identity = {'stage': stage, 'targets': descriptors(targets),
                           'original_sha256': authority.digest(original), 'context_sha256': authority.digest(context)}
        if state['repair_used'] and state.get('repair') != repair_identity:
            raise ValueError('Whole Planning shared repair allowance exhausted')
        state.update(repair_used=True, repair=repair_identity)
        save()  # Written before dispatch; restart never refreshes allowance.
        output = invoke('repair', message)
        return review.apply_patches(original, output, targets), output

    initial = invoke('A', a_message(scope))
    value = initial
    lineage = None
    targets = review.structural_targets(value)
    if targets:
        value, output = repair('A', value, targets)
        lineage = {'stage': 'A', 'targets': descriptors(targets), 'output': output}
    proposal = parse_proposal(value, catalog)
    # Normalize only defined defaults, preserving the immutable captured raw A.
    value = proposal.model_dump(mode='json')
    initial_review_value = value
    directory = review.questions(proposal, inputs, catalog)
    initial_responses, responses = [], []
    batches = review.review_batches(directory)
    # Reserve capacity for one patch and all potentially changed visual Needs
    # plus independent coverage recheck before submitting ANY initial B batch.
    coverage_count = sum(q['kind'] == 'frozen_visual_coverage' for q in directory['questions'])
    maximum_rechecks = (16 * 13 + coverage_count + 47) // 48
    if 1 + len(batches) + 1 + maximum_rechecks > MAX_PLANNING_CALLS:
        raise ValueError('Complete review and required recheck exceed fixed Planning call range')
    messages = [review.checked_message(review.review_message(b)) for b in batches]
    for index, (batch, message) in enumerate(zip(batches, messages, strict=True)):
        response = invoke(f'B-{index:03}', message)
        initial_responses.append(response)
        answer_targets = review.answer_targets(response, batch)
        if answer_targets:
            response, output = repair(f'B-{index:03}', response, answer_targets, batch)
            lineage = {'stage': f'B-{index:03}', 'targets': descriptors(answer_targets), 'output': output}
        responses.append(review.validate_answers(response, batch))
    targets = review.semantic_targets(directory, responses)
    before_semantic = [r.model_dump(mode='json') for r in responses]
    if targets:
        value, output = repair('semantic', value, targets)
        lineage = {'stage': 'semantic', 'targets': descriptors(targets), 'output': output}
        proposal = parse_proposal(value, catalog)
        updated = review.questions(proposal, inputs, catalog)
        kept, pending = review.recheck(directory, responses, updated)
        pending_batches = review.review_batches(pending)
        messages = [review.checked_message(review.review_message(b)) for b in pending_batches]
        for i, (batch, message) in enumerate(zip(pending_batches, messages, strict=True)):
            for answer in review.validate_answers(invoke(f'B-recheck-{i:03}', message), batch).answers:
                kept[answer.question] = answer.model_dump(mode='json')
        directory = updated
        batches = review.review_batches(directory)
        responses = [review.validate_answers({'answers': [kept[q['question']] for q in b['questions']]}, b)
                     for b in batches]
        if review.semantic_targets(directory, responses):
            raise ValueError('Semantic review still challenged or unresolved after single shared repair')
    plan, requirements, proof = project_proposal(proposal, inputs=inputs, catalog=catalog,
        creation_id=attempt['creation_id'], attempt_id=attempt['attempt_id'],
        refs=planning_context['context_refs'], mode=mode)
    effective = review.compact(proposal.model_dump(mode='json')).encode()
    checkpoint = {'schema': CHECKPOINT, 'policy': POLICY, 'scope': scope,
        'initial': initial, 'initial_review_value': initial_review_value,
        'initial_responses': initial_responses, 'before_semantic': before_semantic,
        'repair': lineage, 'draft_sha256': hashlib.sha256(effective).hexdigest(),
        'raw_a_sha256': state['calls']['A']['reply_sha256'],
        'proposal': proposal.model_dump(mode='json'), 'plan': plan.model_dump(mode='json'),
        'proof': proof, 'review_sha256': authority.digest(directory),
        'responses': [r.model_dump(mode='json') for r in responses],
        'capture': {key: {k: v for k, v in call.items() if k != 'reply'}
                    for key, call in state['calls'].items()}}
    encoded = review.compact(checkpoint).encode()
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise ValueError('Complete frozen checkpoint exceeds local artifact capacity')
    frozen()
    # Existing atomic file writer: interrupted publication recovers captured
    # results only, and cannot replace different already-published artifacts.
    try:
        write_file(root, 'SEMANTIC_A_RESULT.json', state['calls']['A']['reply'].encode())
        write_file(root, 'SEMANTIC_PLAN.json', effective)
        write_file(root, 'SEMANTIC_CHECKPOINT.json', encoded)
        write_file(root, 'MATERIAL_PLAN.json', (plan.model_dump_json(indent=2) + '\n').encode())
        write_file(root, 'MATERIAL_REQUIREMENTS.json', review.compact(requirements).encode())
    except OSError:
        state['publication_result'] = 'PERSIST_FAILED'
        save()
        raise
    state['publication_result'] = 'ACCEPTED'
    save()
    from easel.output_contract import output_decision
    return {'plan': plan, 'context_refs': plan.context_refs, 'script': canonical['SCRIPT.md'],
            'scenes': canonical['SCENES.md'], 'treatment': canonical['TREATMENT.md'],
            'output_decision': output_decision('planning', 'ACCEPT', 'semantic_compiled', policy_revision=POLICY)}


def read_artifact(root, name, limit=MAX_CHECKPOINT_BYTES):
    path = Path(root) / 'planning' / name
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('vNext Planning artifact missing or unsafe')
    return path.read_bytes()


def verify(root, plan, mode, script, origin=None, *, canonical=None, attempt=None):
    raw = read_artifact(root, 'SEMANTIC_CHECKPOINT.json')
    checkpoint = json.loads(raw)
    if checkpoint.get('schema') != CHECKPOINT or checkpoint.get('policy') != POLICY:
        raise ValueError('Unknown vNext frozen contract; no downgrade')
    scope = checkpoint['scope']
    actual = canonical if canonical is not None else {name: read_artifact(root, name).decode()
                                                    for name in ('SCRIPT.md', 'SCENES.md', 'TREATMENT.md')}
    identities = origin or {'creation_id': plan.creation_id, 'attempt_id': plan.attempt_id, 'plan_id': plan.plan_id}
    if (attempt is None or Path(attempt['workspace']['path']).resolve() != Path(root).resolve()
            or attempt['creation_id'] != plan.creation_id or attempt['attempt_id'] != plan.attempt_id
            or scope['policy'] != POLICY or scope['creation_id'] != identities['creation_id']
            or scope['attempt_id'] != identities['attempt_id'] or scope['mode'] != mode
            or scope['context_refs'] != plan.context_refs or actual != scope['canonical']
            or actual['SCRIPT.md'] != script):
        raise ValueError('vNext actual Attempt, identity or frozen context changed')
    inputs = authority.load_inputs(attempt, actual, {'context_refs': scope['context_refs']}, mode,
                                   allow_missing_canonical=origin is not None)
    catalog = source_catalog(actual, {'creator_context': inputs['creator_context']})
    if inputs != scope['inputs'] or catalog != scope['catalog']:
        raise ValueError('vNext source binding cannot be reconstructed from frozen originals')
    initial = json.loads(read_artifact(root, 'SEMANTIC_A_RESULT.json', MAX_RESULT_BYTES))
    if (initial != checkpoint['initial'] or hashlib.sha256(read_artifact(root, 'SEMANTIC_A_RESULT.json', MAX_RESULT_BYTES)).hexdigest()
            != checkpoint['raw_a_sha256']):
        raise ValueError('vNext original captured A changed')
    value, lineage = initial, checkpoint['repair']
    if lineage and lineage['stage'] == 'A':
        targets = review.structural_targets(value)
        if descriptors(targets) != lineage['targets']: raise ValueError('A repair scope changed')
        value = review.apply_patches(value, lineage['output'], targets)
    proposal = parse_proposal(value, catalog)
    value = proposal.model_dump(mode='json')
    if value != checkpoint['initial_review_value']: raise ValueError('Accepted initial semantics changed')
    directory = review.questions(proposal, inputs, catalog)
    batches = review.review_batches(directory)
    originals = checkpoint['initial_responses']
    if len(originals) != len(batches): raise ValueError('Initial review coverage incomplete')
    responses = []
    for index, (response, batch) in enumerate(zip(originals, batches, strict=True)):
        if lineage and lineage['stage'] == f'B-{index:03}':
            targets = review.answer_targets(response, batch)
            if descriptors(targets) != lineage['targets']: raise ValueError('B repair scope changed')
            response = review.apply_patches(response, lineage['output'], targets)
        responses.append(review.validate_answers(response, batch))
    if [r.model_dump(mode='json') for r in responses] != checkpoint['before_semantic']:
        raise ValueError('Initial accepted review answers changed')
    targets = review.semantic_targets(directory, responses)
    if lineage and lineage['stage'] == 'semantic':
        if descriptors(targets) != lineage['targets']: raise ValueError('Semantic repair scope changed')
        value = review.apply_patches(value, lineage['output'], targets)
        proposal = parse_proposal(value, catalog)
    elif targets:
        raise ValueError('Challenged semantics cannot be frozen without a reviewed repair')
    updated = review.questions(proposal, inputs, catalog)
    kept, _ = review.recheck(directory, responses, updated)
    directory = updated
    batches = review.review_batches(directory)
    if len(checkpoint['responses']) != len(batches): raise ValueError('Final review coverage incomplete')
    responses = [review.validate_answers(r, b) for r, b in zip(checkpoint['responses'], batches, strict=True)]
    final_by_id = {a.question: a.model_dump(mode='json') for r in responses for a in r.answers}
    if any(final_by_id.get(index) != answer for index, answer in kept.items()):
        raise ValueError('Previously accepted unchanged semantic review was overwritten')
    if review.semantic_targets(directory, responses): raise ValueError('Final review not accepted')
    if not lineage or lineage['stage'] != 'semantic':
        if checkpoint['responses'] != checkpoint['before_semantic']: raise ValueError('Accepted review overwritten')
    effective = review.compact(proposal.model_dump(mode='json')).encode()
    if (checkpoint['proposal'] != proposal.model_dump(mode='json') or read_artifact(root, 'SEMANTIC_PLAN.json') != effective
            or hashlib.sha256(effective).hexdigest() != checkpoint['draft_sha256']
            or checkpoint['review_sha256'] != authority.digest(directory)):
        raise ValueError('vNext candidate or review identity changed')
    projected, requirements, proof = project_proposal(proposal, inputs=inputs, catalog=catalog,
        creation_id=scope['creation_id'], attempt_id=scope['attempt_id'], refs=scope['context_refs'], mode=mode)
    if (projected.plan_id != identities['plan_id'] or projected.model_dump(mode='json') != checkpoint['plan']
            or projected.model_copy(update={k: getattr(plan, k) for k in ('creation_id', 'attempt_id', 'plan_id')}) != plan
            or proof != checkpoint['proof'] or json.loads(read_artifact(root, 'MATERIAL_REQUIREMENTS.json')) != requirements):
        raise ValueError('Formal contract cannot be derived from accepted vNext semantics')
    return {'path': 'planning/SEMANTIC_CHECKPOINT.json', 'sha256': hashlib.sha256(raw).hexdigest(),
            'draft_sha256': checkpoint['draft_sha256'], 'policy': POLICY,
            **({'origin': origin} if origin else {})}
