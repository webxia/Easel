"""Minimal provider interface and normalized search page."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field, model_validator

from easel.materials.domain import SupplyCandidate
from easel.materials.domain.models import ContractModel, RetrievalIntent
from easel.materials.providers.models import ProviderContinuation, ProviderHealth, ProviderInfo


class ProviderPage(ContractModel):
    candidates: tuple[SupplyCandidate, ...] = ()
    continuation: ProviderContinuation | None = None

    @model_validator(mode="after")
    def candidate_ids_unique(self) -> ProviderPage:
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("ProviderPage candidate IDs must be unique")
        return self


class MaterialProvider(Protocol):
    """Adapter protocol; Provider schemas remain behind the adapter."""

    def info(self) -> ProviderInfo: ...

    def search(
        self,
        intent: RetrievalIntent,
        continuation: ProviderContinuation | None = None,
    ) -> ProviderPage: ...

    def health(self) -> ProviderHealth: ...
