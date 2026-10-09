"""Program-owned review slots and verifiable frozen support, not entailment.

Models select existing source handles and judge whole obligations. The program
checks reference existence/eligibility and restores question identity; it never
deduces ACCEPT from a matching quote or rewrites candidate requirements.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from easel.integrations.planning_authority import digest
from easel.integrations.planning_result_contract import (
    Carrier, Handle, Text, ReviewAnswer, MAX_B_ANSWERS, MAX_RESULT_BYTES,
    maximum_compact_bytes,
)

REVISION = 'bounded-semantic-support@1'


class Support(Carrier):
    source: Handle
    # A citation anchor, never a replacement for the complete frozen source.
    # This preserves a finite 48-question/16-reference response below 8MiB.
    quote: Annotated[str, Field(min_length=1, max_length=512)] | None
    role: Literal['authority', 'context', 'output_authority']


class SupportedAnswer(ReviewAnswer):
    support: Annotated[tuple[Support, ...], Field(max_length=16)]


class SupportedResponse(Carrier):
    answers: Annotated[tuple[SupportedAnswer, ...], Field(min_length=1, max_length=MAX_B_ANSWERS)]


def source_catalog(batch):
    """Paths come solely from frozen values; no model-written path or alias."""
    result = {}
    def walk(value, path, origin, evidence_id):
        if isinstance(value, dict):
            for key in sorted(value):
                walk(value[key], [*path, key], origin, evidence_id)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, [*path, index], origin, evidence_id)
        else:
            handle = f'source-{len(result):04}'
            roles = (['context'] if origin == 'derived_preparation' else
                     ['context', 'output_authority'] if origin == 'confirmed_spec' else
                     ['context', 'authority'])
            result[handle] = {'origin': origin, 'evidence_id': evidence_id,
                'path': path, 'value': value, 'sha256': digest(value), 'roles': roles}
    for source in batch['evidence']:
        walk(source['value'], [], source['origin'], source['id'])
    if not result or len(result) > 4096:
        raise ValueError('Frozen support catalog capacity exceeded; no clipping')
    return result


def slot(question):
    return f"question-{question['question']:04}"


def response_schema(batch):
    """Exactly one required property per real question, no repeated ID field."""
    sources = source_catalog(batch)
    schema = SupportedAnswer.model_json_schema()
    for field in ('question', 'evidence'):
        del schema['properties'][field]
        schema['required'].remove(field)
    definitions = schema.pop('$defs', {})
    definitions['Support']['properties']['source']['enum'] = list(sources)
    schema = {'title': 'PlanningVisualReview', 'type': 'object', 'additionalProperties': False,
        '$defs': definitions, 'properties': {slot(q): deepcopy(schema) for q in batch['questions']},
        'required': [slot(q) for q in batch['questions']]}
    if not 1 <= len(batch['questions']) <= MAX_B_ANSWERS or maximum_compact_bytes(schema) > MAX_RESULT_BYTES:
        raise ValueError('Complete supported review exceeds capacity')
    return schema


def decode_slots(value, batch):
    keys = [slot(q) for q in batch['questions']]
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Review slots must cover each frozen question exactly once')
    catalog = source_catalog(batch)
    answers = []
    for question, key in zip(batch['questions'], keys, strict=True):
        item = value[key]
        if not isinstance(item, dict) or set(item) != {'decision', 'support', 'reason'}:
            raise ValueError('Unknown supported review structure; no invented identity')
        # Leave malformed semantic leaves for the existing single local repair.
        # Never treat unavailable/invalid references as independent evidence.
        support = item['support'] if isinstance(item['support'], list) else []
        evidence = sorted({catalog[row['source']]['evidence_id'] for row in support
            if isinstance(row, dict) and isinstance(row.get('source'), str) and row['source'] in catalog})
        answers.append({**item, 'question': question['question'], 'evidence': evidence})
    return {'answers': answers}


def validate_support(answer, question, batch):
    """Eligibility only. An admitted reference is never an entailment proof."""
    catalog = source_catalog(batch)
    seen, authority, evidence = set(), False, set()
    for reference in answer.support:
        source = catalog.get(reference.source)
        key = (reference.source, reference.quote, reference.role)
        if (source is None or key in seen or reference.role not in source['roles']
                or source['evidence_id'] not in question['evidence']):
            raise ValueError('Support reference or authority role is invalid')
        seen.add(key)
        evidence.add(source['evidence_id'])
        original = source['value']
        if isinstance(original, str):
            if not reference.quote or not reference.quote.strip() or reference.quote not in original:
                raise ValueError('Quoted support does not exist in the frozen source')
        elif reference.quote is not None:
            raise ValueError('Scalar support binds the original value, not a fabricated quote')
        if reference.role == 'output_authority':
            if (question['kind'] != 'complete_obligation'
                    or question['candidate'].get('responsibility') != 'postproduction'):
                raise ValueError('Final output fact cannot authorize a source material property')
        authority |= reference.role in {'authority', 'output_authority'}
    if set(answer.evidence) != evidence:
        raise ValueError('Review source IDs must derive from the frozen support handles')
    if answer.decision == 'ACCEPT' and not authority:
        raise ValueError('Accepted whole obligation requires eligible independent support')
