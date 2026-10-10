"""Lossless Planning wire projection for XML-backed function arguments.

Canonical contracts remain unchanged. This codec removes local references and
represents required nullable values explicitly; it never repairs semantics.
Invalid business leaves remain diagnostic candidates for the existing repair.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import json

from jsonschema import Draft202012Validator

from easel.integrations.planning_authority import digest
from easel.integrations.planning_result_contract import MAX_RESULT_BYTES, maximum_compact_bytes

POLICY = 'planning-xml-wire@1'
GUIDANCE = ('工具Schema已经展开引用。必填可空值用且只用 {"null":true} 或 {"value":非空原值}；'
            '字符串 "null" 是普通文本。数组直接提交数组，不使用 item 包装。')

# Cache only pure compiled schema representations within one synchronous,
# read-only checkpoint traversal. Do not cache accepted replies, source facts,
# execution fingerprints or Material readiness. No process-wide retention.
_SCHEMA_READ_CACHE: ContextVar[dict | None] = ContextVar('easel_planning_schema_read_cache', default=None)


@contextmanager
def _schema_read_scope():
    if _SCHEMA_READ_CACHE.get() is not None:
        yield
        return
    token = _SCHEMA_READ_CACHE.set({})
    try:
        yield
    finally:
        _SCHEMA_READ_CACHE.reset(token)


def _scoped_compile(kind, canonical, variant, factory):
    cache = _SCHEMA_READ_CACHE.get()
    if cache is None:
        return factory()
    try:
        # Exact JSON content prevents a hash collision or differing schema from
        # sharing a codec. Cached instances are internal read-only codecs.
        key = (kind, variant, json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':'), allow_nan=False))
    except (TypeError, ValueError):
        return factory()  # Keep the original schema rejection behavior.
    cached = cache.get(key)
    if cached is not None:
        return cached
    compiled = factory()
    if len(cache) < 64:
        cache[key] = compiled
    return compiled



def _types(schema):
    value = schema.get('type')
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return set(value)
    if 'anyOf' in schema:
        branches = [_types(item) for item in schema['anyOf']]
        if all(branches):
            return set.union(*branches)
    if 'allOf' in schema:
        branches = [types for item in schema['allOf'] if (types := _types(item))]
        if branches:
            return set.intersection(*branches)
    return set()


def _hints(schema):
    """Only redundant consequences, never removal of a branch constraint."""
    branches = schema.get('allOf', [])
    for branch in branches:
        for key in ('type', 'properties', 'items', 'prefixItems'):
            if key in branch and key not in schema:
                schema[key] = deepcopy(branch[key])
    branches = schema.get('anyOf', [])
    types = _types(schema)
    nonnull = [b for b in branches if _types(b) != {'null'}]
    # Never coerce a nullable string's legal literal "null" to JSON null.
    if (types and 'type' not in schema and len(nonnull) == 1
            and types <= {'null', 'array', 'object', 'integer', 'number', 'boolean'}):
        schema['type'] = sorted(types)
        for key in ('properties', 'items', 'prefixItems'):
            if key in nonnull[0]:
                schema[key] = deepcopy(nonnull[0][key])
    return schema


class Projection:
    def __init__(self, canonical, stage):
        self.canonical = deepcopy(canonical)
        self.stage = stage
        def inline(node, stack=()):
            if isinstance(node, list):
                return [inline(value, stack) for value in node]
            if not isinstance(node, dict):
                return node
            if '$ref' in node:
                ref = node['$ref']
                if not isinstance(ref, str) or not ref.startswith('#/$defs/') or ref in stack:
                    raise ValueError('Planning wire requires finite local nonrecursive references')
                name = ref[len('#/$defs/'):]
                if '/' in name or name not in canonical.get('$defs', {}):
                    raise ValueError('Unknown Planning wire reference')
                target = inline(canonical['$defs'][name], (*stack, ref))
                siblings = inline({k: v for k, v in node.items() if k != '$ref'}, stack)
                return _hints({'allOf': [target, siblings]}) if siblings else target
            return _hints({key: inline(value, stack) for key, value in node.items() if key != '$defs'})

        def project(node, required=False):
            if not isinstance(node, dict):
                return node, {}
            types = _types(node)
            if required and 'null' in types and types != {'null'}:
                null_allowed = Draft202012Validator(node).is_valid(None)
                # Preserve every original constraint at the value position.
                value, tree = project(node, False)
                value = _hints({'allOf': [value, {'not': {'type': 'null'}}],
                                'type': sorted(types - {'null'})})
                null_branch = {'type': 'object', 'additionalProperties': False,
                               'properties': {'null': {'type': 'boolean', 'const': True}}, 'required': ['null']}
                value_branch = {'type': 'object', 'additionalProperties': False,
                                'properties': {'value': value}, 'required': ['value']}
                wire = {'type': 'object', 'additionalProperties': False,
                    'properties': {'null': {'type': 'boolean', 'const': True} if null_allowed else False, 'value': value},
                    'anyOf': [null_branch if null_allowed else False, value_branch]}
                if 'default' in node:
                    if not Draft202012Validator(node).is_valid(node['default']):
                        raise ValueError('Planning wire default conflicts with the complete canonical schema')
                    wire['default'] = ({'null': True} if node['default'] is None else
                                       {'value': self._transform(node['default'], tree, True)})
                return wire, {'wrap': True, 'null_allowed': null_allowed, 'value': tree}
            out, tree = deepcopy(node), {}
            children = {}
            for key, child in node.get('properties', {}).items():
                out['properties'][key], child_tree = project(child, key in node.get('required', []))
                if child_tree:
                    children[key] = child_tree
            if children:
                # Moving instance positions beneath value cannot leave sibling
                # predicates referring to the old shape. Reject unsupported
                # combinations at construction instead of dropping predicates.
                if any(k in node for k in ('allOf', 'anyOf', 'oneOf', 'not', 'if', 'then', 'else',
                                           'dependentSchemas', 'dependencies', 'const', 'enum')):
                    raise ValueError('Nullable wire field has unsupported cross-field predicates')
                tree['properties'] = children
            if isinstance(node.get('items'), dict):
                out['items'], child = project(node['items'], True)
                if child:
                    tree['items'] = child
            if 'prefixItems' in node:
                rows = [project(child, True) for child in node['prefixItems']]
                out['prefixItems'] = [schema for schema, _ in rows]
                if any(child for _, child in rows):
                    tree['prefixItems'] = [child for _, child in rows]
            for keyword in ('anyOf', 'allOf', 'oneOf'):
                if keyword in node:
                    rows = [project(child, False) for child in node[keyword]]
                    out[keyword] = [schema for schema, _ in rows]
                    if any(child for _, child in rows):
                        raise ValueError('Ambiguous union contains a nullable wire field')
            return out, tree

        self.schema, self.tree = project(inline(canonical), True)
        Draft202012Validator.check_schema(self.schema)
        # Finite capacity is still measured, never clipped to fit transport.
        if maximum_compact_bytes(self.schema) > MAX_RESULT_BYTES:
            raise ValueError('Projected Planning wire exceeds full result capacity')
        self.validator = Draft202012Validator(self.schema)
        self.identity = {'stage': stage, 'codec_policy': POLICY,
                         'canonical_schema_sha256': digest(canonical), 'wire_schema_sha256': digest(self.schema)}

    def errors(self, value):
        # No candidate values or arbitrary exception prose in diagnostics.
        return sorted([{'path': list(e.absolute_path), 'keyword': e.validator}
                       for e in self.validator.iter_errors(value)], key=lambda e: repr(e))

    def _transform(self, value, tree, encode):
        if tree.get('wrap'):
            if encode:
                return {'null': True} if value is None else {'value': self._transform(value, tree['value'], True)}
            if not isinstance(value, dict):
                raise ValueError('Required nullable wire value must use an explicit branch')
            if set(value) == {'null'} and value['null'] is True and tree['null_allowed']:
                return None
            if set(value) == {'value'} and value['value'] is not None:
                return self._transform(value['value'], tree['value'], False)
            raise ValueError('Invalid nullable wire branch; no guessed value')
        if isinstance(value, dict):
            return {key: self._transform(item, tree.get('properties', {}).get(key, {}), encode)
                    for key, item in value.items()}
        if isinstance(value, list):
            prefix = tree.get('prefixItems', [])
            return [self._transform(item, prefix[i] if i < len(prefix) else tree.get('items', {}), encode)
                    for i, item in enumerate(value)]
        return value

    def decode_candidate(self, value):
        """Strict representation decode; business errors are never corrected."""
        return self._transform(value, self.tree, False)

    def decode_valid(self, value):
        if self.errors(value):
            raise ValueError('Planning repair wire does not satisfy its complete schema')
        result = self.decode_candidate(value)
        if not Draft202012Validator(self.canonical).is_valid(result):
            raise ValueError('Decoded Planning wire violates its complete canonical schema')
        return result

    def encode(self, value):
        """Used by offline provider fixtures; production only decodes."""
        return self._transform(value, self.tree, True)


FRAME_POLICY = 'planning-atomic-framing@1'
FRAME_GUIDANCE = ('画幅只提交一个framing选择：{"mode":"unconstrained"}、'
                  '{"mode":"match_output"}或{"mode":"native","ratio":"4:5"}。'
                  'native的ratio是独立源画幅；不再提交frame/native_ratio两个字段。')


def _frame_schema(canonical):
    """Change only declared Need schemas; retain all other predicates.

    The one removed predicate is exactly the native/pair constraint represented
    by the tagged union. Unknown pair predicates fail request construction.
    """
    native_rule = {'if': {'properties': {'frame': {'const': 'native'}}, 'required': ['frame']},
                   'then': {'required': ['native_ratio'], 'properties': {'native_ratio': {'type': 'string'}}},
                   'else': {'properties': {'native_ratio': {'type': 'null'}}}}
    def visit(node):
        if isinstance(node, list): return [visit(child) for child in node]
        if not isinstance(node, dict): return node
        out = deepcopy(node)
        if node.get('title') == 'NeedProposal':
            properties = out['properties']
            if properties['frame'].get('enum') != ['unconstrained', 'match_output', 'native']:
                raise ValueError('Unknown canonical frame choices')
            ratio = properties.pop('native_ratio')
            properties.pop('frame')
            properties['framing'] = {
                'type': 'object', 'additionalProperties': False,
                'properties': {'mode': {'type': 'string', 'enum': ['unconstrained', 'match_output', 'native']},
                               'ratio': next(deepcopy(b) for b in ratio['anyOf'] if b.get('type') == 'string')},
                'required': ['mode'], 'default': {'mode': 'unconstrained'},
                'oneOf': [
                    {'properties': {'mode': {'enum': ['unconstrained', 'match_output']}},
                     'not': {'required': ['ratio']}},
                    {'properties': {'mode': {'const': 'native'}}, 'required': ['ratio']}],
            }
            properties['framing']['description'] = 'One independent source frame choice; output specs do not imply native ratio.'
            rules = []
            for rule in out.get('allOf', []):
                if rule == native_rule:
                    continue  # Proven equivalent on the valid instance set.
                changed = deepcopy(rule)
                props = changed.get('then', {}).get('properties', {})
                if 'frame' in props or 'native_ratio' in props:
                    if (props.get('frame') != {'const': 'unconstrained'}
                            or props.get('native_ratio') != {'type': 'null'}):
                        raise ValueError('Unsupported canonical frame predicate')
                    props.pop('frame'); props.pop('native_ratio')
                    props['framing'] = {'properties': {'mode': {'const': 'unconstrained'}}}
                # A future predicate cannot silently keep a stale split path.
                def split_path(value):
                    return (any(key in {'frame', 'native_ratio'} or split_path(child)
                                for key, child in value.items()) if isinstance(value, dict)
                            else any(map(split_path, value)) if isinstance(value, list) else False)
                if split_path(changed):
                    raise ValueError('Unmapped canonical frame predicate')
                rules.append(changed)
            if rules: out['allOf'] = rules
        return {key: visit(value) for key, value in out.items()}
    return visit(canonical)


def _frame_tree(schema):
    definitions = schema.get('$defs', {})
    def split_predicate(node):
        if not isinstance(node, dict): return False
        if ({'frame', 'native_ratio'} & set(node.get('properties', {}))
                or {'frame', 'native_ratio'} & set(node.get('required', []))):
            return True
        return any(split_predicate(value) for key, value in node.items()
                   if key in {'if', 'then', 'else', 'not'}) or any(
            split_predicate(branch) for key in ('allOf', 'anyOf', 'oneOf') for branch in node.get(key, []))
    def walk(node, stack=()):
        if not isinstance(node, dict): return {}
        if '$ref' in node:
            ref = node['$ref']
            if ref in stack or not ref.startswith('#/$defs/') or ref.split('/')[-1] not in definitions:
                raise ValueError('Unknown or recursive frame schema reference')
            target = walk(definitions[ref.split('/')[-1]], (*stack, ref))
            if target.get('frame') and split_predicate({k: v for k, v in node.items() if k != '$ref'}):
                raise ValueError('Unmapped frame predicate on reference sibling')
            return target
        tree = {}
        if node.get('title') == 'NeedProposal': tree['frame'] = True
        children = {key: child for key, value in node.get('properties', {}).items() if (child := walk(value, stack))}
        if children: tree['properties'] = children
        if child := walk(node.get('items'), stack): tree['items'] = child
        prefix = [walk(value, stack) for value in node.get('prefixItems', [])]
        if any(prefix): tree['prefixItems'] = prefix
        for keyword in ('anyOf', 'oneOf', 'allOf'):
            for branch in node.get(keyword, []):
                if child := walk(branch, stack):
                    if child.get('frame') and any(split_predicate(other) for other in node[keyword] if other is not branch):
                        raise ValueError('Unmapped frame predicate on composition sibling')
                    if tree and tree != child:
                        raise ValueError('Ambiguous frame-bearing union')
                    tree = child
        return tree
    return walk(schema)


class FrameProjection:
    def __init__(self, canonical, stage):
        self.canonical = deepcopy(canonical)
        self.tree = _frame_tree(canonical)
        self.codec = Projection(_frame_schema(canonical), stage)
        self.schema = self.codec.schema
        self.identity = {**self.codec.identity, 'producer_schema_sha256': digest(self.codec.canonical),
                         'canonical_schema_sha256': digest(canonical), 'semantic_representation': FRAME_POLICY}

    def errors(self, value): return self.codec.errors(value)

    def _transform(self, value, tree, encode):
        if isinstance(value, list):
            prefix = tree.get('prefixItems', [])
            return [self._transform(child, prefix[i] if i < len(prefix) else tree.get('items', {}), encode)
                    for i, child in enumerate(value)]
        if not isinstance(value, dict): return value
        out = {key: self._transform(child, tree.get('properties', {}).get(key, {}), encode)
               for key, child in value.items()}
        if tree.get('frame'):
            if encode:
                if 'framing' in out:
                    raise ValueError('Atomic producer field cannot enter original canonical input')
                mode = out.pop('frame', 'unconstrained')
                ratio = out.pop('native_ratio', None)
                if (mode not in {'unconstrained', 'match_output', 'native'}
                        or (mode == 'native') != (ratio is not None)):
                    raise ValueError('Illegal split frame cannot become a legal choice')
                out['framing'] = {'mode': mode, **({'ratio': ratio} if mode == 'native' else {})}
            else:
                if 'frame' in out or 'native_ratio' in out:
                    raise ValueError('Split frame fields cannot enter atomic Planning')
                framing = out.pop('framing', {'mode': 'unconstrained'})
                frame_schema = {'type': 'object', 'additionalProperties': False,
                    'properties': {'mode': {'enum': ['unconstrained', 'match_output', 'native']},
                                   'ratio': {'type': 'string', 'maxLength': 9,
                                             'pattern': r'^[1-9][0-9]{0,3}:[1-9][0-9]{0,3}$'}},
                    'required': ['mode'], 'oneOf': [
                        {'properties': {'mode': {'enum': ['unconstrained', 'match_output']}},
                         'not': {'required': ['ratio']}},
                        {'properties': {'mode': {'const': 'native'}}, 'required': ['ratio']}]}
                if not Draft202012Validator(frame_schema).is_valid(framing):
                    raise ValueError('Invalid atomic frame choice; no guessed correction')
                out.update(frame=framing['mode'], native_ratio=framing.get('ratio'))
        return out

    def decode_candidate(self, value):
        return self._transform(self.codec.decode_candidate(value), self.tree, False)

    def decode_valid(self, value):
        result = self._transform(self.codec.decode_valid(value), self.tree, False)
        if not Draft202012Validator(self.canonical).is_valid(result):
            raise ValueError('Atomic frame violates complete canonical contract')
        return result

    def encode(self, value):
        return self.codec.encode(self._transform(value, self.tree, True))


def project(canonical, stage, *, atomic_framing=False):
    return _scoped_compile('wire', canonical, (stage, atomic_framing),
        lambda: FrameProjection(canonical, stage) if atomic_framing else Projection(canonical, stage))
