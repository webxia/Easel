"""Test-only producer experiment: representation safety, not model quality.

Only the explicitly authorized diagnostic evaluator may use this experiment;
it is never selected by product Planning. Original Condition leaves and
repair semantics stay unchanged. ACCEPT still requires the complete original
canonical schema and model. An invalid input is never cleaned into a valid one.
"""
from copy import deepcopy
import hashlib

from jsonschema import Draft202012Validator

from easel.integrations import planning_wire as wire
from easel.integrations.planning_result_contract import SemanticProposal
from easel.integrations.planning_input_view import SourceSelection, PlanningInputView


class SourceKindSelectionExperiment(SourceSelection):
    """Bijective source names, only for explicit bounded diagnostics."""
    POLICY = 'planning-source-kind-handles-experiment@1'

    def __init__(self, canonical, catalog):
        from easel.integrations.planning_authority import digest
        super().__init__(canonical, catalog)
        aliases = {old: ref['kind'] + '_' + old.removeprefix('src_')
                   for old, ref in self.references.items()}
        if any(not h.startswith('src_') for h in aliases) or len(set(aliases.values())) != len(aliases):
            raise ValueError('Source kind alias collision')
        self.to_wire = {source: aliases[handle] for source, handle in self.to_wire.items()}
        self.references = {aliases[handle]: ref for handle, ref in self.references.items()}
        self.schema['properties']['needs']['items']['properties']['scope']['enum'] = list(self.references)
        self.identity = {'policy': self.POLICY, 'catalog_sha256': digest(catalog),
                         'schema_sha256': digest(self.schema), 'mapping_sha256': digest(self.references)}


class SourceKindInputViewExperiment(PlanningInputView):
    POLICY = 'planning-input-kind-view-experiment@1'

    def __init__(self, inputs, catalog):
        from easel.integrations import planning_authority as authority
        from easel.integrations.planning_result_contract import semantic_tool_schema
        super().__init__(inputs, catalog)
        original = self.decode(self.view, self.identity)
        old_codec = self.codec
        self.codec = SourceKindSelectionExperiment(semantic_tool_schema(catalog, compiled=True), catalog)
        aliases = {handle: self.codec.to_wire[ref['original']]
                   for handle, ref in old_codec.references.items()}
        document = self.view['inputs']['confirmed']['SCENES.md']
        for line in document['lines']:
            if 'choices' in line:
                line['choices'] = {kind: aliases[handle] for kind, handle in line['choices'].items()}
        document['whole_document'] = aliases[document['whole_document']]
        self.identity = {**self.identity, 'view_sha256': authority.digest(self.view),
            'lineage_sha256': authority.digest({'metadata': self.metadata, 'links': self.links,
                                               'scope_mapping': self.codec.references})}
        if self.decode(self.view, self.identity) != original:
            raise ValueError('Source kind view is not exactly reversible')


def equivalent_schema_experiment(original):
    """Offline only: two assertion-equivalent rewrites, never value repairs.

    P AND P == P removes only the exact duplicate array maxItems conjunct.
    (type T AND C_T) OR null == type [T,null] AND C_T when every C_T
    keyword ignores null. Only primitive type-specific assertions qualify;
    enum/const, references, annotations within branches and applicators do not.
    Parent annotations and instance/property order stay untouched. No traversal
    into instance-valued defaults/enum/const or protected oneOf/not/contains.
    This proves assertion equivalence, not identical validator error paths or
    Provider quality. Product dispatch never imports this function.
    """
    Draft202012Validator.check_schema(original)
    changes = []
    primitives = {
        'string': {'minLength', 'maxLength', 'pattern'},
        'number': {'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf'},
        'integer': {'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf'},
        'boolean': set(),
    }

    def visit(node, path):
        if not isinstance(node, dict):
            return deepcopy(node)
        out = deepcopy(node)
        for key in ('properties', '$defs', 'definitions', 'patternProperties', 'dependentSchemas'):
            if key in out:
                out[key] = {k: visit(v, (*path, key, k)) for k, v in out[key].items()}
        for key in ('items', 'additionalProperties'):
            if isinstance(out.get(key), (dict, bool)):
                out[key] = visit(out[key], (*path, key))
        for key in ('prefixItems', 'allOf', 'anyOf'):
            if key in out:
                out[key] = [visit(v, (*path, key, i)) for i, v in enumerate(out[key])]
        if (out.get('type') == 'array' and 'maxItems' in out
                and out.get('allOf') == [{'maxItems': out['maxItems']}]):
            del out['allOf']
            changes.append({'rule': 'duplicate_max_items', 'path': list(path)})
        branches = out.get('anyOf')
        if (set(out) <= {'anyOf', 'type', 'title', 'description', 'default'}
                and isinstance(branches, list) and len(branches) == 2):
            nulls = [b for b in branches if b == {'type': 'null'}]
            nonnull = [b for b in branches if b != {'type': 'null'}]
            if len(nulls) == len(nonnull) == 1 and isinstance(nonnull[0], dict):
                branch = nonnull[0]
                kind = branch.get('type')
                parent_type = out.get('type', [kind, 'null'])
                if (isinstance(kind, str) and kind in primitives
                        and set(branch) <= {'type', *primitives[kind]}
                        and isinstance(parent_type, list) and set(parent_type) == {kind, 'null'}):
                    # Preserve an existing type-list order; otherwise follow
                    # original branch order. Other annotations are not moved.
                    out.pop('anyOf')
                    out['type'] = deepcopy(parent_type) if 'type' in node else [b['type'] for b in branches]
                    out.update({k: deepcopy(v) for k, v in branch.items() if k != 'type'})
                    changes.append({'rule': 'primitive_nullable', 'path': list(path)})
        return out

    candidate = visit(original, ())
    Draft202012Validator.check_schema(candidate)
    return candidate, changes


def source_scope_selection_experiment(codec):
    """Test-only preflight of existing modality scope assertions.

    Handles, source choices and values are untouched. A missing source set
    remains False; no source is inferred, changed, created or repaired.
    """
    from easel.integrations.planning_authority import digest
    result = deepcopy(codec.schema)
    header = result['properties']['needs']['items']
    branches = []
    for modality in header['properties']['modality']['enum']:
        branch = codec.staged.branches[modality]
        scope = branch['properties']['scope']
        if scope is False:
            allowed = False
        else:
            if (not isinstance(scope, dict) or 'enum' not in scope
                    or set(scope) - {'type', 'title', 'minLength', 'maxLength', 'enum'}):
                raise ValueError('Unknown source constraint cannot be approximated')
            if any(name not in codec.to_wire for name in scope['enum']):
                raise ValueError('Canonical source constraint has no exact handle')
            handles = [codec.to_wire[name] for name in scope['enum']]
            allowed = {'type': 'string', 'enum': handles} if handles else False
        specialized = deepcopy(header)
        specialized['properties']['modality'] = {'type': 'string', 'const': modality}
        specialized['properties']['scope'] = allowed
        branches.append(specialized)
    # Disjoint modality constants make exactly one branch eligible. Every
    # original header assertion remains within each closed branch; only the
    # already enforced source constraint moves to the directly visible field.
    result['properties']['needs']['items'] = {**header, 'anyOf': branches}
    Draft202012Validator.check_schema(result)
    return result, {'policy': 'planning-source-scope-experiment@3',
                    'base_codec_identity': deepcopy(codec.identity), 'schema_sha256': digest(result)}


def source_scope_message_experiment(message, codec):
    """Replace conflicting scope guidance, retaining every frozen input byte.

    No source is selected or inferred. This is a separate test-only request
    version; old messages and production dispatch are never rewritten.
    """
    import json
    from easel.integrations.planning_authority import digest
    instruction, body = message.rsplit('\n', 1)
    context = json.loads(body)
    old = 'scope必须选择原文旁对应kind的src引用，它是文本位置而非镜头编号。'
    expected = 'scope选择工具enum中的实际使用范围，不是声音原文的出处或字节区间。全片素材可选global_scope；局部素材可选对应场景引用。原文支持由完整冻结内容核对，不根据范围数字拼造src引用。'
    if (not message.startswith('〔Easel Semantic Planning vNext A-selection〕')
            or instruction.count(old) != 1
            or context.get('scope_reference_contract', {}).get('instruction') != expected):
        raise ValueError('Unknown guidance cannot be silently replaced')
    allowed = {}
    for modality in codec.schema['properties']['needs']['items']['properties']['modality']['enum']:
        source = codec.staged.branches[modality]['properties']['scope']
        handles = [] if source is False else [codec.to_wire[name] for name in source['enum']]
        allowed[modality] = {'handles': handles,
                            'kinds': sorted({codec.references[h]['kind'] for h in handles})}
    contract = context['scope_reference_contract']
    contract['instruction'] = ('scope绑定冻结文本位置和来源种类，不是素材使用点位或镜头编号。'
        '逐模态只从allowed_scope的handles中选择；原文行choices给出这些句柄。'
        'SFX只能选其允许的event引用，同文scene与event不是可互换身份；'
        '其他模态按各自允许集合选择，不增添范围限制。'
        '时序及镜头对齐另由后期处理；语义支持仍核对完整冻结内容，不由kind自动通过。'
        '不得按镜头数字拼造引用，也不得自动改写已选择的来源。')
    contract['allowed_scope'] = allowed
    binding = {'policy': 'planning-source-scope-guidance-experiment@1',
               'base_message_sha256': hashlib.sha256(message.encode()).hexdigest(),
               'allowed_scope_sha256': digest(allowed)}
    context['source_scope_guidance_binding'] = binding
    updated = instruction.replace(old, 'scope按scope_reference_contract选择冻结文本位置和模态允许来源种类的src引用，不是镜头编号。')
    result = updated + '\n' + json.dumps(context, ensure_ascii=False, separators=(',', ':'))
    return result, {**binding, 'message_sha256': hashlib.sha256(result.encode()).hexdigest()}


def validate_source_scope_diagnostic_cell(cell, item, manifest, scope):
    """Rebuild both variants before any diagnostic HTTP reservation."""
    import json
    from easel.integrations import semantic_boundary_run as boundary
    from easel.integrations.planning_authority import digest
    policies = {'L': SourceSelection.POLICY, 'K': SourceKindSelectionExperiment.POLICY}
    variant = item.get('variant')
    if (variant not in policies or cell.get('source_codec_policy') != policies[variant]
            or type(cell.get('number')) is not int or cell['number'] != item.get('number')
            or cell.get('variant') != variant or cell.get('identity') != item.get('identity')):
        raise ValueError('Diagnostic cell identity changed')
    view = (SourceKindInputViewExperiment if variant == 'K' else PlanningInputView)(scope['inputs'], scope['catalog'])
    schema, binding = source_scope_selection_experiment(view.codec)
    schema = boundary.intake_selection(scope, schema)
    binding.update(schema_sha256=digest(schema), scope_sha256=digest(scope), input_view_identity=view.identity)
    message, _ = source_scope_message_experiment(boundary.view_a_message(scope, view, 'A-selection'), view.codec)
    message += '\n独立生产外来源约束实验身份：' + json.dumps(binding, ensure_ascii=False, separators=(',', ':'))
    if (cell.get('experimental_binding') != binding
            or manifest.get('experimental_bindings', {}).get(variant) != binding
            or cell.get('schema') != schema or item.get('schema_sha256') != digest(schema)
            or cell.get('message') != message
            or item.get('message_sha256') != hashlib.sha256(message.encode()).hexdigest()):
        raise ValueError('Diagnostic cell binding changed')
    return view

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
