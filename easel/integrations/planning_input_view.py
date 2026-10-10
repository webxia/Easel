"""Versioned, reversible Planning input view; no semantic decisions are inferred."""
from copy import deepcopy
from jsonschema import Draft202012Validator
from easel.integrations.planning_staged_proposal import _read_only_staged


class SourceSelection:
    """Reversible scope names and known-empty choices.

    Does not select source kind, modality, necessity, obligations, or repair.
    Old malformed selections cannot enter through encode().
    """
    POLICY = 'planning-source-selection@1'

    def __init__(self, canonical, catalog):
        from easel.integrations.planning_authority import digest
        self.staged = _read_only_staged(canonical)
        self.catalog = deepcopy(catalog)
        self.references = {}
        self.to_wire = {}
        for kind in ('global', 'scene', 'segment', 'event'):
            for original, value in sorted(catalog.get(kind, {}).items()):
                handle = 'src_' + digest({'kind': kind, 'original': original, 'value': value})[:20]
                if original in self.to_wire or handle in self.references:
                    raise ValueError('Source mapping collision')
                self.to_wire[original] = handle
                self.references[handle] = {'kind': kind, 'original': original, 'value_sha256': digest(value)}
        self.empty_continuity = catalog.get('continuity') == {}
        self.schema = deepcopy(self.staged.selection_schema)
        header = self.schema['properties']['needs']['items']
        header['properties']['scope'] = {'type': 'string', 'enum': list(self.references)}
        if self.empty_continuity:
            del header['properties']['continuity_choices']
            header['required'].remove('continuity_choices')
        Draft202012Validator.check_schema(self.schema)
        self.identity = {'policy': self.POLICY, 'catalog_sha256': digest(catalog),
                         'schema_sha256': digest(self.schema), 'mapping_sha256': digest(self.references)}

    def encode(self, selection):
        Draft202012Validator(self.staged.selection_schema).validate(selection)
        result = deepcopy(selection)
        for row in result['needs']:
            row['scope'] = self.to_wire[row['scope']]
            if self.empty_continuity:
                if row.pop('continuity_choices') != []:
                    raise ValueError('Cannot discard nonempty continuity')
        Draft202012Validator(self.schema).validate(result)
        return result

    def decode(self, selection, identity, *, diagnostic=False):
        if identity != self.identity:
            raise ValueError('Source selection mapping identity changed')
        if diagnostic:
            self.staged.shape(selection, self.schema)
        else:
            Draft202012Validator(self.schema).validate(selection)
        result = deepcopy(selection)
        for row in result['needs']:
            handle = row['scope']
            if not isinstance(handle, str) or handle not in self.references:
                raise ValueError('Unknown source position')
            row['scope'] = self.references[handle]['original']
            if self.empty_continuity:
                row['continuity_choices'] = []
        if not diagnostic:
            Draft202012Validator(self.staged.selection_schema).validate(result)
        return result


class PlanningInputView:
    """Reversible view; no inference, dispatcher, or authority changes.

    Reference paths are JSON key/index arrays, not filesystem paths. Text
    ranges are half-open UTF-8 byte offsets; original authority spans retain
    their explicit Python-character unit. Program metadata stays in lineage.
    """
    POLICY = 'planning-input-view@1'

    def snapshot(self):
        return deepcopy({'identity': self.identity, 'view': self.view,
            'metadata': self.metadata, 'links': self.links, 'source_mapping': self.codec.references})

    def opaque_headers(self, canonical):
        """Keep invalid business leaves; only the exact scope representation changes."""
        value = deepcopy(canonical)
        for need in value['needs']:
            scope = need['scope']
            if not isinstance(scope, str) or scope not in self.codec.to_wire:
                raise ValueError('Unknown canonical source position')
            need['scope'] = self.codec.to_wire[scope]
            if self.codec.empty_continuity:
                if need.pop('continuity_choices', None) != []:
                    raise ValueError('Cannot omit an illegal continuity candidate')
        return value

    def source_position(self, original):
        import hashlib
        document = self.view['inputs']['confirmed']['SCENES.md']
        text = ''.join(row['text'] for row in document['lines'])
        sha = hashlib.sha256(text.encode()).hexdigest()
        handle = self.codec.to_wire.get(original)
        if handle is None:
            raise ValueError('Review uses an unknown source mapping')
        kind = self.codec.references[handle]['kind']
        if kind == 'global':
            return {'kind': kind, 'handle': original, 'position_kind': 'whole_document',
                'evidence_id': 0, 'document_path': 'SCENES.md', 'document_sha256': sha,
                'byte_start': 0, 'byte_end': len(text.encode()), 'line': None}
        for number, row in enumerate(document['lines'], 1):
            if row.get('choices', {}).get(kind) == handle:
                literal = row['text'].splitlines()[0]
                return {'kind': kind, 'handle': original, 'position_kind': 'literal_line_not_shot_number',
                    'document_sha256': sha, 'text': literal, 'line': number,
                    'byte_start': row['byte_start'], 'byte_end': row['byte_start'] + len(literal.encode())}
        raise ValueError('Review source position is not present')

    def check_review(self, directory):
        for question in directory['questions']:
            if 'selected_source' in question:
                selected = question['selected_source']
                if selected != self.source_position(selected['handle']):
                    raise ValueError('Independent review source differs from input view')
            elif question['kind'] == 'frozen_visual_coverage':
                scope = question['target'][0]
                ref = self.source_position(scope)
                expected = (''.join(r['text'] for r in self.view['inputs']['confirmed']['SCENES.md']['lines'])
                            if ref['kind'] == 'global' else ref['text'])
                if question['candidate']['scope_original'] != expected:
                    raise ValueError('Frozen coverage source differs from input view')

    @staticmethod
    def at(value, path):
        for part in path:
            if isinstance(value, dict) and isinstance(part, str) and part in value:
                value = value[part]
            elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
                value = value[part]
            else:
                raise ValueError('Invalid exact JSON path')
        return value

    @classmethod
    def put(cls, value, path, item):
        parent = cls.at(value, path[:-1])
        if not isinstance(parent, dict) or not isinstance(path[-1], str):
            raise ValueError('Reference destination is not an object member')
        parent[path[-1]] = deepcopy(item)

    def __init__(self, inputs, catalog):
        from easel.integrations import planning_authority as authority
        from easel.integrations.planning_result_contract import semantic_tool_schema
        self.inputs_sha = authority.digest(inputs)
        self.catalog_sha = authority.digest(catalog)
        self.codec = SourceSelection(semantic_tool_schema(catalog, compiled=True), catalog)
        self.metadata, self.links = [], []
        view = {'policy': self.POLICY, 'inputs': deepcopy(inputs), 'catalog': deepcopy(catalog)}
        self.scope_kinds = [kind for kind in ('global', 'scene', 'segment', 'event') if kind in catalog]
        text = inputs['confirmed']['SCENES.md']
        if not isinstance(text, str):
            raise ValueError('Frozen scene document must be text')
        lines, offset, ordinal = [], 0, 0
        for line in text.splitlines(keepends=True):
            row = {'text': line, 'byte_start': offset, 'byte_end': offset + len(line.encode())}
            offset = row['byte_end']
            if line.strip():
                ordinal += 1
                row['choices'] = {}
                for kind in ('scene', 'segment', 'event'):
                    original = f'{kind}-{ordinal}'
                    if original in catalog.get(kind, {}):
                        if catalog[kind][original] != line.splitlines()[0]:
                            raise ValueError('Scope is not its exact frozen physical line')
                        row['choices'][kind] = self.codec.to_wire[original]
            lines.append(row)
        view['inputs']['confirmed']['SCENES.md'] = {
            'format': 'ordered-literal-lines', 'offset_unit': 'utf8_bytes', 'lines': lines,
            'whole_document': self.codec.to_wire['global'],
            'warning': 'Literal text positions, not narrative shot numbers; source kind is not inferred.'}
        for kind in self.scope_kinds:
            del view['catalog'][kind]

        def omit(path):
            parent = self.at(view, path[:-1])
            if path[-1] in parent:
                self.metadata.append({'path': path, 'value': parent.pop(path[-1])})

        def link(path, target, span=None):
            reference = {'json_path': target}
            if span is not None:
                reference.update(offset_unit='utf8_bytes', span=span)
            self.links.append({'path': path, 'reference': reference})
            self.put(view, path, {'program_reference': reference})

        omit(['inputs', 'handoff_sha256'])
        omit(['inputs', 'voice_binding'])
        proposal = inputs.get('proposal')
        if isinstance(proposal, dict):
            for field, document in [('script', 'SCRIPT.md'), ('scenes', 'SCENES.md'),
                                    ('treatment', 'TREATMENT.md'), ('sound', 'TREATMENT.md'),
                                    ('sound_source', 'TREATMENT.md')]:
                value = proposal.get(field)
                original = inputs['confirmed'].get(document)
                if not isinstance(value, str) or not isinstance(original, str):
                    continue  # Unknown/legal independent values stay verbatim.
                start = original.encode().find(value.encode())
                if start >= 0:
                    link(['inputs', 'proposal', field], ['inputs', 'confirmed', document],
                         [start, start + len(value.encode())])
            for field in ('revision', 'sha256', 'updated_at'):
                omit(['inputs', 'proposal', field])

        derived = catalog.get('derived_voice')
        if isinstance(derived, dict):
            for field in ('plan_sha256', 'script_sha256', 'sound_source_sha256'):
                omit(['catalog', 'derived_voice', field])
            if (isinstance(proposal, dict) and 'voice_profile' in proposal
                    and 'profile' in derived and derived['profile'] == proposal['voice_profile']):
                link(['catalog', 'derived_voice', 'profile'], ['inputs', 'proposal', 'voice_profile'])
        # Only references that actually exist are projected. No implicit voice.
        for name, record in sorted(catalog.get('voice', {}).items()):
            if not isinstance(record, dict) or 'context' not in record:
                continue
            if isinstance(derived, dict) and record['context'] == derived:
                link(['catalog', 'voice', name, 'context'], ['catalog', 'derived_voice'])
            elif ('voice' in inputs.get('creator_context', {})
                  and record['context'] == inputs['creator_context']['voice']):
                link(['catalog', 'voice', name, 'context'], ['inputs', 'creator_context', 'voice'])

        original_authority = authority.catalog(inputs)
        self.authority_sha = authority.digest(original_authority)
        # Group only identical eligibility, with original IDs and sequence.
        # Scope and SHA are rebuilt from exact inputs, not inferred from groups.
        groups = {}
        for row in original_authority['sources']:
            key = (row['origin'], row['path'], tuple(row['relations']), row['primary'])
            group = groups.setdefault(key, {'origin': row['origin'], 'path': row['path'],
                'relations': row['relations'], 'primary': row['primary'],
                'offset_unit': 'python_characters', 'occurrences': []})
            group['occurrences'].append({'id': row['id'], 'span': row['span']})
        view['eligibility'] = list(groups.values())
        view['precedence'] = {
            'explicit_vs_default': 'A generic default is not permission to downgrade an explicit confirmed requirement. Deciding what the text requires remains semantic judgment.',
            'director': 'All Director text retains its existing authority; not every sentence is a default.',
            'derived': 'Preparation does not create author authorization.',
            'program': 'Identity hashes and resource binding are not missing creative obligations.'}
        self.view = view
        self.identity = {'policy': self.POLICY, 'inputs_sha256': self.inputs_sha,
            'catalog_sha256': self.catalog_sha, 'authority_sha256': self.authority_sha,
            'view_sha256': authority.digest(view),
            'lineage_sha256': authority.digest({'metadata': self.metadata, 'links': self.links,
                                               'scope_mapping': self.codec.references})}
        # Construction itself proves every source SHA, scope, duplicate/order,
        # qualification and field can be reconstructed from the candidate view.
        restored, restored_catalog, restored_authority = self.decode(view, self.identity)
        if restored != inputs or restored_catalog != catalog or restored_authority != original_authority:
            raise ValueError('Input projection is not lossless')

    def decode(self, view, identity):
        from easel.integrations import planning_authority as authority
        if identity != self.identity or authority.digest(view) != identity['view_sha256']:
            raise ValueError('Input view belongs to another frozen identity')
        if authority.digest({'metadata': self.metadata, 'links': self.links,
                             'scope_mapping': self.codec.references}) != identity['lineage_sha256']:
            raise ValueError('Input view lineage changed')
        value = deepcopy(view)
        document = value['inputs']['confirmed']['SCENES.md']
        if document.get('offset_unit') != 'utf8_bytes' or document.get('format') != 'ordered-literal-lines':
            raise ValueError('Unknown source offset representation')
        offset, text, positions = 0, '', {}
        for row in document['lines']:
            part = row['text']
            if row['byte_start'] != offset or row['byte_end'] != offset + len(part.encode()):
                raise ValueError('Source byte intervals are not contiguous')
            offset = row['byte_end']; text += part
            for kind, handle in row.get('choices', {}).items():
                ref = self.codec.references.get(handle)
                if not ref or ref['kind'] != kind or handle in positions:
                    raise ValueError('Source kind/position was reused or changed')
                literal = part.splitlines()[0]
                if authority.digest(literal) != ref['value_sha256']:
                    raise ValueError('Source position text changed')
                positions[handle] = literal
        global_handle = document['whole_document']
        if global_handle != self.codec.to_wire['global']:
            raise ValueError('Whole document reference changed')
        positions[global_handle] = text
        if set(positions) != set(self.codec.references):
            raise ValueError('Source mapping is incomplete')
        value['inputs']['confirmed']['SCENES.md'] = text
        for kind in self.scope_kinds:
            value['catalog'][kind] = {r['original']: positions[h] for h, r in self.codec.references.items()
                                      if r['kind'] == kind}
        for row in self.metadata:
            self.put(value, row['path'], row['value'])
        for row in self.links:
            ref = row['reference']
            if self.at(value, row['path']) != {'program_reference': ref}:
                raise ValueError('Declared text reference changed')
            original = self.at(value, ref['json_path'])
            if 'span' in ref:
                start, end = ref['span']
                if (ref['offset_unit'] != 'utf8_bytes' or not isinstance(original, str)
                        or type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(original.encode())):
                    raise ValueError('Invalid exact text byte range')
                try: original = original.encode()[start:end].decode('utf8')
                except UnicodeDecodeError as exc: raise ValueError('Text range splits a UTF-8 codepoint') from exc
            self.put(value, row['path'], original)
        inputs, catalog = value['inputs'], value['catalog']
        if authority.digest(inputs) != self.inputs_sha or authority.digest(catalog) != self.catalog_sha:
            raise ValueError('Input/source reconstruction differs from frozen originals')
        sources = authority.catalog(inputs)
        if authority.digest(sources) != self.authority_sha:
            raise ValueError('Source order, qualification, scope or SHA changed')
        ordered = {}
        for group in value['eligibility']:
            if group['offset_unit'] != 'python_characters':
                raise ValueError('Authority offsets must retain character units')
            for occurrence in group['occurrences']:
                number = occurrence['id']
                if type(number) is not int or number in ordered or not 0 <= number < len(sources['sources']):
                    raise ValueError('Authority occurrence identity changed')
                row = sources['sources'][number]
                if any(row[k] != group[k] for k in ('origin', 'path', 'relations', 'primary')) or row['span'] != occurrence['span']:
                    raise ValueError('Source qualification changed')
                ordered[number] = row
        if list(sorted(ordered)) != list(range(len(sources['sources']))):
            raise ValueError('Authority occurrence lost')
        return inputs, catalog, sources
