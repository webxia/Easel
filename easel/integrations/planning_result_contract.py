"""Bounded semantic response carriers; never a model output-token limit.

These are Planning-local choices. Formal IDs, paths, hashes and authorizations
belong to the application. Capacity rejection never truncates an obligation.
"""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

REPLY_CONTRACT = 'planning-result-v2'
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MAX_B_ANSWERS = 48
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Handle = Annotated[str, Field(min_length=1, max_length=512)]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]


class Carrier(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Condition(Carrier):
    text: Text
    strength: Literal['required', 'preference']
    responsibility: Literal['material', 'postproduction', 'narrative']
    meaning: Literal['observable', 'dynamic_action'] = 'observable'


class SoundIntent(Carrier):
    mood: ShortText | None = None
    genre: ShortText | None = None
    instruments: Annotated[tuple[ShortText, ...], Field(max_length=12)] = ()
    vocals_allowed: bool = False
    energy: ShortText | None = None
    tempo_bpm: tuple[Annotated[int, Field(ge=1, le=400)], Annotated[int, Field(ge=1, le=400)]] | None = None
    event_description: Text | None = None
    sound_character: ShortText | None = None
    intensity: ShortText | None = None
    environment: ShortText | None = None


class NeedProposal(Carrier):
    scope: Handle
    role: ShortText
    modality: Literal['image', 'video', 'voice', 'bgm', 'sfx']
    necessity: Literal['required', 'optional']
    conditions: Annotated[tuple[Condition, ...], Field(min_length=1, max_length=12)]
    purpose: Text | None = None
    frame: Literal['unconstrained', 'match_output', 'native'] = 'unconstrained'
    native_ratio: Annotated[str, Field(max_length=9, pattern=r'^[1-9][0-9]{0,3}:[1-9][0-9]{0,3}$')] | None = None
    visual_preference: ShortText | None = None
    source_seconds: Annotated[float, Field(gt=0, le=3600)] | None = None
    continuity_choices: Annotated[tuple[Handle, ...], Field(max_length=16)] = ()
    queries: Annotated[tuple[Annotated[str, Field(min_length=1, max_length=100)], ...], Field(max_length=3)] = ()
    voice_choice: Handle | None = None
    voice_expression: Text | None = None
    sound: SoundIntent | None = None

    @model_validator(mode='after')
    def semantic_shape(self):
        visual = self.modality in {'image', 'video'}
        if visual and self.queries and (len(self.queries) != 3 or any(not q.strip() or not q.isascii()
                for q in self.queries) or len({q.strip().casefold() for q in self.queries}) != 3):
            raise ValueError('Visual query candidates require three distinct short English phrases')
        if not visual and self.queries:
            raise ValueError('Visual retrieval queries cannot enter audio')
        if self.modality == 'image' and self.source_seconds is not None:
            raise ValueError('Display/final duration cannot become image source duration')
        if self.frame != 'native' and self.native_ratio is not None:
            raise ValueError('Native ratio is not an independent aspect alias')
        if self.frame == 'native' and self.native_ratio is None:
            raise ValueError('A native frame choice requires its ratio')
        if not visual and (self.frame != 'unconstrained' or self.visual_preference or self.native_ratio):
            raise ValueError('Audio proposal cannot contain visual controls')
        if self.source_seconds is not None and self.modality not in {'video', 'bgm', 'sfx'}:
            raise ValueError('Source duration belongs only to timed source media')
        if any(c.meaning == 'dynamic_action' and c.responsibility == 'material'
               and c.strength == 'required' for c in self.conditions) and self.modality != 'video':
            raise ValueError('Required source action cannot be supplied by a still image')
        if self.modality == 'voice' and (not self.voice_choice or self.sound):
            raise ValueError('Voice needs a frozen voice choice, not BGM/SFX fields')
        if self.modality != 'voice' and (self.voice_choice or self.voice_expression):
            raise ValueError('Voice semantics cannot enter another modality')
        if self.modality in {'bgm', 'sfx'} and self.sound is None:
            raise ValueError('Audio material needs its sound intent')
        if self.modality not in {'bgm', 'sfx'} and self.sound is not None:
            raise ValueError('Sound intent belongs only to BGM/SFX')
        if self.modality == 'bgm' and any(getattr(self.sound, k) is not None for k in
                ('event_description', 'sound_character', 'intensity', 'environment')):
            raise ValueError('SFX fields cannot enter BGM')
        if self.modality == 'sfx' and (not self.sound.event_description or any(
                getattr(self.sound, k) not in (None, (), False) for k in
                ('mood', 'genre', 'instruments', 'vocals_allowed', 'energy', 'tempo_bpm'))):
            raise ValueError('SFX requires its event without BGM fields')
        return self


class SemanticProposal(Carrier):
    needs: Annotated[tuple[NeedProposal, ...], Field(min_length=1, max_length=16)]
    unresolved: Annotated[tuple[Text, ...], Field(max_length=16)] = ()


class ReviewAnswer(Carrier):
    # Local question handle only, generated and matched by the application.
    question: Annotated[StrictInt, Field(ge=0, le=4095)]
    decision: Literal['ACCEPT', 'CHALLENGE', 'UNRESOLVED']
    evidence: Annotated[tuple[Annotated[StrictInt, Field(ge=0, le=4095)], ...], Field(max_length=16)]
    reason: Text


class ReviewResponse(Carrier):
    answers: Annotated[tuple[ReviewAnswer, ...], Field(min_length=1, max_length=MAX_B_ANSWERS)]


def result_schema(stage):
    return {'A': SemanticProposal, 'B': ReviewResponse}[stage].model_json_schema()


def maximum_compact_bytes(schema):
    """Conservative UTF-8 JSON bound, including escaped controls and keys.

    Bounded carriers use finite primitive/array/object schemas. An unbounded
    field fails this audit instead of borrowing the terminal-preview limit.
    Whitespace is separately bounded by the whole raw envelope budget.
    """
    import json
    definitions = schema.get('$defs', {})
    def size(node):
        if '$ref' in node:
            return size(definitions[node['$ref'].split('/')[-1]])
        if 'anyOf' in node:
            return max(map(size, node['anyOf']))
        if 'enum' in node:
            return max(len(json.dumps(v, ensure_ascii=False).encode()) for v in node['enum'])
        if 'const' in node:
            return len(json.dumps(node['const'], ensure_ascii=False).encode())
        kind = node.get('type')
        if kind == 'string':
            # Pattern-only strings here are the finite native-ratio enum.
            count = node.get('maxLength', 4 if node.get('pattern', '').startswith('^(?:16:9') else None)
            if count is None: raise ValueError('Unbounded semantic response string')
            return 2 + 6 * count
        if kind in {'number', 'integer'}:
            if 'maximum' not in node or 'minimum' not in node and 'exclusiveMinimum' not in node:
                raise ValueError('Unbounded semantic response number')
            return 32
        if kind == 'boolean': return 5
        if kind == 'null': return 4
        if kind == 'array':
            if 'prefixItems' in node:
                return 2 + sum(map(size, node['prefixItems'])) + max(0, len(node['prefixItems'])-1)
            count = node.get('maxItems')
            if count is None: raise ValueError('Unbounded semantic response array')
            return 2 + count * (size(node['items']) + 1)
        if kind == 'object':
            if node.get('additionalProperties') is not False:
                raise ValueError('Unbounded semantic response object')
            return 2 + sum(len(json.dumps(k).encode()) + 2 + size(v)
                           for k,v in node.get('properties', {}).items())
        raise ValueError('Unsupported semantic capacity schema')
    return size(schema)
