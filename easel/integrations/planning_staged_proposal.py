"""Versioned producer representation; canonical Material contracts are unchanged."""
from copy import deepcopy

POLICY = 'planning-staged-proposal@1'

from jsonschema import Draft202012Validator

from easel.integrations import planning_wire as wire
from easel.integrations.planning_result_contract import SemanticProposal, FLEXIBLE_QUERY_POLICY

COMMON = {'scope', 'role', 'modality', 'necessity', 'conditions', 'purpose', 'continuity_choices'}
FIELDS = {modality: COMMON | fields for modality, fields in {
    'image': {'framing', 'visual_preference', 'queries'},
    'video': {'framing', 'visual_preference', 'queries', 'source_seconds'},
    'voice': {'voice_choice', 'voice_expression'},
    'bgm': {'sound', 'source_seconds'}, 'sfx': {'sound', 'source_seconds'},
}.items()}
SOUND = {'bgm': {'mood', 'genre', 'instruments', 'vocals_allowed', 'energy', 'tempo_bpm'},
         'sfx': {'event_description', 'sound_character', 'intensity', 'environment'}}


class SpecializedProposal:
    def __init__(self, canonical):
        self.canonical = deepcopy(canonical)
        query_policy = canonical.get('x-easel-query-cardinality')
        if query_policy not in (None, FLEXIBLE_QUERY_POLICY):
            raise ValueError('Unknown staged query cardinality policy')
        self.flexible_queries = query_policy == FLEXIBLE_QUERY_POLICY
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
                props['queries']['allOf'] = ([{'maxItems': 3}] if self.flexible_queries else
                    [{'anyOf': [{'maxItems': 0}, {'minItems': 3, 'maxItems': 3}]}])
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
        normalized = SemanticProposal.model_validate(value, context={'flexible_queries': self.flexible_queries}).model_dump(mode='json')
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
        return SemanticProposal.model_validate(canonical, context={'flexible_queries': self.flexible_queries}).model_dump(mode='json')


class StagedProposal:
    """Two candidate representations; never semantic approval or a new repair policy."""
    HEADER = frozenset({'scope', 'role', 'modality', 'necessity', 'continuity_choices'})

    def __init__(self, canonical):
        self.union = SpecializedProposal(canonical)
        branches = self.union.schema['properties']['needs']['items']['anyOf']
        self.branches = {b['properties']['modality']['const']: b for b in branches}
        # Header constraints are common except for the selected modality.
        common = self.union.frame.schema['properties']['needs']['items']
        self.selection_schema = {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'needs': {'type': 'array', 'minItems': 1,
                    'maxItems': canonical['properties']['needs']['maxItems'],
                    'items': {'type': 'object', 'additionalProperties': False,
                        'properties': {k: deepcopy(common['properties'][k]) for k in sorted(self.HEADER)},
                        'required': sorted(self.HEADER)}},
                'unresolved': deepcopy(self.union.schema['properties']['unresolved']),
            }, 'required': ['needs', 'unresolved'],
        }
        Draft202012Validator.check_schema(self.selection_schema)

    @classmethod
    def shape(cls, value, schema):
        """Reject identity/container damage without suppressing leaf diagnostics."""
        if isinstance(schema, bool):
            # Boolean schemas have no shape. Preserve invalid values for the
            # existing diagnostics; strict validation still enforces False.
            return
        if schema.get('type') == 'object':
            if not isinstance(value, dict):
                raise ValueError('Expected candidate object')
            props = schema.get('properties', {})
            if set(value) - set(props) or set(schema.get('required', ())) - set(value):
                raise ValueError('Candidate properties changed')
            for key, item in value.items():
                cls.shape(item, props[key])
        elif schema.get('type') == 'array':
            if not isinstance(value, list):
                raise ValueError('Expected candidate array')
            for item in value:
                cls.shape(item, schema.get('items', {}))

    def details_contract(self, selection, *, diagnostic=False):
        from easel.integrations.planning_authority import digest
        if diagnostic:
            self.shape(selection, self.selection_schema)
            if not 1 <= len(selection['needs']) <= self.selection_schema['properties']['needs']['maxItems']:
                raise ValueError('Candidate count exceeds original contract')
        else:
            Draft202012Validator(self.selection_schema).validate(selection)
        slots = {}
        for i, need in enumerate(selection['needs']):
            if not isinstance(need['modality'], str) or need['modality'] not in self.branches:
                raise ValueError('Unknown modality cannot select a details contract')
            branch = self.branches[need['modality']]
            # Candidate headers cannot be echoed or replaced by details.
            # Later B/repair still owns its original canonical repair domain.
            if not diagnostic:
                Draft202012Validator({'type': 'object', 'additionalProperties': False,
                    'properties': {k: branch['properties'][k] for k in sorted(self.HEADER)},
                    'required': sorted(self.HEADER)}).validate(need)
            if set(branch) - {'type', 'title', 'properties', 'required', 'additionalProperties'}:
                raise ValueError('Unsupported specialized header/detail predicate')
            slots[f'slot_{i:03}'] = {
                **{k: deepcopy(v) for k, v in branch.items() if k not in {'properties', 'required'}},
                'properties': {k: deepcopy(v) for k, v in branch['properties'].items() if k not in self.HEADER},
                'required': [k for k in branch['required'] if k not in self.HEADER],
            }
        schema = {'type': 'object', 'additionalProperties': False,
            'properties': {
                'slots': {'type': 'object', 'additionalProperties': False,
                          'properties': slots, 'required': list(slots)},
                'unresolved': deepcopy(self.union.schema['properties']['unresolved']),
            }, 'required': ['slots', 'unresolved']}
        Draft202012Validator.check_schema(schema)
        return {'schema': schema, 'identity': {
            'policy': POLICY, 'selection_sha256': digest(selection),
            'schema_sha256': digest(schema), 'canonical_sha256': digest(self.union.canonical)}}

    def encode(self, canonical):
        value = self.union.encode(canonical)  # Reject historical errors before splitting.
        selection = {'needs': [{k: deepcopy(v) for k, v in n.items() if k in self.HEADER}
                                for n in value['needs']], 'unresolved': deepcopy(value['unresolved'])}
        details = {'slots': {f'slot_{i:03}': {k: deepcopy(v) for k, v in n.items() if k not in self.HEADER}
                            for i, n in enumerate(value['needs'])}, 'unresolved': []}
        receipt = self.details_contract(selection)['identity']
        return selection, details, receipt

    @staticmethod
    def parse_raw(raw):
        import json
        def unique(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError('Duplicate candidate or detail slot key')
                value[key] = item
            return value
        return json.loads(raw, object_pairs_hook=unique)

    def assemble(self, selection, details, receipt_identity):
        contract = self.details_contract(selection)
        if receipt_identity != contract['identity']:
            raise ValueError('Detail result belongs to another selection or contract')
        Draft202012Validator(contract['schema']).validate(details)
        value = {'needs': [{**deepcopy(n), **deepcopy(details['slots'][f'slot_{i:03}'])}
                           for i, n in enumerate(selection['needs'])],
                 'unresolved': [*selection['unresolved'], *details['unresolved']]}
        return self.union.decode(value)

    def assemble_candidate(self, selection, details, receipt_identity):
        """Not ACCEPT: preserve local faults for the one existing shared repair."""
        contract = self.details_contract(selection, diagnostic=True)
        if receipt_identity != contract['identity']:
            raise ValueError('Detail result belongs to another selection or contract')
        self.shape(details, contract['schema'])
        value = {'needs': [{**deepcopy(n), **deepcopy(details['slots'][f'slot_{i:03}'])}
                           for i, n in enumerate(selection['needs'])],
                 'unresolved': [*selection['unresolved'], *details['unresolved']]}
        return self.union.decode_candidate(value)


def _read_only_staged(canonical):
    """Compile an exact staged schema once per frozen read, never across runs.

    Callers must not mutate the returned codec or its schema objects. All
    validation/decoding still runs against each original reply independently.
    """
    return wire._scoped_compile('staged', canonical, (), lambda: StagedProposal(canonical))
