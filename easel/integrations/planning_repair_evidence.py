"""New-only Shared Repair evidence wire; reversible frozen source-role choices.

The model chooses a frozen tuple. Only type/identity facts are projected;
textual quote content and semantic decisions always remain model-owned.
"""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from easel.integrations.planning_authority import digest
from easel.integrations.planning_result_contract import MAX_RESULT_BYTES, maximum_compact_bytes
from easel.integrations import planning_wire as wire

LEGACY_POLICY = 'planning-repair-evidence-ref@1'
POLICY = 'planning-repair-evidence-local-ref@2'


class RepairEvidenceProjection:
    def __init__(self, canonical, *, policy=POLICY):
        if policy not in (POLICY, LEGACY_POLICY):
            raise ValueError('Unknown frozen Repair evidence policy')
        self.policy = policy
        self.codec = wire.project(canonical, 'repair', atomic_framing=True)
        self.canonical = deepcopy(canonical)
        schema = deepcopy(self.codec.schema)
        self.choices = {}
        # Sort globally across this frozen schema, so the identical tuple gets
        # the same short code in every target, yet each target retains its own
        # complete, closed allowlist. This never expands candidate authority.
        tuples = set()
        for answer in schema['properties'].values():
            item = answer.get('properties', {}).get('support', {}).get('items', {})
            for branch in item.get('oneOf', []):
                props = branch.get('properties', {})
                for source in props.get('source', {}).get('enum', []):
                    for role in props.get('role', {}).get('enum', []):
                        tuples.add((source, role, props.get('quote', {}).get('type')))
        ordered = sorted(tuples)
        width = max(3, len(str(len(ordered) - 1)))
        local_codes = {triple: f'e{index:0{width}d}' for index, triple in enumerate(ordered)}
        for target, answer in schema['properties'].items():
            support = answer.get('properties', {}).get('support', {})
            item = support.get('items')
            if not isinstance(item, dict) or not isinstance(item.get('oneOf'), list):
                # Other target kinds retain their exact original representation.
                continue
            choices = {}
            quote_schema = None
            for branch in item['oneOf']:
                props = branch.get('properties', {})
                sources, roles = props.get('source', {}).get('enum'), props.get('role', {}).get('enum')
                quote = props.get('quote', {})
                kind = quote.get('type')
                if not isinstance(sources, list) or not isinstance(roles, list) or kind not in ('null', 'string'):
                    raise ValueError('Unprojectable frozen evidence branch')
                for source in sources:
                    for role in roles:
                        if not isinstance(source, str) or not isinstance(role, str):
                            raise ValueError('Invalid frozen evidence identity')
                        triple = (source, role, kind)
                        if triple in choices.values():
                            raise ValueError('Ambiguous frozen evidence branch')
                        ref = (local_codes[triple] if policy == POLICY else
                               'ev_' + digest({'target': target, 'source': source,
                                               'role': role, 'quote_kind': kind})[:24])
                        if ref in choices:
                            raise ValueError('Evidence reference hash collision')
                        choices[ref] = triple
                        if kind == 'string':
                            if quote_schema is not None and quote_schema != quote:
                                raise ValueError('Conflicting frozen textual quote schemas')
                            quote_schema = deepcopy(quote)
            if not choices:
                raise ValueError('Empty frozen evidence choice list')
            self.choices[target] = choices
            text_ids = [ref for ref, (_, _, kind) in choices.items() if kind == 'string']
            null_ids = [ref for ref, (_, _, kind) in choices.items() if kind == 'null']
            branches = []
            if text_ids:
                branches.append({'type': 'object', 'additionalProperties': False,
                    'properties': {'evidence_ref': {'type': 'string', 'enum': text_ids},
                                   'quote': quote_schema},
                    'required': ['evidence_ref', 'quote']})
            if null_ids:
                branches.append({'type': 'object', 'additionalProperties': False,
                    'properties': {'evidence_ref': {'type': 'string', 'enum': null_ids}},
                    'required': ['evidence_ref']})
            support['items'] = {'oneOf': branches}
            # Preserve the original ACCEPT => authority-source contains rule.
            # The output no longer exposes `role`; compile the same predicate
            # against the frozen refs instead of silently dropping it.
            for rule in answer.get('allOf', []):
                constraint = rule.get('then', {}).get('properties', {}).get('support', {})
                predicate = constraint.get('contains')
                if predicate is None:
                    continue
                allowed = predicate.get('properties', {}).get('role', {}).get('enum')
                if (predicate.get('type') != 'object' or predicate.get('required') != ['role']
                        or not isinstance(allowed, list) or set(predicate) != {'type', 'properties', 'required'}
                        or set(predicate['properties']) != {'role'}):
                    raise ValueError('Unprojectable Repair support contains condition')
                refs = [ref for ref, (_, role, _) in choices.items() if role in allowed]
                constraint['contains'] = {'type': 'object',
                    'properties': {'evidence_ref': {'enum': refs}},
                    'required': ['evidence_ref']}
        self.schema = schema
        Draft202012Validator.check_schema(schema)
        # For the finite estimator, these oneOf branches are disjoint by const.
        capacity = deepcopy(schema)
        for target in self.choices:
            capacity['properties'][target]['properties']['support']['items']['anyOf'] = (
                capacity['properties'][target]['properties']['support']['items'].pop('oneOf'))
        if maximum_compact_bytes(capacity) > MAX_RESULT_BYTES:
            raise ValueError('Evidence wire exceeds full result capacity')
        self.validator = Draft202012Validator(schema)
        self.identity = {**self.codec.identity, 'repair_evidence_policy': policy,
                         'wire_schema_sha256': digest(schema),
                         'original_repair_wire_sha256': self.codec.identity['wire_schema_sha256'],
                         **({'frozen_mapping_sha256': digest(self.choices)} if policy == POLICY else {})}

    def _to_original(self, value):
        if not isinstance(value, dict):
            raise ValueError('Repair root is not an object')
        mapped = deepcopy(value)
        for target, choices in self.choices.items():
            if target not in mapped or not isinstance(mapped[target], dict):
                raise ValueError('Missing repair target')
            support = mapped[target].get('support')
            if not isinstance(support, list):
                raise ValueError('Missing explicit model evidence choices')
            converted = []
            for item in support:
                if not isinstance(item, dict):
                    raise ValueError('Invalid evidence choice')
                ref = item.get('evidence_ref')
                if not isinstance(ref, str) or ref not in choices:
                    raise ValueError('Unknown evidence reference')
                source, role, kind = choices[ref]
                if kind == 'null':
                    if set(item) != {'evidence_ref'}:
                        raise ValueError('Non-text source must not carry a quote')
                    quote = None
                else:
                    if set(item) != {'evidence_ref', 'quote'}:
                        raise ValueError('Text source requires explicit quote')
                    quote = item['quote']
                converted.append({'source': source, 'role': role, 'quote': quote})
            mapped[target]['support'] = converted
        return mapped

    def errors(self, value):
        result = sorted([{'path': list(e.absolute_path), 'keyword': e.validator}
                         for e in self.validator.iter_errors(value)], key=repr)
        if result:
            return result
        try:
            mapped = self._to_original(value)
        except ValueError:
            return [{'path': [], 'keyword': 'evidence_ref'}]
        return self.codec.errors(mapped)

    def decode_valid(self, value):
        if self.errors(value):
            raise ValueError('Invalid frozen Repair Evidence projection')
        return self.codec.decode_valid(self._to_original(value))

    def decode_candidate(self, value):
        if self.errors(value):
            raise ValueError('Invalid Repair Evidence projection')
        return self.codec.decode_candidate(self._to_original(value))

    def encode(self, value):
        encoded = self.codec.encode(value)
        self.codec.decode_valid(encoded)
        reverse = {target: {tuple(v): k for k,v in choices.items()}
                   for target, choices in self.choices.items()}
        for target, pairs in reverse.items():
            result = []
            for item in encoded[target]['support']:
                kind = 'null' if item['quote'] is None else 'string'
                identity = (item['source'], item['role'], kind)
                if identity not in pairs:
                    raise ValueError('Canonical evidence lacks frozen reference')
                converted = {'evidence_ref': pairs[identity]}
                if kind == 'string':
                    converted['quote'] = item['quote']
                result.append(converted)
            encoded[target]['support'] = result
        if self.errors(encoded):
            raise ValueError('Evidence encoding violates frozen contract')
        return encoded
