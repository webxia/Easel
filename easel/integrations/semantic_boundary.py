"""vNext Planning semantic carriers and deterministic formal projections.

A proposes obligations, B reviews them, the application compiles. No model
maintains formal IDs, paths, hashes, aliases, authorization or artifacts.
"""
from __future__ import annotations

import hashlib
import json

from easel.integrations.planning_authority import digest
from easel.integrations.planning_facts import bind_facts, project_asset
from easel.materials.domain import MaterialPlan, MaterialNeed, VoiceNeedSpec, VoiceIdentityRef, VoiceIdentitySource
from easel.materials.application.visual_contract import sources_for, planning_contracts
from easel.materials.application.compiler import NeedCompiler

POLICY = 'planning-semantic-boundary@1'


from easel.integrations.planning_result_contract import SemanticProposal, NeedProposal, Condition, SoundIntent, FLEXIBLE_QUERY_POLICY


def _parse_candidate(value, catalog, *, allow_unresolved=False, query_diagnostics=False, flexible_queries=False):
    if isinstance(value, SemanticProposal):
        value = value.model_dump(mode='json')
    proposal = SemanticProposal.model_validate(value, context={
        'candidate_review_queries': query_diagnostics, 'flexible_queries': flexible_queries})
    if catalog.get('derived_voice') and (len(proposal.needs) > 15 or any(n.modality == 'voice' for n in proposal.needs)):
        raise ValueError('Confirmed preset Voice has one program producer; duplicate Voice or capacity overflow rejected')
    if proposal.unresolved and not allow_unresolved:
        raise ValueError('Unresolved semantic proposal cannot become a formal contract')
    scopes = {ref: kind for kind in ('global', 'scene', 'segment', 'event')
              for ref in catalog.get(kind, ())}
    for need in proposal.needs:
        if need.scope not in scopes:
            raise ValueError('Unknown frozen semantic scope')
        if not set(need.continuity_choices) <= set(catalog.get('continuity', ())):
            raise ValueError('Unknown frozen continuity choice')
        if any(not isinstance(catalog['continuity'][ref].get('kind'), str)
               for ref in need.continuity_choices):
            raise ValueError('Continuity choice lacks a frozen kind; no invented binding')
        if need.modality == 'voice' and need.voice_choice not in catalog.get('voice', {}):
            raise ValueError('Unknown frozen voice choice')
    if not allow_unresolved and not catalog.get('derived_voice') and not any(need.necessity == 'required' for need in proposal.needs):
        raise ValueError('At least one required Need must remain')
    return proposal


def parse_proposal(value, catalog, *, flexible_queries=False):
    """Formal admission always revalidates values under its frozen query policy."""
    return _parse_candidate(value, catalog, flexible_queries=flexible_queries)


def parse_review_candidate(value, catalog, *, query_diagnostics=False, flexible_queries=False):
    """Typed, reference-safe candidate; unresolved reports cannot authorize work."""
    return _parse_candidate(value, catalog, allow_unresolved=True,
                            query_diagnostics=query_diagnostics, flexible_queries=flexible_queries)


def project_proposal(proposal, *, inputs, catalog, creation_id, attempt_id, refs, mode, transport=None):
    """Only publish this projection after bounded review accepts its proposal."""
    # A review-only model instance must never bypass ordinary model validators.
    flexible_queries = (transport or {}).get('query_cardinality_policy') == FLEXIBLE_QUERY_POLICY
    proposal = parse_proposal(proposal.model_dump(mode='json'), catalog, flexible_queries=flexible_queries)
    facts = bind_facts(inputs)
    identity = digest({'policy': POLICY, 'proposal': proposal.model_dump(mode='json'),
                       'facts': facts['sha256'], 'creation_id': creation_id, 'attempt_id': attempt_id,
                       'refs': refs, 'mode': mode, **({'transport': transport} if transport is not None else {})})
    items = proposal.needs
    if catalog.get('derived_voice'):
        from easel.integrations.voice_identity import derived_need
        identity = digest({'planning_identity': identity, 'derived_voice': catalog['derived_voice']})
        items = (*items, derived_need(catalog))
    scopes = {ref: kind for kind in ('global', 'scene', 'segment', 'event')
              for ref in catalog.get(kind, ())}
    needs = []
    layouts = []
    for index, item in enumerate(items):
        visual = item.modality in {'image', 'video'}
        required = [c.text for c in item.conditions if c.responsibility == 'material' and c.strength == 'required']
        preferences = [c.text for c in item.conditions if c.responsibility == 'material' and c.strength == 'preference']
        other = [c.text for c in item.conditions if c.responsibility != 'material']
        if not required:
            raise ValueError('A material Need must retain an actual source obligation')
        projection = project_asset(facts, kind=item.modality, frame=item.frame,
            native_ratio=item.native_ratio, style=item.visual_preference, source_seconds=item.source_seconds)
        spec = projection['modality_spec']
        constraints = projection['constraints']
        if visual:
            if spec.get('aspect_ratio') is not None:
                # The current observation contract consumes literal constraint
                # sources. This alias is generated once, never maintained by A.
                constraints['aspect_ratio'] = spec['aspect_ratio']
            if item.queries:
                if flexible_queries and len(item.queries) < 3:
                    # Existing scalar discovery slots already support partial sets.
                    # Preserve each supplied query; never fill the absent slots.
                    from easel.materials.application.query_hints import LEGACY_QUERY_FIELDS
                    constraints.update(dict(zip(LEGACY_QUERY_FIELDS, item.queries)))
                else:
                    constraints['search_query_variants_en'] = dict(zip(('primary', 'alternate', 'relaxed'), item.queries))
            if preferences: constraints['preferred_visual_details'] = '\n'.join(preferences)
            if any(c.meaning == 'dynamic_action' and c.responsibility == 'material'
                   and c.strength == 'required' for c in item.conditions):
                constraints['requires_dynamic_action'] = True
        elif item.modality == 'voice':
            row = catalog['voice'][item.voice_choice]
            spec = VoiceNeedSpec(identity=VoiceIdentityRef(source=VoiceIdentitySource(row['source']), reference=item.voice_choice,
                reference_asset_ids=tuple(row.get('reference_asset_ids', ())), consent_ref=row.get('consent_ref')),
                delivery_description=item.voice_expression, text_ref='planning/SCRIPT.md',
                text_sha256=hashlib.sha256(inputs['confirmed']['SCRIPT.md'].encode()).hexdigest()).model_dump(mode='json')
            if catalog.get('derived_voice'):
                from easel.materials.application.voice_delivery import DEFAULT_DELIVERY
                constraints['voice_delivery'] = dict(mode.get('voice_delivery') or DEFAULT_DELIVERY)
                constraints['required_source_kind'] = 'generative'
        elif item.modality in {'bgm', 'sfx'}:
            keys = ('mood','genre','instruments','vocals_allowed','energy','tempo_bpm') if item.modality=='bgm' else (
                'event_description','sound_character','intensity','environment')
            spec.update({k:getattr(item.sound,k) for k in keys})
            constraints.update(required_source_kind='stock', allow_generation=False)
        function = '\n'.join([*other, *([item.purpose] if item.purpose else [])]) or None
        need = MaterialNeed.model_validate_json(json.dumps({'need_id':f'need-{identity[:24]}-{index:03}',
            'scope':{'type':scopes[item.scope], 'ref':item.scope}, 'media_type':projection['media_type'],
            'role':item.role, 'intent':{'description':'\n'.join(required), 'function':function},
            'importance':item.necessity, 'constraints':constraints, 'modality_spec':spec,
            'duration_hint':projection['duration_hint'], 'desired_options':1,
            'continuity_refs':[{'kind':catalog['continuity'][ref]['kind'],'ref':ref} for ref in item.continuity_choices]},ensure_ascii=False))
        needs.append(need)
        layouts.append({'need_id':need.need_id, 'candidate_index':index,
                        'conditions':[c.model_dump(mode='json') for c in item.conditions]})
    plan = MaterialPlan(plan_id='plan-'+identity[:32], creation_id=creation_id, attempt_id=attempt_id,
        context_refs=refs, policy={'strategy':'bulk_first','semantic_compiler':POLICY,
            **({'visual_requirements': 'visual-requirements@2'} if flexible_queries else {})}, needs=tuple(needs))
    from easel.integrations.semantic_planning import apply_defaults
    plan = apply_defaults(plan, mode, inputs['confirmed']['SCRIPT.md'])
    requirements = {}
    for item, need in zip(items, plan.needs, strict=True):
        NeedCompiler.for_plan(plan).compile(need)
        if need.media_type.value not in {'image','video'}: continue
        rows = []
        for source in sources_for(need):
            kind = 'preference' if source['preference'] else 'postproduction' if source['path']=='intent/function' else 'required'
            rows.append({'path':source['path'],'text':source['text'],'kind':kind,
                         'preference_path':source['path'] if source['preference'] else None})
        requirements[need.need_id] = {'clauses':rows,'queries':list(item.queries)}
    planning_contracts(plan,mode,requirements)
    return plan, requirements, {'facts':facts,'layouts':layouts,'identity':identity}
