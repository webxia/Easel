"""Test-only producer experiment: representation safety, not model quality.

Only the explicitly authorized diagnostic evaluator may use this experiment;
it is never selected by product Planning. Original Condition leaves and
repair semantics stay unchanged. ACCEPT still requires the complete original
canonical schema and model. An invalid input is never cleaned into a valid one.
"""
from copy import deepcopy

from jsonschema import Draft202012Validator

from easel.integrations import planning_wire as wire
from easel.integrations.planning_result_contract import SemanticProposal

COMMON = {'scope', 'role', 'modality', 'necessity', 'conditions', 'purpose', 'continuity_choices'}
FIELDS = {modality: COMMON | fields for modality, fields in {
    'image': {'framing', 'visual_preference', 'queries'},
    'video': {'framing', 'visual_preference', 'queries', 'source_seconds'},
    'voice': {'voice_choice', 'voice_expression'},
    'bgm': {'sound', 'source_seconds'}, 'sfx': {'sound', 'source_seconds'},
}.items()}
SOUND = {'bgm': {'mood', 'genre', 'instruments', 'vocals_allowed', 'energy', 'tempo_bpm'},
         'sfx': {'event_description', 'sound_character', 'intensity', 'environment'}}


class ProducerUnionExperiment:
    def __init__(self, canonical):
        self.canonical = deepcopy(canonical)
        self.frame = wire.FrameProjection(canonical, 'A')
        need = self.frame.schema['properties']['needs']['items']
        branches = []
        for modality in canonical['$defs']['NeedProposal']['properties']['modality']['enum']:
            props = {key: deepcopy(value) for key, value in need['properties'].items()
                     if key in FIELDS[modality]}
            props['modality'] = {'type': 'string', 'const': modality}
            # Keep semantic decisions as separate leaves, with original local
            # repair granularity. These are constraints, not inferred values.
            required_source = {'properties': {'strength': {'const': 'required'},
                'responsibility': {'const': 'material'}}, 'required': ['strength', 'responsibility']}
            props['conditions']['contains'] = required_source
            if modality != 'video':
                props['conditions']['not'] = {'contains': {
                    'properties': {**required_source['properties'], 'meaning': {'const': 'dynamic_action'}},
                    'required': ['strength', 'responsibility', 'meaning']}}
            if modality in SOUND:
                sound = deepcopy(canonical['$defs']['SoundIntent'])
                sound['properties'] = {key: value for key, value in sound['properties'].items()
                                       if key in SOUND[modality]}
                if modality == 'sfx':
                    sound['required'] = ['event_description']
                    sound['properties']['event_description'] = {'type': 'string', 'minLength': 1, 'maxLength': 2000}
                    events = [rule['then']['properties']['scope']
                              for rule in canonical['$defs']['NeedProposal']['allOf']
                              if rule.get('if', {}).get('properties', {}).get('modality', {}).get('enum') == ['sfx']
                              and 'scope' in rule.get('then', {}).get('properties', {})]
                    if events:
                        props['scope'] = {**props['scope'], **events[0]} if isinstance(events[0], dict) else False
                props['sound'] = sound
            if modality == 'voice':
                props['voice_choice'] = next((branch for branch in props['voice_choice']['anyOf']
                                             if branch.get('type') == 'string'), False)
            if modality in {'image', 'video'}:
                props['queries']['allOf'] = [{'anyOf': [{'maxItems': 0}, {'minItems': 3, 'maxItems': 3}]}]
                props['queries']['items']['pattern'] = r'^[\x00-\x7f]*\S[\x00-\x7f]*$'
            required = [key for key in need['required'] if key in props]
            if modality in SOUND:
                required.append('sound')
            if modality == 'voice':
                required.append('voice_choice')
            branches.append({'type': 'object', 'title': modality + ' intent', 'additionalProperties': False,
                             'properties': props, 'required': required})
        producer = deepcopy(self.frame.schema)
        producer['properties']['needs']['items'] = {'type': 'object', 'anyOf': branches}
        self.codec = wire.Projection(producer, 'A')
        self.schema = self.codec.schema

    def encode(self, value):
        # Check before omitting canonical defaults: this is not a fixer for
        # the six illegal Voice Needs or polluted sound fields in real A.
        Draft202012Validator(self.canonical).validate(value)
        normalized = SemanticProposal.model_validate(value).model_dump(mode='json')
        encoded = self.frame.encode(normalized)
        for need in encoded['needs']:
            modality = need['modality']
            for key in list(need):
                if key not in FIELDS[modality]:
                    del need[key]
            if modality in SOUND:
                need['sound'] = {key: value for key, value in need['sound'].items() if key in SOUND[modality]}
        return self.codec.encode(encoded)

    def decode_candidate(self, value):
        # Same strict representation decoder as existing Planning. No strict
        # business-schema gate here, so local invalid leaves remain visible.
        return self.frame.decode_candidate(self.codec.decode_candidate(value))

    def decode(self, value):
        canonical = self.frame.decode_valid(self.codec.decode_valid(value))
        return SemanticProposal.model_validate(canonical).model_dump(mode='json')


class ShallowDetailsExperiment:
    """Test-only bijection: expose fixed detail slots as individual tool fields.

    No product dispatch selects this codec. It cannot repair strings, missing
    fields, semantic decisions, or an invalid original candidate.
    """
    POLICY = 'planning-shallow-details-experiment@1'

    def __init__(self, schema, binding):
        import re
        from easel.integrations.planning_authority import digest
        allowed = {'type', 'properties', 'required', 'additionalProperties', 'title', 'description', '$schema'}
        Draft202012Validator.check_schema(schema)
        if (set(schema) - allowed or schema.get('type') != 'object'
                or schema.get('additionalProperties') is not False
                or set(schema.get('properties', {})) != {'slots', 'unresolved'}
                or set(schema.get('required', [])) != {'slots', 'unresolved'}):
            raise ValueError('Unsupported complete details wrapper; never discard a constraint')
        slots = schema['properties']['slots']
        if (not isinstance(slots, dict) or set(slots) - allowed
                or slots.get('type') != 'object' or slots.get('additionalProperties') is not False
                or not 1 <= len(slots.get('properties', {})) <= 16
                or set(slots.get('required', [])) != set(slots['properties'])
                or any(not re.fullmatch(r'slot_[0-9]{3}', key) for key in slots['properties'])):
            raise ValueError('Unsupported fixed slot contract')
        self.original = deepcopy(schema)
        self.slots = tuple(slots['properties'])
        self.schema = {**deepcopy(schema),
            'properties': {**deepcopy(slots['properties']), 'unresolved': deepcopy(schema['properties']['unresolved'])},
            'required': [*self.slots, 'unresolved']}
        Draft202012Validator.check_schema(self.schema)
        self.identity = {'policy': self.POLICY, 'binding_sha256': digest(binding),
                         'original_schema_sha256': digest(self.original), 'wire_schema_sha256': digest(self.schema)}

    def encode(self, value):
        Draft202012Validator(self.original).validate(value)
        result = {**deepcopy(value['slots']), 'unresolved': deepcopy(value['unresolved'])}
        Draft202012Validator(self.schema).validate(result)
        return result

    def decode(self, value, identity):
        if identity != self.identity:
            raise ValueError('Shallow details belong to another frozen binding')
        Draft202012Validator(self.schema).validate(value)
        result = {'slots': {key: deepcopy(value[key]) for key in self.slots},
                  'unresolved': deepcopy(value['unresolved'])}
        Draft202012Validator(self.original).validate(result)
        return result


# Production codec under test; the historical single-union experiment above stays distinct.
from easel.integrations.planning_staged_proposal import StagedProposal as StagedProducerExperiment


# Offline experiments use the single reviewed implementation.
from easel.integrations.planning_input_view import (
    SourceSelection as SourceSelectionExperiment,
    PlanningInputView as PlanningInputViewExperiment,
)
