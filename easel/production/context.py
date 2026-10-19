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
    schema_version: int = 1

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
        return deepcopy(result)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.creative_data(), sort_keys=True,
                                        ensure_ascii=False).encode()).hexdigest()
