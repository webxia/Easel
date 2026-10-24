"""Explicit creative context, never a developer workspace or chat transcript."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class TaskContext:
    work_id: str
    run_id: str
    task_id: str
    profile_ref: str | None = None
    profile: dict[str, str] = field(default_factory=dict)
    director: dict[str, Any] = field(default_factory=dict)
    brief: str = ""
    plan: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    allowed_handles: frozenset[str] = frozenset()
    facts: tuple[str, ...] = ()
    prohibitions: tuple[str, ...] = ()
    adaptation_permissions: tuple[str, ...] = ()
    capabilities: dict[str, Any] = field(default_factory=dict)
    expression_policy: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    editor_view: bool = False

    def creative_data(self) -> dict[str, Any]:
        if self.profile and not self.profile_ref:
            raise ValueError("A profile requires an explicitly selected profile reference")
        # IDs used by execution/authorization are deliberately not model-editable.
        result = {
            "schema_version": self.schema_version, "brief": self.brief,
            "profile": self.profile if self.profile_ref else {}, "director": self.director,
            "plan": self.plan, "inputs": self.inputs, "artifacts": self.artifacts,
            "facts": self.facts, "prohibitions": self.prohibitions,
            "adaptation_permissions": self.adaptation_permissions,
            "allowed_handles": sorted(self.allowed_handles),
        }
        if self.capabilities:
            result['production_capabilities'] = self.capabilities
        result = deepcopy(result)
        basis = result["plan"].get("conversation_basis")
        if isinstance(basis, dict):
            basis.pop("expression_policy", None)
        return result

    def model_data(self) -> dict[str, Any]:
        """Only editing gets the new view; creative identity stays unprojected."""
        data = self.creative_data()
        if not self.editor_view:
            return data
        from .expression_policy import validate
        policy = validate(self.expression_policy)
        if policy['version'] not in {'natural-expression-3', 'natural-expression-4'}:
            return data
        return _editor_view(data, director_reference=policy['version'] == 'natural-expression-4')

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps({"creative": self.creative_data(),
                                        "expression_policy": self.expression_policy}, sort_keys=True,
                                        ensure_ascii=False).encode()).hexdigest()


def _editor_view(data: dict[str, Any], *, director_reference: bool = False) -> dict[str, Any]:
    """Lossless interning at known constraint paths, not a metadata whitelist.

    Every occurrence keeps a reference at its original scope. Unknown fields,
    material uses (boards/SFX), rights, observations and timing stay untouched.
    This operates only on creative_data's detached copy, never stored records.
    """
    source_characters = len(json.dumps(data, ensure_ascii=False))
    source_fields = {key: len(json.dumps(value, ensure_ascii=False))
                     for key, value in data.items()}
    slots = []
    for artifact in data['artifacts']:
        meta = artifact.get('metadata')
        if not isinstance(meta, dict):
            continue
        if isinstance(meta.get('use_constraints'), dict):
            slots.append((meta, 'use_constraints'))
        for use in meta.get('material_uses', []):
            need = use.get('need') if isinstance(use, dict) else None
            if isinstance(need, dict) and isinstance(need.get('constraints'), dict):
                slots.append((need, 'constraints'))
    # Preserve v3 request bytes. Only newly frozen v4 tasks use director refs.
    # Scope stays at the original constraint; a differing director stays inline.
    if director_reference and data['director']:
        for parent, key in slots:
            if parent[key].get('director') == data['director']:
                parent[key]['director'] = {'context_ref': '/director'}
    grouped = {}
    for parent, key in slots:
        encoded = json.dumps(parent[key], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        grouped.setdefault(encoded, []).append((parent, key))
    shared = {}
    for encoded, occurrences in grouped.items():
        # A reference costs space too. Intern only substantial exact repeats.
        if len(occurrences) < 2 or len(encoded) < 256:
            continue
        ref = 'constraints_' + hashlib.sha256(encoded.encode()).hexdigest()
        shared[ref] = occurrences[0][0][occurrences[0][1]]
        for parent, key in occurrences:
            parent[key] = {'task_view_ref': ref}
    # A historical profile snapshot can differ from current replan input.
    # Only remove its serialized content when it is exactly the same profile.
    snapshot = data['plan'].get('profile_snapshot')
    if isinstance(snapshot, dict) and isinstance(snapshot.get('content'), str):
        try:
            identical = json.loads(snapshot['content']) == data['profile']
        except ValueError:
            identical = False
        if identical:
            snapshot.pop('content')
            snapshot['content_ref'] = '/profile'
    data['task_view'] = {
        'version': 'editor-context-2' if director_reference else 'editor-context-1',
        'source_characters': source_characters,
        'source_field_characters': source_fields,
        'reference_semantics': 'task_view_ref引用本输入shared_constraints中的完整约束；'
            'content_ref=/profile引用本输入完整画像，原content_hash保留。'
            '每个引用仍只作用于其原素材/need位置，不扩大作用域，不代表已观察或已获新授权。',
        'shared_constraints': shared,
    }
    if director_reference:
        data['task_view']['reference_semantics'] += 'context_ref=/director引用本输入完整导演配置，作用域保持在原约束位置。'
    return data
