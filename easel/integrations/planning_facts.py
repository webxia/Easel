"""Planning-local frozen facts and deterministic projections, not a Truth graph.

Equal values on different objects remain distinct facts. Candidate choices do
not create Creator authority; semantic support is reviewed before publication.
"""
from __future__ import annotations

from easel.integrations.planning_authority import digest

REVISION = 'planning-facts@1'


def bind_facts(inputs):
    if inputs.get('schema') != 'planning-authority-inputs@1':
        raise ValueError('Canonical facts require verified frozen inputs')
    proposal = inputs.get('proposal') or {}
    specs = proposal.get('specs') or {}
    rows = []

    def add(entity, meaning, value, authority, path, *, strength='fixed', responsibility='output'):
        if value is None:
            return
        rows.append({'entity': entity, 'scope': 'global', 'meaning': meaning,
            'value': value, 'strength': strength, 'responsibility': responsibility,
            'authority': authority, 'provenance': {'path': path, 'value_sha256': digest(value)}})

    for field, meaning in [('aspect_ratio', 'frame'), ('duration_seconds', 'duration'),
                           ('audio_mode', 'audio_mode'), ('language', 'language')]:
        add('final_output', meaning, specs.get(field), 'confirmed_spec', 'video_plan/specs/' + field)
    import json
    mode = json.loads(inputs['mode_documents']['mode.json'])
    add('material_style', 'visual_style', mode.get('visual_material_style'), 'frozen_mode',
        'mode.json/visual_material_style', strength='preference', responsibility='material')
    for name in ('SCRIPT.md', 'SCENES.md', 'TREATMENT.md'):
        add('confirmed_context', name, inputs['confirmed'][name], 'confirmed_original', name,
            responsibility='context')
    result = {'schema': REVISION, 'input_sha256': digest(inputs), 'facts': rows}
    return {**result, 'sha256': digest(result)}


def fact_value(bound, entity, meaning):
    rows = [row for row in bound['facts'] if row['entity'] == entity and row['meaning'] == meaning]
    if len(rows) > 1:
        raise ValueError('Duplicate canonical authority')
    return rows[0]['value'] if rows else None


def project_asset(bound, *, kind, frame='unconstrained', native_ratio=None,
                  style=None, source_seconds=None):
    """A single accepted choice produces aliases; final facts never imply it.

    ``match_output`` is a semantic choice, not an unconditional inheritance.
    Source duration is supplied independently of final/display duration.
    """
    if kind not in {'image', 'video', 'voice', 'bgm', 'sfx'}:
        raise ValueError('Unknown material modality')
    if frame not in {'unconstrained', 'match_output', 'native'}:
        raise ValueError('Unknown asset framing choice')
    if frame != 'native' and native_ratio is not None:
        raise ValueError('Aspect alias is not a separate choice')
    if frame != 'unconstrained' and kind not in {'image', 'video'}:
        raise ValueError('Audio cannot own a visual frame')
    ratio = (fact_value(bound, 'final_output', 'frame') if frame == 'match_output'
             else native_ratio if frame == 'native' else None)
    if frame != 'unconstrained' and (not isinstance(ratio, str) or not ratio.strip()):
        raise ValueError('Selected asset frame has no canonical value')
    if source_seconds is not None and (kind == 'image' or type(source_seconds) not in {int, float}
                                       or source_seconds <= 0):
        raise ValueError('Source duration must describe time-based media')
    style = style if style is not None else fact_value(bound, 'material_style', 'visual_style')
    modality = {'kind': kind}
    if ratio is not None:
        modality['aspect_ratio'] = ratio
    constraints = {}
    if style and kind in {'image', 'video'}:
        # Existing formal soft alias, always generated from the single value.
        constraints['preferred_style'] = style
        if kind == 'image':
            modality['visual_style'] = style
    return {'media_type': kind if kind in {'image', 'video'} else 'audio',
        'modality_spec': modality, 'constraints': constraints,
        'duration_hint': {'target_seconds': source_seconds} if source_seconds is not None else None}
