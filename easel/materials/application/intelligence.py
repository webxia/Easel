"""Optional, provider-neutral semantic enrichment for acquired assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from easel.materials.domain import (
    IntelligenceStatus,
    MaterialAsset,
    MediaType,
    SemanticAnnotation,
    SemanticInference,
)
from easel.materials.store import AttemptMaterialStore


class SemanticAnalysisOutput(BaseModel):
    """Validated annotations returned by an injected local or remote analyzer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    annotations: tuple[SemanticAnnotation, ...] = ()
    partial: bool = False

    @classmethod
    def validate_output(cls, value: object) -> SemanticAnalysisOutput:
        if isinstance(value, cls):
            return value
        # Analyzer adapters normally return JSON-shaped lists for array fields;
        # JSON validation keeps strict scalar checks while accepting that shape.
        return cls.model_validate_json(json.dumps(value, ensure_ascii=False))


class MaterialSemanticAnalyzer(Protocol):
    """Analyzer plug-in contract. Implementations must not mutate asset facts."""

    analyzer_id: str

    def analyze(self, path: Path, media_type: MediaType) -> SemanticAnalysisOutput | dict[str, object]:
        """Return only inferred semantic annotations for the supplied bytes."""


class BasicMaterialIntelligence:
    """Run optional semantic analysis while preserving all non-semantic facts.

    No analyzer is bundled or invoked implicitly. A caller must inject one and
    enable the service; the default disabled result remains usable by supply.
    """

    _SUPPORTED = frozenset({MediaType.IMAGE, MediaType.VIDEO})

    def __init__(
        self,
        store: AttemptMaterialStore,
        analyzer: MaterialSemanticAnalyzer | None = None,
        *,
        enabled: bool = False,
    ):
        self._store = store
        self._analyzer = analyzer
        self._enabled = enabled

    def enrich(self, asset: MaterialAsset, *, persist: bool = True) -> MaterialAsset:
        """Return one enriched asset; analyzer errors never discard the asset."""
        if not self._enabled or self._analyzer is None:
            updated = self._with_state(asset, IntelligenceStatus.DISABLED, "analyzer_disabled")
        elif asset.media_type not in self._SUPPORTED:
            updated = self._with_state(asset, IntelligenceStatus.DISABLED, "media_type_not_supported")
        else:
            updated = self._analyze(asset)
        if persist:
            self._store.write_asset(updated)
        return updated

    def enrich_many(
        self, assets: tuple[MaterialAsset, ...] | list[MaterialAsset], *, persist: bool = True
    ) -> tuple[MaterialAsset, ...]:
        """Enrich independently so one analyzer failure cannot abort other assets/Needs."""
        return tuple(self.enrich(asset, persist=persist) for asset in assets)

    def _analyze(self, asset: MaterialAsset) -> MaterialAsset:
        assert self._analyzer is not None
        analyzer_id = self._analyzer.analyzer_id
        if not isinstance(analyzer_id, str) or not analyzer_id.strip():
            return self._with_state(asset, IntelligenceStatus.FAILED, "analyzer_identity_invalid")
        try:
            path = self._store.resolve_asset_locator(asset.file.path)
            raw = self._analyzer.analyze(path, asset.media_type)
            output = SemanticAnalysisOutput.validate_output(raw)
            result_status = IntelligenceStatus.PARTIAL if output.partial else IntelligenceStatus.COMPLETE
            inference = SemanticInference(
                analyzer_id=analyzer_id.strip(),
                status=result_status,
                annotations=output.annotations,
            )
            return self._replace_inference(asset, inference, result_status, None)
        except Exception as exc:
            code = self._error_code(exc)
            inference = SemanticInference(
                analyzer_id=analyzer_id.strip(),
                status=IntelligenceStatus.FAILED,
                annotations=(),
                error_code=code,
            )
            return self._replace_inference(asset, inference, IntelligenceStatus.FAILED, code)

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "analyzer_output_invalid"
        if isinstance(exc, OSError):
            return "asset_unavailable_for_analysis"
        return "analyzer_failed"

    @staticmethod
    def _replace_inference(
        asset: MaterialAsset,
        inference: SemanticInference,
        status: IntelligenceStatus,
        error: str | None,
    ) -> MaterialAsset:
        retained = tuple(item for item in asset.semantic.inferences if item.analyzer_id != inference.analyzer_id)
        semantic = asset.semantic.model_copy(update={
            "intelligence_status": status,
            "intelligence_error": error,
            "inferences": retained + (inference,),
        })
        return asset.model_copy(update={"semantic": semantic})

    @staticmethod
    def _with_state(
        asset: MaterialAsset, status: IntelligenceStatus, error: str | None
    ) -> MaterialAsset:
        semantic = asset.semantic.model_copy(update={
            "intelligence_status": status,
            "intelligence_error": error,
        })
        return asset.model_copy(update={"semantic": semantic})
